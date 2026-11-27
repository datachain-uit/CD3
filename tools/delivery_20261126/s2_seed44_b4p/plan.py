import pandas as pd, re, sys
sys.path.insert(0,'<REPO>/tools/subgroups_phaseB')
W='<TEMPO_WORK_ROOT>'
cat=pd.read_parquet(f'{W}/phaseB/pred_files_unified.parquet'); cat=cat[cat.seed==44]
live={t:set(open(f'<WORK_DIR>/live_{t}.txt').read().split()) for t in ('CQ','LO')}
class M(dict):
    def get(self,p,d=None):
        t=p.split('/')[0]; rel=p.split('S3_model/',1)[1]
        return f'{t}/L1_runs/S3_model/seed=44/{rel}' if rel in live[t] else None
mp=M()
TRUNC={'lo_patchtst_seed44_V2_host40077.tar','LO_static_v2_BILSTM.tar'}
PREFER=['primary/release=LO_STATIC_V2','primary/family=PATCHTST','cq_recurrent_batch2048_seed42','cq_lstm_batch2048_full','cq_rnn_historical_layout_batch2048','mantis_v2_seed','staging_incoming']
DENY=['pilot','determinism','replay','ablation','/vastai/','vastai_runs','matched_historical','baseline_drive','nvml_historical','cohort_audit','host_backups']
def rank(p):
    if any(d in p for d in DENY): return 2
    return 0 if any(x in p for x in PREFER) else 1
rows=[]
for k,g in cat.groupby(['task','model_name','window_id','pipeline_id']):
    c=set()
    for r in g.itertuples():
        n=mp.get(r.path); 
        if n: c.add(n)
    c=sorted(c,key=lambda x:(x.split('/')[-1] in TRUNC,rank(x),x))
    rows.append((*k,len(c),c[0] if c else None,';'.join(c)))
d=pd.DataFrame(rows,columns=['task','model_name','window_id','pipeline_id','ncand','tar','allcand'])
print(len(d),d.tar.isna().sum(),d.tar.nunique()); print(d.ncand.value_counts())
d.to_csv('<WORK_DIR>/run_tar_plan.csv',index=False)
print(d.tar.value_counts().head(5)); print(d.tar.str.extract(r'seed=44/([^/]+)/')[0].value_counts())
