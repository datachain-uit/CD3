# Phản hồi yêu cầu đội code 20/11/2026 (đợt 30, bản 2) — trạng thái 21/11/2026

Đối chiếu `Yeu_cau_doi_code_2026-11-20_ban2.md`. Mọi đường dẫn Drive tính từ thư mục gốc dùng chung, dưới `cross_task_meta/work_in_progress/` trừ khi ghi khác. Mục nêu "chưa làm" ghi rõ lý do. Mã nằm trên `origin/main`: commit `6274591` và commit ngay sau đó, tiêu đề bắt đầu bằng "Review 20/11 item A.7".

## 1. Trạng thái từng mục

| Mục | Trạng thái | Vị trí / ghi chú |
|---|---|---|
| A.1 Nhận gói bàn giao | Xong | `metamodel_handoff_2026-11-20b.zip`, sha256 `0930ec2e…64a8` khớp tệp `.sha256`. 38 test `metamodel` và 36 test `tempo_fix` đạt; `metamodel.__version__` = `0.2.6 (2026-11-20)`; `REGISTRY_REVISION` = `registries_rev_2026-11-20b`; sha256 `registry_manifest.json` = `45e78aba…d364`. |
| A.2 Lắp lại release | Xong | `meta_release_CQ_LO_full_F1F2F3_seeds42_43_44_20261120_mm026` (mục 2). Hai release con giữ riêng: `meta_release_CQ_LO_full_F1F2F3_seeds42_43_44_20261120_mm026_child_releases/{CQ_3seed,LO_3seed}` (không kèm bản CSV). |
| A.3 Sáu cấu hình trên một release | Xong | Mục 3. |
| A.4 Đóng gói | Xong, chờ phía viết kiểm | `mm_runs_CQ_LO_full_F1F2F3_seeds42_43_44_20261120_mm026` (146 file, sha256 kiểm khớp trên Drive). README ghi nhãn "biến thể độ vững của Bảng 42". Chưa chuyển vào `accepted/` (chờ kiểm). Thư mục `…_20261119` giữ nguyên. |
| A.5 Bộ chạy trên host | Ghi nhận | Bộ lưu ở `mm_runs_CQ_LO_full_F1F2F3_seeds42_43_44_20261119/host17429_one_thread`; báo cáo này dùng bộ PC. `pip freeze` của bộ đó không còn: máy đã bị xóa mà chưa lưu. Phiên bản Python của bộ đó có trong `m15_progress_17429.log`. |
| A.6 Dòng `rc=127` | Đã giải thích | Mục 4. |
| A.7 Commit file còn thiếu | Xong | Mục 5. |
| A.8 Ledger M-08 | Đã đối chiếu | Mục 6. |
| A.9 Archive cắt hoặc không đọc được | Một phần | Mục 7. |
| A.10 NVML | Một phần | Mục 8. |
| B.0 Ba xác nhận | Đã trả lời | Mục 9. |
| B.1 Cờ seen/unseen | Xong; một mục chưa làm | Cờ và bảng hỗ trợ xong; bảng đối chiếu 48 dòng với `audit_prediction_course_cohort.py` **chưa làm** (mục 10). |
| B.2 Facts bốn subgroup | Đã chạy thử một đơn vị, đạt | CQ RNN seed 42; 35 đơn vị còn lại chờ phía viết xác nhận (mục 10). |
| B.3 S0 v5, F0 | Chưa làm | Làm sau khi phía viết xác nhận hợp đồng ở B.2. |
| B.4 Release năm subgroup | Chưa làm | Cần B.2 đủ 36 đơn vị và B.3. |
| B.5 Kiểm lặp lại trên lát ALL | Chưa làm | Cần B.4. |
| B.6 Đóng gói, commit ba builder | Một phần | Ba builder đã commit (commit "Review 20/11 item A.7"); gói theo B.6 làm cùng B.2 đủ 36 đơn vị. |
| Pha C | Không làm | Khai báo lần chạy thăm dò E1 theo từng task ở mục 11. |

## 2. A.2 — release `…_20261120_mm026`

- Lắp bằng `metamodel.cli assemble` 0.2.6 cho cả CQ và LO từ đúng 70 đầu vào và các khóa của bản 20261120, `--planned-seeds 42 43 44`, `--registry tempo_fix/examples/registries_v1.6`; không dùng `--accept-energy-estimates` ở bước lắp. Manifest ghi `metamodel 0.2.6 (2026-11-20)` và `registries_rev_2026-11-20b`.
- Kèm trong release: `run_assemble_3seed.sh`, `RUN_LOG.md`, `pip_freeze.txt`, `platform.txt`, `sha256sums.txt`.
- Nghiệm thu so với bản 20261120 (cùng số dòng: bảng mức seed 14 688, bảng gộp seed 4 896):

