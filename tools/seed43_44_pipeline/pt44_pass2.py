"""PatchTST LO seed 44, incremental pass: usage pt44_pass2.py TAG   (TAG = pass2, pass3 ...)
Fetch the Drive tars newer than 09:20 local on 19/11, add the cells not yet in the run root, audit only the new cells (standard audit, --allow-partial, own audit dir), cohort audit for every V that now has 3 windows, and when all 51 cells exist build the package from all audit dirs."""
from tempo_paths import A44, REPO, WORK
import json, os, shutil, subprocess, sys, tarfile, time
from pathlib import Path
TAG = sys.argv[1]; TASK = 'LO'
RC = ['rclone', '--drive-root-folder-id', '1GWiedVROrxp8jvGbd0xmvVmWriZUkpOn']
REPO = Path(f'{REPO}'); BASE = Path(f'{WORK}/pt44_LO'); RUNS = BASE / 'runs'; DATA = Path(f'{A44}/data_LO')
SRC = 'LO/L1_runs/S3_model/staging_incoming/patchtst_seed44_20261117'
SALT = REPO / 'downloads/private/lo_grid_prediction_salt'; REF = REPO / 'CQ/resuilt/s_leak_reference_20261109/s_leak_reference_LO.csv'
AUDS = [Path(f'{A44}/out_LO_PATCHTST_pass1')]; AUDS += sorted(Path(f'{A44}').glob('out_LO_PATCHTST_pass[2-9]'))
AUDN = Path(f'{A44}/out_LO_PATCHTST_{TAG}'); OUTPKG = Path(f'{A44}/facts44/LO_patchtst_v0_v16_seed44')
env = dict(os.environ, PYTHONPATH=str(REPO), PYTHONIOENCODING='utf-8')
def log(m): print(time.strftime('%H:%M:%S'), m, flush=True)
def run(cmd, name=None):
    r = subprocess.run([str(c) for c in cmd], cwd=REPO, env=env, capture_output=True, text=True)
    if name: (BASE / name).write_text(r.stdout + '\n' + r.stderr, encoding='utf-8')
    if r.returncode: log('FAILED ' + ' '.join(map(str, cmd))[:150] + ' :: ' + (r.stdout + r.stderr)[-500:]); raise SystemExit(1)
    return r
def cells(root): return {'/'.join(p.parts[-5:-3][::-1]) if False else f'{p.parts[-5]}/{p.parts[-4]}' for p in root.glob(f'{TASK}/W*/V*/PATCHTST/seed=44/run_manifest.json')}
have = {f'{p.parts[-5]}/{p.parts[-4]}' for p in RUNS.glob('LO/W*/V*/PATCHTST/seed=44/run_manifest.json')}
log(f'cells before: {len(have)}')
new_root = BASE / 'runs_new'; shutil.rmtree(new_root, ignore_errors=True); shutil.rmtree(BASE / 'x', ignore_errors=True)
lst = json.loads(subprocess.run(RC + ['lsjson', f'gdrive:{SRC}', '--include', '*.tar'], capture_output=True, text=True).stdout)
for e in sorted(lst, key=lambda e: e['ModTime']):
    if e['ModTime'] < '2026-11-19T02:20:00': continue
    (BASE / 'tars').mkdir(exist_ok=True)
    subprocess.run(RC + ['copy', f"gdrive:{SRC}/{e['Name']}", str(BASE / 'tars'), '-q'], check=True)
    try:
        with tarfile.open(BASE / 'tars' / e['Name']) as tf: tf.extractall(BASE / 'x')
    except Exception as ex: log(f"SKIP unreadable {e['Name']} {type(ex).__name__}")
    (BASE / 'tars' / e['Name']).unlink()
    for p in [p for p in (BASE / 'x').rglob('PATCHTST') if p.is_dir()]:
        i = p.parts.index(TASK); w, v = p.parts[i + 1], p.parts[i + 2]
        if f'{w}/{v}' in have or not (p / 'seed=44' / 'run_manifest.json').exists(): continue
        dst = new_root.joinpath(*p.parts[i:])
        if not dst.exists(): dst.parent.mkdir(parents=True, exist_ok=True); shutil.move(str(p), str(dst))
    shutil.rmtree(BASE / 'x', ignore_errors=True)
newc = {f'{p.parts[-5]}/{p.parts[-4]}' for p in new_root.glob('LO/W*/V*/PATCHTST/seed=44/run_manifest.json')} if new_root.exists() else set()
log(f'new cells: {sorted(newc)}')
if newc:
    AUDN.mkdir(parents=True, exist_ok=True)
    run([sys.executable, 'tools/vastai_audit_shared.py', '--task', TASK, '--data-root', DATA, '--run-root', new_root, '--audit-root', AUDN, '--model-name', 'PATCHTST', '--seed', '44',
         '--bootstrap-repetitions', '2000', '--s-leak-reference', REF, '--s-leak-source', 'copy-reference', '--probe-mode', 'default_multithread', '--skip-probe-refit', '--allow-partial'], f'audit_{TAG}.log')
    log('standard audit of new cells done')
    for w in new_root.glob('LO/W*'):
        for v in w.iterdir(): shutil.move(str(v), str(RUNS / 'LO' / w.name / v.name))
    shutil.rmtree(new_root, ignore_errors=True)
n = len(list(RUNS.glob('LO/W*/V*/PATCHTST/seed=44/run_manifest.json'))); log(f'cells now: {n}')
for v in [f'V{i}' for i in range(17)]:
    out = BASE / 'cohort_out' / v
    if (out / 'summary.json').is_file(): continue
    if len(list(RUNS.glob(f'LO/W*/{v}/PATCHTST/seed=44/run_manifest.json'))) != 3: continue
    run([sys.executable, 'tools/audit_prediction_course_cohort.py', '--data-root', DATA, '--model-root', RUNS, '--output-root', out, '--task', TASK, '--pipeline-id', v, '--model-name', 'PATCHTST', '--seed', '44', '--prediction-salt-file', SALT])
    log('cohort ' + v)
if n == 51:
    auds = AUDS + ([AUDN] if newc and AUDN not in AUDS else [])
    r = run([sys.executable, 'tools/build_facts_package_mantis_lo_20261109.py', '--kind', 'patchtst', '--task', TASK, '--seed', '44', '--audit-roots', *auds, '--cohort-roots', BASE / 'cohort_out', '--std-roots', RUNS, '--out', OUTPKG])
    log('PKG_DONE ' + r.stdout[-300:].replace('\n', ' '))
log(f'PASS_DONE {TAG} cells={n}')
