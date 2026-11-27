import os as _os
# Machine roots come from environment variables (no machine paths in the repository).
REPO = _os.environ.get('TEMPO_REPO_ROOT', '.')
WORK = _os.environ.get('TEMPO_WORK_ROOT', '.')
AUDIT44 = _os.environ.get('TEMPO_AUDIT44_ROOT', '.')
WORKD = _os.environ.get('TEMPO_DELIVERY_WORK_ROOT', '.')
import json, hashlib
from pathlib import Path
OUT = Path(f'{WORKD}/l2_slices_and_per_class_3seeds_20261126')
m = json.loads((OUT / 'manifest.json').read_text(encoding='utf-8'))
T = ['evaluation_slices', 'metrics_per_class', 'bootstrap_metrics_per_class', 'cohort_slice_status']
L = []
L.append('# README_d — gói lát cắt đánh giá và metric theo lớp của 3 seed (REQUEST D)\n')
L.append('Gói gộp (concatenate) các bảng fact ĐÃ ĐƯỢC CHẤP NHẬN của 36 đơn vị = 2 task (CQ, LO) x 6 mô hình (RNN, LSTM, GRU, BILSTM, PATCHTST, MANTIS_V2) x 3 seed (42, 43, 44). Không tính lại bất kỳ giá trị nào; số dòng mỗi đơn vị trong đầu ra bằng số dòng của file nguồn (đã kiểm tra tự động, xem `manifest.json`).\n')
L.append('## Nội dung\n')
L.append('| File | Số dòng | Số cột | Đơn vị có đủ | Kích thước (byte) |\n|---|---|---|---|---|')
for t in T:
    o = m['outputs'][t]
    L.append(f"| `{t}.parquet` | {o['rows']:,} | {o['columns']} | {m['units_complete_per_table'][t]}/36 | {o['bytes']:,} |")
L.append('| `manifest.json` | | | | |\n| `sha256sums.txt` | | | | |\n| `parts/` + `parts/parts_manifest.json` | | | | bảng `evaluation_slices` (> 10 MB) tách theo task x seed, mỗi phần < 3 MB |\n')
L.append('Các bảng còn lại đều nhỏ hơn 10 MB nên không tách. Quy ước tách giống `seed_level_parts` của meta release (task x seed; `parts_manifest.json` có file, rows, bytes, sha256).\n')
L.append('## Cột thêm vào\n')
L.append('- `task`, `model_name`, `seed` đã có sẵn trong mọi file nguồn (giá trị được kiểm tra bằng đúng khóa đơn vị, không có sai lệch), nên giữ nguyên, không thêm trùng.\n- `source_package`: thư mục gói nguồn tương đối so với gốc Drive (không có đường dẫn máy). Với CQ PatchTST seed 42 có hai giá trị (v0-v6 và v7-v16).\n- `schema_version`: mô tả schema nguồn, dạng `<họ schema>;ncols=<số cột nguồn>;sig=<chữ ký schema>`; bảng chữ ký và khác biệt nằm ở `manifest.json` > `schema_differences`.\n- Không đổi tên cột nào. Cột là hợp của các nguồn theo thứ tự xuất hiện đầu tiên; đơn vị thiếu một cột thì giá trị null. Không có cột nào bị ép kiểu (`columns_with_mixed_source_types` rỗng cho cả 4 bảng).\n')
L.append('## Nguồn theo đơn vị\n')
L.append('Các gói đều là đường dẫn Drive hiện tại (sau đợt sắp xếp lại 25-26/11). Tên họ schema: `l2_facts_full_package_v1` = gói đầy đủ (slice dạng rộng ALL/STRICT/OVERLAP, per-class dạng dài, cohort_slice_status); `cq_r4_*` = xuất R4 CQ seed 42 (per-class dạng dài, slice từ gói reconciled); `lo_static_v2_audit_*` = audit LO static v2 seed 42.\n')
L.append('| Task | Mô hình | Seed | Gói nguồn (Drive-relative) | slices | per-class | bootstrap | cohort |\n|---|---|---|---|---|---|---|---|')
for u in m['units']:
    pk = sorted({sf['source_package'] for t in T for sf in u['tables'][t].get('source_files', [])})
    def c(t):
        v = u['tables'][t]
        return f"{v['rows']:,}" if v['status'] == 'OK' else 'NOT_AVAILABLE'
    L.append(f"| {u['task']} | {u['model_name']} | {u['seed']} | " + '<br>'.join(f'`{p}`' for p in pk) + f" | {c('evaluation_slices')} | {c('metrics_per_class')} | {c('bootstrap_metrics_per_class')} | {c('cohort_slice_status')} |")
