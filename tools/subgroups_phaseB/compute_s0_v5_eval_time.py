"""Compute subgroup S0 sample counts, offering counts and observed times.

Intermediate evidence only; it is not a complete S0 v5 profile.
Uses the exact raw-view time convention recorded in the S0 v4 builder.
"""
import json
import os
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
FLAGS = Path(os.environ.get('TEMPO_PHASEB_FLAGS_ROOT', ROOT / 'tmp/phaseB'))
OUT = ROOT / 'CQ/resuilt/s0_v5_subgroup_preflight_20261122'
VIEW = {'CQ': 'CQ/phase_views_v2_2', 'LO': 'LO/phase_views_v3_1_scored_signal_excluded'}
RAW = ROOT / 'downloads/raw_views_20261108'
SUBS = [('LEARNER', 'SEEN'), ('LEARNER', 'UNSEEN'), ('COURSE', 'SEEN'), ('COURSE', 'UNSEEN')]


def compute(task):
    flags = pd.read_parquet(FLAGS / f'seen_flags_{task}.parquet', columns=['window_id', 'split_name', 'phase_id', 'enrollment_id', 'seen_learner', 'seen_course'])
    keys = ['window_id', 'split_name', 'phase_id', 'enrollment_id']
    if flags.duplicated(keys).any():
        raise ValueError(f'{task}: duplicate flag keys')
    lookup = {(w, s, p): d.set_index('enrollment_id')[['seen_learner', 'seen_course']]
              for (w, s, p), d in flags.groupby(['window_id', 'split_name', 'phase_id'], sort=False)}
    del flags
    stats = {}
    def update(frame, window, split, phase):
        if frame.empty:
            return
        keyed = lookup[(window, split, phase)]
        found = keyed.reindex(frame.enrollment_id)
        if found.isna().any().any():
            raise ValueError(f'{task}/{window}/{split}/{phase}: missing flag join')
        cutoff = pd.to_datetime(frame[f'cutoff_time_{phase}']).reset_index(drop=True)
        end = pd.to_datetime(frame.window_end_exclusive).reset_index(drop=True)
        enroll = pd.to_datetime(frame.enrollment_id.str.split('::').str[2]).reset_index(drop=True)
        total = np.floor((end - enroll).dt.total_seconds().to_numpy() / 86400)
        length = np.floor((cutoff - enroll).dt.total_seconds().to_numpy() / 86400)
        ok = (total > 0) & np.isfinite(length)
        for axis, value in [('ALL', 'ALL')] + SUBS:
            mask = np.ones(len(frame), dtype=bool) if axis == 'ALL' else found['seen_' + axis.lower()].to_numpy() == int(value == 'SEEN')
            key = (window, split, phase, axis, value)
            a = stats.setdefault(key, {'n': 0, 'valid': 0, 'length': 0., 'fraction': 0., 'offerings': set()})
            selected = ok & mask
            a['n'] += int(mask.sum())
            a['valid'] += int(selected.sum())
            a['length'] += float(length[selected].sum())
            a['fraction'] += float((length[selected] / total[selected]).sum())
            a['offerings'].update(zip(frame.offering_id.to_numpy()[mask], frame.timeline_source.to_numpy()[mask]))
    sources = [('VALIDATION', None, RAW / VIEW[task])] + [('TEST', f'P{k}', RAW / f'{task}_test/P{k}') for k in range(1, 5)]
    for split, only_phase, folder in sources:
        paths = sorted(folder.glob('part-*.parquet'))
        if not paths:
            raise FileNotFoundError(folder)
        phases = [only_phase] if only_phase else [f'P{k}' for k in range(1, 5)]
        cols = ['window', 'split', 'enrollment_id', 'offering_id', 'timeline_source', 'window_end_exclusive'] + [f'cutoff_time_{p}' for p in phases]
        for path in paths:
            for batch in pq.ParquetFile(path).iter_batches(batch_size=100000, columns=cols):
                frame = batch.to_pandas()
                for window in ('W1', 'W2', 'W3'):
                    part = frame[(frame.window == window) & frame.split.str.upper().eq(split)]
                    for phase in phases:
                        update(part, window, split, phase)
        print(json.dumps({'task': task, 'split': split, 'phase': only_phase or 'ALL', 'stage': 'READ_COMPLETE'}), flush=True)
    rows = []
    for (window, split, phase, axis, value), a in stats.items():
        rows.append({'task': task, 'window_id': window, 'eval_split': split, 'phase_id': phase,
                     'subgroup_axis': axis, 'subgroup_value': value, 'ev_n_enrollments': a['n'],
                     'ev_n_offerings': len(a['offerings']),
                     'ev_mean_observed_length': a['length'] / a['valid'] if a['valid'] else None,
                     'ev_mean_observed_fraction': a['fraction'] / a['valid'] if a['valid'] else None})
    out = pd.DataFrame(rows)
    if len(out) != 120:
        raise ValueError(f'{task}: expected 120 rows, got {len(out)}')
    reference = pd.read_parquet(ROOT / 'CQ/resuilt/m13a_s0_profile_20261109_v4/s0_profile.parquet')
    keys = ['task', 'window_id', 'eval_split', 'phase_id']
    all_rows = out[out.subgroup_axis.eq('ALL')].merge(reference, on=keys, validate='one_to_one', suffixes=('_new', '_v4'))
    errors = {}
    for c in ('ev_n_enrollments', 'ev_n_offerings', 'ev_mean_observed_length', 'ev_mean_observed_fraction'):
        errors[c] = float((all_rows[c + '_new'] - all_rows[c + '_v4']).abs().max())
    if errors['ev_n_enrollments'] or errors['ev_n_offerings'] or max(errors.values()) > 1e-10:
        raise ValueError(f'{task}: ALL parity failed {errors}')
    OUT.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT / f'eval_time_{task}.parquet', index=False)
    (OUT / f'eval_time_{task}_qa.json').write_text(json.dumps({'task': task, 'rows': len(out), 'all_parity_max_abs': errors, 'status': 'INTERMEDIATE_ONLY'}, indent=2), encoding='utf-8')
    print(json.dumps({'task': task, 'status': 'PASS', 'parity': errors}), flush=True)


if __name__ == '__main__':
    for task in (sys.argv[1:] or ['CQ', 'LO']):
        compute(task)
