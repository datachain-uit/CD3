"""When an F1 host is finished (F1 + audits), put it to work on PatchTST seed 44.
 17804 (CQ data and all CQ children already staged): steals the LAST not-yet-started child cell of the busiest PatchTST CQ host (renames its 'staged44' flag so the donor chain never starts it), runs it, repeats.
 17429 (LO data and all LO children already staged): runs the PatchTST LO seed-44 cells (parents first), cell by cell, skipping cells with a run_manifest.json.
Never touches a running training. Log: steal44.log.   usage: steal44.py cq_17804 | lo_17429"""
from tempo_paths import S2, SSH_KEY, hosts
import json
import subprocess
import sys
import time
from pathlib import Path

D = Path(f'{S2}')
LOG = D / 'steal44.log'
K = ['-i', f'{SSH_KEY}', '-o', 'ConnectTimeout=25', '-o', 'ServerAliveInterval=30', '-o', 'StrictHostKeyChecking=no', '-q']
IP = hosts()   # {port: ip} of the rented hosts, from TEMPO_HOSTS_JSON (not committed)
W = '/workspace/CD3'
PLAN = json.load(open(D / 'dispatch_plan_seed44_ptcq.json'))
SALT = {'LO': 'lo_static_v2_prediction_salt', 'CQ': 'mantis_cq_prediction_salt'}
NAME = {'LO': 'LO_V3_1', 'CQ': 'CQ_V2_2'}
PTX = {'LO': '--run-purpose PRIMARY_GRID --augmentation-seed-policy match_model_seed ', 'CQ': ''}


def log(m):
    with LOG.open('a', encoding='utf-8') as f:
        f.write(f'{time.strftime("%H:%M:%S")} {m}\n')
    print(m, flush=True)


def run(port, cmd, timeout=300):
    try:
        return subprocess.run(['ssh', '-n', *K, '-p', port, f'root@{IP[port]}', cmd], capture_output=True, text=True, timeout=timeout).stdout.replace('\r', '').strip()
    except Exception as e:  # noqa: BLE001
        return 'ERR ' + type(e).__name__


def host_free(port):
    """F1 grid script, training and audit all gone (3 consecutive looks)."""
    for _ in range(3):
        n = run(port, 'ps -eo args | grep -E "[v]astai_run_f1_grid|[v]astai_train_shared|[v]astai_audit_shared|[s]eed44_steal" | wc -l')
        if n != '0':
            return False
        time.sleep(20)
    return True


def cell_cmd(t, w, v):
    root = f'{W}/data/{NAME[t]}_clean_grain_seed44'
    out = f'{W}/runs/patchtst_{t.lower()}_seed44'
    return (f'mkdir -p {out}/logs; ( source /venv/main/bin/activate; cd {W}/repo43; export PYTHONPATH={W}/repo43; export TEMPO_PREDICTION_SALT="$(cat {W}/{SALT[t]})"; echo "RUNNER_COMMIT $(git rev-parse --short HEAD)"; '
            f'python -u tools/vastai_train_shared.py --task {t} --data-root {root} --output-root {out} --window {w} --pipeline-id {v} --model-name PATCHTST --seed 44 --batch-size 2048 '
            f'--accumulation-steps 4 --workers 2 --max-epochs 50 --patience 5 --static-layout-policy current {PTX[t]}--energy-sampling-interval-seconds 1.0 ) > {out}/logs/{w}_{v}.log 2>&1 '
            f'&& echo "DONE PT {t} {w} {v} $(date -Is)" || echo "FAILED PT {t} {w} {v} $(date -Is)"')


