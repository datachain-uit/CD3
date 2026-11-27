"""Build qa_outcomes_release_r2_v2 (request B2'): v1 table + QA07, QA11, QA12, QA13, QA14, QA17, QA21, QA22, QA23 from the extra runs.
Inputs (all produced by the scripts committed under tools/delivery_20261126): v1 table, qa4 results, qa5 per-unit evidence (first pass + fill pass).
usage: build_qa_v2.py <work_root> <out_dir> <code_commit>"""
import glob
import hashlib
import json
import shutil
import sys
from pathlib import Path

import pandas as pd

W = Path(sys.argv[1])
OUT = Path(sys.argv[2])
COMMIT = sys.argv[3]
EV = OUT / 'evidence'
EV.mkdir(parents=True, exist_ok=True)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


v1 = pd.read_csv(W / 'b2/qa_outcomes_release_r2.csv')
# ---- evidence of v1 kept (unchanged files)
for f in (W / 'b2/evidence').glob('*.csv'):
    shutil.copy2(f, EV / f.name)
# ---- qa4 evidence
for f in ('qa14_evidence.csv', 'qa17_unit_table.csv', 'qa17_checks.csv', 'qa22_recomputed_from_views.csv', 'qa22_registry_check.csv', 'qa22_inputs_sha256.csv',
          'qa23_cq_behavioural_linkage_by_base.csv', 'qa23_lo_current_grade_group.csv'):
    shutil.copy2(W / 'qa4' / f, EV / f)
for f in ('qa23_detail_CQ.csv', 'qa23_detail_LO.csv', 'qa23_detail_columns.csv', 'qa23_lo_dictionary_used.csv'):
    shutil.copy2(W / 'p' / f, EV / f)
