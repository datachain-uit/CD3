"""Compute the remaining S0 columns from raw (unscaled) phase views.

Validated against S0 at P4 (zero-cell counts equal the S0 producer exactly). All conventions are
written into the output README; the ones that are choices (inactive rule, day-based T_e, PSI bins)
are flagged as conventions, not facts.
"""
import glob
import json
import re
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path('.')
OUT = ROOT / 'CQ/resuilt/m13a_raw_view_columns_20261108'
OUT.mkdir(parents=True, exist_ok=True)
CFG = {
    'CQ': dict(views='downloads/raw_views_20261108/CQ/phase_views_v2_2', test='downloads/raw_views_20261108/CQ_test',
               v0='downloads/vastai/CQ_V2_2_clean_grain_seed42/train/W1/V0/train.parquet',
               s0='CQ/resuilt/s0_current_cq_20261108/L2_facts/task=CQ'),
    'LO': dict(views='downloads/raw_views_20261108/LO/phase_views_v3_1_scored_signal_excluded', test='downloads/raw_views_20261108/LO_test',
               v0='downloads/vastai/LO_V3_1_clean_grain_seed42/train/W1/V0/train.parquet',
               s0='LO/resuilt/s0_current_lo_modal_20261108/L2_facts'),
}
WINDOWS = ('W1', 'W2', 'W3')
PHASE = re.compile(r'^(.*)_P([1-4])$')
EPS = 1e-6
Q = {1: 0.25, 2: 0.5, 3: 0.75, 4: 0.9}

def psi(ref, cmp_):
    """PSI with decile bins from ref non-null values plus one missing bucket."""
    ref_nn, cmp_nn = ref[~np.isnan(ref)], cmp_[~np.isnan(cmp_)]
    edges = np.unique(np.quantile(ref_nn, np.linspace(0.1, 0.9, 9))) if len(ref_nn) else np.array([])
    def dist(x_nn, n_total):
        counts = np.bincount(np.searchsorted(edges, x_nn, side='right'), minlength=len(edges) + 1).astype(float) if len(x_nn) else np.zeros(len(edges) + 1)
        return np.append(counts, n_total - len(x_nn)) / max(n_total, 1)
    p, q = np.clip(dist(ref_nn, len(ref)), EPS, None), np.clip(dist(cmp_nn, len(cmp_)), EPS, None)
    p, q = p / p.sum(), q / q.sum()
    return float(np.sum((p - q) * np.log(p / q)))

