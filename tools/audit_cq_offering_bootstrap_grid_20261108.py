"""Resumable offering-cluster bootstrap for flagged CQ F1 phase-1 cells.

Streams one prediction at a time from the verified Drive project, validates
hashed enrollment and labels, and retains only compact fact JSON locally.
PatchTST cells are intentionally reported as pending until their run archives
are located and checked; never silently substitute facts for predictions.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import time

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'CQ/resuilt/cq_offering_bootstrap_grid_20261108'
OUT.mkdir(parents=True, exist_ok=True)
TMP = OUT / 'temporary_predictions'
TMP.mkdir(exist_ok=True)
DATA = ROOT / 'downloads/vastai/CQ_V2_2_clean_grain_seed42/evaluation'
SALT = ROOT / 'downloads/private/cq_patchtst_prediction_salt'
FLAGS = ROOT / 'CQ/resuilt/cq_offering_dominance_20261108/cell_flags_phase1.parquet'
DRIVE = '1GWiedVROrxp8jvGbd0xmvVmWriZUkpOn'
BASE = 'gdrive:Jobs/CQ/organized_moved_20261029/L1_runs/S3_model/preserved_packages'
PREFIX = {'RNN': 'cq_rnn_historical_layout_batch2048_seed42_20261020/CQ',
          'LSTM': 'cq_lstm_batch2048_full_20261018/lstm/CQ',
          'GRU': 'cq_recurrent_batch2048_seed42_20261019/gru/CQ',
          'BILSTM': 'cq_recurrent_batch2048_seed42_20261019/bilstm/CQ'}
CLASSES = ('c0', 'c1', 'c2')
COLS = ['enrollment_id', 'context__offering_id', 'context__timeline_source', 'CQ_label_final']

def save_status(data):
    temp = OUT / 'status.json.tmp'
    temp.write_text(json.dumps(data, indent=2) + '\n', encoding='utf8')
    temp.replace(OUT / 'status.json')

def cohort(window, salt):
    base = DATA / window / 'V0'
    first = pd.read_parquet(base / 'test_P1.parquet', columns=COLS)
    if first.isna().any().any() or first.enrollment_id.duplicated().any():
        raise ValueError(f'{window}: invalid cohort grain/context')
    for phase in ('P2', 'P3', 'P4'):
        other = pd.read_parquet(base / f'test_{phase}.parquet', columns=COLS)
        if not first.equals(other):
            raise ValueError(f'{window}: cohort/label/offering differs at {phase}')
    first['hash'] = first.enrollment_id.astype(str).map(lambda x: sha256(f'{salt}|{x}'.encode()).hexdigest())
    first['class_id'] = first.CQ_label_final.map({'warning': 0, 'average': 1, 'good': 2})
    if first['class_id'].isna().any() or first['hash'].duplicated().any():
        raise ValueError(f'{window}: invalid hashed cohort or labels')
    first['group_id'] = pd.factorize(pd.MultiIndex.from_frame(first[['context__offering_id', 'context__timeline_source']]), sort=True)[0]
    return first.set_index('hash')[['class_id', 'group_id']]

def run_cell(item, datasets, local_prediction=None):
    w, model, pipeline, phase = item['window_id'], item['model_name'], item['pipeline_id'], item['phase_id']
    out = OUT / 'cells' / model / w / pipeline / f'TEST_{phase}.json'
    if out.is_file():
        old = json.loads(out.read_text(encoding='utf8'))
        if old.get('bootstrap_replicates') == 2000 and old.get('prediction_join') == 'ONE_TO_ONE_LABELS_MATCH':
            return 'EXISTS'
        raise ValueError(f'Invalid existing cell: {out}')
    remote = (f'{BASE}/{PREFIX[model]}/{w}/{pipeline}/seed=42/predictions/test_{phase}.parquet'
              if model in PREFIX else str(local_prediction))
    temp = Path(local_prediction) if local_prediction is not None else TMP / f'{model}_{w}_{pipeline}_{phase}.parquet'
    if local_prediction is None:
        cmd = ['rclone', 'copyto', remote, str(temp), '--drive-root-folder-id', DRIVE, '--retries', '3']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode:
            raise RuntimeError(f'{remote}: {result.stderr[-500:]}')
    try:
        source_hash = sha256(temp.read_bytes()).hexdigest()
        pred = pd.read_parquet(temp, columns=['enrollment_id_hash', 'y_true', 'y_pred']).set_index('enrollment_id_hash')
        raw = datasets[w]
        if pred.index.has_duplicates or len(pred) != len(raw):
            raise ValueError(f'Prediction grain mismatch: {model}/{w}/{pipeline}/{phase}')
        joined = pred.join(raw, how='left', validate='one_to_one')
        mapped = {'c0': 0, 'c1': 1, 'c2': 2}
        if joined.class_id.isna().any() or not joined.y_true.map(mapped).eq(joined.class_id).all():
            raise ValueError(f'Prediction ID/label mismatch: {model}/{w}/{pipeline}/{phase}')
        predicted = joined.y_pred.map(mapped)
        if predicted.isna().any():
            raise ValueError('Unexpected predicted class')
        true = joined.class_id.to_numpy(dtype='int64')
        group = joined.group_id.to_numpy(dtype='int64')
        n_groups = int(group.max()) + 1
        matrix = np.bincount(group * 9 + true * 3 + predicted.to_numpy(dtype='int64'), minlength=n_groups * 9).reshape(n_groups, 3, 3)
        seed = int.from_bytes(sha256(f'42|{w}|TEST|{model}|{pipeline}|{phase}'.encode()).digest()[:4], 'big')
        rng = np.random.default_rng(seed)
        draws = rng.multinomial(n_groups, np.full(n_groups, 1 / n_groups), size=2000)
        cm = (draws @ matrix.reshape(n_groups, 9)).reshape(-1, 3, 3)
        classes = []
        for i, code in enumerate(CLASSES):
            n = cm[:, i, :].sum(axis=1)
            values = np.divide(cm[:, i, i], n, out=np.full(2000, np.nan), where=n > 0)
            values = values[np.isfinite(values)]
            n_clusters = int((matrix[:, i, :].sum(axis=1) > 0).sum())
            valid = n_clusters > 1 and len(values) > 0
            support = int(matrix[:, i, :].sum())
            classes.append({'class_code': code, 'support': support, 'offering_count': n_clusters,
                            'recall': float(matrix[:, i, i].sum() / support) if support else None,
                            'valid_replicates': len(values), 'missing_class_replicates': 2000 - len(values),
                            'ci_status': 'ESTIMATED_CONDITIONAL_ON_CLASS_PRESENT' if valid else ('NOT_ESTIMABLE_SINGLE_OFFERING' if n_clusters == 1 else 'CLASS_ABSENT'),
                            'ci_low': float(np.quantile(values, .025)) if valid else None,
                            'ci_high': float(np.quantile(values, .975)) if valid else None})
        record = {'task': 'CQ', 'window_id': w, 'eval_split': 'TEST', 'model_name': model,
                  'pipeline_id': pipeline, 'phase_id': phase, 'seed': 42, 'bootstrap_seed': seed,
                  'bootstrap_replicates': 2000, 'offering_count': n_groups, 'prediction_rows': len(joined),
                  'prediction_join': 'ONE_TO_ONE_LABELS_MATCH', 'prediction_sha256': source_hash,
                  'prediction_source': remote, 'class_recall': classes}
        out.parent.mkdir(parents=True, exist_ok=True)
        pending = out.with_suffix('.tmp')
        pending.write_text(json.dumps(record) + '\n', encoding='utf8')
        pending.replace(out)
        return 'DONE'
    finally:
        if local_prediction is None:
            temp.unlink(missing_ok=True)

def main():
    salt = SALT.read_text(encoding='utf8').strip()
    if not salt:
        raise ValueError('CQ prediction salt is empty')
    flags = pd.read_parquet(FLAGS)
    flagged = flags[flags.single_offering_dominant].copy()
    f1 = flagged[flagged.model_name.isin(PREFIX)]
    f2 = flagged[flagged.model_name.eq('PATCHTST')]
    if len(f1) != 544 or len(f2) != 56 or set(f1.eval_split) != {'TEST'}:
        raise ValueError('Unexpected flagged phase-1 grid')
    datasets = {window: cohort(window, salt) for window in ('W1', 'W3')}
    plan = f1[['window_id', 'model_name', 'pipeline_id', 'phase_id']].to_dict('records')
    progress = {'status': 'RUNNING', 'f1_total': len(plan), 'f1_done': 0, 'errors': [],
                'f2_pending': len(f2), 'f2_reason': 'prediction archives not yet located/verified'}
    save_status(progress)
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(run_cell, item, datasets): item for item in plan}
        for future in as_completed(futures):
            item = futures[future]
            try:
                result = future.result()
                progress['f1_done'] += 1
                print(json.dumps({'cell': item, 'status': result, 'done': progress['f1_done']}), flush=True)
            except Exception as exc:
                progress['errors'].append({'cell': item, 'error': str(exc)})
                print(json.dumps({'cell': item, 'status': 'ERROR', 'error': str(exc)}), flush=True)
            save_status(progress)
    progress['status'] = 'F1_COMPLETE_F2_PENDING' if not progress['errors'] else 'F1_PARTIAL_ERRORS_F2_PENDING'
    save_status(progress)
    print(json.dumps(progress), flush=True)

if __name__ == '__main__':
    main()
