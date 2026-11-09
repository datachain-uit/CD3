"""Rebuild the per-phase prediction files of the Mantis CQ V0 cells from the stored probabilities.

The V0 bundle (mantis_v0_results.tar.gz, written by the earlier single-pipeline script) kept only
result/{validation,test}_probabilities.npy [rows, 4 phases, 3 classes], f3_cell_record.json and probe_head.pt.
The grid runner (tools/run_mantis_cq_grid_zstd_20261108.py) writes predictions as argmax of exactly that array joined to
the evaluation parquet row order, so this script repeats that step (same columns, salted ids, y_true from the label)
and writes run_manifest.json + metrics_overall.parquet in the runner layout so the standard standardize/audit tools apply.
Every value is derived from the stored probabilities and the data release; nothing is re-trained.
A check against the best-epoch validation score in f3_cell_record.json must pass (exit 2 otherwise).
Usage: python tools/rebuild_mantis_v0_predictions_20261109.py --bundle B --data-root D --salt-file S --out OUT
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score

ap = argparse.ArgumentParser()
ap.add_argument('--bundle', type=Path, required=True, help='extracted mantis_v0_results (contains runs/W*/V0)')
ap.add_argument('--data-root', type=Path, required=True)
ap.add_argument('--salt-file', type=Path, required=True)
ap.add_argument('--out', type=Path, required=True, help='output root; writes OUT/runs/W*/V0 in the runner layout')
args = ap.parse_args()

CLASSES = ('warning', 'average', 'good')
LABEL = 'CQ_label_final'
salt = args.salt_file.read_bytes().decode('utf-8').rstrip('\n')
release = json.loads((args.data_root / 'download_manifest.json').read_text(encoding='utf-8'))
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
KEEP = ['enrollment_id', 'offering_id', 'timeline_source', 'course_id',
        'context__temporal_strict_P1', 'context__temporal_strict_P2', 'context__temporal_strict_P3', 'context__temporal_strict_P4']

for window in ('W1', 'W2', 'W3'):
    src = args.bundle / 'runs' / window / 'V0'
    res = src / 'result'
    record = json.loads((res / 'f3_cell_record.json').read_text(encoding='utf-8'))
    eval_dir = args.data_root / 'evaluation' / window / 'V0'
    out = args.out / 'runs' / window / 'V0'
    (out / 'predictions').mkdir(parents=True)
    (out / 'result').mkdir()
    for name in ('probe_head.pt', 'f3_cell_record.json', 'diagnostic_metrics.json'):
        if (res / name).is_file():
            (out / 'result' / name).write_bytes((res / name).read_bytes())
    metrics = []
    val_scores = []
    for split, fname in (('validation', 'validation.parquet'), ('test', 'test_P4.parquet')):
        frame = pd.read_parquet(eval_dir / fname)
        probs = np.load(res / f'{split}_probabilities.npy')
        if probs.shape != (len(frame), 4, 3):
            sys.exit(f'{window} {split}: probabilities {probs.shape} do not match {len(frame)} rows')
        y = frame[LABEL].map({c: i for i, c in enumerate(CLASSES)})
        if y.isna().any():
            sys.exit(f'{window} {split}: unmapped labels')
        y = y.to_numpy()
        ids = frame.enrollment_id.astype(str).map(lambda v: hashlib.sha256(f'{salt}|{v}'.encode()).hexdigest())
        context = frame[[c for c in KEEP if c in frame.columns]]
        for index in range(4):
            pred = probs[:, index].argmax(axis=1)
            common = {'task': 'CQ', 'window_id': window, 'pipeline_id': 'V0', 'model_name': 'MANTIS_V2', 'seed': 42,
                      'eval_split': split.upper(), 'phase_id': f'P{index + 1}'}
            frame_out = pd.DataFrame({**common, 'enrollment_id_hash': ids, 'y_true': [f'c{x}' for x in y], 'y_pred': [f'c{x}' for x in pred],
                                      **{f'prob_c{i}': probs[:, index, i] for i in range(3)}})
            for col in context.columns:
                if col != 'enrollment_id':
                    frame_out[col.removeprefix('context__')] = context[col].to_numpy()
            frame_out.to_parquet(out / 'predictions' / f'{split}_P{index + 1}.parquet', index=False)
            f1 = f1_score(y, pred, labels=[0, 1, 2], average='macro', zero_division=0)
            if split == 'validation':
                val_scores.append(f1)
            metrics.append({**common, 'n_eval_samples': len(y), 'accuracy': accuracy_score(y, pred),
                            'balanced_acc': balanced_accuracy_score(y, pred), 'macro_f1': f1})
    pd.DataFrame(metrics).to_parquet(out / 'metrics_overall.parquet', index=False)
    recorded = max(h.get('validation_macro_f1_mean_p1_p4', 0.0) for h in record['history'])
    mine = float(np.mean(val_scores))
    print(json.dumps({'window': window, 'rebuilt_validation_macro_f1_mean_p1_p4': mine, 'recorded_best': recorded, 'abs_diff': abs(mine - recorded)}), flush=True)
    if abs(mine - recorded) > 1e-6:
        sys.exit(f'{window}: rebuilt validation score differs from the cell record')
    paths = {'validation': eval_dir / 'validation.parquet', 'test': eval_dir / 'test_P4.parquet'}
    manifest = {'task': 'CQ', 'window': window, 'pipeline': 'V0', 'parent': 'V0', 'seed': 42,
                'release_id': release['release_id'], 'data_release_id': release['data_release_id'],
                'input_sha256': {k: sha(v) for k, v in paths.items()},
                'download_manifest_sha256': sha(args.data_root / 'download_manifest.json'),
                'run_purpose': 'EXPLORATORY_CACHE_VALIDATION',
                'limitations': 'Predictions and metrics_overall were rebuilt post hoc (tools/rebuild_mantis_v0_predictions_20261109.py) from the stored '
                               'probabilities of the original run; the validation score matches f3_cell_record.json. Not recorded in the original V0 bundle: '
                               'runner manifest, elapsed time and GPU energy.',
                'cache_mode': record.get('cache_mode'), 'cache_reuse': record.get('cache_reuse'), 'epochs_trained': record.get('epochs_trained')}
    (out / 'run_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    (out / 'COMPLETE').write_text('complete\n', encoding='utf-8')
print('REBUILD_DONE')
