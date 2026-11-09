# -*- coding: utf-8 -*-
"""Selection metrics of the probe (macro-F1 over the fixed class ids, mean cross-entropy).

They only drive checkpoint selection. Exported metrics of a run come from the team's
``metrics_core.evaluation.classification_metrics`` applied to the predictions, as for tiers F1 and F2.
"""
from __future__ import annotations

import numpy as np


def macro_f1(y_true: np.ndarray, y_pred: np.ndarray, num_classes: int) -> float:
    """Macro-F1 over labels 0..num_classes-1; a class with no support and no prediction scores 0 (zero_division=0)."""
    y_true = np.asarray(y_true, dtype=np.int64)
    y_pred = np.asarray(y_pred, dtype=np.int64)
    scores = []
    for c in range(num_classes):
        tp = int(np.sum((y_true == c) & (y_pred == c)))
        fp = int(np.sum((y_true != c) & (y_pred == c)))
        fn = int(np.sum((y_true == c) & (y_pred != c)))
        denom = 2 * tp + fp + fn
        scores.append(0.0 if denom == 0 else 2.0 * tp / denom)
    return float(np.mean(scores))


def cross_entropy_from_logits(logits: np.ndarray, y_true: np.ndarray) -> float:
    logits = np.asarray(logits, dtype=np.float64)
    shifted = logits - logits.max(axis=1, keepdims=True)
    log_norm = np.log(np.exp(shifted).sum(axis=1))
    picked = shifted[np.arange(len(y_true)), np.asarray(y_true, dtype=np.int64)]
    return float(np.mean(log_norm - picked))
