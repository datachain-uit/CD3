import os as _os
# Machine roots come from environment variables (no machine paths in the repository).
REPO = _os.environ.get('TEMPO_REPO_ROOT', '.')
WORK = _os.environ.get('TEMPO_WORK_ROOT', '.')
AUDIT44 = _os.environ.get('TEMPO_AUDIT44_ROOT', '.')
WORKD = _os.environ.get('TEMPO_DELIVERY_WORK_ROOT', '.')
import pandas as pd, hashlib, glob, numpy as np
inv=pd.read_parquet(f'{WORK}/tree/inventory_all.parquet')
print(inv.columns.tolist(), len(inv))
base=f'{REPO}/CQ/resuilt/input/results/R21_evidence_20261031/LO/audit_seed42/'
def md5(p): return hashlib.md5(open(p,'rb').read()).hexdigest()
inv['md5']=inv['md5'].astype(str)
byname=inv[inv.path.str.contains('LO') & inv.path.str.contains('seed=42')]
m={}
for mod,sub in (('RNN','RNN'),('LSTM','LSTM'),('GRU','GRU'),('BILSTM','audits_seed42')):
    for t in ('evaluation_slices','metrics_per_class','bootstrap_metrics_per_class','sanity_components'):
        p=f'{base}{sub}/LO/{mod}/seed=42/{t}.parquet' if sub!='audits_seed42' else f'{base}audits_seed42/LO/{mod}/seed=42/{t}.parquet'
        h=md5(p)
        hits=inv[inv.md5==h]
        print(mod,t,h[:8],[ (r.root,r.path) for r in hits.itertuples()][:4])
fa=pd.read_parquet(f'{WORK}/m14c/lo_static_v2_facts_no_confusion.parquet')
print(fa.model_name.value_counts().to_dict())
for mod,sub in (('RNN','RNN'),('LSTM','LSTM'),('GRU','GRU'),('BILSTM','audits_seed42')):
    p=f'{base}{sub}/LO/{mod}/seed=42/evaluation_slices.parquet'
    es=pd.read_parquet(p); a=es[es.slice=='ALL']
    f=fa[fa.model_name==mod]
    k=['window_id','pipeline_id','phase_id','eval_split']
    mm=a.merge(f,on=k,suffixes=('_a','_f'))
    print(mod,len(a),len(f),len(mm),'macro_f1 maxdiff',np.nanmax(np.abs(mm.macro_f1_a-mm.macro_f1_f)),'s_leak diff',np.nanmax(np.abs(mm.s_leak_a-mm.s_leak_f)))
