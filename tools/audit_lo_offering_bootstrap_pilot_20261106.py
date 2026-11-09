"""Read-only W1/V0/RNN pilot: verify prediction linkage and offering bootstrap."""
from pathlib import Path
from hashlib import sha256
from datetime import datetime,timezone
import json
import numpy as np
import pandas as pd

ROOT=Path(r'G:\My Drive\Jobs\LO\organized_moved_20261029\L1_runs\S3_model\run_bundles\lo_static_v2_seed42_20261026\models')
DATA=Path('downloads/vastai/LO_V3_1_clean_grain_seed42/evaluation/W1/V0/test_P1.parquet')
SALT=Path('downloads/private/lo_grid_prediction_salt')
OUT=Path('LO/resuilt/lo_offering_support_20261106')
def main():
 salt=SALT.read_text(encoding='utf8').strip()
 if not salt:raise ValueError('missing salt')
 d=pd.read_parquet(DATA,columns=['enrollment_id','context__offering_id','context__timeline_source','LO_performance_label_3'])
 d['enrollment_id_hash']=d.enrollment_id.astype(str).map(lambda x:sha256(f'{salt}|{x}'.encode()).hexdigest())
 pred=pd.read_parquet(ROOT/'RNN/runs/W1/V0/seed=42/predictions/test_P1.parquet',columns=['enrollment_id_hash','y_true','y_pred'])
 joined=d.merge(pred,on='enrollment_id_hash',how='outer',validate='one_to_one',indicator=True)
 if not joined['_merge'].eq('both').all():raise ValueError('prediction hash mismatch')
 if not joined.LO_performance_label_3.map({'I/D':'c0','G':'c1','E':'c2'}).eq(joined.y_true).all():raise ValueError('label mismatch')
 joined['correct']=(joined.y_true==joined.y_pred).astype(int)
 grouped=joined.groupby(['context__offering_id','context__timeline_source','y_true'],dropna=False).agg(n=('correct','size'),hits=('correct','sum')).reset_index()
 pivot_n=grouped.pivot(index=['context__offering_id','context__timeline_source'],columns='y_true',values='n').fillna(0).reindex(columns=['c0','c1','c2'],fill_value=0).to_numpy()
 pivot_h=grouped.pivot(index=['context__offering_id','context__timeline_source'],columns='y_true',values='hits').fillna(0).reindex(columns=['c0','c1','c2'],fill_value=0).to_numpy()
 rng=np.random.default_rng(42); counts=rng.multinomial(len(pivot_n),np.full(len(pivot_n),1/len(pivot_n)),size=2000); n=counts@pivot_n; h=counts@pivot_h
 records=[]
 for i,label in enumerate(['I/D','G','E']):
  values=np.divide(h[:,i],n[:,i],out=np.full(len(n),np.nan),where=n[:,i]>0); finite=values[np.isfinite(values)]
  clusters=int((pivot_n[:,i]>0).sum()); estimable=clusters>1 and len(finite)>0
  records.append(dict(class_code=label,support=int(pivot_n[:,i].sum()),n_offerings_with_class=clusters,recall=float(pivot_h[:,i].sum()/pivot_n[:,i].sum()),bootstrap_valid=int(len(finite)),bootstrap_missing_class=int(len(values)-len(finite)),ci_status='ESTIMATED_CONDITIONAL_ON_CLASS_PRESENT' if estimable else 'NOT_ESTIMABLE_SINGLE_OFFERING',ci_2_5=float(np.quantile(finite,.025)) if estimable else None,ci_97_5=float(np.quantile(finite,.975)) if estimable else None))
 summary=dict(status='PILOT_ONLY_NOT_ALL_CELLS',task='LO',window='W1',pipeline='V0',model='RNN',split='TEST',phase='P1',seed=42,bootstrap_seed=42,bootstrap_replicates=2000,n_rows=len(joined),n_offerings=len(pivot_n),join='ONE_TO_ONE_ALL_ROWS',labels='MATCH',class_recall=records,created_at_utc=datetime.now(timezone.utc).isoformat())
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'bootstrap_pilot_w1_v0_rnn_test_p1.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf8');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
