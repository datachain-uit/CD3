"""LO Mantis (MANTIS_V2, seed 42) V0-V16 x W1-W3: extract -> standardise -> standard audit -> cohort audit -> facts package, window by window with
checkpoint markers so that it can be re-run. Usage: python tools/run_lo_mantis_audit_pipeline_20261110.py --work DIR [--skip-w1-audit-wait]
Inputs: the 51 result tars (upload_staging/lo_mantis_bk), the LO code tar (runner), the LO clean-grain data root, the private prediction salt (never printed)."""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser()
ap.add_argument('--work', type=Path, required=True)
ap.add_argument('--tars', type=Path, default=ROOT / 'upload_staging/lo_mantis_bk')
ap.add_argument('--data-root', type=Path, default=ROOT / 'downloads/vastai/LO_V3_1_clean_grain_seed42')
ap.add_argument('--salt-file', type=Path, default=ROOT / 'downloads/private/lo_grid_prediction_salt')
ap.add_argument('--reference', type=Path, default=ROOT / 'CQ/resuilt/s_leak_reference_20261109/s_leak_reference_LO.csv')
ap.add_argument('--code-tar', type=Path, required=True)
ap.add_argument('--runner', type=Path, required=True)
ap.add_argument('--pip-freeze', type=Path, required=True)
ap.add_argument('--tolerance', default='1e-3')
args = ap.parse_args()
W = args.work
W.mkdir(parents=True, exist_ok=True)
LOG = W / 'pipeline.log'
PIPES = [f'V{i}' for i in range(17)]


def log(m):
    with LOG.open('a', encoding='utf-8') as f:
        f.write(f'{time.strftime("%H:%M:%S")} {m}\n')
    print(m, flush=True)


def run(cmd, logname):
    log('RUN ' + ' '.join(str(c) for c in cmd)[:200])
    with (W / logname).open('a', encoding='utf-8') as f:
        r = subprocess.run([str(c) for c in cmd], stdout=f, stderr=subprocess.STDOUT, cwd=ROOT, env={**os.environ, 'MSYS_NO_PATHCONV': '1'})
    if r.returncode:
        log(f'FAILED rc={r.returncode} {logname}')
        raise SystemExit(f'step failed: {logname}')


def audit_running():
    out = subprocess.run(['powershell', '-c', "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'run_standard_audit_pruned' -and $_.Name -match 'python' } | Measure-Object | Select -Expand Count"],
                         capture_output=True, text=True).stdout.strip()
    return out not in ('', '0')


for win in ('W1', 'W2', 'W3'):
    mark = W / f'DONE_{win}'
    if mark.exists():
        log(f'{win} already done')
        continue
    ex, std, aud = W / f'ex_{win}', W / f'std_{win}', W / f'aud_{win}'
    if win == 'W1':  # a first W1 audit may be running from the interactive session
        while audit_running():
            time.sleep(30)
        if (W / 'std').exists() and not std.exists():
            (W / 'std').rename(std)
        if (W / 'aud_W1').exists() and any((W / 'aud_W1').rglob('sanity_components.parquet')):
            mark.write_text('done by the interactive run\n')
            log('W1 audit present; marked done')
            if ex.exists():
                shutil.rmtree(ex, ignore_errors=True)
            continue
    if not ex.exists():
        ex.mkdir()
        for t in sorted(args.tars.glob(f'mantis_lo_V*_{win}_20261109_results.tar.gz')):
            with tarfile.open(t) as tf:
                members = [m for m in tf.getmembers() if m.name.startswith('runs/') or m.name.startswith('state/')]
                tf.extractall(ex, members=members)
        log(f'{win}: extracted {len(list((ex / "runs" / win).glob("V*")))} cells')
    if not std.exists():
        run([sys.executable, 'tools/mantis_standardize_runs_20261110.py', '--task', 'LO', '--runner-rel', 'tools/run_mantis_grid_zstd_20261109.py', '--data-root', args.data_root,
             '--out', std, '--runner', args.runner, '--code-tar', args.code_tar, '--pip-freeze', args.pip_freeze, '--extracted', ex], f'standardize_{win}.log')
    shutil.rmtree(ex, ignore_errors=True)
    if aud.exists():
        shutil.rmtree(aud, ignore_errors=True)
    aud.mkdir()
    run([sys.executable, '-u', 'tools/run_standard_audit_pruned_20261108.py', '--task', 'LO', '--data-root', args.data_root, '--run-root', std, '--audit-root', aud,
         '--model-name', 'MANTIS_V2', '--seed', '42', '--bootstrap-repetitions', '2000', '--allow-partial', '--s-leak-reference', args.reference,
         '--s-leak-tolerance', args.tolerance], f'audit_{win}.log')
    mark.write_text('done\n')
    log(f'{win} audited')

# merged standard tree for the cohort audit
allroot = W / 'std_all'
if not (W / 'COHORT_DONE').exists():
    for win in ('W1', 'W2', 'W3'):
        src = W / f'std_{win}' / 'LO' / win
        dst = allroot / 'LO' / win
        if src.exists() and not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dst)
    for v in PIPES:
        out = W / 'cohort_out' / v
        if (out / 'summary.json').is_file():
            continue
        run([sys.executable, 'tools/audit_prediction_course_cohort.py', '--data-root', args.data_root, '--model-root', allroot, '--output-root', W / 'cohort_out' / v,
             '--task', 'LO', '--pipeline-id', v, '--model-name', 'MANTIS_V2', '--seed', '42', '--prediction-salt-file', args.salt_file], f'cohort_{v}.log')
    (W / 'COHORT_DONE').write_text('done\n')
    log('cohort audit done')

pkg = W / 'pkg_raw'
if not pkg.exists():
    run([sys.executable, 'tools/build_facts_package_mantis_lo_20261109.py', '--kind', 'lo_mantis', '--audit-roots', *[W / f'aud_{w}' for w in ('W1', 'W2', 'W3')],
         '--cohort-roots', W / 'cohort_out', '--std-roots', allroot, '--out', pkg], 'package.log')
log('PIPELINE_DONE (raw facts package built; s_leak copy and receipts follow)')
