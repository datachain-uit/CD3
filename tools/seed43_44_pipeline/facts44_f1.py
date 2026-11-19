"""Seed-44 F1 facts packages (CQ|LO): port of facts43_f1.py. Per family: download+extract the flat host tars, cohort audit per V, build the package from the standard audit (D:/audit44/out_<TASK>_<FAM>), remove the runs.
usage: facts44_f1.py TASK [FAM ...]"""
import os, shutil, subprocess, sys, tarfile, time
from pathlib import Path
TASK = sys.argv[1]
FAMS = sys.argv[2:] or ['RNN', 'LSTM', 'GRU', 'BILSTM']
RC = ['rclone', '--drive-root-folder-id', '1GWiedVROrxp8jvGbd0xmvVmWriZUkpOn']
REPO = Path('D:/Source_code/myself'); DATA = Path(f'D:/audit43/data_{TASK}')
SALT = REPO / 'downloads/private' / ('lo_grid_prediction_salt' if TASK == 'LO' else 'cq_patchtst_prediction_salt')
SRCDIR = f'{TASK}/L1_runs/S3_model/staging_incoming/f1_recurrent_seed44_20261115'
env = dict(os.environ, PYTHONPATH=str(REPO), PYTHONIOENCODING='utf-8')
def log(m): print(time.strftime('%H:%M:%S'), m, flush=True)
def run(cmd):
    r = subprocess.run([str(c) for c in cmd], cwd=REPO, env=env, capture_output=True, text=True)
    if r.returncode: log('FAILED ' + ' '.join(map(str, cmd))[:150] + ' :: ' + (r.stdout + r.stderr)[-500:]); raise SystemExit(1)
    return r
for FAM in FAMS:
    BASE = Path(f'D:/audit44/facts_{TASK}_{FAM}'); RUNS = BASE / 'runs'; TARS = BASE / 'tars'
    OUTPKG = Path(f'D:/audit44/facts44/{TASK}_f1_recurrent_v0_v16_seed44/{FAM}')
    if (OUTPKG / 'sha256sums.txt').exists(): log(f'{FAM} already built'); continue
    if not (BASE / 'EXTRACTED').exists():
        RUNS.mkdir(parents=True, exist_ok=True); TARS.mkdir(parents=True, exist_ok=True)
        names = [n for n in subprocess.run(RC + ['lsf', f'gdrive:{SRCDIR}'], capture_output=True, text=True).stdout.split() if f'_seed44_{FAM}_' in n and n.endswith('.tar')]
        log(f'{FAM}: {len(names)} tars')
        for n in sorted(names):
            subprocess.run(RC + ['copy', f'gdrive:{SRCDIR}/{n}', str(TARS), '-q'], check=True)
            with tarfile.open(TARS / n) as tf: tf.extractall(RUNS)
            (TARS / n).unlink()
        (BASE / 'EXTRACTED').write_text('ok')
    log(f'{FAM} cells: {len(list(RUNS.rglob("seed=44/run_manifest.json")))}')
    for v in [f'V{i}' for i in range(17)]:
        out = BASE / 'cohort_out' / v
        if (out / 'summary.json').is_file(): continue
        run([sys.executable, 'tools/audit_prediction_course_cohort.py', '--data-root', DATA, '--model-root', RUNS, '--output-root', out, '--task', TASK, '--pipeline-id', v, '--model-name', FAM, '--seed', '44', '--prediction-salt-file', SALT])
    r = run([sys.executable, 'tools/build_facts_package_mantis_lo_20261109.py', '--kind', 'patchtst', '--task', TASK, '--model', FAM, '--seed', '44', '--audit-roots', f'D:/audit44/out_{TASK}_{FAM}', '--cohort-roots', BASE / 'cohort_out', '--std-roots', RUNS, '--out', OUTPKG])
    log(f'PKG_DONE {FAM} ' + r.stdout[-200:].replace('\n', ' '))
    shutil.rmtree(BASE, ignore_errors=True)
log('F1_FACTS_DONE ' + TASK)
