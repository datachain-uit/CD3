"""Build LO M-03 matched baseline and verified course/temporal slice tables."""
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, recall_score

BASE = Path('/workspace/CD3')
STATE = BASE / 'runs/lo_m03_static_v2_rnn_20261108'
DATA = BASE / 'data/LO_M03_W1_20261108'
OUT = STATE / 'm03_tables'
OUT.mkdir(exist_ok=True)
salt = os.environ['TEMPO_PREDICTION_SALT']
classes = ['c0', 'c1', 'c2']
label_map = dict(zip(['I/D', 'G', 'E'], classes))
audit = STATE / 'audits_fixed/LO/RNN/seed=42'
manifest = json.loads((audit / 'audit_manifest.json').read_text())
assert manifest['runs'] == 2 and manifest['bootstrap_repetitions'] == 2000
keys = ['task', 'window_id', 'pipeline_id', 'model_name', 'seed', 'eval_split', 'phase_id']
baseline = pd.read_parquet(BASE / 'm03_baseline_metrics.parquet')
ablation = pd.read_parquet(audit / 'sanity_components.parquet')
baseline = baseline.query("task == 'LO' and window_id == 'W1' and model_name == 'RNN' and seed == 42 and pipeline_id in ['V0','V8']")
assert len(baseline) == len(ablation) == 16
assert not baseline.duplicated(keys).any() and not ablation.duplicated(keys).any()
cols = ['macro_f1', 'balanced_acc', 's_perf', 's_san_plus', 'acctempo_m3', 's_ent', 'n_eval_samples']
pair = baseline[keys + cols].merge(ablation[keys + cols], on=keys, validate='one_to_one', suffixes=('_baseline', '_no_static'))
assert len(pair) == 16
assert (pair.n_eval_samples_baseline == pair.n_eval_samples_no_static).all()
for c in cols[:-1]:
    pair['delta_' + c] = pair[c + '_no_static'] - pair[c + '_baseline']
pair['baseline_static_columns'] = 13
pair['ablation_static_columns'] = 0
pair['baseline_runner_commit'] = 'b0e5ae1270fae1c0397facf6e9fc9e522016dc9d'
pair.to_csv(OUT / 'ablation_comparison.csv', index=False)

rows = []
for v, parent in [('V0', 'V0'), ('V8', 'V5')]:
    run = STATE / f'runs/LO/W1/{v}/RNN/seed=42'
    m = json.loads((run / 'run_manifest.json').read_text())
    layout = json.loads((run / 'feature_layout.json').read_text())
    assert m['static_ablation'] == 'no_static' and not layout['static_columns'] and not layout['mask_static_columns']
    assert m['reference_layout_sha256'] == 'sha256:847617755f0d0190efdc52ecada53772f24117e7034885e3432f609b604e17d1'
    source = pd.read_parquet(DATA / f'train/W1/{parent}/train.parquet', columns=['context__course_id'])
    assert source.context__course_id.notna().all()
    courses = set(source.context__course_id.astype(str))
    del source
    for split in ('validation', 'test'):
        for phase in ('P1', 'P2', 'P3', 'P4'):
            name = 'validation.parquet' if split == 'validation' else f'test_{phase}.parquet'
            strict = f'context__temporal_strict_{phase}'
            f = pd.read_parquet(DATA / f'evaluation/W1/{parent}' / name, columns=['enrollment_id', 'context__course_id', 'LO_performance_label_3', strict])
            if f[['enrollment_id', 'context__course_id', strict]].isna().any().any() or not f[strict].isin([0, 1]).all():
                raise ValueError(f'Invalid cohort source: {v}/{split}/{phase}')
            f['enrollment_id_hash'] = f.enrollment_id.astype(str).map(lambda x: hashlib.sha256(f'{salt}|{x}'.encode()).hexdigest())
            f['course_cohort'] = np.where(f.context__course_id.astype(str).isin(courses), 'SEEN', 'UNSEEN')
            f['temporal_slice'] = np.where(f[strict].eq(1), 'STRICT', 'OVERLAP')
            pred = pd.read_parquet(run / f'predictions/{split}_{phase}.parquet', columns=['enrollment_id_hash', 'y_true', 'y_pred'])
            joined = f.merge(pred, on='enrollment_id_hash', validate='one_to_one', how='outer', indicator=True)
            if not joined._merge.eq('both').all() or not joined.LO_performance_label_3.map(label_map).eq(joined.y_true).all():
                raise ValueError(f'Hash or label mismatch: {v}/{split}/{phase}')
            for cohort in ('SEEN', 'UNSEEN'):
                for temporal in ('STRICT', 'OVERLAP'):
                    part = joined[(joined.course_cohort == cohort) & (joined.temporal_slice == temporal)]
                    n = len(part)
                    support = part.y_true.value_counts()
                    status = 'SLICE_EMPTY' if not n else ('ONE_CLASS' if len(support) == 1 else 'OK')
                    recalls = recall_score(part.y_true, part.y_pred, labels=classes, average=None, zero_division=0) if n else [np.nan] * 3
                    row = dict(task='LO', window_id='W1', pipeline_id=v, model_name='RNN', seed=42, variant='no_static', eval_split=split.upper(), phase_id=phase, course_cohort=cohort, temporal_slice=temporal, status=status, n=n)
                    row.update({f'support_{c}': int(support.get(c, 0)) for c in classes})
                    row.update({f'recall_{c}': float(recalls[i]) for i, c in enumerate(classes)})
                    row.update(macro_f1_fixed3=f1_score(part.y_true, part.y_pred, labels=classes, average='macro', zero_division=0) if n else np.nan, balanced_accuracy=balanced_accuracy_score(part.y_true, part.y_pred) if n else np.nan, accuracy=accuracy_score(part.y_true, part.y_pred) if n else np.nan)
                    rows.append(row)
            print('verified', v, split, phase, len(joined), flush=True)

result = pd.DataFrame(rows)
assert len(result) == 64
result.to_csv(OUT / 'ablation_seen_course_x_strict.csv', index=False)
(OUT / 'summary.json').write_text(json.dumps({'comparison_rows': len(pair), 'slice_rows': len(result), 'slice_status_counts': result.status.value_counts().to_dict(), 'join': 'ONE_TO_ONE_LABELS_MATCH', 'baseline_source': 'lo_family_pipeline_window_phase_metrics.parquet', 'scope': 'no_static ablation; baseline comparison is aggregate, not paired predictions'}, indent=2))
print('M03_TABLES_COMPLETE', flush=True)
