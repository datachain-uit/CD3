import hashlib,json,math,os
from pathlib import Path
import pandas as pd
import numpy as np

root=Path(os.environ.get('TEMPO_REPO_ROOT', Path(__file__).resolve().parents[2]))
out=root/'CQ/resuilt/mm_runs_phaseC_r2_20261123'
data=root/'CQ/resuilt/meta_release_CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2/meta_dataset_seed_agg.parquet'
spec=json.loads((out/'frozen_configurations_r2.json').read_text(encoding='utf8'))
progress=(out/'progress.log').read_text(encoding='utf8')
assert 'PHASE_C_ALL_COMPLETE' in progress
target={'PAPER_COMPOSITE_CAL':'acctempo_m3_cal_delta_mean','META_PRIMARY_M3_V1':'acctempo_m3_delta_mean','PAPER_PERF_AXIS':'s_perf_delta_mean','SECONDARY_MACRO_F1':'macro_f1_delta_mean'}
meta=pd.read_parquet(data); assert meta.meta_obs_id_agg.is_unique
ref=meta.set_index('meta_obs_id_agg'); results=[]; errors=[]
required=['mm_fold_composition','mm_metrics_joint','mm_metrics_secondary','mm_recommendations_secondary','mm_run_registry','mm_predictions','mm_hypotheses','mm_negative_control','mm_metrics','mm_recommendations','mm_split_manifest']
for c in spec['runs']:
 name=c['name']; p=out/name
 if f'END {name} rc=0' not in progress:errors.append(name+':missing successful exit')
 if (p/'mm_config_sha256.txt').read_text().strip()!=c['mm_config_sha256']:errors.append(name+':digest mismatch')
 expected_empty=[]
 for table in required:
  if not (p/f'{table}.parquet').is_file():
   if name=='var_all_only_main' and table in ('mm_metrics_secondary','mm_recommendations_secondary'):expected_empty.append(table)
   else:errors.append(name+':missing '+table)
 cfg=json.loads((p/'mm_config.json').read_text(encoding='utf8'))
 if cfg['meta_release_id']!=spec['release_id']:errors.append(name+':release id mismatch')
 pred=pd.read_parquet(p/'mm_predictions.parquet'); reg=pd.read_parquet(p/'mm_run_registry.parquet'); nc=pd.read_parquet(p/'mm_negative_control.parquet'); hyp=pd.read_parquet(p/'mm_hypotheses.parquet')
 expected=ref[target[cfg['objective']]].reindex(pred.meta_obs_id).to_numpy(dtype=float)
 actual=pred.y.to_numpy(dtype=float); missing=int(np.isnan(expected).sum()); diff=float(np.nanmax(np.abs(expected-actual))) if len(actual) else 0
 if missing or diff>1e-10:errors.append(f'{name}: prediction target mismatches missing={missing} max={diff}')
 statuses=reg.status.fillna('<NULL>').value_counts().to_dict()
 unexpected={str(k):int(v) for k,v in statuses.items() if k!='OK' and not str(k).startswith('SKIPPED')}
 if unexpected:errors.append(f'{name}: unexpected registry statuses {unexpected}')
 ncfail=nc[nc.MQ08_pass.eq(False)] if 'MQ08_pass' in nc else pd.DataFrame()
 results.append({'name':name,'objective':cfg['objective'],'digest':c['mm_config_sha256'],'prediction_rows':len(pred),'target_missing':missing,'target_max_abs_diff':diff,'registry_statuses':{str(k):int(v) for k,v in statuses.items()},'missing_secondary_tables_all_only':expected_empty,'mq08_fail_count':len(ncfail),'mq08_fail_folds':ncfail[['protocol','fold_id']].to_dict('records') if len(ncfail) else [],'hypothesis_statuses':hyp.status.fillna('<NULL>').value_counts().to_dict(),'primary_rows':int(hyp.analysis_role.eq('PRIMARY').sum())})
 print(name,'pred',len(pred),'target_max',diff,'status',statuses,'MQ08 fail',len(ncfail),flush=True)
summary={'status':'PASS_STRUCTURAL' if not errors else 'FAIL','errors':errors,'configs':results}
(out/'qa_phaseC_20261124.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False,default=str)+'\n',encoding='utf8')
if errors:raise ValueError(errors)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
parts=out/'large_file_parts';parts.mkdir(exist_ok=True); index=[]
for p in sorted(out.rglob('*')):
 if not p.is_file() or parts in p.parents or p.stat().st_size<=10_000_000:continue
 folder=parts/p.relative_to(out).parent/p.name;folder.mkdir(parents=True,exist_ok=True); pieces=[]
 with p.open('rb') as f:
  i=0
  while b:=f.read(9_000_000):
   i+=1; piece=folder/f'part_{i:04d}';piece.write_bytes(b);pieces.append({'path':piece.relative_to(out).as_posix(),'bytes':len(b),'sha256':sha(piece)})
 index.append({'original':p.relative_to(out).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p),'parts':pieces})
(parts/'parts_manifest.json').write_text(json.dumps(index,indent=2)+'\n',encoding='utf8')
(out/'RUN_LOG.md').write_text('# Pha C r2 — RUN LOG\n\n10/10 cấu hình exit 0; xem progress.log. Digest, cấu hình, hash đầu vào và môi trường được lưu trong gói. QA cấu trúc và đối chiếu y xem qa_phaseC_20261124.json; MQ08 chưa đạt được ghi riêng, không coi là đạt. Biến thể var_all_only_main chỉ đọc ALL nên không có hai bảng secondary; runner không xuất bảng rỗng. File >10 MB được chia byte thành các phần dưới 10 MB, thứ tự và SHA-256 trong large_file_parts/parts_manifest.json. Chạy xong không đồng nghĩa QA khoa học đã đạt hoặc đã nghiệm thu.\n',encoding='utf8')
files=sorted(p for p in out.rglob('*') if p.is_file() and p.name!='SHA256SUMS.txt')
(out/'SHA256SUMS.txt').write_text(''.join(f'{sha(p)}  {p.relative_to(out).as_posix()}\n' for p in files),encoding='utf8')
print('DONE',len(files),'large_files',len(index),flush=True)
