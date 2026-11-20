"""Seed-44 Mantis (CQ|LO): download tars -> audit44_mantis.py -> package (kind mantis|lo_mantis, seed 44). usage: facts44_mantis.py TASK"""
from tempo_paths import A44, REPO, S2, WORK
import os, shutil, subprocess, sys, time
from pathlib import Path
TASK = sys.argv[1]
RC = ['rclone', '--drive-root-folder-id', '1GWiedVROrxp8jvGbd0xmvVmWriZUkpOn']
REPO = Path(f'{REPO}'); SRC = Path(f'{A44}/mantis/{TASK}'); W = Path(f'{WORK}/m44work_{TASK}'); OUT = Path(f'{A44}/out_{TASK}_MANTIS')
PKG = Path(f'{A44}/facts44/{TASK}_mantis_v2_v0_v16_seed44')
DRV = {'CQ': 'CQ/L1_runs/S3_model/staging_incoming/mantis_v2_seed44_exploratory_20261116', 'LO': 'LO/L1_runs/S3_model/staging_incoming/mantis_v2_seed44_exploratory_20261118'}[TASK]
env = dict(os.environ, PYTHONPATH=str(REPO), PYTHONIOENCODING='utf-8')
def log(m): print(time.strftime('%H:%M:%S'), m, flush=True)
if not (SRC / 'DL_OK').exists():
    names = [n for n in subprocess.run(RC + ['lsf', '-R', '--files-only', f'gdrive:{DRV}'], capture_output=True, text=True).stdout.split('\n') if n.endswith('_results.tar.gz')]
    log(f'{TASK}: {len(names)} tars')
    for n in names:
        v = n.split('/')[-1].split('_')[2]; d = SRC / v; d.mkdir(parents=True, exist_ok=True)
        if not (d / n.split('/')[-1]).exists(): subprocess.run(RC + ['copy', f'gdrive:{DRV}/{n}', str(d), '-q'], check=True)
    (SRC / 'DL_OK').write_text('ok')
r = subprocess.run([sys.executable, '-u', f'{S2}/audit44_mantis.py', TASK], env=env)
if r.returncode: log('FAILED audit'); sys.exit(1)
if not (PKG / 'sha256sums.txt').exists():
    r = subprocess.run([sys.executable, 'tools/build_facts_package_mantis_lo_20261109.py', '--kind', 'mantis' if TASK == 'CQ' else 'lo_mantis', '--seed', '44', '--audit-roots', W / 'aud_W1', W / 'aud_W2', W / 'aud_W3',
                        '--cohort-roots', W / 'cohort_out', '--std-roots', W / 'std_all', '--out', PKG], cwd=REPO, env=env, capture_output=True, text=True)
    if r.returncode: log('FAILED build ' + (r.stdout + r.stderr)[-600:]); sys.exit(1)
    log('PKG_DONE ' + r.stdout[-200:].replace('\n', ' '))
log('MANTIS_FACTS_DONE ' + TASK)
