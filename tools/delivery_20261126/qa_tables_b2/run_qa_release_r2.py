# -*- coding: utf-8 -*-
"""Reproducible QA run for meta release CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2 (request B.2).

Part 1 (verbatim copy of functions from handoff 2026-11-26 tempo_fix/qa_checks.py: qa03, qa04, qa08, qa09, qa10,
qa18, qa19, qa20, qa24 and helpers) - the block between the two markers below is copied unchanged.
Part 2: driver. Where the repo function cannot be applied as-is to this table (column names differ, group keys
miss model/seed/pipeline, wildcard keys in null_reason_map) the driver runs the repo function unchanged AND a
documented adaptation; both results are written.

Env: TEMPO_REPO_ROOT (repo), B2_OUT (output folder).  Run: python run_qa_release_r2.py
"""
from __future__ import annotations
import os as _os
# Machine roots come from environment variables (no machine paths in the repository).
REPO = _os.environ.get('TEMPO_REPO_ROOT', '.')
WORK = _os.environ.get('TEMPO_WORK_ROOT', '.')
AUDIT44 = _os.environ.get('TEMPO_AUDIT44_ROOT', '.')
WORKD = _os.environ.get('TEMPO_DELIVERY_WORK_ROOT', '.')
import ast, fnmatch, glob, hashlib, json, os, re, subprocess, sys, time
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
import numpy as np
import pandas as pd

# ===== BEGIN verbatim copy of tempo_fix/qa_checks.py (handoff 2026-11-26) =====
TOL_DELTA = 1e-12
GROUP_STATE = ['task', 'feature_regime', 'window_id', 'cohort', 'eval_split', 'subgroup_axis', 'subgroup_value']
PHASE_ORDER = ['P1', 'P2', 'P3', 'P4']


def _metrics_in(df: pd.DataFrame) -> List[str]:
    return sorted({c[:-6] for c in df.columns if c.endswith('_after') and (c[:-6] + '_before') in df.columns})


def qa03_delta_identity(df: pd.DataFrame, tol: float = TOL_DELTA) -> Tuple[bool, pd.DataFrame]:
    """|after − before − delta| ≤ tol for every metric; V0 rows must have delta = 0."""
    rows = []
    for m in _metrics_in(df):
        if f'{m}_delta' not in df:
            continue
        a, b, d = df[f'{m}_after'], df[f'{m}_before'], df[f'{m}_delta']
        bad = ((a - b - d).abs() > tol) & a.notna() & b.notna() & d.notna()
        v0bad = (df.get('pipeline_id') == 'V0') & (d.abs() > tol) if 'pipeline_id' in df else pd.Series(False, index=df.index)
        rows.append({'metric': m, 'n_violations': int(bad.sum()), 'n_v0_delta_nonzero': int(v0bad.sum())})
    det = pd.DataFrame(rows)
    return bool(det[['n_violations', 'n_v0_delta_nonzero']].sum().sum() == 0) if len(det) else True, det


def qa04_decomposition(df: pd.DataFrame, tol: float = TOL_DELTA) -> Tuple[bool, pd.DataFrame]:
    """delta = delta_imp + delta_bal for every metric that has both parts."""
    rows = []
    for m in _metrics_in(df):
        if f'{m}_delta_imp' in df and f'{m}_delta_bal' in df:
            bad = (df[f'{m}_delta'] - df[f'{m}_delta_imp'] - df[f'{m}_delta_bal']).abs() > tol
            rows.append({'metric': m, 'n_violations': int(bad.fillna(False).sum())})
    det = pd.DataFrame(rows)
    return bool(det['n_violations'].sum() == 0) if len(det) else True, det


CELL_IDENTITIES = [
    ('n_cells_total', ['n_cells_unavailable', 'n_cells_eligible']),
    ('n_cells_eligible', ['n_cells_structural_absence', 'n_cells_observed_eligible']),
    ('n_cells_observed_eligible', ['n_cells_observed_value', 'n_cells_observed_missing']),
    ('n_cells_observed_value', ['n_cells_observed_zero', 'n_cells_observed_nonzero']),
]


def qa08_cell_accounting(df: pd.DataFrame, prefixes: Sequence[str] = ('tr_', 'ev_')) -> Tuple[bool, pd.DataFrame]:
    """Cell-state identities of PLAN §6.1 hold exactly for every row and prefix."""
    rows = []
    for pre in prefixes:
        for lhs, parts in CELL_IDENTITIES:
            cols = [pre + lhs] + [pre + p for p in parts]
            if not all(c in df for c in cols):
                continue
            bad = (df[cols[0]] - df[cols[1:]].sum(axis=1)).abs() > 0
            rows.append({'identity': f'{pre}{lhs} = ' + ' + '.join(pre + p for p in parts), 'n_violations': int(bad.sum())})
    det = pd.DataFrame(rows)
    return bool(det['n_violations'].sum() == 0) if len(det) else True, det


def _phase_groups(df: pd.DataFrame, extra: Sequence[str] = ()) -> Iterable[Tuple[tuple, pd.DataFrame]]:
    keys = [k for k in GROUP_STATE if k in df] + list(extra)
    return df.groupby(keys, sort=False, dropna=False) if keys else [((), df)]


def qa09_unavailable_monotone(df: pd.DataFrame, col: str = 'ev_unavailable_rate') -> Tuple[bool, pd.DataFrame]:
    """FIXED cohort: unavailable_rate(P1) ≥ P2 ≥ P3 ≥ P4 within each state slice."""
    rows = []
    for key, g in _phase_groups(df):
        g = g.drop_duplicates('phase_id').set_index('phase_id').reindex(PHASE_ORDER)
        v = g[col].to_numpy(dtype=float)
        v = v[~np.isnan(v)]
        rows.append({'group': key, 'monotone_ok': bool(np.all(np.diff(v) <= 1e-12)) if len(v) > 1 else True})
    det = pd.DataFrame(rows)
    return bool(det['monotone_ok'].all()) if len(det) else True, det


def qa10_fixed_labels(df: pd.DataFrame, count_cols: Sequence[str] = ('ev_class_count_c0', 'ev_class_count_c1', 'ev_class_count_c2')) -> Tuple[bool, pd.DataFrame]:
    """FIXED cohort: class counts identical across P1–P4 within each state slice (ΔIR = 0)."""
    rows = []
    cols = [c for c in count_cols if c in df]
    for key, g in _phase_groups(df):
        ok = all(g[c].nunique(dropna=True) <= 1 for c in cols)
        rows.append({'group': key, 'fixed_ok': ok})
    det = pd.DataFrame(rows)
    return bool(det['fixed_ok'].all()) if len(det) else True, det


