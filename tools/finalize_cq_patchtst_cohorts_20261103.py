"""Validate, publish and document completed CQ cohort audit facts."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,shutil
import pandas as pd
from docx import Document
from docx.shared import Pt

B=Path('CQ/resuilt/cq_patchtst_v0_v6_full_facts_20261103')
REPORT=Path('CQ/docs/BAO_CAO_CQ_PATCHTST_V0_V6_2026-11-02.docx')
K=['pipeline_id','window_id','eval_split','phase_id']
def main():
    frames=[]
    for i in range(7):
        root=B/'cohort_audit'/f'V{i}'; meta=json.loads((root/'summary.json').read_text(encoding='utf8'))
        if meta['prediction_files']!=24 or meta['duplicate_hashes'] or meta['invalid_strict']:raise ValueError(f'V{i} audit checks failed')
        frame=pd.read_parquet(root/'seen_unseen_strict_overlap_metrics.parquet')
        if len(frame)!=96:raise ValueError(f'V{i} missing cells')
        frames.append(frame)
    c=pd.concat(frames,ignore_index=True); s=pd.read_parquet(B/'sanity_components.parquet')
    if len(c)!=672 or c.duplicated(K+['course_cohort','temporal_slice']).any():raise ValueError('cohort keys not unique')
    total=c.groupby(K,as_index=False).n_eval.sum().merge(s[K+['n_eval_samples']],on=K,validate='one_to_one')
    if len(total)!=168 or not total.n_eval.eq(total.n_eval_samples).all():raise ValueError('cohort partition mismatch')
    n=(c[['support_c0','support_c1','support_c2']]>0).sum(axis=1)
    c['status']='OK';c.loc[n.eq(1),'status']='ONE_CLASS';c.loc[c.n_eval.eq(0),'status']='SLICE_EMPTY'
    c.to_parquet(B/'cohort_slice_status.parquet',index=False);c.to_csv(B/'cohort_slice_status.csv',index=False)
    d=Document(REPORT);hits=0
    for p in d.paragraphs:
        if 'Chưa tính đủ 672 lát' in p.text:
            p.text='Đã tính 672 lát SEEN/UNSEEN × STRICT/OVERLAP bằng cách ghép hash với input gốc theo đúng salt. Toàn bộ 168 ô phân hoạch đủ số dòng; không trùng hash, cờ STRICT hợp lệ. ONE_CLASS và SLICE_EMPTY cần đọc thận trọng; SEEN là course xuất hiện trong real parent TRAIN cùng window.';hits+=1
        elif 'Gói có đủ audit V0–V6; phần cohort SEEN/UNSEEN chưa nghiệm thu.' in p.text:
            p.text=p.text.replace('Gói có đủ audit V0–V6; phần cohort SEEN/UNSEEN chưa nghiệm thu.','Gói có đủ audit V0–V6 và 672 lát cohort đã đối chiếu.')
    if hits!=1:raise ValueError('cohort paragraph not found')
    d.add_page_break();d.add_heading('11. Chi tiết SEEN/UNSEEN × STRICT/OVERLAP',level=1)
    d.add_paragraph('Mỗi dòng là một lát, có số mẫu, Macro-F1, balanced accuracy và trạng thái; các lát một lớp hoặc rỗng không diễn giải như tập đa lớp đầy đủ.')
    for v in sorted(c.pipeline_id.unique(),key=lambda x:int(x[1:])):
        d.add_heading(v,level=2);t=d.add_table(rows=1,cols=9);t.style='Table Grid'
        for cell,text in zip(t.rows[0].cells,['W','Split','P','Course','Time','N','Macro-F1','Balanced','Status']):cell.text=text
        for x in c[c.pipeline_id==v].sort_values(['window_id','eval_split','phase_id','course_cohort','temporal_slice']).itertuples():
            fmt=lambda z:'—' if pd.isna(z) else f'{float(z):.4f}'
            vals=[x.window_id,x.eval_split,x.phase_id,x.course_cohort.replace('_COURSE',''),x.temporal_slice,int(x.n_eval),fmt(x.macro_f1),fmt(x.balanced_accuracy),x.status]
            for cell,text in zip(t.add_row().cells,vals):cell.text=str(text)
        for row in t.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    for run in p.runs:run.font.size=Pt(10)
    d.save(REPORT)
    meta=json.loads((B/'summary.json').read_text(encoding='utf8'));meta.update({'cohort_status':'COMPLETE_FULL_JOIN','cohort_status_counts':c.status.value_counts().to_dict(),'cohort_partition_counts':'PASS','cohort_completed_utc':datetime.now(timezone.utc).isoformat()});(B/'summary.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf8')
    p=B/'README.md';text=p.read_text(encoding='utf8');start=text.index('`cohort_slice_status`');end=text.index(' V7–V16',start);text=text[:start]+'`cohort_slice_status` contains 672 audited SEEN/UNSEEN × STRICT/OVERLAP facts with OK/ONE_CLASS/SLICE_EMPTY flags. All 168 four-slice sums match evaluation totals; prediction hashes are unique and strict flags valid.'+text[end:];p.write_text(text,encoding='utf8')
    shutil.copy2(REPORT,B/'report'/REPORT.name)
    files=sorted(p for p in B.rglob('*') if p.is_file() and p.name!='sha256sums.txt')
    (B/'sha256sums.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(B).as_posix()+'\n' for p in files),encoding='utf8')
    print(json.dumps({'cells':len(c),'partition':'PASS','status_counts':meta['cohort_status_counts'],'files_hashed':len(files)},indent=2),flush=True)
if __name__=='__main__':main()
