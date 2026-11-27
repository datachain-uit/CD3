"""qa_fill_merge.py UNIT FIRST_DIR FILL_DIR RUNS_FROM(first|fill): merged evidence = first pass + fill pass; the first-pass files are only read.
File-level counts: sum of the two passes (recomputed from the concatenated csv and asserted equal to the sum of the two passes).
Run-level counts: from the pass named by RUNS_FROM (fill for BILSTM because the first pass found no manifest; first for LSTM because its 51 manifests were found in the first pass)."""
import json
import sys
from pathlib import Path

import pandas as pd

UNIT, FIRST, FILL, RUNS_FROM = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
ev1 = json.load(open(FIRST / f'{UNIT}_qa_evidence.json'))
ev2 = json.load(open(FILL / f'{UNIT}_qa_fill_evidence.json'))
f1 = pd.read_csv(FIRST / f'{UNIT}_qa_files.csv')
f2 = pd.read_csv(FILL / f'{UNIT}_qa_fill_files.csv')
supp = FILL / f'{UNIT}_qa_fill_rows_vs_manifest_first_pass_files.csv'
if supp.exists():           # manifests absent in the first pass: the rows-vs-manifest columns of the first-pass files come from the supplement
    s = pd.read_csv(supp)
    assert len(s) == len(f1) and (s.sha256.values == f1.sha256.values).all()
    f1 = s[[c for c in f1.columns if c in s.columns]]
r1 = pd.read_csv(FIRST / f'{UNIT}_qa_runs.csv')
r2 = pd.read_csv(FILL / f'{UNIT}_qa_fill_runs.csv')
fm = pd.concat([f1, f2], ignore_index=True)
assert len(fm) == 408 and not fm.duplicated(['window_id', 'pipeline_id', 'eval_split', 'phase_id']).any()


def vc(df, col):
    return int(df[col].fillna(0).astype(float).sum())


def files_part(d):
    return {'files': len(d), 'rows_checked': int(d.n_rows.sum()), 'max_abs_sum_err': float(d.qa07_max_abs_sum_err.max()), 'n_sum_viol': vc(d, 'qa07_n_sum_viol'), 'n_nonfinite': vc(d, 'qa07_n_nonfinite_prob'),
            'n_bad_label': vc(d, 'qa07_n_bad_label'), 'n_argmax_mismatch': vc(d, 'qa07_n_argmax_mismatch'), 'n_pred_below_max': vc(d, 'qa07_n_pred_below_max'), 'n_ties': vc(d, 'qa07_n_ties'),
            'synthetic_like_columns_files': int(d.qa12_synthetic_like_columns.astype(object).fillna('').ne('').sum()), 'split_col_not_ok': int((d.qa12_split_col_ok == False).sum()), 'hash_null_rows': vc(d, 'qa12_n_hash_null'),
            'hash_duplicate_rows': vc(d, 'qa12_n_hash_duplicate'), 'population_checked_files': int((d.qa12_pop_checked.astype(str) == 'True').sum()), 'no_salt_match_files': int((d.qa12_pop_checked.astype(str) == 'NO_SALT_MATCH').sum()),
            'rows_not_in_real_population': vc(d, 'qa12_n_not_in_population'), 'files_rows_ne_manifest': int((d.qa12_rows_equal_manifest.astype(str) == 'False').sum()), 'files_with_manifest_rows': int(d.qa12_manifest_rows.notna().sum()),
            'p1_val_test_overlap_total_keys': vc(d, 'qa21p1_val_test_overlap'), 'p1_pairs_checked': int(d.qa21p1_val_test_overlap.notna().sum())}


p1, p2, pm = files_part(f1), files_part(f2), files_part(fm)
for k in p1:
    if k != 'max_abs_sum_err':
        assert pm[k] == p1[k] + p2[k], (k, p1[k], p2[k], pm[k])
assert pm['max_abs_sum_err'] == max(p1['max_abs_sum_err'], p2['max_abs_sum_err'])
for p, q in ((p1, ev1), (p2, ev2)):       # cross-check against the pass's own evidence json
    assert p['n_sum_viol'] == q['QA07']['n_sum_viol'] and p['rows_checked'] == q['QA07']['rows_checked'] and p['p1_pairs_checked'] == q['QA21']['p1_pairs_checked'] and p['files'] == q['files_checked']
