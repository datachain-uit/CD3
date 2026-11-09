"""Summarize LO V0 evaluation cohorts and locked block mapping, without train leakage."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib
import numpy as np
import pandas as pd
BASE=Path('downloads/vastai/LO_V3_1_clean_grain_seed42')
OUT=Path('LO/resuilt/lo_split_evidence_20261106')
REG=Path(r'G:\My Drive\Jobs\LO\organized_moved_20261029\L0_registry\modal_L0_registry\L0_registry\split_registry.json')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for c in iter(lambda:f.read(1048576),b''):h.update(c)
 return h.hexdigest()
def main():
 reg=json.loads(REG.read_text(encoding='utf8')); expected={'W1':['A','B','C'],'W2':['A+B+C','D','E'],'W3':['A+B+C+D+E','F','G']}
 if reg['windows']!=expected:raise ValueError('Unexpected registry mapping')
 cohorts=[('A',BASE/'train/W1/V0/train.parquet')]+[(block,BASE/f'evaluation/{w}/V0/{file}') for w,blocks in [('W1',('B','C')),('W2',('D','E')),('W3',('F','G'))] for block,file in zip(blocks,('validation.parquet','test_P1.parquet'))]
 rows=[];ids=set()
 for block,f in cohorts:
  d=pd.read_parquet(f,columns=['enrollment_id','LO_performance_label_3']); current=set(d.enrollment_id)
  if d.enrollment_id.isna().any() or len(current)!=len(d) or ids.intersection(current):raise ValueError(f'Block overlap or duplicate {block}')
  ids.update(current);v=d.LO_performance_label_3.value_counts(dropna=False)
  for label in ('I/D','G','E'): rows.append(dict(block=block,class_code=label,n=int(v.get(label,0)),block_n=len(d),class_share=float(v.get(label,0)/len(d))))
  print('block',block,len(d),flush=True)
  del d,current
 strict=[]
 for w in ('W1','W2','W3'):
  for split in ('VALIDATION','TEST'):
   for p in range(1,5):
    f=BASE/f'evaluation/{w}/V0'/('validation.parquet' if split=='VALIDATION' else f'test_P{p}.parquet');col=f'context__temporal_strict_P{p}'
    d=pd.read_parquet(f,columns=[col]); s=pd.to_numeric(d[col],errors='coerce')
    if s.isna().any() or not s.isin([0,1]).all():raise ValueError(f'Invalid strict {f}/{col}')
    strict.append(dict(window_id=w,eval_split=split,phase_id=f'P{p}',n=len(s),strict_n=int(s.sum()),strict_share=float(s.mean()),overlap_n=int((s==0).sum())))
   print('strict',w,split,flush=True)
 OUT.mkdir(parents=True,exist_ok=True);pd.DataFrame(rows).to_csv(OUT/'block_class_counts.csv',index=False);pd.DataFrame(strict).to_csv(OUT/'strict_share.csv',index=False)
 summary={'status':'PARTIAL','block_mapping':expected,'block_rows':len(rows),'strict_rows':len(strict),'block_overlap_check':'PASS','registry_sha256':sha(REG),'created_at_utc':datetime.now(timezone.utc).isoformat(),'missing':['tau_w','ev_train_overlap_share','offering_duration_distribution','exclusion_reasons','raw_pre_post_population']}
 (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf8');(OUT/'README.md').write_text('# LO split evidence — partial\n\nBlocks are reconstructed using the locked registry mapping and V0 real input cohorts. An exact enrollment disjointness check passed across A–G. STRICT rows use the phase-specific context flags. Full M-07 requires the missing fields listed in summary.json and original-source provenance.\n',encoding='utf8');(OUT/'sha256sums.txt').write_text(''.join(sha(f)+'  '+f.name+'\n' for f in sorted(OUT.iterdir()) if f.is_file() and f.name!='sha256sums.txt'),encoding='utf8');print(json.dumps(summary),flush=True)
if __name__=='__main__':main()
