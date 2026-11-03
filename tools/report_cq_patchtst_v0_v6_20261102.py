"""Build CQ PatchTST V0–V6 report from verified downloaded audit artifacts."""
from pathlib import Path
from io import BytesIO
from datetime import datetime
import hashlib,json,tarfile
import pandas as pd
from docx import Document
from docx.shared import Cm,Pt,RGBColor
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH

ROOT=Path('CQ/resuilt')
OUT=Path('CQ/docs/BAO_CAO_CQ_PATCHTST_V0_V6_2026-11-02.docx')
NAMES={1:'cq_patchtst_v1_seed42_20261031',2:'cq_patchtst_v2_seed42_20261101',3:'cq_patchtst_v3_seed42_20261101',4:'cq_patchtst_v4_seed42_20261101',5:'cq_patchtst_v5_seed42_20261101',6:'cq_patchtst_v6_seed42_20261101'}
def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
def collect():
    records=[]; manifests=[]; sources=[]
    p=ROOT/'cq_patchtst_v0_current_seed42_r21_audit/CQ/PATCHTST/seed=42/sanity_components.parquet'
    a=pd.read_parquet(p); records.append(a)
    for f in (ROOT/'cq_patchtst_v0_current_seed42_r21').rglob('run_manifest.json'): manifests.append(json.loads(f.read_text(encoding='utf8')))
    sources.append({'version':'V0','source':str(p),'sha256':digest(p)})
    for i,name in NAMES.items():
        folder=ROOT/name; receipt=folder/'download_receipt.json'
        if not receipt.exists(): print(f'WAIT V{i}: missing verified receipt',flush=True); continue
        r=json.loads(receipt.read_text(encoding='utf8')); archive=Path(r['archive'])
        actual=digest(archive)
        if actual!=r['sha256'] or r['status']!='download_verified':raise ValueError(f'V{i} archive hash mismatch')
        with tarfile.open(archive,'r:gz') as tar:
            for m in tar:
                if not m.isfile():continue
                if m.name.endswith('/sanity_components.parquet') and '_audit/' in m.name:
                    records.append(pd.read_parquet(BytesIO(tar.extractfile(m).read())))
                elif m.name.endswith('/run_manifest.json') and '/CQ/W' in m.name:
                    manifests.append(json.load(tar.extractfile(m)))
        sources.append({'version':f'V{i}','source':str(archive),'sha256':actual})
    cells=pd.concat(records,ignore_index=True)
    keys=['pipeline_id','window_id','eval_split','phase_id']
    if cells.duplicated(keys).any():raise ValueError('duplicate evaluation keys')
    if any(cells.groupby('pipeline_id').size()!=24):raise ValueError('incomplete version audit')
    runs=pd.DataFrame(manifests)
    if len(runs)!=3*len(sources) or runs.duplicated(['pipeline_id','window_id']).any():raise ValueError('manifest coverage mismatch')
    return cells,runs,sources
def table(doc,head,rows):
    t=doc.add_table(rows=1,cols=len(head));t.style='Table Grid'
    for c,v in zip(t.rows[0].cells,head):c.text=str(v)
    for row in rows:
        for c,v in zip(t.add_row().cells,row):c.text=str(v)
    for row in t.rows:
        for c in row.cells:
            for p in c.paragraphs:
                for run in p.runs:run.font.size=Pt(10)