shutil.copy2(W / 'qa4/qa4_results.json', EV / 'qa4_results.json')
# ---- qa5: one row per unit
rows = []
UD = EV / 'qa5_units'
UD.mkdir(exist_ok=True)
merged = {u: json.load(open(W / f'qa5/fill/LO_{u}_seed42_qa_evidence_merged.json', encoding='utf8'))['merged'] for u in ('BILSTM', 'LSTM')}
for f in sorted(glob.glob(str(W / 'qa5/full/*_qa_evidence.json'))):
    d = json.load(open(f, encoding='utf8'))
    unit = d['unit']
    shutil.copy2(f, UD / Path(f).name)
    for suf in ('files', 'runs'):
        shutil.copy2(f.replace('_qa_evidence.json', f'_qa_{suf}.csv'), UD / (unit + f'_qa_{suf}.csv'))
    q7, q12, q13, q11, q21 = d['QA07'], d['QA12'], d['QA13'], d['QA11'], d['QA21']
    r = dict(unit=unit, source='first_pass', files_expected=d['files_expected'], files_checked=d['files_checked'], rows_checked=q7['rows_checked'], max_abs_sum_err=q7['max_abs_sum_err'],
             qa07_n_sum_viol=q7['n_sum_viol'], qa07_n_nonfinite=q7['n_nonfinite'], qa07_n_bad_label=q7['n_bad_label'], qa07_n_argmax_mismatch=q7['n_argmax_mismatch'], qa07_n_ties=q7['n_ties'],
             qa12_files=q12['files_val_test'], qa12_population_checked_files=q12['population_checked_files'], qa12_rows_not_in_real_population=q12['rows_not_in_real_population'],
             qa12_files_rows_ne_manifest=q12['files_rows_ne_manifest'], qa12_synthetic_like_columns_files=q12['synthetic_like_columns_files'],
             qa12_runs_s2_manifest=q12['runs_with_s2_manifest'], qa12_s2_touched_true=q12['runs_s2_validation_test_touched_true'],
             qa13_runs=q13['runs'], qa13_runs_checkpoint_sha256_field=q13['runs_with_checkpoint_sha256_field'], qa13_runs_preprocessor_sha256_field=q13['runs_with_preprocessor_sha256_field'],
             qa13_runs_s1_preprocessor_sha256=q13['runs_with_s1_preprocessor_sha256'],
             qa11_runs_linked_s1=q11['runs_linked_to_s1'], qa11_sum_future_imputed_cells=q11['sum_future_imputed_cells_over_linked_runs'], qa11_runs_nonzero=q11['runs_with_nonzero'],
             qa21_p1_pairs=q21['p1_pairs_checked'], qa21_p1_overlap_keys=q21['p1_val_test_overlap_total_keys'], qa21_p3_runs_fit_scope_train=q21['p3_runs_fit_scope_train'],
             qa21_p5_runs_checked=q21.get('p5_model_input_runs_checked_LO_contract', 0), qa21_p5_runs_with_proxy_in_model_input=q21.get('p5_runs_with_proxy_in_model_input', 0))
    key = unit.split('_seed')[0].replace('LO_', '')
    if unit in ('LO_BILSTM_seed42', 'LO_LSTM_seed42'):
        m = merged[key]
        fl, rl = m['file_level'], m['run_level']
        r.update(source='first_pass+fill_pass(merged)', files_checked=m['files_checked'], rows_checked=fl['rows_checked'], max_abs_sum_err=fl['max_abs_sum_err'],
                 qa07_n_sum_viol=fl['n_sum_viol'], qa07_n_nonfinite=fl['n_nonfinite'], qa07_n_bad_label=fl['n_bad_label'], qa07_n_argmax_mismatch=fl['n_argmax_mismatch'], qa07_n_ties=fl['n_ties'],
                 qa12_files=fl['files'], qa12_population_checked_files=fl['population_checked_files'], qa12_rows_not_in_real_population=fl['rows_not_in_real_population'],
                 qa12_files_rows_ne_manifest=fl['files_rows_ne_manifest'], qa12_synthetic_like_columns_files=fl['synthetic_like_columns_files'],
                 qa12_runs_s2_manifest=rl['QA12_runs_with_s2_manifest'], qa12_s2_touched_true=rl['QA12_runs_s2_validation_test_touched_true'],
                 qa13_runs=rl['runs'], qa13_runs_checkpoint_sha256_field=rl['QA13_runs_with_checkpoint_sha256_field'],
                 qa13_runs_preprocessor_sha256_field=rl['QA13_runs_with_preprocessor_sha256_field'], qa13_runs_s1_preprocessor_sha256=rl['QA13_runs_with_s1_preprocessor_sha256'],
                 qa11_runs_linked_s1=rl['QA11_runs_linked_to_s1'], qa11_sum_future_imputed_cells=rl['QA11_sum_future_imputed_cells_over_linked_runs'], qa11_runs_nonzero=rl['QA11_runs_with_nonzero'],
                 qa21_p1_pairs=fl['p1_pairs_checked'], qa21_p1_overlap_keys=fl['p1_val_test_overlap_total_keys'], qa21_p3_runs_fit_scope_train=rl['QA21_p3_runs_fit_scope_train'],
                 qa21_p5_runs_checked=rl['QA21_p5_model_input_runs_checked'], qa21_p5_runs_with_proxy_in_model_input=0)
        shutil.copy2(W / f'qa5/fill/LO_{key}_seed42_qa_evidence_merged.json', UD / f'LO_{key}_seed42_qa_evidence_merged.json')
        for suf in ('fill_evidence.json', 'fill_files.csv', 'fill_runs.csv'):
            shutil.copy2(W / f'qa5/fill/LO_{key}_seed42_qa_{suf}', UD / f'LO_{key}_seed42_qa_{suf}')
    rows.append(r)
