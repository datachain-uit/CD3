# -*- coding: utf-8 -*-
"""Assemble qa_outcomes_release_r2.csv from qa_results_raw.json (output of run_qa_release_r2.py) + NOT_RUN entries."""
import csv, hashlib, json, os
OUT = os.path.dirname(os.path.abspath(__file__))
raw = json.load(open(OUT + '/qa_results_raw.json', encoding='utf-8'))
R = raw['results']
TREE = ' Mã kiểm tra: tempo_fix của bàn giao 2026-11-26 (băm cây file trong handoff_2026-11-26_tree_sha256.txt; qa_checks.py sha256 2ef9fc51...09f3f), sao chép nguyên văn vào run_qa_release_r2.py.'
NAMES = {
 'QA01': ('Lưới đầy đủ', 'assembly release L3'), 'QA02': ('Ghép cặp before', 'assembly release L3'), 'QA03': ('Đồng nhất Δ', 'assembly release L3'),
 'QA04': ('Phân rã Δ', 'assembly release L3'), 'QA05': ('Tính lại metric', 'facts L2'), 'QA06': ('Tổng confusion matrix', 'facts L2'),
 'QA07': ('Xác suất', 'facts L2'), 'QA08': ('Kế toán ô', 'profile S0'), 'QA09': ('Unavailable đơn điệu', 'profile S0'),
 'QA10': ('Nhãn cố định', 'profile S0'), 'QA11': ('Không impute tương lai', 'facts L2'), 'QA12': ('Mẫu tổng hợp chỉ ở TRAIN', 'facts L2'),
 'QA13': ('Một checkpoint, một preprocessing', 'facts L2'), 'QA14': ('Sanity tests', 'facts L2'), 'QA15': ('Cờ seen', 'facts L2'),
 'QA16': ('Toàn vẹn file', 'release file'), 'QA17': ('Đơn vị', 'release file'), 'QA18': ('NULL có lý do', 'assembly release L3'),
 'QA19': ('Vai trò cột', 'release file'), 'QA20': ('Khóa duy nhất', 'assembly release L3'), 'QA21': ('Guard rò rỉ tiền xử lý', 'profile S0'),
 'QA22': ('Thứ tự thời điểm nhãn của split', 'profile S0'), 'QA23': ('Kiểm toán liên hệ proxy nhãn (CQ: 8 tiền tố hành vi đã duyệt được miễn theo quyết định 21)', 'profile S0'),
 'QA24': ('Bất biến cấp run (s_eff không đổi trong một run)', 'assembly release L3')}
