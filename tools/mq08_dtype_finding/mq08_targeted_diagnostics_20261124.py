"""Exploratory controls on two folds; fixed registered parameters, no retuning."""
from pathlib import Path
import json,sys,time
import numpy as np,pandas as pd
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'tmp/metamodel_handoff_20261121'))
from metamodel import experiment as E,features as F,schema as S,learners as L
base=root/'CQ/resuilt/mm_runs_phaseC_r2_20261123/full_main_cal_time';out=root/'CQ/resuilt/mq08_targeted_diagnostics_20261124';out.mkdir(parents=True,exist_ok=True)
cfg=E.MMConfig(**json.loads((base/'mm_config.json').read_text(encoding='utf8')));meta=pd.read_parquet(root/'CQ/resuilt/meta_release_CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2/meta_dataset_seed_agg.parquet');df,names=E.prepare_frame(meta,cfg)
reg=pd.read_parquet(base/'mm_run_registry.parquet');orig=pd.read_parquet(base/'mm_recommendations.parquet'); records=[];summ=[]
targets={('E1-B','LO:W1W2->W3'),('E3','CQ:holdout:F2_TS_TRANSFORMER')}
for protocol in cfg.protocols:
 for fold,task,_ in E._fold_units(df,protocol,cfg):
  if (protocol,fold.fold_id) not in targets:continue
  train=df[fold.train];test=df[fold.test];test=test[test[E.MAIN_COL].astype(bool)]
  p=reg[(reg.protocol==protocol)&(reg.fold_id==fold.fold_id)&(reg.strategy=='L3-FS3')];assert len(p)==1;params=json.loads(p.iloc[0].best_params)
  original=orig[(orig.protocol==protocol)&(orig.fold_id==fold.fold_id)&(orig.strategy=='L3-FS3')].set_index('rec_group_id')
  cols=[c for c in F.select_columns(train.columns,'FS3',drop_task=fold.drop_task) if S.role_of(c)[1]=='X_STATE']; groups=pd.unique(train.rec_group_id); first=train.groupby('rec_group_id')[cols].first();context=train.groupby('rec_group_id',sort=False).first().reindex(groups)
  # Stratification is exploratory and preserves task, subgroup, window, phase;
  # model is allowed to change within a stratum. Small singleton strata stay fixed.
  strata=['task','subgroup_axis','subgroup_value','window_id','phase_id'];strat=context[strata].astype(str).agg('|'.join,axis=1).to_numpy()
  for mode in ('registered_unrestricted','stratified_context'):
   for perm_seed in range(5):
    start=time.monotonic();rng=np.random.default_rng(perm_seed)
    if mode=='registered_unrestricted':shuffled=rng.permutation(groups)
    else:
     shuffled=groups.copy()
     for key in pd.unique(strat):
      idx=np.flatnonzero(strat==key);shuffled[idx]=rng.permutation(groups[idx])
    mapping=dict(zip(groups,shuffled));perm=train.copy();perm[cols]=first.loc[pd.Series(perm.rec_group_id).map(mapping).to_numpy()].to_numpy()
    pre=F.Preprocessor('FS3',drop_task=fold.drop_task).fit(perm);xt=pre.transform(perm);xe=pre.transform(test);scores=[]
    for seed in cfg.learner_seeds:scores.append(L.MetaLearner('L3',params=params,seed=seed).fit(xt,perm.y,groups=perm.rec_group_id,eps=cfg.eps).score(xe))
    scored=test.copy();scored['score']=np.vstack(scores).mean(axis=0);outcomes,summary=E._evaluate_scored(scored,names,cfg);j=outcomes.set_index('rec_group_id').join(original[['regret','pipeline_recommended']],rsuffix='_original',validate='one_to_one');assert len(j)==len(original)
    for gid,r in j.iterrows():records.append({'protocol':protocol,'fold_id':fold.fold_id,'mode':mode,'permutation_seed':perm_seed,'rec_group_id':gid,'regret_permuted':r.regret,'regret_original':r.regret_original,'delta':r.regret-r.regret_original,'pipeline_permuted':r.pipeline_recommended,'pipeline_original':r.pipeline_recommended_original,'task':r.task,'model_name':r.model_name,'phase_id':r.phase_id})
    summ.append({'protocol':protocol,'fold_id':fold.fold_id,'mode':mode,'permutation_seed':perm_seed,'n_groups':len(j),'n_changed_groups':int((shuffled!=groups).sum()),'delta_mean':float((j.regret-j.regret_original).mean()),'n_improved':int((j.regret<j.regret_original-1e-12).sum()),'n_worse':int((j.regret>j.regret_original+1e-12).sum()),'n_tied':int((abs(j.regret-j.regret_original)<=1e-12).sum()),'seconds':round(time.monotonic()-start,1)})
    pd.DataFrame(summ).to_csv(out/'summary_partial.csv',index=False);pd.DataFrame(records).to_csv(out/'per_group_partial.csv',index=False)
    print(protocol,fold.fold_id,mode,perm_seed,'delta',summ[-1]['delta_mean'],flush=True)
pd.DataFrame(summ).to_csv(out/'summary.csv',index=False);pd.DataFrame(records).to_csv(out/'per_group.csv',index=False)
(out/'README.md').write_text('Exploratory only: two folds; five group permutations, five learner seeds, fixed registered hyperparameters. Stratified control preserves task, subgroup axis/value, window, phase and shuffles model group within stratum; singleton strata fixed. Compare per-group regret to frozen original. Does not replace registered MQ08 or support inferential claims.\n',encoding='utf8')
print('COMPLETE',len(summ),flush=True)
