# -*- coding: utf-8 -*-
"""Tong hop qa4_results.json + bang lien ket QA23 tu cac file bang chung da tao boi qa17.py, qa14.py, qa22.py, qa23.py.
Env: QA4_OUT, TEMPO_REPO_ROOT. Doc-chi-doc voi repo (git rev-parse)."""
import os, re, json, hashlib, subprocess
import pandas as pd

OUT = os.environ['QA4_OUT']
REPO = os.environ['TEMPO_REPO_ROOT']
commit = subprocess.run(['git', '-C', REPO, 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True).stdout.strip()
RUN_DATE = '2026-11-26'


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest()


# ---------- QA23: bang lien ket + tong hop ----------
aud = pd.read_csv(f'{OUT}/qa23_fullrows/qa23_audit_by_feature.csv')
S = pd.read_csv(f'{OUT}/qa23_fullrows/qa23_summary_by_phase.csv')
cq = aud[(aud.task == 'CQ') & aud.reviewed_base_cq].copy()
cq['base'] = cq.column_name.str.replace(r'_P[1-4]$', '', regex=True)
cq['column_phase'] = cq.column_name.str.extract(r'_(P[1-4])$')[0]
cq = cq[cq.column_phase <= cq.phase_id]   # tai Pk chi cac bien P1..Pk la hop le
cq = cq[['task', 'window_id', 'phase_id', 'base', 'column_phase', 'column_name', 'n_obs', 'spearman_rho', 'spearman_abs', 'nmi', 'flagged_by_rule', 'needs_review', 'proxy_review_note']]
cq.to_csv(f'{OUT}/qa23_cq_behavioural_linkage_by_base.csv', index=False)
lo = aud[(aud.task == 'LO') & aud.lo_grade_group]
lo = lo[lo.column_name.str.extract(r'_(P[1-4])$')[0] <= lo.phase_id]
lo[['task', 'window_id', 'phase_id', 'column_name', 'n_obs', 'spearman_rho', 'spearman_abs', 'nmi', 'needs_review', 'proxy_review_note']].to_csv(f'{OUT}/qa23_lo_current_grade_group.csv', index=False)
# doi chieu voi bang lien ket da luu (Drive, tai ve read-only trong src/drive): |rho| max theo phase cua 8 co so
mx = cq.groupby(['window_id', 'phase_id']).agg(max_abs_rho=('spearman_abs', 'max'), max_nmi=('nmi', 'max')).reset_index()
try:
    old = pd.read_csv(f'{OUT}/src/drive/cq_qa23_reviewed_behavioural_linkage.csv')
    om = old.groupby('phase_id').agg(drive_max_abs_rho=('spearman_abs', 'max'), drive_max_nmi=('nmi', 'max'), drive_n_columns=('column_name', 'size')).reset_index()
    mx = mx.merge(om, on='phase_id', how='left')
except FileNotFoundError:
    pass
mx.to_csv(f'{OUT}/qa23_cq_linkage_max_vs_stored.csv', index=False)

res = []
rec = lambda **k: res.append(dict(run_date=RUN_DATE, code_commit=commit, **k))

# ---------- QA17 ----------
u = pd.read_csv(f'{OUT}/qa17_unit_table.csv'); ck = pd.read_csv(f'{OUT}/qa17_checks.csv')
n_pass = int((u.status == 'PASS').sum()); n_fail = int((u.status != 'PASS').sum()) + int(ck.n_fail.sum())
rec(check_id='QA17', status='PASS' if n_fail == 0 else 'FAIL', unit='cột COST của release (12 ở bảng seed-level + 84 ở bảng seed_agg)', n_units_checked=len(u), n_pass=n_pass, n_fail=n_fail,
    evidence_file='qa17_unit_table.csv', evidence_sha256=sha(f'{OUT}/qa17_unit_table.csv'),
    note=('Từ điển cột của release không có trường đơn vị. Đơn vị gán theo định nghĩa đăng ký: quy ước đặt tên trong Mo_ta_meta-dataset (_s = giây, _kwh = kWh; ratio không thứ nguyên; delta cùng đơn vị với cột gốc) '
          'và công thức energy_nvml.py (kWh = mJ/3.6e9 hoặc tích phân W*s/3.6e6). Kiểm tra: hậu tố tên khớp đơn vị; miền giá trị theo đơn vị (s: 0<x<=7 ngày; kWh: 0<x<=10; ratio: 0<x<=100; sd>=0); '
          'time_train_s <= time_run_total_s trên 73,320 dòng; ratio = after/before và delta = after-before (1e-9 tương đối); công suất trung bình suy ra = kWh*3.6e6/s theo run nằm trong [10,100] W '
          '(1,605 run có năng lượng; min 22.9 W, median 33.9 W, max 72.06 W, phù hợp GPU L4 TDP 72 W; ước lượng NVML_POWER_SAMPLING_ESTIMATE). Phạm vi: release chỉ có cột thời gian (s) và năng lượng (kWh); '
          'KHÔNG có cột MB, W, gCO2e, USD nào trong hai bảng nên các đơn vị này không thể kiểm (không áp dụng, không phải đã pass). '
          'Hạn chế: nguồn định nghĩa là tài liệu Mo_ta và mã tempo_fix, không phải trường trong từ điển cột; đề xuất thêm trường unit vào meta_column_dictionary.csv. '
          '9,120 dòng energy_measurement_type = UNAVAILABLE và 120 dòng trống không có kWh (không đưa vào min/max). Bảng đề xuất: qa17_unit_table.csv.'))

# ---------- QA14 ----------
e = pd.read_csv(f'{OUT}/qa14_evidence.csv'); struct = e[~e['item'].str.startswith('search')]
rec(check_id='QA14', status='NOT_RUN', unit='test (6 sanity test của Kịch bản §3.5)', n_units_checked=0, n_pass=0, n_fail=0,
    evidence_file='qa14_evidence.csv', evidence_sha256=sha(f'{OUT}/qa14_evidence.csv'),
    note=('Không tìm thấy kết quả của 6 sanity test (prefix nesting, label identity, split identity, future perturbation, cutoff equality, cardinality) gắn với release này: manifest release không có khóa kết quả test '
          '(chỉ đường dẫn sanity_components.csv, là thành phần điểm S_san+, không thay thế kiểm tra theo Meta-Dataset-Report), bảng release không có cột qa_sanity_tests_ok, run_manifest mẫu không có khóa sanity/pre_run/check, '
          'listing Drive (inventory_all.parquet, drive_ctm_20261126.json) không có file kết quả test, và không có tools/*sanity* hay báo cáo phase_builder cho 36 gói unit. '
          'Không chạy lại được đủ 6 test: prefix nesting, future perturbation và cutoff equality cần dữ liệu sự kiện thô hoặc chạy lại phase builder (phase view local chỉ là bảng rộng cấp enrollment). '
          f'Bằng chứng bổ sung (KHÔNG thay 6 test): {len(struct)} kiểm tra cấu trúc trên phase view local của CQ và LO (một dòng/enrollment/window, enrollment thuộc một partition, TEST P1-P4 cùng tập enrollment, cutoff P1<=P2<=P3<=P4, '
          f'nhãn duy nhất/enrollment): {int((struct.result == "PASS").sum())} PASS, {int((struct.result == "FAIL").sum())} FAIL. Cần: kết quả 6 test của lần chạy phase builder tạo view v2.2/v3.1, kèm sha256 gắn với view.'))

# ---------- QA22 ----------
B = pd.read_csv(f'{OUT}/qa22_recomputed_from_views.csv'); A = pd.read_csv(f'{OUT}/qa22_registry_check.csv')
ok = (B.qa22_ok & B.end_order_ok & B.counts_match_registry & A.qa22_ok.reset_index(drop=True)).astype(bool)
rec(check_id='QA22', status='PASS' if ok.all() else 'FAIL', unit='split (task x window), 3 window x 2 task', n_units_checked=len(B), n_pass=int(ok.sum()), n_fail=int((~ok).sum()),
    evidence_file='qa22_recomputed_from_views.csv', evidence_sha256=sha(f'{OUT}/qa22_recomputed_from_views.csv'),
    note=('Hàm repo split_v2.qa22 (tempo_fix bàn giao 2026-11-26) chạy hai lần cho mỗi task và window: (A) trên split registry đã lưu (CQ: split_version v2.2, m07_split_evidence_received_20261107/split_registry.csv; '
          'LO: v3.1.scored.signal.excluded, lo_split_evidence_20261106/split_registry_source.csv; cờ end_order_ok được tính lại từ tau_w <= min_evaluation_end_utc và khớp cờ đã lưu); '
          '(B) tính lại từ phase view local (downloads/raw_views_20261108: phase_views_v2_2, phase_views_v3_1_scored_signal_excluded và test P4): mốc kết thúc offering = enroll_time + (cutoff_P4 - enroll_time)/0.90 làm tròn phút '
          '(= window_end_exclusive, nên bằng ngày kết thúc registry cộng 1 ngày), tau_w = max TRAIN, so với min kết thúc của VALIDATION/TEST; hai tập đánh giá không rỗng; số enrollment VAL/TEST khớp registry 6/6. '
          'Kết quả 6/6 pass cả hai nguồn. Lưu ý: CQ có biên độ 0 ngày (min kết thúc đánh giá = tau_w, điều kiện là <=, hợp lệ); LO có biên 1-2 ngày. Mỗi window có 1 offering có hai mốc kết thúc khác nhau 1 ngày '
          '(lấy max cho TRAIN, min cho VAL/TEST, tức là phía bất lợi). Liên kết băm: sha256 của hai file view local và hai registry ghi trong qa22_inputs_sha256.csv; sha256 hai file view local trùng với bản lưu trên Drive (inv_CQ.json, inv_LO.json). '
          'Giới hạn: registry và view không nằm trong inputs_sha256 của manifest release; gắn với release qua split_version (CQ v2.2, LO v3.1) và meta_release_id con CQ_V2_2_*/LO_V3_1_* chứ không bằng băm. '
          'Bằng chứng m07 ghi trạng thái PARTIAL (quần thể thô trước nhãn chưa xác minh độc lập), không đổi kết quả của kiểm tra này.'))

# ---------- QA23 ----------
n_units = len(S); n_p = int(S.qa23_ok.sum()); n_f = n_units - n_p
cqS, loS = S[S.task == 'CQ'], S[S.task == 'LO']
rec(check_id='QA23', status='PASS' if n_f == 0 else 'FAIL', unit='kiểm toán (task x window x phase), 2 task x 3 window x 4 phase', n_units_checked=n_units, n_pass=n_p, n_fail=n_f,
    evidence_file='qa23_fullrows/qa23_summary_by_phase.csv', evidence_sha256=sha(f'{OUT}/qa23_fullrows/qa23_summary_by_phase.csv'),
    note=(f'Chạy audit_label_proxy + qa23 của tempo_fix trên toàn bộ dòng TRAIN của phase view local (không lấy mẫu), mỗi window và mỗi phase P1-P4; CQ đích = CQ_proximity_final, LO đích = performance_score. '
          f'CQ (từ điển = bản sao nguyên văn classify() và danh sách 8 cơ sở hành vi miễn theo quyết định 21 của audit_cq_label_proxy.py; số cột kiểm toán 90/161/232/303 và cờ is_label_proxy khớp từ điển đã lưu cq_qa23_detail_20261103): '
          f'{int(cqS.qa23_ok.sum())}/{len(cqS)} pass (W1 và W3 đủ P1-P4 pass; W2 fail ở P1-P4 với 1/6/10/15 hàng needs_review chưa có ghi chú, tất cả là cột video_* và segment_* chỉ có 98-497 quan sát không rỗng trong TRAIN W2, '
          f'|rho|>=0.5 trên mẫu rất nhỏ; hàm repo không có ngưỡng n tối thiểu). Không có proxy trong imputer predictors và không thiếu cột trong kiểm toán ở 24/24. '
          f'Bảng liên kết từng cơ sở (quyết định 21): qa23_cq_behavioural_linkage_by_base.csv; so với bảng đã lưu trên Drive (gộp window) trong qa23_cq_linkage_max_vs_stored.csv. '
          f'LO: {int(loS.qa23_ok.sum())}/{len(loS)} pass: không có quyết định miễn hay ghi chú review cho LO trong registry (quy tắc LO chỉ nói chạy theo phase và báo cáo nhóm current-grade; 19 trường canonical của lo_proxy_contract_v3 và biến thể _Pk đặt is_label_proxy=1), '
          f'nên các cột hành vi như score_sum, correct_problem_count, unique_video_count... có |rho|>=0.5 (max |rho| 0.64-0.92 trên các phase) bị tính là chưa review (6-42 hàng mỗi phase); bảng nhóm current-grade: qa23_lo_current_grade_group.csv. '
          f'Từ điển LO do tôi dựng từ registry (không có từ điển LO đã duyệt có is_label_proxy), kết luận LO phụ thuộc cách đọc đó. Tác giả cần quyết định có đăng ký review/miễn cho LO hay không. '
          f'Chạy phụ với mẫu 500,000 dòng (mặc định repo) trong qa23_full500k/ cho cùng kết luận tổng thể (CQ W2 P2-P4 fail, LO fail). Spearman/NMI tính bằng hàm repo (NMI chia 20 phân vị), không giống ntile Spark của công cụ gốc.'))

json.dump(res, open(f'{OUT}/qa4_results.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
for r in res:
    print(r['check_id'], r['status'], r['n_units_checked'], r['n_pass'], r['n_fail'])