U = pd.DataFrame(rows)
U.to_csv(EV / 'qa5_units_summary_36.csv', index=False, lineterminator='\n')
S = U.sum(numeric_only=True)
ud = EV / 'qa5_units_summary_36.csv'
assert len(U) == 36 and (U.files_checked == U.files_expected).all()
nf = int(S.files_checked)
n_runs = 36 * 51
q4 = json.load(open(W / 'qa4/qa4_results.json', encoding='utf8'))
q4 = {x['check_id']: x for x in q4} if isinstance(q4, list) else q4
today = '2026-11-27'


def put(cid, status, unit, n, npass, nfail, ev, note):
    i = v1.index[v1.check_id == cid][0]
    v1.loc[i, ['status', 'unit', 'n_units_checked', 'n_pass', 'n_fail', 'evidence_file', 'evidence_sha256', 'run_date', 'note']] = \
        [status, unit, n, npass, nfail, ev, sha(OUT / ev), today, note]


put('QA07', 'PASS', 'file dự đoán VALIDATION/TEST (36 đơn vị × 408)', nf, nf - int(S.qa07_n_sum_viol > 0), 0, 'evidence/qa5_units_summary_36.csv',
    f'Chạy trên mọi dòng của {nf} file dự đoán ({int(S.rows_checked):,} dòng, 36 đơn vị; hai đơn vị LO seed 42 được bổ sung ở lượt thứ hai): vi phạm |Σp−1| > 1e-4: {int(S.qa07_n_sum_viol)}; xác suất không hữu hạn: {int(S.qa07_n_nonfinite)}; nhãn sai: {int(S.qa07_n_bad_label)}; lớp dự đoán khác argmax: {int(S.qa07_n_argmax_mismatch)}; hòa: {int(S.qa07_n_ties)}; sai số tổng lớn nhất {U.max_abs_sum_err.max():.3g}. Bằng chứng từng đơn vị trong evidence/qa5_units/.')
put('QA12', 'PASS', 'file dự đoán VALIDATION/TEST (36 đơn vị × 408)', nf, nf, 0, 'evidence/qa5_units_summary_36.csv',
    f'Bằng chứng GIÁN TIẾP (file dự đoán không có cờ mẫu tổng hợp): ở cả {nf} file, mọi `enrollment_id_hash` khớp ghi danh thật của đúng window/split/phase (dòng ngoài tập: {int(S.qa12_rows_not_in_real_population)}), số dòng bằng số dòng ghi trong manifest (lệch: {int(S.qa12_files_rows_ne_manifest)}), không có cột kiểu mẫu tổng hợp ({int(S.qa12_synthetic_like_columns_files)} file). Thêm: {int(S.qa12_runs_s2_manifest)} run có manifest S2 đều ghi validation_test_touched=false (số run bị chạm: {int(S.qa12_s2_touched_true)}); seed 44 không có manifest S2 trong gói mô hình (xem gói B4′). Phía viết quyết định có chấp nhận bằng chứng gián tiếp này hay không.')
n11 = int(S.qa11_runs_linked_s1)
put('QA11', 'NOT_RUN', 'run (liên kết với manifest S1)', n_runs, n11 - int(S.qa11_runs_nonzero), int(S.qa11_runs_nonzero), 'evidence/qa5_units_summary_36.csv',
    f'Không có cột `n_cells_imputed_in_unavailable` ở artefact nào; trường tương đương là `future_imputed_cells` của manifest S1 (theo window và pipeline, dùng chung cho mô hình và seed). Liên kết được {n11}/{n_runs} run, tổng ô tương lai bị điền: {S.qa11_sum_future_imputed_cells:g}, run khác 0: {int(S.qa11_runs_nonzero)}. {n_runs - n11} run còn lại (các đơn vị MANTIS_V2 seed 43 và 44 của CQ và cả ba seed của LO: chỉ 15/51 run mỗi đơn vị có manifest S1 liên kết) chưa được kiểm; theo quy tắc chỉ ghi PASS khi đủ, ghi NOT_RUN kèm số đã kiểm.')
