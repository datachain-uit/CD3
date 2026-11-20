"""Seed 44, task CQ: unified work queue for the hosts that become free. Priority: (1) PatchTST CQ cells that no host has started yet (taken from the busiest donor by renaming its 'staged44'
flag, so the donor chain never starts them), (2) Mantis LO groups = one parent pipeline (V0/V1/V5/V9/V13) of one window plus its three balanced children in that window.
One worker thread per host; a host takes work only when nothing runs on it (3 looks) and its own chain has no unstarted flagged cell. Uplink transfers are serialised (global lock).
Mantis group: stage data -> lo44_mantis_parent.sh V W -> lo44_mantis_child.sh child V W for each child -> tars in /workspace/CD3/runs/mantis_lo44_*_results.tar.gz (kept; upload later) -> remove the group's work dirs.
Never touches a running training. Log: lo_workers44.log, state: lo_workers44_state.json.   usage: lo_workers44.py PORT [PORT ...]"""
from tempo_paths import S2
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, f'{S2}')
import phaseB_orch as B  # noqa: E402
import steal44 as S  # noqa: E402

B.IP.update(S.IP)   # host addresses of steal44 (TEMPO_HOSTS_JSON) are also the ones phaseB_orch uses

D = Path(f'{S2}')
LOGF = D / 'lo_workers44.log'
STATEF = D / 'lo_workers44_state.json'
W = '/workspace/CD3'
B.ENV['37835'] = '/workspace/cuda13_probe/venv'
B.LDD['37835'] = '/workspace/cuda13_probe/extracted/usr/local/cuda-13.0/compat'
NO_PT = set()
EXPENSIVE = set()    # user 18/11: 40077/40081/40106 stay on until Mantis LO is finished (40066 is stopped)
LOCK = threading.Lock()          # queue + flag renames
RELAY = threading.Lock()         # slow PC relay of a parent cache (one at a time) - does not block the small data staging
import collections
UPLOCK = collections.defaultdict(threading.Lock)   # one transfer per HOST at a time, different hosts in parallel
UPLINK = threading.Lock()        # one transfer at a time
PARENTS = ['V0', 'V1', 'V5', 'V9', 'V13']
KIDS = {p: [c for c, par in B.PARENT.items() if par == p] for p in PARENTS}
GROUPS = [(v, w) for w in ('W1', 'W2', 'W3') for v in PARENTS]
ALLOW = {'44016': {'W1', 'W2'}}   # 40066: thermally throttled, user wants it stopped after its current training -> it takes no new work      # 44016 has a 21 GB RAM limit: a W3 PatchTST cell was OOM-killed there (2026-11-16), so only W1 work goes to it
MANTIS_FIRST = set()      # user (2026-11-16): after its current PatchTST cell 40081 runs Mantis (not more PatchTST)
PARTIAL_MV = ('d=' + W + '/runs/patchtst_cq_seed44/CQ/{w}/{c}; if test -d $d && ! test -f $d/PATCHTST/seed=44/run_manifest.json; then mv $d $d.partial_$(date +%s); fi; ')
PROC = '[v]astai_train_shared|[v]astai_audit_shared|[r]un_mantis_grid_zstd|[s]eed44_steal|[s]eed44_mantis|[c]q44_mantis|[l]o44_mantis|[s]eed44_lo_chain|[s]eed44_lo_patch'


def log(m):
    with LOGF.open('a', encoding='utf-8') as f:
        f.write(f'{time.strftime("%H:%M:%S")} {m}\n')
    print(m, flush=True)


def state():
    return json.loads(STATEF.read_text()) if STATEF.exists() else {}


def set_state(k, v):
    with LOCK:
        s = state()
        s[k] = v
        STATEF.write_text(json.dumps(s, indent=1))


