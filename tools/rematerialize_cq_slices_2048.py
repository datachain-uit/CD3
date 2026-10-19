"""Produce immutable CQ slice audit r2 from downloaded predictions and parents."""
from pathlib import Path
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.vastai_audit_shared import _class_ids, _slice_rows
from tools.vastai_metadata_contract import PARENT_PIPELINES

BASE = ROOT/'CQ/resuilt/cq_recurrent_batch2048_seed42_20261019'
DATA = ROOT/'downloads/vastai/CQ_V2_2_clean_grain_seed42'
OUT = ROOT/'CQ/resuilt/cq_recurrent_batch2048_slice_r2_20261019/audits/CQ'
SOURCES = {
 'LSTM': (ROOT/'CQ/resuilt/cq_lstm_batch2048_full_20261018/lstm', ROOT/'CQ/resuilt/cq_lstm_batch2048_audit_20261018/CQ/LSTM/seed=42'),
 'GRU': (BASE/'gru', BASE/'audits/CQ/GRU/seed=42'),
 'BILSTM': (BASE/'bilstm', BASE/'audits/CQ/BILSTM/seed=42'),
}
CHECK_COLUMNS = ['macro_f1','balanced_acc','s_perf','s_nan','s_maj_jsd','s_ent','s_drift','s_eff','s_leak','s_san_plus','s_cal','s_san_plus_v2','acctempo_m3']

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''): h.update(b)
    return h.hexdigest()

counts={}
for window in ('W1','W2','W3'):
    for parent in ('V0','V1','V5','V9','V13'):
        path = DATA/'train'/window/parent/'train.parquet'
        frame = pd.read_parquet(path, columns=['CQ_label_final'])
        counts[(window,parent)] = np.bincount(_class_ids(frame['CQ_label_final'],'CQ'),minlength=3)
        print('PARENT',window,parent,len(frame),flush=True)
        del frame

for model,(run_root,old) in SOURCES.items():
    dest = OUT/model/'seed=42'
    if dest.exists(): raise FileExistsError(f'Refusing overwrite: {dest}')
    sanity = pd.read_parquet(old/'sanity_components.parquet')
    rows=[]
    for record in sanity.to_dict('records'):
        w,p,split,phase = (record[x] for x in ('window_id','pipeline_id','eval_split','phase_id'))
        parent = PARENT_PIPELINES.get(p,p)
        prefix = 'validation' if split == 'VALIDATION' else 'test'
        pred = pd.read_parquet(run_root/'CQ'/w/p/model/'seed=42'/'predictions'/f'{prefix}_{phase}.parquet')
        generated = _slice_rows(pred, task='CQ', window=w, pipeline=p, model=model, seed=42,
                    split=split, phase=phase, train_class_counts=counts[(w,parent)],
                    s_eff=float(record['s_eff']), s_leak=float(record['s_leak']))
        allrow=generated[0]
        for c in CHECK_COLUMNS:
            if not np.isclose(float(allrow[c]),float(record[c]),rtol=1e-9,atol=1e-9):
                raise ValueError(f'ALL/sanity mismatch {model}/{w}/{p}/{split}/{phase}/{c}: {allrow[c]} vs {record[c]}')
        rows.extend(generated)
        if len(rows)%102==0: print(model,'slice_rows',len(rows),flush=True)
    if len(rows)!=1224: raise ValueError(f'Unexpected slice coverage {model}: {len(rows)}')
    dest.mkdir(parents=True)
    for name in ('canonical_s_leak','sanity_components','metrics_per_class','bootstrap_metrics_per_class','checkpoint_selection'):
        shutil.copy2(old/(name+'.parquet'),dest/(name+'.parquet'))
    pd.DataFrame(rows).to_parquet(dest/'evaluation_slices.parquet',index=False)
    meta=json.loads((old/'audit_manifest.json').read_text(encoding='utf-8'))
    meta.update({'audit_schema_version':'vastai_posthoc_audit_v2_slice_parent_contract',
        'source_audit_manifest_sha256':'sha256:'+sha(old/'audit_manifest.json'),
        'slice_definition':'classification metrics use parent TRAIN class counts and canonical full-evaluation s_eff/s_leak; drift and prediction sanity recomputed on slice',
        'slice_parent_s_leak_scope':'PARENT_REAL_EVALUATION_FULL_SPLIT_PHASE_NOT_REFIT_PER_SLICE',
        'all_slice_vs_sanity':'PASS_ALL_408', 'created_at_utc':datetime.now(timezone.utc).isoformat()})
    (dest/'audit_manifest.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
    print('COMPLETE',model,dest,flush=True)
