"""Build qa_outcomes_release_r2_v5 (B2'): v4 table + QA14 note with the Databricks audit tables (phase_builder_audit, cumulative v2 audit, exclusion_log summary).
usage: build_qa_v5.py <work_root> <v4_dir> <out_dir> <code_commit>"""
import hashlib
import shutil
import sys
from pathlib import Path

import pandas as pd

W, V4, OUT, COMMIT = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
OUT.mkdir(parents=True, exist_ok=True)
shutil.copytree(V4 / 'evidence', OUT / 'evidence', dirs_exist_ok=True)
EV = OUT / 'evidence'
for name in ('phase_builder_audit_hybrid.csv', 'cumulative_phase_features_v2_audit_hybrid.csv', 'exclusion_log_summary_by_reason.csv'):
    shutil.copy2(W / 'qa14c/pkg' / name, EV / name)
shutil.copy2(W / 'qa14c/pkg/README.md', EV / 'README_databricks_audit_tables.md')
shutil.copy2(W / 'qa14/qa14_code_derived_argument.md', EV / 'qa14_code_derived_argument.md')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


v = pd.read_csv(V4 / 'qa_outcomes_release_r2.csv')
a = pd.read_csv(EV / 'phase_builder_audit_hybrid.csv')
g = a.groupby(['temporal_block', 'timeline_source']).enrollment_count.nunique()
assert len(a) == 72 and int((g == 1).sum()) == 18 and int(a[a.phase == 'P1'].enrollment_count.sum()) == 11807090
j = v.index[v.check_id == 'QA14'][0]
base = str(v.loc[j, 'note'])
cut = base.index(' Bản 4:')
v.loc[j, 'note'] = base[:cut] + (
    ' Bản 5: (a) đã quét toàn bộ Drive (35.368 file, 27/11/2026): không có log của sáu test. (b) Đã lấy từ Databricks Volume (`features/scenarios/hybrid/`) ba thư mục kiểm: `phase_builder_audit` (72 dòng; cả 18 nhóm block × nguồn timeline có cùng số enrollment ở P1..P4; tổng 11.807.090), `cumulative_phase_features_v2_audit` (11.807.090 dòng trước và sau khi loại trùng, 0 bản trùng, `generated_at_utc` 2026-10-05 09:02:23 UTC, tức 16:02 giờ +07) và `exclusion_log` (38.731.106 bản trùng chính xác bị loại; chỉ giữ bản tổng hợp, bản gốc chứa mã người học); tổng enrollment bằng số dòng bảng `features` của `materialization_lineage` (11.807.090). (c) Bảng `phase_builder_audit/conformance_checks/` (bốn kiểm: cardinality và cutoff equality của video, bài tập, bình luận) không còn trên Volume: không có thư mục con (đội code xác nhận); các tệp `_committed` cho thấy `phase_builder_audit` đã bị ghi đè ít nhất bốn lần, nhiều khả năng ghi đè thư mục cha đã xóa nó. (d) Mốc mã: phase builder `609751a` (03/10/2026 18:32, không đổi về sau), bước cộng dồn `bb9711c` (05/10 15:39, chạy 16:02), view dựng 16:25 (CQ) và 16:26 (LO). (e) Lập luận từ mã (không phải kết quả chạy): lồng nhau theo tiền tố, cutoff equality và cardinality đúng theo cấu trúc của builder, future perturbation đúng nếu các bảng tóm tắt khóa học, giáo viên, trường không dùng sự kiện sau cutoff (`qa14_code_derived_argument.md`). Theo quy tắc chỉ ghi PASS khi sáu test chạy thật, giữ NOT_RUN.')
v.loc[j, 'evidence_file'] = 'evidence/qa14_results.csv'
v.loc[j, 'evidence_sha256'] = sha(EV / 'qa14_results.csv')
v['code_commit'] = COMMIT
v.to_csv(OUT / 'qa_outcomes_release_r2.csv', index=False, lineterminator='\n')
print(v.status.value_counts().to_dict())
