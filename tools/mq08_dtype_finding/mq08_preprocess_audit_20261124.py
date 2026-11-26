from pathlib import Path
import json,sys
import numpy as np,pandas as pd
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'tmp/metamodel_handoff_20261121'))
from metamodel import experiment as E,features as F,schema as S
base=root/'CQ/resuilt/mm_runs_phaseC_r2_20261123/full_main_cal_time';out=root/'CQ/resuilt/mq08_preprocess_audit_20261124';out.mkdir(parents=True,exist_ok=True)
cfg=E.MMConfig(**json.loads((base/'mm_config.json').read_text()));df,_=E.prepare_frame(pd.read_parquet(root/'CQ/resuilt/meta_release_CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2/meta_dataset_seed_agg.parquet'),cfg);folds=[];columns=[]
for protocol in cfg.protocols:
 for fold,task,_ in E._fold_units(df,protocol,cfg):
  tr=df[fold.train];te=df[fold.test];te=te[te[E.MAIN_COL].astype(bool)];cols=[c for c in F.select_columns(tr.columns,'FS3',drop_task=fold.drop_task) if S.role_of(c)[1]=='X_STATE'];groups=tr.rec_group_id.to_numpy();uniq=pd.unique(groups);rng=np.random.default_rng(0);mapping=dict(zip(uniq,rng.permutation(uniq)));first=tr.groupby('rec_group_id')[cols].first();mapped=first.loc[pd.Series(groups).map(mapping).to_numpy()];permuted=tr.copy();permuted[cols]=mapped.to_numpy();fixed=tr.copy()
  for c in cols:fixed[c]=pd.Series(mapped[c].array,index=fixed.index).astype(tr[c].dtype)
  basepre=F.Preprocessor('FS3',drop_task=fold.drop_task).fit(tr);badpre=F.Preprocessor('FS3',drop_task=fold.drop_task).fit(permuted);goodpre=F.Preprocessor('FS3',drop_task=fold.drop_task).fit(fixed)
  changed=[c for c in cols if tr[c].dtype!=permuted[c].dtype]
  for c in changed:
   if c not in badpre.categorical_:continue
   vals=te[c].astype(str);known=vals.isin(badpre.categories_.get(c,[]));nonnull=te[c].notna();denom=int(nonnull.sum())
   columns.append({'protocol':protocol,'fold_id':fold.fold_id,'column':c,'old_dtype':str(tr[c].dtype),'permuted_dtype':str(permuted[c].dtype),'n_train_categories':len(badpre.categories_[c]),'n_test_nonnull':denom,'n_test_nonnull_unseen':int((nonnull & ~known).sum()),'test_nonnull_unseen_fraction':float((nonnull & ~known).sum()/denom) if denom else None})
  folds.append({'protocol':protocol,'fold_id':fold.fold_id,'state_columns':len(cols),'state_dtype_changes':len(changed),'original_output_features':len(basepre.output_columns_),'official_control_output_features':len(badpre.output_columns_),'dtype_preserved_control_output_features':len(goodpre.output_columns_),'test_rows':len(te),'state_columns_categorical_in_official_control':sum(c in badpre.categorical_ for c in changed)})
  print(protocol,fold.fold_id,'dtypes',len(changed),'features',len(basepre.output_columns_),len(badpre.output_columns_),len(goodpre.output_columns_),flush=True)
pd.DataFrame(folds).to_csv(out/'fold_preprocess_comparison.csv',index=False);pd.DataFrame(columns).to_csv(out/'per_column_unseen_categories.csv',index=False)
print('COMPLETE',len(folds),len(columns),flush=True)
