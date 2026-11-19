"""Seed-44 F1 audit on this PC (port of audit43_local.py): per family download the flat host tars from Drive, extract, standard audit (s_leak copied from the reference table, no probe refit), keep audit output, delete the runs.
usage: audit44_f1.py TASK FAMILY [BOOTSTRAP]"""
import os, subprocess, sys, tarfile, time, shutil
from pathlib import Path
TASK, FAM = sys.argv[1], sys.argv[2]
BOOT = sys.argv[3] if len(sys.argv) > 3 else '2000'
RC = ['rclone', '--drive-root-folder-id', '1GWiedVROrxp8jvGbd0xmvVmWriZUkpOn']
REPO = Path('D:/Source_code/myself')
BASE = Path(f'D:/audit44/{TASK}_{FAM}'); RUNS = BASE / 'runs'; TARS = BASE / 'tars'
DATA = Path(f'D:/audit43/data_{TASK}')            # same real-data root (junctions to the seed-42 clean-grain data) as for seed 43
OUT = Path(f'D:/audit44/out_{TASK}_{FAM}')
SRCDIR = f'{TASK}/L1_runs/S3_model/staging_incoming/f1_recurrent_seed44_20261115'
def log(m): print(time.strftime('%H:%M:%S'), m, flush=True)
assert DATA.exists(), 'data root missing'
for d in (RUNS, TARS, OUT): d.mkdir(parents=True, exist_ok=True)
if not (BASE / 'EXTRACTED').exists():
    names = [n for n in subprocess.run(RC + ['lsf', f'gdrive:{SRCDIR}'], capture_output=True, text=True).stdout.split() if f'_seed44_{FAM}_' in n and n.endswith('.tar')]
    log(f'{FAM}: {len(names)} tars')
    for n in sorted(names):
        subprocess.run(RC + ['copy', f'gdrive:{SRCDIR}/{n}', str(TARS), '-q'], check=True)
        with tarfile.open(TARS / n) as tf: tf.extractall(RUNS)
        (TARS / n).unlink(); log('extracted ' + n)
    (BASE / 'EXTRACTED').write_text('ok')
cells = len(list(RUNS.rglob('seed=44/run_manifest.json')))
log(f'cells with manifest: {cells}')
ref = REPO / 'CQ' / 'resuilt' / 's_leak_reference_20261109' / f's_leak_reference_{TASK}.csv'
cmd = [sys.executable, 'tools/vastai_audit_shared.py', '--task', TASK, '--data-root', str(DATA), '--run-root', str(RUNS), '--audit-root', str(OUT), '--model-name', FAM, '--seed', '44',
       '--bootstrap-repetitions', BOOT, '--s-leak-reference', str(ref), '--s-leak-source', 'copy-reference', '--probe-mode', 'default_multithread', '--skip-probe-refit']
log('audit start')
r = subprocess.run(cmd, cwd=REPO, env=dict(os.environ, PYTHONPATH=str(REPO), PYTHONIOENCODING='utf-8'), capture_output=True, text=True)
(BASE / 'audit.log').write_text(r.stdout + '\n' + r.stderr, encoding='utf-8')
log(f'audit rc={r.returncode}; tail: {(r.stdout + r.stderr)[-400:]!r}')
if r.returncode == 0: shutil.rmtree(RUNS, ignore_errors=True)
