# -*- coding: utf-8 -*-
"""L3 pilot builder: keys, V0 rows and column dictionary (PLAN v1.6 §3.1, §3.2, §4.4, §5.1, P2 of the roadmap).

The pilot turns the existing V0 runs (RNN × seed × W1–W3) into meta_dataset_seed_level rows so that
QA01–QA24 and the column dictionary can be exercised before the run grid grows. Reference columns
(imp_only, ref) that do not exist yet are NULL with an explicit reason in null_reason_map.
"""
from __future__ import annotations

import json
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

import numpy as np
import pandas as pd

from .seeds import sha256_of

KEY_FIELDS = ('task', 'label_rule_version', 'label_threshold_set', 'feature_regime', 'window_id', 'seed', 'phase_id',
              'cohort', 'eval_split', 'subgroup_axis', 'subgroup_value', 'model_name', 'pipeline_id')
PHASE_INDEX = {'P1': (1, 0.25), 'P2': (2, 0.50), 'P3': (3, 0.75), 'P4': (4, 0.90)}
CORE_METRICS = ('acctempo_m3', 's_perf', 'macro_f1', 'balanced_acc', 'mcc', 'kappa', 'pr_auc_macro', 'gmean')
EXT_METRICS = ('accuracy', 'weighted_f1', 'roc_auc_macro_ovr', 'log_loss', 'brier', 'ece')
SAN_COMPONENTS = ('s_nan', 's_maj_jsd', 's_ent', 's_drift', 's_eff', 's_leak', 's_cal', 's_san_plus', 's_san_plus_v2')
MANDATORY_SUBGROUPS = (('ALL', 'ALL'), ('LEARNER', 'SEEN'), ('LEARNER', 'UNSEEN'), ('COURSE', 'SEEN'), ('COURSE', 'UNSEEN'))


def meta_key(**kw) -> Dict[str, object]:
    missing = [k for k in KEY_FIELDS if k not in kw]
    if missing:
        raise KeyError(f'meta key missing {missing}')
    return {k: kw[k] for k in KEY_FIELDS}


def meta_obs_id(key: Mapping[str, object]) -> str:
    return sha256_of({k: key[k] for k in KEY_FIELDS})


def rec_group_id(key: Mapping[str, object]) -> str:
    return sha256_of({k: key[k] for k in KEY_FIELDS if k != 'pipeline_id'})


def build_v0_rows(l2_rows: pd.DataFrame, key_defaults: Mapping[str, object], run_ids: Mapping[str, str],
                  subgroups: Sequence[tuple] = MANDATORY_SUBGROUPS, provenance: Optional[Mapping[str, object]] = None) -> pd.DataFrame:
    """l2_rows: one row per (window_id, eval_split, phase_id[, subgroup_axis, subgroup_value]) of a V0 run with
    metric columns named exactly as CORE/EXT metrics and sanity components (values of the V0 run).
    key_defaults: task, label_rule_version, label_threshold_set, feature_regime, seed, cohort, model_name.
    run_ids: {'W1': run_id_after, ...} for the V0 run of each window.
    Returns seed-level rows with after = before, delta = 0, is_no_intervention = 1 and null reasons."""
    out = []
    has_sub = {'subgroup_axis', 'subgroup_value'} <= set(l2_rows.columns)
    for _, r in l2_rows.iterrows():
        subs = [(r['subgroup_axis'], r['subgroup_value'])] if has_sub else list(subgroups)
        for axis, value in subs:
            key = meta_key(pipeline_id='V0', window_id=r['window_id'], phase_id=r['phase_id'], eval_split=r['eval_split'],
                           subgroup_axis=axis, subgroup_value=value, **key_defaults)
            row = dict(key)
            row['meta_obs_id'] = meta_obs_id(key)
            row['rec_group_id'] = rec_group_id(key)
            row['run_id_after'] = row['run_id_before'] = run_ids[r['window_id']]
            row['run_group_id'] = row['run_id_after']
            row['meta_cv_group'] = r['window_id']
            row['phase_index'], row['q'] = PHASE_INDEX[r['phase_id']]
            row['is_primary_cohort'], row['population_varies_by_phase'] = 1, 0
            row['is_no_intervention'], row['has_imputation'], row['has_balancing'] = 1, 0, 0
            nulls: Dict[str, str] = {}
            if not has_sub and (axis, value) != ('ALL', 'ALL'):
                # subgroup metrics not yet computed for this pilot → NULL with reason
                for m in CORE_METRICS + EXT_METRICS:
                    for suf in ('_before', '_after', '_delta'):
                        row[m + suf] = np.nan
                        nulls[m + suf] = 'NOT_COMPUTED'
                for c in SAN_COMPONENTS:
                    row[c + '_before'] = row[c + '_after'] = np.nan
                    nulls[c + '_before'] = nulls[c + '_after'] = 'NOT_COMPUTED'
            else:
                for m in CORE_METRICS + EXT_METRICS:
                    v = r.get(m)
                    if v is None or pd.isna(v):
                        row[m + '_before'] = row[m + '_after'] = row[m + '_delta'] = np.nan
                        nulls[m + '_before'] = nulls[m + '_after'] = nulls[m + '_delta'] = 'NOT_COMPUTED'
                    else:
                        row[m + '_before'] = row[m + '_after'] = float(v)
                        row[m + '_delta'] = 0.0
                for c in SAN_COMPONENTS:
                    v = r.get(c)
                    if v is None or pd.isna(v):
                        row[c + '_before'] = row[c + '_after'] = np.nan
                        nulls[c + '_before'] = nulls[c + '_after'] = 'NOT_COMPUTED'
                    else:
                        row[c + '_before'] = row[c + '_after'] = float(v)
            for m in CORE_METRICS:
                row[m + '_imp_only'] = row[m + '_delta_imp'] = row[m + '_delta_bal'] = np.nan
                nulls[m + '_imp_only'] = nulls[m + '_delta_imp'] = nulls[m + '_delta_bal'] = 'BASELINE_MISSING'
                row[m + '_ref'] = row[m + '_delta_ref'] = np.nan
                nulls[m + '_ref'] = nulls[m + '_delta_ref'] = 'NOT_APPLICABLE' if m == 'acctempo_m3' else 'BASELINE_MISSING'
            row['run_id_imp_only'] = row['run_id_after']          # V0 → V0 (PLAN Table 14)
            row['run_id_ref'] = None
            nulls['run_id_ref'] = 'BASELINE_MISSING'
            if provenance:
                row.update(provenance)
            row['row_status'] = 'COMPLETE' if not any(v == 'NOT_COMPUTED' for v in nulls.values()) else 'PARTIAL'
            row['null_reason_map'] = json.dumps(nulls, sort_keys=True)
            out.append(row)
    return pd.DataFrame(out)


