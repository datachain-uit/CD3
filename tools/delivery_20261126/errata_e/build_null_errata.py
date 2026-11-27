# -*- coding: utf-8 -*-
"""Build release_r2_errata_null_reasons.csv (item E.2). Read-only on the release.
Env: RELEASE_DIR (release folder, trailing slash), OUT_DIR (output folder, trailing slash)."""
import json, fnmatch, os, hashlib
import numpy as np, pandas as pd

R = os.environ['RELEASE_DIR']
OUT = os.environ.get('OUT_DIR', os.path.dirname(os.path.abspath(__file__)).replace(chr(92), '/') + '/')
dic_sha = hashlib.sha256(open(R + 'meta_column_dictionary.csv', 'rb').read()).hexdigest()
df = pd.read_parquet(R + 'meta_dataset_seed_level.parquet')
dic = pd.read_csv(R + 'meta_column_dictionary.csv')
N = len(df)

# ---------- W mask: NULL cell without key in the row's null_reason_map (wildcard aware, same as QA18 of run_qa_release_r2.py) ----------
body = df.drop(columns=['null_reason_map'])
nullm = body.isna()
cols = list(nullm.columns)
arr = nullm.to_numpy()
nrm = df.null_reason_map.fillna('{}').to_numpy()
W = np.zeros_like(arr)
for s_ in pd.unique(nrm):
    mp = json.loads(s_) if s_ else {}
    cw = np.array([(c in mp) or any(fnmatch.fnmatchcase(c, k) for k in mp if '*' in k) for c in cols])
    ii = np.where(nrm == s_)[0]
    W[ii] = arr[ii] & ~cw
Wd = pd.DataFrame(W, columns=cols)
nn = lambda c: df[c].isna().to_numpy()
cand = [c for c in cols if not c.endswith('_reason') and Wd[c].any()]
print('columns with NULL w/o reason (excl *_reason):', len(cand), 'cells', int(Wd[cand].to_numpy().sum()))

# ---------- structural helpers ----------
model = df.model_name.to_numpy(); task = df.task.to_numpy(); seed = df.seed.to_numpy()
tier = df.model_tier.to_numpy(); axis = df.subgroup_axis.to_numpy(); split = df.eval_split.to_numpy()
phase = df.phase_id.to_numpy(); win = df.window_id.to_numpy()
old = (seed == 42) & (tier == 'F1_RECURRENT')             # package of older facts schema (seed 42, F1 recurrent)
cq_old_all = old & (task == 'CQ') & (axis == 'ALL')       # CQ seed42 recurrent ALL rows without subgroup-schema columns
lo_old = old & (task == 'LO')
T = lambda a: np.asarray(a, dtype=bool)

KEY = ['task', 'feature_regime', 'window_id', 'model_name', 'seed', 'eval_split', 'subgroup_axis', 'subgroup_value', 'phase_id']
v0 = df[df.pipeline_id == 'V0'].set_index(KEY)
assert v0.index.is_unique
idx = pd.MultiIndex.from_frame(df[KEY])
def v0v(col):
    return v0[col].reindex(idx).to_numpy()

runs = df.drop_duplicates('run_id_after').set_index('run_id_after')
def before_run(col):
    return runs[col].reindex(df.run_id_before).to_numpy()

KEY2 = ['task', 'feature_regime', 'window_id', 'pipeline_id', 'model_name', 'seed', 'subgroup_axis', 'subgroup_value', 'phase_id']
vs = df[df.eval_split == 'VALIDATION'].set_index(KEY2)
assert vs.index.is_unique
idx2 = pd.MultiIndex.from_frame(df[KEY2])
def valsib(col):
    return vs[col].reindex(idx2).to_numpy()

C_NIS, C_NA, C_CA, C_ZD, C_IN, C_TEL, C_NP, C_NPW, C_NPR = (
    'NOT_IN_SOURCE_PACKAGE', 'NOT_APPLICABLE', 'CLASS_ABSENT', 'UNDEFINED_ZERO_DENOMINATOR', 'INPUT_NULL_PROPAGATED',
    'TELEMETRY_UNAVAILABLE', 'NOT_POPULATED_IN_RELEASE', 'NO_PREVIOUS_PHASE',
    'ZERO_CELL_RATE_NOT_RECOVERABLE_FROM_SCALED_INPUTS_PREFIX_NOT_P4')
