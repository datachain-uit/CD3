from pathlib import Path
import json,sys
import numpy as np,pandas as pd
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'tmp/metamodel_handoff_20261121'))
from metamodel import experiment as E,features as F,schema as S
base=root/'CQ/resuilt/mm_runs_phaseC_r2_20261123';meta=pd.read_parquet(root/'CQ/resuilt/meta_release_CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2/meta_dataset_seed_agg.parquet')
spec=json.loads((base/'frozen_configurations_r2.json').read_text(encoding='utf8'));rows=[]; problems=[]
for c in spec['runs']:
 name=c['name'];d=base/name;cfg=E.MMConfig(**json.loads((d/'mm_config.json').read_text(encoding='utf8')));df,_=E.prepare_frame(meta,cfg);nc=pd.read_parquet(d/'mm_negative_control.parquet')
 for protocol in cfg.protocols:
  for fold,task,_ in E._fold_units(df,protocol,cfg):
   rec=nc[(nc.protocol==protocol)&(nc.fold_id==fold.fold_id)]
   if len(rec)!=1:problems.append(f'{name}/{protocol}/{fold.fold_id}: rows={len(rec)}');continue
   rec=rec.iloc[0];orig=float(rec.mean_regret_model);perm=float(rec.mean_regret_permuted)
   if not np.isfinite(orig) or not np.isfinite(perm):problems.append(f'{name}/{protocol}/{fold.fold_id}: nonfinite')
   if bool(rec.MQ08_pass)!=bool(perm>=orig):problems.append(f'{name}/{protocol}/{fold.fold_id}: flag mismatch')
   train=df[fold.train]
   if cfg.small_subgroup_policy=='DROP_FROM_TRAINING':train=train[train[E.TRAIN_OK_COL].astype(bool)]
   cols=[x for x in F.select_columns(train.columns,'FS3',drop_task=fold.drop_task) if S.role_of(x)[1]=='X_STATE']
   grouped=train.groupby('rec_group_id',dropna=False)[cols].nunique(dropna=False)
   varying=(grouped>1); maxgroups=int(varying.any(axis=1).sum());varcols=int(varying.any(axis=0).sum())
   groupmeta=train.groupby('rec_group_id',sort=False).first();rng=np.random.default_rng(0);groups=pd.unique(train.rec_group_id);dest=pd.DataFrame({'dst':groups,'src':rng.permutation(groups)});a=groupmeta.reindex(dest.dst);b=groupmeta.reindex(dest.src)
   cross={}
   for field in ['task','subgroup_axis','subgroup_value','window_id','model_name','phase_id']:
    if field in groupmeta:cross[field]=int((a[field].to_numpy()!=b[field].to_numpy()).sum())
   rows.append({'config':name,'protocol':protocol,'fold_id':fold.fold_id,'n_state_columns':len(cols),'train_groups':len(groups),'groups_with_within_group_state_variation':maxgroups,'state_columns_varying_within_group':varcols,'permutation_cross_group_counts':json.dumps(cross,sort_keys=True),'official_regret':orig,'permuted_regret':perm,'delta':perm-orig,'official_pass':bool(rec.MQ08_pass)})
 print(name,'done',flush=True)
out=root/'CQ/resuilt/mq08_investigation_all_20261124';out.mkdir(parents=True,exist_ok=True);pd.DataFrame(rows).to_csv(out/'official_fold_audit.csv',index=False)
(out/'summary.json').write_text(json.dumps({'configurations':len(spec['runs']),'folds':len(rows),'problems':problems,'folds_with_within_group_state_variation':sum(r['groups_with_within_group_state_variation']>0 for r in rows)},indent=2)+'\n',encoding='utf8')
if problems:raise ValueError(problems)
print('complete',len(rows),flush=True)
