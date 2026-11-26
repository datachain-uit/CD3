from pathlib import Path
import json,sys
import numpy as np,pandas as pd
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'tmp/metamodel_handoff_20261121'))
from metamodel import experiment as E,features as F,schema as S,learners as L
base=root/'CQ/resuilt/mm_runs_phaseC_r2_20261123/full_main_cal_time';out=root/'CQ/resuilt/mq08_targeted_diagnostics_20261124'
cfg=E.MMConfig(**json.loads((base/'mm_config.json').read_text(encoding='utf8')));meta=pd.read_parquet(root/'CQ/resuilt/meta_release_CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2/meta_dataset_seed_agg.parquet');df,names=E.prepare_frame(meta,cfg)
reg=pd.read_parquet(base/'mm_run_registry.parquet');pred=pd.read_parquet(base/'mm_predictions.parquet');orig=pd.read_parquet(base/'mm_recommendations.parquet');rows=[]
targets={('E1-B','LO:W1W2->W3'),('E3','CQ:holdout:F2_TS_TRANSFORMER')}
for protocol in cfg.protocols:
 for fold,task,_ in E._fold_units(df,protocol,cfg):
  if (protocol,fold.fold_id) not in targets:continue
  train=df[fold.train];test_all=df[fold.test];test=test_all[test_all[E.MAIN_COL].astype(bool)];rr=reg[(reg.protocol==protocol)&(reg.fold_id==fold.fold_id)&(reg.strategy=='L3-FS3')];params=json.loads(rr.iloc[0].best_params)
  pre=F.Preprocessor('FS3',drop_task=fold.drop_task).fit(train);xt=pre.transform(train);xe=pre.transform(test)
  scores=[L.MetaLearner('L3',params=params,seed=seed).fit(xt,train.y,groups=train.rec_group_id,eps=cfg.eps).score(xe) for seed in cfg.learner_seeds]
  scored=test.copy();scored['score']=np.vstack(scores).mean(axis=0);_,summ=E._evaluate_scored(scored,names,cfg)
  pp=pred[(pred.protocol==protocol)&(pred.fold_id==fold.fold_id)&(pred.strategy=='L3-FS3')].set_index('meta_obs_id');a=scored.set_index('meta_obs_id').join(pp[['score']],rsuffix='_original',validate='one_to_one');original=orig[(orig.protocol==protocol)&(orig.fold_id==fold.fold_id)&(orig.strategy=='L3-FS3')]
  cols=[c for c in F.select_columns(train.columns,'FS3',drop_task=fold.drop_task) if S.role_of(c)[1]=='X_STATE'];groups=pd.unique(train.rec_group_id);first=train.groupby('rec_group_id')[cols].first();context=train.groupby('rec_group_id',sort=False).first().reindex(groups);strat=context[['task','subgroup_axis','subgroup_value','window_id','phase_id']].astype(str).agg('|'.join,axis=1).to_numpy();rng=np.random.default_rng(0);shuffled=groups.copy()
  for k in pd.unique(strat):
   idx=np.flatnonzero(strat==k);shuffled[idx]=rng.permutation(groups[idx])
  mp=dict(zip(groups,shuffled));new=first.loc[pd.Series(train.rec_group_id).map(mp).to_numpy()].reset_index(drop=True);old=train[cols].reset_index(drop=True)
  diff=~((old.eq(new))|(old.isna()&new.isna()));perm=train.copy();perm[cols]=new.to_numpy();changed=[{'column':c,'original':str(train[c].dtype),'permuted':str(perm[c].dtype)} for c in cols if train[c].dtype!=perm[c].dtype];pre2=F.Preprocessor('FS3',drop_task=fold.drop_task).fit(perm);rows.append({'protocol':protocol,'fold_id':fold.fold_id,'score_max_abs_delta_vs_frozen':float((a.score-a.score_original).abs().max()),'replayed_regret':float(summ['mean_regret']),'frozen_regret':float(original.regret.mean()),'stratified_changed_state_cells':int(diff.to_numpy().sum()),'stratified_changed_state_columns':int(diff.any(axis=0).sum()),'dtype_changes':len(changed),'dtype_changes_detail':json.dumps(changed),'original_features':len(pre.output_columns_),'permuted_features':len(pre2.output_columns_),'original_dropped':json.dumps(pre.dropped_),'permuted_dropped':json.dumps(pre2.dropped_)})
pd.DataFrame(rows).to_csv(out/'identity_refit_check.csv',index=False);print(pd.DataFrame(rows).to_string(index=False))
