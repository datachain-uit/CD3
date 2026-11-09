"""Recompute phase-prefix missingness from V0's preserved observed-missing masks.

P4 is checked against exact S0_RAW all-family counts before any prefix output
is accepted. Zero rates cannot be recovered reliably from scaled inputs.
"""
import hashlib
import json
import re
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path('CQ/resuilt/m13a_s0_profile_20261108')
TASKS = {
    'CQ': (Path('downloads/vastai/CQ_V2_2_clean_grain_seed42'), Path('CQ/resuilt/s0_current_cq_20261108/L2_facts/task=CQ'), 'CQ_label_final', {'warning': 0, 'average': 1, 'good': 2}),
    'LO': (Path('downloads/vastai/LO_V3_1_clean_grain_seed42'), Path('LO/resuilt/s0_current_lo_modal_20261108/L2_facts'), 'LO_performance_label_3', {'I/D': 0, 'G': 1, 'E': 2}),
}
PHASE = re.compile(r'^(.*)_P([1-4])$')

def modality(stem):
    if stem.startswith(('segment_', 'video_', 'watch_', 'avg_playback', 'fast_forward', 'unique_video', 'most_common_hour')):
        return 'video'
    if stem.startswith(('problem_', 'exercise_', 'score_', 'correct_', 'incorrect_', 'attempts_', 'submit_')):
        return 'problem'
    if stem.startswith(('comment_', 'positive_', 'negative_', 'neutral_', 'avg_comment', 'min_comment', 'max_comment')):
        return 'comment'
    return None

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for b in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()

def mutual_info(ones, classes, n):
    if n == 0:
        return None
    result = np.zeros(ones.shape[1], dtype=np.float64)
    for c in range(3):
        for value in (0, 1):
            joint_count = ones[c] if value else classes[c] - ones[c]
            row_count = ones.sum(axis=0) if value else n - ones.sum(axis=0)
            good = (joint_count > 0) & (row_count > 0) & (classes[c] > 0)
            result[good] += (joint_count[good] / n) * np.log((joint_count[good] * n) / (row_count[good] * classes[c]))
    return float(result.max()) if len(result) else None

records = []
for task, (data, s0, label, class_map) in TASKS.items():
    for window in ('W1', 'W2', 'W3'):
        for split in ('TRAIN', 'VALIDATION'):
            path = data / (f'train/{window}/V0/train.parquet' if split == 'TRAIN' else f'evaluation/{window}/V0/validation.parquet')
            parquet = pq.ParquetFile(path)
            names = parquet.schema_arrow.names
            masks = [name for name in names if name.startswith('missing__')]
            parsed = []
            for name in masks:
                match = PHASE.match(name.removeprefix('missing__'))
                parsed.append((int(match.group(2)), modality(match.group(1))) if match else (0, None))
            needed = masks + [f'{kind}_observed_mask_P{i}' for kind in ('video', 'problem', 'comment') for i in range(1, 5)]
            if split == 'TRAIN':
                needed.append(label)
            needed = list(dict.fromkeys(needed))
            missing = set(needed).difference(names)
            if missing:
                raise ValueError(f'Missing expected columns in {path}: {sorted(missing)}')
            selected = {k: np.array([i for i, (phase, _) in enumerate(parsed) if phase == 0 or phase <= k], dtype=int) for k in range(1, 5)}
            acc = {k: {'rows': 0, 'missing': 0, 'structural': 0, 'incomplete': 0,
                       'ones': np.zeros((3, len(masks)), dtype=np.int64), 'classes': np.zeros(3, dtype=np.int64)} for k in range(1, 5)}
            for batch in parquet.iter_batches(batch_size=32768, columns=needed):
                frame = batch.to_pandas()
                arr = frame[masks].to_numpy(dtype=np.int8, copy=False)
                if ((arr != 0) & (arr != 1)).any():
                    raise ValueError(f'Nonbinary missing flag in {path}')
                n = len(frame)
                labels = None
                if split == 'TRAIN':
                    labels = frame[label].map(class_map)
                    if labels.isna().any():
                        raise ValueError('Unknown training label')
                    labels = labels.to_numpy(dtype=np.int8)
                for k in range(1, 5):
                    a = acc[k]; index = selected[k]; current = arr[:, index]
                    a['rows'] += n
                    a['missing'] += int(current.sum(dtype=np.int64))
                    a['incomplete'] += int(current.any(axis=1).sum())
                    for phase in range(1, k + 1):
                        for kind in ('video', 'problem', 'comment'):
                            idx = [i for i, (p, m) in enumerate(parsed) if p == phase and m == kind]
                            if not idx:
                                continue
                            available = frame[f'{kind}_observed_mask_P{phase}'].to_numpy()
                            if not np.isin(available, (0, 1)).all():
                                raise ValueError('Invalid modality mask')
                            structural = available == 0
                            if arr[structural][:, idx].any():
                                raise ValueError('Missing flag set for structural cell')
                            a['structural'] += int(structural.sum()) * len(idx)
                    if labels is not None:
                        for c in range(3):
                            subset = labels == c
                            a['classes'][c] += int(subset.sum())
                            a['ones'][c] += arr[subset].sum(axis=0, dtype=np.int64)
            dq = pd.read_parquet(s0 / f'window_id={window}/phase_id=P4/dq_feature_profile.parquet')
            reference = dq[(dq.split == split) & (dq.feature_family == 'all')].iloc[0]
            full = acc[4]
            if full['rows'] != int(parquet.metadata.num_rows) or full['missing'] != int(reference.n_cells_observed_missing) or full['structural'] != int(reference.n_cells_structural_absence) or full['rows'] * len(masks) != int(reference.n_cells_total):
                raise ValueError(f'P4 masks fail S0 count parity: {task}/{window}/{split}')
            file_sha = sha(path)
            dynamic_per_phase = {k: sum(p == k for p, _ in parsed) for k in range(1, 5)}
            for k in range(1, 5):
                a = acc[k]; n = a['rows']; total = n * len(masks)
                unavailable = n * sum(dynamic_per_phase[j] for j in range(k + 1, 5))
                eligible = total - unavailable - a['structural']
                record = {'task': task, 'window_id': window, 'phase_id': f'P{k}', 'split': split,
                          'n_rows': n, 'n_cells_total': total, 'n_cells_unavailable': unavailable,
                          'n_cells_structural_absence': a['structural'], 'n_cells_observed_eligible': eligible,
                          'n_cells_observed_missing': a['missing'], 'n_cells_observed_value': eligible - a['missing'],
                          'missing_rate': a['missing'] / eligible if eligible else None,
                          'unavailable_rate': unavailable / total if total else None,
                          'structural_absence_rate': a['structural'] / total if total else None,
                          'source_file_sha256': file_sha, 'p4_s0_count_parity': 'PASS'}
                if split == 'TRAIN':
                    record['incomplete_history_ratio'] = a['incomplete'] / n if n else None
                    record['missing_label_mi_max'] = mutual_info(a['ones'][:, selected[k]], a['classes'], n)
                records.append(record)
            print(json.dumps({'task': task, 'window': window, 'split': split, 'rows': full['rows'], 'p4_parity': 'PASS'}), flush=True)
out = pd.DataFrame(records)
if len(out) != 48 or out.duplicated(['task', 'window_id', 'phase_id', 'split']).any():
    raise ValueError('Prefix mask profile coverage mismatch')
out.to_parquet(ROOT / 'prefix_mask_profile.parquet', index=False)
out.to_csv(ROOT / 'prefix_mask_profile.csv', index=False)
print('PREFIX_MASK_PROFILE_COMPLETE', len(out), flush=True)
