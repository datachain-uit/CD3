"""Classification, sanity, AccTEMPO_M3 and paired-bootstrap metrics.

All functions use the fixed three-class order c0/c1/c2 required by the MDS
specification.  Per-class values are NULL/None when a class is absent, while
primary macro metrics retain the fixed-K convention (missing class contributes
zero) so results remain comparable across slices.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, cohen_kappa_score, confusion_matrix,
                             f1_score, log_loss, matthews_corrcoef, precision_recall_fscore_support)
from sklearn.preprocessing import StandardScaler

CLASS_IDS = np.array([0, 1, 2])
EPS = 1e-12
# Registered floor for composite quality/performance scores.  Keep numerical
# probability/JSD smoothing separate so this policy does not distort either.
COMPOSITE_EPS = 1e-3


def _jsd_base2(left: np.ndarray, right: np.ndarray) -> float:
    left = np.asarray(left, dtype=float) + EPS
    right = np.asarray(right, dtype=float) + EPS
    left /= left.sum()
    right /= right.sum()
    middle = (left + right) / 2
    return float(0.5 * np.sum(left * np.log2(left / middle)) + 0.5 * np.sum(right * np.log2(right / middle)))


def _ece(y_true: np.ndarray, probabilities: np.ndarray, bins: int = 15) -> float:
    confidence = probabilities.max(axis=1)
    correct = probabilities.argmax(axis=1) == y_true
    edges = np.linspace(0, 1, bins + 1)
    value = 0.0
    for lower, upper in zip(edges[:-1], edges[1:]):
        selected = (confidence >= lower) & (confidence < upper if upper < 1 else confidence <= upper)
        if selected.any():
            value += selected.mean() * abs(correct[selected].mean() - confidence[selected].mean())
    return float(value)


def _class_metrics(confusion: np.ndarray, probabilities: np.ndarray, y_true: np.ndarray) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for class_id in CLASS_IDS:
        tp = int(confusion[class_id, class_id])
        fn = int(confusion[class_id, :].sum() - tp)
        fp = int(confusion[:, class_id].sum() - tp)
        tn = int(confusion.sum() - tp - fn - fp)
        support = tp + fn
        predicted = tp + fp
        prefix = f"c{class_id}"
        output[f"{prefix}_support"] = support
        output[f"{prefix}_predicted_count"] = predicted
        if support == 0:
            output.update({f"{prefix}_{metric}": None for metric in ("precision", "recall", "specificity", "f1", "gmean", "ap")})
            continue
        precision = None if predicted == 0 else tp / predicted
        recall = tp / support
        specificity = None if tn + fp == 0 else tn / (tn + fp)
        f1 = None if precision is None or precision + recall == 0 else 2 * precision * recall / (precision + recall)
        gmean = None if specificity is None else float(np.sqrt(recall * specificity))
        try:
            ap = float(average_precision_score((y_true == class_id).astype(int), probabilities[:, class_id]))
        except ValueError:
            ap = None
        output.update({f"{prefix}_precision": precision, f"{prefix}_recall": recall,
                       f"{prefix}_specificity": specificity, f"{prefix}_f1": f1,
                       f"{prefix}_gmean": gmean, f"{prefix}_ap": ap})
    return output


def classification_metrics(y_true: np.ndarray, probabilities: np.ndarray, *, train_class_counts: np.ndarray | None = None,
                           s_eff: float | None = None, s_leak: float | None = None) -> dict[str, Any]:
    """Compute all MDS primary classification and prediction-sanity metrics."""
    y_true = np.asarray(y_true, dtype=int)
    probabilities = np.asarray(probabilities, dtype=float)
    if probabilities.ndim != 2 or probabilities.shape[1] != 3 or len(y_true) != len(probabilities):
        raise ValueError("Expected y_true[n] and probabilities[n, 3] in c0/c1/c2 order")
    finite = np.isfinite(probabilities).all()
    row_sum_error = float(np.abs(probabilities.sum(axis=1) - 1).max()) if len(probabilities) else float("inf")
    clipped = np.clip(probabilities, EPS, 1 - EPS)
    clipped /= clipped.sum(axis=1, keepdims=True)
    y_pred = clipped.argmax(axis=1)
    matrix = confusion_matrix(y_true, y_pred, labels=CLASS_IDS)
    support = matrix.sum(axis=1)
    recalls = np.divide(np.diag(matrix), support, out=np.zeros(3), where=support > 0)
    precision, recall, _, _ = precision_recall_fscore_support(y_true, y_pred, labels=CLASS_IDS, zero_division=0)
    macro_f1 = float(f1_score(y_true, y_pred, labels=CLASS_IDS, average="macro", zero_division=0))
    balanced_accuracy = float(recalls.mean())
    mcc = float(matthews_corrcoef(y_true, y_pred)) if len(np.unique(y_true)) > 1 else 0.0
    kappa = float(cohen_kappa_score(y_true, y_pred, labels=CLASS_IDS)) if len(np.unique(y_true)) > 1 else 0.0
    gmean = float(np.prod(recalls) ** (1 / 3))
    ap_values = []
    for class_id in CLASS_IDS:
        if np.any(y_true == class_id):
            ap_values.append(average_precision_score((y_true == class_id).astype(int), clipped[:, class_id]))
    entropy = -(clipped * np.log(clipped)).sum(axis=1) / np.log(3)
    true_distribution = np.bincount(y_true, minlength=3)
    predicted_distribution = np.bincount(y_pred, minlength=3)
    s_nan = float(finite and row_sum_error <= 1e-4)
    s_maj_jsd = 1 - _jsd_base2(predicted_distribution, true_distribution)
    s_ent = 1 - min(abs(float(np.median(entropy)) - 0.5) / 0.5, 1.0)
    reference = true_distribution if train_class_counts is None else np.asarray(train_class_counts, dtype=float)
    s_drift = 1 - _jsd_base2(predicted_distribution, reference)
    s_eff_value = 1.0 if s_eff is None else float(s_eff)
    s_leak_value = 1.0 if s_leak is None else float(s_leak)
    sanity_parts = np.clip([s_nan, s_maj_jsd, s_ent, s_drift, s_eff_value, s_leak_value], COMPOSITE_EPS, 1)
    s_san_plus = float(np.prod(sanity_parts) ** (1 / 6))
    s_perf = float(np.prod(np.clip([macro_f1, balanced_accuracy, (mcc + 1) / 2, (kappa + 1) / 2], COMPOSITE_EPS, 1)) ** 0.25)
    acctempo = float((max(s_perf, COMPOSITE_EPS) ** 0.6) * (max(s_san_plus, COMPOSITE_EPS) ** 0.4))
    output: dict[str, Any] = {
        "n_eval_samples": int(len(y_true)), "ev_n_classes_present": int((support > 0).sum()),
        # Registered subgroup rule: n_g < 30 or any present-class support < 5.
        "small_subgroup_flag": bool(len(y_true) < 30 or int(support.min()) < 5), "confusion_matrix": matrix.tolist(),
        "probability_sum_max_abs_error": row_sum_error, "prediction_nan_inf_count": int((~np.isfinite(probabilities)).sum()),
        "macro_f1": macro_f1, "balanced_acc": balanced_accuracy, "mcc": mcc, "kappa": kappa,
        "gmean": gmean, "pr_auc_macro": float(np.mean(ap_values)) if ap_values else None,
        "log_loss": float(log_loss(y_true, clipped, labels=CLASS_IDS)),
        "brier": float(np.mean(np.sum((clipped - np.eye(3)[y_true]) ** 2, axis=1)),), "ece": _ece(y_true, clipped),
        "s_perf": s_perf, "s_nan": s_nan, "s_maj_jsd": s_maj_jsd, "s_ent": s_ent,
        "s_drift": s_drift, "s_eff": s_eff_value, "s_leak": s_leak_value,
        "s_san_plus": s_san_plus, "acctempo_m3": acctempo,
        "acctempo_alpha": 0.6, "acctempo_beta": 0.4, "acctempo_eps_floor": COMPOSITE_EPS,
    }
    output.update(_class_metrics(matrix, clipped, y_true))
    return output


def fit_missingness_probe(train_x: np.ndarray, train_y: np.ndarray, *, seed: int = 42):
    """Fit the registered TRAIN-only missingness/availability probe once."""
    if len(np.unique(train_y)) < 2:
        return None
    scaler = StandardScaler()
    train_scaled = scaler.fit_transform(train_x)
    model = LogisticRegression(C=1.0, max_iter=500, random_state=seed)
    model.fit(train_scaled, train_y)
    return scaler, model


def score_missingness_probe_auc(probe, eval_x: np.ndarray, eval_y: np.ndarray) -> float | None:
    """Score a frozen TRAIN-only probe on one validation/test slice."""
    from sklearn.metrics import roc_auc_score
    if probe is None or len(np.unique(eval_y)) < 2:
        return None
    scaler, model = probe
    eval_scaled = scaler.transform(eval_x)
    probabilities = model.predict_proba(eval_scaled)
    try:
        return float(roc_auc_score(eval_y, probabilities, multi_class="ovr", average="macro", labels=CLASS_IDS))
    except ValueError:
        return None


def missingness_probe_auc(train_x: np.ndarray, train_y: np.ndarray, eval_x: np.ndarray, eval_y: np.ndarray,
                          *, seed: int = 42) -> float | None:
    """Backward-compatible one-shot wrapper for callers outside sanity."""
    return score_missingness_probe_auc(fit_missingness_probe(train_x, train_y, seed=seed), eval_x, eval_y)


def s_leak_from_probe(auc: float | None) -> float | None:
    return None if auc is None else float(1 - 2 * max(auc - 0.5, 0))


def paired_bootstrap_delta(before_probabilities: np.ndarray, after_probabilities: np.ndarray, y_true: np.ndarray,
                           metric: Callable[[np.ndarray, np.ndarray], float], *, n_boot: int = 2000,
                           seed: int = 20260922, groups: np.ndarray | None = None) -> dict[str, float]:
    """Paired enrollment bootstrap; pass groups for offering-cluster sensitivity."""
    rng = np.random.default_rng(seed)
    y_true = np.asarray(y_true)
    units = np.arange(len(y_true)) if groups is None else np.unique(groups)
    deltas = np.empty(n_boot, dtype=float)
    for index in range(n_boot):
        sampled = rng.choice(units, size=len(units), replace=True)
        rows = sampled if groups is None else np.concatenate([np.flatnonzero(groups == unit) for unit in sampled])
        deltas[index] = metric(y_true[rows], after_probabilities[rows]) - metric(y_true[rows], before_probabilities[rows])
    return {"delta_ci_low": float(np.quantile(deltas, .025)), "delta_ci_high": float(np.quantile(deltas, .975)),
            "delta_p_boot_le0": float((deltas <= 0).mean()), "delta_n_boot": n_boot,
            "delta_boot_unit": "ENROLLMENT" if groups is None else "OFFERING"}
