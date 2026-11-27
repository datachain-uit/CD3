# -*- coding: utf-8 -*-
"""Metrics missing from stage 1 and the paired bootstrap (PLAN v1.6 §6.3, §6.8, Table 25).

* per-class precision / recall / specificity / F1 / G-mean / AP / support / predicted_count
* pr_auc_macro, roc_auc_macro_ovr (from stored probability matrices; no rerun needed)
* macro_f1, balanced_acc, mcc, kappa, gmean (multi-class) and s_perf
* paired bootstrap of Δ metric between an *after* and a *before* run on the same enrollments
  (B = 2000, unit = ENROLLMENT), returning ci_low, ci_high and p_boot_le0.
"""
from __future__ import annotations

from typing import Callable, Dict, Optional, Sequence

import numpy as np
from sklearn.metrics import (average_precision_score, balanced_accuracy_score, cohen_kappa_score,
                             confusion_matrix, f1_score, matthews_corrcoef, roc_auc_score)

from .sanity import s_perf as _s_perf


def per_class_metrics(y: np.ndarray, y_pred: np.ndarray, P: Optional[np.ndarray] = None, k: int = 3) -> Dict[str, Dict[str, float]]:
    """Per class c: support, predicted_count, precision, recall, specificity, f1, gmean_class, ap.
    NULL (nan) when the denominator is zero (CLASS_ABSENT / NO_PREDICTION), never 0."""
    cm = confusion_matrix(y, y_pred, labels=list(range(k)))
    out = {}
    n = cm.sum()
    for c in range(k):
        tp = cm[c, c]; fn = cm[c].sum() - tp; fp = cm[:, c].sum() - tp; tn = n - tp - fn - fp
        rec = tp / (tp + fn) if (tp + fn) else float('nan')
        prec = tp / (tp + fp) if (tp + fp) else float('nan')
        spec = tn / (tn + fp) if (tn + fp) else float('nan')
        f1 = (2 * prec * rec / (prec + rec)) if (prec == prec and rec == rec and (prec + rec) > 0) else (0.0 if (tp + fn) else float('nan'))
        gm = float(np.sqrt(rec * spec)) if (rec == rec and spec == spec) else float('nan')
        ap = float(average_precision_score((y == c).astype(int), P[:, c])) if (P is not None and (tp + fn)) else float('nan')
        out[f'c{c}'] = {'support': int(tp + fn), 'predicted_count': int(tp + fp), 'precision': prec, 'recall': rec,
                        'specificity': spec, 'f1': f1, 'gmean': gm, 'ap': ap}
    return out


def overall_metrics(y: np.ndarray, P: np.ndarray, k: int = 3) -> Dict[str, float]:
    y = np.asarray(y, dtype=int); P = np.asarray(P, dtype=float)
    y_pred = P.argmax(axis=1)
    labels = list(range(k))
    macro_f1 = f1_score(y, y_pred, labels=labels, average='macro', zero_division=0)
    ba = balanced_accuracy_score(y, y_pred)
    mcc = matthews_corrcoef(y, y_pred)
    kappa = cohen_kappa_score(y, y_pred)
    rec = np.array([per_class_metrics(y, y_pred, None, k)[f'c{c}']['recall'] for c in range(k)], dtype=float)
    gmean = float(np.prod(np.nan_to_num(rec, nan=0.0)) ** (1.0 / k))
    present = np.unique(y)
    if len(present) >= 2:
        pr_auc = float(np.mean([average_precision_score((y == c).astype(int), P[:, c]) for c in present]))
        roc = float(np.mean([roc_auc_score((y == c).astype(int), P[:, c]) for c in present]))
    else:
        pr_auc = roc = float('nan')
    return {'macro_f1': float(macro_f1), 'balanced_acc': float(ba), 'mcc': float(mcc), 'kappa': float(kappa),
            'gmean': gmean, 'pr_auc_macro': pr_auc, 'roc_auc_macro_ovr': roc, 'accuracy': float((y == y_pred).mean()),
            'weighted_f1': float(f1_score(y, y_pred, labels=labels, average='weighted', zero_division=0)),
            's_perf': _s_perf(macro_f1, ba, mcc, kappa), 'n_eval_samples': int(len(y)), 'n_classes_present': int(len(present))}


def paired_bootstrap_delta(y: np.ndarray, P_after: np.ndarray, P_before: np.ndarray,
                           metric_fn: Callable[[np.ndarray, np.ndarray], float], unit_ids: Optional[np.ndarray] = None,
                           B: int = 2000, seed: int = 0, ci: float = 0.95) -> Dict[str, float]:
    """Paired bootstrap (PLAN §6.8): resample units (enrollments) with replacement, compute the metric on
    the SAME resample for after and before, Δ*_b = m_after,b − m_before,b."""
    rng = np.random.default_rng(seed)
    y = np.asarray(y); P_after = np.asarray(P_after); P_before = np.asarray(P_before)
    if unit_ids is None:
        unit_ids = np.arange(len(y))
    unit_ids = np.asarray(unit_ids)
    units, inv = np.unique(unit_ids, return_inverse=True)
    rows_by_unit = [np.flatnonzero(inv == u) for u in range(len(units))]
    point = metric_fn(y, P_after) - metric_fn(y, P_before)
    deltas = np.empty(B)
    for b in range(B):
        pick = rng.integers(0, len(units), len(units))
        idx = np.concatenate([rows_by_unit[u] for u in pick])
        deltas[b] = metric_fn(y[idx], P_after[idx]) - metric_fn(y[idx], P_before[idx])
    lo, hi = np.percentile(deltas, [(1 - ci) / 2 * 100, (1 + ci) / 2 * 100])
    return {'delta': float(point), 'delta_ci_low': float(lo), 'delta_ci_high': float(hi),
            'delta_p_boot_le0': float(np.mean(deltas <= 0)), 'delta_n_boot': int(B), 'delta_boot_unit': 'ENROLLMENT', 'boot_seed': seed}


def macro_f1_fn(y: np.ndarray, P: np.ndarray, k: int = 3) -> float:
    return float(f1_score(y, P.argmax(axis=1), labels=list(range(k)), average='macro', zero_division=0))
