# -*- coding: utf-8 -*-
"""Build release_r2_errata_column_roles.csv (item E.1). Read-only on the release."""
import os, hashlib
import pandas as pd

R = os.environ['RELEASE_DIR']
OUT = os.environ.get('OUT_DIR', os.path.dirname(os.path.abspath(__file__)).replace(chr(92), '/') + '/')
dic_path = R + 'meta_column_dictionary.csv'
dic_sha = hashlib.sha256(open(dic_path, 'rb').read()).hexdigest()
dic = pd.read_csv(dic_path)
df = pd.read_parquet(R + 'meta_dataset_seed_level.parquet')
un = dic[dic.role == 'UNASSIGNED'].column_name.tolist()
assert len(un) == 54, len(un)
ROLES = set(dic.role.unique()) - {'UNASSIGNED'}

SRC_OLD = 'gói dữ kiện schema cũ (seed 42 x F1_RECURRENT) / facts schema'
spec = {}
def add(cols, role, basis, siblings, amb='NONE', note=''):
    for c in cols:
        spec[c] = (role, basis, siblings, amb, note)

# --- performance outputs on the evaluated slice: TARGET (same as c0..c2 metric columns, accuracy, log_loss, brier, ece in block Y) ---
add(['per_class_precision', 'per_class_recall', 'per_class_f1', 'per_class_support'], 'TARGET',
    'Cột sao chép từ schema dữ kiện (facts) dạng danh sách 3 phần tử [lớp 0, 1, 2]: gộp của c0_*, c1_*, c2_* (precision, recall, f1, support) đã là TARGET (khối Y). Mục 4.3: TARGET = hiệu năng TEST before/after/delta.',
    'c0_precision_after, c1_recall_after, c2_f1_after, c0_support (TARGET/QA)', 'LOW',
    'Không dùng làm input (kết quả đánh giá). Kiểu chuỗi dạng list, trùng thông tin c*_ ; chỉ có ở gói seed 42 x F1_RECURRENT.')
add(['confusion_matrix'], 'TARGET',
    'Ma trận nhầm lẫn 3x3 của lát đánh giá (QA06: tổng = n_eval_samples), từ schema dữ kiện; là kết quả đánh giá trên EVAL, cùng loại với accuracy/c*_support (TARGET). Mô tả meta-dataset nêu confusion matrix là nguyên liệu của Y.',
    'accuracy_after, c0_support, balanced_acc_after (TARGET)', 'LOW',
    'Không dùng làm input; chứa nhãn thật của EVAL (hàng = lớp thật), nên tuyệt đối không X_STATE/X_VAL.')
add(['cross_entropy', 'multiclass_nll'], 'TARGET',
    'Giá trị bằng log_loss của cùng dòng (builder gán cross_entropy = multiclass_nll = log_loss); log_loss đã là TARGET (khối Y).',
    'log_loss_after, log_loss_imp_only (TARGET)', 'LOW', 'Cột trùng log_loss (dư thừa); không phải input.')
add(['multiclass_brier'], 'TARGET', 'Bằng brier của cùng dòng (builder: multiclass_brier = brier); brier đã là TARGET.', 'brier_after (TARGET)', 'LOW', 'Cột trùng brier (dư thừa).')
add(['top_label_ece_15'], 'TARGET', 'ECE top-label 15 bin của lát đánh giá; cùng họ với ece (TARGET).', 'ece_after (TARGET)', 'LOW', 'Chỉ số hiệu chuẩn trên EVAL; không phải input.')
add(['calibration_bins'], 'PROV', 'Hằng số 15 (số bin của ECE), tham số của công thức đo, không phải kết quả; cùng loại các hằng của công thức (acctempo_alpha/beta/eps_floor là PROV).',
    'acctempo_alpha, acctempo_eps_floor (PROV)', 'LOW', 'Hằng số; không mang tín hiệu.')
add(['probability_sum_max_abs_error', 'prediction_nan_inf_count'], 'QA',
    'Cờ/đại lượng kiểm tra tính hợp lệ của dự đoán (sai số tổng xác suất, số NaN/Inf), không phải thuộc tính dữ liệu hay hiệu năng; cùng loại n_eval_samples, ev_n_classes_present, qa_*. Mục 4.3: QA = cờ kiểm tra, dùng để lọc dòng.',
    'n_eval_samples, ev_n_classes_present, qa_metric_recompute_ok (QA)', 'LOW', 'Chỉ dùng lọc dòng.')
