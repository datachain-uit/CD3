"""Compute subgroup evaluation mask counts, with ALL parity against S0 v4.

Intermediate evidence only. Zero-cell counts require the unscaled raw views.
"""
import json
import os
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'tmp/s0_v5_inputs'
FLAGS = Path(os.environ.get('TEMPO_PHASEB_FLAGS_ROOT', ROOT / 'tmp/phaseB'))
OUT = ROOT / 'CQ/resuilt/s0_v5_subgroup_preflight_20261122'
PHASE = re.compile(r'^(.*)_P([1-4])$')
SUBS = [('ALL', 'ALL'), ('LEARNER', 'SEEN'), ('LEARNER', 'UNSEEN'), ('COURSE', 'SEEN'), ('COURSE', 'UNSEEN')]


def modality(stem):
    for group, prefixes in [('video', ('segment_', 'video_', 'watch_', 'avg_playback', 'fast_forward', 'unique_video', 'most_common_hour')),
                            ('problem', ('problem_', 'exercise_', 'score_', 'correct_', 'incorrect_', 'attempts_', 'submit_')),
                            ('comment', ('comment_', 'positive_', 'negative_', 'neutral_', 'avg_comment', 'min_comment', 'max_comment'))]:
        if stem.startswith(prefixes):
            return group
    return None