NEW = {
    C_NIS: 'Cột không có trong gói dữ kiện nguồn của dòng này (gói = tập run cùng task x họ mô hình x seed, nạp bằng schema dữ kiện khác); không phải giá trị bị mất khi tính; không thể suy ra từ bảng này.',
    C_NP: 'Cột tham chiếu có trong schema nhưng không bao giờ được điền (100% NULL) trong release này.',
    C_ZD: 'Chỉ số không xác định do mẫu số bằng 0 (precision khi không có dự đoán dương cho lớp; F1 khi precision + recall = 0); theo quy ước của builder là NULL, không thay bằng 0.',
    C_IN: 'Giá trị dẫn xuất (delta, ratio, utility, rank, F1) NULL vì ít nhất một toán hạng đầu vào của chính dòng đó NULL; lý do gốc nằm ở cột toán hạng.',
}

spec = {}
def add(col, family, rule, parts):
    spec[col] = dict(family=family, rule=rule, parts=parts)

# A. reference column never filled
add('run_id_ref', 'F_REF_UNFILLED', 'Cột tham chiếu run_id_ref (khóa tham chiếu F0) không bao giờ được điền: NULL trên mọi dòng.', [(C_NP, np.ones(N, bool))])
# B. model-family-specific
for c in ['patch_len', 'patch_stride']:
    add(c, 'F_MODEL_SPECIFIC', 'Siêu tham số chỉ của PatchTST (patch_*): NULL khi model_name != PATCHTST.', [(C_NA, model != 'PATCHTST')])
for c in ['param_count_backbone_used', 'param_count_backbone_total', 'return_transf_layer', 'output_token', 'interp_len', 'adapter_components']:
    add(c, 'F_MODEL_SPECIFIC', 'Cấu hình chỉ của mô hình nền MANTIS_V2 (adapter/backbone): NULL khi model_name != MANTIS_V2.', [(C_NA, model != 'MANTIS_V2')])
add('max_seq_len', 'F_MODEL_SPECIFIC', 'max_seq_len áp dụng cho mô hình chuỗi (recurrent, PatchTST); MANTIS_V2 dùng interp_len thay thế: NULL khi model_name == MANTIS_V2.', [(C_NA, model == 'MANTIS_V2')])
# C. columns of the older facts schema (seed 42 recurrent package only)
oldcols = ['per_class_precision', 'per_class_recall', 'per_class_f1', 'per_class_support', 'calibration_bins', 'cross_entropy']
for m in ['accuracy', 'weighted_f1']:
    oldcols += [f'{m}_before', f'{m}_imp_only', f'{m}_after']
for c in oldcols:
    add(c, 'F_OLD_FACTS_PACKAGE', 'Cột của schema dữ kiện cũ (accuracy, weighted_f1, per_class_*, calibration_bins, cross_entropy) chỉ có trong gói seed 42 x F1_RECURRENT (16320 dòng): NULL ngoài gói đó.', [(C_NIS, ~old)])
for c in ['roc_auc_macro_ovr_before', 'roc_auc_macro_ovr_imp_only', 'roc_auc_macro_ovr_after']:
    add(c, 'F_OLD_FACTS_PACKAGE', 'roc_auc_macro_ovr chỉ có trong gói seed 42 x F1_RECURRENT; trong gói, NULL khi lớp 2 vắng (c2_support = 0; macro-AUC cần đủ K lớp).',
        [(C_NIS, ~old), (C_CA, old & T(df.c2_support.to_numpy() == 0))])
# deltas of old-package metrics
for m in ['accuracy', 'weighted_f1', 'roc_auc_macro_ovr']:
    ops = np.zeros(N, bool)
    for o in [f'{m}_before', f'{m}_after', f'{m}_imp_only']:
        ops |= nn(o)
    for suf in ['_delta', '_delta_imp', '_delta_bal']:
        add(m + suf, 'F_DELTA_OF_NULL', f'{m}{suf} là hiệu của {m}_before/_after/_imp_only: NULL khi ít nhất một toán hạng NULL (dòng V0 ngoài gói cũ có delta = 0, không NULL).', [(C_IN, ops)])
