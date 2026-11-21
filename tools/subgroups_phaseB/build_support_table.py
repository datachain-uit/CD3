"""B.1 deliverable: subgroup_slice_support.csv, 240 rows = 2 tasks x 3 windows x 2 splits x 4 phases x 5 subgroups (ALL plus the four seen/unseen slices)."""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1] / 'seed43_44_pipeline'))
from tempo_paths import REPO, WORK
import glob
import numpy as np
import pandas as pd

RAW = f'{REPO}/downloads/raw_views_20261108'
CFG = {'CQ': ('CQ/phase_views_v2_2', 'CQ_test', 'CQ_label_final', ('warning', 'average', 'good')),
       'LO': ('LO/phase_views_v3_1_scored_signal_excluded', 'LO_test', 'LO_performance_label_3', ('I/D', 'G', 'E'))}
out = []
for task, (view, test, lab, classes) in CFG.items():
    fl = pd.read_parquet(f'{WORK}/phaseB/seen_flags_{task}.parquet')
    val = pd.concat([pd.read_parquet(f, columns=['enrollment_id', 'window', 'split', lab]) for f in glob.glob(f'{RAW}/{view}/*.parquet')])
    val = val[val.split == 'validation']
    cmap = {c: i for i, c in enumerate(classes)}
    for split, phase_src in (('VALIDATION', None), ('TEST', 'test')):
        for ph in ('P1', 'P2', 'P3', 'P4'):
            if split == 'VALIDATION':
                lb = val[['enrollment_id', 'window', lab]].rename(columns={'window': 'window_id'})
            else:
                lb = pd.concat([pd.read_parquet(f, columns=['enrollment_id', 'window', lab]) for f in glob.glob(f'{RAW}/{test}/{ph}/*.parquet')]).rename(columns={'window': 'window_id'})
            lb['y'] = lb[lab].astype(str).map(cmap)
            f_ = fl[(fl.split_name == split) & (fl.phase_id == ph)].merge(lb[['enrollment_id', 'window_id', 'y']], on=['enrollment_id', 'window_id'], how='left')
            for w, g in f_.groupby('window_id'):
                for axis, val_, mask in (('ALL', 'ALL', np.ones(len(g), bool)), ('LEARNER', 'SEEN', g.seen_learner.to_numpy() == 1), ('LEARNER', 'UNSEEN', g.seen_learner.to_numpy() == 0),
                                         ('COURSE', 'SEEN', g.seen_course.to_numpy() == 1), ('COURSE', 'UNSEEN', g.seen_course.to_numpy() == 0)):
                    s = g[mask]; sup = np.bincount(s.y.dropna().astype(int), minlength=3)
                    n = int(len(s)); present = int((sup > 0).sum())
                    out.append({'task': task, 'window_id': w, 'eval_split': split, 'phase_id': ph, 'subgroup_axis': axis, 'subgroup_value': val_, 'n_eval': n, 'c0_support': int(sup[0]), 'c1_support': int(sup[1]), 'c2_support': int(sup[2]),
                                'n_offerings': int(s.offering_id.nunique()), 'n_unlabelled': int(s.y.isna().sum()),
                                'slice_status': 'SLICE_EMPTY' if n == 0 else ('ONE_CLASS' if present == 1 else 'OK'),
                                'small_subgroup_flag': bool(n < 30 or (sup < 5).any())})
d = pd.DataFrame(out)
d.to_csv(f'{WORK}/phaseB/subgroup_slice_support.csv', index=False, lineterminator='\n')
print(len(d), d.slice_status.value_counts().to_dict(), 'small_subgroup_flag', int(d.small_subgroup_flag.sum()), 'unlabelled', int(d.n_unlabelled.sum()))
print(d[d.slice_status != 'OK'].head(10).to_string())
