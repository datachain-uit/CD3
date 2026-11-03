"""Reconcile R4 slice metrics from saved predictions without caching Drive files.

ALL probability metrics are the immutable R4 values; separate recomputed ALL
columns and audit values are retained. STRICT/OVERLAP use the model metric
definitions on saved probabilities. Existing audit sanity composites remain
based on their original audit calibration convention.
"""
from pathlib import Path
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
import argparse,hashlib,json,os,subprocess,sys
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from model.metrics import calibration_metrics

JOBS=Path(os.environ.get('CD3_JOBS_ROOT','data/Jobs'))/'CQ/organized_moved_20261029'
REMOTE=os.environ.get('CD3_CQ_DRIVE_REMOTE','')
RCLONE=os.environ.get('RCLONE_EXE','rclone')
OUT=Path('CQ/resuilt/cq_r4_slices_reconciled_20261103')
K=['task','window_id','pipeline_id','model_name','seed','eval_split','phase_id']
ROOTS={'RNN':'cq_rnn_historical_layout_batch2048_seed42_20261020/CQ','LSTM':'cq_lstm_batch2048_full_20261018/lstm/CQ','GRU':'cq_recurrent_batch2048_seed42_20261019/gru/CQ','BILSTM':'cq_recurrent_batch2048_seed42_20261019/bilstm/CQ'}

def prediction_path(row):
    name=('validation' if row['eval_split']=='VALIDATION' else 'test')+'_'+row['phase_id']+'.parquet'
    return f"L1_runs/S3_model/preserved_packages/{ROOTS[row['model_name']]}/{row['window_id']}/{row['pipeline_id']}/seed=42/predictions/{name}"

def values(y,prob):
    if not len(y):return {'log_loss':None,'brier':None,'ece':None,'pr_auc_macro':None}
    cal=calibration_metrics(y,prob,np.arange(3));present=np.unique(y)
    ap=float(np.mean([average_precision_score((y==c).astype(int),prob[:,c]) for c in range(3) if np.any(y==c)])) if len(present)>=2 else None
    return {'log_loss':cal['multiclass_nll'],'brier':cal['multiclass_brier'],'ece':cal['top_label_ece_15'],'pr_auc_macro':ap}

