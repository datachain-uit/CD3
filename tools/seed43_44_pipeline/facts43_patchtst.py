"""Seed-43 PatchTST facts package (CQ|LO): re-download+extract the cells, cohort audit per V, build package with tools/build_facts_package_mantis_lo_20261109.py --kind patchtst.  usage: facts43_patchtst.py TASK"""
from tempo_paths import A43, REPO
import os, shutil, subprocess, sys, tarfile, time
from pathlib import Path
TASK = sys.argv[1]
RC = ['rclone', '--drive-root-folder-id', '1GWiedVROrxp8jvGbd0xmvVmWriZUkpOn']
REPO = Path(f'{REPO}'); BASE = Path(f'{A43}/pt_facts_{TASK}'); TARS = BASE / 'tars'; RUNS = BASE / 'runs'; DATA = Path(f'{A43}/data_{TASK}')
SRC = {'CQ': 'CQ/L1_runs/S3_model/staging_incoming/patchtst_seed43_cells_20261112', 'LO': 'LO/L1_runs/S3_model/staging_incoming/patchtst_seed43_cells_20261114'}[TASK]
SALT = REPO / 'downloads/private' / ('lo_grid_prediction_salt' if TASK == 'LO' else 'cq_patchtst_prediction_salt')
AUD = Path(f'{A43}/out_{TASK}_PATCHTST'); OUTPKG = Path(f'{A43}/facts43/{TASK}_patchtst_v0_v16_seed43')
env = dict(os.environ, PYTHONPATH=str(REPO), PYTHONIOENCODING='utf-8')
def log(m): print(time.strftime('%H:%M:%S'), m, flush=True)
def run(cmd):
    r = subprocess.run([str(c) for c in cmd], cwd=REPO, env=env, capture_output=True, text=True)
    if r.returncode: log('FAILED ' + ' '.join(map(str, cmd))[:150] + ' :: ' + (r.stdout + r.stderr)[-400:]); raise SystemExit(1)
    return r
if not (BASE / 'EXTRACTED').exists():
    for d in (TARS, RUNS): d.mkdir(parents=True, exist_ok=True)
    for t in subprocess.run(RC + ['lsf', f'gdrive:{SRC}', '--include', '*.tar'], capture_output=True, text=True).stdout.split():
        subprocess.run(RC + ['copy', f'gdrive:{SRC}/{t}', str(TARS), '-q'], check=True)
        with tarfile.open(TARS / t) as tf: tf.extractall(BASE / 'x')
        (TARS / t).unlink()
        for p in [p for p in (BASE / 'x').rglob('PATCHTST') if p.is_dir()]:
            i = p.parts.index(TASK); dst = RUNS.joinpath(*p.parts[i:])
            if not dst.exists(): dst.parent.mkdir(parents=True, exist_ok=True); shutil.move(str(p), str(dst))
        shutil.rmtree(BASE / 'x', ignore_errors=True)
    (BASE / 'EXTRACTED').write_text('ok')
log('cells: %d' % len(list(RUNS.rglob('seed=43/run_manifest.json'))))
for v in [f'V{i}' for i in range(17)]:
    out = BASE / 'cohort_out' / v
    if (out / 'summary.json').is_file(): continue
    run([sys.executable, 'tools/audit_prediction_course_cohort.py', '--data-root', DATA, '--model-root', RUNS, '--output-root', out, '--task', TASK, '--pipeline-id', v, '--model-name', 'PATCHTST', '--seed', '43', '--prediction-salt-file', SALT])
    log('cohort ' + v)
r = run([sys.executable, 'tools/build_facts_package_mantis_lo_20261109.py', '--kind', 'patchtst', '--task', TASK, '--seed', '43', '--audit-roots', AUD, '--cohort-roots', BASE / 'cohort_out', '--std-roots', RUNS, '--out', OUTPKG])
log('PKG_DONE ' + r.stdout[-300:].replace('\n', ' '))
