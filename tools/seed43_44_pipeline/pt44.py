"""Seed-44 PatchTST audit + facts package (CQ|LO): download the cell tars from Drive, normalise to RUNS/<TASK>/<W>/<V>/PATCHTST/seed=44, standard audit (s_leak copied from the reference table, no probe refit),
cohort audit per V, package via tools/build_facts_package_mantis_lo_20261109.py --kind patchtst. usage: pt44.py TASK"""
import os, shutil, subprocess, sys, tarfile, time
from pathlib import Path
TASK = sys.argv[1]
RC = ['rclone', '--drive-root-folder-id', '1GWiedVROrxp8jvGbd0xmvVmWriZUkpOn']
REPO = Path('D:/Source_code/myself'); BASE = Path(f'D:/audit44/pt_{TASK}'); TARS = BASE / 'tars'; RUNS = BASE / 'runs'; DATA = Path(f'D:/audit44/data_{TASK}')
SRC = {'CQ': ['CQ/L1_runs/S3_model/staging_incoming/patchtst_seed44_cells_20261116'], 'LO': ['LO/L1_runs/S3_model/staging_incoming/patchtst_seed44_20261117']}[TASK]
SALT = REPO / 'downloads/private' / ('lo_grid_prediction_salt' if TASK == 'LO' else 'cq_patchtst_prediction_salt')
AUD = Path(f'D:/audit44/out_{TASK}_PATCHTST'); OUTPKG = Path(f'D:/audit44/facts44/{TASK}_patchtst_v0_v16_seed44')
REF = REPO / 'CQ' / 'resuilt' / 's_leak_reference_20261109' / f's_leak_reference_{TASK}.csv'
env = dict(os.environ, PYTHONPATH=str(REPO), PYTHONIOENCODING='utf-8')
def log(m): print(time.strftime('%H:%M:%S'), m, flush=True)
def run(cmd, name=None):
    r = subprocess.run([str(c) for c in cmd], cwd=REPO, env=env, capture_output=True, text=True)
    if name: (BASE / name).write_text(r.stdout + '\n' + r.stderr, encoding='utf-8')
    if r.returncode: log('FAILED ' + ' '.join(map(str, cmd))[:150] + ' :: ' + (r.stdout + r.stderr)[-500:]); raise SystemExit(1)
    return r
for d in (TARS, RUNS, AUD): d.mkdir(parents=True, exist_ok=True)
if not (BASE / 'EXTRACTED').exists():
    for src in SRC:
        for t in subprocess.run(RC + ['lsf', f'gdrive:{src}', '--include', '*.tar'], capture_output=True, text=True).stdout.split():
            subprocess.run(RC + ['copy', f'gdrive:{src}/{t}', str(TARS), '-q'], check=True)
            with tarfile.open(TARS / t) as tf: tf.extractall(BASE / 'x')
            (TARS / t).unlink()
            for p in [p for p in (BASE / 'x').rglob('PATCHTST') if p.is_dir()]:
                i = p.parts.index(TASK); dst = RUNS.joinpath(*p.parts[i:])
                s = p / 'seed=44' / 'run_manifest.json'
                if dst.exists() and (dst / 'seed=44' / 'run_manifest.json').exists() or not s.exists(): continue
                if dst.exists(): shutil.rmtree(dst)
                dst.parent.mkdir(parents=True, exist_ok=True); shutil.move(str(p), str(dst))
            shutil.rmtree(BASE / 'x', ignore_errors=True)
            log('extracted ' + t)
    (BASE / 'EXTRACTED').write_text('ok')
n = len(list(RUNS.rglob('seed=44/run_manifest.json'))); log(f'cells with manifest: {n}')
if n != 51: log(f'WARNING expected 51 cells, found {n}')
if not (BASE / 'AUDIT_DONE').exists():
    run([sys.executable, 'tools/vastai_audit_shared.py', '--task', TASK, '--data-root', DATA, '--run-root', RUNS, '--audit-root', AUD, '--model-name', 'PATCHTST', '--seed', '44',
         '--bootstrap-repetitions', '2000', '--s-leak-reference', REF, '--s-leak-source', 'copy-reference', '--probe-mode', 'default_multithread', '--skip-probe-refit'], 'audit.log')
    (BASE / 'AUDIT_DONE').write_text('ok'); log('standard audit done')
for v in [f'V{i}' for i in range(17)]:
    out = BASE / 'cohort_out' / v
    if (out / 'summary.json').is_file(): continue
    run([sys.executable, 'tools/audit_prediction_course_cohort.py', '--data-root', DATA, '--model-root', RUNS, '--output-root', out, '--task', TASK, '--pipeline-id', v, '--model-name', 'PATCHTST', '--seed', '44', '--prediction-salt-file', SALT])
    log('cohort ' + v)
r = run([sys.executable, 'tools/build_facts_package_mantis_lo_20261109.py', '--kind', 'patchtst', '--task', TASK, '--seed', '44', '--audit-roots', AUD, '--cohort-roots', BASE / 'cohort_out', '--std-roots', RUNS, '--out', OUTPKG])
log('PKG_DONE ' + r.stdout[-300:].replace('\n', ' '))
log('PT_FACTS_DONE ' + TASK)
