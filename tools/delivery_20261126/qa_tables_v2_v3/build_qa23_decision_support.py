"""QA23 decision support (not a change of status): for each task x window x phase slice, the unreviewed flagged columns split by
(a) sample size (n_obs < 1000 or >= 1000) and (b) membership of the LO current-grade group (registry: LOCKED 2026-10-01, regimes LO_FULL_EARLY included,
"QA23 is run per phase on this group and reported"). Input: the per-column QA23 detail (work/p/qa23_detail_columns.csv). Output: qa23_decision_support.csv."""
import sys
import pandas as pd

src, out = sys.argv[1], sys.argv[2]
d = pd.read_csv(src)
un = d[d.col_status == 'unreviewed'].copy()
base = un.column_name.str.replace(r'_P[1-4]$', '', regex=True)
grp = {'score_sum', 'score_mean', 'score_std', 'score_fraction_mean', 'score_fraction_std', 'correct_problem_count', 'incorrect_problem_count', 'correct_ratio', 'correct_ratio_std'}
un['small_n_lt_1000'] = un.n_obs < 1000
un['in_lo_current_grade_group'] = (un.task == 'LO') & base.isin(grp)
allsl = d[['task', 'window_id', 'phase_id']].drop_duplicates()
g = un.groupby(['task', 'window_id', 'phase_id']).agg(n_unreviewed=('column_name', 'size'), n_small_n=('small_n_lt_1000', 'sum'), n_in_current_grade_group=('in_lo_current_grade_group', 'sum')).reset_index()
t = allsl.merge(g, how='left').fillna(0)
for c in ('n_unreviewed', 'n_small_n', 'n_in_current_grade_group'):
    t[c] = t[c].astype(int)
t['unreviewed_large_n'] = t.n_unreviewed - t.n_small_n
t['unreviewed_large_n_outside_group'] = t.n_unreviewed - t.n_small_n - (un[~un.small_n_lt_1000].groupby(['task', 'window_id', 'phase_id']).in_lo_current_grade_group.sum().reindex(pd.MultiIndex.from_frame(t[['task', 'window_id', 'phase_id']])).fillna(0).astype(int).values)
t['status_registered_rule'] = (t.n_unreviewed == 0).map({True: 'PASS', False: 'FAIL'})
t['status_if_min_n_1000'] = (t.unreviewed_large_n == 0).map({True: 'PASS', False: 'FAIL'})
t['status_if_min_n_1000_and_group_reported_only'] = (t.unreviewed_large_n_outside_group == 0).map({True: 'PASS', False: 'FAIL'})
t = t.sort_values(['task', 'window_id', 'phase_id'])
t.to_csv(out, index=False, lineterminator='\n')
print(t.groupby('task')[['status_registered_rule', 'status_if_min_n_1000', 'status_if_min_n_1000_and_group_reported_only']].agg(lambda x: (x == 'PASS').sum()))
