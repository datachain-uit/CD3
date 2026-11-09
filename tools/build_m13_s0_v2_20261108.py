"""Merge exact phase-prefix mask recomputation, split-registry timing and overlap into the S0 partial.

Inputs are the audited partial profile and prefix_mask_profile (P4 parity vs S0 passed
for every task/window/split). Quantities that cannot be recovered are left NULL with a reason.
"""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

SRC = Path('CQ/resuilt/m13a_s0_profile_20261108')
OUT = Path('CQ/resuilt/m13a_s0_profile_20261108_v2')
OUT.mkdir(parents=True, exist_ok=True)
SPLIT = {'CQ': Path('CQ/resuilt/m07_split_evidence_received_20261107/split_registry.csv'),
         'LO': Path('LO/resuilt/lo_split_evidence_20261106/split_registry_source.csv')}

frame = pd.read_csv(SRC / 's0_profile_partial.csv')
mask = pd.read_csv(SRC / 'prefix_mask_profile.csv')
if (mask.p4_s0_count_parity != 'PASS').any() or len(mask) != 48:
    raise ValueError('Prefix mask profile did not pass S0 parity')
mask = mask.set_index(['task', 'window_id', 'phase_id', 'split'])
CELLS = {'n_cells_total': 'n_cells_total', 'n_cells_unavailable': 'n_cells_unavailable',
         'n_cells_structural_absence': 'n_cells_structural_absence',
         'n_cells_observed_eligible': 'n_cells_observed_eligible',
         'n_cells_observed_value': 'n_cells_observed_value',
         'n_cells_observed_missing': 'n_cells_observed_missing'}
RATES = {'missing_rate': 'missing_rate', 'unavailable_rate': 'unavailable_rate',
         'structural_absence_rate': 'structural_absence_rate'}
ZERO_REASON = 'ZERO_CELL_RATE_NOT_RECOVERABLE_FROM_SCALED_INPUTS_PREFIX_NOT_P4'

def put(row, name, value, reason=None):
    row[name] = value
    if (name + '_reason') in row.index or reason:
        row[name + '_reason'] = reason

records = []
for _, row in frame.iterrows():
    row = row.copy()
    key = (row.task, row.window_id, row.phase_id)
    tr = mask.loc[key + ('TRAIN',)]
    for field, src in CELLS.items():
        put(row, 'tr_' + field, int(tr[src]))
    for field, src in RATES.items():
        put(row, 'tr_' + field, float(tr[src]))
    put(row, 'tr_incomplete_history_ratio', float(tr.incomplete_history_ratio))
    put(row, 'tr_missing_label_mi_max', float(tr.missing_label_mi_max))
    if row.phase_id == 'P4':
        # S0 full trajectory equals P4 prefix; zero-cell facts are exact there.
        put(row, 'tr_observed_zero_rate', row.trpool_observed_zero_rate)
        put(row, 'tr_n_cells_observed_zero', row.trpool_n_cells_observed_zero)
        put(row, 'tr_sparsity_cell', row.trpool_sparsity_cell)
        put(row, 'tr_sparsity_cell_reason', None)
    else:
        for name in ('tr_observed_zero_rate', 'tr_sparsity_cell', 'tr_n_cells_observed_zero'):
            put(row, name, np.nan, ZERO_REASON)
        row['tr_sparsity_cell_reason'] = ZERO_REASON
    if row.eval_split == 'VALIDATION':
        ev = mask.loc[key + ('VALIDATION',)]
        for field, src in CELLS.items():
            put(row, 'ev_' + field, int(ev[src]))
        put(row, 'ev_missing_rate', float(ev.missing_rate))
        if row.phase_id != 'P4':
            put(row, 'ev_n_cells_observed_zero', np.nan, ZERO_REASON)
    split_row = pd.read_csv(SPLIT[row.task]).set_index('window_id').loc[row.window_id]
    put(row, 'days_train_end_to_test_start', float(split_row.days_train_end_to_test_start))
    put(row, 'train_history_span_days', float(split_row.train_history_span_days))
    prefix = 'test' if row.eval_split == 'TEST' else 'validation'
    share = float(split_row[f'{prefix}_offering_start_overlap_share'])
    if row.task == 'CQ' and abs(share - float(row.ev_train_overlap_share)) > 1e-12:
        raise ValueError('CQ overlap disagrees with the M-07 table')
    put(row, 'ev_train_overlap_share', share)
    records.append(row)
out = pd.DataFrame(records)

# Recompute previous-phase and delta-to-P1 temporal columns from prefix-correct values.
base_keys = ['task', 'window_id', 'eval_split']
for field in ('tr_missing_rate', 'tr_minority_ratio'):
    ordered = out.sort_values('phase_id')
    out[field + '_prev'] = ordered.groupby(base_keys)[field].shift().reindex(out.index)
    out[field + '_delta_prev'] = out[field] - out[field + '_prev']
    out[field + '_prev_reason'] = np.where(out.phase_id.eq('P1'), 'NO_PREVIOUS_PHASE', None)
    p1 = out[out.phase_id.eq('P1')].set_index(base_keys)[field]
    out[field + '_delta_p1'] = [r[field] - p1.loc[(r.task, r.window_id, r.eval_split)] for _, r in out.iterrows()]
