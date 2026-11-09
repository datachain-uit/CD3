"""SEEN/UNSEEN x STRICT/OVERLAP cohort audit for LO PatchTST V0-V16 (seed 42), one pipeline at a time.

For each pipeline the result bundle(s) are streamed from Drive (rclone cat | tar), the run directories
W*/V<n>/PATCHTST/seed=42 are normalised into <work>/V<n>/LO/..., tools/audit_prediction_course_cohort.py runs on them,
and the temporary tree is deleted. The prediction salt is read from a local private file and never printed.
Usage: python tools/run_lo_patchtst_cohort_20261109.py --work W --out OUT --salt-file S [--pipelines V1 V2 ...]
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument('--work', type=Path, required=True)
ap.add_argument('--out', type=Path, required=True)
ap.add_argument('--salt-file', type=Path, required=True)
ap.add_argument('--data-root', type=Path, default=Path('downloads/vastai/LO_V3_1_clean_grain_seed42'))
ap.add_argument('--pipelines', nargs='*')
args = ap.parse_args()

ROOT = 'gdrive:LO/L1_runs/S3_model/staging_incoming/patchtst_seed42_after_credit_20261108'
V0 = 'gdrive:LO/L1_runs/S3_model/primary/family=PATCHTST/lo_patchtst_v0_seed42_20261107'
SRC = {
    'V0': ('tree', [V0]),
    'V1': ('tar', [f'{ROOT}/V1/lo_patchtst_V1_seed42_20261109_runs.tar.gz']),
    'V2': ('tar', [f'{ROOT}/V2/lo_patchtst_v2_w1_w2_20261107.tar.gz', f'{ROOT}/V2/lo_patchtst_v2_w3_20261107.tar.gz']),
    'V3': ('tar', [f'{ROOT}/V3/lo_patchtst_V3_seed42_20261109_runs.tar.gz']),
    'V4': ('tar', [f'{ROOT}/V4/lo_patchtst_V4_seed42_20261109_runs.tar.gz']),
    'V7': ('tar', [f'{ROOT}/V7/lo_v7_w1_w2_partial_20261107.tar.gz', f'{ROOT}/V7/lo_v7_w3_closure_20261107.tar.gz']),
    'V11': ('tar', [f'{ROOT}/V11/lo_patchtst_V11_seed42_20261109_runs.tar.gz']),
    'V12': ('tar', [f'{ROOT}/V12/lo_patchtst_V12_seed42_20261109_runs.tar.gz']),
}
for v in ('V5', 'V6', 'V8', 'V9', 'V10', 'V13', 'V14', 'V15', 'V16'):
    SRC[v] = ('tar', [f'{ROOT}/{v}/lo_patch_{v}_resume_credit_20261107.tar.gz'])

RCLONE = ['rclone', '--drive-root-folder-id', '1GWiedVROrxp8jvGbd0xmvVmWriZUkpOn']


def fetch(kind, items, dest):
    dest.mkdir(parents=True, exist_ok=True)
    for item in items:
        if kind == 'tree':
            subprocess.run(RCLONE + ['copy', item, str(dest), '--exclude', '*.log', '--transfers', '4', '-q'], check=True)
        else:
            cat = subprocess.Popen(RCLONE + ['cat', item], stdout=subprocess.PIPE)
            subprocess.run(['tar', 'xz', '-C', str(dest)], stdin=cat.stdout, check=True)
            cat.wait()


def normalise(raw, v, dest_root):
    found = {}
    for p in raw.rglob('seed=42'):
        parts = p.parts
        if p.parent.name != 'PATCHTST' or p.parent.parent.name != v or p.parent.parent.parent.name not in ('W1', 'W2', 'W3'):
            continue
        if not (p / 'predictions').is_dir() or len(list((p / 'predictions').glob('*.parquet'))) != 8:
            continue
        w = p.parent.parent.parent.name
        if any(s in str(p) for s in ('pre_resume', 'failed', 'backup')) and w in found:
            continue
        found[w] = p
    for w, p in found.items():
        target = dest_root / 'LO' / w / v / 'PATCHTST' / 'seed=42'
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(p), str(target))
    return sorted(found)


todo = args.pipelines or list(SRC)
status = {}
for v in todo:
    raw = args.work / v / 'raw'
    norm = args.work / v / 'norm'
    shutil.rmtree(args.work / v, ignore_errors=True)
    try:
        kind, items = SRC[v]
        fetch(kind, items, raw)
        windows = normalise(raw, v, norm)
        shutil.rmtree(raw, ignore_errors=True)
        res_rows = []
        for w in windows:
            run = norm / 'LO' / w / v / 'PATCHTST' / 'seed=42'
            m = json.loads((run / 'run_manifest.json').read_text(encoding='utf-8'))
            h = pd.read_parquet(run / 'train_history.parquet')
            m['train_seconds'] = float(h.train_seconds.sum())
            res_rows.append(m)
        (args.out / v).mkdir(parents=True, exist_ok=True)
        pd.DataFrame(res_rows).to_parquet(args.out / v / 'run_manifests.parquet', index=False)
        if windows != ['W1', 'W2', 'W3']:
            raise RuntimeError(f'{v}: windows found {windows}')
        out = args.out / v
        proc = subprocess.run([sys.executable, 'tools/audit_prediction_course_cohort.py', '--data-root', str(args.data_root),
                               '--model-root', str(norm), '--output-root', str(out), '--task', 'LO', '--pipeline-id', v,
                               '--model-name', 'PATCHTST', '--seed', '42', '--prediction-salt-file', str(args.salt_file)],
                              capture_output=True, text=True)
        if proc.returncode:
            raise RuntimeError(f'{v}: audit failed: ' + proc.stderr.strip().splitlines()[-1][:300])
        status[v] = 'OK'
    except Exception as exc:  # keep going with the next pipeline
        status[v] = f'FAIL {exc}'
    finally:
        shutil.rmtree(args.work / v, ignore_errors=True)
    print(v, status[v], flush=True)
print('LO_COHORT_DONE', {k: ('OK' if x == 'OK' else 'FAIL') for k, x in status.items()}, flush=True)
