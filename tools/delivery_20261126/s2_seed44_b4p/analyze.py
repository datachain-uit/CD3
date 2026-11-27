import json, glob, os, hashlib, re
import pandas as pd
B='<WORK_DIR>'
plan=pd.read_csv(f'{B}/run_tar_plan.csv')
# --- manifests
recs=[]
for d in sorted(glob.glob(f'{B}/raw/t*.done')):
    meta=json.load(open(d)); i=os.path.basename(d)[1:4]
    for n,name in enumerate(meta['members']):
        m=json.load(open(f'{B}/raw/t{i}__{n}.json'))
        recs.append(dict(tar=meta['tar'],member=name,m=m))
mf={}
for r in recs:
    m=r['m']
    if m.get('seed')!=44: continue
    mant='model_name' not in m
    model='MANTIS_V2' if mant else m['model_name']
    k=(m['task'],model,m['window_id'] if not mant else m['window'],m['pipeline_id'] if not mant else m['pipeline'])
    r['mantis']=mant
    mf.setdefault(k,[]).append(r)
# --- S2 set
S2={}
for f in glob.glob('<B34_DIR>/src/seed44/*.json'):
    d=json.load(open(f)); S2[(d['task'],d['window_id'],d['balance_pipeline'])]=d
assert len(S2)==72
DM={t:json.load(open(f'{B}/dm_{t}_seed44.json')) for t in ('CQ','LO')}
DMSHA={t:'sha256:'+hashlib.sha256(open(f'{B}/dm_{t}_seed44.json','rb').read()).hexdigest() for t in DM}
DMREF={}
for t,d in DM.items():
    for f in d['files']:
        if f['kind']=='train':
            mm=re.search(r'run_id=([0-9a-f]+)/attempt_id=([^/]+)/',f['remote_path'])
            DMREF[(t,f['window_id'],f['pipeline_id'])]=(mm.group(1),mm.group(2),f['remote_path'],f['local_path'])
BAL={f'V{i}' for i in (2,3,4,6,7,8,10,11,12,14,15,16)}
rows=[]
for r in plan.itertuples():
    k=(r.task,r.model_name,r.window_id,r.pipeline_id)
    c=mf.get(k,[])
    pick=[x for x in c if x['tar']==r.tar] or c
    base=dict(task=r.task,model=r.model_name,window=r.window_id,pipeline=r.pipeline_id,balanced=r.pipeline_id in BAL,n_manifests_found=len(c),tar=r.tar.split('/')[-1])
    if not pick:
        base.update(status='MANIFEST_NOT_FOUND'); rows.append(base); continue
    m=pick[0]['m']
    mant=pick[0]['mantis']
    ip=m.get('input_paths',{}).get('train') if not mant else None

    s2fields=[x for x in m if re.search(r's2|sampling|augment|balanc|parent_run|source_train',x,re.I)]
    base.update(manifest_member=pick[0]['member'],train_path_recorded=ip,train_path_local_rel=ip.split('seed44/',1)[-1] if ip else None,train_rows=m.get('train_rows'),manifest_schema='mantis_cache_manifest' if mant else 'vastai_train_shared',
        dm_sha_recorded=('sha256:'+m['download_manifest_sha256']) if mant else m.get('input_download_manifest_sha256'),parent_pipeline=m.get('parent_pipeline') or m.get('parent'),seed_augmentation=m.get('seed_augmentation'),
        train_sha256_recorded=(m.get('input_sha256') or {}).get('train'),
        created_at_utc=m.get('created_at_utc'),s2_named_fields=';'.join(s2fields),
        has_explicit_s2_field=any(re.search(r's2|sampling_plan|source_train|s2_run',x,re.I) for x in m))
    rows.append(base)
R=pd.DataFrame(rows)
R.to_pickle(f"{B}/runs.pkl")
print(R.status.value_counts() if 'status' in R else '', R.shape, R.n_manifests_found.value_counts().to_dict())
print(R.has_explicit_s2_field.value_counts(dropna=False).to_dict()); print(R.s2_named_fields.value_counts().head())
print(R.groupby(['task','dm_sha_recorded']).size())

# ---------------- linking
def link(r):
    if r.get('status')=='MANIFEST_NOT_FOUND': return pd.Series(dict(link_status='MANIFEST_NOT_FOUND'))
    t=r.task; mant=r.manifest_schema=='mantis_cache_manifest'
    ok_dm=(r.dm_sha_recorded==DMSHA[t])
    if not r.balanced:
        ok_path=True if mant else bool(re.search(r'/train/'+r.window+'/'+r.pipeline+r'/train\.parquet$',r.train_path_recorded or ''))
        return pd.Series(dict(link_status='NOT_BALANCED_NO_S2_NEEDED' if ok_path else 'NOT_BALANCED_UNEXPECTED_PATH',ok_dm_sha=ok_dm))
    key=(t,r.window,r.pipeline)
    s2=S2.get(key); ref=DMREF.get(key)
    ok_path=True if mant else bool(re.search(r'/train/'+r.window+'/'+r.pipeline+r'/balanced_train\.parquet$',r.train_path_recorded or ''))
    ref_in=bool(ref and s2 and ref[0]==s2['run_id'] and ref[1]==s2['attempt_id'])
    rows_ok=None if mant else bool(s2 and r.train_rows==s2['rows_balanced'])
    par_ok=bool(s2 and r.parent_pipeline==s2['parent_pipeline'])
    ts_ok=None if mant else bool(s2 and r.created_at_utc and r.created_at_utc[:19]>s2['resource_summary']['created_at_utc'][:19])
    good=ok_path and ok_dm and ref_in and par_ok and (rows_ok in (True,None))
    return pd.Series(dict(link_status='LINKED_VIA_DOWNLOAD_MANIFEST' if good else 'CHECK_FAILED',ok_path=ok_path,ok_dm_sha=ok_dm,ref_in_set72=ref_in,rows_equal=rows_ok,parent_equal=par_ok,after_s2=ts_ok,
        s2_run_id=ref[0] if ref else None,s2_attempt_id=ref[1] if ref else None))
L=R.apply(link,axis=1); R=pd.concat([R,L],axis=1)
R.to_pickle(f'{B}/runs_linked.pkl')
print(R.link_status.value_counts())
print(R.groupby(['task','model']).size().unstack())
print(R[R.balanced].groupby('link_status')[['ok_path','ok_dm_sha','ref_in_set72','rows_equal','parent_equal','after_s2']].agg(lambda x:x.sum()))
print(R.groupby('manifest_schema').size()); print(R.n_manifests_found.value_counts())
