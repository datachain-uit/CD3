"""Exploratory negative-control only; never overwrite registered phase C."""
import json,os,sys,time
from pathlib import Path
import numpy as np
import pandas as pd

root=Path(__file__).resolve().parents[1]; pkg=root/'tmp/metamodel_handoff_20261121';sys.path.insert(0,str(pkg))
from metamodel import experiment as E, features as F, schema as S, learners as L
base=root/'CQ/resuilt/mm_runs_phaseC_r2_20261123/full_main_cal_time'
out=root/'CQ/resuilt/mq08_sensitivity_main_20261124';out.mkdir(parents=True,exist_ok=True)
cfg=E.MMConfig(**json.loads((base/'mm_config.json').read_text(encoding='utf8')))
meta=pd.read_parquet(root/'CQ/resuilt/meta_release_CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2/meta_dataset_seed_agg.parquet')
df,names=E.prepare_frame(meta,cfg)
registry=pd.read_parquet(base/'mm_run_registry.parquet');official=pd.read_parquet(base/'mm_negative_control.parquet')
rows=[]
for protocol in cfg.protocols:
 for fold,task,_ in E._fold_units(df,protocol,cfg):
  tr=df[fold.train];test_all=df[fold.test];test=test_all[test_all[E.MAIN_COL].astype(bool)]
  rr=registry[(registry.protocol==protocol)&(registry.fold_id==fold.fold_id)&(registry.strategy=='L3-FS3')]
  oo=official[(official.protocol==protocol)&(official.fold_id==fold.fold_id)]
  if len(rr)!=1 or len(oo)!=1:raise ValueError('registry ambiguity')
  params=json.loads(rr.iloc[0].best_params); official_row=oo.iloc[0]
  # Reproduce the locked single-seed control first as an implementation check.
  replay=E._negative_control(tr,test,names,cfg,params,fold.drop_task,seed=0)
  if abs(replay['mean_regret_permuted']-official_row.mean_regret_permuted)>1e-10:raise ValueError(f'official replay mismatch {protocol} {fold.fold_id}')
  state=[c for c in F.select_columns(tr.columns,'FS3',drop_task=fold.drop_task) if S.role_of(c)[1]=='X_STATE']
  groups=tr.rec_group_id.to_numpy();unique=pd.unique(groups);first=tr.groupby('rec_group_id')[state].first()
  for perm_seed in range(5):
   start=time.monotonic();rng=np.random.default_rng(perm_seed);mapping=dict(zip(unique,rng.permutation(unique)))
   perm=tr.copy(); perm[state]=first.loc[pd.Series(groups).map(mapping).to_numpy()].to_numpy()
   pre=F.Preprocessor('FS3',drop_task=fold.drop_task).fit(perm); xt=pre.transform(perm); xe=pre.transform(test)
   scores=[]
   for seed in cfg.learner_seeds:
    model=L.MetaLearner('L3',params=params,seed=seed).fit(xt,perm.y,groups=perm.rec_group_id,eps=cfg.eps)
    scores.append(model.score(xe))
   scored=test.copy();scored['score']=np.vstack(scores).mean(axis=0)
   _,summary=E._evaluate_scored(scored,names,cfg)
   rows.append({'protocol':protocol,'fold_id':fold.fold_id,'permutation_seed':perm_seed,'learner_seeds':len(cfg.learner_seeds),'n_train_rows':len(tr),'n_test_rows':len(test),'regret_original_5seed':float(official_row.mean_regret_model),'regret_permuted_5seed':float(summary['mean_regret']),'regret_delta_permuted_minus_original':float(summary['mean_regret']-official_row.mean_regret_model),'official_single_seed_regret':float(official_row.mean_regret_permuted),'official_mq08_pass':bool(official_row.MQ08_pass),'official_replay_abs_diff':abs(replay['mean_regret_permuted']-official_row.mean_regret_permuted),'elapsed_seconds':round(time.monotonic()-start,2)})
   pd.DataFrame(rows).to_csv(out/'permutation_results_partial.csv',index=False)
   print(protocol,fold.fold_id,'perm',perm_seed,'delta',rows[-1]['regret_delta_permuted_minus_original'],flush=True)
pd.DataFrame(rows).to_csv(out/'permutation_results.csv',index=False)
(out/'README.md').write_text('# MQ08 exploratory sensitivity\nFive group permutations (seeds 0–4), five model seeds (0–4), fixed phase-C L3-FS3 selected parameters; score ensemble then regret on ALL. Each fold first replays official single-seed control. Not registered, does not replace MQ08, no causal claim.\n',encoding='utf8')
print('COMPLETE',len(rows),flush=True)
