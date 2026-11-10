"""S0 profile v4 (M-13a): v3 without tr_inactive_learner_ratio (Q-28 (c), writing-side recommendation, applied 2026-11-09, author ratification pending).

The column's candidate definition ("no event before the phase cutoff") equals tr_zero_activity_ratio already in the profile, and every
inactivity share is 0.96-0.99 because 97-99 % of enrollments have no event; it carried no information, so it leaves the minimum set.
All other columns, values and conventions of v3 are unchanged. The required minimum set is re-checked for NULLs.
"""
import hashlib
import json
from pathlib import Path
import pandas as pd

V3 = Path('CQ/resuilt/m13a_s0_profile_20261108_v3')
OUT = Path('CQ/resuilt/m13a_s0_profile_20261109_v4')
OUT.mkdir(parents=True, exist_ok=True)
DROP = ['tr_inactive_learner_ratio', 'tr_inactive_learner_ratio_reason']
f = pd.read_parquet(V3 / 's0_profile.parquet')
assert (f['tr_zero_activity_ratio'] <= f['tr_inactive_learner_ratio'] + 1e-12).all()
same_p1 = f[f.phase_id == 'P1']
dup_p1 = float((same_p1['tr_zero_activity_ratio'] - same_p1['tr_inactive_learner_ratio']).abs().max())
f4 = f.drop(columns=[c for c in DROP if c in f])
req = ['tr_n_enrollments', 'ev_n_enrollments', 'tr_n_offerings', 'ev_n_offerings', 'tr_n_features_total', 'tr_n_features_static', 'tr_n_features_seq',
       'tr_class_count_c0', 'tr_class_count_c1', 'tr_class_count_c2', 'tr_imbalance_ratio', 'tr_minority_ratio', 'tr_class_entropy_norm',
       'ev_mean_observed_fraction', 'ev_mean_observed_length', 'tr_missing_rate', 'ev_missing_rate', 'tr_unavailable_rate',
       'tr_structural_absence_rate', 'tr_observed_zero_rate', 'tr_sparsity_cell', 'tr_zero_activity_ratio',
       'tr_incomplete_history_ratio', 'tr_mean_events_per_enrollment', 'tr_missing_label_mi_max', 'ev_train_overlap_share',
       'days_train_end_to_test_start', 'train_history_span_days', 'has_prev_phase', 'drift_tr_ev_psi_mean', 'drift_tr_ev_jsd_mean']
missing_cols = [c for c in req if c not in f4]
nulls = {c: int(f4[c].isna().sum()) for c in req if c in f4}
bad = {c: n for c, n in nulls.items() if n}
summary = json.loads((V3 / 'summary.json').read_text(encoding='utf-8'))
summary.update({'version': 'v4', 'rows': len(f4), 'required_minimum_set_null_counts': nulls, 'unexpected_nulls': bad, 'missing_required_columns': missing_cols,
                'removed_columns': DROP, 'removal_reason': 'Q-28 (author, 2026-11-09): tr_inactive_learner_ratio left the minimum set; the "no event before cutoff" definition equals tr_zero_activity_ratio and all inactivity shares are 0.96-0.99',
                'status': 'MINIMUM_SET_COMPLETE_V4' if not bad and not missing_cols else 'INCOMPLETE'})
summary['conventions'].pop('tr_inactive_learner_ratio', None)
f4.to_csv(OUT / 's0_profile.csv', index=False)
f4.to_parquet(OUT / 's0_profile.parquet', index=False)
(OUT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
readme = (V3 / 's0_profile_README.md').read_text(encoding='utf-8')
(OUT / 's0_profile_README.md').write_text(readme.replace('S0 profile (M-13a) v3', 'S0 profile (M-13a) v4') +
    '\n## v4 change (09/11/2026, Q-28)\n\n`tr_inactive_learner_ratio` and its reason column are removed. Under the definition "no event at all before the phase cutoff" it equals '
    '`tr_zero_activity_ratio` (kept), and every inactivity share is 0.96–0.99 because 97–99 % of enrollments have no event, so the column had no spread. '
    'All other columns and values are those of v3.\n', encoding='utf-8')
with open(OUT / 'sha256sums.txt', 'w', encoding='utf-8', newline='\n') as fh:
    for n in ('s0_profile.csv', 's0_profile.parquet', 'summary.json', 's0_profile_README.md'):
        fh.write(f"{hashlib.sha256((OUT / n).read_bytes()).hexdigest()}  {n}\n")
print(json.dumps({'status': summary['status'], 'rows': len(f4), 'cols_v3': f.shape[1], 'cols_v4': f4.shape[1], 'unexpected_nulls': bad, 'missing_required_columns': missing_cols,
                  'max_abs_diff_zero_activity_vs_inactive_at_P1': dup_p1}, indent=1))
