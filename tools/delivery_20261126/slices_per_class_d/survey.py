import os as _os
# Machine roots come from environment variables (no machine paths in the repository).
REPO = _os.environ.get('TEMPO_REPO_ROOT', '.')
WORK = _os.environ.get('TEMPO_WORK_ROOT', '.')
AUDIT44 = _os.environ.get('TEMPO_AUDIT44_ROOT', '.')
WORKD = _os.environ.get('TEMPO_DELIVERY_WORK_ROOT', '.')
import sys; sys.path.insert(0,f'{WORKD}/code')
import registry,hashlib,json
import pandas as pd
BS=chr(92)
man=json.load(open(f'{REPO}/CQ/resuilt/meta_release_CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2/meta_release_manifest.json'))['inputs_sha256']
acc={v['path'].replace(BS,'/'):v['sha256'] for v in man.values()}
def sh(p): return hashlib.sha256(open(p,'rb').read()).hexdigest()
for k,v in registry.units().items():
    out=[]
    for d,_ in v['dirs']:
        n={}
        for t in registry.TABLES:
            p=d/f'{t}.parquet'
            n[t]=len(pd.read_parquet(p)) if p.exists() else None
        out.append((d.name[-30:],n))
    s=''
    if v['accepted_sanity']:
        ap=str(v['accepted_sanity']).replace(BS,'/')
        exp=acc.get(ap)
        got=sh(v['sanity_in']) if v['sanity_in'].exists() else None
        s='SANITY '+('OK' if exp==got else f'MISMATCH exp={exp} got={got} ap={ap}')
    print(k,s,out)