def run_cell(port, t, w, v):
    """Runs one cell in a detached remote script and waits for it; returns the last line of its log."""
    name = f'seed44_steal_{port}_{t}_{w}_{v}.sh'
    mf = f'{W}/runs/patchtst_{t.lower()}_seed44/{t}/{w}/{v}/PATCHTST/seed=44/run_manifest.json'
    body = f'#!/bin/bash\ncd {W}\nif ! test -f {mf}; then echo "START PT {t} {w} {v} $(date -Is)"; {cell_cmd(t, w, v)}; fi\n'
    p = D / name
    p.write_bytes(body.encode())
    subprocess.run(['scp', '-q', *K, '-P', port, str(p), f'root@{IP[port]}:{W}/{name}'], check=True)
    run(port, f'cd {W} && (nohup setsid bash {name} > {name}.log 2>&1 < /dev/null &); sleep 3')
    log(f'{port}: started PatchTST {t} {w} {v}')
    while True:
        time.sleep(120)
        if run(port, f'ps -eo args | grep -c "[s]eed44_steal_{port}_{t}_{w}_{v}"') == '0':
            break
    res = run(port, f'tail -n1 {W}/{name}.log')
    log(f'{port}: {t} {w} {v} -> {res}')
    return res


def donor_candidate():
    best = None
    for port, p in PLAN.items():
        cells = [tuple(c.split(':')) for c in p['pt_children']]       # (CQ, W, child, parent)
        names = ' '.join(f'CQ_{w}_{c}' for (_t, w, c, _p) in cells)
        out = run(port, f'for f in {names}; do w=$(echo $f | cut -d_ -f2); c=$(echo $f | cut -d_ -f3); '
                        f'echo "$f $(test -e {W}/staged44/$f && echo F || echo -) $(test -f {W}/runs/patchtst_cq_seed44/CQ/$w/$c/PATCHTST/seed=44/run_manifest.json && echo M || echo -) '
                        f'$(test -e {W}/runs/patchtst_cq_seed44/logs/${{w}}_$c.log && echo L || echo -)"; done')
        if out.startswith('ERR') or not out:
            continue
        st = {line.split()[0]: line.split()[1:] for line in out.splitlines() if line.strip()}
        unstarted = [(w, c) for (_t, w, c, _p) in cells if st.get(f'CQ_{w}_{c}') == ['F', '-', '-']]
        if unstarted and (best is None or len(unstarted) > best[1]):
            best = (port, len(unstarted), unstarted[-1])
    return best


def steal_cq(thief):
    while True:
        b = donor_candidate()
        if b is None:
            log(f'{thief}: nothing left to steal')
            return
        donor, n, (w, c) = b
        flag = f'{W}/staged44/CQ_{w}_{c}'
        run(donor, f'mv {flag} {flag}.stolen_by_{thief}')
        if run(donor, f'test -e {W}/runs/patchtst_cq_seed44/logs/{w}_{c}.log && echo STARTED') == 'STARTED':     # lost the race: the donor had already begun it
            run(donor, f'mv {flag}.stolen_by_{thief} {flag}')
            log(f'race lost on {donor} CQ {w} {c}')
            time.sleep(60)
            continue
        log(f'{thief}: took CQ {w} {c} from {donor} (donor had {n} unstarted)')
        if 'FAILED' in run_cell(thief, 'CQ', w, c):
            log(f'{thief}: FAILED CQ {w} {c}; flag handed back to {donor}')
            run(donor, f'mv {flag}.stolen_by_{thief} {flag}')
            return


def run_lo(host):
    order = [(w, v) for v in ('V0', 'V1', 'V5', 'V9', 'V13') for w in ('W1', 'W2', 'W3')] + [(w, f'V{i}') for i in (2, 3, 4, 6, 7, 8, 10, 11, 12, 14, 15, 16) for w in ('W1', 'W2', 'W3')]
    for w, v in order:
        if run(host, f'test -f {W}/runs/patchtst_lo_seed44/LO/{w}/{v}/PATCHTST/seed=44/run_manifest.json && echo M') == 'M':
            continue
        if 'FAILED' in run_cell(host, 'LO', w, v):
            log(f'{host}: FAILED LO {w} {v}; stopping')
            return
    log(f'{host}: LO list finished')


if __name__ == '__main__':
    job = sys.argv[1]
    if job == 'cq_17804':
        while not host_free('17804'):
            time.sleep(300)
        log('17804 free -> steal PatchTST CQ cells')
        steal_cq('17804')
    elif job == 'lo_17429':
        while not host_free('17429'):
            time.sleep(300)
        log('17429 free -> PatchTST LO seed 44')
        run_lo('17429')
