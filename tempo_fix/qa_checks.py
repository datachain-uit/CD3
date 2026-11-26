# -*- coding: utf-8 -*-
"""QA checks on L2/L3 tables (PLAN v1.6 §8, Table 37). Each check returns (passed, details DataFrame).

Implemented: QA03, QA04, QA08, QA09, QA10, QA15, QA18, QA19, QA20, QA22 (via split_v2), QA24.
The remaining checks (QA01, QA02, QA05–QA07, QA11–QA14, QA16, QA17, QA21, QA23) depend on artefacts
that only exist in the user's pipeline (run registry, sample predictions, checkpoints); their
contracts are documented in CHANGE_SPEC and in feature_dictionary.qa23 / seen_flags.qa15.
"""
from __future__ import annotations

import json
import re
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

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


def run_all(df: pd.DataFrame, dictionary: Optional[pd.DataFrame] = None, split_audit: Optional[pd.DataFrame] = None) -> Dict[str, object]:
    """Convenience: run every applicable check and return a manifest-style summary."""
    from .split_v2 import qa22
    summary = {}
    checks = {'QA03': lambda: qa03_delta_identity(df), 'QA04': lambda: qa04_decomposition(df),
              'QA08': lambda: qa08_cell_accounting(df), 'QA09': lambda: qa09_unavailable_monotone(df) if 'ev_unavailable_rate' in df else (True, None),
              'QA10': lambda: qa10_fixed_labels(df), 'QA15': lambda: qa15_seen_offering(df) if 'seen_offering' in df else (True, None),
              'QA18': lambda: qa18_null_reasons(df), 'QA20': lambda: qa20_unique_keys(df), 'QA24': lambda: qa24_run_level_invariants(df)}
    if dictionary is not None:
        checks['QA19'] = lambda: qa19_roles(df, dictionary)
    if split_audit is not None:
        checks['QA22'] = lambda: qa22(split_audit)
    for name, fn in checks.items():
        ok, det = fn()
        summary[name] = {'passed': bool(ok), 'n_detail_rows': (0 if det is None else int(len(det)))}
    summary['all_passed'] = all(v['passed'] for v in summary.values() if isinstance(v, dict))
    return summary
