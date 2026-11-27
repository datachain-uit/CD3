"""Build qa_outcomes_release_r2_v4 (B2'): v3 table + QA13 on the checkpoint files (1,836 / 1,836 runs) + QA14 note with the whole-Drive scan.
usage: build_qa_v4.py <work_root> <v3_dir> <out_dir> <code_commit>"""
import hashlib
import shutil
import sys
from pathlib import Path

import pandas as pd

W, V3, OUT, COMMIT = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
OUT.mkdir(parents=True, exist_ok=True)
shutil.copytree(V3 / 'evidence', OUT / 'evidence', dirs_exist_ok=True)
EV = OUT / 'evidence'
for src, name in ((W / 'qa13/qa13_checkpoint_coverage_by_run.csv', 'qa13_checkpoint_coverage_by_run.csv'), (W / 'qa13/qa13_coverage_summary_by_unit.csv', 'qa13_coverage_summary_by_unit.csv'),
                  (W / 'qa13/README_qa13.md', 'README_qa13.md')):
    shutil.copy2(src, EV / name)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


v = pd.read_csv(V3 / 'qa_outcomes_release_r2.csv')
c = pd.read_csv(EV / 'qa13_checkpoint_coverage_by_run.csv')
assert len(c) == 1836 and (c.n_checkpoint_files == 1).all() and c.hash_value.astype(str).str.fullmatch(r'[0-9a-f]{64}').all() and not c.hash_value.duplicated().any()
n_model = int((c.checkpoint_name.str.endswith('model.pt')).sum() - c.checkpoint_name.str.contains('probe_head').sum())
n_probe = int(c.checkpoint_name.str.contains('probe_head').sum())
n_sib = int(c.package_kind.astype(str).str.contains('SIBLING', case=False).sum()) if 'package_kind' in c else 0
src = c.hash_kind.value_counts().to_dict()
i = v.index[v.check_id == 'QA13'][0]
v.loc[i, ['status', 'unit', 'n_units_checked', 'n_pass', 'n_fail', 'evidence_file', 'evidence_sha256', 'run_date']] = ['PASS', 'run (một checkpoint cho P1–P4)', 1836, 1836, 0, 'evidence/qa13_checkpoint_coverage_by_run.csv', sha(EV / 'qa13_checkpoint_coverage_by_run.csv'), '2026-11-28']
v.loc[i, 'note'] = (
    'PASS ở mức bằng chứng FILE, không phải từ trường manifest (manifest không có `checkpoint_sha256` và `preprocessor_sha256` ở run nào: 0/1.836). '
    f'Mỗi run trong 1.836 run có đúng một file checkpoint với sha256 đầy đủ 64 ký tự (1.530 run `model.pt`: RNN, LSTM, GRU, BILSTM, PATCHTST; 306 run Mantis `probe_head.pt`); không run nào có 0 hoặc nhiều hơn một checkpoint, không hash nào trùng giữa hai run, 1.098 tiền tố 12 ký tự của lượt QA đầu khớp hash đầy đủ. '
    f'Nguồn hash: {src.get("sha256_drive_listing", 0)} run từ danh sách Drive (file rời), {src.get("sha256_tar_stream", 0)} run từ băm thành viên tar khi đọc luồng. Tám file dự đoán của mỗi run lấy từ đúng một gói; 69 run có checkpoint ở gói anh em cùng release (LO BILSTM seed 42: 51 run, CQ PATCHTST seed 42: 18 run; chỉ một ứng viên và kích thước tám file dự đoán bằng nhau, đây là khớp kích thước không phải khớp hash của dự đoán); 209 run có bản giống hệt ở gói khác cùng hạng, cùng hash; gói hạng thấp hơn (pilot, replay, ablation) có `model.pt` khác hash nhưng không phải nguồn của dự đoán đã nghiệm thu. '
    'Bộ tiền xử lý: không có file trong thư mục run; hash là `preprocessor_sha256` của manifest S1, một giá trị duy nhất cho mỗi (task, window, pipeline) (102 tổ hợp), nên P1–P4 trùng theo cấu trúc; 180 run Mantis lấy giá trị S1 của cùng tổ hợp ở đơn vị khác (cột `s1_preprocessor_source`). '
    'Giới hạn: các file cho thấy một checkpoint mỗi run đi cùng dự đoán P1–P4 (giao thức `shared_checkpoint_prefix_safe_v2_4`, một `best_epoch`) nhưng không chứng minh dự đoán được suy ra từ chính file đó (cần chạy lại suy luận); với Mantis, coi `probe_head.pt` cùng `backbone_pin.json` (backbone đóng băng, không lưu theo run) là checkpoint là đề xuất của đội code. Hai tar Drive bị cụt (`LO_static_v2_BILSTM.tar`, `lo_patchtst_seed44_V2_host40077.tar`) đọc lại cho cùng kết quả; không run nào phụ thuộc phần thiếu. '
    'Nếu tác giả hiểu QA13 là "trường có trong manifest" thì không đạt (0/1.836) và cần quyết định của tác giả.')
j = v.index[v.check_id == 'QA14'][0]
v.loc[j, 'note'] = str(v.loc[j, 'note']) + (' Bản 4: đã quét toàn bộ Drive (35.368 file, 27/11/2026) tìm log của sáu test: không có file nào tên `conformance`, `phase_builder` hay `perturb`; bằng chứng gần nhất không phải sáu test: bảng phân phối nhãn `phase_views_v2_2_audit` (CQ), bảng `materialization_lineage` của CQ và LO (số dòng, 0 dòng trùng bị loại, hash danh sách file nguồn), và các gói kiểm tiền tố (`lo_prefix_audit_evidence_20261108`, `rnn_prefix_audit_20261017`). Phần còn thiếu của QA14 không bổ sung được từ Drive; cần log `conformance_checks` của phase builder (kèm sha256 gắn với view) hoặc sự kiện thô.')
v['code_commit'] = COMMIT
v.to_csv(OUT / 'qa_outcomes_release_r2.csv', index=False, lineterminator='\n')
print(v[['check_id', 'status', 'n_units_checked', 'n_pass', 'n_fail']].to_string(index=False))
print(v.status.value_counts().to_dict())
