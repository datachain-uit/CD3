"""Seed-43 F1 facts packages (CQ|LO): per family download+extract, cohort audit per V, package; then one folder per task with the 4 family packages. usage: facts43_f1.py TASK"""
from tempo_paths import A43, REPO
import os, shutil, subprocess, sys, tarfile, time
from pathlib import Path
TASK = sys.argv[1]
RC = ['rclone', '--drive-root-folder-id', '1GWiedVROrxp8jvGbd0xmvVmWriZUkpOn']
REPO = Path(f'{REPO}'); DATA = Path(f'{A43}/data_{TASK}')
SALT = REPO / 'downloads/private' / ('lo_grid_prediction_salt' if TASK == 'LO' else 'cq_patchtst_prediction_salt')
env = dict(os.environ, PYTHONPATH=str(REPO), PYTHONIOENCODING='utf-8')
def log(m): print(time.strftime('%H:%M:%S'), m, flush=True)
def run(cmd):
    r = subprocess.run([str(c) for c in cmd], cwd=REPO, env=env, capture_output=True, text=True)
    if r.returncode: log('FAILED ' + ' '.join(map(str, cmd))[:150] + ' :: ' + (r.stdout + r.stderr)[-400:]); raise SystemExit(1)
    return r
for FAM in ('RNN', 'LSTM', 'GRU', 'BILSTM'):
    BASE = Path(f'{A43}/f1_facts_{TASK}_{FAM}'); RUNS = BASE / 'runs'; TARS = BASE / 'tars'
    OUTPKG = Path(f'{A43}/facts43/{TASK}_f1_recurrent_v0_v16_seed43/{FAM}')
    if (OUTPKG / 'sha256sums.txt').exists(): continue
    if not (BASE / 'EXTRACTED').exists():
        RUNS.mkdir(parents=True, exist_ok=True); TARS.mkdir(parents=True, exist_ok=True)
        subprocess.run(RC + ['copy', f'gdrive:{TASK}/L1_runs/S3_model/staging_incoming/f1_recurrent_seed43_20261110/{FAM}', str(TARS), '--transfers', '4', '-q'], check=True)
        for t in sorted(TARS.rglob('*.tar.gz')):
            with tarfile.open(t) as tf: tf.extractall(RUNS)
            t.unlink()
        (BASE / 'EXTRACTED').write_text('ok')
    log(f'{FAM} cells: {len(list(RUNS.rglob("seed=43/run_manifest.json")))}')
    for v in [f'V{i}' for i in range(17)]:
        out = BASE / 'cohort_out' / v
        if (out / 'summary.json').is_file(): continue
        run([sys.executable, 'tools/audit_prediction_course_cohort.py', '--data-root', DATA, '--model-root', RUNS, '--output-root', out, '--task', TASK, '--pipeline-id', v, '--model-name', FAM, '--seed', '43', '--prediction-salt-file', SALT])
    r = run([sys.executable, 'tools/build_facts_package_mantis_lo_20261109.py', '--kind', 'patchtst', '--task', TASK, '--model', FAM, '--seed', '43', '--audit-roots', f'{A43}/out_{TASK}_{FAM}', '--cohort-roots', BASE / 'cohort_out', '--std-roots', RUNS, '--out', OUTPKG])
    log(f'PKG_DONE {FAM} ' + r.stdout[-200:].replace('\n', ' '))
    shutil.rmtree(BASE, ignore_errors=True)
log('F1_FACTS_DONE ' + TASK)
