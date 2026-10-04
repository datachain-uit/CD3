"""Classification metrics required for model-level L2/L3 facts."""
from __future__ import annotations

import numpy as np
from sklearn.metrics import (accuracy_score, balanced_accuracy_score, cohen_kappa_score,
                             confusion_matrix, f1_score, matthews_corrcoef,
                             average_precision_score, log_loss, precision_recall_fscore_support,
                             recall_score, roc_auc_score)


def geometric_mean_recall(y_true: np.ndarray, y_pred: np.ndarray, labels: np.ndarray) -> float:
    """Geometric mean of per-class recalls; zero for an entirely missed class."""
    recalls = recall_score(y_true, y_pred, labels=labels, average=None, zero_division=0)
    return float(np.prod(recalls) ** (1.0 / len(recalls))) if len(recalls) else float("nan")


def classification_metrics(y_true: np.ndarray, y_pred: np.ndarray, probabilities: np.ndarray,
                           labels: np.ndarray) -> tuple[dict, np.ndarray]:
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, zero_division=0,
    )
    result = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "f1_macro": float(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)),
        "f1_weighted": float(f1_score(y_true, y_pred, labels=labels, average="weighted", zero_division=0)),
        "gmean_recall": geometric_mean_recall(y_true, y_pred, labels),
        "mcc": float(matthews_corrcoef(y_true, y_pred)),
        "cohen_kappa": float(cohen_kappa_score(y_true, y_pred)),
        "n_rows": int(len(y_true)),
        "per_class_precision": precision.tolist(),
        "per_class_recall": recall.tolist(),
        "per_class_f1": f1.tolist(),
        "per_class_support": support.astype(int).tolist(),
    }
    present = np.unique(y_true)
    if len(present) >= 2:
        result["pr_auc_macro"] = float(np.mean([
            average_precision_score((y_true == label).astype(int), probabilities[:, label])
            for label in labels if np.any(y_true == label)
        ]))
        result["roc_auc_macro_ovr"] = float(np.mean([
            roc_auc_score((y_true == label).astype(int), probabilities[:, label])
            for label in labels if np.any(y_true == label) and np.any(y_true != label)
        ]))
    else:
        result["pr_auc_macro"] = None
        result["roc_auc_macro_ovr"] = None
    return result, confusion_matrix(y_true, y_pred, labels=labels)


def per_class_metric_records(y_true: np.ndarray, y_pred: np.ndarray, labels: np.ndarray,
                             class_codes: tuple[str, ...], probabilities: np.ndarray | None = None,
                             small_support_threshold: int = 400) -> list[dict]:
    """Return normalized per-class facts, including the registered support flag."""
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, zero_division=0,
    )
    matrix = confusion_matrix(y_true, y_pred, labels=labels)
    rows = []
    for index in range(len(labels)):
        tp = int(matrix[index, index]); fp = int(matrix[:, index].sum() - tp)
        fn = int(matrix[index, :].sum() - tp); tn = int(matrix.sum() - tp - fp - fn)
        class_absent = int(support[index] == 0)
        specificity = None if tn + fp == 0 else float(tn / (tn + fp))
        recall_value = None if class_absent else float(recall[index])
        ap = None
        if probabilities is not None and not class_absent:
            ap = float(average_precision_score((y_true == labels[index]).astype(int), probabilities[:, index]))
        rows.append({
            "class_index": int(index), "class_code": class_codes[index],
            "n_support": int(support[index]), "n_predicted": int(tp + fp),
            "class_status": "CLASS_ABSENT" if class_absent else "PRESENT",
            "small_support_threshold": int(small_support_threshold),
            "small_support_flag": int(support[index] < small_support_threshold),
            "precision": None if tp + fp == 0 else float(precision[index]),
            "recall": recall_value, "specificity": specificity,
            "f1": None if class_absent else float(f1[index]),
            "gmean": None if recall_value is None or specificity is None else float(np.sqrt(recall_value * specificity)),
            "average_precision": ap,
        })
    return rows


def stratified_bootstrap_per_class_ci(y_true: np.ndarray, y_pred: np.ndarray, labels: np.ndarray,
                                      class_codes: tuple[str, ...], *, repetitions: int = 2000,
                                      seed: int = 42, alpha: float = .05,
                                      small_support_threshold: int = 400) -> list[dict]:
    """CI for every present class using efficient stratified bootstrap.

    Each true-class stratum is resampled with replacement at its original
    size. For a target class, TP and each source-class FP count are binomial
    draws, which is equivalent to materializing every resample but avoids
    copying potentially millions of prediction rows 2,000 times.
    """
    rng = np.random.default_rng(seed)
    output: list[dict] = []
    for index, label in enumerate(labels):
        target = y_true == label
        support = int(target.sum())
        if support == 0:
            continue
        tp_probability = float((y_pred[target] == label).mean())
        tp = rng.binomial(support, tp_probability, size=repetitions)
        fp = np.zeros(repetitions, dtype=np.int64)
        for other in labels:
            if other == label:
                continue
            source = y_true == other
            source_count = int(source.sum())
            if source_count:
                fp += rng.binomial(source_count, float((y_pred[source] == label).mean()), size=repetitions)
        fn = support - tp
        denom_precision = tp + fp
        precision = np.divide(tp, denom_precision, out=np.zeros(repetitions, dtype=float), where=denom_precision > 0)
        recall = tp / support
        denom_f1 = 2 * tp + fp + fn
        f1 = np.divide(2 * tp, denom_f1, out=np.zeros(repetitions, dtype=float), where=denom_f1 > 0)
        low, high = alpha / 2, 1 - alpha / 2
        for metric_name, samples in (("precision", precision), ("recall", recall), ("f1", f1)):
            output.append({
                "class_index": int(index), "class_code": class_codes[index],
                "n_support": support, "small_support_threshold": int(small_support_threshold),
                "small_support_flag": int(support < small_support_threshold),
                "bootstrap_method": "stratified_binomial_equivalent_v1",
                "bootstrap_repetitions": int(repetitions), "ci_level": float(1 - alpha),
                "metric_name": metric_name, "estimate": float(samples.mean()),
                "ci_lower": float(np.quantile(samples, low)), "ci_upper": float(np.quantile(samples, high)),
                "bootstrap_seed": int(seed),
            })
    return output


def calibration_metrics(y_true: np.ndarray, probabilities: np.ndarray, labels: np.ndarray,
                        bins: int = 15) -> dict:
    """Multiclass NLL, Brier score and top-label ECE, with stable semantics."""
    clipped = np.clip(probabilities, 1e-7, 1.0 - 1e-7)
    clipped /= clipped.sum(axis=1, keepdims=True)
    one_hot = np.eye(len(labels), dtype=np.float64)[y_true]
    confidence = clipped.max(axis=1)
    correct = (clipped.argmax(axis=1) == y_true).astype(np.float64)
    ece = 0.0
    for lower in np.linspace(0.0, 1.0, bins, endpoint=False):
        upper = lower + 1.0 / bins
        in_bin = (confidence >= lower) & ((confidence < upper) if upper < 1 else (confidence <= upper))
        if in_bin.any():
            ece += float(in_bin.mean() * abs(correct[in_bin].mean() - confidence[in_bin].mean()))
    return {
        "multiclass_nll": float(log_loss(y_true, clipped, labels=labels)),
        "multiclass_brier": float(np.mean(np.sum((clipped - one_hot) ** 2, axis=1))),
        "top_label_ece_15": float(ece),
        "calibration_bins": bins,
    }
