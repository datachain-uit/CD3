"""Append detailed CQ PatchTST results and provenance without inventing cohorts."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
import numpy as np
import pandas as pd
from docx import Document
from docx.shared import Pt

BASE=Path('CQ/resuilt/cq_patchtst_v0_v6_full_facts_20261103')
REPORT=Path('CQ/docs/BAO_CAO_CQ_PATCHTST_V0_V6_2026-11-02.docx')
KEY=['pipeline_id','window_id','eval_split','phase_id']
def fmt(x):return '—' if pd.isna(x) else f'{float(x):.4f}'
def table(doc,headers,records):
    t=doc.add_table(rows=1,cols=len(headers));t.style='Table Grid'
    for c,x in zip(t.rows[0].cells,headers):c.text=str(x)
    for record in records:
        for c,x in zip(t.add_row().cells,record):c.text=str(x)
    for row in t.rows:
        for cell in row.cells:
            for p in cell.paragraphs:
                for run in p.runs:run.font.size=Pt(10)
def main():
    s=pd.read_parquet(BASE/'sanity_components.parquet'); per=pd.read_parquet(BASE/'metrics_per_class.parquet'); boot=pd.read_parquet(BASE/'bootstrap_metrics_per_class.parquet'); sl=pd.read_parquet(BASE/'evaluation_slices.parquet'); r=pd.read_parquet(BASE/'resource_per_run.parquet')
    if len(s)!=168 or len(per)!=504 or len(boot)!=1512 or len(sl)!=504 or len(r)!=21:raise ValueError('unexpected coverage')
    if not (boot.bootstrap_repetitions==2000).all():raise ValueError('bootstrap count')
    b=boot[boot.metric_name=='recall']; cls=per.merge(b[KEY+['class_index','estimate','ci_lower','ci_upper']],on=KEY+['class_index'],validate='one_to_one',suffixes=('','_bootstrap'))
    if len(cls)!=504:raise ValueError('class coverage')
    sizes=sl.pivot(index=KEY,columns='slice',values='n_eval_samples')
    if not (sizes.ALL==sizes.STRICT+sizes.OVERLAP).all():raise ValueError('slice partition failed')
    placeholders=[]
    for x in s[KEY].to_dict('records'):
        for cohort in ('SEEN_COURSE','UNSEEN_COURSE'):
            for temporal in ('STRICT','OVERLAP'):
                placeholders.append({**x,'course_cohort':cohort,'temporal_slice':temporal,'status':'NOT_COMPUTED_PENDING_FULL_JOIN','n_eval':None,'macro_f1':None,'balanced_acc':None})
    cohort=pd.DataFrame(placeholders);cohort.to_parquet(BASE/'cohort_slice_status.parquet',index=False);cohort.to_csv(BASE/'cohort_slice_status.csv',index=False)
    cls.to_csv(BASE/'recall_support_bootstrap_ci.csv',index=False);cls.to_parquet(BASE/'recall_support_bootstrap_ci.parquet',index=False)
    d=Document(REPORT)
    if any('5. Thành phần sanity chi tiết' in p.text for p in d.paragraphs):raise ValueError('report already contains appendix')
    d.add_page_break();d.add_heading('5. Thành phần sanity chi tiết',level=1)
    d.add_paragraph('M3 là primary; M4 là sensitivity theo S_san+ v2. Sáu thành phần: s_nan, s_maj_jsd, s_ent, s_drift, s_eff, s_leak. Mỗi dòng là một window, split và phase.')
    for v in sorted(s.pipeline_id.unique(),key=lambda x:int(x[1:])):
        d.add_heading(v,level=2);z=s[s.pipeline_id==v].sort_values(['window_id','eval_split','phase_id']); rows=[]
        for _,x in z.iterrows():rows.append([x.window_id,x.eval_split,x.phase_id,*[fmt(x[c]) for c in ['acctempo_m3','acctempo_m4','s_san_plus','s_san_plus_v2','s_cal','s_nan','s_maj_jsd','s_ent','s_drift','s_eff','s_leak']]])
        table(d,['W','Split','P','M3','M4','San v1','San v2','s_cal','nan','maj','ent','drift','eff','leak'],rows)
    d.add_heading('6. Support và recall theo lớp, CI bootstrap',level=1)
    d.add_paragraph('Recall điểm lấy từ metrics_per_class. Khoảng tin cậy 95% lấy từ bootstrap recall, B=2.000; estimate bootstrap không được thay cho recall điểm. Cột c0/c1/c2 ghi support / recall điểm [cận dưới, cận trên].')
    for v in sorted(s.pipeline_id.unique(),key=lambda x:int(x[1:])):
        d.add_heading(v,level=2); rows=[]
        for k,g in cls[cls.pipeline_id==v].groupby(KEY,sort=True):
            by={int(x.class_index):x for x in g.itertuples()}
            def show(i):
                x=by[i];return f'{int(x.n_support)} / {fmt(x.recall)} [{fmt(x.ci_lower)}, {fmt(x.ci_upper)}]'
            rows.append([k[1],k[2],k[3],show(0),show(1),show(2)])
        table(d,['W','Split','P','c0: N / recall [CI]','c1: N / recall [CI]','c2: N / recall [CI]'],rows)
    d.add_heading('7. STRICT và OVERLAP',level=1)
    d.add_paragraph('Ba lát ALL, STRICT, OVERLAP là mô tả trên cùng cohort; số dòng STRICT + OVERLAP đã kiểm khớp ALL ở mọi ô. Không dùng test để chọn checkpoint.')
    for v in sorted(s.pipeline_id.unique(),key=lambda x:int(x[1:])):
        d.add_heading(v,level=2);rows=[]
        for x in sl[sl.pipeline_id==v].sort_values(['window_id','eval_split','phase_id','slice']).itertuples():rows.append([x.window_id,x.eval_split,x.phase_id,x.slice,int(x.n_eval_samples),fmt(x.macro_f1),fmt(x.balanced_acc),fmt(x.acctempo_m3)])
        table(d,['W','Split','P','Lát','N','Macro-F1','Balanced acc.','M3'],rows)
    d.add_heading('8. SEEN/UNSEEN × STRICT/OVERLAP',level=1)
    d.add_paragraph('Chưa tính đủ 672 lát. Salt đã được xác nhận bằng cách ghép đầy đủ W1/Test/P1 cho cả V0–V6; trước đó phép kiểm dùng sai cách đọc CRLF. Bảng cohort_slice_status ghi NOT_COMPUTED_PENDING_FULL_JOIN: không có nghĩa lát rỗng. Cần hoàn thành ghép toàn bộ window, split và phase trước khi kết luận.')
    d.add_heading('9. Tài nguyên và năng lượng theo run',level=1)
    d.add_paragraph('Train giờ = tổng train_seconds theo epoch; elapsed gồm các bước khác của run. Năng lượng là ước lượng GPU-only từ NVML, không phải tổng năng lượng máy hoặc CO₂. Chi phí trong mục 2 chỉ là ước tính theo giá giả định.')
    rows=[]
    for x in r.sort_values(['pipeline_id','window_id']).itertuples():rows.append([x.pipeline_id,x.window_id,f'{x.train_seconds/3600:.2f}',f'{x.elapsed_seconds/3600:.2f}',fmt(x.energy_gpu_estimated_kwh),x.energy_sample_count,fmt(x.energy_missing_sample_rate)])
    table(d,['V','W','Train giờ','Elapsed giờ','GPU kWh ước tính','Số mẫu NVML','Tỷ lệ mẫu thiếu'],rows)
    d.add_heading('10. Bằng chứng và trạng thái bàn giao',level=1)
    d.add_paragraph('Facts CSV/Parquet, inventory nguồn, README và SHA-256 lưu cùng gói cq_patchtst_v0_v6_full_facts_20261103. Gói có đủ audit V0–V6; phần cohort SEEN/UNSEEN chưa nghiệm thu. M4 được tính từ S_perf và S_san+ v2 theo công thức đã đăng ký.')
    d.save(REPORT)
    info={'created_at_utc':datetime.now(timezone.utc).isoformat(),'task':'CQ','model':'PATCHTST','seed':42,'versions':[f'V{i}' for i in range(7)],'sanity_cells':168,'slice_rows':504,'per_class_rows':504,'bootstrap_rows':1512,'resource_runs':21,'cohort_status_rows':672,'cohort_status':'NOT_COMPUTED_PENDING_FULL_JOIN','nvml_energy':'GPU_ONLY_ESTIMATE','strict_partition_counts':'PASS','report':str(REPORT)}
    (BASE/'summary.json').write_text(json.dumps(info,indent=2)+'\n',encoding='utf8')
    (BASE/'README.md').write_text('''# CQ PatchTST V0–V6, seed 42

168 split/window/phase sanity cells; 504 ALL/STRICT/OVERLAP rows; 504 per-class rows; 1,512 bootstrap rows with B=2,000; 21 run-resource rows. `acctempo_m4` is S_perf^0.6 × S_san_plus_v2^0.4 with floor 0.001. `recall_support_bootstrap_ci` keeps point recall and bootstrap estimate separate. STRICT/OVERLAP counts sum to ALL. NVML energy is a GPU-only estimate; `train_seconds` sums recorded epoch train durations. See source_inventory.json for verified archive provenance.

`cohort_slice_status` contains 672 explicit NOT_COMPUTED_PENDING_FULL_JOIN rows, not empty-cohort facts. The salt was verified on all W1/TEST/P1 rows for V0–V6 after preserving CR as shell command substitution does. Other windows/splits/phases still require the full join. V7–V16 and seeds 43/44 are outside this package. V4/W3 used workers=0 after OOM. V0 provenance is the separately downloaded audit and original run directories.
''',encoding='utf8')
    files=sorted(p for p in BASE.iterdir() if p.is_file() and p.name!='sha256sums.txt')
    (BASE/'sha256sums.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in files),encoding='utf8')
    print(json.dumps(info,indent=2),flush=True)
if __name__=='__main__':main()
