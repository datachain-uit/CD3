"""Export CQ R4 evaluation slices only after validation against R4 facts."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib,json,os
import numpy as np
import pandas as pd

BASE=Path(os.environ.get('CD3_JOBS_ROOT','data/Jobs'))/'CQ/organized_moved_20261029/L2_facts/fact_exports'
OUT=Path('CQ/resuilt/cq_r4_evaluation_slices_20261102')
KEY=['task','window_id','pipeline_id','model_name','seed','eval_split','phase_id']
def main():
    root=BASE/'cq_f1_allfamilies_l2_ingest_r3_20261021'/'audits'/'CQ'
    frames=[pd.read_parquet(root/f/'seed=42'/'evaluation_slices.parquet') for f in ('RNN','LSTM','GRU','BILSTM')]
    slices=pd.concat(frames,ignore_index=True)
    if len(slices)!=4896 or slices.duplicated(KEY+['slice']).any(): raise ValueError('slice coverage or uniqueness failed')
    r4=pd.read_parquet(BASE/'cq_recurrent_allfamilies_grid_r4_20261023'/'cq_family_pipeline_window_phase_metrics.parquet')
    allrows=slices[slices['slice']=='ALL']
    combined=r4.merge(allrows,on=KEY,validate='one_to_one',suffixes=('_r4','_slice'))
    if len(combined)!=1632: raise ValueError('ALL does not cover all R4 cells')
    names={'f1_macro':'macro_f1','balanced_accuracy':'balanced_acc','cohen_kappa':'kappa','multiclass_nll':'log_loss','multiclass_brier':'brier','top_label_ece_15':'ece','n_rows':'n_eval_samples'}
    cols=['mcc','pr_auc_macro','s_perf','s_nan','s_maj_jsd','s_ent','s_drift','s_eff','s_leak','s_san_plus','s_san_plus_v2','s_cal','acctempo_m3','c0_recall','c1_recall','c2_recall']
    deltas={}; mismatches={}
    for left,right in list(names.items())+[(c,c) for c in cols]:
        a=combined[left+'_r4' if left==right else left]; b=combined[right+'_slice' if left==right else right]
        if a.isna().ne(b.isna()).any(): raise ValueError(f'null mismatch {left}')
        delta=(a-b).abs().max(); deltas[left]=None if pd.isna(delta) else float(delta)
        if pd.notna(delta) and delta>1e-12: mismatches[left]=float(delta)
    if mismatches:
        OUT.mkdir(parents=True,exist_ok=True)
        (OUT/'validation_blocked.json').write_text(json.dumps({'status':'BLOCKED_ALL_R4_MISMATCH','max_abs_deltas':deltas,'mismatches':mismatches,'explanation':'Model calibration uses 1e-7 probability clipping; post-hoc audit uses 1e-12. This is a plausible contributor to calibration differences; verify PR-AUC separately. Reconcile metric definitions from predictions before publishing.'},indent=2)+'\n',encoding='utf8')
        raise ValueError(f'ALL/R4 mismatches: {mismatches}; no slice export published')
    sizes=slices.pivot(index=KEY,columns='slice',values='n_eval_samples')
    if not (sizes['ALL']==sizes['STRICT']+sizes['OVERLAP']).all(): raise ValueError('partition count mismatch')
    matrices=slices.pivot(index=KEY,columns='slice',values='confusion_matrix')
    for _,row in matrices.iterrows():
        if not np.array_equal(np.asarray(row['ALL']),np.asarray(row['STRICT'])+np.asarray(row['OVERLAP'])): raise ValueError('confusion matrix partition mismatch')
    slices['acctempo_m4']=slices.s_perf.clip(lower=1e-3).pow(.6)*slices.s_san_plus_v2.clip(lower=1e-3).pow(.4)
    OUT.mkdir(parents=True,exist_ok=True)
    slices.to_parquet(OUT/'cq_evaluation_slices.parquet',index=False)
    slices.to_csv(OUT/'cq_evaluation_slices.csv',index=False)
    info={'created_at_utc':datetime.now(timezone.utc).isoformat(),'rows':len(slices),'cells':len(combined),'partition_counts':'PASS','partition_confusion_matrices':'PASS','all_r4_max_abs_deltas':deltas}
    (OUT/'summary.json').write_text(json.dumps(info,indent=2)+'\n',encoding='utf8')
    (OUT/'README.md').write_text('# CQ R4 evaluation slices, seed 42\n\nSource: cq_f1_allfamilies_l2_ingest_r3_20261021/audits/CQ. ALL rows validated against cq_recurrent_allfamilies_grid_r4_20261023 to 1e-12; STRICT + OVERLAP counts and confusion matrices equal ALL. acctempo_m4 derives from registered S_perf and S_san_plus_v2 with floor 0.001.\n',encoding='utf8')
    files=sorted(p for p in OUT.iterdir() if p.is_file() and p.name!='sha256sums.txt')
    (OUT/'sha256sums.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in files),encoding='utf8')
    print(json.dumps(info,indent=2))
if __name__=='__main__': main()