ROLE_RULES = [
    (('meta_obs_id', 'rec_group_id', 'run_group_id', 'meta_cv_group') + KEY_FIELDS + ('phase_index', 'q', 'is_primary_cohort', 'population_varies_by_phase'), 'K', 'KEY'),
    (('run_id_after', 'run_id_before', 'run_id_imp_only', 'run_id_ref', 'meta_release_id', 'meta_schema_version', 'data_release_id', 'split_version',
      'feature_dictionary_version', 'hparam_config_id', 'metric_def_version', 'acctempo_def_version', 's_san_formula_version'), 'K', 'PROV'),
    (('row_status', 'null_reason_map'), 'K', 'QA'),
    (('is_no_intervention', 'has_imputation', 'has_balancing'), 'Z_A', 'X_CONTEXT'),
]


def build_column_dictionary(df: pd.DataFrame, extra_rules: Optional[Iterable[tuple]] = None) -> pd.DataFrame:
    """Assign block/role to every column of the L3 frame from name patterns (PLAN §4.3, Table 17)."""
    rules = list(ROLE_RULES) + list(extra_rules or [])
    rows = []
    for c in df.columns:
        block = role = None
        for names, b, r in rules:
            if c in names:
                block, role = b, r
                break
        if role is None:
            if c.startswith('val_'):
                block, role = 'Y', 'X_VAL'
            elif c.startswith(('s_nan', 's_maj_jsd', 's_ent', 's_drift', 's_eff', 's_leak', 's_cal', 's_san_plus')):
                block, role = 'Y_DQ', 'DIAG'
            elif any(c.startswith(m) for m in CORE_METRICS + EXT_METRICS):
                block, role = 'Y', 'TARGET'
            elif c.startswith(('ev_class_', 'ev_imbalance', 'ev_minority', 'ev_n_classes', 'label_drift_tr_ev')):
                block, role = 'Z_D', 'X_RESTRICTED'
            elif c.startswith(('tr_', 'trpool_', 'ev_', 'drift_', 'label_drift_window')):
                block, role = 'Z_D', 'X_STATE'
            elif c.startswith(('time_', 'energy_', 'co2e_', 'cost_', 'peak_')):
                block, role = 'C', 'COST'
            elif c.startswith(('rank_', 'regret', 'is_best', 'within_eps', 'recommended', 'beats_v0', 'harms_v0', 'utility_')):
                block, role = 'R', 'DERIVED'
            elif c.startswith('qa_'):
                block, role = 'QA', 'QA'
            else:
                block, role = 'UNASSIGNED', ''
        rows.append({'column_name': c, 'block': block, 'role': role, 'dtype': str(df[c].dtype), 'nullable': bool(df[c].isna().any())})
    return pd.DataFrame(rows)
