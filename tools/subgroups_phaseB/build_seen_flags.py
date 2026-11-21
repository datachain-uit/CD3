"""B.1: seen/unseen flags per evaluated enrollment, rule seen_v1_train_partition_only (tempo_fix/seen_flags.py definition, Table 10).

Inputs (local raw views): downloads/raw_views_20261108/{CQ/phase_views_v2_2, LO/phase_views_v3_1_scored_signal_excluded} (TRAIN and VALIDATION rows of all windows) and
{CQ_test,LO_test}/P1..P4 (TEST rows per phase). Per enrollment the views carry user_id, course_id, offering_id and cutoff_time_P1..P4; enroll_time is the third token of enrollment_id,
offering_end_date = enroll_time + (cutoff_time_P4 - enroll_time) / 0.90 (PHASE_Q P4 = 0.90; checked against P1 and P2 below).
Output: <OUT>/seen_flags_<task>.parquet, one row per (window, split, phase, enrollment_id); <OUT>/seen_flags_qa.json.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1] / 'seed43_44_pipeline'))
from tempo_paths import REPO, WORK
import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAW = Path(f'{REPO}/downloads/raw_views_20261108')
OUT = Path(f'{WORK}/phaseB')
VIEW = {'CQ': 'CQ/phase_views_v2_2', 'LO': 'LO/phase_views_v3_1_scored_signal_excluded'}
TEST = {'CQ': 'CQ_test', 'LO': 'LO_test'}
Q = {'P1': 0.25, 'P2': 0.50, 'P3': 0.75, 'P4': 0.90}
BASE = ['enrollment_id', 'window', 'split', 'offering_id', 'user_id', 'course_id'] + [f'cutoff_time_{p}' for p in Q]


def load(path_glob, extra=()):
    parts = [pd.read_parquet(f, columns=BASE + list(extra)) for f in sorted(glob.glob(path_glob))]
    return pd.concat(parts, ignore_index=True)


def enroll_time(ids):
    return pd.to_datetime(ids.str.split('::').str[2])


for task in (sys.argv[1:] or ['CQ', 'LO']):
    qa = {'task': task}
    views = load(f'{RAW}/{VIEW[task]}/*.parquet')
    views['enroll_time'] = enroll_time(views.enrollment_id)
    for p in Q:
        views[f'cutoff_time_{p}'] = pd.to_datetime(views[f'cutoff_time_{p}'])
    views['offering_end_date'] = views.enroll_time + (views.cutoff_time_P4 - views.enroll_time) / Q['P4']
    # QA: the other phases give the same end date (to the second)
    for p in ('P1', 'P2', 'P3'):
        alt = views.enroll_time + (views[f'cutoff_time_{p}'] - views.enroll_time) / Q[p]
        qa[f'max_abs_end_diff_{p}_vs_P4_seconds'] = float((alt - views.offering_end_date).abs().dt.total_seconds().max())
    # QA: one end date per offering (to the minute)
    spread = views.groupby('offering_id').offering_end_date.agg(lambda x: (x.max() - x.min()).total_seconds())
    qa['offerings'] = int(len(spread)); qa['offerings_end_date_spread_gt_60s'] = int((spread > 60).sum())
    qa['split_values'] = sorted(views.split.unique().tolist())
    test = {p: load(f'{RAW}/{TEST[task]}/{p}/*.parquet') for p in Q}   # TEST view of phase p = the rows evaluated at phase p
    for p in Q:
        test[p]['cutoff_time_' + p] = pd.to_datetime(test[p]['cutoff_time_' + p])
    qa['test_rows_by_window_phase'] = {f'{p}|{k}': int(v) for p in Q for k, v in test[p].groupby('window').size().items()}
    out = []
    for w in sorted(views.window.unique()):
        tr = views[(views.window == w) & (views.split == 'train')]
        first_user = tr.groupby('user_id').offering_end_date.min()
        first_course = tr.groupby('course_id').offering_end_date.min()
        train_offerings = set(tr.offering_id.unique())
        qa[f'train_rows_{w}'] = int(len(tr))
        for split_name in ('VALIDATION', 'TEST'):
            for p in Q:
                df = views[(views.window == w) & (views.split == 'validation')] if split_name == 'VALIDATION' else test[p][test[p].window == w]
                ev = df[['enrollment_id', 'user_id', 'course_id', 'offering_id', f'cutoff_time_{p}']].rename(columns={f'cutoff_time_{p}': 'cutoff_time'}).copy()
                ev['seen_learner'] = (ev.user_id.map(first_user) < ev.cutoff_time).fillna(False).astype(np.int8)
                ev['seen_course'] = (ev.course_id.map(first_course) < ev.cutoff_time).fillna(False).astype(np.int8)
                ev['seen_offering'] = ev.offering_id.isin(train_offerings).astype(np.int8)
                ev.insert(0, 'phase_id', p); ev.insert(0, 'split_name', split_name); ev.insert(0, 'window_id', w)
                out.append(ev)
    res = pd.concat(out, ignore_index=True)
    res['seen_rule_version'] = 'seen_v1_train_partition_only'
    res['seen_history_reference'] = 'TRAIN_PARTITION_ONLY'
    res.to_parquet(OUT / f'seen_flags_{task}.parquet', index=False)
    qa['rows'] = int(len(res)); qa['qa15_seen_offering_nonzero_rows'] = int(res.seen_offering.sum())
    g = res.groupby(['window_id', 'split_name', 'phase_id'])
    qa['shares'] = {f'{k[0]}|{k[1]}|{k[2]}': [round(float(v.seen_learner.mean()), 4), round(float(v.seen_course.mean()), 4), int(len(v))] for k, v in g}
    (OUT / f'seen_flags_qa_{task}.json').write_text(json.dumps(qa, indent=1), encoding='utf-8')
    print(task, 'rows', len(res), 'QA15 nonzero', qa['qa15_seen_offering_nonzero_rows'], 'end diffs', [qa[f'max_abs_end_diff_{p}_vs_P4_seconds'] for p in ('P1', 'P2', 'P3')], 'end spread>60s', qa['offerings_end_date_spread_gt_60s'], '/', qa['offerings'])
