"""User-authorized post-hoc MQ08 rerun only; frozen phase-C output unchanged."""
import hashlib,json,os,sys,time
from pathlib import Path
import numpy as np,pandas as pd
root=Path(__file__).resolve().parents[1];pkg=root/'tmp/metamodel_handoff_20261121';sys.path.insert(0,str(pkg))
from metamodel import experiment as E,features as F,schema as S,learners as L
base=root/'CQ/resuilt/mm_runs_phaseC_r2_20261123';out=root/'CQ/resuilt/mq08_dtype_fix_all_configs_20261124'
if out.exists():raise FileExistsError(out)
out.mkdir(parents=True);spec=json.loads((base/'frozen_configurations_r2.json').read_text());meta_path=root/'CQ/resuilt/meta_release_CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2/meta_dataset_seed_agg.parquet';meta=pd.read_parquet(meta_path)
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(4194304),b''):h.update(b)
 return h.hexdigest()
inputs={'release_seed_agg_sha256':sha(meta_path),'frozen_configurations_sha256':sha(base/'frozen_configurations_r2.json'),'runner_source_sha256':sha(pkg/'metamodel/experiment.py'),'diagnostic_source_sha256':sha(Path(__file__))}
(out/'input_sha256.json').write_text(json.dumps(inputs,indent=2)+'\n');rows=[]
for c in spec['runs']:
 name=c['name'];run=base/name;cfg=E.MMConfig(**json.loads((run/'mm_config.json').read_text()));assert (run/'mm_config_sha256.txt').read_text().strip()==c['mm_config_sha256']
 df,names=E.prepare_frame(meta,cfg);registry=pd.read_parquet(run/'mm_run_registry.parquet');official=pd.read_parquet(run/'mm_negative_control.parquet')
 count=0
 for protocol in cfg.protocols:
  for fold,task,_ in E._fold_units(df,protocol,cfg):
   if not df[E.TRAIN_OK_COL].astype(bool).all():fold.train=fold.train & df[E.TRAIN_OK_COL].astype(bool)
   train=df[fold.train];alltest=df[fold.test];test=alltest[alltest[E.MAIN_COL].astype(bool)]
   rr=registry[(registry.protocol==protocol)&(registry.fold_id==fold.fold_id)&(registry.strategy=='L3-FS3')]; oo=official[(official.protocol==protocol)&(official.fold_id==fold.fold_id)]
   if len(rr)!=1 or len(oo)!=1:raise ValueError(f'{name}/{protocol}/{fold.fold_id}: ambiguous registry')
   params=json.loads(rr.iloc[0].best_params); old=oo.iloc[0];t=time.monotonic()
   replay=E._negative_control(train,test,names,cfg,params,fold.drop_task,seed=0);replay_diff=abs(replay['mean_regret_permuted']-old.mean_regret_permuted)
   if not np.isfinite(replay_diff) or replay_diff>1e-10:raise ValueError(f'{name}/{protocol}/{fold.fold_id}: locked control replay mismatch {replay_diff}')
   cols=[col for col in F.select_columns(train.columns,'FS3',drop_task=fold.drop_task) if S.role_of(col)[1]=='X_STATE'];groups=train.rec_group_id.to_numpy();unique=pd.unique(groups);rng=np.random.default_rng(0);mapping=dict(zip(unique,rng.permutation(unique)));first=train.groupby('rec_group_id')[cols].first();mapped=first.loc[pd.Series(groups).map(mapping).to_numpy()];perm=train.copy()
   for col in cols:perm[col]=pd.Series(mapped[col].array,index=perm.index).astype(train[col].dtype)
   if any(perm[col].dtype!=train[col].dtype for col in cols):raise ValueError('dtype preservation failed')
   pre=F.Preprocessor('FS3',drop_task=fold.drop_task).fit(perm); model=L.MetaLearner('L3',params=params,seed=0).fit(pre.transform(perm),perm.y,groups=perm.rec_group_id,eps=cfg.eps);scored=test.copy();scored['score']=model.score(pre.transform(test));_,summary=E._evaluate_scored(scored,names,cfg)
   val=float(summary['mean_regret']);rows.append({'config':name,'protocol':protocol,'fold_id':fold.fold_id,'official_digest':c['mm_config_sha256'],'official_model_regret_5seed':float(old.mean_regret_model),'official_control_regret_1seed':float(old.mean_regret_permuted),'dtype_fixed_control_regret_1seed':val,'official_pass':bool(old.MQ08_pass),'dtype_fixed_pass':bool(val>=old.mean_regret_model),'control_regret_delta':val-float(old.mean_regret_permuted),'official_replay_abs_diff':replay_diff,'fixed_n_features':len(pre.output_columns_),'elapsed_seconds':round(time.monotonic()-t,2)})
   count+=1;pd.DataFrame(rows).to_csv(out/'results_partial.csv',index=False);print(name,protocol,fold.fold_id,'old',bool(old.MQ08_pass),'fixed',val>=old.mean_regret_model,flush=True)
 if count!=len(official):raise ValueError(f'{name}: coverage {count} vs {len(official)}')
print('COMPLETE',len(rows),flush=True)
dfout=pd.DataFrame(rows);assert len(dfout)==115 and not dfout.duplicated(['config','protocol','fold_id']).any();dfout.to_csv(out/'mq08_dtype_fixed_folds.csv',index=False)
summary=dfout.groupby('config',as_index=False).agg(n_folds=('fold_id','size'),official_pass=('official_pass','sum'),dtype_fixed_pass=('dtype_fixed_pass','sum'),control_max_abs_delta=('control_regret_delta',lambda x:float(x.abs().max())),official_replay_max_abs_diff=('official_replay_abs_diff','max'));summary.to_csv(out/'config_summary.csv',index=False)
(out/'README.md').write_text('# MQ08: kiểm lại giữ dtype, 10 cấu hình\n\nBản kiểm lại sau sửa do người dùng yêu cầu, tách khỏi pha C đã nghiệm thu. Chỉ hoán vị một lần seed 0, fit một learner seed 0 như MQ08 gốc; giữ dtype từng cột, tái sử dụng tham số đã chọn và score model chính thức năm seed. Mỗi fold tái lập số đối chứng chính thức trước; không train lại model cơ sở hay meta-grid. Kết quả không tự thay cờ chính thức hoặc protocol mới của phía viết. Chưa giải quyết bất đối xứng một seed đối chứng so với năm seed model gốc.\n',encoding='utf8')
files=sorted(p for p in out.iterdir() if p.is_file() and p.name!='SHA256SUMS.txt');(out/'SHA256SUMS.txt').write_text(''.join(f'{sha(p)}  {p.name}\n' for p in files),encoding='utf8')
