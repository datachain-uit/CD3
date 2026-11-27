import os as _os
# Machine roots come from environment variables (no machine paths in the repository).
REPO = _os.environ.get('TEMPO_REPO_ROOT', '.')
WORK = _os.environ.get('TEMPO_WORK_ROOT', '.')
AUDIT44 = _os.environ.get('TEMPO_AUDIT44_ROOT', '.')
WORKD = _os.environ.get('TEMPO_DELIVERY_WORK_ROOT', '.')
import pandas as pd, glob
S=f'{WORKD}/src/CQ/seed42/F1_recurrent/cq_recurrent_allfamilies_grid_r4_20261023/'
files={
 'cq43_slices':f'{AUDIT44}/facts44/CQ_patchtst_v0_v16_seed44/evaluation_slices.parquet',
 'cq43_pc':f'{AUDIT44}/facts44/CQ_patchtst_v0_v16_seed44/metrics_per_class.parquet',
 'cq43_bs':f'{AUDIT44}/facts44/CQ_patchtst_v0_v16_seed44/bootstrap_metrics_per_class.parquet',
 'cq43_coh':f'{AUDIT44}/facts44/CQ_patchtst_v0_v16_seed44/cohort_slice_status.parquet',
 'r4_slices':f'{REPO}/CQ/resuilt/cq_r4_slices_reconciled_20261103/cq_evaluation_slices.parquet',
 'r4_pc':S+'cq_metrics_per_class_long.parquet','r4_bs':S+'cq_bootstrap_metrics_per_class_long.parquet',
 'lo_rnn_slices':f'{REPO}/CQ/resuilt/input/results/R21_evidence_20261031/LO/audit_seed42/RNN/LO/RNN/seed=42/evaluation_slices.parquet',
 'lo_rnn_pc':f'{REPO}/CQ/resuilt/input/results/R21_evidence_20261031/LO/audit_seed42/RNN/LO/RNN/seed=42/metrics_per_class.parquet',
 'lo_rnn_bs':f'{REPO}/CQ/resuilt/input/results/R21_evidence_20261031/LO/audit_seed42/RNN/LO/RNN/seed=42/bootstrap_metrics_per_class.parquet',
}
for k,p in files.items():
    d=pd.read_parquet(p)
    print('==',k,d.shape); print(' '.join(f'{c}:{str(t)[:8]}' for c,t in d.dtypes.items()))
    for c in ('model_name','eval_slice','slice_name','slice','metric_name'):
        if c in d: print('  ',c,d[c].unique()[:8])
