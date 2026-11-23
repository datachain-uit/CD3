"""Compute raw-value zero cell counts for evaluation subgroup slices."""
import json
import os
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / 'downloads/raw_views_20261108'
DATA = ROOT / 'tmp/s0_v5_inputs'
OUT = ROOT / 'CQ/resuilt/s0_v5_subgroup_preflight_20261122'
FLAGS = Path(os.environ.get('TEMPO_PHASEB_FLAGS_ROOT', ROOT / 'tmp/phaseB'))
VIEWS = {'CQ': 'CQ/phase_views_v2_2', 'LO': 'LO/phase_views_v3_1_scored_signal_excluded'}
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
        raise ValueError('duplicate seen keys')
    lookup = {(w, s, p): d.set_index('enrollment_id')[['seen_learner', 'seen_course']]
              for (w, s, p), d in flags.groupby(['window_id', 'split_name', 'phase_id'], sort=False)}
    del flags
    input_schema = pq.ParquetFile(DATA / task / 'evaluation/W1/V0/validation.parquet').schema_arrow.names
    names = [n.removeprefix('missing__') for n in input_schema if n.startswith('missing__')]
    view = sorted((RAW / VIEWS[task]).glob('part-*.parquet'))
    if len(view) != 1:
        raise ValueError(f'{task}: expected one raw phase-view file, got {len(view)}')
    raw_names = set(pq.ParquetFile(view[0]).schema_arrow.names)
    fields = []
    for name in names:
        m = PHASE.match(name)
        phase = int(m.group(2)) if m else 0
        stem = m.group(1) if m else name
        source = name
        transform = None
        if stem in ('most_common_hour_sin', 'most_common_hour_cos'):
            source = f'most_common_hour_P{phase}' if phase else 'most_common_hour'
            transform = 'sin' if stem.endswith('_sin') else 'cos'
        if source not in raw_names:
            raise ValueError(f'{task}: missing raw source for {name}: {source}')
        fields.append((source, phase, modality(stem), transform))
    columns = list(dict.fromkeys(['window', 'split', 'enrollment_id'] + [x[0] for x in fields] +
                                 [f'{m}_observed_mask_P{k}' for m in ('video', 'problem', 'comment') for k in range(1, 5)]))
    accum = {}
    inputs = [('VALIDATION', None, view)] + [('TEST', k, sorted((RAW / f'{task}_test/P{k}').glob('part-*.parquet'))) for k in range(1, 5)]
    for split, only, paths in inputs:
        if not paths:
            raise ValueError(f'no raw source for {task}/{split}/{only}')
        for path in paths:
            for batch in pq.ParquetFile(path).iter_batches(batch_size=16000, columns=columns):
                frame = batch.to_pandas()
                for window in ('W1', 'W2', 'W3'):
                    d = frame[(frame.window == window) & frame.split.str.upper().eq(split)]
                    if d.empty:
                        continue
                    for k in ([only] if only else range(1, 5)):
                        fl = lookup[(window, split, f'P{k}')].reindex(d.enrollment_id)
                        if fl.isna().any().any():
                            raise ValueError(f'{task}/{window}/{split}/P{k}: missing seen flag')
                        zero = np.zeros(len(d), dtype=np.int32)
                        full_zero = np.zeros(len(d), dtype=np.int32)
                        for source, phase, group, transform in fields:
                            v = pd.to_numeric(d[source], errors='coerce').to_numpy(dtype=float)
                            if transform == 'sin': v = np.sin(2*np.pi*v/24)
                            if transform == 'cos': v = np.cos(2*np.pi*v/24)
                            z = v == 0
                            if group and phase:
                                z &= d[f'{group}_observed_mask_P{phase}'].fillna(0).to_numpy() != 0
                            full_zero += z
                            if phase <= k: zero += z
                        for axis, value in SUBS:
                            sel = np.ones(len(d), dtype=bool) if axis == 'ALL' else fl['seen_'+axis.lower()].to_numpy() == int(value == 'SEEN')
                            key = (window, split, f'P{k}', axis, value)
                            a = accum.setdefault(key, [0, 0])
                            a[0] += int(zero[sel].sum()); a[1] += int(full_zero[sel].sum())
        print(json.dumps({'task': task, 'split': split, 'phase': only or 'ALL', 'status': 'computed'}), flush=True)
    rows = [{'task': task, 'window_id': w, 'eval_split': s, 'phase_id': p, 'subgroup_axis': a, 'subgroup_value': v,
             'ev_n_cells_observed_zero': counts[0], 'evpool_n_cells_observed_zero': counts[1] if s == 'VALIDATION' and p != 'P4' else None}
            for (w, s, p, a, v), counts in accum.items()]
    out = pd.DataFrame(rows)
    if len(out) != 120: raise ValueError(f'{task}: wrong coverage {len(out)}')
    ref = pd.read_parquet(ROOT / 'CQ/resuilt/m13a_s0_profile_20261109_v4/s0_profile.parquet')
    keys = ['task', 'window_id', 'eval_split', 'phase_id']
    joined = out[out.subgroup_axis.eq('ALL')].merge(ref, on=keys, validate='one_to_one', suffixes=('_new', '_v4'))
    errors = {}
    for c in ('ev_n_cells_observed_zero', 'evpool_n_cells_observed_zero'):
        valid = joined[c+'_v4'].notna()
        errors[c] = float((joined.loc[valid, c+'_new']-joined.loc[valid, c+'_v4']).abs().max()) if valid.any() else 0.
    if max(errors.values()) != 0: raise ValueError(f'{task}: ALL raw-zero parity failed: {errors}')
    out.to_parquet(OUT / f'eval_zero_{task}.parquet', index=False)
    (OUT / f'eval_zero_{task}_qa.json').write_text(json.dumps({'task': task, 'status': 'INTERMEDIATE_ONLY', 'parity': errors}, indent=2), encoding='utf-8')
    print(json.dumps({'task': task, 'status': 'PASS', 'parity': errors}), flush=True)


if __name__ == '__main__':
    for task in (sys.argv[1:] or ['CQ', 'LO']): run(task)