| Bảng | Cột chung | Trùng tuyệt đối | Trùng trong 1e-9 | Khác | Cột mới |
|---|---|---|---|---|---|
| Mức seed | 557 | 555 | 0 | 2 (`meta_release_id`, `builder_version`) | 1 (`rec_energy_measured_types`) |
| Gộp seed | 1 790 | 1 788 | 0 | 2 (cùng hai cột) | 7 (`n_eval_samples`, `ev_n_classes_present`, `small_subgroup_flag`, `rec_energy_measured_types`, `energy_ratio_n_seeds`, `energy_measurement_types`, `rec_energy_measured_types_agg`) |

- Cột năng lượng: bản vá cục bộ của 20261120 và cách tính theo từng dòng của 0.2.6 cho **cùng giá trị trên mọi dòng** (các cột `energy_gpu_run_kwh_*` nằm trong số cột trùng tuyệt đối), nên không có dòng nào cần liệt kê theo task × mô hình × seed. Bản vá được lưu ở `tools/m15_3seed/assemble_energy_fix_20261120.patch`.

## 3. A.3 — sáu cấu hình trên một release

Cả sáu cấu hình chạy trên release ở mục 2 bằng metamodel 0.2.6, cùng cờ và cùng cách giới hạn một luồng như lần 20/11; `sens_energy` là `run --accept-energy-estimates` trên chính release đó.

| Cấu hình | Dòng registry | Trạng thái | Phương án dự phòng | MQ08 đạt (fold) | Thời gian (giờ) |
|---|---|---|---|---|---|
| `main_cal_time` | 238 | OK 238 | không | 5/7 | 2,35 |
| `sens_v1` | 238 | OK 238 | không | 4/7 | 2,51 |
| `sens_energy` | 238 | OK 238 | không | 5/7 | 2,35 |
| `sens_conservative` | 238 | OK 238 | không | 3/7 | 2,48 |
| `obj_perf` | 238 | OK 231, SKIPPED 7 (thiếu thành phần phân rã) | không | 7/7 | 2,28 |
| `obj_macrof1` | 238 | OK 231, SKIPPED 7 (thiếu thành phần phân rã) | không | 6/7 | 2,46 |

- **Năm cấu hình không dùng năng lượng** (`main_cal_time`, `sens_v1`, `sens_conservative`, `obj_perf`, `obj_macrof1`): `compare_mm_dirs_r30b.py` với bộ `pc_one_thread` hiện có cho **8 bảng so, different: 0**; `mm_cost_basis` chỉ có ở bộ mới.
- **`sens_energy`**: 3 bảng khác bộ cũ (`mm_hypotheses`, `mm_metrics`, `mm_recommendations`, ở cột chi phí và Pareto). So với `main_cal_time`: 170/238 dòng `mm_metrics` khác, danh sách pipeline được khuyến nghị giống ở 6 528/6 528 dòng.
- **`mm_cost_basis` của `sens_energy`** (số nhóm theo task × mô hình × cơ sở): CQ cả sáu mô hình TIME (12 nhóm mỗi mô hình); LO ENERGY ở BILSTM, GRU, LSTM, RNN (12 nhóm mỗi mô hình) và MANTIS_V2 (8 nhóm); LO TIME ở PATCHTST (12 nhóm) và MANTIS_V2 (4 nhóm).
- Không chạy E1 theo từng task ở pha này (nhưng xem mục 11).

## 4. A.6 — dòng `rc=127`

`pc_one_thread/m15_progress.log` có hai lần chạy `sens_energy_rel20261120`: lần 1 bắt đầu 11:34:55 ngày 20/11, được dừng theo quyết định của người vận hành ở khoảng 60% tiến độ, dòng `END … rc=127` là của lần này; lần 2 bắt đầu 13:37:28 và kết thúc `rc=0`. Các file trong thư mục `sens_energy/` do lần 2 tạo ra. Nguồn chính xác của mã 127 chưa xác định: nhiều khả năng do script bao quanh ghi mã thoát sau khi tiến trình bị dừng. Bản `pc_one_thread/sens_energy` lúc đó dùng kết quả chạy trên release 20261119; bộ mới ở mục 3 thay thế nó.

## 5. A.7 — commit file còn thiếu (commit "Review 20/11 item A.7" trên `origin/main`)

