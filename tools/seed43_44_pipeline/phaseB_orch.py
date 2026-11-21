"""Seed 44 phase B orchestrator (runs unattended on this PC, restartable; log: phaseB.log, state: phaseB_state.json).
 0. wait until the canonical S2 seed 44 re-run (17429) is on Drive: 12 group tars per task; relaunch missing groups when the S2 workers are idle
 1. start F1 LO on 17429 (parents staged by f1_assign44.py) and index the S2 children (stream the Drive tars, extract every balanced_train.parquet, md5)
 2. build the seed-44 download manifests (children point to the new S2 runs), stage children + manifest on 17804 and release F1 CQ (READY_CHILDREN)
 3. stage children + manifest on 17429 and release F1 LO
 4. PatchTST CQ children: per host stage children, write the phase-B chain (waits for the host's phase-A chain), launch
 5. when everything above is in place: replace the previous seed-44 S2 folders on Drive (trash) and update the reply document path.
Idempotent: every transfer is md5-checked and skipped when already on the host."""
from tempo_paths import REPO, S2, SSH_KEY
from tempo_paths import REPO, S2, SSH_KEY
import hashlib
import json
import os
import re
import subprocess
import sys
import tarfile
import time
import traceback
from pathlib import Path

D = Path(f'{S2}')
LOG = D / 'phaseB.log'
STATE = D / 'phaseB_state.json'
OUT = Path(S2).parent / 's2_44_children'
RC = ['rclone', '--drive-root-folder-id', '1GWiedVROrxp8jvGbd0xmvVmWriZUkpOn']
K = ['-i', f'{SSH_KEY}', '-o', 'ConnectTimeout=25', '-o', 'ServerAliveInterval=30', '-o', 'StrictHostKeyChecking=no', '-q']
IP = {'17429': '185.101.222.14', '17804': '185.101.222.14', '37740': '81.27.69.179', '37774': '81.27.69.179', '37901': '81.27.69.179', '37939': '81.27.69.179',
      '40066': '162.210.22.189', '40077': '162.210.22.189', '40081': '162.210.22.189', '40106': '162.210.22.189', '44016': '118.100.13.19'}
ENV = {'37740': '/workspace/CD3/.venv-cq', '37774': '/workspace/CD3/.venv-cq', '37939': '/workspace/CD3/lo_patchtst_seed42_code/venv_py312_20261107',
       '37901': '/workspace/cuda13_probe/venv', '40066': '/venv/main', '40077': '/venv/main', '40081': '/venv/main', '40106': '/venv/main', '44016': '/venv/main'}
LDD = {'37901': '/workspace/cuda13_probe/extracted/usr/local/cuda-13.0/compat'}
W = '/workspace/CD3'
NAME = {'LO': 'LO_V3_1', 'CQ': 'CQ_V2_2'}
REG = {'CQ': 'CQ_RAW_EARLY', 'LO': 'LO_FULL_EARLY'}
SRC = {t: Path(f'{REPO}/downloads/vastai/{NAME[t]}_clean_grain_seed42') for t in NAME}
PARENT = {'V2': 'V1', 'V3': 'V1', 'V4': 'V1', 'V6': 'V5', 'V7': 'V5', 'V8': 'V5', 'V10': 'V9', 'V11': 'V9', 'V12': 'V9', 'V14': 'V13', 'V15': 'V13', 'V16': 'V13'}
GROUPS = [(t, w, p) for t in ('LO', 'CQ') for w in ('W1', 'W2', 'W3') for p in ('V1', 'V5', 'V9', 'V13')]
S2DIR = 'L1_runs/S2_augmentation/seed44_17429_20261114'
PLAN = json.load(open(D / 'dispatch_plan_seed44_ptcq.json'))
SALT = {'LO': 'lo_static_v2_prediction_salt', 'CQ': 'mantis_cq_prediction_salt'}
state = json.load(open(STATE)) if STATE.exists() else {}


def log(m):
    with LOG.open('a', encoding='utf-8') as f:
        f.write(f'{time.strftime("%H:%M:%S")} {m}\n')
    print(m, flush=True)


def save():
    STATE.write_text(json.dumps(state, indent=1))


def run(port, cmd, timeout=3600):
    return subprocess.run(['ssh', '-n', *K, '-p', port, f'root@{IP[port]}', cmd], capture_output=True, text=True, timeout=timeout).stdout.replace('\r', '').strip()


def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(8 << 20), b''):
            h.update(b)
    return h.hexdigest()