put('QA13', 'NOT_RUN', 'run', n_runs, 0, 0, 'evidence/qa5_units_summary_36.csv',
    f'`checkpoint_sha256` và `preprocessor_sha256` không có trong manifest của run nào ({int(S.qa13_runs_checkpoint_sha256_field)}/{n_runs} và {int(S.qa13_runs_preprocessor_sha256_field)}/{n_runs}). Chỉ có bằng chứng cấu trúc (không đủ để ghi PASS): giao thức `shared_checkpoint_prefix_safe_v2_4` (một checkpoint cho P1–P4), cùng hash layout đặc trưng, và `preprocessor_sha256` của manifest S1 ở {int(S.qa13_runs_s1_preprocessor_sha256)}/{n_runs} run. Với các họ recurrent, file `model.pt` nằm trong tar nên sha256 của checkpoint tính được nếu cần.')
put('QA21', 'NOT_RUN', 'run / cặp VALIDATION–TEST', n_runs, 0, 0, 'evidence/qa5_units_summary_36.csv',
    f'Năm điều kiện, chỉ ba điều có bằng chứng. (1) Không trùng khóa giữa VALIDATION và TEST: {int(S.qa21_p1_pairs)} cặp run–phase, {int(S.qa21_p1_overlap_keys)} khóa trùng (TRAIN so với phần còn lại chưa kiểm). (3) Bộ tiền xử lý chỉ fit trên TRAIN: {int(S.qa21_p3_runs_fit_scope_train)} run có manifest S1 với fit_scope=TRAIN, VALIDATION/TEST chỉ transform. (5) Imputer không dùng đặc trưng proxy nhãn: không đọc được `imputer_predictors` (nằm trong joblib); phần kiểm đầu vào mô hình LO theo hợp đồng `lo_proxy_contract_v3` cho thấy {int(S.qa21_p5_runs_with_proxy_in_model_input)}/{int(S.qa21_p5_runs_checked)} run LO đã kiểm có ba họ cột `*_catalog_coverage` trong đầu vào (xem gói P). (2) Nhãn TRAIN sau mốc cắt: không có nhãn thời gian trong artefact của run. (4) Không điền ô tương lai: như QA11. Không đủ để ghi PASS hay FAIL.')
c = q4['QA17'] if 'QA17' in q4 else q4[0]
put('QA17', 'PASS', c.get('unit', 'cột chi phí'), 96, 96, 0, 'evidence/qa17_unit_table.csv', c['note'])
put('QA22', 'PASS', 'task × window', 6, 6, 0, 'evidence/qa22_recomputed_from_views.csv', q4['QA22']['note'] if 'QA22' in q4 else q4[2]['note'])
put('QA23', 'FAIL', 'task × window × phase', 24, 8, 16, 'evidence/qa23_detail_columns.csv', q4['QA23']['note'] if 'QA23' in q4 else q4[3]['note'])
put('QA14', 'NOT_RUN', 'sanity test', 0, 0, 0, 'evidence/qa14_evidence.csv', q4['QA14']['note'] if 'QA14' in q4 else q4[1]['note'])
# QA18: fix the column count in the note
i = v1.index[v1.check_id == 'QA18'][0]
n18 = str(v1.loc[i, 'note'])
n18 = n18.replace('244 cột', '162 cột') + ' Đính chính (v2): các ô NULL không có lý do thuộc 162 cột (244 là số cột có bất kỳ NULL, kể cả 82 cột đã có khóa trong null_reason_map); `qa18_qa19_with_errata.csv` (gói errata) là lớp phủ riêng, không thay dòng này.'
v1.loc[i, 'note'] = n18
v1['code_commit'] = COMMIT
v1.to_csv(OUT / 'qa_outcomes_release_r2.csv', index=False, lineterminator='\n')
print(v1[['check_id', 'status', 'n_units_checked', 'n_pass', 'n_fail']].to_string(index=False))
print(U[['files_checked']].sum().to_dict(), int(S.rows_checked))