def run(task):
    flags = pd.read_parquet(FLAGS / f'seen_flags_{task}.parquet', columns=['window_id', 'split_name', 'phase_id', 'enrollment_id', 'seen_learner', 'seen_course'])
    if flags.duplicated(['window_id', 'split_name', 'phase_id', 'enrollment_id']).any():
        raise ValueError(f'{task}: duplicate flag keys')
    lookup = {(w, s, p): d.set_index('enrollment_id')[['seen_learner', 'seen_course']]
              for (w, s, p), d in flags.groupby(['window_id', 'split_name', 'phase_id'], sort=False)}
    del flags
    rows = []
    for window in ('W1', 'W2', 'W3'):
        for split, phases in [('VALIDATION', (1, 2, 3, 4)), ('TEST', (1, 2, 3, 4))]:
            for k in phases:
                path = DATA / task / 'evaluation' / window / 'V0' / ('validation.parquet' if split == 'VALIDATION' else f'test_P{k}.parquet')
                parquet = pq.ParquetFile(path)
                names = parquet.schema_arrow.names
                masks = [n for n in names if n.startswith('missing__')]
                parsed = []
                for n in masks:
                    m = PHASE.match(n.removeprefix('missing__'))
                    parsed.append((int(m.group(2)), modality(m.group(1))) if m else (0, None))
                cols = ['enrollment_id'] + masks + [f'{m}_observed_mask_P{p}' for m in ('video', 'problem', 'comment') for p in range(1, 5)]
                selected = np.array([i for i, (p, _) in enumerate(parsed) if p == 0 or p <= k])
                future = sum(p > k for p, _ in parsed)
                acc = {sub: {'n': 0, 'missing': 0, 'structural': 0, 'pool_missing': 0, 'pool_structural': 0} for sub in SUBS}
                for batch in parquet.iter_batches(batch_size=16000, columns=cols):
                    f = batch.to_pandas()
                    fl = lookup[(window, split, f'P{k}')].reindex(f.enrollment_id)
                    if fl.isna().any().any():
                        raise ValueError(f'{task}/{window}/{split}/P{k}: incomplete flag join')
                    arr = f[masks].to_numpy(dtype=np.int8, copy=False)
                    if not np.isin(arr, (0, 1)).all():
                        raise ValueError('non-binary missing flags')
                    structural_per_row = np.zeros(len(f), dtype=np.int32)
                    pool_structural = np.zeros(len(f), dtype=np.int32)
                    for phase in range(1, 5):
                        for group in ('video', 'problem', 'comment'):
                            count = sum(p == phase and m == group for p, m in parsed)
                            if count:
                                unavailable = f[f'{group}_observed_mask_P{phase}'].to_numpy() == 0
                                pool_structural += unavailable * count
                                if phase <= k:
                                    structural_per_row += unavailable * count
                    missing_row = arr[:, selected].sum(axis=1, dtype=np.int32)
                    pool_missing = arr.sum(axis=1, dtype=np.int32)
                    for axis, value in SUBS:
                        sel = np.ones(len(f), dtype=bool) if axis == 'ALL' else fl['seen_' + axis.lower()].to_numpy() == int(value == 'SEEN')
                        a = acc[(axis, value)]
                        a['n'] += int(sel.sum())
                        a['missing'] += int(missing_row[sel].sum())
                        a['structural'] += int(structural_per_row[sel].sum())
                        a['pool_missing'] += int(pool_missing[sel].sum())
                        a['pool_structural'] += int(pool_structural[sel].sum())
                for (axis, value), a in acc.items():
                    n = a['n']; total = n * len(masks); unavailable = n * future
                    eligible = total - unavailable - a['structural']
                    row = {'task': task, 'window_id': window, 'eval_split': split, 'phase_id': f'P{k}', 'subgroup_axis': axis, 'subgroup_value': value,
                           'ev_n_enrollments': n, 'ev_n_cells_total': total, 'ev_n_cells_unavailable': unavailable,
                           'ev_n_cells_structural_absence': a['structural'], 'ev_n_cells_observed_eligible': eligible,
                           'ev_n_cells_observed_missing': a['missing'], 'ev_n_cells_observed_value': eligible - a['missing'],
                           'ev_missing_rate': a['missing'] / eligible if eligible else np.nan}
                    if split == 'VALIDATION' and k < 4:
                        row.update(evpool_n_cells_total=total, evpool_n_cells_unavailable=0, evpool_n_cells_structural_absence=a['pool_structural'],
                                   evpool_n_cells_observed_eligible=total-a['pool_structural'], evpool_n_cells_observed_missing=a['pool_missing'],
                                   evpool_n_cells_observed_value=total-a['pool_structural']-a['pool_missing'],
                                   evpool_missing_rate=a['pool_missing']/(total-a['pool_structural']) if total>a['pool_structural'] else np.nan)
                    rows.append(row)
                print(json.dumps({'task': task, 'window': window, 'split': split, 'phase': f'P{k}', 'status': 'computed'}), flush=True)
    out = pd.DataFrame(rows)
    ref = pd.read_parquet(ROOT / 'CQ/resuilt/m13a_s0_profile_20261109_v4/s0_profile.parquet')
    keys = ['task', 'window_id', 'eval_split', 'phase_id']
    paired = out[out.subgroup_axis.eq('ALL')].merge(ref, on=keys, validate='one_to_one', suffixes=('_new', '_v4'))
    errors = {}
    for col in ('ev_n_enrollments', 'ev_n_cells_total', 'ev_n_cells_unavailable', 'ev_n_cells_structural_absence', 'ev_n_cells_observed_eligible', 'ev_n_cells_observed_missing', 'ev_n_cells_observed_value', 'ev_missing_rate'):
        a, b = paired[col+'_new'], paired[col+'_v4']
        if a.isna().ne(b.isna()).any():
            raise ValueError(f'{task}: ALL null pattern differs for {col}')
        errors[col] = float((a-b).abs().max())
    if len(out) != 120 or max(errors.values()) > 1e-10:
        raise ValueError(f'{task}: ALL mask parity failed: {errors}')
    out.to_parquet(OUT / f'eval_masks_{task}.parquet', index=False)
    (OUT / f'eval_masks_{task}_qa.json').write_text(json.dumps({'task': task, 'status': 'INTERMEDIATE_ONLY', 'rows': len(out), 'parity': errors}, indent=2), encoding='utf-8')
    print(json.dumps({'task': task, 'status': 'PASS', 'parity': errors}), flush=True)


if __name__ == '__main__':
    for task in (sys.argv[1:] or ['CQ', 'LO']):
        run(task)