def pending(port):
    """unstarted cells of this host's own PatchTST CQ child list that still have their flag"""
    if port not in S.PLAN:
        return []
    cells = [tuple(c.split(':')) for c in S.PLAN[port]['pt_children']]
    names = ' '.join(f'CQ_{w}_{c}' for (_t, w, c, _p) in cells)
    out = S.run(port, f'for f in {names}; do w=$(echo $f | cut -d_ -f2); c=$(echo $f | cut -d_ -f3); '
                      f'echo "$f $(test -e {W}/staged44/$f && echo F || echo -) $(test -f {W}/runs/patchtst_cq_seed44/CQ/$w/$c/PATCHTST/seed=44/run_manifest.json && echo M || echo -) '
                      f'$(test -e {W}/runs/patchtst_cq_seed44/logs/${{w}}_$c.log && echo L || echo -)"; done')
    if out.startswith('ERR') or not out:
        return None
    st = {line.split()[0]: line.split()[1:] for line in out.splitlines() if line.strip()}
    return [(w, c) for (_t, w, c, _p) in cells if st.get(f'CQ_{w}_{c}') == ['F', '-', '-']]


def host_free(port):
    for _ in range(3):
        if S.run(port, f'ps -eo args | grep -E "{PROC}" | wc -l') != '0':
            return False
        time.sleep(20)
    p = pending(port)
    return p == [] if p is not None else False


def free_gb(port):
    v = S.run(port, "df -Pk /workspace | awk 'NR==2{print int($4/1048576)}'")
    return int(v) if v.isdigit() else 0


def script_run(port, name, body, tail_ok):
    """run a bash body as a detached remote script, wait for it, return (ok, last log line)"""
    hdr = '#!/bin/bash\ncd /workspace/CD3\n' + (f'export LD_LIBRARY_PATH="{B.LDD[port]}:${{LD_LIBRARY_PATH:-}}"\n' if port in B.LDD else '')
    p = D / name
    p.write_bytes((hdr + body + '\n').encode())
    subprocess.run(['scp', '-q', *S.K, '-P', port, str(p), f'root@{S.IP[port]}:{W}/{name}'], check=True)
    S.run(port, f'cd {W} && (nohup setsid bash {name} > {name}.log 2>&1 < /dev/null &); sleep 3')
    while True:
        time.sleep(120)
        if S.run(port, f'ps -eo args | grep -c "[b]ash {name}"') == '0':
            break
    last = S.run(port, f'tail -n2 {W}/{name}.log').replace('\n', ' | ')
    return tail_ok in last, last


def take_pool_cell(port):
    """cells given back by closed hosts (state keys 'PTQ|<W>|<V>' = 'queued'); run on this host (data staged from the PC)"""
    with LOCK:
        s = state()
        pick = None
        for k, val in s.items():
            if k.startswith('PTQ|') and val == 'queued':
                w, c = k.split('|')[1:]
                if w in ALLOW.get(port, ('W1', 'W2', 'W3')) and s.get(f'PTFAIL|{w}|{c}', 0) < 2 and (B.OUT / 'CQ' / w / c / 'balanced_train.parquet').exists():
                    pick = (k, w, c)
                    break
        if pick is None:
            return False
        s[pick[0]] = f'running on {port}'
        STATEF.write_text(json.dumps(s, indent=1))
    k, w, c = pick
    log(f'{port}: took requeued PatchTST CQ {w} {c}')
    try:
        with UPLOCK[port]:
            B.stage_children(port, 'LO', [(w, c)])
    except Exception as e:  # noqa: BLE001
        log(f'{port}: staging failed {type(e).__name__}: {e}; cell put back')
        set_state(k, 'queued')
        return True
    env = B.ENV.get(port, '/venv/main')
    mf = f'{W}/runs/patchtst_cq_seed44/CQ/{w}/{c}/PATCHTST/seed=44/run_manifest.json'
    body = PARTIAL_MV.format(w=w, c=c) + f'if ! test -f {mf}; then echo "START PT CQ {w} {c} $(date -Is)"; {S.cell_cmd("CQ", w, c).replace("/venv/main", env)}; else echo "DONE PT already {w} {c}"; fi'
    ok, last = script_run(port, f'seed44_steal_{port}_CQ_{w}_{c}_q.sh', body, 'DONE PT')
    log(f'{port}: requeued PatchTST CQ {w} {c} -> {last}')
    if ok:
        set_state(k, f'done on {port}')
    else:
        set_state(k, 'queued')
        set_state(f'PTFAIL|{w}|{c}', state().get(f'PTFAIL|{w}|{c}', 0) + 1)
    return True