runs = (r2 if RUNS_FROM == 'fill' else r1).copy()
nfile = fm.groupby(['window_id', 'pipeline_id']).size()
runs['n_pred_files'] = [int(nfile.get((a, b), 0)) for a, b in zip(runs.window_id, runs.pipeline_id)]
run_part = {'runs': len(runs), 'runs_with_manifest': int(runs.manifest_found.sum()), 'runs_with_all_8_prediction_files': int((runs.n_pred_files == 8).sum()),
            'QA12_runs_with_s2_manifest': int(runs.qa12_s2_validation_test_touched.notna().sum()), 'QA12_runs_s2_validation_test_touched_true': int((runs.qa12_s2_validation_test_touched == True).sum()),
            'QA12_runs_train_input_balanced': int((runs.qa12_train_input_is_balanced == True).sum()), 'QA12_runs_eval_inputs_not_train_false': int((runs.qa12_eval_inputs_not_train == False).sum()),
            'QA13_runs_with_checkpoint_sha256_field': int(runs.qa13_checkpoint_sha256_in_manifest.sum()), 'QA13_runs_with_preprocessor_sha256_field': int(runs.qa13_preprocessor_sha256_in_manifest.sum()),
            'QA13_runs_with_s1_preprocessor_sha256': int(runs.qa13_s1_preprocessor_sha256.notna().sum()), 'QA13_protocols': sorted(runs.qa13_protocol.dropna().unique().tolist()),
            'QA11_runs_linked_to_s1': int(runs.s1_pipeline.notna().sum()), 'QA11_sum_future_imputed_cells_over_linked_runs': float(runs.qa11_future_imputed_cells_total.sum()), 'QA11_runs_with_nonzero': int((runs.qa11_future_imputed_cells_total > 0).sum()),
            'QA21_p3_runs_fit_scope_train': int(runs.qa21p3_fit_scope.astype(str).str.startswith('TRAIN').sum()), 'QA21_p3_runs_fit_rows_le_train_rows': int((runs.qa21p3_fit_rows <= runs.qa21p3_train_rows).sum()),
            'QA21_p3_runs_transform_only': int((runs.qa21p3_validation_test_mode == 'TRANSFORM_ONLY').sum()), 'QA21_p5_model_input_runs_checked': int(runs.qa21p5_proxy_in_model_input.notna().sum()) if 'qa21p5_proxy_in_model_input' in runs else 0}
merged = {'unit': UNIT, 'files_expected': 408, 'files_checked': len(fm), 'files_missing': [], 'runs_expected': 51, 'manifests_found': run_part['runs_with_manifest'],
          'bytes_downloaded_total': ev1['bytes_downloaded_total'] + ev2['bytes_downloaded_total'], 'file_level': pm, 'run_level': run_part}
out = {'unit': UNIT, 'how_to_read': 'first_pass = numbers of the untouched first-pass evidence; fill_pass = numbers of the fill pass on the previously missing files only; merged.file_level = sum of both passes (asserted by the script) except max_abs_sum_err (maximum); merged.run_level is taken from the pass named in run_level_source',
       'run_level_source': RUNS_FROM,
       'first_pass': {'evidence_file': f'{UNIT}_qa_evidence.json', 'files_checked': ev1['files_checked'], 'files_missing': ev1['files_missing'], 'manifests_found': ev1['manifests_found'], 'file_level': p1},
       'fill_pass': {'evidence_file': f'{UNIT}_qa_fill_evidence.json', 'files_checked': ev2['files_checked'], 'files_missing': ev2['files_missing'], 'manifests_found': ev2['manifests_found'], 'file_level': p2,
                     'rows_vs_manifest_first_pass_files': ev2.get('rows_vs_manifest_first_pass_files'), 'file_sources': ev2['file_sources'], 'manifest_sources': ev2['manifest_sources']},
       'merged': merged}
Path(FILL / f'{UNIT}_qa_evidence_merged.json').write_text(json.dumps(out, indent=1, default=str), encoding='utf-8')
print(json.dumps({'first': p1, 'fill': p2, 'merged': pm, 'runs': run_part}, indent=0, default=str))
