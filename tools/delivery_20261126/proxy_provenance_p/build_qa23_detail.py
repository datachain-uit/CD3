# -*- coding: utf-8 -*-
"""P.4 qa23_detail_CQ.csv / qa23_detail_LO.csv / qa23_detail_columns.csv / qa23_lo_dictionary_used.csv.
Reorganises the existing full-row QA23 output (qa4/qa23_fullrows); nothing is recomputed except the LO dictionary, which is rebuilt with
the dict_for() of qa23.py on the schema of the phase view (that function is what the run used).
Env: TEMPO_REPO_ROOT, P_OUT, QA4_DIR, TEMPO_FIX (handoff tempo_fix dir)."""
import os, re, sys, glob, importlib.util
import pandas as pd
import pyarrow.parquet as pq

REPO = os.environ['TEMPO_REPO_ROOT']; OUT = os.environ['P_OUT']; QA4 = os.environ['QA4_DIR']
os.environ.setdefault('QA4_OUT', OUT)
spec = importlib.util.spec_from_file_location('qa23_run', f'{QA4}/qa23.py')
q = importlib.util.module_from_spec(spec); sys.modules['qa23_run'] = q; spec.loader.exec_module(q)

aud = pd.read_csv(f'{QA4}/qa23_fullrows/qa23_audit_by_feature.csv')
summ = pd.read_csv(f'{QA4}/qa23_fullrows/qa23_summary_by_phase.csv')
THR = 0.5


def status(row):
    if row.flagged_by_rule == 1:
        return 'registered_label_proxy (excluded by the dictionary assumed in the audit)'
    if isinstance(row.proxy_review_note, str) and row.proxy_review_note:
        return 'exempt_decision21 (' + row.proxy_review_note + ')'
    return 'unreviewed'


aud['col_status'] = aud.apply(status, axis=1)
hi = aud[aud.spearman_abs >= THR].copy()
hi['item'] = hi.apply(lambda r: f'{r.column_name}[rho={r.spearman_rho:+.3f};n={int(r.n_obs)};{r.col_status.split(" ")[0]}]', axis=1)
hi.sort_values(['task', 'window_id', 'phase_id', 'spearman_abs'], ascending=[True, True, True, False]).drop(columns=['item']).to_csv(f'{OUT}/qa23_detail_columns.csv', index=False)

rows = []
for (task, w, ph), g in aud.groupby(['task', 'window_id', 'phase_id']):
    h = hi[(hi.task == task) & (hi.window_id == w) & (hi.phase_id == ph)].sort_values('spearman_abs', ascending=False)
    s = summ[(summ.task == task) & (summ.window_id == w) & (summ.phase_id == ph)].iloc[0]
    n_unrev = int((h.col_status == 'unreviewed').sum())
    n_ex = int(h.col_status.str.startswith('exempt').sum())
    n_px = int(h.col_status.str.startswith('registered').sum())
    if n_unrev:
        rs = 'unreviewed'
    elif n_ex:
        rs = 'reviewed (exempt under decision 21)'
    else:
        rs = 'no non-proxy column at |rho|>=0.5 (nothing to review)'
    cat = h[h.column_name.str.contains('catalog_coverage')]
    rows.append(dict(
        task=task, window=w, phase=ph, n_features_audited=len(g), n_train_rows=int(s.n_train_rows_used),
        n_features_abs_rho_ge_0_5=len(h), n_registered_proxy_among=n_px, n_exempt_decision21_among=n_ex, n_unreviewed_among=n_unrev,
        columns_abs_rho_ge_0_5=';'.join(h.column_name), max_abs_rho=float(g.spearman_abs.max()),
        column_of_max_abs_rho=g.loc[g.spearman_abs.idxmax(), 'column_name'],
        n_obs_min_over_listed_columns=int(h.n_obs.min()) if len(h) else '', n_obs_max_over_listed_columns=int(h.n_obs.max()) if len(h) else '',
        n_obs_min_over_unreviewed_columns=int(h[h.col_status == 'unreviewed'].n_obs.min()) if n_unrev else '',
        unreviewed_columns=';'.join(h[h.col_status == 'unreviewed'].column_name),
        catalog_coverage_columns_listed=';'.join(f'{r.column_name}(rho={r.spearman_rho:+.3f},n={int(r.n_obs)})' for r in cat.itertuples()),
        review_status=rs, qa23_ok_as_run=bool(s.qa23_ok), n_unreviewed_as_run=int(s.n_unreviewed),
        source_file='qa4/qa23_fullrows/qa23_audit_by_feature.csv + qa23_summary_by_phase.csv', rho_threshold=THR))
d = pd.DataFrame(rows)
# consistency with the summary of the run
chk = d.merge(summ[['task', 'window_id', 'phase_id', 'n_unreviewed', 'n_needs_review', 'max_abs_rho']].rename(columns={'window_id': 'window', 'phase_id': 'phase'}), on=['task', 'window', 'phase'])
assert (chk.n_unreviewed_among == chk.n_unreviewed).all(), chk[chk.n_unreviewed_among != chk.n_unreviewed]
assert (abs(chk.max_abs_rho_x - chk.max_abs_rho_y) < 1e-12).all()
for t in ('CQ', 'LO'):
    d[d.task == t].to_csv(f'{OUT}/qa23_detail_{t}.csv', index=False)
    print(d[d.task == t].drop(columns=['columns_abs_rho_ge_0_5', 'unreviewed_columns', 'catalog_coverage_columns_listed', 'source_file']).to_string())

# ---- LO dictionary used (dict_for of qa23.py on the schema of the LO phase view)
vf = glob.glob(f'{REPO}/downloads/raw_views_20261108/{q.VIEW["LO"]}/*.parquet')[0]
dic = q.dict_for('LO', pq.ParquetFile(vf).schema_arrow)


def src(r):
    base = re.sub(r'_P[1-4]$', '', r.column_name)
    if base in q.LO_CANON:
        return ('assumption of the audit author: LO_CANON = the 19 fields of LO/registries.py LO_PROXY_CONTRACT lo_proxy_contract_v3; suffix rule '
                '= phase_variants_rule of the same contract (base name after stripping _P1.._P4); not read from any stored dictionary')
    if r.role == 'KEY_OR_CONTEXT':
        return 'copy of CQ classify() KEY_OR_CONTEXT set (qa23.py)'
    if r.role == 'MASK':
        return 'copy of CQ classify() mask patterns (qa23.py)'
    if r.role == 'LABEL':
        return 'copy of CQ classify() LABEL_PATTERNS (qa23.py)'
    if r.role == 'FEATURE':
        return 'default for LO: every other numeric column = is_label_proxy 0, regime LO_FULL_EARLY (qa23.py dict_for); no stored LO dictionary with is_label_proxy exists'
    return 'non numeric'


dic['source_of_assumption'] = dic.apply(src, axis=1)
dic.to_csv(f'{OUT}/qa23_lo_dictionary_used.csv', index=False)
print(dic.role.value_counts().to_dict(), int((dic.is_label_proxy == 1).sum()), dic[dic.is_label_proxy == 1].column_name.tolist())
