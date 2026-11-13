"""C2 check on real data: run the audit's canonical s_leak computation (deterministic, single-thread) for one window/parent, twice, and once in
the default multi-thread mode, then compare with the canonical F1 reference table.
Usage: python tools/check_leak_probe_reproduction_20261109.py --task CQ --window W1 --parent V0 --data-root D --layout-dir DIR --reference CSV --out report.json
(--layout-dir: any standard run directory of that window/parent that holds feature_layout.json)
"""
import argparse
import json
import sys
import time
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
ap.add_argument('--window', required=True)
ap.add_argument('--parent', required=True)
ap.add_argument('--data-root', type=Path, required=True)
ap.add_argument('--layout-dir', type=Path, required=True)
ap.add_argument('--reference', type=Path, required=True)
ap.add_argument('--out', type=Path, required=True)
ap.add_argument('--skip-multithread', action='store_true')
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

args = Namespace(task=a.task, data_root=a.data_root, seed=42)
selected = {(a.window, a.parent): a.layout_dir}
reference = pd.read_csv(a.reference)
real_fit = ME.fit_missingness_probe


def run(label, deterministic):
    if not deterministic:
        ME.fit_missingness_probe = lambda x, y, *, seed=42, deterministic=True: real_fit(x, y, seed=seed, deterministic=False)
    else:
        ME.fit_missingness_probe = real_fit
    t = time.time()
    frame = A._canonical_s_leak(args, selected, deterministic=deterministic)
    ME.fit_missingness_probe = real_fit
    ref_cols = [c for c in ('window_id', 'eval_split', 'phase_id', 's_leak', 's_leak_probe_auc') if c in reference.columns]
    merged = frame.merge(reference[ref_cols], on=['window_id', 'eval_split', 'phase_id'], suffixes=('', '_reference'))
    diff = (merged.s_leak - merged.s_leak_reference).abs()
    out = {'label': label, 'seconds': round(time.time() - t, 1), 'cells': len(frame), 'probe_fit_rows': int(frame.probe_fit_rows.iloc[0]),
           'probe_n_iter': int(frame.probe_n_iter.iloc[0]) if 'probe_n_iter' in frame else None,
           'max_abs_diff_vs_reference': float(diff.max()), 'mean_abs_diff_vs_reference': float(diff.mean()),
           'within_1e-9': bool((diff <= 1e-9).all()), 'within_1e-3': bool((diff <= 1e-3).all()),  # Q-31 (a), 2026-11-13: probe reproduction tolerance (check 41) is 1e-3
           'probe_mode': str(frame.probe_mode.iloc[0]) if 'probe_mode' in frame else None, 'probe_threads': (int(frame.probe_threads.iloc[0]) if 'probe_threads' in frame and frame.probe_threads.iloc[0] is not None else None)}
    print(json.dumps(out), flush=True)
    return frame, out


res = []
f1, o1 = run('deterministic_run_1', True)
res.append(o1)
f2, o2 = run('deterministic_run_2', True)
o2['bitwise_equal_to_run_1'] = bool(np.array_equal(f1.s_leak.to_numpy(), f2.s_leak.to_numpy()) and np.array_equal(f1.s_leak_probe_auc.to_numpy(), f2.s_leak_probe_auc.to_numpy()))
o2['max_abs_diff_between_runs'] = float(np.abs(f1.s_leak.to_numpy() - f2.s_leak.to_numpy()).max())
res.append(o2)
print(json.dumps({'run1_vs_run2': o2['bitwise_equal_to_run_1']}), flush=True)
if not a.skip_multithread:
    f3, o3 = run('default_multithread', False)
    o3['max_abs_diff_vs_deterministic_run_1'] = float(np.abs(f1.s_leak.to_numpy() - f3.s_leak.to_numpy()).max())
    res.append(o3)
import platform  # noqa: E402
a.out.write_text(json.dumps({'task': a.task, 'window': a.window, 'parent': a.parent, 'runs': res, 'environment': ME.probe_environment(), 'machine': platform.platform()}, indent=1) + '\n', encoding='utf-8')
print('DONE', flush=True)