def take_pt_cell(port):
    return False          # PatchTST LO is run by the other session's chains
    if port in NO_PT:
        return False
    if take_pool_cell(port):
        return True
    best = None
    for dport in S.PLAN:
        if dport == port:
            continue
        p = [x for x in (pending(dport) or []) if x[0] in ALLOW.get(port, ('W1', 'W2', 'W3')) and state().get(f'PTFAIL|{x[0]}|{x[1]}', 0) < 2]
        if p and (best is None or len(p) > best[1] or dport in ('40081', '40066')):      # take 40066's unstarted cells first (it is slow), so it ends after its current cell
            best = (dport, len(p), p[-1])
            if dport in ('40081', '40066'):
                break
    if best is None:
        return False
    donor, n, (w, c) = best
    flag = f'{W}/staged44/CQ_{w}_{c}'
    with LOCK:
        S.run(donor, f'mv {flag} {flag}.stolen_by_{port}')
        if S.run(donor, f'test -e {W}/runs/patchtst_cq_seed44/logs/{w}_{c}.log && echo STARTED') == 'STARTED':
            S.run(donor, f'mv {flag}.stolen_by_{port} {flag}')
            log(f'race lost {donor} CQ {w} {c}')
            return True
    log(f'{port}: took PatchTST CQ {w} {c} from {donor} ({n} unstarted there)')
    try:
        with UPLOCK[port]:
            B.stage_children(port, 'LO', [(w, c)])
    except Exception as e:  # noqa: BLE001
        log(f'{port}: staging failed {type(e).__name__}: {e}; flag handed back')
        S.run(donor, f'mv {flag}.stolen_by_{port} {flag}')
        return True
    env = B.ENV.get(port, '/venv/main')
    mf = f'{W}/runs/patchtst_cq_seed44/CQ/{w}/{c}/PATCHTST/seed=44/run_manifest.json'
    body = PARTIAL_MV.format(w=w, c=c) + f'if ! test -f {mf}; then echo "START PT CQ {w} {c} $(date -Is)"; {S.cell_cmd("CQ", w, c).replace("/venv/main", env)}; else echo "DONE PT already {w} {c}"; fi'
    ok, last = script_run(port, f'seed44_steal_{port}_CQ_{w}_{c}.sh', body, 'DONE PT')
    log(f'{port}: PatchTST CQ {w} {c} -> {last}')
    if not ok:
        S.run(donor, f'mv {flag}.stolen_by_{port} {flag}')
        set_state(f'PTFAIL|{w}|{c}', state().get(f'PTFAIL|{w}|{c}', 0) + 1)
    return ok


def stage_parent(port, v, w):
    root = f'{W}/data/LO_V3_1_clean_grain_seed44'
    with UPLOCK[port]:
        for ww in sorted({w, 'W1'}):          # lo44_mantis_parent.sh always runs its smoke test on W1 of the parent
            for sub in ('train', 'evaluation'):
                for f in sorted((B.SRC['LO'] / sub / ww / v).glob('*.parquet')):
                    B.put(port, f, f'{root}/{sub}/{ww}/{v}/{f.name}')
        B.put(port, B.build_manifest('LO'), f'{root}/download_manifest.json')
    for f in ('lo44_mantis_parent.sh', 'lo44_mantis_child.sh'):
        subprocess.run(['scp', '-q', *S.K, '-P', port, str(D / f), f'root@{S.IP[port]}:{W}/{f}'], check=True)


def tar_ok(port, name):
    return S.run(port, f'test -s {W}/runs/{name} && tar -tzf {W}/runs/{name} >/dev/null 2>&1 && echo OK') == 'OK'


