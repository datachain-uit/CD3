# -*- coding: utf-8 -*-
"""sampling_strategy arithmetic for the balancers (PLAN v1.6 §2.3).

Two registered schemes and their combination:
  IR_TARGET   : n_target_c = max(n_c, ceil(n_max / ir_target))        — fixes the post-balancing class ratio
  MULTIPLIER  : n_target_c = k * n_c                                    — fixes the synthetic burden per real sample
  COMBINED    : n_target_c = min(max(n_c, ceil(n_max / ir_target)), k_max * n_c)
The majority class is never undersampled. Everything here is arithmetic on class counts, so the same
function is used to size a run before it starts and to check trpool_n_synth afterwards.
"""
from __future__ import annotations

import math
from typing import Dict, Iterable, List, Mapping, Optional

import pandas as pd


def plan_targets(counts: Mapping[str, int], ir_target: Optional[float] = None, k_max: Optional[float] = None,
                 scheme_id: Optional[str] = None) -> pd.DataFrame:
    """Per-class targets for one TRAIN class distribution.

    counts: {class_code: n}. ir_target and/or k_max define the scheme (at least one must be given).
    Returns one row per class with n, n_target, synthetic, expansion (= n_target/n), post_ir (= n_max/n_target),
    binding ('MAJORITY' | 'IR_TARGET' | 'K_MAX' | 'NONE')."""
    if ir_target is None and k_max is None:
        raise ValueError('give ir_target, k_max or both')
    n_max = max(counts.values())
    rows = []
    for c, n in counts.items():
        if n == n_max:
            rows.append({'class': c, 'n': n, 'n_target': n, 'synthetic': 0, 'expansion': 1.0, 'post_ir': 1.0, 'binding': 'MAJORITY'})
            continue
        t_ir = max(n, math.ceil(n_max / ir_target)) if ir_target else None
        t_k = int(round(k_max * n)) if k_max else None
        if t_ir is not None and t_k is not None:
            n_target = min(t_ir, t_k)
            binding = 'IR_TARGET' if t_ir <= t_k else 'K_MAX'
        elif t_ir is not None:
            n_target, binding = t_ir, 'IR_TARGET'
        else:
            n_target, binding = t_k, 'K_MAX'
        if n_target <= n:
            n_target, binding = n, 'NONE'
        rows.append({'class': c, 'n': n, 'n_target': int(n_target), 'synthetic': int(n_target - n),
                     'expansion': n_target / n, 'post_ir': n_max / n_target, 'binding': binding})
    df = pd.DataFrame(rows)
    df['scheme_id'] = scheme_id or _scheme_id(ir_target, k_max)
    return df


def _scheme_id(ir_target, k_max) -> str:
    parts = []
    if ir_target:
        parts.append(f'IR{ir_target:g}')
    if k_max:
        parts.append(f'K{k_max:g}')
    return '_'.join(parts)


def summarize(targets: pd.DataFrame) -> Dict[str, float]:
    """Dataset-level summary of a plan_targets frame."""
    n_before = int(targets['n'].sum())
    n_after = int(targets['n_target'].sum())
    minority = targets[targets['binding'] != 'MAJORITY']
    return {
        'scheme_id': targets['scheme_id'].iloc[0],
        'n_train_before': n_before, 'n_train_after': n_after,
        'n_synthetic': int(targets['synthetic'].sum()),
        'expansion_ratio': n_after / n_before,
        'synthetic_share': float(targets['synthetic'].sum() / n_after),
        'post_ir_max': float(minority['post_ir'].max()) if len(minority) else 1.0,
        'max_class_expansion': float(minority['expansion'].max()) if len(minority) else 1.0,
    }


def grid(counts: Mapping[str, int], schemes: Iterable[Dict], dataset: str = '') -> pd.DataFrame:
    """Evaluate several schemes on one class distribution; one row per (scheme, class) plus summary columns."""
    out = []
    for sch in schemes:
        t = plan_targets(counts, sch.get('ir_target'), sch.get('k_max'), sch.get('scheme_id'))
        s = summarize(t)
        for _, r in t.iterrows():
            out.append({'dataset': dataset, **s, **r.to_dict()})
    return pd.DataFrame(out)


DEFAULT_SCHEMES: List[Dict] = [
    {'scheme_id': 'IR5', 'ir_target': 5}, {'scheme_id': 'IR10', 'ir_target': 10}, {'scheme_id': 'IR20', 'ir_target': 20},
    {'scheme_id': 'IR50', 'ir_target': 50},
    {'scheme_id': 'K2', 'k_max': 2}, {'scheme_id': 'K5', 'k_max': 5}, {'scheme_id': 'K10', 'k_max': 10}, {'scheme_id': 'K20', 'k_max': 20},
    {'scheme_id': 'IR10_K10', 'ir_target': 10, 'k_max': 10}, {'scheme_id': 'IR5_K20', 'ir_target': 5, 'k_max': 20},
    {'scheme_id': 'IR20_K5', 'ir_target': 20, 'k_max': 5},
]


# Decision 2026-09-27: combined rule IR_target = 10 with max_expansion_per_class = 10 (primary).
PRIMARY_SCHEME: Dict = {'scheme_id': 'IR10_K10', 'ir_target': 10, 'k_max': 10}
SENSITIVITY_SCHEMES: List[Dict] = [{'scheme_id': 'IR5_K20', 'ir_target': 5, 'k_max': 20},
                                   {'scheme_id': 'IR20_K5', 'ir_target': 20, 'k_max': 5}]


def targets_from_registry(counts: Mapping[str, int], strategy: Mapping) -> pd.DataFrame:
    """plan_targets driven by a registry entry ({ir_target, max_expansion_per_class, sampling_strategy_id})."""
    return plan_targets(counts, strategy.get('ir_target'), strategy.get('max_expansion_per_class'), strategy.get('sampling_strategy_id'))


def check_synthetic_counts(counts_real: Mapping[str, int], counts_synth: Mapping[str, int], strategy: Mapping) -> pd.DataFrame:
    """QA helper: compare the synthetic counts actually produced by a balancer run (trpool_n_synth per class)
    with the registered rule; returns per-class expected/actual/diff (diff must be 0)."""
    t = targets_from_registry(counts_real, strategy).set_index('class')
    rows = []
    for c in counts_real:
        exp = int(t.loc[c, 'synthetic'])
        act = int(counts_synth.get(c, 0))
        rows.append({'class': c, 'expected_synthetic': exp, 'actual_synthetic': act, 'diff': act - exp})
    return pd.DataFrame(rows)