# --- split descriptor ---
add(['strict_share'], 'X_STATE',
    'Tỉ lệ dòng STRICT (nhãn chuẩn thời gian sau cutoff) trên lát đánh giá, tính từ ngày offering, không dùng nhãn; tương tự ev_train_overlap_share (Z_T, X_STATE) và p1_cutoff_overlap_share = 1 - strict_share trong registries.',
    'ev_train_overlap_share, days_train_end_to_test_start (X_STATE, khối Z_T)', 'MEDIUM',
    'CẦN TÁC GIẢ XÁC NHẬN. Nếu gán X_STATE thì thành input: cột chỉ có ở 8160/73440 dòng (LO seed 42 recurrent), 88.9% NULL, nên thực tế không dùng được. Lựa chọn thay thế: DIAG (không là input) nếu tác giả coi đây là cột báo cáo.')
add(['w2_strict_share'], 'DERIVED',
    'Bản sao của strict_share chỉ giữ cho window W2 (builder: ss nếu window = W2, ngược lại NaN); là cột báo cáo phụ trợ, trùng strict_share nên không nên là input.',
    'strict_share (đề xuất X_STATE)', 'MEDIUM',
    'CẦN XÁC NHẬN. Không để X_STATE/X_VAL vì là bản sao có điều kiện theo window (rò rỉ cấu trúc window).')
# --- evpool ---
add(['evpool_n_cells_total', 'evpool_n_cells_unavailable', 'evpool_n_cells_structural_absence', 'evpool_n_cells_observed_eligible', 'evpool_n_cells_observed_value',
     'evpool_n_cells_observed_missing', 'evpool_n_cells_observed_zero', 'evpool_missing_rate'], 'X_STATE',
    'Đếm ô/tỉ lệ thiếu của pool EVAL (không dùng nhãn), cùng khối với ev_n_cells_* và trpool_* (đều X_STATE trong từ điển); README_metamodel xếp evpool_* cùng nhóm cột đo trên lát đánh giá (ev_*, drift_tr_ev_*).',
    'ev_n_cells_total, ev_missing_rate, trpool_n_cells_total, trpool_missing_rate (X_STATE)', 'HIGH',
    'CẦN TÁC GIẢ XÁC NHẬN, ảnh hưởng input. FACTS_OF_RECORD_PHASE1 ghi: các count/rate này lấy trên toàn bộ P1-P4 dù partition gắn nhãn P1/P2/P3, "không dùng làm đặc trưng prefix"; chúng chỉ được điền cho eval_split = VALIDATION, phase P1-P3 (37.5% dòng). Gán X_STATE theo đúng sibling trpool_*, nhưng nếu tác giả muốn chặn rò rỉ prefix thì nên là DIAG. Cột NULL trên mọi dòng TEST.')
# --- run purpose / slice status / versions ---
add(['run_purpose'], 'PROV', 'Mục đích run (PRIMARY_GRID / EXPLORATORY_CACHE_VALIDATION), siêu dữ liệu của gói nguồn; cùng loại execution_backend, model_revision (PROV).',
    'execution_backend, model_revision (PROV)', 'LOW', 'Chỉ để lọc/phân loại dòng; trùng gần hoàn toàn với seed x model nên không nên là input. Lựa chọn thay thế: QA (lọc dòng).')
add(['slice_status'], 'QA', 'Trạng thái dựng lát seen/unseen (OK) của dòng; cùng loại row_status (QA).', 'row_status (QA)', 'LOW', 'Dùng lọc dòng.')
add(['seen_rule_version', 'seen_history_reference'], 'PROV', 'Phiên bản quy tắc gán cờ seen và tham chiếu lịch sử (TRAIN_PARTITION_ONLY) ghi theo mô tả meta-dataset (quy tắc gán cờ seen); cùng loại label_rule_version/acctempo_def_version/meta_schema_version (KEY/PROV).',
    'acctempo_def_version, meta_schema_version (PROV)', 'LOW', 'Hằng số; không mang tín hiệu.')
# --- lineage / reference ---
add(['parent_pipeline'], 'PROV', 'Pipeline cha (pipeline imputation mà pipeline cân bằng kế thừa), dùng làm khóa ghép probe/s_eff; cùng loại imputer_only_pipeline, pipeline_imputer_only_ref (PROV).',
    'imputer_only_pipeline, pipeline_before_ref (PROV)', 'MEDIUM',
    'Đề xuất PROV (nguồn gốc). Nếu tác giả gán X_CONTEXT thì trùng imputer/imputer_family (Z_A) và NULL ở gói CQ seed 42 recurrent.')