def put(port, local, remote, h=None):
    h = h or md5(local)
    if run(port, f'md5sum {remote} 2>/dev/null | cut -c1-32') == h:
        return
    run(port, f'mkdir -p $(dirname {remote})')
    with open(local, 'rb') as fh:   # ssh pipe: measured 2 MB/s where scp of large files trickled
        subprocess.run(['ssh', *K, '-p', port, f'root@{IP[port]}', f'cat > {remote}.part'], stdin=fh, check=True, timeout=900)
    run(port, f'mv {remote}.part {remote}')
    assert run(port, f'md5sum {remote} | cut -c1-32') == h, ('md5 mismatch', port, remote)


def step(name, fn, tries=3):
    if state.get(name) == 'done':
        return True
    for i in range(tries):
        try:
            log(f'STEP {name} start (try {i + 1})')
            fn()
            state[name] = 'done'; save(); log(f'STEP {name} DONE')
            return True
        except Exception:
            log(f'STEP {name} ERROR {traceback.format_exc()[-600:]}')
            time.sleep(120)
    state[name] = 'failed'; save()
    return False


# ---------------------------------------------------------------- 0: S2 on Drive
def drive_groups(task):
    out = subprocess.run(RC + ['lsf', f'gdrive:{task}/{S2DIR}'], capture_output=True, text=True).stdout.split()
    return {x[:-4] for x in out if x.endswith('.tar')}


def relaunch_missing(missing):
    n = run('17429', "ps -eo args | grep -E 's2_canon.sh' | grep -v grep | wc -l")
    ready = run('17429', 'ls /workspace/CD3/s2_c44_*/ready/*.tar 2>/dev/null | wc -l')
    if n != '0' or ready != '0':
        return
    log(f'S2 workers idle but groups missing on Drive: {sorted(missing)} -> relaunch (r-workers)')
    for i, name in enumerate(sorted(missing)[:5]):
        t, w, p = name.split('_')
        d = f'{W}/s2_c44_r{i}'
        run('17429', f"mkdir -p {d} && cd {d} && for x in venv_old tools augmentation_core release_core; do ln -sfn {W}/s2/$x $x; done && ln -sfn {W}/s2/in in && cp {W}/s2_canon.sh . && rm -rf mnt done logs ready && mkdir -p mnt done logs ready && "
                       f"(nohup setsid bash {d}/s2_canon.sh {t}:{w}:{p} > worker.log 2>&1 < /dev/null &)")


def wait_s2():
    want = {f'{t}_{w}_{p}' for t, w, p in GROUPS}
    idle = 0
    while True:
        have = drive_groups('LO') | drive_groups('CQ')
        missing = want - have
        log(f'S2 on Drive: {len(want) - len(missing)}/24')
        if not missing:
            return
        idle += 1
        if idle % 3 == 0:
            relaunch_missing(missing)
        time.sleep(240)


# ---------------------------------------------------------------- 1: index children
KEYRE = re.compile(r'task=(\w+)/.*?window_id=(W\d)/.*?pipeline_id=(V\d+)/.*?run_id=([0-9a-f]+)/attempt_id=([^/]+)/balanced_train\.parquet$')


def index_children():
    idx = json.load(open(OUT / 'index.json')) if (OUT / 'index.json').exists() else {}
    OUT.mkdir(parents=True, exist_ok=True)
    for t, w, p in GROUPS:
        kids = [c for c, par in PARENT.items() if par == p]
        if all(f'{t}|{w}|{c}' in idx and (OUT / t / w / c / 'balanced_train.parquet').exists() for c in kids):
            continue
        proc = subprocess.Popen(RC + ['--timeout', '90s', '--low-level-retries', '3', 'cat', f'gdrive:{t}/{S2DIR}/{t}_{w}_{p}.tar'], stdout=subprocess.PIPE)
        with tarfile.open(fileobj=proc.stdout, mode='r|') as tf:
            for m in tf:
                mm = KEYRE.search(m.name)
                if not mm:
                    continue
                tk, wk, vk, rid, aid = mm.groups()
                dest = OUT / tk / wk / vk / 'balanced_train.parquet'
                dest.parent.mkdir(parents=True, exist_ok=True)
                with open(dest, 'wb') as f:
                    h = hashlib.md5()
                    src = tf.extractfile(m)
                    for b in iter(lambda: src.read(8 << 20), b''):
                        f.write(b); h.update(b)
                idx[f'{tk}|{wk}|{vk}'] = {'run_id': rid, 'attempt_id': aid, 'md5': h.hexdigest(), 'size': dest.stat().st_size}
                if all(f'{t}|{w}|{c}' in idx for c in kids):
                    break
        proc.kill()
        (OUT / 'index.json').write_text(json.dumps(idx, indent=1))
        log(f'indexed {t} {w} {p}')
    missing = [f'{t}|{w}|{c}' for t, w, p in GROUPS for c, par in PARENT.items() if par == p and f'{t}|{w}|{c}' not in idx]
    assert not missing, missing