# val_* (validation metrics carried on TEST rows; VALIDATION rows already carry the wildcard key val_*)
for m in ['accuracy', 'weighted_f1']:
    for st in ['before', 'after']:
        add(f'val_{m}_{st}', 'F_OLD_FACTS_PACKAGE', f'val_{m}: chỉ có ở gói seed 42 x F1_RECURRENT (schema cũ); dòng VALIDATION đã có khóa val_* trong null_reason_map.', [(C_NIS, ~old)])
for st in ['before', 'after']:
    sib = valsib(f'roc_auc_macro_ovr_{st}')
    add(f'val_roc_auc_macro_ovr_{st}', 'F_OLD_FACTS_PACKAGE', 'val_roc_auc: NULL ngoài gói cũ; trong gói, NULL khi dòng VALIDATION cùng nhóm có roc_auc NULL (lớp 2 vắng trên VALIDATION).',
        [(C_NIS, ~old), (C_CA, old & T(pd.isna(sib)))])
for m in ['accuracy', 'weighted_f1', 'roc_auc_macro_ovr']:
    add(f'val_{m}_delta', 'F_DELTA_OF_NULL', f'val_{m}_delta: NULL khi val_{m}_before hoặc val_{m}_after NULL.', [(C_IN, nn(f'val_{m}_before') | nn(f'val_{m}_after'))])
# F. probe/parent package (CQ seed 42 recurrent)
for c in ['parent_pipeline', 's_eff_definition_version', 's_eff_train_source', 's_eff_observed_rate', 's_eff_availability_rate', 's_leak_probe_fit_once', 'probe_seed',
          'probe_fit_rows', 's_leak_probe_n_eval', 'probe_fit_scope', 'probe_score_scope', 's_leak_probe_auc_before', 's_leak_probe_auc_after', 's_leak_probe_auc_delta']:
    add(c, 'F_PROBE_PARENT_PACKAGE', 'Trường probe/s_eff/parent_pipeline không có trong gói CQ x seed 42 x F1_RECURRENT (8160 dòng): NULL khi task = CQ và gói cũ.', [(C_NIS, old & (task == 'CQ'))])
for c in ['val_s_leak_probe_auc_before', 'val_s_leak_probe_auc_after', 'val_s_leak_probe_auc_delta']:
    add(c, 'F_PROBE_PARENT_PACKAGE', 'val_s_leak_probe_auc_*: NULL ở gói CQ x seed 42 x F1_RECURRENT (không có probe); dòng VALIDATION đã có khóa val_*.', [(C_NIS, old & (task == 'CQ'))])
# G. probe configuration recorded only for LO MANTIS_V2 seed 42
for c in ['probe_solver', 'probe_tol', 'probe_max_iter', 'probe_n_iter', 'probe_deterministic_single_thread']:
    add(c, 'F_PROBE_CONFIG_PACKAGE', 'Cấu hình probe (solver, tol, max_iter, n_iter, single-thread) chỉ ghi ở gói LO x MANTIS_V2 x seed 42 (2040 dòng): NULL ở các gói còn lại.',
        [(C_NIS, ~((task == 'LO') & (model == 'MANTIS_V2') & (seed == 42)))])
# H. strict share
add('strict_share', 'F_OLD_FACTS_PACKAGE', 'strict_share chỉ có trong gói LO x seed 42 x F1_RECURRENT (8160 dòng): NULL ở các gói còn lại.', [(C_NIS, ~lo_old)])
add('w2_strict_share', 'F_OLD_FACTS_PACKAGE', 'w2_strict_share chỉ có trong gói seed 42 x F1_RECURRENT (CQ và LO) và window W2 (5440 dòng): NULL ở các dòng còn lại.', [(C_NIS, ~(old & (win == 'W2')))])
for c in ['multiclass_nll', 'multiclass_brier', 'top_label_ece_15']:
    add(c, 'F_OLD_FACTS_PACKAGE', 'Chỉ số hiệu chuẩn mức ALL chỉ có ở gói LO x seed 42 x F1_RECURRENT, dòng subgroup_axis = ALL (1632 dòng): NULL ở các dòng còn lại.', [(C_NIS, ~(lo_old & (axis == 'ALL')))])