def main():
    cells,runs,sources=collect();present=set(cells.pipeline_id)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    d=Document(); sec=d.sections[0]; sec.orientation=WD_ORIENT.LANDSCAPE;sec.page_width,sec.page_height=sec.page_height,sec.page_width;sec.left_margin=sec.right_margin=Cm(1.5)
    normal=d.styles['Normal'];normal.font.name='Arial';normal.font.size=Pt(10)
    d.add_heading('BÁO CÁO CQ PATCHTST — SEED 42',0)
    d.add_paragraph('Tổng hợp V0–V6 theo W1–W3 và P1–P4; số liệu từ sanity audit và manifest đã tải, không gộp nhầm các window. Ngày lập: '+datetime.now().strftime('%d/%m/%Y %H:%M'))
    d.add_paragraph('AccTEMPO M3 là độ đo tổng hợp chính; Macro-F1 và balanced accuracy là các thành phần hiệu suất. Số liệu validation và test được trình bày riêng. Đây là kết quả seed 42, chưa chứng minh độ ổn định qua seed.')
    d.add_heading('1. Phạm vi và trạng thái',level=1)
    d.add_paragraph('Các version có đầy đủ audit được đưa vào bảng: '+', '.join(sorted(present,key=lambda x:int(x[1:])))+'. V7 đã dừng trước khi hoàn tất; V8–V16 không thuộc báo cáo này. Chỉ coi là đầy đủ khi cả 7 version đều xuất hiện.')
    d.add_paragraph('Protocol: CQ V2.2, PatchTST current layout, seed 42, batch hiệu dụng 2.048 = 512 × 4, learning rate 0,001, tối đa 50 epoch, early stopping patience 5. V4/W3 chạy lại với workers=0 sau OOM; các tham số học được giữ nguyên.')
    d.add_heading('2. Run và checkpoint được chọn',level=1)
    rows=[]
    for _,m in runs.sort_values(['pipeline_id','window_id']).iterrows():
        rows.append([m.get('pipeline_id'),m.get('window_id'),m.get('best_epoch'),f"{float(m.get('elapsed_seconds',0))/3600:.2f}",m.get('gpu'),m.get('batch_size'),m.get('micro_batch_size'),m.get('accumulation_steps')])
    table(d,['V','W','Epoch chọn','Run giờ','GPU','Batch','Micro','Tích lũy'],rows)
    d.add_heading('Ước tính thời gian và chi phí',level=1)
    if runs.elapsed_seconds.isna().any():raise ValueError('missing elapsed_seconds; cost estimate cannot be calculated')
    duration=(runs.groupby('pipeline_id',as_index=False)['elapsed_seconds'].sum())
    duration['hours']=duration.elapsed_seconds/3600
    rate=0.368
    duration['estimated_usd']=duration.hours*rate
    table(d,['Version','Tổng thời gian W1–W3 (giờ)','Chi phí ước tính (USD)'],[[r.pipeline_id,f'{r.hours:.2f}',f'{r.estimated_usd:.2f}'] for r in duration.itertuples()])
    mean_hours=float(duration.hours.mean());total_hours=float(duration.hours.sum());remaining=17-len(duration)
    d.add_paragraph(f'Tổng {len(duration)} version đã hoàn tất: {total_hours:.2f} giờ run, tương đương {total_hours*rate:.2f} USD nếu áp dụng đồng nhất 0,368 USD/giờ. Trung bình {mean_hours:.2f} giờ/version; khoảng {mean_hours*rate:.2f} USD/version. Đây là phép nhân ước tính, không phải hóa đơn thực tế.')
    d.add_paragraph(f'Nếu {remaining} version còn lại có thời gian giống trung bình trên, ước tính thêm {remaining*mean_hours:.2f} giờ máy và {remaining*mean_hours*rate:.2f} USD. Chạy song song rút ngắn thời gian chờ theo version chậm nhất, còn chi phí cộng theo giờ của từng máy. Số epoch, loại máy và thời gian mỗi version có thể khác nhau; không suy diễn đây là dự báo chính xác.')
    d.add_paragraph('Thời lượng trên dùng elapsed_seconds của từng run trong manifest: bao gồm phần chuẩn bị và xuất kết quả của run, không phải train_seconds thuần. Chưa cộng audit, tải dữ liệu, thời gian chờ máy, lưu trữ, truyền dữ liệu hoặc phí khác; không bao gồm thời gian và phí của các lần lỗi/chạy lại. Giá thực tế có thể thay đổi theo instance.')
    costout=ROOT/'cq_patchtst_v0_v6_summary_20261102';costout.mkdir(exist_ok=True)
    duration.to_csv(costout/'runtime_cost_estimates.csv',index=False)
    for split,label in [('VALIDATION','Validation'),('TEST','Test')]:
        d.add_heading('3. '+label+' — từng window và phase',level=1)
        d.add_paragraph('M3 = AccTEMPO M3; S_perf và S_san+ là các thành phần được lưu trong audit. Các dòng không phải trung bình qua window hoặc phase.')
        data=cells[cells.eval_split==split].copy();data['_v']=data.pipeline_id.str[1:].astype(int)
        rows=[]
        for _,x in data.sort_values(['_v','window_id','phase_id']).iterrows():
            fmt=lambda k:f"{float(x[k]):.4f}" if pd.notna(x[k]) else '—'
            rows.append([x.pipeline_id,x.window_id,x.phase_id,int(x.n_eval_samples),fmt('acctempo_m3'),fmt('s_perf'),fmt('s_san_plus'),fmt('macro_f1'),fmt('balanced_acc')])
        table(d,['V','W','P','N','AccTEMPO M3','S_perf','S_san+','Macro-F1','Balanced acc.'],rows)
    d.add_heading('4. Nguồn và giới hạn',level=1)
    d.add_paragraph('Audit dùng bootstrap 2.000 theo manifest; báo cáo này trình bày các chỉ số chính, dữ liệu per-class, CI và phân lát nằm trong các gói audit gốc. Mọi tệp archive V1–V6 được so SHA-256 với receipt trước khi đọc. V0 dùng audit đã tải riêng.')
    for s in sources:d.add_paragraph(f"{s['version']}: {s['source']} — SHA-256 {s['sha256']}",style='Normal')
    d.save(OUT)
    out=ROOT/'cq_patchtst_v0_v6_summary_20261102';out.mkdir(exist_ok=True)
    cells.to_parquet(out/'sanity_all_cells.parquet',index=False);cells.to_csv(out/'sanity_all_cells.csv',index=False)
    (out/'source_inventory.json').write_text(json.dumps(sources,indent=2)+'\n',encoding='utf8')
    print(f'REPORT {OUT} VERSIONS={len(sources)} CELLS={len(cells)}',flush=True)
if __name__=='__main__':main()