1. `tools/seed43_44_pipeline/phaseB_orch.py` (đường dẫn máy thay bằng biến môi trường như các script khác).
2. `cq44_mantis_parent.sh`, `cq44_mantis_child.sh`.
3. `tools/m15_3seed/report_aggregate_3seed.py`, `report_write_3seed.py`, `md_to_docx_m4.js`.
4. `tools/m15_3seed/run_assemble_3seed.sh`.
5. Bản vá `assemble.py` của 20261120: `tools/m15_3seed/assemble_energy_fix_20261120.patch`.
6. Script chạy M-15 ba seed (`run_local_all_1t.sh`, `m15_run_logged.py`, `run_six_mm026.sh`, `run_e1_per_task.sh`) và bản vá `n_jobs=1` của phiên khác (`n_jobs1_patch_other_session.patch`).
7. `tools/seed43_44_pipeline/build_energy_proposal_seed44.py`: đã viết lại theo mô tả phương pháp của thư mục `energy_proposal_seed44_20261119` (công suất trung vị của các ô đã đo cùng họ, và cùng GPU với PatchTST, nhân thời gian chạy; khoảng p5–p95 của công suất). Chạy trên dữ liệu seed 44 cho đúng 8 ô, `elapsed_seconds` và công suất cơ sở giống hệt bản đã giao; `proposed_kwh` và hai cột khoảng lệch tối đa 0,001 kWh (làm tròn chữ số cuối), nên script tái tạo gần đúng chứ chưa trùng từng chữ số. Script gốc không còn bản lưu.
8. `tools/seed43_44_pipeline/m44_stream_repair.py`, `m44_build_m18_repair.py`.

Cũng commit: `tools/m15_3seed/scan_release_ids.py`, `verify_err_tars.py`, ba builder pha B và hai script quét danh mục (`tools/subgroups_phaseB/`), `tools/combine_meta_release_3seed_mm026.py`.

## 6. A.8 — ledger M-08: một xác nhận

Quét 899 tar kết quả CQ và LO trên `CQ|LO/L1_runs/S3_model`, đọc `data_release_id` của từng `run_manifest` và manifest audit:

| Task | Nhóm | Manifest có mã | `CURRENT` | Mã khác (`OTHER_RELEASE`) | Không có trường mã |
|---|---|---|---|---|---|
| CQ | ngoài `historical` | 749 | 749 | 0 | 0 |
| LO | ngoài `historical` | 968 | 968 | 0 | 0 |
| LO | `historical/preserved_packages_20261029` (run cũ, seed 42) | 62 | 62 | 0 | 473 (run cũ, schema cũ) |

**Xác nhận:** trong 1 717 manifest ngoài `historical`, 1 717 có `data_release_id` bằng định danh `CURRENT` của ledger tương ứng (CQ `sha256:8db2b1d3…`, LO `sha256:2edf8cc2…`); không có manifest nào thuộc lớp `OTHER_RELEASE`. 473 manifest không có trường mã đều thuộc **run cũ**: F1 LO seed 42 của đợt chạy đầu (tháng 10/2026), lưu trong `historical/preserved_packages_20261029`; manifest của các run đó theo schema cũ nên chưa có trường `data_release_id`. Mọi manifest của run mới (seed 43, seed 44 và các gói PatchTST, Mantis ngoài `historical`) đều có trường mã và đều là `CURRENT`. Với run cũ, các manifest ghi `input_paths` chứa `LO_V3_1` (tên release trùng ledger) nhưng không có băm, nên xác nhận bằng mã không áp dụng cho chúng. Phạm vi của xác nhận: mức manifest; chưa nối từng ô trong gói facts với manifest tương ứng.

## 7. A.9 — archive cắt hoặc không đọc được

Đọc hết 899 tar bằng cách tải toàn bộ và so md5 với Drive; chỉ hai tar bị cắt (md5 trùng giá trị đã ghi lúc tải lên, nhưng nội dung dừng giữa chừng):

| Tar | Nội dung còn lại | Bản đầy đủ |
|---|---|---|
| `staging_incoming/patchtst_seed44_20261117/lo_patchtst_seed44_V2_host40077.tar` (LO PatchTST seed 44) | W1 V2 đủ 14/14 file; W2 V2 chỉ 10/14 (thiếu `validation_P3/P4`, `run_manifest.json`, `train_history`) | W2 V2 đủ ở `patchtst_lo_seed44_auto_host37835_1cells_202611190242.tar`; W3 V2 đủ ở `patchtst_lo_seed44_auto_host40106_1cells_202611190136.tar`. Các file chung của W2: `model.pt` và `feature_layout.json` trùng từng byte; `metrics_overall`, `test_P1`, `test_P4`, `validation_P1` trùng giá trị. |
| `staging_incoming/lo_static_v2_seed42_20261026/LO_static_v2_BILSTM.tar` (LO BILSTM seed 42) | 30/51 ô | `LO_static_v2_BILSTM_full_20261107.tar` đủ 51 ô (trong `historical/preserved_packages_20261029`); 122 file chung (`model.pt`, `train_history`, `metrics_overall`, `run_manifest`) trùng sha256. |

