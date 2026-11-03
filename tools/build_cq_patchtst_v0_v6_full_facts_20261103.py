"""Collect verified CQ PatchTST V0–V6 facts; never export private salts."""
from pathlib import Path
from io import BytesIO
import hashlib,json,tarfile
import pandas as pd

ROOT=Path('CQ/resuilt'); OUT=ROOT/'cq_patchtst_v0_v6_full_facts_20261103'
NAMES={1:'cq_patchtst_v1_seed42_20261031',2:'cq_patchtst_v2_seed42_20261101',3:'cq_patchtst_v3_seed42_20261101',4:'cq_patchtst_v4_seed42_20261101',5:'cq_patchtst_v5_seed42_20261101',6:'cq_patchtst_v6_seed42_20261101'}
AUDITS=['sanity_components','evaluation_slices','metrics_per_class','bootstrap_metrics_per_class','checkpoint_selection']
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''): h.update(b)
    return h.hexdigest()
def save(frame,name):
    frame.to_parquet(OUT/(name+'.parquet'),index=False)
    frame.to_csv(OUT/(name+'.csv'),index=False)
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    frames={k:[] for k in AUDITS};runs=[];sources=[]
    v0audit=ROOT/'cq_patchtst_v0_current_seed42_r21_audit/CQ/PATCHTST/seed=42'
    for n in AUDITS: frames[n].append(pd.read_parquet(v0audit/(n+'.parquet')))
    for p in (ROOT/'cq_patchtst_v0_current_seed42_r21').rglob('run_manifest.json'):
        m=json.loads(p.read_text(encoding='utf8')); h=pd.read_parquet(p.parent/'train_history.parquet'); m['train_seconds']=float(h.train_seconds.sum());runs.append(m)
    for i,name in NAMES.items():
        receipt=json.loads((ROOT/name/'download_receipt.json').read_text(encoding='utf8')); archive=Path(receipt['archive']); digest=sha(archive)
        if digest!=receipt['sha256'] or receipt['status']!='download_verified':raise ValueError(f'V{i}: bad checksum')
        sources.append({'version':f'V{i}','archive':str(archive),'sha256':digest})
        manifests={};histories={};found=set()
        with tarfile.open(archive,'r:gz') as tar:
            for member in tar:
                if not member.isfile():continue
                p=Path(member.name); stem=p.stem
                if '_audit/' in member.name and stem in AUDITS and p.suffix=='.parquet':
                    frames[stem].append(pd.read_parquet(BytesIO(tar.extractfile(member).read())));found.add(stem)
                elif '/CQ/W' in member.name and p.name in ('run_manifest.json','train_history.parquet'):
                    key=str(p.parent).replace('\\','/')
                    if p.name=='run_manifest.json': manifests[key]=json.load(tar.extractfile(member))
                    else: histories[key]=pd.read_parquet(BytesIO(tar.extractfile(member).read()))
        if set(manifests)!=set(histories) or len(manifests)!=3 or found!=set(AUDITS):raise ValueError(f'V{i}: incomplete artifacts')
        for key,m in manifests.items():m['train_seconds']=float(histories[key].train_seconds.sum());runs.append(m)
        print('verified',name,flush=True)
    combined={name:pd.concat(items,ignore_index=True) for name,items in frames.items()}
    expected={'sanity_components':168,'evaluation_slices':504,'metrics_per_class':504,'bootstrap_metrics_per_class':1512,'checkpoint_selection':21}
    for name,n in expected.items():
        if len(combined[name])!=n:raise ValueError(f'{name}: expected {n}, got {len(combined[name])}')
    sanity=combined['sanity_components']; sanity['acctempo_m4']=sanity.s_perf.clip(lower=1e-3).pow(.6)*sanity.s_san_plus_v2.clip(lower=1e-3).pow(.4)
    for name,frame in combined.items():save(frame,name)
    m=pd.DataFrame(runs)
    keys=['task','model_name','window_id','pipeline_id','seed','train_seconds','elapsed_seconds','gpu','batch_size','micro_batch_size','accumulation_steps','energy_measurement_type','energy_gpu_estimated_kwh','energy_sample_count','energy_sample_attempt_count','energy_missing_sample_rate','energy_sampling_duration_s','energy_boundary','execution_backend','runner_git_commit','feature_layout_sha256']
    for k in keys:
        if k not in m:m[k]=None
    resources=m[keys]
    if len(resources)!=21 or resources.train_seconds.isna().any() or resources.duplicated(['pipeline_id','window_id']).any():raise ValueError('resource coverage failed')
    save(resources,'resource_per_run')
    (OUT/'source_inventory.json').write_text(json.dumps(sources,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'counts':expected,'resources':len(resources),'energy_types':resources.energy_measurement_type.fillna('NULL').value_counts().to_dict()},indent=2),flush=True)
if __name__=='__main__':main()