def run_parent(port, v, w):
    key = f'P|{v}|{w}'
    env = B.ENV.get(port, '/venv/main')
    log(f'{port}: Mantis LO PARENT {v} {w}')
    stage_parent(port, v, w)
    ok, last = script_run(port, f'seed44_mantis_{port}_{v}_{w}.sh', f'ENVROOT={env} MIN_FREE_KB=7000000 bash lo44_mantis_parent.sh {v} {w}', f'RESULTS_READY LO44 {v}')
    log(f'{port}: parent {v} {w} -> {last}')
    if not (ok and tar_ok(port, f'mantis_lo44_{v}_{w}_20261114_results.tar.gz')):
        set_state(key, f'FAILED on {port}')
        return False
    if not KIDS[v]:
        S.run(port, f'cd {W} && rm -rf mantis_lo44_{v}_20261114', timeout=900)      # V0 has no children: the cache is not needed any more
    set_state(key, f'done on {port}')
    return True


def run_child(port, c, v, w):
    key = f'C|{c}|{w}'
    env = B.ENV.get(port, '/venv/main')
    log(f'{port}: Mantis LO child {c} {w} (parent {v})')
    with UPLOCK[port]:
        B.stage_children(port, 'LO', [(w, c)])
    ok, last = script_run(port, f'seed44_mantis_{port}_{c}_{w}.sh', f'V={c} PARENT={v} WINDOWS={w} ENVROOT={env} bash lo44_mantis_child.sh', f'RESULTS_READY LO44 {c}')
    log(f'{port}: child {c} {w} -> {last}')
    if not (ok and tar_ok(port, f'mantis_lo44_{c}_{w}_20261114_results.tar.gz')):
        set_state(key, f'FAILED on {port}')
        return False
    S.run(port, f'cd {W} && rm -rf mantis_lo44_{c}_20261114', timeout=900)
    set_state(key, f'done on {port}')
    s = state()
    if all(s.get(f'C|{k}|{w}', '').startswith('done') for k in KIDS[v]):
        S.run(port, f'cd {W} && rm -rf mantis_lo44_{v}_20261114/cache/task=LO/window={w}; ls mantis_lo44_{v}_20261114/cache/task=LO 2>/dev/null | grep -q window= || rm -rf mantis_lo44_{v}_20261114', timeout=900)         # all children of this parent window are finished: drop the parent cache of THIS window only
        log(f'{port}: parent cache {v} {w} removed (children done)')
    return True


PRIORITY = [('V9', 'W3'), ('V13', 'W3'), ('V1', 'W3'), ('V5', 'W3'), ('V9', 'W2'), ('V13', 'W2'), ('V0', 'W3')]


def next_parent(port):
    with LOCK:
        s = state()
        for k, val in s.items():            # parents reserved for this host by the user
            if val == f'queued for {port}':
                s[k] = f'running on {port}'
                STATEF.write_text(json.dumps(s, indent=1))
                return tuple(k.split('|')[1:])
        if port in NO_PT:
            return None
        # user (18/11): schedule the remaining parents longest-chain first (W3 parents take 3.7 h + 3 children, V0 has no children)
        for v, w in PRIORITY:
            if w in ALLOW.get(port, ('W1', 'W2', 'W3')) and f'P|{v}|{w}' not in s:
                s[f'P|{v}|{w}'] = f'running on {port}'
                STATEF.write_text(json.dumps(s, indent=1))
                return v, w
        for w in ('W1', 'W2', 'W3'):
            if w not in ALLOW.get(port, ('W1', 'W2', 'W3')):
                continue
            for v in PARENTS:
                if f'P|{v}|{w}' not in s:
                    s[f'P|{v}|{w}'] = f'running on {port}'
                    STATEF.write_text(json.dumps(s, indent=1))
                    return v, w
    return None


NEED_GB = {'W1': 7, 'W2': 7, 'W3': 7}      # observed child caches: 7-9 GB (W1/W2), W3 larger