add('confusion_matrix', 'F_OLD_FACTS_PACKAGE', 'confusion_matrix không có ở dòng ALL của gói seed 42 x F1_RECURRENT (3264 dòng); các dòng khác có.', [(C_NIS, old & (axis == 'ALL'))])
# K. class-level columns
for c in ['ev_n_classes_present', 'small_subgroup_flag', 'probability_sum_max_abs_error', 'prediction_nan_inf_count'] + [f'c{k}_{x}' for k in (0, 1, 2) for x in ('support', 'predicted_count')]:
    add(c, 'F_CQ_OLD_ALL_NO_SUBGROUP_SCHEMA', 'Dòng ALL của gói CQ x seed 42 x F1_RECURRENT (1632 dòng) không mang cột của schema subgroup: NULL ở đúng các dòng đó.', [(C_NIS, cq_old_all)])

def trio(base, parts_fn, rule, family):
    for suf in ['before', 'after']:
        add(f'{base}_{suf}', family, rule, parts_fn(suf))
    add(f'{base}_delta', 'F_DELTA_OF_NULL', f'{base}_delta: NULL khi {base}_before hoặc {base}_after NULL.', [(C_IN, nn(f'{base}_before') | nn(f'{base}_after'))])

sup = {k: df[f'c{k}_support'].to_numpy() for k in (0, 1, 2)}
for k in (0, 1):
    for x in ('specificity', 'gmean', 'ap'):
        trio(f'c{k}_{x}', lambda suf: [(C_NIS, cq_old_all)], 'Chỉ số theo lớp NULL ở dòng ALL của gói CQ x seed 42 x F1_RECURRENT (không có schema subgroup).', 'F_CQ_OLD_ALL_NO_SUBGROUP_SCHEMA')
for x in ('specificity', 'gmean', 'ap'):
    trio(f'c2_{x}', lambda suf: [(C_NIS, cq_old_all), (C_CA, T(sup[2] == 0))], 'Chỉ số lớp 2: NULL khi gói CQ cũ (ALL) hoặc lớp 2 vắng trong lát (c2_support = 0, CLASS_ABSENT).', 'F_CLASS_LEVEL_UNDEFINED')
trio('c2_recall', lambda suf: [(C_CA, T(sup[2] == 0))], 'recall lớp 2 NULL khi lớp 2 vắng trong lát (c2_support = 0).', 'F_CLASS_LEVEL_UNDEFINED')
for k in (0, 1, 2):
    pc = df[f'c{k}_predicted_count'].to_numpy()
    pc0b = v0v(f'c{k}_predicted_count')
    base = f'c{k}_precision'
    if k == 0:
        trio(base, lambda suf: [(C_NIS, cq_old_all)], 'precision lớp 0 NULL ở dòng ALL của gói CQ x seed 42 x F1_RECURRENT.', 'F_CQ_OLD_ALL_NO_SUBGROUP_SCHEMA')
    else:
        def parts(suf, k=k, pc=pc, pc0b=pc0b):
            p0 = T(pc == 0) if suf == 'after' else T(pc0b == 0)
            return [(C_NIS, cq_old_all), (C_CA, T(sup[k] == 0)), (C_ZD, p0)]
        trio(base, parts, f'precision lớp {k} NULL khi: gói CQ cũ (ALL), lớp vắng (support = 0), hoặc không có dự đoán lớp {k} (predicted_count = 0; trạng thái before lấy từ dòng V0 cùng nhóm).', 'F_CLASS_LEVEL_UNDEFINED')
for k in (0, 1, 2):
    base = f'c{k}_f1'
    if k == 0:
        trio(base, lambda suf: [(C_NIS, cq_old_all)], 'F1 lớp 0 NULL ở dòng ALL của gói CQ x seed 42 x F1_RECURRENT.', 'F_CQ_OLD_ALL_NO_SUBGROUP_SCHEMA')
        continue
    P = {s: df[f'c{k}_precision_{s}'].to_numpy() for s in ('before', 'after')}
    Rr = {s: df[f'c{k}_recall_{s}'].to_numpy() for s in ('before', 'after')}
    def parts(suf, P=P, Rr=Rr):
        p = pd.isna(P[suf]); r = pd.isna(Rr[suf])
        s0 = (np.nan_to_num(P[suf]) + np.nan_to_num(Rr[suf])) == 0
        return [(C_IN, T(p | r)), (C_ZD, T(~(p | r) & s0))]
    trio(base, parts, f'F1 lớp {k} NULL khi precision hoặc recall cùng trạng thái NULL, hoặc precision + recall = 0 (0/0).', 'F_CLASS_LEVEL_UNDEFINED')
