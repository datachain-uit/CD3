"""S0 profile v3: v2 plus columns recomputed from raw phase views (parity with S0 zero-cell counts verified for all task/window)."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

V2 = Path('CQ/resuilt/m13a_s0_profile_20261108_v2')
RAW = Path('CQ/resuilt/m13a_raw_view_columns_20261108')
OUT = Path('CQ/resuilt/m13a_s0_profile_20261108_v3')
OUT.mkdir(parents=True, exist_ok=True)
for task in ('CQ', 'LO'):
    p = json.loads((RAW / f'parity_{task}.json').read_text())[task]
    if not all(v['match'] for v in p.values()):
        raise SystemExit(f'Raw-view zero-cell parity failed for {task}')
frame = pd.read_csv(V2 / 's0_profile.csv')
raw = pd.concat([pd.read_csv(RAW / f'raw_view_columns_{t}.csv') for t in ('CQ', 'LO')])
key = ['task', 'window_id', 'phase_id', 'eval_split']
frame = frame.merge(raw, on=key, how='left', validate='one_to_one')
for col in ('tr_zero_activity_ratio', 'tr_inactive_learner_ratio', 'tr_mean_events_per_enrollment',
            'ev_mean_observed_length', 'ev_mean_observed_fraction', 'drift_tr_ev_psi_mean', 'drift_phase_prev_psi_mean'):
    frame[col] = frame[col + '_y']
    frame[col + '_reason'] = np.where(frame[col].isna(), 'NO_PREVIOUS_PHASE' if col == 'drift_phase_prev_psi_mean' else 'NOT_COMPUTED', None)
    frame = frame.drop(columns=[col + '_x', col + '_y'])
# Zero-cell facts for every prefix, same formulas as the S0 producer (verified at P4).
zero = frame['tr_zero_cell_count']
frame['tr_n_cells_observed_zero'] = zero
frame['tr_observed_zero_rate'] = zero / frame['tr_n_cells_observed_eligible']
frame['tr_sparsity_cell'] = (zero + frame['tr_n_cells_observed_missing']) / frame['tr_n_cells_observed_eligible']
for col in ('tr_observed_zero_rate', 'tr_sparsity_cell', 'tr_n_cells_observed_zero'):
    frame[col + '_reason'] = None
frame['tr_sparsity_cell_reason'] = None
# P4 must equal the S0 pooled values.
p4 = frame[frame.phase_id == 'P4']
assert np.allclose(p4.tr_observed_zero_rate, p4.trpool_observed_zero_rate, rtol=0, atol=1e-12)
assert np.allclose(p4.tr_sparsity_cell, p4.trpool_sparsity_cell, rtol=0, atol=1e-12)
frame = frame.drop(columns=['tr_zero_cell_count', 'tr_nonnull_cell_count', 'ev_observed_t_valid', 'ev_n', 'tr_events_monotone_violations', 'psi_n_features'])
# Quantities that reference the tr_ values depend on them: recompute temporal deltas is unchanged (missing/minority only).
req = ['tr_n_enrollments', 'ev_n_enrollments', 'tr_n_offerings', 'ev_n_offerings', 'tr_n_features_total', 'tr_n_features_static', 'tr_n_features_seq',
       'tr_class_count_c0', 'tr_class_count_c1', 'tr_class_count_c2', 'tr_imbalance_ratio', 'tr_minority_ratio', 'tr_class_entropy_norm',
       'ev_mean_observed_fraction', 'ev_mean_observed_length', 'tr_missing_rate', 'ev_missing_rate', 'tr_unavailable_rate',
       'tr_structural_absence_rate', 'tr_observed_zero_rate', 'tr_sparsity_cell', 'tr_zero_activity_ratio', 'tr_inactive_learner_ratio',
       'tr_incomplete_history_ratio', 'tr_mean_events_per_enrollment', 'tr_missing_label_mi_max', 'ev_train_overlap_share',
       'days_train_end_to_test_start', 'train_history_span_days', 'has_prev_phase', 'drift_tr_ev_psi_mean', 'drift_tr_ev_jsd_mean']
nulls = {c: int(frame[c].isna().sum()) for c in req}
bad = {c: n for c, n in nulls.items() if n}
legit = {'drift_phase_prev_psi_mean': 12, 'tr_missing_rate_prev': 12, 'tr_minority_ratio_prev': 12}
summary = {'rows': len(frame), 'required_minimum_set_null_counts': nulls, 'unexpected_nulls': bad,
           'p1_rows_legitimately_null': {'columns': list(legit), 'rows_each': 12},
           'conventions': {
               'tr_inactive_learner_ratio': 'share of TRAIN enrollments whose cumulative event count (video segments + problems + comments) did not increase in the last phase interval (P1: no event at all); chapters are not in the views',
               'ev_mean_observed_length': 'mean whole days from enrollment to the phase cutoff (T_e measured in days, not chapters)',
               'ev_mean_observed_fraction': 'mean of floor(days to cutoff) / floor(days from enrollment to window end); cutoffs sit at q=0.25/0.5/0.75/0.9',
               'drift_*_psi_mean': 'mean PSI over raw phase-matched features; decile bins from the reference non-null values plus one missing bucket; eps 1e-6',
               'tr_mean_events_per_enrollment': 'cumulative segment_count + problem_count + comment_count, NaN as 0'},
           'status': 'MINIMUM_SET_COMPLETE_CONVENTIONS_NEED_WRITER_CONFIRMATION' if not bad else 'INCOMPLETE'}
frame.to_csv(OUT / 's0_profile.csv', index=False)
frame.to_parquet(OUT / 's0_profile.parquet', index=False)
(OUT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf8')
(OUT / 's0_profile_README.md').write_text(
    '# S0 profile (M-13a) v3\n\n48 rows = 2 task x 3 window x 4 phase x 2 split. Built from S0_RAW facts, phase-prefix recomputation of V0 observed-missing masks '
    '(P4 parity vs S0 passed), split registries, and raw (unscaled) phase views. Zero-cell counts recomputed from raw views equal the S0 producer exactly at P4 for all six task/window pairs. '
    'Cell formulas: observed_zero_rate = zero / observed-eligible; sparsity_cell = (zero + observed-missing) / observed-eligible; incomplete_history_ratio = share of TRAIN enrollments with at least one observed-missing cell in the eligible region.\n\n'
    'Conventions that are choices, not source facts (need writer confirmation): ' + json.dumps(summary['conventions'], ensure_ascii=False) + '\n\n'
    'P1 has no *_prev / PSI-vs-previous values by definition (NO_PREVIOUS_PHASE). Class-conditional or label-derived quantities of the evaluation slice are not included.\n', encoding='utf8')
with (OUT / 'sha256sums.txt').open('w') as f:
    for n in ('s0_profile.csv', 's0_profile.parquet', 'summary.json', 's0_profile_README.md'):
        f.write(f"{hashlib.sha256((OUT / n).read_bytes()).hexdigest()}  {n}\n")
print(json.dumps({'status': summary['status'], 'unexpected_nulls': bad}, indent=1))