Không ô nào chỉ còn trong tar cắt. **Chưa làm:** đối chiếu từng ô của sáu gói facts seed 44 với archive đã dùng để dựng M-18 (hai script `_repair` nay đã commit). Việc này không đổi kết luận trên, vì cả hai archive cắt đều có bản đủ.

## 8. A.10 — NVML

Tám run CQ seed 44 thiếu năng lượng (PatchTST W1/V5, W1/V16, W2/V7, W2/V12, W2/V16, W3/V0, W3/V12; Mantis W2/V0) giữ rỗng, không ghi đề xuất vào gói (Q-38 (a)). **(a) Nguyên nhân chưa xác định:** nguồn chỉ ghi `ENERGY_NOT_MEASURED`; không còn host/image để kiểm lại. **(b)** Với mọi lần chạy lưới sau, đội code sẽ thử lấy mẫu công suất trên từng host trước khi cấp lưới; chưa có lần chạy nào mới nên chưa áp dụng.

## 9. B.0 — ba xác nhận

1. **Dự đoán cấp mẫu còn đọc được không.** Có đủ 8 file (`validation|test` × `P1..P4`, kích thước lớn hơn 0) cho **1 836/1 836 run**. Một phần nằm trong tar (1 626 run), một phần là **file rời** nên không có trong các lần quét tar: CQ F1 seed 42 (204 run) ở `CQ/L1_runs/S3_model/historical/preserved_packages_20261029/{cq_recurrent_batch2048_seed42_20261019 (BILSTM, GRU), cq_lstm_batch2048_full_20261018 (LSTM), cq_rnn_historical_layout_batch2048_seed42_20261020 (RNN)}`; CQ Mantis seed 42 (51 run, kể cả V0) ở `mantis_v2_seed42_exploratory_20261108`; LO PatchTST seed 42 V0 (3 run). Mới kiểm danh sách file và kích thước; việc mở file sẽ diễn ra trong lúc chạy B.2.
2. **Khóa enrollment nối được về `user_id`, `course_id`, `offering_id`.** Có, cho cả hai task, ba window và hai split. Dự đoán mang `enrollment_id_hash` = sha256(`salt|enrollment_id`); dữ liệu đầu vào có `enrollment_id` dạng rõ cùng `user_id`, `course_id`, `offering_id`. Mỗi họ run có salt riêng. Đã xác minh khớp 100%: CQ F1 seed 42 (178 095/178 095 ở W1 TEST P1) và LO PatchTST seed 44 (200 844/200 844). Các họ còn lại được xác minh ở lúc chạy; nếu họ nào không khớp thì dừng và báo.
3. **Mốc cutoff.** Lấy từ cột `cutoff_time_P1..P4` của các phase view (`raw_views_20261108`). `offering_end_date` suy ra bằng `enroll_time + (cutoff_P4 − enroll_time)/0,90`, với `enroll_time` là phần thứ ba của `enrollment_id`; ngày kết thúc suy từ P1, P2, P3 trùng trong 3 giây; 1/3 309 offering CQ và 1/2 169 offering LO có độ lệch ngày kết thúc trên 60 giây. Công thức cutoff của phase view trùng `tempo_fix/seen_flags.py` trong sai số trên.

**Ước lượng công.** B.1 xong. B.2: mỗi đơn vị khoảng 8 phút tính cộng tải dự đoán (khoảng 5 GB), 35 đơn vị còn lại khoảng 4–6 giờ. B.3 đến B.5: chưa ước lượng, phụ thuộc hợp đồng được xác nhận.

## 10. B.1 và B.2 — kết quả