def qa15_seen_offering(df: pd.DataFrame, col: str = 'seen_offering') -> Tuple[bool, pd.DataFrame]:
    n = int((df[col] != 0).sum()) if col in df else -1
    return n == 0, pd.DataFrame([{'n_rows_seen_offering_nonzero': n}])


def qa18_null_reasons(df: pd.DataFrame, reason_col: str = 'null_reason_map', ignore: Sequence[str] = ()) -> Tuple[bool, pd.DataFrame]:
    """Every NULL cell has an entry in the row's null_reason_map (JSON string or dict)."""
    rows = []
    for i, r in df.iterrows():
        m = r.get(reason_col)
        m = json.loads(m) if isinstance(m, str) and m else (m or {})
        nulls = [c for c in df.columns if c not in ignore and c != reason_col and pd.isna(r[c])]
        missing = [c for c in nulls if c not in m]
        if missing:
            rows.append({'row': i, 'nulls_without_reason': missing})
    det = pd.DataFrame(rows, columns=['row', 'nulls_without_reason'])
    return len(det) == 0, det


def qa19_roles(df: pd.DataFrame, dictionary: pd.DataFrame) -> Tuple[bool, pd.DataFrame]:
    roles = dict(zip(dictionary['column_name'], dictionary['role']))
    missing = [c for c in df.columns if c not in roles or not roles[c]]
    return len(missing) == 0, pd.DataFrame({'column_without_role': missing})


def qa20_unique_keys(df: pd.DataFrame, key: str = 'meta_obs_id') -> Tuple[bool, pd.DataFrame]:
    dup = df[df.duplicated(key, keep=False)]
    return len(dup) == 0, dup[[key]] if len(dup) else pd.DataFrame(columns=[key])


RUN_LEVEL_COLS = ('s_eff_after', 's_eff_before', 's_leak_probe_n_fit', 'time_train_s', 'energy_gpu_run_kwh_after',
                  'peak_gpu_mem_mb_after', 'trpool_n_synth', 'epochs_trained', 'selected_epoch')


def qa24_run_level_invariants(df: pd.DataFrame, run_col: str = 'run_id_after', cols: Sequence[str] = RUN_LEVEL_COLS) -> Tuple[bool, pd.DataFrame]:
    """Run-level quantities are constant over phases, cohorts, subgroups and eval splits of one run."""
    rows = []
    present = [c for c in cols if c in df]
    for rid, g in df.groupby(run_col):
        for c in present:
            if g[c].nunique(dropna=True) > 1:
                rows.append({run_col: rid, 'column': c, 'n_distinct': int(g[c].nunique(dropna=True))})
    det = pd.DataFrame(rows, columns=[run_col, 'column', 'n_distinct'])
    return len(det) == 0, det


# ===== END verbatim copy =====


# ============================= driver =============================
REPO = os.environ.get('TEMPO_REPO_ROOT', REPO).replace('\\', '/')
OUT = os.environ.get('B2_OUT', os.path.dirname(os.path.abspath(__file__))).replace('\\', '/')
EV = OUT + '/evidence'
REL = REPO + '/CQ/resuilt/meta_release_CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2'
DELIV = REPO + '/CQ/resuilt/delivery_phaseB_r2_20261123'
UNITS = REPO + '/tmp/s0_v5_inputs/subgroup_facts'
os.makedirs(EV, exist_ok=True)
RUN_DATE = time.strftime('%Y-%m-%d')
RES: Dict[str, dict] = {}


def sha(path, chunk=1 << 22):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(chunk), b''):
            h.update(b)
    return h.hexdigest()


def rel_path(p):
    """Strip machine-specific prefixes (deliverables must not carry absolute paths)."""
    p = str(p).replace('\\', '/')
    for pre, rep in ((REPO + '/', ''), (f'{REPO}/', ''), (f'{WORK}/', 'WORK:tmp_aud/'), (f'{AUDIT44}/', 'WORK:audit44/'),
                     (os.environ.get('TEMPO_ARCHIVE_C_ROOT', '<unset>') + '/', 'WORK:archive_c/')):
        if p.startswith(pre):
            return rep + p[len(pre):]
    return p


def put(qid, rows_df, name):
    rows_df.to_csv(f'{EV}/{qid}_{name}.csv', index=False)
    return f'evidence/{qid}_{name}.csv'


def rec(qid, status, unit, n_checked, n_pass, n_fail, evidence, note, kind):
    RES[qid] = dict(status=status, unit=unit, n_units_checked=int(n_checked), n_pass=int(n_pass), n_fail=int(n_fail),
                    evidence_file=evidence, note=note, kind=kind)
    print(qid, status, n_checked, n_pass, n_fail, kind, flush=True)


def git_head():
    try:
        return subprocess.check_output(['git', '-C', REPO, 'rev-parse', '--short', 'HEAD'], text=True).strip()
    except Exception:
        return 'UNKNOWN'


