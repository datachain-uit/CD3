"""Build the B4' deliverables from run_manifest.json files of the seed-44 model runs (already read into raw/) and the S2 manifest set seed44_17429_20261114."""
import json, pandas as pd, re, os, hashlib
B='<WORK_DIR>'; O=f'{B}/deliver'; os.makedirs(O,exist_ok=True)
R=pd.read_pickle(f'{B}/runs_linked.pkl')
H=json.load(open(f'{B}/local_s2_children_hash.json'))
def mantis_sha(r):
    if r.manifest_schema!='mantis_cache_manifest' or not r.balanced: return None
    k=f'{r.task}|{r.window}|{r.pipeline}'
    if k not in H: return 'NO_LOCAL_COPY'
    return 'EQUAL' if H[k][0]==r.train_sha256_recorded else 'DIFFERENT'
R['mantis_train_sha256_vs_local_s2_parquet']=R.apply(mantis_sha,axis=1)
rel=lambda p: p.split('/data/',1)[1] if isinstance(p,str) and '/data/' in p else p
R['train_input_recorded']=R.train_path_recorded.map(rel)
R['direct_s2_field_in_run_manifest']=R.has_explicit_s2_field.map(lambda x:'NO')
R['expected_s2']=R.balanced.map({True:'YES',False:'NO'})
order={'RNN':0,'LSTM':1,'GRU':2,'BILSTM':3,'PATCHTST':4,'MANTIS_V2':5}
R=R.sort_values(['task','model','window','pipeline'],key=lambda s:s.map(order) if s.name=='model' else s).reset_index(drop=True)
# 1 consumption
bal=R[R.balanced]
S2M={}
import glob
for f in glob.glob('<B34_DIR>/src/seed44/*.json'):
    d=json.load(open(f)); S2M[(d['task'],d['window_id'],d['balance_pipeline'])]=d
rows=[]
for (t,w,p),g in bal.groupby(['task','window','pipeline']):
    s=S2M[(t,w,p)]
    rows.append(dict(task=t,window=w,pipeline=p,s2_run_id=g.s2_run_id.iloc[0],n_model_runs_using_it=len(g),
        models_using_it=';'.join(sorted(g.model,key=order.get)),s2_attempt_id=g.s2_attempt_id.iloc[0],
        s2_in_set_seed44_17429_20261114=bool((g.ref_in_set72).all()),s2_parent_pipeline=s['parent_pipeline'],s2_algorithm=s['algorithm_config']['algorithm'],
        s2_rows_balanced=s['rows_balanced'],model_runs_train_rows_equal_s2=int((g.rows_equal==True).sum()),model_runs_with_train_rows=int(g.train_rows.notna().sum()),
        recorded_reference='input_download_manifest_sha256 of run_manifest.json -> download_manifest_%s_seed44.json -> remote_path of train/%s/%s'%(t,w,p),
        evidence_level='INDIRECT_VIA_DOWNLOAD_MANIFEST_SHA256'))
C=pd.DataFrame(rows).sort_values(['task','window','pipeline'],key=lambda s:s.str.replace('V','').astype(int) if s.name=='pipeline' else s)
C.to_csv(f'{O}/s2_seed44_consumption.csv',index=False,lineterminator='\n')
# S2 set coverage
cov=set(C[['task','window','pipeline']].itertuples(index=False,name=None)); print('cells',len(cov),'of 72; all in set:',C.s2_in_set_seed44_17429_20261114.all(),'; n_runs per cell',C.n_model_runs_using_it.value_counts().to_dict())
# 2 outside set
out=R[(R.balanced)&(R.link_status!='LINKED_VIA_DOWNLOAD_MANIFEST')|(R.balanced&~(R.ref_in_set72==True))]
out2=out[['task','model','window','pipeline']].copy(); out2['recorded_s2_reference']=out.apply(lambda r:f'download_manifest_sha256={r.dm_sha_recorded}; link_status={r.link_status}; s2_run_id={r.s2_run_id}',axis=1)
out2.to_csv(f'{O}/s2_seed44_runs_outside_set.csv',index=False,lineterminator='\n'); print('outside',len(out2))
# 3 without s2 field
w=R[['task','model','window','pipeline','expected_s2','direct_s2_field_in_run_manifest','manifest_schema','train_input_recorded','dm_sha_recorded','link_status']].rename(columns={'dm_sha_recorded':'input_download_manifest_sha256_recorded'})
w.to_csv(f'{O}/s2_seed44_runs_without_s2_field.csv',index=False,lineterminator='\n'); print('without field',len(w))
# per run
pr=R[['task','model','window','pipeline','expected_s2','manifest_schema','tar','manifest_member','train_input_recorded','train_rows','parent_pipeline','created_at_utc','dm_sha_recorded','ok_dm_sha','ok_path','ref_in_set72','rows_equal','parent_equal','after_s2','s2_run_id','s2_attempt_id','train_sha256_recorded','mantis_train_sha256_vs_local_s2_parquet','link_status']]
pr.to_csv(f'{O}/s2_seed44_per_run_link.csv',index=False,lineterminator='\n')
R.to_pickle(f'{B}/final.pkl')
print(R.link_status.value_counts().to_dict()); print(R.mantis_train_sha256_vs_local_s2_parquet.value_counts(dropna=False).to_dict())
print(R[~R.balanced].ok_dm_sha.value_counts().to_dict(), R[(~R.balanced)].groupby(['task','model']).ok_dm_sha.apply(lambda s:(~s).sum()).loc[lambda s:s>0].to_dict())
print('bal rows_equal', bal.rows_equal.value_counts(dropna=False).to_dict(), 'after_s2',bal.after_s2.value_counts(dropna=False).to_dict())
print(bal.created_at_utc.min(), bal.created_at_utc.max())
