# Phản hồi yêu cầu đội code 10/11/2026 — trạng thái 13/11/2026

Đối chiếu `docs/10112026/review/Yeu_cau_doi_code_2026-11-10.md`. Mọi đường dẫn Drive tính từ thư mục gốc dùng chung. Đội code cấp hai loại biên nhận: biên nhận chuyển giao ở mức byte (`DELIVERED_AND_BYTE_VERIFIED_NOT_L2_INGESTED`) và biên nhận ingest L2 (mục cuối).

## Trạng thái từng mục

| Mục | Trạng thái | Vị trí / ghi chú |
|---|---|---|
| 1. M-15 | p1 đã nộp (13/11); full42 đang chạy lại (bổ sung) | `cross_task_meta/accepted/mm_runs_CQ_LO_p1_20261113`: sáu cấu hình chạy trong môi trường chuẩn (Python 3.12.1, NumPy 2.5.4, SciPy 1.18.1, scikit-learn 1.9.1, LightGBM 4.7.0, Optuna 5.0.0), `obj_macrof1` chạy đầy đủ, kèm `RUN_LOG.md`, `pip_freeze.txt`, `sha256sums.txt`; bản cũ có `SUPERSEDED.md`. **full42** không nằm trong yêu cầu 10/11: đội code chạy lại cùng môi trường để thay gói full42 đã nộp 12/11 theo release `…20261112`, sẽ nộp khi xong; nếu không cần thì gói full42 cũ giữ nguyên. **Đề xuất cho phía viết:** điểm số mức mô hình của L4 và L5 thay đổi theo phiên bản thư viện (kiểm trên hai bộ phiên bản; kết luận H1–H8 không đổi), nên các lần chạy sau dùng đúng phiên bản thư viện ghi trong `pip_freeze.txt` của gói. |
| 2. Lắp lại M-14 (0.2.2) | Xong | `cross_task_meta/accepted/meta_release_CQ_LO_p1_F2V0V16_20261112` và `…full42_F1F2F3_20261112` (macro-F1 của CQ RNN/LSTM/GRU/BILSTM đã điền). Bốn release cũ (`…p1_20261109`, `…p1_F2V0V16_20261109`, `…p1_F2V0V16_20261110`, `…full42_F1F2F3_20261111`) có `SUPERSEDED.md`. |
| 3.1 Bench và pilot | Xong | Bench: `mantis_bench_20261112`. Pilot W1/V0: CQ (`run_B` so `run_C`) và LO (`run_A` so `run_C`), cả hai PASS, kèm khối phiên bản thư viện, README và `sha256sums.txt`, trong thư mục `pilot_determinism_*` của từng task. |
| 3.2 Báo cáo đầu dò | Xong | `CQ/L0_registry/s_leak_reference_20261109` và `LO/L0_registry/s_leak_reference_20261109`: báo cáo CQ W1/V0 và LO W1–W3/V0. Đầu dò chạy ở chế độ mặc định (đa luồng, nhãn `default_multithread` trong báo cáo): lệch so với bảng tham chiếu = 0.0 ở cả bốn ô, vì bảng tham chiếu được tạo ở chế độ này. Các lượt `deterministic_run_*` chạy đơn luồng, tức khác chế độ mặc định, nên lệch nhẹ so với bảng tham chiếu (CQ W1 2,1e-5; LO W1 1,1e-4, W2 9,6e-4, W3 7,2e-6; bảng trong README). Hai lượt tất định lặp lại giống hệt nhau từng bit. |
| 4.1 Chữ "author decision" | Xong | Đổi thành "writing-side recommendation … applied <ngày>, author ratification pending" ở manifest, summary, builder và bằng chứng commit; "author decision 2026-10-24" (N10) giữ nguyên. Commit `2b17334`. |
| 4.2 Script C3 | Xong | `v0_cells` ghi đúng dạng dict; số máy giống nhau tính từ dữ liệu (`--host-hashes` nhận nhiều tệp). Commit `2b17334`. |
| 4.3 Registry | Xong | `REGISTRY_REVISION = registries_rev_2026-11-10_d18_mantis_clean`; export tại `LO/L0_registry/registry_export_repo_20261110`. |
| 5. Ba gói CQ `_r2/_r3` | Xong | `cq_patchtst_v0_v6_full_facts_20261103_r2`, `cq_patchtst_v7_v16_full_facts_20261109_r2`, `cq_mantis_v2_v0_v16_full_facts_20261109_r3` (s_leak chép từ bảng tham chiếu CQ; README đã sửa nguồn). Gói cũ có `SUPERSEDED.md`. |
| 6. Mantis LO | Xong | `LO/L2_facts/fact_exports/lo_mantis_v2_v0_v16_full_facts_20261110`. |
| 7.1 S2 seed 43/44 | Seed 43 xong; seed 44 chạy xong, đang sao lưu | Seed 43: `CQ/L2_facts/s2_augmentation_seed43`, `LO/L2_facts/s2_augmentation_seed43`. Seed 44: đủ 72/72 ô (CQ 36, LO 36), đã kiểm từng ô (trạng thái, seed, phương pháp, số hàng và phân bố lớp, tập validation/test chưa bị động tới): không vấn đề. Đầu ra thô đang sao lưu lên `…/L1_runs/S2_augmentation/seed44_raw_outputs_20261113/`; bố cục chuẩn như seed 43 dựng sau khi sao lưu xong. |
| 7.2 F1/F2/F3 seed 43/44 | Đang chạy | Seed 43: F1 LO 204/204 trên Drive, F1 CQ 203/204 (thiếu BILSTM W3 V16); PatchTST CQ 51/51; Mantis CQ 50/51; PatchTST LO đang chạy; Mantis LO chưa bắt đầu. Seed 44: F1, F2, F3 chưa bắt đầu. |
| 7.3 M-18 và L2 | M-18 seed 42 xong; seed 43 chưa; biên nhận ingest L2 đã lập | `cross_task_meta/accepted/m18_training_history_seed42_20261111`. Biên nhận ingest L2 của các gói 09–13/11: xem mục cuối. |

