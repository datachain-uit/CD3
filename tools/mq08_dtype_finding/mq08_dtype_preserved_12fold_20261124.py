from pathlib import Path
import json,sys
import numpy as np,pandas as pd
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'tmp/metamodel_handoff_20261121'))
from metamodel import experiment as E,features as F,schema as S,learners as L
base=root/'CQ/resuilt/mm_runs_phaseC_r2_20261123/full_main_cal_time';out=root/'CQ/resuilt/mq08_dtype_preserved_12fold_20261124';out.mkdir(parents=True,exist_ok=True)
cfg=E.MMConfig(**json.loads((base/'mm_config.json').read_text()));df,names=E.prepare_frame(pd.read_parquet(root/'CQ/resuilt/meta_release_CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2/meta_dataset_seed_agg.parquet'),cfg)
reg=pd.read_parquet(base/'mm_run_registry.parquet');nc=pd.read_parquet(base/'mm_negative_control.parquet');rows=[]
for protocol in cfg.protocols:
 for fold,task,_ in E._fold_units(df,protocol,cfg):
  train=df[fold.train];te=df[fold.test];te=te[te[E.MAIN_COL].astype(bool)]
  r=reg[(reg.protocol==protocol)&(reg.fold_id==fold.fold_id)&(reg.strategy=='L3-FS3')].iloc[0];o=nc[(nc.protocol==protocol)&(nc.fold_id==fold.fold_id)].iloc[0];params=json.loads(r.best_params)
  replay=E._negative_control(train,te,names,cfg,params,fold.drop_task,seed=0);assert abs(replay['mean_regret_permuted']-o.mean_regret_permuted)<1e-10
  cols=[c for c in F.select_columns(train.columns,'FS3',drop_task=fold.drop_task) if S.role_of(c)[1]=='X_STATE'];groups=train.rec_group_id.to_numpy();unique=pd.unique(groups);rng=np.random.default_rng(0);mapping=dict(zip(unique,rng.permutation(unique)));first=train.groupby('rec_group_id')[cols].first();mapped=first.loc[pd.Series(groups).map(mapping).to_numpy()];perm=train.copy()
  for col in cols:perm[col]=pd.Series(mapped[col].array,index=perm.index).astype(train[col].dtype)
  assert all(perm[col].dtype==train[col].dtype for col in cols)
  pre=F.Preprocessor('FS3',drop_task=fold.drop_task).fit(perm);m=L.MetaLearner('L3',params=params,seed=0).fit(pre.transform(perm),perm.y,groups=perm.rec_group_id,eps=cfg.eps);scored=te.copy();scored['score']=m.score(pre.transform(te));_,summary=E._evaluate_scored(scored,names,cfg)
  val=float(summary['mean_regret']);rows.append({'protocol':protocol,'fold_id':fold.fold_id,'original_model_regret_5seed':float(o.mean_regret_model),'official_control_regret_1seed':float(o.mean_regret_permuted),'dtype_preserved_control_regret_1seed':val,'original_pass':bool(o.MQ08_pass),'dtype_preserved_pass':bool(val>=o.mean_regret_model),'control_regret_delta':val-float(o.mean_regret_permuted),'dtype_preserved_n_features':len(pre.output_columns_)})
  pd.DataFrame(rows).to_csv(out/'folds_partial.csv',index=False);print(protocol,fold.fold_id,'original',bool(o.MQ08_pass),'preserved',val>=o.mean_regret_model,flush=True)
pd.DataFrame(rows).to_csv(out/'folds.csv',index=False);print('COMPLETE',len(rows),flush=True)