def main():
    import itertools
    df = pd.read_parquet(REL + '/meta_dataset_seed_level.parquet')
    agg = pd.read_parquet(REL + '/meta_dataset_seed_agg.parquet')
    dic = pd.read_csv(REL + '/meta_column_dictionary.csv')
    man = json.load(open(REL + '/meta_release_manifest.json', encoding='utf-8'))
    N = len(df)
    df['_sg'] = df.subgroup_axis + '|' + df.subgroup_value
    unit_sum = {}
    for d in sorted(glob.glob(UNITS + '/*_subgroups_20261121')):
        unit_sum[os.path.basename(d).replace('_subgroups_20261121', '')] = (d, json.load(open(d + '/summary.json', encoding='utf-8')))
    print('rows', N, 'units', len(unit_sum), flush=True)

    # ---------------- QA01 full grid ----------------
    # planned grid = (task, model, seed) of the 36 phase-B unit packages (independent of the release table)
    # x W1-W3 x V0-V16 (51 runs per unit) x P1-P4 x {VALIDATION, TEST} x 5 subgroups.
    tms = sorted({(s['task'], s['model'], s['seed']) for _, s in unit_sum.values()})
    runs_planned = sum(s['runs'] for _, s in unit_sum.values())
    plan = pd.DataFrame(list(itertools.product(tms, ['W1', 'W2', 'W3'], [f'V{i}' for i in range(17)], ['P1', 'P2', 'P3', 'P4'],
                                               ['VALIDATION', 'TEST'], ['ALL|ALL', 'LEARNER|SEEN', 'LEARNER|UNSEEN', 'COURSE|SEEN', 'COURSE|UNSEEN'])),
                        columns=['tms', 'window_id', 'pipeline_id', 'phase_id', 'eval_split', '_sg'])
    plan['task'] = plan.tms.str[0]; plan['model_name'] = plan.tms.str[1]; plan['seed'] = plan.tms.str[2].astype(int); plan = plan.drop(columns='tms')
    K = ['task', 'model_name', 'seed', 'window_id', 'pipeline_id', 'phase_id', 'eval_split', '_sg']
    pk = plan[K].assign(planned=1)
    cnt = df[K].astype({'seed': int}).groupby(K).size().rename('n_in_release').reset_index()
    m = pk.merge(cnt, on=K, how='outer')
    m['n_in_release'] = m.n_in_release.fillna(0).astype(int); m['planned'] = m.planned.fillna(0).astype(int)
    bad = m[(m.planned != 1) | (m.n_in_release != 1)]
    sub_cnt = df._sg.value_counts().to_dict()
    chk = pd.DataFrame([
        {'item': 'planned_cells_from_unit_packages', 'value': len(plan)}, {'item': 'runs_planned_sum_unit_summaries', 'value': runs_planned},
        {'item': 'runs_x_4_phases_x_2_splits_x_5_subgroups', 'value': runs_planned * 40}, {'item': 'rows_seed_level', 'value': N},
        {'item': 'manifest_n_rows_seed_level', 'value': man['n_rows_seed_level']}, {'item': 'rows_seed_agg', 'value': len(agg)},
        {'item': 'manifest_n_rows_seed_agg', 'value': man['n_rows_seed_agg']}, {'item': 'distinct_run_id_after', 'value': df.run_id_after.nunique()},
        {'item': 'cells_missing_in_release', 'value': int(((m.planned == 1) & (m.n_in_release == 0)).sum())},
        {'item': 'cells_not_planned', 'value': int(((m.planned == 0) & (m.n_in_release > 0)).sum())},
        {'item': 'cells_duplicated', 'value': int((m.n_in_release > 1).sum())},
        {'item': 'subgroup_counts_match_manifest', 'value': int(all(sub_cnt.get(k) == v for k, v in man['subgroups'].items()))},
        {'item': 'row_status_not_COMPLETE', 'value': int((df.row_status != 'COMPLETE').sum())}])
    f = put('QA01', pd.concat([chk, bad.assign(item='BAD_CELL').head(200)], ignore_index=True, sort=False), 'detail')
    ok1 = len(bad) == 0 and N == len(plan) == man['n_rows_seed_level'] and len(agg) == man['n_rows_seed_agg']
    rec('QA01', 'PASS' if ok1 else 'FAIL', 'cells (row keys)', len(plan), len(plan) - len(bad), len(bad), f,
        f'Lưới kế hoạch = (task, model, seed) của 36 gói unit pha B ({runs_planned} run) x W1-W3 x V0-V16 x P1-P4 x {{VALIDATION,TEST}} x 5 subgroup = {len(plan)} ô; '
        f'so khớp từng khóa với bảng seed-level ({N} dòng, mỗi khóa đúng 1 lần), manifest và bảng seed_agg ({len(agg)} dòng). Số run lấy từ summary.json các unit, độc lập với bảng release.', 'recomputed')

    # ---------------- QA02 pairing ----------------
    KB = ['task', 'model_name', 'seed', 'window_id', 'phase_id', 'eval_split', '_sg']
    base = df[df.pipeline_id == 'V0'].set_index(KB)
    METR = sorted({c[:-6] for c in df.columns if c.endswith('_after') and c[:-6] + '_before' in df.columns} - {'run_id'})
    j = df.join(base[['run_id_after', 'n_eval_samples'] + [m_ + '_after' for m_ in METR]].add_prefix('b0_'), on=KB)
    tests, bad_row = [], pd.Series(False, index=df.index)

    def addt(name, mask):
        nonlocal bad_row
        mask = pd.Series(mask, index=df.index).fillna(True).astype(bool)
        tests.append({'test': name, 'n_violations': int(mask.sum())}); bad_row |= mask
    addt('before_row_exists_V0_same_key', j.b0_run_id_after.isna())
    addt('pipeline_before_ref_is_V0', df.pipeline_before_ref != 'V0')
    addt('run_id_before_notnull', df.run_id_before.isna())
    addt('run_id_before_equals_V0_run_id_after', j.run_id_before != j.b0_run_id_after)
    addt('n_eval_samples_equal_to_before_row', j.n_eval_samples != j.b0_n_eval_samples)
    for mm in METR:
        a, bb = j[f'{mm}_before'], j[f'b0_{mm}_after']
        addt(f'{mm}_before == V0 {mm}_after (1e-12; NULL pattern equal)', (((a - bb).abs() > 1e-12) & a.notna() & bb.notna()) | (a.isna() != bb.isna()))
    HP = [c for c in ['lr', 'batch_size', 'max_epochs', 'loss_name', 'class_weighting', 'model_family', 'model_revision', 'max_seq_len', 'patch_len', 'patch_stride',
                      'frozen_backbone', 'return_transf_layer', 'output_token', 'interp_len', 'micro_batch_size', 'accumulation_steps', 'label_rule_version',
                      'label_threshold_set', 'seen_rule_version', 'seen_history_reference', 'acctempo_def_version', 'n_classes', 'feature_regime'] if c in df.columns]
    jb = df.join(base[HP].add_prefix('b0_'), on=KB)
    for c in HP:
        a, bb = jb[c], jb['b0_' + c]
        addt(f'hparam/split-version column {c} equal to before row', (a != bb) & ~(a.isna() & bb.isna()))
    ik = df[KB + ['pipeline_id', 'run_id_after']].rename(columns={'pipeline_id': 'pipeline_imputer_only_ref', 'run_id_after': 'io_run'})
    iok = df[KB + ['pipeline_imputer_only_ref', 'run_id_imp_only']].merge(ik, on=KB + ['pipeline_imputer_only_ref'], how='left')
    addt('run_id_imp_only equals run_id_after of pipeline_imputer_only_ref row', (iok.run_id_imp_only != iok.io_run).to_numpy())
    det = pd.DataFrame(tests)
    f = put('QA02', det, 'detail')
    nbr = int(bad_row.sum())
    rec('QA02', 'PASS' if nbr == 0 else 'FAIL', 'rows', N, N - nbr, nbr, f,
        f'Mỗi dòng ghép với dòng V0 cùng khóa (task, model, seed, window, phase, split, subgroup): run_id_before = run_id_after của V0, {len(METR)} nhóm cột *_before = *_after của V0 (<=1e-12), '
        f'{len(HP)} cột hparam/phiên bản split/nhãn/seen bằng dòng before, run_id_imp_only khớp dòng imputer-only. n_fail = số dòng vi phạm ít nhất một phép thử.', 'recomputed')

    # ---------------- QA03 / QA04 ----------------
    ok, d3 = qa03_delta_identity(df)
    f = put('QA03', d3, 'detail')
    nv = int(d3[['n_violations', 'n_v0_delta_nonzero']].sum().sum())
    rec('QA03', 'PASS' if ok else 'FAIL', 'rows x metrics (after/before/delta)', int(len(d3)) * N, int(len(d3)) * N - nv, nv, f,
        f'Hàm qa03_delta_identity của repo, tol 1e-12, {len(d3)} metric (gồm val_*), kèm V0 delta = 0. n_fail = số vi phạm (ô metric x dòng). Ô NULL không đánh giá.', 'recomputed')
    ok, d4 = qa04_decomposition(df)
    f = put('QA04', d4, 'detail')
    nv = int(d4.n_violations.sum())
    rec('QA04', 'PASS' if ok else 'FAIL', 'rows x metrics (delta = delta_imp + delta_bal)', int(len(d4)) * N, int(len(d4)) * N - nv, nv, f,
        f'Hàm qa04_decomposition của repo, tol 1e-12, {len(d4)} metric có đủ delta_imp và delta_bal. n_fail = số vi phạm.', 'recomputed')

    # ---------------- QA06 / QA07 (table-level) ----------------
    n_numpy_repr = [0]

    def parse_cm(s):
        try:
            return np.array(ast.literal_eval(str(s)), dtype=float)
        except Exception:
            v = re.findall(r'-?\d+', str(s))      # numpy-repr string "[array([..]) array([..]) ...]" stored by some facts packages
            n_numpy_repr[0] += 1
            return np.array(v, dtype=float).reshape(3, 3) if len(v) == 9 else np.full((3, 3), np.nan)
    has_cm = df.confusion_matrix.notna()
    cm = {i: parse_cm(s) for i, s in df.confusion_matrix[has_cm].items()}
    sums = pd.Series({i: (a.sum() if a is not None else np.nan) for i, a in cm.items()}).reindex(df.index)
    rs = pd.DataFrame({i: a.sum(axis=1) for i, a in cm.items()}).T.reindex(df.index)
    cs = pd.DataFrame({i: a.sum(axis=0) for i, a in cm.items()}).T.reindex(df.index)
    sup = df[['c0_support', 'c1_support', 'c2_support']]; pc = df[['c0_predicted_count', 'c1_predicted_count', 'c2_predicted_count']]
    has_sup = sup.notna().all(axis=1); has_pc = pc.notna().all(axis=1)
    pcs_sum = df.per_class_support.map(lambda x: float(np.nansum(x)) if isinstance(x, (list, np.ndarray)) else np.nan)
    has_pcs = pcs_sum.notna()
    t_cm = has_cm & (sums != df.n_eval_samples)
    t_sup = has_sup & (sup.sum(axis=1) != df.n_eval_samples)
    t_pcs = has_pcs & (pcs_sum != df.n_eval_samples)
    t_row = has_cm & has_sup & ~(rs.to_numpy() == sup.to_numpy()).all(axis=1)
    t_col = has_cm & has_pc & ~(cs.to_numpy() == pc.to_numpy()).all(axis=1)
    covered = has_cm | has_sup | has_pcs
    fail_rows = t_cm | t_sup | t_pcs | t_row | t_col
    KR = ['task', 'model_name', 'seed', 'window_id', 'pipeline_id', 'phase_id', 'eval_split']
    cmdf = df.loc[has_cm, KR + ['subgroup_axis', 'subgroup_value']].copy(); cmdf['cm'] = [cm[i] for i in cmdf.index]
    allm = {tuple(r[KR]): r['cm'] for _, r in cmdf[cmdf.subgroup_axis == 'ALL'].iterrows()}
    npart = nbadpart = n_nocm = 0
    part_bad = []
    for (ax, *k), g in cmdf[cmdf.subgroup_axis != 'ALL'].groupby(['subgroup_axis'] + KR):
        k = tuple(k)
        if k not in allm:
            n_nocm += 1                      # ALL row has no confusion matrix: matrix partition not checkable here
            continue
        npart += 1
        if len(g) != 2 or not np.array_equal(g.cm.iloc[0] + g.cm.iloc[1], allm[k]):
            nbadpart += 1; part_bad.append({'axis': ax, 'key': str(k), 'n_subgroup_rows': len(g)})
    # partition of n_eval_samples (and of c*_support where present): SEEN + UNSEEN = ALL for every run/phase/split/axis
    piv = df.pivot_table(index=KR, columns=['subgroup_axis', 'subgroup_value'], values='n_eval_samples', aggfunc='first')
    npart_n = nbad_n = 0
    for ax in ('LEARNER', 'COURSE'):
        ok_ = piv[(ax, 'SEEN')] + piv[(ax, 'UNSEEN')] == piv[('ALL', 'ALL')]
        npart_n += len(ok_); nbad_n += int((~ok_).sum())
        if nbad_n:
            part_bad += [{'axis': ax, 'key': str(k_), 'n_subgroup_rows': -1} for k_ in ok_[~ok_].index[:50]]
    d6 = pd.DataFrame([
        {'item': 'rows_total', 'value': N}, {'item': 'confusion_matrix_cells_in_numpy_repr_format_not_python_list', 'value': n_numpy_repr[0]}, {'item': 'rows_with_confusion_matrix', 'value': int(has_cm.sum())},
        {'item': 'rows_with_c012_support', 'value': int(has_sup.sum())}, {'item': 'rows_with_per_class_support', 'value': int(has_pcs.sum())},
        {'item': 'rows_covered_by_at_least_one_test', 'value': int(covered.sum())}, {'item': 'rows_failing_any_test', 'value': int(fail_rows.sum())},
        {'item': 'cm_sum_neq_n_eval_samples', 'value': int(t_cm.sum())}, {'item': 'c012_support_sum_neq_n_eval_samples', 'value': int(t_sup.sum())},
        {'item': 'per_class_support_sum_neq_n_eval_samples', 'value': int(t_pcs.sum())},
        {'item': 'cm_rowsum_neq_support', 'value': int(t_row.sum())}, {'item': 'cm_colsum_neq_predicted_count', 'value': int(t_col.sum())},
        {'item': 'partition_cells_confusion_matrix_checked_SEEN+UNSEEN=ALL', 'value': npart}, {'item': 'partition_cells_confusion_matrix_failed', 'value': nbadpart},
        {'item': 'partition_cells_confusion_matrix_not_checkable_ALL_row_without_matrix', 'value': n_nocm},
        {'item': 'partition_cells_n_eval_samples_checked_SEEN+UNSEEN=ALL', 'value': npart_n}, {'item': 'partition_cells_n_eval_samples_failed', 'value': nbad_n}])
    uncov = df.loc[~covered, ['task', 'model_name', 'seed', 'subgroup_axis', 'subgroup_value']].value_counts().rename('rows').reset_index().assign(item='UNCOVERED_ROWS')
    f = put('QA06', pd.concat([d6, uncov, pd.DataFrame(part_bad).assign(item='PARTITION_FAIL')], ignore_index=True, sort=False), 'detail')
    ncov = int(covered.sum()); nbad6 = int(fail_rows.sum()) + nbadpart + nbad_n
    st6 = 'FAIL' if nbad6 else 'PASS'
    rec('QA06', st6, 'rows (+ SEEN/UNSEEN partition cells)', ncov, ncov - int(fail_rows.sum()), nbad6, f,
        f'Tính lại từ bảng release: Σ confusion_matrix = n_eval_samples; Σ c*_support và Σ per_class_support = n_eval_samples; tổng hàng ma trận = support; tổng cột = predicted_count; SEEN+UNSEEN = ALL trên ma trận ({npart} ô run/phase/split/trục) và trên n_eval_samples ({npart_n} ô). '
        f'PHẠM VI MỘT PHẦN NHỎ KHÔNG KIỂM ĐƯỢC: {ncov}/{N} dòng có ít nhất một đại lượng để kiểm, {N - ncov} dòng (dòng ALL của 4 unit CQ recurrent seed 42, bảng dữ kiện cũ không có ma trận/support) chỉ kiểm được n_eval_samples qua phép chia SEEN/UNSEEN; {n_nocm} ô phân hoạch ma trận không kiểm được vì dòng ALL thiếu ma trận. Không đọc dự đoán cấp mẫu. Lưu ý định dạng: {n_numpy_repr[0]} ô confusion_matrix (dòng ALL của các unit seed 43/44 và Mantis/PatchTST seed 42) lưu dạng chuỗi repr numpy chứ không phải list Python, đã phân tích bằng regex. Ngoài ra summary.json 36 unit ghi partition_failures = 0 (xem QA15/QA05).', 'recomputed')
    pe = df.probability_sum_max_abs_error; nn = df.prediction_nan_inf_count
    d7 = pd.DataFrame([{'item': 'rows_with_probability_sum_max_abs_error', 'value': int(pe.notna().sum())}, {'item': 'max_probability_sum_max_abs_error', 'value': float(pe.max())},
                       {'item': 'rows_over_1e-4', 'value': int((pe > 1e-4).sum())}, {'item': 'rows_with_prediction_nan_inf_count', 'value': int(nn.notna().sum())},
                       {'item': 'rows_nan_inf_count_nonzero', 'value': int((nn > 0).sum())}, {'item': 'rows_without_values', 'value': int(pe.isna().sum())},
                       {'item': 'argmax_check', 'value': 'NOT_RUN (needs sample-level predictions)'}])
    f7 = put('QA07', d7, 'partial_detail')
    rec('QA07', 'NOT_RUN', 'rows (chỉ phần Σprob)', int(pe.notna().sum()), int((pe.notna() & (pe <= 1e-4)).sum()), int((pe > 1e-4).sum()), f7,
        f'Chỉ kiểm được nửa đầu trên cột đã lưu của bảng: max |Σprob-1| = {float(pe.max()):.3g} (<=1e-4) trên {int(pe.notna().sum())}/{N} dòng, {int(pe.isna().sum())} dòng không có giá trị; '
        'nửa sau y_pred_index = argmax cần dự đoán cấp mẫu nên chưa chạy, vì vậy không ghi PASS. Có thể chạy lại rẻ trên dự đoán từng unit nếu reviewer cần.', 'NOT_RUN (partial)')

    # ---------------- QA08 ----------------
    ok, d8 = qa08_cell_accounting(df)
    ok2, d8b = qa08_cell_accounting(df, prefixes=('trpool_', 'evpool_'))
    ex = []
    for pre in ('tr_', 'ev_'):
        cols = [pre + c for c in ('n_cells_total', 'n_cells_unavailable', 'n_cells_structural_absence', 'n_cells_observed_eligible')]
        a = df[cols]; nn_ = a.notna().all(axis=1)
        ex.append({'identity': f'{cols[0]} = unavailable + structural_absence + observed_eligible (composed; n_cells_eligible absent)',
                   'n_violations': int(((a[cols[0]] - a[cols[1:]].sum(axis=1)).abs() > 0)[nn_].sum()), 'rows_evaluated': int(nn_.sum())})
        a = df[[pre + 'n_cells_observed_value', pre + 'n_cells_observed_zero']]
        ex.append({'identity': f'{pre}observed_value >= observed_zero (observed_nonzero column absent)',
                   'n_violations': int((a.iloc[:, 0] < a.iloc[:, 1]).sum()), 'rows_evaluated': int(a.notna().all(axis=1).sum())})
    d8all = pd.concat([d8.assign(source='repo qa08 prefixes tr_/ev_'), d8b.assign(source='repo qa08 prefixes trpool_/evpool_'),
                       pd.DataFrame(ex).assign(source='driver supplementary')], ignore_index=True, sort=False)
    f = put('QA08', d8all, 'detail')
    nv = int(d8all.n_violations.sum()); nid = len(d8all)
    rec('QA08', 'PASS' if nv == 0 else 'FAIL', 'rows x identities', N * nid, N * nid - nv, nv, f,
        f'Hàm qa08 của repo chỉ áp dụng được {len(d8)} đẳng thức (tr_/ev_) và {len(d8b)} (trpool_/evpool_) vì bảng không có cột n_cells_eligible và n_cells_observed_nonzero; bổ sung {len(ex)} đẳng thức/bất đẳng thức (total = unavailable + structural + observed_eligible; observed_value >= observed_zero). '
        'Các đẳng thức cần n_cells_eligible/observed_nonzero không kiểm trực tiếp được. Ô NULL không đánh giá (số dòng đánh giá trong file chi tiết).', 'recomputed')

    # ---------------- QA09 / QA10 ----------------
    dfx = df.copy()
    dfx['ev_unavailable_rate'] = dfx.ev_n_cells_unavailable / dfx.ev_n_cells_total
    EXTRA = ['model_name', 'seed', 'pipeline_id']
    GK = [k for k in GROUP_STATE if k in dfx] + EXTRA
    okr, _ = qa09_unavailable_monotone(dfx)
    r9 = []
    for key, g in dfx.groupby(GK, sort=False, dropna=False):
        g = g.drop_duplicates('phase_id').set_index('phase_id').reindex(PHASE_ORDER)
        v = g['ev_unavailable_rate'].to_numpy(dtype=float); v = v[~np.isnan(v)]
        r9.append({'group': str(key), 'n_phases_with_value': len(v), 'monotone_ok': bool(np.all(np.diff(v) <= 1e-12)) if len(v) > 1 else True})
    d9 = pd.DataFrame(r9); ok9 = bool(d9.monotone_ok.all())
    f = put('QA09', d9, 'detail')
    rec('QA09', 'PASS' if ok9 else 'FAIL', 'nhóm (task, regime, window, split, subgroup, model, seed, pipeline) x 4 phase', len(d9), int(d9.monotone_ok.sum()), int((~d9.monotone_ok).sum()), f,
        'ev_unavailable_rate không có trong bảng nên tính = ev_n_cells_unavailable / ev_n_cells_total. Hàm qa09 của repo gom nhóm không có model/seed/pipeline nên chạy bản thích ứng (thêm 3 khóa nhóm, cùng điều kiện P1>=P2>=P3>=P4, tol 1e-12). '
        f'Hàm repo nguyên bản (nhóm gộp) trả {okr}: chỉ tham khảo.', 'recomputed')
    vec = [tuple(r) if not np.isnan(r).any() else (tuple(p) if isinstance(p, (list, np.ndarray)) and len(p) == 3 else None)
           for r, p in zip(sup.to_numpy(dtype=float), df.per_class_support)]
    dfx['_sup'] = vec
    r10 = []
    for key, g in dfx.groupby(GK, sort=False, dropna=False):
        s = [x for x in g._sup if x is not None]
        r10.append({'group': str(key), 'n_phases_with_support': len(s), 'distinct_support_vectors': len(set(s)), 'fixed_ok': len(set(s)) <= 1})
    d10 = pd.DataFrame(r10)
    d10['is_ALL_slice'] = d10.group.str.contains("'ALL', 'ALL'")
    okr10, _ = qa10_fixed_labels(dfx)
    f = put('QA10', d10, 'detail')
    a10 = d10[d10.is_ALL_slice]; s10 = d10[~d10.is_ALL_slice]
    chk10 = a10[a10.n_phases_with_support == 4]
    nunc = int((a10.n_phases_with_support < 4).sum()); nbad10 = int((~chk10.fixed_ok).sum())
    rec('QA10', 'FAIL' if nbad10 else 'PASS', 'nhóm ALL/ALL (task, window, split, model, seed, pipeline) x 4 phase', len(chk10), int(chk10.fixed_ok.sum()), nbad10, f,
        f'Hàm qa10 của repo tìm cột ev_class_count_c0..2 (không có trong bảng nên chạy rỗng, trả {okr10}, vô nghĩa); dùng c0/c1/c2_support của tập eval so sánh qua P1-P4 trong từng nhóm có model/seed/pipeline, áp cho lát ALL/ALL (cohort FIXED). '
        f'PHẠM VI MỘT PHẦN: {nunc} nhóm ALL/ALL (4 unit CQ recurrent seed 42) không có support trong bảng nên không kiểm được. '
        f'Ngoài ra {int((~s10.fixed_ok).sum())}/{len(s10)} nhóm subgroup SEEN/UNSEEN có support đổi theo phase: đúng thiết kế vì cờ seen tính theo cutoff từng phase (seen_flags.py), không tính là vi phạm QA10, nhưng cột population_varies_by_phase = 0 trên mọi dòng subgroup nên cờ này không phản ánh điều đó (lưu ý cho reviewer).', 'recomputed')

    # ---------------- QA05 / QA15 from existing unit evidence ----------------
    man_in = man['inputs_sha256']
    comp_sha = {rel_path(v['path']): v['sha256'] for v in man_in.values() if 'subgroup_components' in v['path']}
    REPORT_ONLY_BUILDER = {'log_loss', 'pr_auc_macro', 'top_label_ece_15', 'multiclass_nll', 'cross_entropy', 'multiclass_brier'}   # as declared in tools/subgroups_phaseB/build_subgroup_facts.py
    ur = []
    for u, (d, s) in unit_sum.items():
        key = rel_path(d + '/subgroup_components.parquet')
        cp = sha(d + '/subgroup_components.parquet')
        diffs = {c: v for c, v in s['all_row_max_abs_diff_by_column'].items() if v is not None}
        over = {c: v for c, v in diffs.items() if v > 1e-6}
        ur.append({'unit': u, 'summary_json': rel_path(d + '/summary.json'), 'summary_sha256': sha(d + '/summary.json'), 'components_parquet_sha256': cp,
                   'components_sha_in_release_manifest': comp_sha.get(key) == cp, 'runs': s['runs'], 'qa15_violations': s['qa15_violations'], 'hash_unmatched': s['hash_unmatched'],
                   'no_salt_match_n': len(s['no_salt_match']), 'partition_failures_n': len(s['partition_failures']), 'all_row_mismatch_gt_1e-12_n': len(s['all_row_mismatch']),
                   'files_missing_n': len(s['files_missing']), 'unit_status': s.get('status'), 'n_columns_compared': len(diffs), 'max_diff_all_columns': max(diffs.values()),
                   'columns_over_1e-6': ';'.join(f'{c}={v:.3g}' for c, v in over.items()), 'over_1e-6_only_report_only_columns': all(c in REPORT_ONLY_BUILDER for c in over)})
    du = pd.DataFrame(ur)
    f = put('QA05_QA15', du, 'unit_summary_aggregation')
    n_u = len(du)
    q15_ok = int(((du.qa15_violations == 0) & (du.hash_unmatched == 0) & (du.no_salt_match_n == 0) & (du.files_missing_n == 0)).sum())
    linked = int(du.components_sha_in_release_manifest.sum())
    rec('QA15', 'PASS' if q15_ok == n_u and linked == n_u else 'FAIL', 'unit pha B (task x model x seed; 1836 run)', n_u, q15_ok, n_u - q15_ok, f,
        'Bằng chứng có sẵn, không chạy lại hôm nay: summary.json của 36 gói unit pha B (tmp/s0_v5_inputs/subgroup_facts/*/summary.json; sha256 từng file trong file chi tiết) ghi qa15_violations = 0 (seen_offering != 0 trên EVAL, tính từ dự đoán + cờ seen), '
        f'hash_unmatched = 0, không thiếu salt/file. {linked}/{n_u} subgroup_components.parquet của các unit khớp sha256 ghi trong meta_release_manifest.json của release này. '
        'Bảng release không có cột seen_offering nên hàm qa15 của repo không áp dụng trực tiếp lên bảng. Chứng cứ cấp unit.', 'existing evidence cited')
    n5ok = int((du.max_diff_all_columns <= 1e-6).sum())
    rec('QA05', 'PASS' if n5ok == n_u else 'FAIL', 'unit pha B (dòng ALL tính lại từ dự đoán so với bảng dữ kiện)', n_u, n5ok, n_u - n5ok, f,
        f'Bằng chứng có sẵn: summary.json từng unit ghi sai khác lớn nhất giữa dòng ALL tính lại từ dự đoán cấp mẫu và bảng dữ kiện theo từng cột (builder dùng ngưỡng 1e-12, riêng log_loss/pr_auc_macro chỉ báo cáo). '
        f'Với ngưỡng 1e-6 của QA05: {n5ok}/{n_u} unit đạt; {n_u - n5ok} unit vượt ngưỡng: ' +
        '; '.join(f'{r.unit} ({r._1})' for r in du[du.max_diff_all_columns > 1e-6][['unit', 'columns_over_1e-6']].itertuples(index=False)) +
        '. Mọi cột vượt 1e-6 đều thuộc nhóm REPORT_ONLY mà builder khai báo (log_loss, pr_auc_macro, top_label_ece_15, multiclass_nll, cross_entropy, multiclass_brier: bảng dữ kiện cũ dùng clip xác suất 1e-7 và average-precision bản cũ); builder coi là báo cáo chứ không phải lỗi, nhưng QA05 ghi ngưỡng 1e-6 nên vẫn đếm là không đạt; mọi cột khác <= 1e-12. Phạm vi: chỉ dòng ALL của các unit; dòng subgroup dùng cùng hàm từ cùng dự đoán, không có bảng dữ kiện độc lập. '
        'Cờ qa_metric_recompute_ok = true trên 73,440 dòng là cờ của bên ghi, không dùng làm bằng chứng.', 'existing evidence cited')

    # ---------------- QA18 ----------------
    body = df.drop(columns=['_sg', 'null_reason_map'])
    nullm = body.isna(); cols = list(nullm.columns); arr = nullm.to_numpy()
    nrm = df.null_reason_map.fillna('{}').to_numpy()
    miss_e = np.zeros(len(cols), dtype=np.int64); miss_w = np.zeros(len(cols), dtype=np.int64)
    rows_bad_e = np.zeros(N, dtype=bool); rows_bad_w = np.zeros(N, dtype=bool)
    for s_ in pd.unique(nrm):
        mp = json.loads(s_) if s_ else {}
        ce = np.array([c in mp for c in cols]); cw = np.array([(c in mp) or any(fnmatch.fnmatchcase(c, k) for k in mp if '*' in k) for c in cols])
        ii = np.where(nrm == s_)[0]; sub = arr[ii]
        be = sub & ~ce; bw = sub & ~cw
        miss_e += be.sum(axis=0); miss_w += bw.sum(axis=0); rows_bad_e[ii] = be.any(axis=1); rows_bad_w[ii] = bw.any(axis=1)
    d18 = pd.DataFrame({'column': cols, 'n_null': arr.sum(axis=0), 'n_null_without_reason_exact_key': miss_e, 'n_null_without_reason_wildcard_aware': miss_w})
    d18['is_reason_column'] = d18.column.str.endswith('_reason')
    d18 = d18[d18.n_null > 0].sort_values(['is_reason_column', 'n_null_without_reason_wildcard_aware'], ascending=[True, False])
    samp = df.drop(columns=['_sg']).sample(200, random_state=0)
    try:
        okp, dp = qa18_null_reasons(samp); par = f'hàm repo gốc trên 200 dòng mẫu: passed={okp}, dòng bị gắn cờ={len(dp)}'
    except Exception as e:
        par = f'hàm repo gốc báo lỗi {type(e).__name__} trên dòng mẫu (ô dạng list)'
    f = put('QA18', d18, 'detail')
    dd = d18[~d18.is_reason_column]
    nnull = int(dd.n_null.sum()); nbad_cells = int(dd.n_null_without_reason_wildcard_aware.sum())
    ncols_bad = int((dd.n_null_without_reason_wildcard_aware > 0).sum())
    rec('QA18', 'PASS' if nbad_cells == 0 else 'FAIL', 'ô NULL (loại các cột *_reason)', nnull, nnull - nbad_cells, nbad_cells, f,
        'Mọi ô NULL phải có khóa trong null_reason_map của dòng. Bản vector hóa tương đương qa18 của repo (hàm gốc dùng iterrows, chậm và lỗi với ô list), hỗ trợ khóa wildcard (vd val_*, *_prev) bằng fnmatch; loại 100% NULL của các cột *_reason (chính chúng là cột mã lý do). '
        f'Kết quả: {nbad_cells} ô NULL không có lý do trong null_reason_map, thuộc {ncols_bad} cột (vd run_id_ref, top_label_ece_15, multiclass_nll, probe_*, strict_share, variant_role); hầu hết các cột này có NULL nhưng lý do chỉ nằm ở cột *_reason hoặc không có. '
        f'Chỉ khớp khóa chính xác như hàm gốc (không wildcard): {int(dd.n_null_without_reason_exact_key.sum())} ô. Nếu tính cả cột *_reason: {int(d18.n_null_without_reason_wildcard_aware.sum())} ô. {par}.', 'recomputed')

    # ---------------- QA19 ----------------
    ok19, d19 = qa19_roles(df.drop(columns=['_sg']), dic)
    un = dic[dic.role == 'UNASSIGNED']
    d19b = pd.concat([d19.assign(kind='repo qa19: column missing or empty role'), un[['column_name', 'block', 'role']].assign(kind='role == UNASSIGNED')], ignore_index=True, sort=False)
    f = put('QA19', d19b, 'detail')
    nc = len(dic)
    rec('QA19', 'FAIL' if len(un) else ('PASS' if ok19 else 'FAIL'), 'cột', nc, nc - len(un), len(un), f,
        f'Hàm qa19 của repo (role khác rỗng) trả {ok19}: {nc}/{nc} cột có giá trị role và từ điển trùng đúng tập cột bảng. Nhưng {len(un)} cột có role = UNASSIGNED (chưa gán vai trò thực); điều kiện "100% cột có role" đọc nghiêm là chưa đạt nên ghi FAIL; reviewer quyết định có coi UNASSIGNED là role hợp lệ không. Danh sách cột trong file chi tiết.', 'recomputed')

    # ---------------- QA20 ----------------
    ok20, d20 = qa20_unique_keys(df)
    kagg = [c for c in agg.columns if c.startswith('meta_obs_id')][0]
    dagg = int(agg.duplicated(kagg).sum())
    d20b = pd.DataFrame([{'table': 'seed_level', 'key': 'meta_obs_id', 'rows': N, 'distinct': int(df.meta_obs_id.nunique()), 'dup_rows': len(d20), 'null_keys': int(df.meta_obs_id.isna().sum())},
                         {'table': 'seed_agg', 'key': kagg, 'rows': len(agg), 'distinct': int(agg[kagg].nunique()), 'dup_rows': dagg, 'null_keys': int(agg[kagg].isna().sum())}])
    f = put('QA20', d20b, 'detail')
    nd = len(d20) + dagg
    rec('QA20', 'PASS' if ok20 and dagg == 0 else 'FAIL', 'dòng (khóa meta_obs_id)', N + len(agg), N + len(agg) - nd, nd, f,
        f'Hàm qa20 của repo trên bảng seed-level; thêm kiểm khóa {kagg} của bảng seed_agg.', 'recomputed')

    # ---------------- QA24 ----------------
    ok24, d24 = qa24_run_level_invariants(df)
    EXT = [c for c in ['s_eff_after', 's_eff_before', 's_eff_definition_version', 's_eff_train_source', 's_eff_observed_rate', 's_eff_availability_rate', 's_leak_probe_fit_once',
                       'probe_seed', 'probe_fit_rows', 'time_train_s_after', 'time_run_total_s_after', 'time_train_s_before', 'time_run_total_s_before',
                       'energy_gpu_run_kwh_after', 'energy_gpu_run_kwh_before', 'param_count_total', 'param_count_trainable', 'model_tier', 'variant_role'] if c in df.columns]
    ok24x, d24x = qa24_run_level_invariants(df, cols=EXT)
    present_default = [c for c in RUN_LEVEL_COLS if c in df]
    f = put('QA24', pd.concat([d24.assign(scope='repo default columns'), d24x.assign(scope='extended columns')], ignore_index=True), 'detail')
    ng = df.run_id_after.nunique(); ncell = ng * len(set(present_default) | set(EXT)); nfail = len(d24) + len(d24x)
    rec('QA24', 'PASS' if ok24 and ok24x else 'FAIL', 'cặp (run, cột run-level)', ncell, ncell - nfail, nfail, f,
        f'{ng} run (run_id_after). Hàm qa24 của repo với cột mặc định (chỉ {len(present_default)} cột có trong bảng: {",".join(present_default)}) và danh sách mở rộng {len(EXT)} cột run-level có thật trong bảng (s_eff*, probe, thời gian, năng lượng, số tham số). '
        'Kiểm hằng số trên mọi phase/split/subgroup của một run. Không đưa s_leak_probe_n_eval vào danh sách vì cột này là số mẫu eval của probe, hằng số trong một run x eval_split nhưng khác nhau giữa VALIDATION và TEST (kiểm tra thực nghiệm), nên thuộc cấp split, không phải cấp run.', 'recomputed')

    FL = [c for c in df.columns if c.startswith('qa_')]
    put('ROWFLAGS', pd.DataFrame([{'flag': c, 'n_true': int(df[c].sum()), 'n_false': int((~df[c]).sum()), 'n_null': int(df[c].isna().sum())} for c in FL] +
                                 [{'flag': 'qa_leak_guard_ok (QA21)', 'n_true': 0, 'n_false': 0, 'n_null': N}]), 'check')

    # ---------------- QA16 integrity ----------------
    ir = []
    for line in open(REL + '/sha256sums.txt', encoding='utf-8'):
        if not line.strip():
            continue
        h, p = line.split(None, 1); p = p.strip().lstrip('*')
        ir.append({'scope': 'release sha256sums.txt', 'file': 'release_r2/' + p, 'expected': h, 'actual': sha(REL + '/' + p)})
    for k, v in man_in.items():
        p = v['path']
        ir.append({'scope': 'manifest inputs_sha256', 'file': rel_path(p), 'expected': v['sha256'], 'actual': sha(p) if os.path.exists(p) else None})
    ir.append({'scope': 'manifest s0_v5_sha256', 'file': 'CQ/resuilt/m13a_s0_profile_20261122_v5_dtypefix/s0_profile.parquet', 'expected': man['s0_v5_sha256'],
               'actual': sha(REPO + '/CQ/resuilt/m13a_s0_profile_20261122_v5_dtypefix/s0_profile.parquet')})
    for t in ('CQ', 'LO'):
        a_ = [sha(DELIV + f'/release_children_r2/{t}_3seed/{n}') for n in ('meta_dataset_seed_level.parquet', 'meta_dataset_seed_agg.parquet', 'meta_release_manifest.json')]
        ir.append({'scope': 'manifest children (match any of 3 files)', 'file': f'delivery_phaseB_r2_20261123/release_children_r2/{t}_3seed', 'expected': man['children'][t],
                   'actual': man['children'][t] if man['children'][t] in a_ else a_[0]})
    for p in ('meta_dataset_seed_level.parquet', 'meta_dataset_seed_agg.parquet', 'meta_column_dictionary.csv', 'meta_release_manifest.json'):
        ir.append({'scope': 'local release vs delivery_phaseB_r2 copy', 'file': p, 'expected': sha(REL + '/' + p), 'actual': sha(DELIV + '/release_r2/' + p)})
    for u, (d, s) in unit_sum.items():
        for line in open(d + '/sha256sums.txt', encoding='utf-8'):
            if not line.strip():
                continue
            h, p = line.split(None, 1); p = p.strip().lstrip('*')
            ir.append({'scope': 'unit package sha256sums.txt', 'file': rel_path(d + '/' + p), 'expected': h, 'actual': sha(d + '/' + p) if os.path.exists(d + '/' + p) else None})
    di = pd.DataFrame(ir); di['match'] = di.expected == di.actual
    f = put('QA16', di, 'detail')
    sc = di.groupby('scope').match.agg(['size', 'sum']).reset_index()
    nmis = int((~di.match).sum())
    rec('QA16', 'PASS' if nmis == 0 else 'FAIL', 'file', len(di), int(di.match.sum()), nmis, f,
        'Tính lại sha256 hôm nay và so với: sha256sums.txt của release, inputs_sha256 + s0_v5_sha256 + children trong manifest, bản sao bàn giao pha B (delivery_phaseB_r2_20261123/release_r2), sha256sums.txt của 36 gói unit. '
        'Biên nhận Drive (rclone check --checksum, 458 file, 0 khác biệt, 23/11/2026) ở CQ/resuilt/delivery_phaseB_r2_20261123_receipt.txt chỉ được trích dẫn. Chi tiết: ' +
        '; '.join(f'{r.scope} {int(r["sum"])}/{r["size"]}' for _, r in sc.iterrows()) + '.', 'recomputed')

    json.dump(dict(run_date=RUN_DATE, code_commit=git_head(), results=RES), open(OUT + '/qa_results_raw.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=str)
    print('done', flush=True)


if __name__ == '__main__':
    main()
