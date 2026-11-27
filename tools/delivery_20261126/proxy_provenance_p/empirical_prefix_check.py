# -*- coding: utf-8 -*-
"""P.1 empirical checks on the local LO phase views (read only). Run: python -I empirical_prefix_check.py
Env: TEMPO_REPO_ROOT, P_OUT."""
import os, glob, json
import numpy as np, pandas as pd, pyarrow.parquet as pq
REPO = os.environ['TEMPO_REPO_ROOT']; OUT = os.environ['P_OUT']
RAW = f'{REPO}/downloads/raw_views_20261108'
main = glob.glob(f'{RAW}/LO/phase_views_v3_1_scored_signal_excluded/*.parquet')[0]
P = (1, 2, 3, 4)
cols = ['enrollment_id', 'window', 'split', 'course_id', 'video_counts']
for k in P:
    cols += [f'{n}_P{k}' for n in ('unique_video_count', 'video_catalog_coverage', 'problem_count', 'problem_catalog_coverage', 'score_sum',
                                   'problem_score_catalog_coverage', 'course_problem_count', 'course_problem_full_score_sum', 'phase_available')]
df = pq.read_table(main, columns=cols).to_pandas()
rows = []
def add(check, scope, value, note=''):
    rows.append(dict(check=check, scope=scope, value=value, note=note)); print(rows[-1], flush=True)

add('n_rows', 'main view', len(df), 'rows (enrollment x window); splits: ' + json.dumps(df.split.value_counts().to_dict()))
for w, g in df.groupby('window'):
    sc = f'main view window={w}'
    for k in P:
        # recomputation of the three ratios
        vc = g[f'unique_video_count_P{k}'] / g['video_counts']
        m = g[f'video_catalog_coverage_P{k}'].notna()
        add(f'video_cov_P{k}: max|value - unique_video_count/video_counts|', sc, float((vc[m] - g.loc[m, f'video_catalog_coverage_P{k}']).abs().max()), f'n={int(m.sum())}')
        pc = g[f'problem_count_P{k}'] / g[f'course_problem_count_P{k}']
        m = g[f'problem_catalog_coverage_P{k}'].notna()
        add(f'problem_cov_P{k}: max|value - problem_count/course_problem_count|', sc, float((pc[m] - g.loc[m, f'problem_catalog_coverage_P{k}']).abs().max()), f'n={int(m.sum())}')
        ps = g[f'score_sum_P{k}'] / g[f'course_problem_full_score_sum_P{k}']
        m = g[f'problem_score_catalog_coverage_P{k}'].notna()
        add(f'problem_score_cov_P{k}: max|value - score_sum/course_problem_full_score_sum|', sc, float((ps[m] - g.loc[m, f'problem_score_catalog_coverage_P{k}']).abs().max()), f'n={int(m.sum())}')
        for n in ('video_catalog_coverage', 'problem_catalog_coverage', 'problem_score_catalog_coverage'):
            x = g[f'{n}_P{k}']
            add(f'{n}_P{k}: n_nonnull / share>1 / max', sc, f'{int(x.notna().sum())} / {float((x > 1).sum() / max(1, x.notna().sum())):.4f} / {float(x.max()):.4f}')
    # denominators are course level constants
    for n in ('video_counts', 'course_problem_count_P1', 'course_problem_count_P2', 'course_problem_count_P3', 'course_problem_count_P4',
              'course_problem_full_score_sum_P1', 'course_problem_full_score_sum_P2', 'course_problem_full_score_sum_P3', 'course_problem_full_score_sum_P4'):
        nu = g.groupby('course_id')[n].nunique(dropna=True)
        add(f'denominator {n}: courses with >1 distinct value', sc, int((nu > 1).sum()), f'courses={int(g.course_id.nunique())}')
    for a, b in (('course_problem_count', 'course_problem_count'), ('course_problem_full_score_sum', 'course_problem_full_score_sum')):
        d = max(float((g[f'{a}_P{k}'] - g[f'{b}_P4']).abs().max()) for k in (1, 2, 3))
        add(f'denominator {a}: max |P1..P3 - P4| (same enrollment)', sc, d)
    # prefix monotonicity (cumulative prefixes are non-decreasing)
    for base in ('unique_video_count', 'problem_count', 'score_sum'):
        for k in (1, 2, 3):
            a, b = g[f'{base}_P{k}'], g[f'{base}_P{k+1}']
            m = a.notna() & b.notna()
            add(f'monotone {base}: share P{k} > P{k+1}', sc, float((a[m] > b[m] + 1e-9).mean()), f'n_both={int(m.sum())}')
        # nulls
    for n in ('video_catalog_coverage', 'problem_catalog_coverage', 'problem_score_catalog_coverage'):
        for k in P:
            add(f'null share {n}_P{k}', sc, float(g[f'{n}_P{k}'].isna().mean()))
pd.DataFrame(rows).to_csv(f'{OUT}/empirical_main_view_checks.csv', index=False)

# test prefix views
rows = []
T = {}
for k in P:
    f = glob.glob(f'{RAW}/LO_test/P{k}/*.parquet')[0]
    _fam = ('video_catalog_coverage', 'problem_catalog_coverage', 'problem_score_catalog_coverage', 'unique_video_count', 'problem_count', 'score_sum')
    _names = pq.ParquetFile(f).schema_arrow.names
    _c = [c for c in ['enrollment_id', 'window', 'prediction_phase'] if c in _names] + [f'{n}_P{j}' for n in _fam for j in P]
    T[k] = pq.read_table(f, columns=_c).to_pandas()
    add('test view rows', f'LO_test/P{k}', len(T[k]), 'prediction_phase=' + str(T[k].prediction_phase.unique().tolist()) + ' cols=' + str(T[k].shape[1]))
fams = ('video_catalog_coverage', 'problem_catalog_coverage', 'problem_score_catalog_coverage', 'unique_video_count', 'problem_count', 'score_sum')
key = ['enrollment_id', 'window'] if 'window' in T[1].columns else ['enrollment_id']
add('join key used', 'LO_test', ','.join(key))
for k in P:
    for j in P:
        for n in fams:
            c = f'{n}_P{j}'
            nn = float(T[k][c].notna().mean())
            add(f'non-null share {c} in test view prefix P{k}', f'LO_test/P{k}', nn, 'visible' if j <= k else 'future slot (expected NULL)')
for k in (1, 2, 3):
    for j in range(1, k + 1):
        m = T[k][key + [f'{n}_P{j}' for n in fams]].merge(T[4][key + [f'{n}_P{j}' for n in fams]], on=key, suffixes=('_a', '_b'))
        for n in fams:
            a, b = m[f'{n}_P{j}_a'], m[f'{n}_P{j}_b']
            same = ((a == b) | (a.isna() & b.isna()))
            add(f'prefix-consistency {n}_P{j}: share equal in test view P{k} vs P4', f'LO_test P{k} vs P4', float(same.mean()), f'n_joined={len(m)}; n_diff={int((~same).sum())}')
pd.DataFrame(rows).to_csv(f'{OUT}/empirical_test_prefix_checks.csv', index=False)