def process(row):
    key='__'.join(str(row[x]) for x in ('model_name','pipeline_id','window_id','eval_split','phase_id'))
    target=OUT/'checkpoints'/f'{key}.json'
    if target.exists():
        previous=json.loads(target.read_text(encoding='utf8'))
        if all(previous['key'][k]==row[k] for k in K) and previous.get('source_sha256'):return key
        raise ValueError(f'{key}: existing checkpoint identity mismatch')
    remote=REMOTE.rstrip('/')+'/'+prediction_path(row)
    proc=subprocess.run([RCLONE,'cat',remote],capture_output=True,check=True,timeout=1800)
    raw=proc.stdout; frame=pd.read_parquet(BytesIO(raw),columns=['y_true','prob_c0','prob_c1','prob_c2','temporal_strict_'+row['phase_id']])
    y=frame.y_true.str.removeprefix('c').astype(int).to_numpy();prob=frame[['prob_c0','prob_c1','prob_c2']].to_numpy();strict=pd.to_numeric(frame['temporal_strict_'+row['phase_id']],errors='coerce').to_numpy()
    if not np.isin(strict,[0,1]).all() or len(frame)!=int(row['n_rows']):raise ValueError(f'{key}: invalid strict flag or row count')
    all_values=values(y,prob);mapped={'log_loss':'multiclass_nll','brier':'multiclass_brier','ece':'top_label_ece_15','pr_auc_macro':'pr_auc_macro'}
    errors={k:abs(float(all_values[k])-float(row[v])) for k,v in mapped.items() if all_values[k] is not None and pd.notna(row[v])}
    if errors and max(errors.values())>1e-6:raise ValueError(f'{key}: recomputation differs from R4 by {max(errors.values())}')
    data={'key':{k:row[k] for k in K},'source_prediction':prediction_path(row),'source_sha256':hashlib.sha256(raw).hexdigest(),'rows':len(frame),'recomputed_all':all_values,'recomputed_all_max_difference':max(errors.values(),default=0),'STRICT':values(y[strict==1],prob[strict==1]),'OVERLAP':values(y[strict==0],prob[strict==0]),'n_strict':int((strict==1).sum()),'n_overlap':int((strict==0).sum())}
    temp=target.with_suffix('.tmp');temp.write_text(json.dumps(data,allow_nan=False)+'\n',encoding='utf8');temp.replace(target)
    return key

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--pilot',action='store_true');parser.add_argument('--workers',type=int,default=4);parser.add_argument('--publish-remote',default='');args=parser.parse_args()
    if not REMOTE:raise ValueError('Set CD3_CQ_DRIVE_REMOTE to CQ organized_moved_20261029 remote root')
    r4=pd.read_parquet(JOBS/'L2_facts/fact_exports/cq_recurrent_allfamilies_grid_r4_20261023/cq_family_pipeline_window_phase_metrics.parquet')
    audit=JOBS/'L2_facts/fact_exports/cq_f1_allfamilies_l2_ingest_r3_20261021/audits/CQ'
    slices=pd.concat([pd.read_parquet(audit/f/'seed=42/evaluation_slices.parquet') for f in ROOTS],ignore_index=True)
    if len(r4)!=1632 or len(slices)!=4896 or r4.duplicated(K).any() or slices.duplicated(K+['slice']).any():raise ValueError('R4 or slice coverage invalid')
    allrows=slices[slices['slice']=='ALL'];comparison=r4.merge(allrows,on=K,validate='one_to_one',suffixes=('_r4','_audit'))
    for field in ('s_perf','s_nan','s_maj_jsd','s_ent','s_drift','s_eff','s_leak','s_san_plus','s_san_plus_v2','s_cal','acctempo_m3','c0_recall','c1_recall','c2_recall'):
        a=comparison[field+'_r4'];b=comparison[field+'_audit']
        if a.isna().ne(b.isna()).any() or ((a-b).abs().fillna(0)>1e-12).any():raise ValueError(f'ALL sanity/R4 mismatch: {field}')
    records=r4.to_dict('records')
    if args.pilot:records=[r for r in records if r['pipeline_id']=='V0' and r['window_id']=='W1' and r['eval_split']=='TEST' and r['phase_id']=='P1']
    (OUT/'checkpoints').mkdir(parents=True,exist_ok=True)
    done=0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures=[pool.submit(process,row) for row in records]
        for future in as_completed(futures):
            future.result();done+=1
            if done%25==0 or done==len(records):print(f'processed {done}/{len(records)}',flush=True)
    if args.pilot:print('PILOT_PASS: recomputed four-family W1/V0/TEST/P1 within 1e-6',flush=True);return
    index={tuple(row[k] for k in K):row for row in records};generated=[]
    for row in slices.to_dict('records'):
        key=tuple(row[k] for k in K); ref=index[key];name='__'.join(str(ref[x]) for x in ('model_name','pipeline_id','window_id','eval_split','phase_id'))
        data=json.loads((OUT/'checkpoints'/f'{name}.json').read_text(encoding='utf8'))
        for c in ('log_loss','brier','ece','pr_auc_macro'):row['audit_'+c]=row[c]
        typ=row['slice']
        if typ=='ALL':
            for dest,source in {'log_loss':'multiclass_nll','brier':'multiclass_brier','ece':'top_label_ece_15','pr_auc_macro':'pr_auc_macro'}.items():row[dest]=ref[source]
        else:
            expected=data['n_strict' if typ=='STRICT' else 'n_overlap']
            if int(row['n_eval_samples'])!=expected:raise ValueError(f'{name}/{typ}: count mismatch')
            row.update(data[typ])
        row['probability_metric_origin']='R4_STORED' if typ=='ALL' else 'RECOMPUTED_SAVED_PREDICTION_MODEL_CONVENTION'
        row['prediction_sha256']=data['source_sha256'];generated.append(row)
    result=pd.DataFrame(generated);result['acctempo_m4']=result.s_perf.clip(lower=.001).pow(.6)*result.s_san_plus_v2.clip(lower=.001).pow(.4)
    sizes=result.pivot(index=K,columns='slice',values='n_eval_samples')
    if not sizes.ALL.eq(sizes.STRICT+sizes.OVERLAP).all():raise ValueError('partition mismatch')
    matrices=result.pivot(index=K,columns='slice',values='confusion_matrix')
    for _,r in matrices.iterrows():
        def numeric_matrix(value):
            return np.asarray([np.asarray(row, dtype=np.int64) for row in value], dtype=np.int64)
        if not np.array_equal(numeric_matrix(r['ALL']),numeric_matrix(r['STRICT'])+numeric_matrix(r['OVERLAP'])):raise ValueError('confusion partition mismatch')
    result.to_parquet(OUT/'cq_evaluation_slices.parquet',index=False);result.to_csv(OUT/'cq_evaluation_slices.csv',index=False)
    meta={'created_at_utc':datetime.now(timezone.utc).isoformat(),'cells':len(r4),'rows':len(result),'partition_counts_and_matrices':'PASS','probability_metric_convention':'ALL copied from immutable R4; slices recomputed on saved predictions using model convention; audit probability metrics preserved in audit_* columns','sanity_composites':'unchanged original audit convention','recomputed_all_validation_tolerance':1e-6,'exact_all_r4':'PASS_BY_SOURCE'}
    (OUT/'summary.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf8')
    (OUT/'README.md').write_text('# CQ R4 slices — reconciled\n\nALL probability metrics originate directly in immutable R4; STRICT/OVERLAP use the model calculation on saved predictions. Original audit metrics remain as audit_*; sanity/calibration components remain from the original audit and therefore use its clipping convention. Predictions are streamed from Drive without storing raw data; prediction SHA-256 is included. ALL recalculation is checked within 1e-6 rather than claimed bitwise identical. Counts and confusion matrices partition exactly.\n',encoding='utf8')
    files=[OUT/'cq_evaluation_slices.parquet',OUT/'cq_evaluation_slices.csv',OUT/'summary.json',OUT/'README.md'];(OUT/'sha256sums.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in files),encoding='utf8');print(json.dumps(meta,indent=2),flush=True)
    if args.publish_remote:
        subprocess.run([RCLONE,'copy',str(OUT),args.publish_remote,'--exclude','checkpoints/**','--immutable'],check=True,timeout=3600)
        subprocess.run([RCLONE,'check',str(OUT),args.publish_remote,'--exclude','checkpoints/**','--one-way'],check=True,timeout=3600)
        print('PUBLISHED_AND_CHECKED',args.publish_remote,flush=True)
if __name__=='__main__':main()
