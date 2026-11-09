"""LO static-v2 evaluation offering bootstrap; resumable, one output shard per cell."""
from pathlib import Path
from hashlib import sha256
import argparse, json, os
import numpy as np
import pandas as pd

ROOT=Path(os.getenv('LO_MODELS_ROOT',r'G:\My Drive\Jobs\LO\organized_moved_20261029\L1_runs\S3_model\run_bundles\lo_static_v2_seed42_20261026\models'))
DATA=Path('downloads/vastai/LO_V3_1_clean_grain_seed42/evaluation')
OUT=Path('LO/resuilt/lo_offering_bootstrap_grid_20261106')
SALT=Path('downloads/private/lo_grid_prediction_salt')
CLASSES=('c0','c1','c2')
def cohort(w,split,salt):
 f=DATA/w/'V0'/('validation.parquet' if split=='VALIDATION' else 'test_P1.parquet')
 d=pd.read_parquet(f,columns=['enrollment_id','context__offering_id','context__timeline_source','LO_performance_label_3'])
 if d.enrollment_id.isna().any() or d.enrollment_id.duplicated().any() or d.context__offering_id.isna().any():raise ValueError(f'cohort identity invalid {f}')
 d['hash']=d.enrollment_id.astype(str).map(lambda x:sha256(f'{salt}|{x}'.encode()).hexdigest())
 d['class']=d.LO_performance_label_3.map({'I/D':0,'G':1,'E':2})
 if d['class'].isna().any() or d['hash'].duplicated().any():raise ValueError(f'labels/hash invalid {f}')
 d['group']=pd.factorize(pd.MultiIndex.from_frame(d[['context__offering_id','context__timeline_source']]),sort=True)[0]
 return d.set_index('hash')[['class','group']]
def run(w,split,model,pipe,phase,d):
 path=ROOT/model/('predictions' if model=='BILSTM' else 'runs')/w/pipe/'seed=42'/'predictions'/f'{split.lower()}_{phase}.parquet'
 out=OUT/'cells'/model/w/pipe/f'{split}_{phase}.json'
 if out.exists():return 'EXISTS'
 p=pd.read_parquet(path,columns=['enrollment_id_hash','y_true','y_pred']).set_index('enrollment_id_hash')
 if p.index.has_duplicates or len(p)!=len(d):raise ValueError(f'prediction grain mismatch {path}')
 p=p.join(d,how='left',validate='one_to_one')
 if p['class'].isna().any() or not p.y_true.map({'c0':0,'c1':1,'c2':2}).eq(p['class']).all():raise ValueError(f'prediction identity/label mismatch {path}')
 actual=p['class'].to_numpy(dtype='int64'); groups=p['group'].to_numpy(dtype='int64'); predicted=p.y_pred.map({'c0':0,'c1':1,'c2':2})
 if predicted.isna().any():raise ValueError(f'bad predicted label {path}')
 predicted=predicted.to_numpy(dtype='int64'); ng=int(groups.max())+1
 matrix=np.bincount(groups*9+actual*3+predicted,minlength=ng*9).reshape(ng,3,3)
 seed=int.from_bytes(sha256(f'42|{w}|{split}|{model}|{pipe}|{phase}'.encode()).digest()[:4],'big')
 rng=np.random.default_rng(seed); draws=rng.multinomial(ng,np.full(ng,1/ng),size=2000); cm=(draws@matrix.reshape(ng,9)).reshape(-1,3,3)
 records=[]
 for i,code in enumerate(CLASSES):
  n=cm[:,i,:].sum(axis=1); v=np.divide(cm[:,i,i],n,out=np.full(2000,np.nan),where=n>0); v=v[np.isfinite(v)]
  nclusters=int((matrix[:,i,:].sum(axis=1)>0).sum()); valid=nclusters>1 and len(v)>0
  records.append({'class_code':code,'support':int(matrix[:,i,:].sum()),'offering_count':nclusters,'recall':float(matrix[:,i,i].sum()/matrix[:,i,:].sum()) if matrix[:,i,:].sum() else None,'valid_replicates':len(v),'missing_class_replicates':2000-len(v),'ci_status':'ESTIMATED_CONDITIONAL_ON_CLASS_PRESENT' if valid else ('NOT_ESTIMABLE_SINGLE_OFFERING' if nclusters==1 else 'CLASS_ABSENT'),'ci_low':float(np.quantile(v,.025)) if valid else None,'ci_high':float(np.quantile(v,.975)) if valid else None})
 result={'task':'LO','window_id':w,'eval_split':split,'model_name':model,'pipeline_id':pipe,'phase_id':phase,'seed':42,'bootstrap_seed':seed,'bootstrap_replicates':2000,'offering_count':ng,'prediction_rows':len(p),'prediction_join':'ONE_TO_ONE_LABELS_MATCH','class_recall':records,'prediction_source':str(path)}
 out.parent.mkdir(parents=True,exist_ok=True);tmp=out.with_suffix('.tmp');tmp.write_text(json.dumps(result)+'\n',encoding='utf8');tmp.replace(out);return 'DONE'
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--max-cells',type=int,default=0);args=parser.parse_args();salt=SALT.read_text(encoding='utf8').strip();n=0
 if not salt:raise ValueError('empty salt')
 for w in ('W1','W2','W3'):
  for split in ('VALIDATION','TEST'):
   d=cohort(w,split,salt)
   for model in ('RNN','LSTM','GRU','BILSTM'):
    for i in range(17):
     for phase in ('P1','P2','P3','P4'):
      status=run(w,split,model,f'V{i}',phase,d);n+=1
      print(w,split,model,f'V{i}',phase,status,flush=True)
      if args.max_cells and n>=args.max_cells:return
if __name__=='__main__':main()
