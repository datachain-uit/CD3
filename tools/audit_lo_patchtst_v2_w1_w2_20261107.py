"""Read-only integrity audit of downloaded LO V2 W1/W2 PatchTST artifacts."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'LO/resuilt/lo_patchtst_v2_w1_w2_20261107'
report={'task':'LO','pipeline':'V2','model':'PATCHTST','seed':42,'windows':{},'issues':[]}
for window in ('W1','W2'):
    run=BASE/window/'V2/PATCHTST/seed=42'
    manifest=json.loads((run/'run_manifest.json').read_text())
    layout=json.loads((run/'feature_layout.json').read_text())
    history=pd.read_parquet(run/'train_history.parquet')
    metrics=pd.read_parquet(run/'metrics_overall.parquet')
    issues=[]
    for k,v in {'task':'LO','window_id':window,'pipeline_id':'V2','model_name':'PATCHTST','seed':42,'batch_size':2048,'micro_batch_size':512,'accumulation_steps':4,'release_id':'LO_V3_1','static_layout_policy':'current'}.items():
        if manifest.get(k)!=v:issues.append(f'manifest {k} mismatch')
    actual='sha256:'+hashlib.sha256((run/'feature_layout.json').read_bytes()).hexdigest()
    if actual!=manifest.get('feature_layout_sha256'):issues.append('feature layout SHA mismatch')
    static=layout.get('static_columns',[])
    if any(x in static for x in ('split_rule_version','timeline_source')):issues.append('excluded static feature present')
    pairs={(str(r.eval_split),str(r.phase_id)) for r in metrics.itertuples()}
    expected={(s,f'P{p}') for s in ('TEST','VALIDATION') for p in range(1,5)}
    if len(metrics)!=8 or pairs!=expected:issues.append('metrics phase coverage')
    checks=[]
    for split in ('validation','test'):
        for p in range(1,5):
            phase=f'P{p}'; path=run/'predictions'/f'{split}_{phase}.parquet'
            frame=pd.read_parquet(path); target=manifest['validation_rows'] if split=='validation' else manifest['test_rows'][phase]
            m=metrics[(metrics.eval_split==split.upper()) & (metrics.phase_id==phase)]
            probs=frame[['prob_c0','prob_c1','prob_c2']].to_numpy(dtype=float)
            duplicates=int(frame.enrollment_id_hash.duplicated().sum()); null_ids=int(frame.enrollment_id_hash.isna().sum())
            expected_predictions=np.array(['c0','c1','c2'])[probs.argmax(axis=1)]
            argmax_mismatches=int(np.count_nonzero(frame.y_pred.to_numpy()!=expected_predictions))
            accuracy=float(accuracy_score(frame.y_true,frame.y_pred))
            macro_f1=float(f1_score(frame.y_true,frame.y_pred,labels=['c0','c1','c2'],average='macro',zero_division=0))
            metrics_match=(len(m)==1 and np.isclose(accuracy,m.iloc[0].accuracy,atol=1e-9) and np.isclose(macro_f1,m.iloc[0].f1_macro,atol=1e-9))
            ok=(len(frame)==target and len(m)==1 and int(m.iloc[0].n_rows)==target and duplicates==0 and null_ids==0 and argmax_mismatches==0 and metrics_match and np.isfinite(probs).all() and (probs>=-1e-7).all() and (probs<=1.0000001).all() and np.allclose(probs.sum(axis=1),1,atol=1e-5))
            if not ok:issues.append(f'prediction integrity {split}/{phase}')
            checks.append({'split':split,'phase':phase,'rows':len(frame),'expected_rows':target,'duplicate_hashes':duplicates,'null_hashes':null_ids,'argmax_mismatches':argmax_mismatches,'metrics_match':bool(metrics_match),'accuracy_recomputed':accuracy,'macro_f1_recomputed':macro_f1,'ok':bool(ok)})
    best=manifest.get('best_epoch')
    if not len(history) or best not in set(history['epoch']):issues.append('best epoch absent in history')
    required=['model.pt','metadata_contract.json','feature_layout.json','train_history.parquet','metrics_overall.parquet','run_manifest.json']
    if not all((run/f).is_file() and (run/f).stat().st_size for f in required):issues.append('required file missing/empty')
    report['windows'][window]={'issues':issues,'manifest_best_epoch':best,'history_epochs':len(history),'static_columns':static,'static_column_count':len(static),'feature_layout_sha256':actual,'reference_layout_sha256':manifest.get('reference_layout_sha256'),'runner_git_commit':manifest.get('runner_git_commit'),'elapsed_seconds':manifest.get('elapsed_seconds'),'energy_gpu_estimated_kwh':manifest.get('energy_gpu_estimated_kwh'),'prediction_checks':checks}
    report['issues'] += [window+': '+x for x in issues]
report['structural_checks_pass']=not report['issues']
(BASE/'integrity_audit.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
