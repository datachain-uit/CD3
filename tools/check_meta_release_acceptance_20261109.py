"""Acceptance check of a phase-1 meta-release (check 36 of the request of 2026-11-04) -- run by the code team before delivery.

Criteria: (1) planned_seeds = [42], no PARTIAL rows, synthetic false; (2) seed_level rows = input fact rows;
(3) QA pass rates per item, QA03/QA04 (delta identity, 1e-9) and AccTEMPO recompute (1e-4) = 100 %; (4) imputer_only_ref status recorded;
(5) F0 present for CQ, NOT_AVAILABLE_PHASE1 for LO; (6) FS1-FS3 not SKIPPED (S0 profile read, required columns non-null, leakage checks
MQ01/MQ06/MQ10 pass on the selected columns); (7) row_status counted by reason.
Usage: python tools/check_meta_release_acceptance_20261109.py --release DIR --pkg DIR --facts F [F ...] --s0 FILE --out report.json
"""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument('--release', type=Path, required=True)
ap.add_argument('--pkg', type=Path, required=True)
ap.add_argument('--facts', type=Path, nargs='+', required=True)
ap.add_argument('--s0', type=Path, required=True)
ap.add_argument('--out', type=Path, required=True)
args = ap.parse_args()
sys.path.insert(0, str(args.pkg))
from metamodel import features as FT  # noqa: E402

REQ_S0 = ['tr_n_enrollments', 'ev_n_enrollments', 'tr_n_offerings', 'ev_n_offerings', 'tr_n_features_total', 'tr_n_features_static', 'tr_n_features_seq',
          'tr_class_count_c0', 'tr_class_count_c1', 'tr_class_count_c2', 'tr_imbalance_ratio', 'tr_minority_ratio', 'tr_class_entropy_norm',
          'ev_mean_observed_fraction', 'ev_mean_observed_length', 'tr_missing_rate', 'ev_missing_rate', 'tr_unavailable_rate',
          'tr_structural_absence_rate', 'tr_observed_zero_rate', 'tr_sparsity_cell', 'tr_zero_activity_ratio', 'tr_incomplete_history_ratio',
          'tr_mean_events_per_enrollment', 'tr_missing_label_mi_max', 'days_train_end_to_test_start', 'train_history_span_days', 'has_prev_phase',
          'drift_tr_ev_psi_mean', 'drift_tr_ev_jsd_mean']
res = {}
man = json.loads((args.release / 'meta_release_manifest.json').read_text(encoding='utf-8'))
lvl = pd.read_parquet(args.release / 'meta_dataset_seed_level.parquet')
agg = pd.read_parquet(args.release / 'meta_dataset_seed_agg.parquet')

# (1)
partial = int(agg.get('row_status_agg', pd.Series(dtype=str)).astype(str).str.contains('PARTIAL').sum())
res['1_seeds_and_partial'] = {'planned_seeds': man['planned_seeds'], 'synthetic': man['synthetic'], 'partial_rows': partial,
                              'pass': man['planned_seeds'] == [42] and man['synthetic'] is False and partial == 0}
# (2)
n_in = 0
for f in args.facts:
    n_in += len(pd.read_parquet(f) if f.suffix == '.parquet' else pd.read_csv(f))
res['2_row_count'] = {'seed_level_rows': len(lvl), 'input_fact_rows': n_in, 'by_task': lvl.task.value_counts().to_dict(), 'pass': len(lvl) == n_in}
# (3)
qa = {k: v['qa_pass_rates'] for k, v in man['child_releases'].items()}
need = ('qa_delta_identity_ok', 'qa_metric_recompute_ok')
res['3_qa'] = {'pass_rates': qa, 'qa03_qa04_and_recompute_100pct': all(r[k] == 1.0 for r in qa.values() for k in need),
               'items_below_100pct': {c: {k: v for k, v in r.items() if v < 1.0} for c, r in qa.items()},
               'pass': all(r[k] == 1.0 for r in qa.values() for k in need)}
# (4)
res['4_imputer_only_ref'] = {'status': man.get('registry_imputer_only_ref_status'),
                             'definition': man.get('imputer_only_ref_definition'),
                             'pass': bool(man.get('registry_imputer_only_ref_status'))}
# (5)
cq, lo = lvl[lvl.task == 'CQ'], lvl[lvl.task == 'LO']
f0cols = [f'{m}_ref' for m in ('macro_f1', 'balanced_acc', 'mcc', 'kappa', 'gmean', 's_perf') if f'{m}_ref' in lvl.columns]  # F0 metric references only
cq_f0 = int(cq[f0cols].notna().any(axis=1).sum()) if f0cols else 0
lo_f0 = int(lo[f0cols].notna().any(axis=1).sum()) if f0cols else 0
res['5_f0'] = {'f0_columns': f0cols[:6], 'cq_rows_with_f0': cq_f0, 'cq_rows': len(cq), 'lo_rows_with_f0': lo_f0, 'lo_status_in_manifest': man.get('lo_f0'),
               'pass': cq_f0 > 0 and lo_f0 == 0 and man.get('lo_f0') == 'NOT_AVAILABLE_PHASE1'}
# (6)
s0 = pd.read_parquet(args.s0)
feat = {}
for fs in ('FS1', 'FS2', 'FS3'):
    cols = FT.select_columns(agg.columns, fs)
    chk = FT.check_inputs(cols, fs)
    feat[fs] = {'n_columns': len(cols), 'leakage_checks': {k: bool(v[0]) for k, v in chk.items()}}
sel3 = set(FT.select_columns(agg.columns, 'FS3'))
absent = [c for c in REQ_S0 if c not in agg.columns]
notin = [c for c in REQ_S0 if c in agg.columns and c not in sel3]
nullrates = {c: round(float(agg[c].isna().mean()), 4) for c in REQ_S0 if c in agg.columns and agg[c].isna().any()}
res['6_features'] = {'sets': feat, 'required_s0_absent_in_release': absent, 'required_s0_not_selected_in_FS3': notin, 'required_s0_with_nulls': nullrates,
                     'has_state_profile': man['has_state_profile'],
                     'feature_regime_null_rows': int(lvl.feature_regime.isna().sum()),
                     'pass': all(all(v['leakage_checks'].values()) and v['n_columns'] > 0 for v in feat.values()) and not absent
                             and not nullrates and not notin and int(lvl.feature_regime.isna().sum()) == 0}
# (7)
reason_cols = [c for c in agg.columns if 'row_status' in c or 'null_reason' in c]
res['7_row_status'] = {'counts': {c: agg[c].astype(str).value_counts().head(8).to_dict() for c in reason_cols[:3]}, 'pass': True}
res['overall_pass_excluding_known_qa_note'] = all(v['pass'] for v in res.values() if isinstance(v, dict) and 'pass' in v)
args.out.write_text(json.dumps(res, indent=2, default=str) + '\n', encoding='utf-8')
print(json.dumps({k: (v['pass'] if isinstance(v, dict) and 'pass' in v else v) for k, v in res.items()}, indent=1))