def next_child(port):
    """a child of a parent window whose cache is on THIS host (only if the disk can hold the child cache; otherwise a roomier host takes it via replica)"""
    fg = free_gb(port)
    with LOCK:
        s = state()
        # user (16/11): parents first, children only after every parent window has been taken
        if any(f'P|{v}|{w}' not in s for w in ALLOW.get(port, ('W1', 'W2', 'W3')) for v in PARENTS):   # only parents this host could take
            return None
        for w in ('W1', 'W2', 'W3'):
            for v in PARENTS:
                if s.get(f'P|{v}|{w}') == f'done on {port}':
                    if fg < NEED_GB[w]:
                        continue
                    for c in KIDS[v]:
                        if f'C|{c}|{w}' not in s:
                            s[f'C|{c}|{w}'] = f'running on {port}'
                            STATEF.write_text(json.dumps(s, indent=1))
                            return c, v, w
    return None


def take_replica_child(port):
    """user (16/11, away 8 h): spread the children evenly. An idle host copies the cache of one parent window from a busy owner (via the PC) and takes children of it."""
    fg = free_gb(port)
    with LOCK:
        s = state()
        if any(f'P|{v}|{w}' not in s for w in ALLOW.get(port, ('W1', 'W2', 'W3')) for v in PARENTS):
            return None
        for k, val in s.items():                                   # a replica already on this host
            if k.startswith('RC|') and k.endswith(f'|{port}') and val == 'ready':
                _, v, w, _p = k.split('|')
                if fg < NEED_GB[w]:
                    continue
                for c in KIDS[v]:
                    if f'C|{c}|{w}' not in s:
                        s[f'C|{c}|{w}'] = f'running on {port}'
                        STATEF.write_text(json.dumps(s, indent=1))
                        return c, v, w
        best = None
        for w in ALLOW.get(port, ('W1', 'W2', 'W3')):
            for v in PARENTS:
                own = s.get(f'P|{v}|{w}', '')
                if not own.startswith('done on ') or own == f'done on {port}' or fg < NEED_GB[w] + 3:
                    continue
                pend = [c for c in KIDS[v] if f'C|{c}|{w}' not in s]
                if len(pend) >= 1 and not any(k.startswith(f'RC|{v}|{w}|') and (val == 'copying' or k.endswith(f'|{port}')) for k, val in s.items()) and (best is None or len(pend) > best[0]):
                    best = (len(pend), v, w, own.split()[-1])
        if best is None:
            return None
        _n, v, w, owner = best
        s[f'RC|{v}|{w}|{port}'] = 'copying'
        STATEF.write_text(json.dumps(s, indent=1))
    log(f'{port}: replicating parent cache {v} {w} from {owner} ({_n} children pending there)')
    try:
        stage_parent(port, v, w)                  # takes UPLINK itself (the lock is not re-entrant)
        src = f'{W}/mantis_lo44_{v}_20261114/cache/task=LO/window={w}'
        # user idea (17/11): copy host -> host directly (measured ~29 MB/s vs ~1.3 MB/s through the PC) with a throwaway key made on the owner host
        key = f'/tmp/xfer_{owner}_{port}'
        pub = S.run(owner, f'test -s {key} || ssh-keygen -q -t ed25519 -N "" -C tmp-xfer-{owner} -f {key}; cat {key}.pub')
        if not pub.startswith('ssh-ed25519'):
            raise RuntimeError(f'no throwaway key on {owner}: {pub[:60]}')
        S.run(port, f"mkdir -p ~/.ssh; sed -i '/tmp-xfer-{owner}/d' ~/.ssh/authorized_keys; printf '\n%s\n' '{pub}' >> ~/.ssh/authorized_keys; chmod 600 ~/.ssh/authorized_keys")
        try:
            S.run(owner, f'cd {W} && tar cf - mantis_lo44_{v}_20261114/cache/task=LO/window={w} | ssh -i {key} -o StrictHostKeyChecking=no -o BatchMode=yes -p {port} root@{S.IP[port]} "cd {W} && tar xf -"', timeout=5400)
        finally:
            S.run(port, f"sed -i '/tmp-xfer-{owner}/d' ~/.ssh/authorized_keys")
            S.run(owner, f'rm -f {key} {key}.pub')
        cnt_src = S.run(owner, f'find {src} -type f | wc -l; find {src} -type f -printf "%s\n" | awk "{{s+=\$1}} END {{print s}}"').split()
        cnt_dst = S.run(port, f'find {src} -type f | wc -l; find {src} -type f -printf "%s\n" | awk "{{s+=\$1}} END {{print s}}"').split()
        if S.run(port, f'test -s {src}/imputer={v}/channel_adapter.npz && echo OK') != 'OK' or cnt_src != cnt_dst:
            # some host pairs cannot reach each other (same public IP: connection timed out): relay through the PC (slow, one at a time)
            log(f'{port}: direct copy from {owner} failed, relaying through the PC')
            with RELAY:
                cmd = (f'ssh {" ".join(S.K)} -p {owner} root@{S.IP[owner]} "cd {W} && tar cf - mantis_lo44_{v}_20261114/cache/task=LO/window={w}" | '
                       f'ssh {" ".join(S.K)} -p {port} root@{S.IP[port]} "cd {W} && tar xf -"')
                subprocess.run(cmd, shell=True, timeout=7200)
            if S.run(port, f'test -s {src}/imputer={v}/channel_adapter.npz && echo OK') != 'OK':
                raise RuntimeError('cache copy failed (adapter file missing on target)')
    except Exception as e:  # noqa: BLE001
        log(f'{port}: replica {v} {w} failed {type(e).__name__}: {e}')
        set_state(f'RC|{v}|{w}|{port}', 'FAILED')
        S.run(port, f'cd {W} && rm -rf mantis_lo44_{v}_20261114/cache/task=LO/window={w}', timeout=900)
        return None
    set_state(f'RC|{v}|{w}|{port}', 'ready')
    log(f'{port}: replica {v} {w} ready')
    with LOCK:
        s = state()
        for c in KIDS[v]:
            if f'C|{c}|{w}' not in s:
                s[f'C|{c}|{w}'] = f'running on {port}'
                STATEF.write_text(json.dumps(s, indent=1))
                return c, v, w
    return None


