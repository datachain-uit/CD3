"""Seed-43 Mantis audit (CQ|LO): per window extract -> standardise -> standard audit (s_leak copied from the reference table, no probe refit) -> cohort audit per V.
usage: audit43_mantis.py TASK"""
import os, shutil, subprocess, sys, tarfile, time
from pathlib import Path
TASK = sys.argv[1]
REPO = Path('D:/Source_code/myself'); SRC = Path(f'D:/audit43/mantis/{TASK}'); W = Path(f'D:/audit43/mantis_work_{TASK}'); OUT = Path(f'D:/audit43/out_{TASK}_MANTIS')
DATA = Path(f'D:/audit43/data_{TASK}')
CODE = Path('C:/tmp_aud/lom/mantis_lo_code_20261109.tar')
REF = REPO / 'CQ/resuilt/s_leak_reference_20261109' / f's_leak_reference_{TASK}.csv'
SALT = REPO / 'downloads/private' / ('lo_grid_prediction_salt' if TASK == 'LO' else 'cq_patchtst_prediction_salt')
W.mkdir(parents=True, exist_ok=True); OUT.mkdir(parents=True, exist_ok=True)
LOG = W / 'pipeline.log'
def log(m):
    with LOG.open('a', encoding='utf-8') as f: f.write(f'{time.strftime("%H:%M:%S")} {m}\n')
    print(m, flush=True)
env = dict(os.environ, PYTHONPATH=str(REPO), PYTHONIOENCODING='utf-8')
def run(cmd, name):
    log('RUN ' + ' '.join(map(str, cmd))[:220])
    with (W / name).open('a', encoding='utf-8') as f:
        r = subprocess.run([str(c) for c in cmd], cwd=REPO, env=env, stdout=f, stderr=subprocess.STDOUT)
    if r.returncode: log(f'FAILED rc={r.returncode} {name}'); raise SystemExit(1)
runner = W / 'code' / 'tools/run_mantis_grid_zstd_20261109.py'
if not runner.exists():
    with tarfile.open(CODE) as tf: tf.extractall(W / 'code')
first = sorted(SRC.glob('V0/*_W1_*.tar.gz'))[0]
freeze = W / 'pip_freeze.txt'
if not freeze.exists():
    with tarfile.open(first) as tf: freeze.write_bytes(tf.extractfile('state/environment_pip_freeze.txt').read())
for win in ('W1', 'W2', 'W3'):
    mark = W / f'DONE_{win}'
    if mark.exists(): continue
    ex, std, aud = W / f'ex_{win}', W / f'std_{win}', W / f'aud_{win}'
    for d in (ex, std, aud): shutil.rmtree(d, ignore_errors=True)
    ex.mkdir()
    for t in sorted(SRC.glob(f'V*/*_{win}_*_results.tar.gz')):
        with tarfile.open(t) as tf:
            tf.extractall(ex, members=[m for m in tf if m.name.startswith(('runs/', 'state/'))])
    log(f'{win}: extracted {len(list((ex / "runs" / win).glob("V*")))} cells')
    run([sys.executable, 'tools/mantis_standardize_runs_20261110.py', '--task', TASK, '--runner-rel', 'tools/run_mantis_grid_zstd_20261109.py', '--data-root', DATA, '--out', std,
         '--runner', runner, '--code-tar', CODE, '--pip-freeze', freeze, '--extracted', ex], f'standardize_{win}.log')
    shutil.rmtree(ex, ignore_errors=True)
    aud.mkdir()
    run([sys.executable, '-u', 'tools/run_standard_audit_pruned_20261108.py', '--task', TASK, '--data-root', DATA, '--run-root', std, '--audit-root', aud, '--model-name', 'MANTIS_V2',
         '--seed', '43', '--bootstrap-repetitions', '2000', '--allow-partial', '--s-leak-reference', REF, '--s-leak-source', 'copy-reference', '--probe-mode', 'default_multithread',
         '--skip-probe-refit'], f'audit_{win}.log')
    mark.write_text('done\n'); log(f'{win} audited')
allroot = W / 'std_all'
if not (W / 'COHORT_DONE').exists():
    for win in ('W1', 'W2', 'W3'):
        src, dst = W / f'std_{win}' / TASK / win, allroot / TASK / win
        if src.exists() and not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True); src.rename(dst)
    for v in [f'V{i}' for i in range(17)]:
        if (W / 'cohort_out' / v / 'summary.json').is_file(): continue
        run([sys.executable, 'tools/audit_prediction_course_cohort.py', '--data-root', DATA, '--model-root', allroot, '--output-root', W / 'cohort_out' / v, '--task', TASK,
             '--pipeline-id', v, '--model-name', 'MANTIS_V2', '--seed', '43', '--prediction-salt-file', SALT], f'cohort_{v}.log')
    (W / 'COHORT_DONE').write_text('done\n')
log('MANTIS43_AUDIT_DONE ' + TASK)
