"""Cluster-bootstrap CQ W1/V0/TEST/P1 for four recurrent families."""
from hashlib import sha256
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path('CQ/resuilt/cq_offering_dominance_20261108')
salt = Path('downloads/private/cq_patchtst_prediction_salt').read_text(encoding='utf8').strip()
raw = pd.read_parquet('downloads/vastai/CQ_V2_2_clean_grain_seed42/evaluation/W1/V0/test_P1.parquet',
                      columns=['enrollment_id', 'context__offering_id', 'context__timeline_source', 'CQ_label_final'])
if raw.isna().any().any() or raw.enrollment_id.duplicated().any():
    raise ValueError('Invalid evaluation cohort')
raw['enrollment_id_hash'] = raw.enrollment_id.astype(str).map(lambda x: sha256(f'{salt}|{x}'.encode()).hexdigest())
raw['expected'] = raw.CQ_label_final.map({'warning': 'c0', 'average': 'c1', 'good': 'c2'})
records = []
for model in ('RNN', 'LSTM', 'GRU', 'BILSTM'):
    prefix = model.lower() if model == 'GRU' else model
    source = ROOT / f'{prefix}_w1_v0_test_p1_probe.parquet'
    pred = pd.read_parquet(source, columns=['enrollment_id_hash', 'y_true', 'y_pred'])
    joined = raw.merge(pred, on='enrollment_id_hash', how='outer', validate='one_to_one', indicator=True)
    if not joined._merge.eq('both').all() or not joined.expected.eq(joined.y_true).all():
        raise ValueError(f'{model}: cohort or labels differ')
    joined['correct'] = joined.y_true.eq(joined.y_pred).astype(int)
    grouped = joined.groupby(['context__offering_id', 'context__timeline_source', 'y_true'], dropna=False).correct.agg(['size', 'sum']).reset_index()
    labels = ['c0', 'c1', 'c2']
    n = grouped.pivot(index=['context__offering_id', 'context__timeline_source'], columns='y_true', values='size').fillna(0).reindex(columns=labels, fill_value=0).to_numpy()
    hit = grouped.pivot(index=['context__offering_id', 'context__timeline_source'], columns='y_true', values='sum').fillna(0).reindex(columns=labels, fill_value=0).to_numpy()
    rng = np.random.default_rng(42)
    weights = rng.multinomial(len(n), np.full(len(n), 1 / len(n)), size=2000)
    samples_n, samples_hit = weights @ n, weights @ hit
    for i, label in enumerate(labels):
        estimates = np.divide(samples_hit[:, i], samples_n[:, i], out=np.full(2000, np.nan), where=samples_n[:, i] > 0)
        valid = estimates[np.isfinite(estimates)]
        clusters = int((n[:, i] > 0).sum())
        estimable = clusters > 1 and len(valid) > 0
        records.append({'task': 'CQ', 'window_id': 'W1', 'pipeline_id': 'V0', 'model_name': model,
                        'seed': 42, 'eval_split': 'TEST', 'phase_id': 'P1', 'class_code': label,
                        'support': int(n[:, i].sum()), 'n_offerings_with_class': clusters,
                        'recall': float(hit[:, i].sum() / n[:, i].sum()) if n[:, i].sum() else None,
                        'bootstrap_replicates': 2000, 'bootstrap_seed': 42, 'bootstrap_valid': len(valid),
                        'ci_status': 'ESTIMATED_CONDITIONAL_ON_CLASS_PRESENT' if estimable else 'NOT_ESTIMABLE_SINGLE_OFFERING',
                        'ci_2_5': float(np.quantile(valid, .025)) if estimable else None,
                        'ci_97_5': float(np.quantile(valid, .975)) if estimable else None,
                        'prediction_sha256': sha256(source.read_bytes()).hexdigest(), 'prediction_join': 'ONE_TO_ONE_LABELS_MATCH'})
out = ROOT / 'offering_bootstrap_pilot_w1_v0_test_p1.csv'
pd.DataFrame(records).to_csv(out, index=False)
print(json.dumps({'pilot_cells': 4, 'class_rows': len(records), 'bootstrap_replicates': 2000, 'output': str(out)}, indent=2))
