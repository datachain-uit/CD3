"""B.1 extras requested by the writer side (20/11 version 2, 21/11 section 3.2):
 (1) seen_end_date_spread_report.csv: offerings whose derived offering_end_date spreads over more than 60 s; per window x split x phase, the number of scored enrollments whose seen flags change if the
     earliest instead of the latest end date of the offering is used for the TRAIN history;
 (2) seen_course_crosswalk_48.csv: seen_course of the rule seen_v1_train_partition_only (history ended before the cutoff) against the SEEN_COURSE flag of audit_prediction_course_cohort.py
     (course_id occurs in the TRAIN partition of the window, no time condition); 48 rows = 2 tasks x 3 windows x 2 splits x 4 phases.
Inputs as build_seen_flags.py (local raw views).  usage: build_seen_extras.py [CQ] [LO]"""
import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1] / 'seed43_44_pipeline'))
from tempo_paths import REPO, WORK

RAW = Path(f'{REPO}/downloads/raw_views_20261108')
OUT = Path(f'{WORK}/phaseB')
VIEW = {'CQ': 'CQ/phase_views_v2_2', 'LO': 'LO/phase_views_v3_1_scored_signal_excluded'}
TEST = {'CQ': 'CQ_test', 'LO': 'LO_test'}
Q = {'P1': 0.25, 'P2': 0.50, 'P3': 0.75, 'P4': 0.90}
BASE = ['enrollment_id', 'window', 'split', 'offering_id', 'user_id', 'course_id'] + [f'cutoff_time_{p}' for p in Q]


def load(pattern):
    return pd.concat([pd.read_parquet(f, columns=BASE) for f in sorted(glob.glob(pattern))], ignore_index=True)


spread_rows, cross_rows = [], []
for task in (sys.argv[1:] or ['CQ', 'LO']):
    views = load(f'{RAW}/{VIEW[task]}/*.parquet')
    views['enroll_time'] = pd.to_datetime(views.enrollment_id.str.split('::').str[2])
    for p in Q:
        views[f'cutoff_time_{p}'] = pd.to_datetime(views[f'cutoff_time_{p}'])
    views['end'] = views.enroll_time + (views.cutoff_time_P4 - views.enroll_time) / Q['P4']
    g = views.groupby('offering_id').end.agg(['min', 'max'])
    g['spread_s'] = (g['max'] - g['min']).dt.total_seconds()
    wide = g[g.spread_s > 60]
    test = {p: load(f'{RAW}/{TEST[task]}/{p}/*.parquet') for p in Q}
    for p in Q:
        test[p]['cutoff_time_' + p] = pd.to_datetime(test[p]['cutoff_time_' + p])
    for w in sorted(views.window.unique()):
        tr = views[(views.window == w) & (views.split == 'train')].copy()
        end_min = tr.offering_id.map(g['min']); end_max = tr.offering_id.map(g['max'])
        fu = {k: tr.assign(e=e).groupby('user_id').e.min() for k, e in (('base', tr.end), ('early', end_min), ('late', end_max))}
        fc = {k: tr.assign(e=e).groupby('course_id').e.min() for k, e in (('base', tr.end), ('early', end_min), ('late', end_max))}
        train_courses = set(tr.course_id.unique())
        for split in ('VALIDATION', 'TEST'):
            for ph in Q:
                df = views[(views.window == w) & (views.split == 'validation')] if split == 'VALIDATION' else test[ph][test[ph].window == w]
                cut = df[f'cutoff_time_{ph}']
                base_sc = (df.course_id.map(fc['base']) < cut).fillna(False).to_numpy()
                base_sl = (df.user_id.map(fu['base']) < cut).fillna(False).to_numpy()
                early_sc = (df.course_id.map(fc['early']) < cut).fillna(False).to_numpy()
                early_sl = (df.user_id.map(fu['early']) < cut).fillna(False).to_numpy()
                late_sc = (df.course_id.map(fc['late']) < cut).fillna(False).to_numpy()
                late_sl = (df.user_id.map(fu['late']) < cut).fillna(False).to_numpy()
                in_wide = df.offering_id.isin(wide.index).to_numpy()
                spread_rows.append({'task': task, 'window_id': w, 'eval_split': split, 'phase_id': ph, 'n_eval': int(len(df)), 'offerings_spread_gt_60s': int(len(wide)),
                                    'max_spread_s': float(wide.spread_s.max()) if len(wide) else 0.0,
                                    'eval_enrollments_in_those_offerings': int(in_wide.sum()),
                                    'seen_course_flips_early_vs_late': int((early_sc != late_sc).sum()), 'seen_learner_flips_early_vs_late': int((early_sl != late_sl).sum()),
                                    'seen_course_flips_early_vs_base': int((early_sc != base_sc).sum()), 'seen_learner_flips_early_vs_base': int((early_sl != base_sl).sum())})
                audit_sc = df.course_id.isin(train_courses).to_numpy()
                cross_rows.append({'task': task, 'window_id': w, 'eval_split': split, 'phase_id': ph, 'n_eval': int(len(df)),
                                   'seen_course_rule': int(base_sc.sum()), 'seen_course_audit_cohort': int(audit_sc.sum()),
                                   'differ_total': int((base_sc != audit_sc).sum()), 'rule_seen_audit_unseen': int((base_sc & ~audit_sc).sum()), 'rule_unseen_audit_seen': int((~base_sc & audit_sc).sum()),
                                   'differ_share': round(float((base_sc != audit_sc).mean()), 6)})
    print(task, 'wide offerings', wide.spread_s.to_dict(), flush=True)
pd.DataFrame(spread_rows).to_csv(OUT / 'seen_end_date_spread_report.csv', index=False, lineterminator='\n')
c = pd.DataFrame(cross_rows)
c.to_csv(OUT / 'seen_course_crosswalk_48.csv', index=False, lineterminator='\n')
print(len(c), 'crosswalk rows; max differ share', c.differ_share.max(), '; total differ', int(c.differ_total.sum()), 'of', int(c.n_eval.sum()))