def child_failed(port, c, v, w):
    """unattended mode (user away 7 h): clean the partial child dir, give the child up to 2 more tries (possibly on another host), keep the host working"""
    n = state().get(f'CFAIL|{c}|{w}', 0) + 1
    set_state(f'CFAIL|{c}|{w}', n)
    S.run(port, f'cd {W} && rm -rf mantis_lo44_{c}_20261114', timeout=900)
    if n <= 2:
        with LOCK:
            s = state()
            s.pop(f'C|{c}|{w}', None)
            STATEF.write_text(json.dumps(s, indent=1))
        log(f'{port}: child {c} {w} failed ({n}x): partial dir removed, child back in the queue')
    else:
        log(f'{port}: child {c} {w} failed {n}x: left FAILED')
    time.sleep(600)


# ---------------------------------------------------------------- PatchTST LO cells (after Mantis LO; user 18/11: cheap hosts only)
PL_ORDER = [('V12', 'W1'), ('V14', 'W1'), ('V15', 'W1'), ('V16', 'W1'), ('V2', 'W2'), ('V2', 'W3'), ('V0', 'W2'), ('V0', 'W3'), ('V13', 'W3'), ('V11', 'W2'), ('V11', 'W3'),
            ('V12', 'W2'), ('V12', 'W3'), ('V14', 'W2'), ('V14', 'W3'), ('V15', 'W2'), ('V15', 'W3'), ('V16', 'W2'), ('V16', 'W3')]
PL_EXPENSIVE = {'40077', '40081', '40106'}   # user 18/11 late: queued PatchTST LO cells go to the cheap hosts only (the 3 expensive ones finish their current cell)
PL_CMD = ('python -u tools/vastai_train_shared.py --task LO --data-root /workspace/CD3/data/LO_V3_1_clean_grain_seed44 --output-root /workspace/CD3/runs/patchtst_lo_seed44 '
          '--window {w} --pipeline-id {v} --model-name PATCHTST --seed 44 --batch-size 2048 --accumulation-steps 4 --workers 2 --max-epochs 50 --patience 5 '
          '--static-layout-policy current --run-purpose PRIMARY_GRID --augmentation-seed-policy match_model_seed --energy-sampling-interval-seconds 1.0')