out['drift_phase_prev_psi_mean_reason'] = np.where(out.phase_id.eq('P1'), 'NO_PREVIOUS_PHASE', 'PSI_NOT_IN_S0_FACTS_RAW_DISTRIBUTIONS_REQUIRED')
out['drift_tr_ev_psi_mean_reason'] = 'PSI_NOT_IN_S0_FACTS_RAW_DISTRIBUTIONS_REQUIRED'
RAW = 'RAW_EVENT_COUNTS_REQUIRED_MODEL_INPUTS_ARE_SCALED'
for name in ('tr_zero_activity_ratio', 'tr_inactive_learner_ratio', 'tr_mean_events_per_enrollment'):
    out[name + '_reason'] = RAW
for name in ('ev_mean_observed_fraction', 'ev_mean_observed_length'):
    out[name + '_reason'] = 'CUTOFF_Q_AND_COURSE_LENGTH_Te_REQUIRED_FROM_PHASE_BUILDER'
# Drop pool columns' prefix-NULL reasons that no longer apply.
for column in [c for c in out.columns if c.endswith('_reason')]:
    value_column = column[:-len('_reason')]
    if value_column in out.columns:
        filled = out[value_column].notna()
        out.loc[filled & ~out[column].astype(str).str.startswith('NO_PREVIOUS'), column] = None

if len(out) != 48 or out.duplicated(['task', 'window_id', 'phase_id', 'eval_split']).any():
    raise ValueError('Coverage mismatch')
REQUIRED = ['tr_n_enrollments', 'ev_n_enrollments', 'tr_n_offerings', 'ev_n_offerings', 'tr_n_features_total',
            'tr_n_features_static', 'tr_n_features_seq', 'tr_class_count_c0', 'tr_class_count_c1', 'tr_class_count_c2',
            'tr_imbalance_ratio', 'tr_minority_ratio', 'tr_class_entropy_norm', 'ev_mean_observed_fraction',
            'ev_mean_observed_length', 'tr_missing_rate', 'ev_missing_rate', 'tr_unavailable_rate',
            'tr_structural_absence_rate', 'tr_observed_zero_rate', 'tr_sparsity_cell', 'tr_zero_activity_ratio',
            'tr_inactive_learner_ratio', 'tr_incomplete_history_ratio', 'tr_mean_events_per_enrollment',
            'tr_missing_label_mi_max', 'ev_train_overlap_share', 'days_train_end_to_test_start',
            'train_history_span_days', 'has_prev_phase', 'drift_tr_ev_psi_mean', 'drift_tr_ev_jsd_mean',
            'drift_phase_prev_psi_mean', 'tr_missing_rate_prev', 'tr_missing_rate_delta_p1',
            'tr_minority_ratio_prev', 'tr_minority_ratio_delta_p1']
coverage = {c: int(out[c].notna().sum()) for c in REQUIRED}
unmet = {c: n for c, n in coverage.items() if n < 48}
# P1 has no *_prev by definition: 8 of 48 rows legitimately NULL.
legit = {'drift_phase_prev_psi_mean', 'tr_missing_rate_prev', 'tr_minority_ratio_prev'}
summary = {'rows': 48, 'status': 'PARTIAL_NOT_FOR_OFFICIAL_ASSEMBLY',
           'required_columns_fully_populated': sorted(c for c, n in coverage.items() if n == 48),
           'required_columns_partially_populated': {c: n for c, n in unmet.items() if n > 0},
           'required_columns_all_null': sorted(c for c, n in coverage.items() if n == 0),
           'p1_legitimately_null': sorted(legit),
           'sources': {'prefix_mask_profile': 'P4 count parity vs S0 PASS for 12 task/window/split',
                       'timing': 'split registries (CQ: M-07 received; LO: lo_split_evidence_20261106)',
                       'overlap': 'offering_start_overlap_share per split from the same registries'}}
out.to_csv(OUT / 's0_profile.csv', index=False)
out.to_parquet(OUT / 's0_profile.parquet', index=False)
(OUT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf8')
(OUT / 'README.md').write_text(
    '# S0 profile v2 — still not an M-14 input\n\n'
    'Builds on `m13a_s0_profile_20261108` (S0_RAW exact facts). New here: TRAIN/VALIDATION cell counts and rates, '
    'incomplete_history_ratio and tr_missing_label_mi_max are recomputed at each phase prefix from V0 observed-missing masks '
    '(P4 exactly matches S0 counts for every task/window/split before any prefix value is accepted). Zero-cell rates and sparsity '
    'are exact only at P4; at P1-P3 they are NULL because model inputs are scaled and zeros are not recoverable. '
    'days_train_end_to_test_start, train_history_span_days and ev_train_overlap_share come from the split registries '
    '(overlap = share of evaluation enrollments whose offering starts before tau_w, per split). '
    'Still NULL with reasons: tr_zero_activity_ratio, tr_inactive_learner_ratio, tr_mean_events_per_enrollment '
    '(raw event counts needed), ev_mean_observed_fraction / ev_mean_observed_length (cutoff q and course length T_e from the '
    'phase builder), drift_tr_ev_psi_mean and drift_phase_prev_psi_mean (raw distributions needed; S0 holds JSD only). '
    'M-13a is therefore NOT satisfied until these are produced from raw sources.\n', encoding='utf8')
with (OUT / 'sha256sums.txt').open('w', encoding='utf8') as f:
    for name in ('s0_profile.csv', 's0_profile.parquet', 'summary.json', 'README.md'):
        f.write(f"{hashlib.sha256((OUT / name).read_bytes()).hexdigest()}  {name}\n")
print(json.dumps(summary, indent=2))
