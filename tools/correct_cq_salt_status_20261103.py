"""Correct provisional CQ cohort status after shell-compatible salt verification."""
from pathlib import Path
import hashlib,json,shutil
import pandas as pd
from docx import Document

base=Path('CQ/resuilt/cq_patchtst_v0_v6_full_facts_20261103')
report=Path('CQ/docs/BAO_CAO_CQ_PATCHTST_V0_V6_2026-11-02.docx')
d=Document(report); hits=0
for p in d.paragraphs:
    if 'hai tệp salt CQ local' in p.text:
        p.text=('Chưa tính đủ 672 lát. Salt đã được xác nhận bằng cách ghép đầy đủ W1/Test/P1 cho cả V0–V6; phép kiểm trước dùng sai cách đọc CRLF. Bảng cohort_slice_status ghi NOT_COMPUTED_PENDING_FULL_JOIN, không có nghĩa lát rỗng. Cần hoàn thành ghép toàn bộ window, split và phase trước khi kết luận.')
        hits+=1
if hits!=1:raise ValueError(f'expected one paragraph to correct, found {hits}')
d.save(report)
f=pd.read_parquet(base/'cohort_slice_status.parquet');f['status']='NOT_COMPUTED_PENDING_FULL_JOIN';f.to_parquet(base/'cohort_slice_status.parquet',index=False);f.to_csv(base/'cohort_slice_status.csv',index=False)
p=base/'summary.json';summary=json.loads(p.read_text(encoding='utf8'));summary['cohort_status']='NOT_COMPUTED_PENDING_FULL_JOIN';summary['salt_verified_scope']='W1/TEST/P1 V0–V6 exact unique set';p.write_text(json.dumps(summary,indent=2)+'\n',encoding='utf8')
p=base/'README.md';s=p.read_text(encoding='utf8');s=s.replace('`cohort_slice_status` contains 672 explicit NOT_COMPUTED_SALT_NOT_VERIFIED rows, not empty-cohort facts: two local salt candidates failed a sample join.','`cohort_slice_status` contains 672 NOT_COMPUTED_PENDING_FULL_JOIN rows, not empty-cohort facts. Salt matched all W1/TEST/P1 IDs for V0–V6 after preserving CR as shell command substitution does; full joins remain pending.');p.write_text(s,encoding='utf8')
shutil.copy2(report,base/'report'/report.name)
files=sorted(p for p in base.rglob('*') if p.is_file() and p.name!='sha256sums.txt')
(base/'sha256sums.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(base).as_posix()+'\n' for p in files),encoding='utf8')
print(f'Corrected report and {len(files)} inventory hashes; salt value not exported')
