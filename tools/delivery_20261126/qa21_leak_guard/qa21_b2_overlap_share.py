# -*- coding: utf-8 -*-
"""QA21 phan 2, doc nghiem hon (thong tin): ti le dong VALIDATION/TEST co thoi diem du doan (cutoff_k) < tau_w, tuc la co nhan TRAIN
ket thuc SAU thoi diem du doan cua dong do (temporal_strict_Pk = 0, OVERLAP). Tu phase view local. Env: TEMPO_REPO_ROOT, QA21_OUT."""
import os, glob
import pandas as pd, pyarrow.parquet as pq
REPO = os.environ['TEMPO_REPO_ROOT']; OUT = os.environ['QA21_OUT']
RAW = f'{REPO}/downloads/raw_views_20261108'
MAIN = {'CQ': 'CQ/phase_views_v2_2', 'LO': 'LO/phase_views_v3_1_scored_signal_excluded'}
TESTD = {'CQ': 'CQ_test', 'LO': 'LO_test'}
rows = []
for task in ['CQ', 'LO']:
    cols = ['window', 'split'] + [f'temporal_strict_P{k}' for k in range(1, 5)]
    m = pq.read_table(glob.glob(f'{RAW}/{MAIN[task]}/*.parquet')[0], columns=cols).to_pandas()
    m = m[m.split == 'validation']
    t = {P: pq.read_table(glob.glob(f'{RAW}/{TESTD[task]}/{P}/*.parquet')[0], columns=['window', 'split', f'temporal_strict_{P}']).to_pandas() for P in ['P1', 'P2', 'P3', 'P4']}
    for w in ['W1', 'W2', 'W3']:
        for k in range(1, 5):
            P = f'P{k}'
            mv = m[m.window == w][f'temporal_strict_{P}']
            tt = t[P][t[P].window == w][f'temporal_strict_{P}']
            rows.append(dict(task=task, window=w, phase=P, split='VALIDATION', n=len(mv), n_overlap_cutoff_before_tau=int((mv == 0).sum()), share_overlap=round(float((mv == 0).mean()), 6),
                             n_null=int(mv.isna().sum())))
            rows.append(dict(task=task, window=w, phase=P, split='TEST', n=len(tt), n_overlap_cutoff_before_tau=int((tt == 0).sum()), share_overlap=round(float((tt == 0).mean()), 6),
                             n_null=int(tt.isna().sum())))
d = pd.DataFrame(rows); d.to_csv(f'{OUT}/qa21_b_eval_rows_with_cutoff_before_tau.csv', index=False)
print(d.pivot_table(index=['task', 'window', 'split'], columns='phase', values='share_overlap').to_string())
