"""Audit 153 CQ metadata histories and sample checkpoint/prefix replay (read-only inputs)."""
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from model.data import FeatureLayout, transform_frame
from model.architectures import build_shared_phase_model

artifacts = ROOT/'CQ/resuilt/cq_recurrent_batch2048_slice_r2_20261019/artifacts'
out = ROOT/'CQ/resuilt/cq_batch2048_closure_audit_20261019'
out.mkdir(parents=True, exist_ok=True)
files = sorted(artifacts.rglob('run_manifest.json'))
if len(files) != 153: raise ValueError(f'Expected 153 manifests, got {len(files)}')
rows=[]
for path in files:
    m=json.loads(path.read_text(encoding='utf-8'))
    h=pd.read_parquet(path.parent/'train_history.parquet')
    metrics=pd.read_parquet(path.parent/'metrics_overall.parquet')
    v=metrics[metrics.eval_split.eq('VALIDATION')]
    if len(v)!=4 or set(v.phase_id)!=set(('P1','P2','P3','P4')): raise ValueError(f'Incomplete validation: {path}')
    best=h.sort_values(['validation_macro_f1_mean_p1_p4','validation_cross_entropy_mean_p1_p4','epoch'],ascending=[False,True,True]).iloc[0]
    stored=h[h.epoch.eq(m['best_epoch'])]
    if len(stored)!=1: raise ValueError(f'Invalid best epoch: {path}')
    stored=stored.iloc[0]
    rows.append({'window':m['window_id'],'pipeline':m['pipeline_id'],'family':m['model_name'],'epoch_match':int(best.epoch)==int(m['best_epoch']),
                 'selected_epoch':int(m['best_epoch']), 'history_vs_export_mean_abs_diff':abs(float(stored.validation_macro_f1_mean_p1_p4)-float(v.f1_macro.mean())),
                 'energy_type':m.get('energy_measurement_type'),'energy_gpu_estimated_kwh':m.get('energy_gpu_estimated_kwh'),
                 'energy_null_reason':m.get('energy_null_reason'),'energy_sample_count':m.get('energy_sample_count'),
                 'energy_missing_sample_rate':m.get('energy_missing_sample_rate'),'batch_size':m.get('batch_size'),
                 'micro_batch_size':m.get('micro_batch_size'),'accumulation_steps':m.get('accumulation_steps')})
pd.DataFrame(rows).to_csv(out/'manifest_history_energy_153.csv',index=False)
df=pd.DataFrame(rows)
summary={'n_runs':len(df),'epoch_history_match':int(df.epoch_match.sum()),'max_history_vs_validation_f1_difference':float(df.history_vs_export_mean_abs_diff.max()),
         'energy_type_counts':dict(Counter(str(x) for x in df.energy_type)), 'energy_nonnull':int(df.energy_gpu_estimated_kwh.notna().sum()),
         'energy_sample_count_range':[int(df.energy_sample_count.min()),int(df.energy_sample_count.max())], 'energy_missing_rate_max':float(df.energy_missing_sample_rate.max()),
         'energy_scope':'GPU only; 1-second NVML estimates, not system energy or CO2', 'replay':[]}

roots={'LSTM':ROOT/'CQ/resuilt/cq_lstm_batch2048_full_20261018/lstm',
       'GRU':ROOT/'CQ/resuilt/cq_recurrent_batch2048_seed42_20261019/gru',
       'BILSTM':ROOT/'CQ/resuilt/cq_recurrent_batch2048_seed42_20261019/bilstm'}
input_path=ROOT/'downloads/vastai/CQ_V2_2_clean_grain_seed42/evaluation/W1/V0/validation.parquet'
frame=next(pq.ParquetFile(input_path).iter_batches(batch_size=512)).to_pandas()
for name, root in roots.items():
    run=root/'CQ/W1/V0'/name/'seed=42'
    ck=torch.load(run/'model.pt',map_location='cpu',weights_only=False)
    l=ck['layout']; layout=FeatureLayout(l['task'],l['phase_id'],tuple(l['dynamic_bases']),tuple(l['static_columns']),tuple(l['mask_dynamic_columns']),tuple(l['mask_static_columns']),tuple(l.get('mask_phase_bases',[])))
    x,s,_,y=transform_frame(frame,layout,classes=tuple(ck['classes']),use_masks=True)
    model=build_shared_phase_model(x.shape[2],s.shape[1],len(ck['classes']),name.lower(),hidden_size=128,num_layers=1,dropout=.3)
    model.load_state_dict(ck['model_state_dict']); model.eval()
    with torch.no_grad():
        dynamic=torch.from_numpy(x); static=torch.from_numpy(s)
        full=model(dynamic,static)
        phases=[]
        for i in range(4):
            isolated=model(dynamic[:,:i+1],static)[:,-1]
            diff=float((full[:,i]-isolated).abs().max())
            stored=pd.read_parquet(run/'predictions'/f'validation_P{i+1}.parquet').iloc[:len(frame)]
            probability=torch.softmax(full[:,i].float(),dim=1).numpy()
            original=stored[['prob_c0','prob_c1','prob_c2']].to_numpy()
            labels=stored.y_true.astype(str).to_numpy()
            phases.append({'phase':f'P{i+1}','n_sample':len(frame),'prefix_vs_full_logits_max_abs_diff':diff,
                           'saved_probabilities_max_abs_diff':float(np.max(np.abs(probability-original))),
                           'prediction_agreement':float(np.mean(probability.argmax(1)==stored.y_pred.str.removeprefix('c').astype(int).to_numpy())),
                           'label_agreement':float(np.mean(np.array(['c'+str(z) for z in y])==labels))})
    summary['replay'].append({'family':name,'window':'W1','pipeline':'V0','phase_results':phases,
                              'limitation':'CPU replay of first 512 rows uses positional alignment; hash identity not verified without prediction salt; CPU/GPU numeric differences possible.'})
(out/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps(summary,indent=2))