def mantis_unclaimed():
    """True while more than 5 Mantis children have no host yet (the last few are covered by hosts that are copying their parent cache)"""
    s = state()
    return sum(1 for w in ('W1', 'W2', 'W3') for v in PARENTS for c in KIDS[v] if f'C|{c}|{w}' not in s) > 5


def take_patchtst_lo(port):
    if port in PL_EXPENSIVE or mantis_unclaimed():
        return False
    with LOCK:
        s = state()
        pick = None
        for v, w in PL_ORDER:
            if w == 'W3' and port == '44016':
                continue
            if w not in ALLOW.get(port, ('W1', 'W2', 'W3')):
                continue
            k = f'PL|{v}|{w}'
            if k not in s and s.get(f'PLFAIL|{v}|{w}', 0) < 2:
                pick = (k, v, w)
                break
        if pick is None:
            return False
        s[pick[0]] = f'running on {port}'
        STATEF.write_text(json.dumps(s, indent=1))
    k, v, w = pick
    env = B.ENV.get(port, '/venv/main')
    log(f'{port}: PatchTST LO {v} {w} (cheap-host queue)')
    mf = f'{W}/runs/patchtst_lo_seed44/LO/{w}/{v}/PATCHTST/seed=44/run_manifest.json'
    try:
        if v in PARENTS:
            stage_parent(port, v, w)
        else:
            with UPLOCK[port]:
                B.stage_children(port, 'LO', [(w, v)])
    except Exception as e:  # noqa: BLE001
        log(f'{port}: PatchTST LO staging failed {type(e).__name__}; cell put back')
        with LOCK:
            s = state(); s.pop(k, None); STATEF.write_text(json.dumps(s, indent=1))
        return True
    cmd = PL_CMD.format(w=w, v=v)
    body = (f'if ! test -f {mf}; then echo "START PT LO {w} {v} $(date -Is)"; mkdir -p {W}/runs/patchtst_lo_seed44/logs; '
            f'( source {env}/bin/activate; cd {W}/repo43; export PYTHONPATH={W}/repo43; export TEMPO_PREDICTION_SALT="$(cat {W}/lo_static_v2_prediction_salt)"; '
            f'echo "RUNNER_COMMIT $(git rev-parse --short HEAD)"; {cmd} ) > {W}/runs/patchtst_lo_seed44/logs/{w}_{v}.log 2>&1 && echo "DONE PT LO {w} {v} $(date -Is)" || echo "FAILED PT LO {w} {v} $(date -Is)"; '
            f'else echo "DONE PT LO already {w} {v}"; fi')
    ok, last = script_run(port, f'seed44_lo_pl_{port}_{w}_{v}.sh', body, 'DONE PT LO')
    done = S.run(port, f'test -s {mf} && echo Y') == 'Y'
    log(f'{port}: PatchTST LO {v} {w} -> {"done" if done else "NOT finished"} ({last[:80]})')
    if done:
        set_state(k, f'done on {port}')
    else:
        with LOCK:
            s = state(); s.pop(k, None); s[f'PLFAIL|{v}|{w}'] = s.get(f'PLFAIL|{v}|{w}', 0) + 1; STATEF.write_text(json.dumps(s, indent=1))
    return True


def work_left():
    s = state()
    if any(f'PL|{v}|{w}' not in s and s.get(f'PLFAIL|{v}|{w}', 0) < 2 for v, w in PL_ORDER):
        return True
    parents = [f'P|{v}|{w}' for w in ('W1', 'W2', 'W3') for v in PARENTS]
    children = [f'C|{c}|{w}' for w in ('W1', 'W2', 'W3') for v in PARENTS for c in KIDS[v]]
    return any(not s.get(k, '').startswith(('done', 'FAILED')) for k in parents + children)


def on_drive(name):
    """the backup loop removes a finished tar from the host after the Drive md5 check: a missing host tar may simply be on Drive"""
    r = subprocess.run(['rclone', '--drive-root-folder-id', '1GWiedVROrxp8jvGbd0xmvVmWriZUkpOn', 'lsf', '-R', '--files-only', '--include', name,
                        'gdrive:LO/L1_runs/S3_model/staging_incoming/mantis_v2_seed44_exploratory_20261118'], capture_output=True, text=True, timeout=300)
    return name in r.stdout


