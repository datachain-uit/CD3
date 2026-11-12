# Phản hồi yêu cầu đội code 10/11/2026 — trạng thái 12/11/2026

Đối chiếu `docs/10112026/review/Yeu_cau_doi_code_2026-11-10.md`. Mọi đường dẫn Drive tính từ thư mục gốc dùng chung. Biên nhận của đội code là biên nhận chuyển giao ở mức byte (`DELIVERED_AND_BYTE_VERIFIED_NOT_L2_INGESTED`), không phải biên nhận ingest L2.

## Trạng thái từng mục

| Mục | Trạng thái | Vị trí / ghi chú |
|---|---|---|
| 1. M-15 | Bản p1 và full42 đã nộp; chạy lại sáu cấu hình trên release sửa `…20261112` đang tiến hành | `cross_task_meta/accepted/mm_runs_CQ_LO_p1`, `…/mm_runs_CQ_LO_full42`. `obj_macrof1` đầy đủ chạy được trên release sửa (bản cũ lỗi vì cột macro-F1 của CQ RECURRENT trống, xem "Lỗi cần phía viết sửa"). Khi đủ sáu cấu hình sẽ nộp `mm_runs_*_r2` và đánh dấu bản cũ SUPERSEDED. |
| 2. Lắp lại M-14 (0.2.2) | Xong | `cross_task_meta/accepted/meta_release_CQ_LO_p1_F2V0V16_20261112` và `…full42_F1F2F3_20261112` (macro-F1 của CQ RNN/LSTM/GRU/BILSTM đã điền). Bốn release cũ (`…p1_20261109`, `…p1_F2V0V16_20261109`, `…p1_F2V0V16_20261110`, `…full42_F1F2F3_20261111`) có `SUPERSEDED.md`. |
| 3.1 Bench và pilot | Xong | Bench: `mantis_bench_20261112`. Pilot W1/V0: CQ (`run_B` so `run_C`) và LO (`run_A` so `run_C`), cả hai PASS, kèm khối phiên bản thư viện, README và `sha256sums.txt`, trong thư mục `pilot_determinism_*` của từng task. |
| 3.2 Báo cáo đầu dò | Xong | `CQ/L0_registry/s_leak_reference_20261109` và `LO/L0_registry/s_leak_reference_20261109`: báo cáo CQ W1/V0 và LO W1–W3/V0. Ở chế độ mặc định, lệch so với bảng tham chiếu = 0.0 ở cả bốn ô; các lượt chạy đơn luồng tất định ở chế độ khác nên lệch nhẹ (bảng trong README). |
| 4.1 Chữ "author decision" | Xong | Đổi thành "writing-side recommendation … applied <ngày>, author ratification pending" ở manifest, summary, builder và bằng chứng commit; "author decision 2026-10-24" (N10) giữ nguyên. Commit `2b17334`. |
| 4.2 Script C3 | Xong | `v0_cells` ghi đúng dạng dict; số máy giống nhau tính từ dữ liệu (`--host-hashes` nhận nhiều tệp). Commit `2b17334`. |
| 4.3 Registry | Xong | `REGISTRY_REVISION = registries_rev_2026-11-10_d18_mantis_clean`; export tại `LO/L0_registry/registry_export_repo_20261110`. |
| 5. Ba gói CQ `_r2/_r3` | Xong | `cq_patchtst_v0_v6_full_facts_20261103_r2`, `cq_patchtst_v7_v16_full_facts_20261109_r2`, `cq_mantis_v2_v0_v16_full_facts_20261109_r3` (s_leak chép từ bảng tham chiếu CQ; README đã sửa nguồn). Gói cũ có `SUPERSEDED.md`. |
| 6. Mantis LO | Xong | `LO/L2_facts/fact_exports/lo_mantis_v2_v0_v16_full_facts_20261110`. |
| 7.1 S2 seed 43/44 | Seed 43 xong; seed 44 đang chạy | Seed 43: `CQ/L2_facts/s2_augmentation_seed43`, `LO/L2_facts/s2_augmentation_seed43`. |
| 7.2 F1/F2 seed 43/44 | Đang chạy | PatchTST CQ seed 43 còn vài ô; Mantis CQ seed 43 đang chạy các pipeline con. LO seed 43/44 và seed 44 CQ chưa bắt đầu. |
| 7.3 M-18 và L2 | M-18 seed 42 xong; seed 43 chưa | `cross_task_meta/accepted/m18_training_history_seed42_20261111`. Ingest L2 chính thức do phía viết thực hiện. |

## Biên nhận chuyển giao

`cross_task_meta/work_in_progress/delivery_receipts_20261112`: tám biên nhận (ba gói CQ, hai gói LO, hai release `…20261112`, M-18), mỗi tệp có kích thước, sha256 và MD5 cục bộ so với MD5 Drive; 0 vấn đề. Công cụ: `tools/build_delivery_receipts_20261112.py`.

## Lỗi cần phía viết sửa (metamodel 0.2.2 → 0.2.3)

1. **`assemble.py` (dòng 62–63):** việc đổi tên cột bí danh (`f1_macro` → `macro_f1`) bị bỏ qua khi cột đích đã tồn tại trong bảng sau khi nối. Khi facts PatchTST hoặc Mantis (đã có `macro_f1`) được nối với R4 của CQ F1 (cột `f1_macro`), các cột macro-F1 của CQ RNN/LSTM/GRU/BILSTM rỗng và `obj_macrof1` lỗi `Input y contains NaN`. Cách tạm: lắp từ bản sao R4 có `macro_f1 = f1_macro` (đã dùng cho release `…20261112`). Đề nghị: đổi tên theo từng nguồn trước khi nối.
2. **B5 (KNNMeta):** cột chuỗi `*_prev_reason` lọt vào ma trận đặc trưng làm B5 lỗi. Bản vá cục bộ chỉ giữ cột số: `local_patch_baselines_B5.diff` trong `mm_runs_CQ_LO_p1_20261111`. Đề nghị đưa vào 0.2.3.