# M. all-row is not a slice
for c in ['slice_status', 'seen_rule_version', 'seen_history_reference']:
    add(c, 'F_SLICE_ONLY', 'Cột mô tả lát seen/unseen: không áp dụng cho dòng subgroup_axis = ALL (NULL ở đúng 14688 dòng ALL).', [(C_NA, axis == 'ALL')])
# N. evpool
for c in ['evpool_n_cells_total', 'evpool_n_cells_unavailable', 'evpool_n_cells_structural_absence', 'evpool_n_cells_observed_eligible', 'evpool_n_cells_observed_value',
          'evpool_n_cells_observed_missing', 'evpool_n_cells_observed_zero', 'evpool_missing_rate']:
    add(c, 'F_EVPOOL_VALIDATION_P123', 'Cột evpool_* (đếm ô của pool EVAL) chỉ được điền cho eval_split = VALIDATION và phase P1..P3; NULL ở TEST và ở P4.',
        [(C_NA, ~((split == 'VALIDATION') & (phase != 'P4')))])
add('ev_n_cells_observed_zero', 'F_EXISTING_REASON_COLUMN', 'NULL đúng khi cột ev_n_cells_observed_zero_reason có mã (VALIDATION, ALL, P1..P3).', [(C_NPR, T(df.ev_n_cells_observed_zero_reason.notna().to_numpy()))])
add('drift_phase_prev_psi_mean', 'F_NO_PREVIOUS_PHASE', 'Không có phase trước: NULL ở phase P1; cột drift_phase_prev_psi_mean_reason ghi NO_PREVIOUS_PHASE.', [(C_NPW, phase == 'P1')])
# Q. provenance
add('run_purpose', 'F_OLD_FACTS_PACKAGE', 'run_purpose chưa được ghi ở các dòng seed 42 (trừ 120 dòng CQ x MANTIS_V2 exploratory): NULL khi seed = 42 và variant_role NULL.', [(C_NIS, (seed == 42) & nn('variant_role'))])
add('variant_role', 'F_MODEL_SPECIFIC', 'variant_role chỉ có giá trị cho run EXPLORATORY_CACHE_VALIDATION; run PRIMARY_GRID hoặc chưa ghi run_purpose: NULL.', [(C_NA, T(df.run_purpose.ne('EXPLORATORY_CACHE_VALIDATION').to_numpy()))])
for c in ['s_leak_source', 'probe_fit_rows_source']:
    add(c, 'F_SEED_REFERENCE_PROBE', 'Nguồn probe tham chiếu chỉ ghi cho seed 43/44 (copy bảng tham chiếu seed 42, không fit lại); seed 42 là seed nguồn: NULL khi seed = 42.', [(C_NA, seed == 42)])