add(['reference_task', 'reference_window', 'reference_pipeline', 'reference_layout_sha256', 'reference_checkpoint_sha256'], 'PROV',
    'Định danh/mã băm của run và checkpoint tham chiếu F0 (layout, checkpoint); mô tả nguồn gốc, cùng loại pipeline_before_ref, run_id_ref, run_id_before (PROV).',
    'pipeline_before_ref, run_id_ref, run_id_before (PROV)', 'LOW', 'Mã băm/định danh, không phải input.')
add(['reference_dynamic_channels', 'reference_static_channels'], 'PROV',
    'Số kênh của layout đặc trưng tham chiếu (148/25 cho LO, 140/21 cho CQ); hằng theo task nên là mô tả nguồn gốc của layout, đi cùng reference_layout_sha256.',
    'reference_layout_sha256 (đề xuất PROV), tr_n_features_seq/static (X_STATE)', 'MEDIUM',
    'CẦN XÁC NHẬN. Nếu gán X_CONTEXT/X_STATE thì chỉ là mã hóa lại của task (2 giá trị). Lưu ý tr_n_features_* đã là X_STATE và mang cùng loại thông tin.')
# --- Z_M model configuration ---
add(['param_count_backbone_used', 'param_count_backbone_total', 'frozen_backbone', 'return_transf_layer', 'output_token', 'interp_len', 'adapter_components', 'micro_batch_size', 'accumulation_steps'],
    'X_CONTEXT', 'Cấu hình mô hình/huấn luyện (khối Z_M: mô tả mô hình), cùng loại param_count_total, param_count_trainable, patch_len, batch_size, lr, max_epochs (X_CONTEXT). Mục 4.3: X_CONTEXT = mô tả mô hình và can thiệp.',
    'param_count_total, param_count_trainable, batch_size, patch_len (X_CONTEXT)', 'MEDIUM',
    'Là input nếu gán X_CONTEXT. 7 cột đầu chỉ có ở MANTIS_V2 (NULL ở 83.3% dòng, NOT_APPLICABLE); micro_batch_size/accumulation_steps/frozen_backbone nhận 2 giá trị và tách đúng MANTIS_V2 khỏi các mô hình khác, nên là mã hóa lại của model_name; cần chính sách mã hóa NULL trước khi dùng.')
add(['gpu'], 'PROV', 'Tên GPU thực thi (hạ tầng); mục 4.3: PROV = phiên bản, mã băm, hạ tầng; cùng loại execution_backend, energy_measurement_type (PROV).',
    'execution_backend, energy_measurement_type (PROV)', 'LOW', 'Hằng "NVIDIA L4" ở mọi dòng có giá trị; không phải input.')
# --- probe configuration ---
add(['probe_seed', 'probe_fit_rows', 'probe_fit_scope', 'probe_score_scope', 'probe_fit_rows_source', 'probe_solver', 'probe_tol', 'probe_max_iter', 'probe_n_iter', 'probe_deterministic_single_thread'], 'PROV',
    'Cấu hình và nguồn gốc probe s_leak (seed, số dòng fit, phạm vi fit/score, solver, tol, max_iter, số vòng lặp, single-thread); là siêu dữ liệu tái lập của s_leak_probe_auc (DIAG), cùng loại s_leak_probe_n_eval (PROV) và s_leak_source.',
    's_leak_probe_n_eval (PROV), s_leak_probe_fit_once / s_leak_source (DIAG)', 'LOW',
    'probe_n_iter là kết quả của lần fit (số vòng hội tụ) nhưng chỉ phục vụ tái lập; không là input. Lựa chọn thay thế: DIAG.')

miss = [c for c in un if c not in spec]
extra = [c for c in spec if c not in un]
assert not miss and not extra, (miss, extra)
for c, v in spec.items():
    assert v[0] in ROLES, (c, v[0])
rows = []
for c in un:
    role, basis, sib, amb, note = spec[c]
    rows.append(dict(column_name=c, current_role='UNASSIGNED', proposed_role=role, basis=basis, analogous_assigned_siblings=sib, ambiguity=amb,
                     model_input_note=note, n_null=int(df[c].isna().sum()), column_dictionary_sha256=dic_sha))
out = pd.DataFrame(rows)
out.to_csv(OUT + 'release_r2_errata_column_roles.csv', index=False, encoding='utf-8', lineterminator='\n')
print(len(out)); print(out.proposed_role.value_counts().to_string()); print(out.ambiguity.value_counts().to_string())
print(out[out.proposed_role.isin(['X_STATE', 'X_CONTEXT', 'X_VAL'])].column_name.tolist())