L.append('\nGhi chú nguồn seed 42 xuất F1 (RNN/LSTM/GRU/BILSTM):\n')
L.append('- CQ seed 42: `evaluation_slices` lấy từ `CQ/L2_facts/model_facts/seed=42/other_exports/cq_r4_slices_reconciled_20261103/cq_evaluation_slices.parquet` (một file chứa cả 4 mô hình, 4,896 dòng; lọc theo `model_name`, mỗi mô hình 1,224 dòng; có thêm 7 cột `audit_*`, `probability_metric_origin`, `prediction_sha256`, `acctempo_m4`). `metrics_per_class` và `bootstrap_metrics_per_class` lấy từ `cq_metrics_per_class_long.parquet` (4,896 dòng) và `cq_bootstrap_metrics_per_class_long.parquet` (14,688 dòng) của `CQ/L2_facts/model_facts/seed=42/F1_recurrent/cq_recurrent_allfamilies_grid_r4_20261023`, cũng lọc theo `model_name`.\n- LO seed 42: từng mô hình lấy từ audit LO static v2 trong `LO/L1_runs/S3_model/seed=42/primary/release=LO_STATIC_V2/lo_static_v2_seed42_20261026` (RNN/LSTM/GRU: `models/<M>/audits/LO/<M>/seed=42`; BILSTM: `audits/closure_seed42/audits_seed42/LO/BILSTM/seed=42`). MD5 của các file này trùng với bản trên Drive (inventory 21/11).\n- Xác nhận đây là nguồn được chấp nhận: các dòng `slice == ALL` của hai nguồn trên khớp tuyệt đối (sai khác 0.0 ở macro_f1, c0_recall hoặc s_leak) với file xuất mà release đã đọc (`cq_r4_with_regime_macro.parquet`, `lo_static_v2_facts_no_confusion.parquet`; sha256 trùng `inputs_sha256`). Chi tiết ở `manifest.json` > `check_all_rows_vs_release_inputs`.\n')
L.append('## NOT_AVAILABLE\n')
L.append(f"`cohort_slice_status` không tồn tại cho 8 đơn vị seed 42 F1 (CQ và LO x RNN/LSTM/GRU/BILSTM): gói R4 CQ và audit LO static v2 không sinh bảng này (chỉ có ở gói F2/F3 seed 42 và các gói seed 43/44). Không tổng hợp lại. Bảng đủ 36/36 cho `evaluation_slices`, `metrics_per_class`, `bootstrap_metrics_per_class`; `cohort_slice_status` có 28/36 (cohort_slice_status: {m['outputs']['cohort_slice_status']['rows']:,} dòng = 28 x 1,632). Lý do theo từng đơn vị nằm ở `manifest.json` > `not_available`. (Trên Drive có bảng khác tên `seen_unseen_strict_overlap_metrics` trong gói lịch sử `lo_static_v2_cohort_audit_20261028`, schema khác; không dùng.)\n")
L.append('## Kiểm tra số dòng\n')
L.append('Mỗi đơn vị có đúng 1,224 dòng slice (408 ô x 3 lát cắt), 1,224 dòng per-class, 3,672 dòng bootstrap (1,224 x 3 metric precision/recall/f1) và 1,632 dòng cohort (khi có), đúng như README của các gói. CQ PatchTST seed 42 = 504 + 720 (v0-v6 + v7-v16), 1,224 tổng; cohort 672 + 960 = 1,632. Không có sai lệch số dòng.\n')
L.append('## Xác minh nguồn được chấp nhận\n')
L.append('- Seed 43, 44 và seed 42 PatchTST/Mantis: sha256 của `sanity_components.csv` trong gói khớp `inputs_sha256` của release `CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2` (36 đơn vị có xác minh kiểu này hoặc ALL-row, không có sai khác). Các file bảng khớp `sha256sums.txt` của gói (trừ 8 đơn vị audit seed 42 F1 không có sha256sums tương ứng; thay bằng MD5 trùng Drive và kiểm tra dòng ALL).\n- Mọi file nguồn có MD5 trùng một file trong inventory Drive 21/11, và kích thước khớp danh sách Drive 26/11.\n')
L.append('## Khác biệt schema (chi tiết trong `manifest.json` > `schema_differences`)\n')
L.append('- `evaluation_slices`: 62 cột chuẩn (28 đơn vị). CQ F1 seed 42 (R4 reconciled) có 69 cột: thêm `audit_log_loss`, `audit_brier`, `audit_ece`, `audit_pr_auc_macro`, `probability_metric_origin`, `prediction_sha256`, `acctempo_m4`. CQ PatchTST, LO PatchTST, LO Mantis seed 42 có thêm `acctempo_m4` (63 cột); CQ Mantis seed 42 có thêm `acctempo_m4`, `model_tier`, `variant_role`, `run_purpose` (66 cột).\n- `metrics_per_class` và `bootstrap_metrics_per_class`: 32 cột chuẩn (24 đơn vị: toàn bộ seed 43 và 44). 10 đơn vị seed 42 (F1 R4/LO audit và PatchTST) có 34 cột: thêm `probe_fit_rows`, `s_leak_probe_n_eval`, `probe_score_scope`, và thiếu `s_leak_source`. CQ Mantis seed 42 thêm `model_tier`, `variant_role`, `run_purpose` (37 cột); LO Mantis seed 42 thêm các cột `probe_solver`, `probe_tol`, `probe_max_iter`, `probe_n_iter`, `probe_deterministic_single_thread` (39 cột).\n- `cohort_slice_status`: một schema 16 cột cho cả 28 đơn vị.\n- Không có khác biệt kiểu dữ liệu giữa các nguồn cho cột trùng tên.\n')
L.append('## Ghi chú\n- Các gói seed 43/44 và seed 42 PatchTST/Mantis đọc trực tiếp từ gói đã chấp nhận (bản sao cục bộ trùng sha256 với `inputs_sha256`); seed 43 tải mới từ Drive (chỉ tải xuống, không tải lên/xóa/di chuyển).\n- Không commit, không đẩy lên Drive.\n')
(OUT / 'README_d.md').write_text('\n'.join(L), encoding='utf-8')
# sha256sums
lines = []
for p in sorted(OUT.rglob('*')):
    if p.is_file() and p.name != 'sha256sums.txt':
        lines.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(OUT).as_posix()}")
(OUT / 'sha256sums.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
print('\n'.join(lines))
