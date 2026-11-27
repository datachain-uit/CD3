"""Build qa_outcomes_release_r2_v3 (B2'): v2 table + extended QA11/QA13 coverage (Mantis link extension), QA14 results on the views, QA21 all five parts, QA23 LO review table.
usage: build_qa_v3.py <work_root> <v2_dir> <out_dir> <code_commit>"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

import pandas as pd

W, V2, OUT, COMMIT = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
OUT.mkdir(parents=True, exist_ok=True)
shutil.copytree(V2 / 'evidence', OUT / 'evidence', dirs_exist_ok=True)
EV = OUT / 'evidence'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# new evidence
for src, name in ((W / 'qa5m/qa5_mantis_link_extension_v2.csv', 'qa5m_link_extension_v2.csv'), (W / 'qa5m/qa5_mantis_link_summary_by_unit.csv', 'qa5m_link_summary_by_unit.csv'),
                  (W / 'qa14/qa14_results.csv', 'qa14_results.csv'), (W / 'qa14/qa14_test_definitions.md', 'qa14_test_definitions.md'),
                  (W / 'qa21/qa21_status_by_part.csv', 'qa21_status_by_part.csv'), (W / 'qa21/qa21_c_summary_by_task.csv', 'qa21_c_summary_by_task.csv'),
                  (W / 'qa21/qa21_c_imputer_predictors_by_state.csv', 'qa21_c_imputer_predictors_by_state.csv'), (W / 'qa21/qa21_a_key_overlap_by_window.csv', 'qa21_a_key_overlap_by_window.csv'),
                  (W / 'qa21/qa21_b_train_label_end_vs_tau.csv', 'qa21_b_train_label_end_vs_tau.csv'),
                  (W / 'qa21/qa23_lo_review_candidates.csv', 'qa23_lo_review_candidates.csv'), (W / 'qa21/qa23_lo_review_candidates_by_slice.csv', 'qa23_lo_review_candidates_by_slice.csv'),
                  (W / 'b2v3/qa23_decision_support.csv', 'qa23_decision_support.csv')):
    shutil.copy2(src, EV / name)
v = pd.read_csv(V2 / 'qa_outcomes_release_r2.csv')
U = pd.read_csv(EV / 'qa5_units_summary_36.csv')
today = '2026-11-27'


def put(cid, status, unit, n, npass, nfail, ev, note):
    i = v.index[v.check_id == cid][0]
    v.loc[i, ['status', 'unit', 'n_units_checked', 'n_pass', 'n_fail', 'evidence_file', 'evidence_sha256', 'run_date', 'note']] = [status, unit, n, npass, nfail, ev, sha(OUT / ev), today, note]


S = pd.read_csv(EV / 'qa5m_link_summary_by_unit.csv')
T = S[S.unit == 'TOTAL'].iloc[0]
assert int(T.linked_after) == 1836 and int(T.qa11_runs_nonzero_after) == 0
put('QA11', 'PASS', 'run (liên kết với manifest S1)', 1836, 1836, 0, 'evidence/qa5m_link_summary_by_unit.csv',
    'Không có cột `n_cells_imputed_in_unavailable`; trường tương đương là `future_imputed_cells` của manifest S1 (6 split), một thuộc tính của trạng thái imputation, dùng chung cho mọi mô hình và seed. Phủ 1.836/1.836 run, tổng ô tương lai bị điền = 0, không run nào khác 0. '
    'Cách liên kết: 1.656 run qua trường `model_parent_pipeline` của manifest; 180 run Mantis cân bằng qua manifest S2 (hash cha S2 = hash chuẩn hóa của manifest S1 cha, kiểm cho cả 180), bước run mô hình sang S2 là ánh xạ: 108 run seed 42 và 43 theo khóa (task, window, pipeline, seed), đối chiếu độc lập với trường `parent` khai báo trong manifest của run (108/108 khớp); 72 run seed 44 qua download manifest (gói B4′), trường `parent` của chúng bằng `parent_pipeline` của S2 ở 72/72. Nguyên nhân của khoảng hở ở bản 2: công cụ QA đọc khóa `parent_pipeline` còn manifest Mantis ghi `parent`.')
put('QA13', 'NOT_RUN', 'run', 1836, 0, 0, 'evidence/qa5m_link_summary_by_unit.csv',
    '`checkpoint_sha256` và `preprocessor_sha256` không có trong manifest của run nào (0/1.836). Bằng chứng cấu trúc, không đủ để ghi PASS: giao thức `shared_checkpoint_prefix_safe_v2_4` (một checkpoint cho P1–P4) và `preprocessor_sha256` của manifest S1 ở 1.836/1.836 run (bản 3: sau khi nối thêm 180 run Mantis). Có thể tính sha256 từ `model.pt` nếu tải lại các tar của họ recurrent, nhưng đó không phải trường đã ghi lúc chạy.')
put('QA14', 'NOT_RUN', 'sanity test', 6, 0, 0, 'evidence/qa14_results.csv',
    'Sáu test định nghĩa duy nhất trong tài liệu kịch bản (AGENT_READY_EXPERIMENT_REEXECUTION_GUIDE.md, §3.5). Không có kết quả của chúng gắn với release; `tempo_fix/sanity.py` là mã của metric S_san+, không phải các test này. Chạy trên view cục bộ (10 file khớp MD5 với Drive): label identity PASS (CQ, LO), split identity PASS (CQ, LO), cardinality PASS (CQ, LO). Ba test còn lại chỉ có mức proxy: prefix nesting (proxy: 16 cột đếm tích lũy không giảm, nhưng `score_sum` giảm ở 382 cặp CQ và 394 cặp LO, tức PROXY_FAIL chưa giải thích; có thể do điểm âm của lần nộp sau), future perturbation (proxy: view P1 không mang gì từ P2..P4), cutoff equality (proxy: cutoff khớp giữa các view test). Cần để đóng: log `conformance_checks` của phase builder gắn sha256 với view, hoặc sự kiện thô để chạy lại builder. Theo quy tắc, giữ NOT_RUN.')
put('QA21', 'FAIL', 'điều kiện của kiểm (5 điều)', 5, 4, 1, 'evidence/qa21_status_by_part.csv',
    'Cả năm điều được chạy trên bằng chứng của release. (1) Không trùng khóa giữa các phân vùng: PASS (khóa đăng ký là `offering_id`, kèm `enrollment_id`; 36 phép giao bằng 0 trên phase view; VALIDATION–TEST 7.344 cặp dự đoán, 0 trùng). (2) Không nhãn TRAIN sau mốc cắt trừ khoảng đệm: PASS theo cách đọc nghĩa đen (đệm đăng ký 0 ngày, train_cutoff = tau_w; 0 enrollment TRAIN kết thúc sau tau_w ở 6/6 task × window; registry chỉ có ngày kết thúc mức offering nên không chứng minh được thời điểm nhãn có sẵn trong hệ nguồn; cách đọc chặt theo từng dòng không đạt theo thiết kế ở các dòng OVERLAP). (3) Bộ tiền xử lý chỉ fit trên TRAIN: PASS 1.836/1.836. (4) Không điền ô tương lai: PASS 1.836/1.836. '
    '(5) Imputer không dùng đặc trưng proxy nhãn: danh sách `imputer_predictors` đọc từ `fitted_pipeline.joblib` của 12 trạng thái S1 có predictor (V9 ExtraTrees và V13 MICE; sha256 file = `preprocessor_sha256` của manifest ở 12/12; đọc bằng bộ giải pickle thay lớp bằng stub, không chạy mã trong file). Theo quy tắc biến thể pha của hợp đồng (bỏ hậu tố `_P1.._P4`): FAIL ở 6/6 trạng thái của mỗi task (LO: `video_catalog_coverage`, `problem_catalog_coverage`, `problem_score_catalog_coverage`; CQ: thêm `commented_resource_catalog_coverage`, và sau khi miễn trừ tám cơ sở theo quyết định 21 vẫn còn `commented_resource_catalog_coverage` và `video_catalog_coverage`). Theo cách khớp tên chính xác trên cột có hậu tố (cách mã đã áp dụng) thì không có proxy. Trạng thái FAIL là đề xuất của đội code theo cách đọc quy tắc đã đăng ký; tác giả quyết cách đọc.')
i = v.index[v.check_id == 'QA23'][0]
v.loc[i, 'note'] = str(v.loc[i, 'note']) + (' Bản 3: bảng `qa23_lo_review_candidates.csv` (15 cơ sở LO: 10 trong 11 cơ sở ngoài nhóm điểm hiện tại là hành vi tiền tố không phải thành phần nhãn, `unique_video_count` là phiên bản tiền tố của thành phần nhãn; các cơ sở điểm trong nhóm là phiên bản mức lần nộp của điểm) và `qa23_decision_support.csv` (CQ 8/12 lát, 12/12 nếu có ngưỡng cỡ mẫu 1.000; LO 0/12 trong mọi trường hợp). Trạng thái không đổi: FAIL.')
v.loc[i, 'evidence_file'] = 'evidence/qa23_detail_columns.csv'
v['code_commit'] = COMMIT
v.to_csv(OUT / 'qa_outcomes_release_r2.csv', index=False, lineterminator='\n')
print(v[['check_id', 'status', 'n_units_checked', 'n_pass', 'n_fail']].to_string(index=False))
print(v.status.value_counts().to_dict())
