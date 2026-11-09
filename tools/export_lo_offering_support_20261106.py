"""Profile real evaluation cohort offering concentration without training."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json
import pandas as pd
import pyarrow.parquet as pq

BASE=Path('downloads/vastai/LO_V3_1_clean_grain_seed42/evaluation')
OUT=Path('LO/resuilt/lo_offering_support_20261106')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for x in iter(lambda:f.read(1024*1024),b''):h.update(x)
 return h.hexdigest()
def main():
 rows=[]; flags=[]; sources=[]
 for w in ('W1','W2','W3'):
  for split,name in [('VALIDATION','validation.parquet'),('TEST','test_P1.parquet')]:
   f=BASE/w/'V0'/name; schema=pq.read_schema(f).names
   required=['enrollment_id','context__offering_id','LO_performance_label_3']
   if any(c not in schema for c in required):raise ValueError(f'Missing identity in {f}')
   cols=required+(['context__timeline_source'] if 'context__timeline_source' in schema else [])
   d=pd.read_parquet(f,columns=cols)
   if d.enrollment_id.isna().any() or d.enrollment_id.duplicated().any():raise ValueError(f'grain violation {f}')
   if d.context__offering_id.isna().any():raise ValueError(f'null offering in {f}')
   if set(d.LO_performance_label_3.dropna().unique())-{'I/D','G','E'} or d.LO_performance_label_3.isna().any():raise ValueError(f'bad labels {f}')
   grouping=['context__offering_id']+(['context__timeline_source'] if 'context__timeline_source' in cols else [])
   for label in ('I/D','G','E'):
    sub=d[d.LO_performance_label_3==label]; g=sub.groupby(grouping,dropna=False).size(); n=len(sub); top=int(g.max()) if n else 0
    rows.append(dict(task='LO',window_id=w,eval_split=split,class_code=label,n_support=n,n_offerings_with_class=len(g),top_offering_count=top,top_offering_share=top/n if n else None,single_offering_flag=len(g)==1,single_offering_dominant=(top/n>=.5) if n else None,offering_identity=' + '.join(grouping)))
   sources.append(dict(path=str(f),n_rows=len(d),has_timeline_source='context__timeline_source' in cols))
   print(w,split,len(d),flush=True)
 out=pd.DataFrame(rows); OUT.mkdir(parents=True,exist_ok=True)
 facts=pd.read_parquet('LO/resuilt/lo_static_v2_grid_seed42_20261102/lo_family_pipeline_window_phase_metrics.parquet')
 keys=['task','window_id','pipeline_id','model_name','seed','eval_split','phase_id']
 if len(facts)!=1632 or facts.duplicated(keys).any():raise ValueError('unexpected fact grain')
 for idx,label in enumerate(('I/D','G','E')):
  source=out[out.class_code==label][['window_id','eval_split','n_support','single_offering_dominant']].rename(columns={'n_support':f'expected_c{idx}','single_offering_dominant':f'c{idx}_single_offering_dominant'})
  facts=facts.merge(source,on=['window_id','eval_split'],how='left',validate='many_to_one')
  if facts[f'expected_c{idx}'].isna().any() or not (facts[f'expected_c{idx}']==facts[f'c{idx}_support']).all():raise ValueError(f'Fact support mismatch {label}')
 flags=facts[keys+[f'c{i}_single_offering_dominant' for i in range(3)]].copy()
 flags['single_offering_dominant']=flags[[f'c{i}_single_offering_dominant' for i in range(3)]].any(axis=1)
 flags.to_csv(OUT/'cell_flags.csv',index=False); flags.to_parquet(OUT/'cell_flags.parquet',index=False)
 out.to_csv(OUT/'class_offering_support.csv',index=False); out.to_parquet(OUT/'class_offering_support.parquet',index=False)
 (OUT/'summary.json').write_text(json.dumps(dict(created_at_utc=datetime.now(timezone.utc).isoformat(),status='PARTIAL_PENDING_IDENTITY_PARITY_AND_CLUSTER_BOOTSTRAP',rows=len(out),cell_flags=len(flags),sources=sources,dominant_class_slices=int(out.single_offering_dominant.fillna(False).sum()),dominant_cells=int(flags.single_offering_dominant.sum()),support_match='ALL_1632_FACT_ROWS'),indent=2)+'\n',encoding='utf8')
 (OUT/'README.md').write_text('# LO offering support — partial\n\nCounts use V0 real evaluation inputs, one row per enrollment; TEST uses P1 cohort. Offering key uses context__offering_id and context__timeline_source when present. Per-class support matches all 1,632 fact rows, but equal counts do not prove identity parity across all pipelines/phases. Prediction-linked cluster bootstrap and input source hashes are not yet verified.\n',encoding='utf8')
 (OUT/'sha256sums.txt').write_text(''.join(sha(p)+'  '+p.name+'\n' for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='sha256sums.txt'),encoding='utf8')
if __name__=='__main__':main()
