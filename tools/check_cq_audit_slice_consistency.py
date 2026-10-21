from pathlib import Path
import pandas as pd
root = Path(__file__).resolve().parents[1]
base = root / 'CQ/resuilt/cq_recurrent_batch2048_seed42_20261019/audits/CQ'
paths = {'LSTM': root / 'CQ/resuilt/cq_lstm_batch2048_audit_20261018/CQ/LSTM/seed=42', 'GRU': base / 'GRU/seed=42', 'BILSTM': base / 'BILSTM/seed=42'}
keys = ['window_id','pipeline_id','eval_split','phase_id']
columns = ['s_leak','s_eff','s_drift','acctempo_m3','s_san_plus','macro_f1']
for model, path in paths.items():
    sanity = pd.read_parquet(path / 'sanity_components.parquet')
    slices = pd.read_parquet(path / 'evaluation_slices.parquet')
    merged = sanity.merge(slices[slices['slice'].eq('ALL')], on=keys, suffixes=('_sanity','_slice'), validate='one_to_one')
    print(model, 'rows', len(merged), {c:int(((merged[c+'_sanity']-merged[c+'_slice']).abs()>1e-9).sum()) for c in columns})
