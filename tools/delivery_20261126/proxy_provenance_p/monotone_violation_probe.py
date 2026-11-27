# -*- coding: utf-8 -*-
"""Probe: enrollments where score_sum_Pk > score_sum_P(k+1) in the LO phase view (read only)."""
import os, glob
import numpy as np, pandas as pd, pyarrow.parquet as pq
REPO = os.environ['TEMPO_REPO_ROOT']; OUT = os.environ['P_OUT']
p = glob.glob(f'{REPO}/downloads/raw_views_20261108/LO/phase_views_v3_1_scored_signal_excluded/*.parquet')[0]
cols = ['enrollment_id', 'window', 'split'] + [f'{n}_P{k}' for k in (1, 2, 3, 4) for n in ('score_sum', 'problem_count', 'attempts_sum', 'problem_score_catalog_coverage')]
df = pq.read_table(p, columns=cols).to_pandas()
res = []
for k in (1, 2, 3):
    a, b = df[f'score_sum_P{k}'], df[f'score_sum_P{k+1}']
    m = a.notna() & b.notna()
    v = m & (a > b + 1e-9)
    res.append(dict(pair=f'P{k}->P{k+1}', n_both=int(m.sum()), n_decrease=int(v.sum()),
                    min_score_sum_P_all=float(df[f'score_sum_P{k}'].min()),
                    n_negative_score_sum=int((df[f'score_sum_P{k}'] < 0).sum()),
                    same_problem_count_among_decrease=float((df.loc[v, f'problem_count_P{k}'] == df.loc[v, f'problem_count_P{k+1}']).mean()) if v.any() else None,
                    median_drop=float((a[v] - b[v]).median()) if v.any() else None))
r = pd.DataFrame(res); r.to_csv(f'{OUT}/monotone_violation_probe.csv', index=False); print(r.to_string())
