"""Build the registered five-subgroup release; stop on either acceptance failure."""
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
PKG=ROOT/'tmp/metamodel_handoff_20261121'
TMP=ROOT/'tmp/s0_v5_inputs'
PACKAGES=TMP/'subgroup_facts'
REF=TMP/'accepted_children'
STATE=Path(os.environ['TEMPO_S0_PROFILE']) if os.environ.get('TEMPO_S0_PROFILE') else ROOT/'CQ/resuilt/m13a_s0_profile_20261122_v5/s0_profile.parquet'
CTX=ROOT/'CQ/resuilt/m13b_z_m_delivery_20261109_v2/z_m.csv'
RELEASE=os.environ.get('TEMPO_5SUBGROUP_RELEASE_ID','CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r1')
if RELEASE not in ('CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r1','CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2'):
    raise ValueError('unregistered release ID')
REV=RELEASE.rsplit('_',1)[-1]
OUT=ROOT/'CQ/resuilt'/('meta_release_'+RELEASE)
CHILD=ROOT/'tmp/s0_v5_inputs'/('children_5subgroups_'+REV)
FAMILIES=('RNN','LSTM','GRU','BILSTM')


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()


def old_files(task):
    cq=ROOT/'CQ/resuilt'; lo=ROOT/'LO/resuilt'
    if task=='CQ':
        facts=[Path(os.environ.get('TEMPO_M14C_ROOT', ROOT/'tmp/m14c'))/'cq_r4_with_regime_macro.parquet',cq/'cq_patchtst_v0_v6_full_facts_20261103_r2/sanity_components.csv',cq/'cq_patchtst_v7_v16_full_facts_20261109_r2/sanity_components.csv',cq/'cq_mantis_v2_v0_v16_full_facts_20261109_r3/sanity_components.csv']
        res=[ROOT/'upload_staging/m09/r4/cq_resource_per_run.parquet',cq/'cq_patchtst_v0_v6_full_facts_20261103_r2/resource_per_run.csv',cq/'cq_patchtst_v7_v16_full_facts_20261109_r2/resource_per_run.csv',cq/'cq_mantis_v2_v0_v16_full_facts_20261109_r3/resource_per_run.csv']
        keys=['task=CQ','label_rule_version=cq_vector_proximity_v1_zero_activity_policy','label_threshold_set=CQ_VECTOR_PROXIMITY_PRIMARY_V1','feature_regime=CQ_RAW_EARLY']
    else:
        facts=[Path(os.environ.get('TEMPO_M14C_ROOT', ROOT/'tmp/m14c'))/'lo_static_v2_facts_no_confusion.parquet',lo/'lo_patchtst_v0_v16_full_facts_20261109_r2/sanity_components.csv',lo/'lo_mantis_v2_v0_v16_full_facts_20261110/sanity_components.csv']
        res=[lo/'lo_static_v2_grid_seed42_20261102/lo_resource_per_run.parquet',lo/'lo_patchtst_v0_v16_full_facts_20261109_r2/resource_per_run.csv',lo/'lo_mantis_v2_v0_v16_full_facts_20261110/resource_per_run.csv']
        keys=['task=LO','label_rule_version=lo_final_score_catalog_normalized_v3_1','label_threshold_set=CATALOG_NORMALIZED_PRIMARY_V3_1__EXCLUDE_NO_SCORED_SIGNAL','feature_regime=LO_FULL_EARLY']
    for seed in (43,44):
        base=Path(os.environ.get('TEMPO_SEED43_FACTS_ROOT', ROOT/'tmp/seed43_facts')) if seed==43 else Path(os.environ.get('TEMPO_SEED44_FACTS_ROOT', ROOT/'tmp/seed44_facts'))
        prefix=task+'_'
        suff='' if seed==43 else '_v0_v16_seed44'
        f1=base/(prefix+'f1_recurrent'+suff); pt=base/(prefix+'patchtst'+suff); mt=base/(prefix+'mantis_v2'+suff)
        facts += [f1/f/'sanity_components.csv' for f in FAMILIES]+[pt/'sanity_components.csv',mt/'sanity_components.csv']
        res += [f1/f/'resource_per_run.csv' for f in FAMILIES]+[pt/'resource_per_run.csv',mt/'resource_per_run.csv']
    return facts,res,keys


