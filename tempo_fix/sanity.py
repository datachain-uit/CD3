# -*- coding: utf-8 -*-
"""Sanity components, S_san+ (v1 / v2), S_perf and AccTEMPO_M3 (PLAN v1.6 §6.3, §6.10, §6.11).

All functions work on a probability matrix P (n × K, rows sum to 1) and integer labels y in {0..K-1}.
Run-level quantities (s_eff, s_leak) are passed in, because they are properties of the run, not of
the evaluated slice (QA24). Everything here is recomputable from stored L1/L2 artefacts.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional, Sequence, Tuple

import numpy as np

EPS_FLOOR = 1e-3          # s_eps_floor and acctempo_eps_floor (v1.6)
PROB_CLIP = 1e-12


# ---------------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------------
def _clip_renorm(P: np.ndarray, clip: float = PROB_CLIP) -> np.ndarray:
    P = np.clip(np.asarray(P, dtype=float), clip, 1.0)
    return P / P.sum(axis=1, keepdims=True)


def jsd_base2(p: np.ndarray, q: np.ndarray) -> float:
    """Jensen–Shannon divergence with log2 (in [0, 1]); 0·log(0/b) := 0."""
    p = np.asarray(p, dtype=float); q = np.asarray(q, dtype=float)
    p = p / p.sum() if p.sum() > 0 else p
    q = q / q.sum() if q.sum() > 0 else q
    m = 0.5 * (p + q)

    def kl(a, b):
        mask = a > 0
        return float(np.sum(a[mask] * np.log2(a[mask] / b[mask])))
    return 0.5 * kl(p, m) + 0.5 * kl(q, m)


def class_counts(y: np.ndarray, k: int) -> np.ndarray:
    return np.bincount(np.asarray(y, dtype=int), minlength=k).astype(float)


# ---------------------------------------------------------------------------------------------
# six components
# ---------------------------------------------------------------------------------------------
def s_nan(P: np.ndarray, tol: float = 1e-4) -> float:
    P = np.asarray(P, dtype=float)
    if not np.all(np.isfinite(P)):
        return 0.0
    return 1.0 if float(np.max(np.abs(P.sum(axis=1) - 1.0))) <= tol else 0.0


def s_maj_jsd(P: np.ndarray, y: np.ndarray) -> float:
    """1 − JSD2(predicted class distribution ‖ true class distribution of the slice)."""
    k = P.shape[1]
    pred = class_counts(P.argmax(axis=1), k)
    true = class_counts(y, k)
    return 1.0 - jsd_base2(pred, true)


def normalised_entropy(P: np.ndarray) -> np.ndarray:
    P = _clip_renorm(P)
    k = P.shape[1]
    return -(P * np.log(P)).sum(axis=1) / math.log(k)


def s_ent_v1(P: np.ndarray) -> float:
    """v1 (published): 1 − min(|median(h_i) − 0.5| / 0.5, 1)."""
    m = float(np.median(normalised_entropy(P)))
    return 1.0 - min(abs(m - 0.5) / 0.5, 1.0)


def ece_top_label(P: np.ndarray, y: np.ndarray, n_bins: int = 15) -> float:
    """Expected calibration error on the top-label confidence, equal-width bins."""
    P = np.asarray(P, dtype=float); y = np.asarray(y, dtype=int)
    conf = P.max(axis=1); pred = P.argmax(axis=1); correct = (pred == y).astype(float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip(np.searchsorted(edges, conf, side='right') - 1, 0, n_bins - 1)
    ece = 0.0
    n = len(conf)
    for b in range(n_bins):
        m = idx == b
        if m.any():
            ece += m.sum() / n * abs(correct[m].mean() - conf[m].mean())
    return float(ece)


def s_cal_v2(P: np.ndarray, y: np.ndarray, n_bins: int = 15) -> float:
    """v2 registered variant: 1 − ECE_15 (replaces s_ent in S_san+ v2)."""
    return 1.0 - ece_top_label(P, y, n_bins)


def s_drift(P: np.ndarray, train_prior_counts: Sequence[float]) -> float:
    """1 − JSD2(predicted class distribution ‖ TRAIN real class distribution before balancing)."""
    k = P.shape[1]
    pred = class_counts(P.argmax(axis=1), k)
    return 1.0 - jsd_base2(pred, np.asarray(train_prior_counts, dtype=float))


def s_eff_from_mask(mask: np.ndarray) -> float:
    """Run-level effective-batch score: share of tensor elements that carry information (mask = 1)
    in the TRAIN tensor actually used for training (S3_MODEL_INPUT, pooled P1–P4)."""
    return float(np.mean(np.asarray(mask, dtype=float)))


def s_leak_from_auc(auc_probe: float) -> float:
    """v1.5 scale: 1 − 2·max(AUC − 0.5, 0); chance → 1, perfect probe → 0."""
    return 1.0 - 2.0 * max(float(auc_probe) - 0.5, 0.0)


def leak_probe_auc(X_fit: np.ndarray, y_fit: np.ndarray, X_eval: np.ndarray, y_eval: np.ndarray,
                   seed: int = 0, C: float = 1.0) -> Dict[str, float]:
    """Missingness-only probe (multinomial logistic regression, L2, standardised features).
    X_* must contain ONLY missingness indicators (share of M_missing=1, share of M_available=0 per
    feature, zero_event_flag). Returns macro OvR AUC on the evaluation slice plus row counts."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.preprocessing import StandardScaler
    sc = StandardScaler().fit(X_fit)
    clf = LogisticRegression(C=C, max_iter=1000, random_state=seed)
    clf.fit(sc.transform(X_fit), y_fit)
    proba = clf.predict_proba(sc.transform(X_eval))
    classes = clf.classes_
    present = np.isin(classes, np.unique(y_eval))
    if present.sum() < 2:
        auc = float('nan')
    else:
        # macro OvR over classes present in the evaluation slice
        aucs = []
        for j, c in enumerate(classes):
            if present[j]:
                aucs.append(roc_auc_score((y_eval == c).astype(int), proba[:, j]))
        auc = float(np.mean(aucs))
    return {'auc_probe': auc, 's_leak': s_leak_from_auc(auc) if auc == auc else float('nan'),
            'n_fit': int(len(y_fit)), 'n_eval': int(len(y_eval))}