NOTRUN = {
 'QA11': ('ô (n_cells_imputed_in_unavailable)', 'Chưa chạy: cột n_cells_imputed_in_unavailable (và mọi số đếm ô được impute) không có trong bảng release (chỉ có trong schema imputation_core/meta_storage.py), và không tìm thấy số liệu cấp run tương ứng cho 36 unit của release này. Không suy từ release cũ. Cần xuất số đếm từ worker imputation.'),
 'QA12': ('run / dự đoán VALIDATION-TEST', 'Chưa chạy: cần dự đoán cấp mẫu kèm cờ mẫu tổng hợp hoặc trpool_n_synth theo run; bảng release không có cột này. Các gói S2 sampling tìm thấy (CQ/resuilt/cq_s2_sampling_seed42_partial_20261103, LO/resuilt/lo_s2_sampling_seed42_20261106) chỉ phủ seed 42, trạng thái PARTIAL, và đo mục tiêu lấy mẫu chứ không phải kiểm QA12 nên không trích làm bằng chứng. Không suy từ release cũ.'),
 'QA13': ('run (P1-P4)', 'Chưa chạy: bảng release không có checkpoint_sha256/preprocessor_sha256 theo phase (chỉ reference_checkpoint_sha256 và reference_layout_sha256 của nhánh Mantis); gói facts chỉ có feature_layout_sha256 mức run. Cần băm checkpoint theo từng phase từ run_manifest.'),
 'QA14': ('test', 'Chưa chạy: không tìm thấy kết quả 6 sanity test của Kịch bản §3.5 gắn với release này (sanity_components.csv của các gói facts là thành phần điểm S_san+, không phải kết quả 6 test). Có thể chạy tempo_fix/sanity.py nếu có checkpoint; chưa thực hiện.'),
 'QA17': ('cột', 'Chưa chạy: từ điển cột không có trường đơn vị; hậu tố tên cột (_s, _kwh, _mb...) không đủ để khẳng định đơn vị (s, MB, W, kWh, gCO2e, USD). Cần bảng đơn vị chính thức để so khớp.'),
 'QA21': ('dòng / điều kiện', 'Chưa chạy: bảng release không có cờ qa_leak_guard_ok (7 cờ qa_* hiện có là metric_recompute, pairing, delta_identity, decomposition, run_level_invariant, leak_probe_identity, v0_zero_delta, đều true trên 73,440 dòng, xem evidence/ROWFLAGS_check.csv, và không thay được QA21). Các điều kiện (khóa trùng giữa partition, nhãn TRAIN sau train_cutoff - embargo, preprocessor fit trên TRAIN, imputer_predictors không chứa is_label_proxy = 1) cần artefact cấp run/split, chưa có cho release này.'),
 'QA22': ('split (task x window)', 'Chưa chạy cho release này. Có bằng chứng cấp dữ liệu đầu vào nhưng không gắn băm với manifest release: CQ/resuilt/m07_split_evidence_received_20261107/qa22.csv (CQ V2.2, qa22_ok = True cho W1-W3, sha256 4baf3d5dd4e0f98a...); LO chỉ có gói split evidence ghi "partial" (LO/resuilt/lo_split_evidence_20261106) không có kết quả qa22 tường minh. Không ghi PASS theo quy tắc không suy từ bản trước. Có thể chạy rẻ tempo_fix/split_v2.qa22 trên split registry CQ V2.2 và LO V3.1 nếu reviewer chấp nhận đó là đầu vào của release.'),
 'QA23': ('phase x task', 'Chưa chạy cho release này. Bằng chứng cấp đầu vào chỉ cho CQ: CQ/resuilt/cq_qa23_detail_20261103 (qa23_ok = true P1-P4, unreviewed_proxy_count = 0, proxy_in_imputer_predictors = 0, từ qa23_v2_2.zip) không gắn băm với manifest release; không tìm thấy kết quả tương đương cho LO. Không ghi PASS. Có thể chạy rẻ tempo_fix/feature_dictionary.qa23 nếu có từ điển feature + imputer_predictors của hai task.'),
}
def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest()
rows = []
for q in [f'QA{i:02d}' for i in range(1, 25)]:
    nm, layer = NAMES[q]
    if q in R:
        r = R[q]
        ev = r['evidence_file']; evs = sha(OUT + '/' + ev) if ev else ''
        note = r['note'] + (TREE if r['kind'] == 'recomputed' else (' Mã kiểm tra: tempo_fix 2026-11-26 chỉ dùng cho phần tính trên bảng.' if q == 'QA07' else ''))
        rows.append([q, nm, layer, r['unit'], r['n_units_checked'], r['n_pass'], r['n_fail'], r['status'], ev, evs, raw['run_date'], raw['code_commit'], note])
    else:
        u, n = NOTRUN[q]
        rows.append([q, nm, layer, u, 0, 0, 0, 'NOT_RUN', '', '', raw['run_date'], raw['code_commit'], n])
with open(OUT + '/qa_outcomes_release_r2.csv', 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f)
    w.writerow(['check_id', 'name', 'layer', 'unit', 'n_units_checked', 'n_pass', 'n_fail', 'status', 'evidence_file', 'evidence_sha256', 'run_date', 'code_commit', 'note'])
    w.writerows(rows)
for r in rows:
    print(r[0], r[7], r[4], r[5], r[6], r[8])