def idx_load():
    return json.load(open(OUT / 'index.json'))


def build_manifest(task):
    idx = idx_load()
    dm = json.loads((SRC[task] / 'download_manifest.json').read_text(encoding='utf-8'))
    n = 0
    for f in dm['files']:
        if f['kind'] == 'train' and f['pipeline_id'] in PARENT:
            e = idx[f"{task}|{f['window_id']}|{f['pipeline_id']}"]
            f['remote_path'] = (f"meta_release=imputation-v1/L1_runs/task={task}/feature_regime={REG[task]}/window_id={f['window_id']}/phase_id=P4/pipeline_id={f['pipeline_id']}/"
                                f"model_name=BALANCED_TRAIN_ONLY/seed=44/run_id={e['run_id']}/attempt_id={e['attempt_id']}/balanced_train.parquet")
            n += 1
    assert n == 36, n
    dm['seed_note'] = 'Seed-44 data root: balanced TRAIN paths point to the seed-44 S2 runs of the canonical re-run (MATCH_MASTER_SEED); parents and evaluation as in seed 42.'
    p = D / f'download_manifest_{task}_seed44.json'
    p.write_text(json.dumps(dm, indent=2), encoding='utf-8')
    return p


def stage_children(port, task, cells, with_parent_eval=True):
    """cells = [(window, child)]"""
    idx = idx_load()
    root = f'{W}/data/{NAME[task]}_clean_grain_seed44'
    mp = build_manifest(task)
    for w, c in cells:
        par = PARENT[c]
        if with_parent_eval:
            for f in sorted((SRC[task] / 'evaluation' / w / par).glob('*.parquet')):
                put(port, f, f'{root}/evaluation/{w}/{par}/{f.name}')
        e = idx[f'{task}|{w}|{c}']
        put(port, OUT / task / w / c / 'balanced_train.parquet', f'{root}/train/{w}/{c}/balanced_train.parquet', e['md5'])
        run(port, f'mkdir -p {W}/staged44 && touch {W}/staged44/{task}_{w}_{c}')
        log(f'staged child {port} {task} {w} {c}')
    put(port, mp, f'{root}/download_manifest.json')


# ---------------------------------------------------------------- F1 helpers
def release_f1(port, task):
    """Window by window: after W1 the children are released (F1 needs hours for the W1 children, W2/W3 arrive meanwhile)."""
    root = f'{W}/data/{NAME[task]}_clean_grain_seed44'
    for w in ('W1', 'W2', 'W3'):
        stage_children(port, task, [(w, c) for c in PARENT])
        if w == 'W1':
            run(port, f'touch {root}/READY_CHILDREN')
            log(f'F1 {task} children released on {port} after W1 (W2, W3 follow)')
    log(f'F1 {task} all children staged on {port}')


def overlay_audit(port):
    """The repo checkout of the hosts (5ba9829) lacks --s-leak-source/--probe-mode: copy the committed audit files (HEAD 2152d49+) before the first audit; training files are untouched."""
    for rel in ('tools/vastai_audit_shared.py', 'metrics_core/evaluation.py'):
        run(port, f'cd {W}/repo43 && test -f {rel}.orig || cp {rel} {rel}.orig')
        subprocess.run(['scp', '-q', *K, '-P', port, f'{REPO}/{rel}', f'root@{IP[port]}:{W}/repo43/{rel}'], check=True)
    out = run(port, f'cd {W}/repo43 && PYTHONPATH={W}/repo43 {ENV.get(port, "/venv/main")}/bin/python -c "import tools.vastai_audit_shared as m; print(\'AUDIT_IMPORT_OK\')" 2>&1 | tail -n 1')
    log(f'audit overlay on {port}: {out}')
    assert 'AUDIT_IMPORT_OK' in out, out