def reconcile(port):
    """entries left as 'running on <port>' by a previous worker process: the remote script has ended (host is free) -> decide by the result tar"""
    for k, val in list(state().items()):
        if val != f'running on {port}':
            continue
        kind, *rest = k.split('|')
        if kind == 'PTQ':          # a requeued PatchTST cell whose worker died during staging/run: back to the pool
            set_state(k, 'queued')
            log(f'{port}: pool cell {k} back to queued')
            continue
        if kind == 'PL':           # PatchTST LO cell: done iff its run_manifest.json exists; else put back in the queue (max 2 tries)
            v, w = rest
            if S.run(port, f'test -s {W}/runs/patchtst_lo_seed44/LO/{w}/{v}/PATCHTST/seed=44/run_manifest.json && echo Y') == 'Y':
                set_state(k, f'done on {port}')
            else:
                with LOCK:
                    s = state(); s.pop(k, None); s[f'PLFAIL|{v}|{w}'] = s.get(f'PLFAIL|{v}|{w}', 0) + 1; STATEF.write_text(json.dumps(s, indent=1))
            log(f'{port}: reconciled {k} -> {state().get(k, "re-queued")}')
            continue
        if kind == 'P':
            v, w = rest
            ok = tar_ok(port, f'mantis_lo44_{v}_{w}_20261114_results.tar.gz') or on_drive(f'mantis_lo44_{v}_{w}_20261114_results.tar.gz')
            if ok and not KIDS[v]:
                S.run(port, f'cd {W} && rm -rf mantis_lo44_{v}_20261114', timeout=900)
        else:
            c, w = rest
            ok = tar_ok(port, f'mantis_lo44_{c}_{w}_20261114_results.tar.gz') or on_drive(f'mantis_lo44_{c}_{w}_20261114_results.tar.gz')
        set_state(k, f'done on {port}' if ok else f'FAILED on {port}')
        log(f'{port}: reconciled {k} -> {state()[k]}')


def _worker(port):
    warned = False
    while True:
        if not host_free(port):
            time.sleep(240)
            continue
        reconcile(port)
        if port in EXPENSIVE:          # user (18/11): the 4 most expensive hosts only finish what they are running, then are stopped; no new work
            time.sleep(300)
            continue
        if port not in MANTIS_FIRST and take_pt_cell(port):
            continue
        low_disk = free_gb(port) < 9
        g = next_parent(port) if not low_disk else None     # a new parent needs >= 9 GB free; children of the parents already cached here do not (their script has its own 7.5 GB guard)
        if g:
            if not run_parent(port, *g):
                log(f'{port}: stopping after a failed parent')
                return
            continue
        if low_disk and not warned:
            log(f'{port}: free disk below 9 GB: no new Mantis parent here, children of the cached parents still run')
            warned = True
        ch = next_child(port)
        if ch:
            if not run_child(port, *ch):
                child_failed(port, *ch)
            continue
        rc = take_replica_child(port)
        if rc:
            if not run_child(port, *rc):
                child_failed(port, *rc)
            continue
        if take_patchtst_lo(port):
            continue
        if port in MANTIS_FIRST and take_pt_cell(port):
            continue
        if not work_left():
            log(f'{port}: nothing left in the CQ queue')
            return
        time.sleep(90)


def worker(port):
    """a crash of one host thread (ssh timeout, scp error...) must not leave the host idle for hours: log it and start the loop again"""
    while True:
        try:
            _worker(port)
            return
        except Exception as e:  # noqa: BLE001
            log(f'{port}: worker loop crashed ({type(e).__name__}: {str(e)[:120]}); restarting in 120 s')
            time.sleep(120)


if __name__ == '__main__':
    log('workers start (parents first): ' + ' '.join(sys.argv[1:]))
    ts = [threading.Thread(target=worker, args=(p,), daemon=False) for p in sys.argv[1:]]
    for t in ts:
        t.start()
        time.sleep(7)
    for t in ts:
        t.join()
