# -*- coding: utf-8 -*-
"""Thong tin bo sung cho muc C (LO): nhom diem hien hanh (LO_PROXY_CONTRACT['current_grade_group'], 9 cot) co nam trong predictor cua imputer khong.
Doc qa21_c_predictor_list_long.csv. Hop dong ghi nhom nay 'included' trong LO_FULL_EARLY (khong phai is_label_proxy theo hop dong 19 ten);
qa4/qa23.py lai gia dinh no la proxy. Env: QA21_OUT."""
import os, pandas as pd
OUT = os.environ['QA21_OUT']
G = ['score_sum', 'score_mean', 'score_std', 'score_fraction_mean', 'score_fraction_std', 'correct_problem_count', 'incorrect_problem_count', 'correct_ratio', 'correct_ratio_std']
l = pd.read_csv(f'{OUT}/qa21_c_predictor_list_long.csv'); l = l[l.task == 'LO']
r = []
for (w, v), g in l.groupby(['window', 'pipeline']):
    hit = sorted(set(g.predictor) & set(G))
    r.append(dict(task='LO', window=w, pipeline=v, n_current_grade_group_in_predictors=len(hit), names=';'.join(hit), n_grade_group_not_in_predictors=len(set(G) - set(hit)),
                  not_in_predictors=';'.join(sorted(set(G) - set(hit)))))
pd.DataFrame(r).to_csv(f'{OUT}/qa21_c_info_current_grade_group_in_predictors.csv', index=False)
print(pd.DataFrame(r).to_string())