# S. cost / energy / telemetry
tb = before_run('time_run_total_s_after'); eb = before_run('energy_gpu_run_kwh_after')
add('time_run_total_s_after', 'F_TELEMETRY_RUN_LEVEL', 'Run không có bản ghi chi phí (time_run_total_s_after, energy_measurement_type, gpu cùng NULL; run CQ x MANTIS_V2 x seed 42 V0): NULL khi energy_measurement_type và gpu NULL.', [(C_TEL, nn('energy_measurement_type') & nn('gpu'))])
add('energy_measurement_type', 'F_TELEMETRY_RUN_LEVEL', 'Cùng run không có bản ghi chi phí: NULL khi time_run_total_s_after NULL.', [(C_TEL, nn('time_run_total_s_after'))])
add('gpu', 'F_TELEMETRY_RUN_LEVEL', 'Tên GPU NULL ở các run không có năng lượng đo (energy_gpu_run_kwh_after NULL); cột run-level, hằng trong run.', [(C_TEL, nn('energy_gpu_run_kwh_after'))])
add('time_run_total_s_before', 'F_TELEMETRY_RUN_LEVEL', 'before = giá trị after của run baseline (run_id_before): NULL khi run baseline không có time_run_total_s.', [(C_TEL, T(pd.isna(tb)))])
add('energy_gpu_run_kwh_before', 'F_TELEMETRY_RUN_LEVEL', 'before = giá trị after của run baseline (run_id_before): NULL khi run baseline không có năng lượng đo.', [(C_TEL, T(pd.isna(eb)))])
for m in ['time_run_total_s', 'energy_gpu_run_kwh']:
    for s in ['ratio', 'delta']:
        add(f'{m}_{s}', 'F_DELTA_OF_NULL', f'{m}_{s}: NULL khi {m}_before hoặc {m}_after NULL.', [(C_IN, nn(f'{m}_before') | nn(f'{m}_after'))])
for c in ['cost_ratio_used', 'utility_l1', 'rank_utility_l1', 'utility_l2', 'rank_utility_l2', 'utility_l3', 'rank_utility_l3']:
    add(c, 'F_DELTA_OF_NULL', f'{c} dẫn xuất từ time_run_total_s_ratio: NULL khi time_run_total_s_ratio NULL.', [(C_IN, nn('time_run_total_s_ratio'))])

print('cand not in spec:', [c for c in cand if c not in spec])
print('spec not in table:', [c for c in spec if c not in cols])

rows = []
Wcov = pd.DataFrame(False, index=df.index, columns=cand)   # cells explained by the overlay
for c in cand:
    if c not in spec:
        continue
    s = spec[c]; w = Wd[c].to_numpy(); nul = nn(c)
    covered = np.zeros(N, bool); bycode = {}
    for code, m in s['parts']:
        m = T(m)
        bycode[code] = int((w & m & ~covered).sum())
        covered |= m
    expl = w & covered
    Wcov[c] = expl
    counter = int((covered & ~nul).sum())
    codes = [k for k, v in bycode.items() if v > 0] or [k for k, _ in s['parts']]
    rows.append(dict(
        column_name=c, n_null_without_reason=int(w.sum()), proposed_reason_code='|'.join(codes),
        n_cells_by_code=';'.join(f'{k}:{v}' for k, v in bycode.items() if v),
        code_status='|'.join('NEW' if k in NEW else 'EXISTING' for k in codes),
        rule_family=s['family'], rule=s['rule'],
        n_cells_explained_by_rule=int(expl.sum()), n_cells_not_explained=int((w & ~covered).sum()),
        n_rule_true_but_cell_not_null=counter, n_null_total=int(nul.sum()),
        evidence=(f'Kiểm trên meta_dataset_seed_level.parquet ({N} dòng): trong {int(w.sum())} ô NULL không có khóa null_reason_map, {int(expl.sum())} ô nằm đúng trong tập dòng mà quy tắc nêu, '
                  f'{int((w & ~covered).sum())} ô không được quy tắc giải thích; dòng thuộc quy tắc nhưng ô có giá trị (phản ví dụ): {counter}.'),
        column_dictionary_sha256=dic_sha))
out = pd.DataFrame(rows)
out['code_definition_if_new'] = out.proposed_reason_code.map(lambda s: ' || '.join(f'{k}: {NEW[k]}' for k in s.split('|') if k in NEW))
out.to_csv(OUT + 'release_r2_errata_null_reasons.csv', index=False, encoding='utf-8', lineterminator='\n')
Wcov.to_pickle(OUT + '_overlay_cov.pkl')
print(len(out), 'cols; cells', int(out.n_null_without_reason.sum()), 'explained', int(out.n_cells_explained_by_rule.sum()), 'unexplained', int(out.n_cells_not_explained.sum()))
print(out[out.n_cells_not_explained > 0][['column_name', 'n_null_without_reason', 'n_cells_not_explained', 'n_rule_true_but_cell_not_null']].to_string())
print(out[out.n_rule_true_but_cell_not_null > 0][['column_name', 'n_rule_true_but_cell_not_null']].to_string())