# ---------------------------------------------------------------- 4: PatchTST CQ children
def pt_children_host(port):
    p = PLAN[port]
    cells = [tuple(c.split(':')) for c in p['pt_children']]   # (CQ, W, child, parent)
    if not cells:
        return
    stage_children(port, 'CQ', [(w, c) for (_t, w, c, _p) in cells])
    envroot = ENV[port]
    root = f'{W}/data/CQ_V2_2_clean_grain_seed44'
    out = f'{W}/runs/patchtst_cq_seed44'
    L = ['#!/bin/bash', 'set -uo pipefail', f'cd {W}']
    if port in LDD:
        L.append(f'export LD_LIBRARY_PATH="{LDD[port]}:${{LD_LIBRARY_PATH:-}}"')
    L.append('quiet=0; while [ $quiet -lt 3 ]; do if ps -eo args | grep -E "[s]eed44_phaseA_' + port + '|[v]astai_train_shared|[r]un_pt_lo43|[r]un_mantis_grid" >/dev/null; then quiet=0; else quiet=$((quiet+1)); fi; sleep 60; done')
    for (_t, w, c, _p) in cells:
        L.append(f'while ! test -e {W}/staged44/CQ_{w}_{c}; do sleep 60; done')
        L.append(f'if ! test -f {out}/CQ/{w}/{c}/PATCHTST/seed=44/run_manifest.json; then echo "START PT CQ {w} {c} $(date -Is)"; mkdir -p {out}/logs; '
                 f'( source {envroot}/bin/activate; cd {W}/repo43; export PYTHONPATH={W}/repo43; export TEMPO_PREDICTION_SALT="$(cat {W}/{SALT["CQ"]})"; echo "RUNNER_COMMIT $(git rev-parse --short HEAD)"; '
                 f'python -u tools/vastai_train_shared.py --task CQ --data-root {root} --output-root {out} --window {w} --pipeline-id {c} --model-name PATCHTST --seed 44 --batch-size 2048 '
                 f'--accumulation-steps 4 --workers 2 --max-epochs 50 --patience 5 --static-layout-policy current --energy-sampling-interval-seconds 1.0 ) > {out}/logs/{w}_{c}.log 2>&1 '
                 f'&& echo "DONE PT CQ {w} {c} $(date -Is)" || echo "FAILED PT CQ {w} {c} $(date -Is)"; fi')
    L.append('echo SEED44_PT_CQ_CHILDREN_DONE')
    name = f'seed44_phaseB_{port}.sh'
    (D / name).write_bytes(('\n'.join(L) + '\n').encode())
    subprocess.run(['scp', '-q', *K, '-P', port, str(D / name), f'root@{IP[port]}:{W}/{name}'], check=True)
    if run(port, f'ps -eo args | grep -c "[s]eed44_phaseB_{port}"') == '0':
        log(f'phase B chain {port}: ' + run(port, f'cd {W} && bash -n {name} && (nohup setsid bash {name} > {name}.log 2>&1 < /dev/null &); sleep 2; ps -eo args | grep -c "[s]eed44_phaseB_{port}"'))


# ---------------------------------------------------------------- 5: replace the old S2 folders
def replace_old_drive():
    for t in ('CQ', 'LO'):
        new = drive_groups(t)
        assert len(new) == 12, (t, len(new))
        old = f'gdrive:{t}/L1_runs/S2_augmentation/seed44_raw_outputs_20261113'
        r = subprocess.run(RC + ['lsf', old], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            subprocess.run(RC + ['purge', old], check=True)    # goes to the Drive trash
            log(f'old seed-44 raw outputs removed from Drive: {t}')


def update_doc():
    p = Path(f'{REPO}/docs/13112026/PHAN_HOI_YEU_CAU_13-11_2026-11-13.md')
    s = p.read_bytes().decode('utf-8')
    if 'seed44_raw_outputs_20261113' in s:
        s = s.replace('`…/L1_runs/S2_augmentation/seed44_raw_outputs_20261113/`', '`…/L1_runs/S2_augmentation/seed44_17429_20261114/` (mỗi task)')
        p.write_bytes(s.encode('utf-8'))
        log('reply document path updated (md); docx to be rebuilt')


if __name__ == '__main__':
    log('ORCH_START')
    step('wait_s2', wait_s2, tries=1)
    # F1 LO: parents staged and launched on 17429 while the children are being indexed
    if state.get('f1_lo_launch') != 'done':
        subprocess.Popen([sys.executable, str(D / 'f1_assign44.py'), 'LO', '17429', '/venv/main'], stdout=open(D / 'f1_assign_lo.out', 'w'), stderr=subprocess.STDOUT)
        state['f1_lo_launch'] = 'done'; save(); log('F1 LO staging/launch started on 17429')
    step('index_children', index_children)
    step('overlay_17804', lambda: overlay_audit('17804'))
    step('release_f1_cq', lambda: release_f1('17804', 'CQ'))
    # the F1 LO driver must have launched the script before the audit overlay on 17429
    step('overlay_17429', lambda: (time.sleep(1), overlay_audit('17429')))
    step('release_f1_lo', lambda: release_f1('17429', 'LO'))
    for port in ('37740', '40066', '40106', '37901', '40081', '37939', '40077', '37774', '44016'):
        step(f'pt_children_{port}', lambda port=port: pt_children_host(port))
    ok = all(state.get(k) == 'done' for k in ('index_children', 'release_f1_cq', 'release_f1_lo'))
    if ok:
        step('replace_old_drive', replace_old_drive, tries=1)
        step('update_doc', update_doc, tries=1)
    log('ORCH_END ' + json.dumps({k: v for k, v in state.items()}))
