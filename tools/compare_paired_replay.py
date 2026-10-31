"""Compare two run predictions by source enrollment using each run's private salt."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd

def main():
    p=argparse.ArgumentParser(); p.add_argument('--baseline',type=Path,required=True); p.add_argument('--replay',type=Path,required=True)
    p.add_argument('--evaluation-root',type=Path,required=True); p.add_argument('--baseline-salt-file',type=Path,required=True)
    p.add_argument('--replay-salt-file',type=Path,required=True); p.add_argument('--output',type=Path,required=True)
    args=p.parse_args(); paths=(args.baseline,args.replay)
    salts=[x.read_text(encoding='utf8') for x in (args.baseline_salt_file,args.replay_salt_file)]
    if any(not x for x in salts): raise ValueError('Salt file is empty')
    manifests=[json.loads((x/'run_manifest.json').read_text(encoding='utf8')) for x in paths]
    fields=['task','window_id','pipeline_id','model_name','seed','batch_size','micro_batch_size','accumulation_steps',
            'data_release_id','split_version','phase_version','feature_layout_sha256','learning_rate','warmup_epochs','gradient_clip_norm','best_epoch']
    if any(manifests[0].get(k)!=manifests[1].get(k) for k in fields): raise ValueError('Run contracts differ')
    rows=[]
    for split in ('validation','test'):
        for phase in ('P1','P2','P3','P4'):
            source=args.evaluation_root/('validation.parquet' if split=='validation' else f'test_{phase}.parquet')
            ids=pd.read_parquet(source,columns=['enrollment_id']).enrollment_id
            if ids.isna().any() or ids.duplicated().any(): raise ValueError(f'Invalid source IDs: {source}')
            aligned=[]
            for path,salt in zip(paths,salts):
                frame=pd.read_parquet(path/'predictions'/f'{split}_{phase}.parquet')
                if frame.enrollment_id_hash.duplicated().any() or len(frame)!=len(ids): raise ValueError('Prediction grain differs')
                hashes=ids.astype(str).map(lambda x:hashlib.sha256(f'{salt}|{x}'.encode()).hexdigest())
                frame=frame.set_index('enrollment_id_hash').reindex(hashes)
                if frame.y_true.isna().any(): raise ValueError('Unmatched IDs')
                aligned.append(frame.reset_index(drop=True))
            a,b=aligned; equal_true=a.y_true.equals(b.y_true); equal_pred=a.y_pred.equals(b.y_pred)
            delta=max(float(np.max(np.abs(a[c].to_numpy()-b[c].to_numpy()))) for c in ('prob_c0','prob_c1','prob_c2'))
            if not np.isfinite(delta): raise ValueError('Non-finite probability delta')
            rows.append({'split':split,'phase':phase,'rows':len(ids),'labels_equal':equal_true,'predictions_equal':equal_pred,'max_probability_delta':delta})
    result={'baseline_commit':manifests[0].get('runner_git_commit'),'replay_commit':manifests[1].get('runner_git_commit'),
            'contract_fields_equal':fields,'paired_exact':all(x['labels_equal'] and x['predictions_equal'] and x['max_probability_delta']==0 for x in rows),'cells':rows}
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps(result,indent=2))
if __name__=='__main__': main()