def run(task):
    cfg = CFG[task]
    view = glob.glob(cfg['views'] + '/part-*.parquet')[0]
    tests = {k: glob.glob(f"{cfg['test']}/P{k}/part-*.parquet")[0] for k in range(1, 5)}
    names = pq.ParquetFile(view).schema_arrow.names
    stems = [n[len('missing__'):] for n in pq.ParquetFile(cfg['v0']).schema_arrow.names if n.startswith('missing__')]
    stems = [s for s in stems if s in names]
    phase_of = {s: (int(PHASE.match(s).group(2)) if PHASE.match(s) else 0) for s in stems}
    cell_cols = {k: [s for s in stems if phase_of[s] <= k] for k in range(1, 5)}
    ev_cols = [f'{m}_P{k}' for m in ('segment_count', 'problem_count', 'comment_count') for k in range(1, 5)]
    time_cols = ['window_end_exclusive'] + [f'cutoff_time_P{k}' for k in range(1, 5)]
    acc = {}
    def slot(window, kind, k):
        return acc.setdefault((window, kind, k), dict(n=0, events=0.0, zero_act=0, inactive=0, zero_cells=0, nonnull_cells=0,
                                                       t_valid=0, sum_len=0.0, sum_frac=0.0, monotone_bad=0))
    def update_time(a, d, k):
        end = pd.to_datetime(d['window_end_exclusive'])
        enroll = pd.to_datetime(d['enrollment_id'].str.split('::').str[2])
        cut = pd.to_datetime(d[f'cutoff_time_P{k}'])
        t_e = np.floor((end - enroll).dt.total_seconds() / 86400)
        ok = (t_e > 0) & cut.notna()
        length = np.floor((cut[ok] - enroll[ok]).dt.total_seconds() / 86400)
        a['t_valid'] += int(ok.sum()); a['sum_len'] += float(length.sum()); a['sum_frac'] += float((length / t_e[ok]).sum())
    # Pass A: train and validation phase view, all four phases per row.
    hour_cols = [f'most_common_hour_P{k}' for k in range(1, 5)]
    read = ['window', 'split', 'enrollment_id'] + time_cols + ev_cols + stems + hour_cols
    pf = pq.ParquetFile(view)
    for batch in pf.iter_batches(batch_size=150000, columns=list(dict.fromkeys(read))):
        d = batch.to_pandas()
        for window in WINDOWS:
            for split, kind in (('train', 'TRAIN'), ('validation', 'VALIDATION')):
                g = d[(d.window == window) & (d.split == split)]
                if g.empty:
                    continue
                prev_total = np.zeros(len(g))
                X = {k: g[cell_cols[k]].to_numpy(dtype=float) for k in range(1, 5)} if kind == 'TRAIN' else None
                for k in range(1, 5):
                    a = slot(window, kind, k)
                    total = sum(g[f'{m}_P{k}'].fillna(0).to_numpy(dtype=float) for m in ('segment_count', 'problem_count', 'comment_count'))
                    a['n'] += len(g); a['events'] += float(total.sum()); a['zero_act'] += int((total == 0).sum())
                    a['inactive'] += int(((total - prev_total) == 0).sum()); a['monotone_bad'] += int((total < prev_total).sum())
                    prev_total = total
                    if X is not None:
                        a['zero_cells'] += int((X[k] == 0).sum()); a['nonnull_cells'] += int((~np.isnan(X[k])).sum())
                        # The model inputs encode the hour as sin/cos: sin is exactly 0 at hour 0, and each non-null hour makes two cells.
                        for j in range(1, k + 1):
                            hour = g[f'most_common_hour_P{j}'].to_numpy(dtype=float)
                            a['zero_cells'] += int((hour == 0).sum()); a['nonnull_cells'] += 2 * int((~np.isnan(hour)).sum())
                    update_time(a, g, k)
    # Test prefix views: observed length and fraction only.
    for k, path in tests.items():
        for batch in pq.ParquetFile(path).iter_batches(batch_size=200000, columns=['window', 'split', 'enrollment_id'] + time_cols):
            d = batch.to_pandas()
            for window in WINDOWS:
                g = d[(d.window == window) & (d.split == 'test')]
                if len(g):
                    a = slot(window, 'TEST', k); a['n'] += len(g); update_time(a, g, k)
    # PSI, per base feature.
    bases = sorted({PHASE.match(s).group(1) for s in stems if PHASE.match(s)})
    psi_vals = {}
    for base in bases:
        cols = [f'{base}_P{k}' for k in range(1, 5)]
        if not all(c in names for c in cols):
            continue
        t = pq.read_table(view, columns=['window', 'split'] + cols).to_pandas()
        test_t = {k: pq.read_table(tests[k], columns=['window', 'split', f'{base}_P{k}']).to_pandas() for k in range(1, 5)}
        for window in WINDOWS:
            tr = t[(t.window == window) & (t.split == 'train')]
            va = t[(t.window == window) & (t.split == 'validation')]
            te = {k: test_t[k][(test_t[k].window == window) & (test_t[k].split == 'test')][f'{base}_P{k}'].to_numpy(dtype=float) for k in range(1, 5)}
            for k in range(1, 5):
                ref = tr[f'{base}_P{k}'].to_numpy(dtype=float)
                evals = {'VALIDATION': va[f'{base}_P{k}'].to_numpy(dtype=float), 'TEST': te[k]}
                prevs = {'VALIDATION': va[f'{base}_P{k-1}'].to_numpy(dtype=float) if k > 1 else None,
                         'TEST': te[k - 1] if k > 1 else None}
                for kind, vals in evals.items():
                    psi_vals.setdefault((window, kind, k, 'tr_ev'), []).append(psi(ref, vals))
                    if prevs[kind] is not None:
                        psi_vals.setdefault((window, kind, k, 'prev'), []).append(psi(prevs[kind], vals))
        print(json.dumps({'task': task, 'psi_base_done': base}), flush=True)
    # Parity with the S0 producer at P4 (TRAIN zero cells).
    parity = {}
    for window in WINDOWS:
        dq = pd.read_parquet(f"{cfg['s0']}/window_id={window}/phase_id=P4/dq_feature_profile.parquet")
        ref = dq[(dq.split == 'TRAIN') & (dq.feature_family == 'all')].iloc[0]
        parity[window] = dict(raw_zero=acc[(window, 'TRAIN', 4)]['zero_cells'], s0_zero=int(ref.n_cells_observed_zero),
                              match=acc[(window, 'TRAIN', 4)]['zero_cells'] == int(ref.n_cells_observed_zero))
    rows = []
    for window in WINDOWS:
        for k in range(1, 5):
            tr = acc[(window, 'TRAIN', k)]
            for kind in ('VALIDATION', 'TEST'):
                ev = acc[(window, kind, k)]
                rows.append(dict(task=task, window_id=window, phase_id=f'P{k}', eval_split=kind,
                    tr_zero_activity_ratio=tr['zero_act'] / tr['n'], tr_inactive_learner_ratio=tr['inactive'] / tr['n'],
                    tr_mean_events_per_enrollment=tr['events'] / tr['n'], tr_zero_cell_count=tr['zero_cells'], tr_nonnull_cell_count=tr['nonnull_cells'],
                    ev_mean_observed_length=ev['sum_len'] / ev['t_valid'], ev_mean_observed_fraction=ev['sum_frac'] / ev['t_valid'],
                    ev_observed_t_valid=ev['t_valid'], ev_n=ev['n'], tr_events_monotone_violations=tr['monotone_bad'],
                    drift_tr_ev_psi_mean=float(np.mean(psi_vals[(window, kind, k, 'tr_ev')])),
                    drift_phase_prev_psi_mean=(float(np.mean(psi_vals[(window, kind, k, 'prev')])) if k > 1 else np.nan),
                    psi_n_features=len(psi_vals[(window, kind, k, 'tr_ev')])))
    return pd.DataFrame(rows), parity

if __name__ == '__main__':
    frames, parities = [], {}
    for task in (sys.argv[1:] or ['CQ', 'LO']):
        f, p = run(task)
        frames.append(f); parities[task] = p
        f.to_csv(OUT / f'raw_view_columns_{task}.csv', index=False)
    (OUT / ('parity_' + '_'.join(parities) + '.json')).write_text(json.dumps(parities, indent=2) + '\n', encoding='utf8')
    print(json.dumps(parities, indent=2))