# ---------------------------------------------------------------------------------------------
# composites
# ---------------------------------------------------------------------------------------------
def geometric_mean(values: Sequence[float], eps_floor: float = EPS_FLOOR) -> Tuple[float, int]:
    """Geometric mean with per-component floor; returns (value, n_components_at_floor)."""
    v = np.asarray(values, dtype=float)
    at_floor = int(np.sum(v < eps_floor))
    v = np.maximum(v, eps_floor)
    return float(np.exp(np.mean(np.log(v)))), at_floor


def s_perf(macro_f1: float, balanced_acc: float, mcc: float, kappa: float) -> float:
    """(MacroF1 · BA · (MCC+1)/2 · (κ+1)/2)^(1/4)."""
    parts = [macro_f1, balanced_acc, (mcc + 1) / 2, (kappa + 1) / 2]
    parts = [max(x, 0.0) for x in parts]
    return float(np.prod(parts) ** 0.25)


def acctempo_m3(sperf: float, ssan: float, alpha: float = 0.6, beta: float = 0.4,
                eps_floor: float = EPS_FLOOR) -> float:
    return float(max(sperf, eps_floor) ** alpha * max(ssan, eps_floor) ** beta)


def log_decomposition(sperf_before: float, ssan_before: float, sperf_after: float, ssan_after: float,
                      alpha: float = 0.6, beta: float = 0.4, eps_floor: float = EPS_FLOOR) -> Dict[str, float]:
    """Δ log AccTEMPO_M3 = α·Δ log S_perf + β·Δ log S_san+ (perf_part, san_part)."""
    f = lambda x: math.log(max(x, eps_floor))
    perf_part = alpha * (f(sperf_after) - f(sperf_before))
    san_part = beta * (f(ssan_after) - f(ssan_before))
    return {'log_delta_perf_part': perf_part, 'log_delta_san_part': san_part, 'log_delta_total': perf_part + san_part}


@dataclass
class SanityResult:
    s_nan: float
    s_maj_jsd: float
    s_ent: float
    s_cal: float
    s_drift: float
    s_eff: float
    s_leak: float
    s_san_plus_v1: float
    s_san_plus_v2: float
    n_at_floor_v1: int
    n_at_floor_v2: int
    ece_15: float
    median_norm_entropy: float

    def as_dict(self) -> Dict[str, float]:
        return self.__dict__.copy()


def compute_sanity(P: np.ndarray, y: np.ndarray, train_prior_counts: Sequence[float], s_eff_value: float,
                   s_leak_value: float, eps_floor: float = EPS_FLOOR) -> SanityResult:
    """All six components for one evaluated slice; s_eff and s_leak are run-level inputs."""
    P = np.asarray(P, dtype=float); y = np.asarray(y, dtype=int)
    comp = {
        's_nan': s_nan(P), 's_maj_jsd': s_maj_jsd(P, y), 's_ent': s_ent_v1(P), 's_cal': s_cal_v2(P, y),
        's_drift': s_drift(P, train_prior_counts), 's_eff': float(s_eff_value), 's_leak': float(s_leak_value),
    }
    v1, f1 = geometric_mean([comp['s_nan'], comp['s_maj_jsd'], comp['s_ent'], comp['s_drift'], comp['s_eff'], comp['s_leak']], eps_floor)
    v2, f2 = geometric_mean([comp['s_nan'], comp['s_maj_jsd'], comp['s_cal'], comp['s_drift'], comp['s_eff'], comp['s_leak']], eps_floor)
    return SanityResult(**comp, s_san_plus_v1=v1, s_san_plus_v2=v2, n_at_floor_v1=f1, n_at_floor_v2=f2,
                        ece_15=1.0 - comp['s_cal'], median_norm_entropy=float(np.median(normalised_entropy(P))))


def acctempo_bundle(sperf: float, san: SanityResult, alpha: float = 0.6, beta: float = 0.4,
                    eps_floor: float = EPS_FLOOR) -> Dict[str, float]:
    return {'s_perf': sperf,
            'acctempo_m3': acctempo_m3(sperf, san.s_san_plus_v1, alpha, beta, eps_floor),
            'acctempo_m3_v2': acctempo_m3(sperf, san.s_san_plus_v2, alpha, beta, eps_floor)}
