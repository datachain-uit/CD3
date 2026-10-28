"""Verify LO replay against baseline by hashing source IDs with each private salt."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

root = Path(__file__).resolve().parents[1]
base = root / 'LO/resuilt/lo_static_v2_seed42_20261026/RNN/LO/W1/V0/RNN/seed=42'
replay = root / 'LO/resuilt/lo_static_v2_seed42_20261026/lo_rnn_replay_protocol27_seed42/LO/W1/V0/RNN/seed=42'
data = root / 'downloads/vastai/LO_V3_1_clean_grain_seed42/evaluation/W1/V0'
salts = [(root / 'downloads/private/lo_grid_prediction_salt').read_text().strip(),
         (root / 'downloads/private/lo_replay_protocol27_prediction_salt').read_text().strip()]
ma, mb = [json.loads((p / 'run_manifest.json').read_text(encoding='utf-8')) for p in (base, replay)]
keys = ['task', 'window_id', 'pipeline_id', 'model_name', 'seed', 'batch_size', 'micro_batch_size',
        'accumulation_steps', 'data_release_id', 'split_version', 'phase_version', 'feature_layout_sha256',
        'learning_rate', 'warmup_epochs', 'gradient_clip_norm', 'best_epoch']
assert all(ma.get(k) == mb.get(k) for k in keys), 'Run contracts differ'
rows = []
for split in ('test', 'validation'):
    for phase in ('P1', 'P2', 'P3', 'P4'):
        source = data / (f'test_{phase}.parquet' if split == 'test' else 'validation.parquet')
        ids = pd.read_parquet(source, columns=['enrollment_id']).enrollment_id.astype(str)
        assert not ids.duplicated().any(), f'duplicate source IDs: {source}'
        frames = []
        for path, salt in zip((base, replay), salts):
            frame = pd.read_parquet(path / 'predictions' / f'{split}_{phase}.parquet')
            hashes = ids.map(lambda value: hashlib.sha256(f'{salt}|{value}'.encode()).hexdigest())
            assert not frame.enrollment_id_hash.duplicated().any()
            frame = frame.set_index('enrollment_id_hash').reindex(hashes)
            assert len(frame) == len(ids) and frame.y_true.notna().all(), 'unmatched IDs'
            frames.append(frame.reset_index(drop=True))
        x, y = frames
        delta = max(float(np.max(np.abs(x[c].to_numpy() - y[c].to_numpy()))) for c in ('prob_c0', 'prob_c1', 'prob_c2'))
        same_true = x.y_true.equals(y.y_true)
        same_pred = x.y_pred.equals(y.y_pred)
        rows.append({'split': split, 'phase': phase, 'rows': len(ids), 'labels_equal': same_true,
                     'predictions_equal': same_pred, 'max_probability_delta': delta})
        assert same_true and same_pred and delta == 0.0
receipt = {'task': 'LO', 'window': 'W1', 'pipeline': 'V0', 'model': 'RNN', 'seed': 42,
           'baseline_commit': ma.get('runner_git_commit'), 'replay_commit': mb.get('runner_git_commit'),
           'best_epoch': ma['best_epoch'], 'identity_method': 'source_enrollment_id_hashed_with_each_run_salt',
           'contract_fields_equal': keys, 'paired_exact': True, 'cells': rows}
out = root / 'LO/resuilt/lo_static_v2_cohort_audit_20261028/paired_replay_equivalence.json'
out.write_text(json.dumps(receipt, indent=2), encoding='utf-8')
print(json.dumps(receipt, indent=2))