- **Cờ seen/unseen** (`seen_v1_train_partition_only`, `tempo_fix/seen_flags.py`): xong cho CQ (4,30 triệu dòng) và LO (3,27 triệu dòng); QA15: `seen_offering` = 0 trên mọi dòng VALIDATION và TEST.
- **`subgroup_slice_support.csv`:** 240 dòng, tất cả `OK` (không có lát rỗng hay một lớp); `small_subgroup_flag` đúng ở 38 dòng.
- **Đơn vị chạy thử CQ RNN seed 42** (`subgroups_pilot_CQ_RNN_seed42_20261121`): 1 632 dòng, tất cả `OK`; dòng ALL tính lại trên mọi (run, split, pha) khớp facts đã nghiệm thu (lệch tối đa 1,1e-16); SEEN + UNSEEN = ALL ở cả hai trục (0 lỗi); `s_eff`, `s_leak` kế thừa từ dòng ALL; gói facts đã nghiệm thu không bị sửa.
- **Chưa làm:** bảng đối chiếu 48 dòng (task × window × split × pha) giữa cờ `seen_course` theo quy tắc trên và cờ SEEN_COURSE của `audit_prediction_course_cohort.py`; cần salt/nối `course_id` theo hai định nghĩa. Sẽ làm cùng lượt 35 đơn vị còn lại.
- Xin phía viết kiểm hợp đồng bằng `assemble --require-subgroups` trên thư mục chạy thử; xác nhận xong thì đội code chạy 35 đơn vị còn lại.

## 11. Khai báo về pha C: lần chạy thăm dò E1 theo từng task

E1 theo từng task đã được chạy thăm dò trước khi đội code đọc bản 2 (mục 5 của bản 2 yêu cầu không chạy trước khi nhận bản gói kế tiếp). Cách chạy: bảng gộp seed của release 20261120 (không phải `_mm026`) được lọc theo task (`CQ` hoặc `LO`, mỗi bảng 2 448 dòng) rồi chạy `metamodel.cli run` 0.2.4 không đổi, chỉ với E1-A (W1→W2) và E1-B (W1W2→W3), cùng learner, mục tiêu, cờ, 50 lần thử Optuna và 5 hạt giống learner như M-15; mỗi tiến trình một luồng. Vì bảng chỉ còn một task, mỗi fold chỉ chứa task đó. Không chạy E2, E3, không đổi tham số nào đã đăng ký.

| Cấu hình | CQ: dòng registry (OK / SKIPPED) | CQ: MQ08 đạt | LO: dòng registry (OK / SKIPPED) | LO: MQ08 đạt | Thời gian mỗi lần chạy (giờ) |
|---|---|---|---|---|---|
| `main_cal_time` | 68 (68 / 0) | 2/2 | 68 (68 / 0) | 0/2 | 0,41 |
| `sens_v1` | 68 (68 / 0) | 1/2 | 68 (68 / 0) | 2/2 | 0,40–0,41 |
| `sens_energy` | 68 (68 / 0) | 2/2 | 68 (68 / 0) | 0/2 | 0,41 |
| `sens_conservative` | 68 (68 / 0) | 1/2 | 68 (68 / 0) | 0/2 | 0,41 |
| `obj_perf` | 68 (66 / 2) | 0/2 | 68 (66 / 2) | 0/2 | 0,38–0,39 |
| `obj_macrof1` | 68 (66 / 2) | 0/2 | 68 (66 / 2) | 1/2 | 0,38–0,39 |

12 lần chạy đều kết thúc mã thoát 0, không dùng phương án dự phòng. Các dòng SKIPPED của `obj_perf` và `obj_macrof1` có cùng lý do như bản gộp (thiếu thành phần phân rã khi mục tiêu không phải M3). Bộ ở `mm_runs_CQ_LO_full_F1F2F3_seeds42_43_44_20261119/e1_per_task_20261120` (254 file, kiểm khớp trên Drive, kèm `README.txt`).

Kết quả hối tiếc và giả thuyết **không được đưa vào phản hồi này**, để giữ phép so của C2 chưa bị chạm; chúng nằm trong các tệp `mm_*` của bộ trên. Các kết quả đó đã được đội code **đọc** (so hối tiếc CQ và LO với bản gộp). Đội code đề nghị coi bộ này là thăm dò, không dùng cho kết luận về C2, và sẽ chuyển sang thư mục có nhãn nếu phía viết yêu cầu. Từ nay không chạy E1 theo từng task hay huấn luyện năm subgroup cho tới khi nhận bản gói kế tiếp.

## 12. Cần phía viết

1. Kiểm gói chạy thử CQ RNN seed 42 (mục 10) và xác nhận hợp đồng dữ liệu.
2. Kiểm release `…_mm026` và gói `mm_runs_…_mm026` để chuyển vào `accepted/` (A.2, A.4).
3. Cho biết có chuyển bộ E1 theo từng task sang thư mục có nhãn thăm dò không (mục 11).