## Biên nhận chuyển giao

`cross_task_meta/work_in_progress/delivery_receipts_20261112`: tám biên nhận (ba gói CQ, hai gói LO, hai release `…20261112`, M-18), mỗi tệp có kích thước, sha256 và MD5 cục bộ so với MD5 Drive; 0 vấn đề. Công cụ: `tools/build_delivery_receipts_20261112.py`.

## Lỗi cần phía viết sửa (metamodel 0.2.2 → 0.2.3)

1. **`assemble.py` (dòng 62–63):** việc đổi tên cột bí danh (`f1_macro` → `macro_f1`) bị bỏ qua khi cột đích đã tồn tại trong bảng sau khi nối. Khi facts PatchTST hoặc Mantis (đã có `macro_f1`) được nối với R4 của CQ F1 (cột `f1_macro`), các cột macro-F1 của CQ RNN/LSTM/GRU/BILSTM rỗng và `obj_macrof1` lỗi `Input y contains NaN`. Cách tạm: lắp từ bản sao R4 có `macro_f1 = f1_macro` (đã dùng cho release `…20261112`). Đề nghị: đổi tên theo từng nguồn trước khi nối.
2. **B5 (KNNMeta):** cột chuỗi `*_prev_reason` lọt vào ma trận đặc trưng làm B5 lỗi. Bản vá cục bộ chỉ giữ cột số: `local_patch_baselines_B5.diff` trong `mm_runs_CQ_LO_p1_20261113`. Đề nghị đưa vào 0.2.3.

## Biên nhận ingest L2

Đội code lập biên nhận ingest L2 cho chín gói: năm gói facts (Mantis CQ r3, PatchTST CQ V0–V6 và V7–V16 r2, PatchTST LO r2, Mantis LO), hai release `…20261112`, M-18 seed 42 và M-15 p1 (`mm_runs_CQ_LO_p1_20261113`). Thư mục `cross_task_meta/work_in_progress/l2_ingest_receipts_20261113`, công cụ `tools/build_l2_ingest_receipts_20261113.py`. Mỗi biên nhận kiểm: gói nằm đúng một chỗ trên Drive, mọi tệp khớp MD5 với bản trong repo, `sha256sums` đủ và đúng, và các điều kiện kiểm được của yêu cầu 10/11 (`s_leak` trùng bảng tham chiếu ≤ 1e-9, nhãn tier/role/purpose, `runner_git_commit`, `resource_null_reason`, `source_inventory`).

- **Đủ điều kiện:** 6 gói (hai gói PatchTST CQ, hai release, M-18, M-15 p1). Với hai gói PatchTST CQ, `runner_git_commit` (29da3b2) do runner ghi vào manifest lúc chạy: đã mở đối chiếu 9 manifest của ba bundle gốc (V1, V7, V10).
- **Có ngoại lệ, chờ tác giả quyết định:** 3 gói (Mantis CQ r3, Mantis LO, PatchTST LO r2) có `runner_git_commit` ánh xạ hồi tố từ nội dung runner, không ghi lúc chạy như mục 6.1 đòi. Manifest Mantis ghi lúc chạy `runner_sha256` và `code_tar_sha256` (nhận diện theo nội dung); PatchTST LO chỉ khớp theo cây mã trên 12 máy. Các lượt chạy đã xong, nên khắc phục thật sự là chạy lại cả lưới seed 42. Ba cell V0 của Mantis CQ để NULL theo Q-32 (a).

### Đề xuất cho tác giả về `runner_git_commit` hồi tố

Ba gói có ngoại lệ không sửa được bằng cách làm thêm trên dữ liệu đã chạy: lúc chạy runner không ghi commit. Đội code đề xuất để tác giả cân nhắc: chấp nhận `runner_git_commit_basis = *_RETROACTIVE` làm cơ sở ingest khi có nhận diện nội dung đi kèm (Mantis: `runner_sha256` và `code_tar_sha256` ghi trong manifest lúc chạy; PatchTST LO: khớp cây mã trên 12 máy), và ghi nhãn cơ sở trong manifest. Nếu tác giả đồng ý, ba ngoại lệ chuyển thành đạt kèm nhãn; nếu không, cách khắc phục duy nhất là chạy lại lưới seed 42 của ba gói. Trong lúc chờ quyết định, trạng thái giữ là `L2_INGEST_WITH_EXCEPTIONS`.
