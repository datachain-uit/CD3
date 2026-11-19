"""Build the s_leak reference table of ONE master seed on the standard probe machine (host 17429): the audit's canonical s_leak (missingness probe fitted with seed=<seed> on the
train rows of parent V0, scored on TEST and VALIDATION, phases P1-P4) in the default multi-thread mode, for the three windows. Output has the same columns as
s_leak_reference_{CQ,LO}.csv (task, window_id, eval_split, phase_id, s_leak, s_leak_probe_auc) plus a JSON with probe mode, thread count and library versions.
Why per seed: fit_missingness_probe(..., seed=args.seed) -> the value depends on the seed (user, 2026-11-15).
usage: python tools/build_sleak_reference_seed_20261115.py --task LO --seed 44 --data-root DATA --layout-run-root RUNROOT --out-dir OUT
  --layout-run-root: a run root with <task>/<window>/V0/<family>/seed=<N>/feature_layout.json (any family); the first family found per window is used."""
import argparse
import json
import platform
import sys
from argparse import Namespace
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools'))

ap = argparse.ArgumentParser()
ap.add_argument('--task', required=True)
ap.add_argument('--seed', type=int, required=True)
ap.add_argument('--data-root', type=Path, required=True)
ap.add_argument('--layout-run-root', type=Path, required=True)
ap.add_argument('--layout-seed', type=int, default=None, help='seed folder name of the layout run (default: --seed)')
ap.add_argument('--out-dir', type=Path, required=True)
a = ap.parse_args()

_original = pd.read_parquet
LABELS = ('CQ_label_final', 'LO_performance_label_3')


def _pruned(path, *args, **kw):
    p = str(path).replace(chr(92), '/')
    if kw.get('columns') is None and not args and p.endswith('.parquet') and ('/train/' in p or '/evaluation/' in p):
        names = pq.ParquetFile(path).schema_arrow.names
        keep = [n for n in names if n in LABELS or n.startswith('missing__') or n.startswith('phase_available_')
                or n.endswith(tuple(f'_observed_mask_P{i}' for i in range(1, 5)))]
        return _original(path, columns=keep, **kw)
    return _original(path, *args, **kw)


pd.read_parquet = _pruned
import metrics_core.evaluation as ME  # noqa: E402
import vastai_audit_shared as A  # noqa: E402

lseed = a.layout_seed if a.layout_seed is not None else a.seed
selected = {}
for w in ('W1', 'W2', 'W3'):
    for parent in ('V0', 'V1', 'V5', 'V9', 'V13'):   # the audit computes one probe per window AND per parent pipeline
        hits = sorted((a.layout_run_root / a.task / w / parent).glob(f'*/seed={lseed}/feature_layout.json'))
        if not hits:
            raise SystemExit(f'no feature_layout.json for {a.task} {w} {parent} seed {lseed} under {a.layout_run_root}')
        selected[(w, parent)] = hits[0].parent
args = Namespace(task=a.task, data_root=a.data_root, seed=a.seed)
real_fit = ME.fit_missingness_probe
ME.fit_missingness_probe = lambda x, y, *, seed=42, deterministic=True: real_fit(x, y, seed=seed, deterministic=False)   # default multi-thread mode, as the earlier reference tables
frame = A._canonical_s_leak(args, selected, deterministic=False)
ME.fit_missingness_probe = real_fit
a.out_dir.mkdir(parents=True, exist_ok=True)
full = frame[['task', 'window_id', 'parent_pipeline', 'eval_split', 'phase_id', 's_leak', 's_leak_probe_auc']].sort_values(['window_id', 'parent_pipeline', 'eval_split', 'phase_id'])
full.to_csv(a.out_dir / f's_leak_by_parent_{a.task}_seed{a.seed}.csv', index=False, lineterminator='\n')
g = full.groupby(['window_id', 'eval_split', 'phase_id'])['s_leak']
spread = float((g.max() - g.min()).max())          # largest difference between the parents of one cell
out = full[full.parent_pipeline == 'V0'][['task', 'window_id', 'eval_split', 'phase_id', 's_leak', 's_leak_probe_auc']].reset_index(drop=True)
csv = a.out_dir / f's_leak_reference_{a.task}_seed{a.seed}.csv'
out.to_csv(csv, index=False, lineterminator='\n')
info = {'task': a.task, 'seed': a.seed, 'cells': int(len(out)), 'max_spread_across_parents': spread, 'parents': ['V0', 'V1', 'V5', 'V9', 'V13'], 'rows_per_cell_probe_fit': int(frame.probe_fit_rows.iloc[0]) if 'probe_fit_rows' in frame else None,
        'probe_mode': str(frame.probe_mode.iloc[0]) if 'probe_mode' in frame else 'default_multithread',
        'probe_threads': int(frame.probe_threads.iloc[0]) if 'probe_threads' in frame and pd.notna(frame.probe_threads.iloc[0]) else None,
        'platform': platform.platform(), 'python': platform.python_version(), 'numpy': np.__version__, 'pandas': pd.__version__}
try:
    import sklearn
    info['scikit_learn'] = sklearn.__version__
except Exception:  # noqa: BLE001
    pass
(a.out_dir / f's_leak_reference_{a.task}_seed{a.seed}.json').write_text(json.dumps(info, indent=1), encoding='utf-8')
print(json.dumps(info), flush=True)
print(out.groupby('window_id')[['s_leak', 's_leak_probe_auc']].mean().to_string(), flush=True)
