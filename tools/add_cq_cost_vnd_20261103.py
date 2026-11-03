"""Add a dated, illustrative VND conversion without rebuilding the report."""
from pathlib import Path
import hashlib,shutil
import pandas as pd
from docx import Document
from docx.shared import Cm,Pt

REPORT=Path('CQ/docs/BAO_CAO_CQ_PATCHTST_V0_V6_2026-11-02.docx')
OUTPUT=Path('CQ/docs/BAO_CAO_CQ_PATCHTST_V0_V6_2026-11-02_VND.docx')
SOURCE=Path('CQ/resuilt/cq_patchtst_v0_v6_summary_20261102/runtime_cost_estimates.csv')
BUNDLE=Path('CQ/resuilt/cq_patchtst_v0_v6_full_facts_20261103')
RATE=25990
df=pd.read_csv(SOURCE)
if len(df)!=7 or set(df.pipeline_id)!={f'V{i}' for i in range(7)}:raise ValueError('cost coverage incomplete')
df['exchange_rate_vnd_per_usd']=RATE;df['estimated_vnd']=(df.estimated_usd*RATE).round().astype('int64')
df.to_csv(BUNDLE/'runtime_cost_estimates_vnd.csv',index=False)
d=Document(REPORT)
matches=[t for t in d.tables if len(t.rows) and [c.text for c in t.rows[0].cells][:2]==['Version','Tổng thời gian W1–W3 (giờ)']]
if len(matches)!=1:raise ValueError('cost table ambiguous')
t=matches[0]
if len(t.columns)==3:t.add_column(Cm(3.7))
if len(t.columns)!=4:raise ValueError('unexpected cost table schema')
t.rows[0].cells[3].text='Quy đổi ước tính (VNĐ)'
mapping=df.set_index('pipeline_id')['estimated_vnd'].to_dict()
for row in t.rows[1:]:
    version=row.cells[0].text.strip()
    if version not in mapping:raise ValueError(f'unexpected version {version}')
    row.cells[3].text=f'{mapping[version]:,}'.replace(',','.')
for row in t.rows:
    for cell in row.cells:
        for p in cell.paragraphs:
            for run in p.runs:run.font.size=Pt(10)
total=round(df.estimated_usd.sum()*RATE);mean=round(df.estimated_usd.mean()*RATE);remaining=round(df.estimated_usd.mean()*10*RATE)
vnd=lambda value:f'{value:,}'.replace(',','.')
for p in d.paragraphs:
    text=p.text
    if text.startswith('Tổng 7 version đã hoàn tất:'):
        p.text=f'Tổng 7 version đã hoàn tất: {df.hours.sum():.2f} giờ run, ước tính {df.estimated_usd.sum():.2f} USD (khoảng {vnd(total)} VNĐ). Trung bình {df.hours.mean():.2f} giờ/version, ước tính {df.estimated_usd.mean():.2f} USD (khoảng {vnd(mean)} VNĐ)/version. Đây là phép nhân ước tính, không phải hóa đơn thực tế.'
    elif text.startswith('Nếu 10 version còn lại'):
        p.text=f'Nếu 10 version còn lại có thời gian giống trung bình trên: ước tính thêm {df.hours.mean()*10:.2f} giờ máy và {df.estimated_usd.mean()*10:.2f} USD (khoảng {vnd(remaining)} VNĐ). Chạy song song rút ngắn thời gian chờ theo version chậm nhất; chi phí cộng theo giờ của từng máy. Số epoch và thời gian thực tế có thể khác nhau.'
    elif text.startswith('Tỷ giá quy đổi tham khảo:'):
        p.text=f'Tỷ giá quy đổi tham khảo: 1 USD = {RATE:,} VNĐ, giá bán USD của Vietcombank cập nhật 23:00 ngày 02/11/2026; https://www.vietcombank.com.vn/vi-VN/KHCN/Cong-cu-Tien-ich/Ty-gia. Tỷ giá thẻ, ngân hàng và phụ phí thực tế có thể khác.'.replace(',','.')
        break
else:
    anchor=next(p for p in d.paragraphs if p.text.startswith('Thời lượng trên dùng elapsed_seconds'))
    anchor.insert_paragraph_before(f'Tỷ giá quy đổi tham khảo: 1 USD = 25.990 VNĐ, giá bán USD của Vietcombank cập nhật 23:00 ngày 02/11/2026; https://www.vietcombank.com.vn/vi-VN/KHCN/Cong-cu-Tien-ich/Ty-gia. Tỷ giá thẻ, ngân hàng và phụ phí thực tế có thể khác.')
d.save(OUTPUT)
shutil.copy2(OUTPUT,BUNDLE/'report'/OUTPUT.name)
files=sorted(p for p in BUNDLE.rglob('*') if p.is_file() and p.name!='sha256sums.txt')
(BUNDLE/'sha256sums.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(BUNDLE).as_posix()+'\n' for p in files),encoding='utf8')
print(f'total_usd={df.estimated_usd.sum():.4f} total_vnd={total} remaining_vnd={remaining} rate={RATE} files={len(files)}')