def main():
    if OUT.exists() or CHILD.exists(): raise FileExistsError('output already exists; preserve prior attempt')
    if not STATE.is_file(): raise FileNotFoundError('S0 v5 not complete')
    verified=ROOT/'CQ/resuilt/s0_v5_subgroup_preflight_20261122/subgroup_packages_verification.json'
    if json.loads(verified.read_text(encoding='utf8'))['status']!='PASS': raise ValueError('subgroup package verification failed')
    inputs={'state':str(STATE),'context':str(CTX)}
    for task in ('CQ','LO'):
        facts,res,keys=old_files(task)
        subs=sorted(PACKAGES.glob(f'{task}_*_seed*_subgroups_20261121/subgroup_components.parquet'))
        if len(subs)!=18: raise ValueError(f'{task}: expected 18 subgroup packages, got {len(subs)}')
        required=facts+res+subs+[STATE,CTX,REF/f'{task}_3seed/meta_dataset_seed_level.parquet',REF/f'{task}_3seed/meta_dataset_seed_agg.parquet']
        missing=[str(x) for x in required if not x.is_file()]
        if missing: raise FileNotFoundError('\n'.join(missing))
        inputs.update({f'{task}_fact_{i}':str(x) for i,x in enumerate(facts+subs)})
        inputs.update({f'{task}_resource_{i}':str(x) for i,x in enumerate(res)})
        cmd=[sys.executable,'-m','metamodel.cli','assemble','--facts']+[str(x) for x in facts+subs]+['--resources']+[str(x) for x in res]+['--state',str(STATE),'--model-context',str(CTX)]
        if task=='CQ':
            f0=ROOT/'CQ/resuilt/f0_cq_partial_triad_20261108/f0_cq_partial_triad.csv'
            if not f0.is_file(): raise FileNotFoundError(f0)
            cmd+=['--f0',str(f0)]; inputs['f0_cq']=str(f0)
        for key in keys: cmd+=['--key',key]
        cmd+=['--registry',str(PKG/'tempo_fix/examples/registries_v1.6'),'--planned-seeds','42','43','44',
              '--release-id',('CQ_V2_2_full_seeds42_43_44' if task=='CQ' else 'LO_V3_1_full_seeds42_43_44'),
              '--require-subgroups','--compare-all-with',str(REF/f'{task}_3seed'),'--out',str(CHILD/f'{task}_3seed')]
        CHILD.mkdir(parents=True,exist_ok=True)
        with (CHILD/f'{task}_assemble.log').open('w',encoding='utf8') as log:
            p=subprocess.run(cmd,cwd=PKG,stdout=log,stderr=subprocess.STDOUT,env=os.environ.copy())
        print(f'{task} assemble exit={p.returncode}',flush=True)
        if p.returncode: raise SystemExit(p.returncode)
        m=json.loads((CHILD/f'{task}_3seed/meta_release_manifest.json').read_text(encoding='utf8'))
        if m['n_rows_seed_level']!=36720 or not m['subgroup_report']['ok']: raise ValueError(f'{task}: coverage/subgroup gate failed')
    OUT.mkdir(parents=True,exist_ok=False)
    seed=pd.concat([pd.read_parquet(CHILD/f'{t}_3seed/meta_dataset_seed_level.parquet') for t in ('CQ','LO')],ignore_index=True,sort=False)
    agg=pd.concat([pd.read_parquet(CHILD/f'{t}_3seed/meta_dataset_seed_agg.parquet') for t in ('CQ','LO')],ignore_index=True,sort=False)
    if len(seed)!=73440: raise ValueError(f'wrong combined rows: {len(seed)}')
    for name,frame in [('meta_dataset_seed_level',seed),('meta_dataset_seed_agg',agg)]:
        for col in frame.columns[frame.dtypes=='object']:
            frame[col]=frame[col].map(lambda v:json.dumps(v.tolist() if hasattr(v,'tolist') else v) if isinstance(v,(list,tuple)) or hasattr(v,'tolist') else v)
        frame.to_parquet(OUT/f'{name}.parquet',index=False)
    dictionaries=[pd.read_csv(CHILD/f'{t}_3seed/meta_column_dictionary.csv') for t in ('CQ','LO')]
    dictionary=pd.concat(dictionaries,ignore_index=True)
    for field in ('role','block'):
        if dictionary.groupby('column_name')[field].nunique().gt(1).any(): raise ValueError(f'dictionary conflict {field}')
    dictionary=dictionary.groupby('column_name',sort=False).agg(block=('block','first'),role=('role','first'),nullable=('nullable','max')).reset_index()
    dictionary['dtype']=dictionary.column_name.map(lambda c:str(seed[c].dtype) if c in seed.columns else '')
    dictionary[['column_name','block','role','dtype','nullable']].to_csv(OUT/'meta_column_dictionary.csv',index=False)
    parts=OUT/'seed_level_parts'; parts.mkdir()
    index=[]; rebuilt=[]
    for (task,axis,value,master_seed),group in seed.groupby(['task','subgroup_axis','subgroup_value','seed'],sort=True,dropna=False):
        name=f'{task}__{axis}__{value}__seed{master_seed}.parquet'; path=parts/name
        group.to_parquet(path,index=False)
        if path.stat().st_size>=10_000_000: raise ValueError(f'part exceeds 10MB: {path}')
        index.append({'file':name,'rows':len(group),'bytes':path.stat().st_size,'sha256':sha(path)})
        rebuilt.append(pd.read_parquet(path))
    if len(index)!=30: raise ValueError(f'expected 30 parts, got {len(index)}')
    joined=pd.concat(rebuilt,ignore_index=True).sort_values('meta_obs_id').reset_index(drop=True)
    pd.testing.assert_frame_equal(joined,seed.sort_values('meta_obs_id').reset_index(drop=True),check_dtype=False,check_exact=True)
    (parts/'parts_manifest.json').write_text(json.dumps({'parts':index,'reconstructed_exact':True},indent=2)+'\n',encoding='utf8')
    manifest={'meta_release_id':RELEASE,'created_at_utc':datetime.now(timezone.utc).isoformat(),'n_rows_seed_level':len(seed),'n_rows_seed_agg':len(agg),
              'subgroups':seed.groupby(['subgroup_axis','subgroup_value']).size().to_dict(),
              'children':{t:sha(CHILD/f'{t}_3seed/meta_release_manifest.json') for t in ('CQ','LO')},
              'inputs_sha256':{k:{'path':p,'sha256':sha(Path(p))} for k,p in inputs.items()},'s0_v5_sha256':sha(STATE)}
    manifest['subgroups']={'|'.join(k):v for k,v in manifest['subgroups'].items()}
    (OUT/'meta_release_manifest.json').write_text(json.dumps(manifest,indent=2,default=str)+'\n',encoding='utf8')
    (OUT/'RUN_LOG.md').write_text('# Five-subgroup release\n\nBoth child assemblies passed --require-subgroups and --compare-all-with.\nS0 v5 retains 48 original ALL rows; 30 seed-level parts reconstruct the full table.\nB.5 remains required.\n',encoding='utf8')
    (OUT/'sha256sums.txt').write_text(''.join(f'{sha(p)}  {p.relative_to(OUT).as_posix()}\n' for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='sha256sums.txt'),encoding='utf8')
    print(f'RELEASE_READY rows={len(seed)} seed_agg={len(agg)}',flush=True)


if __name__=='__main__':main()
