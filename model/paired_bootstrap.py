"""Paired prediction bootstrap used only for registered LO W2/W3 comparisons."""
from __future__ import annotations

import numpy as np
from sklearn.metrics import f1_score


def paired_bootstrap_macro_f1_delta(y_true: np.ndarray, y_pred_reference: np.ndarray,
                                    y_pred_candidate: np.ndarray, labels: np.ndarray, *,
                                    repetitions: int = 2000, seed: int = 42,
                                    alpha: float = .05) -> dict:
    """Return candidate-minus-reference paired bootstrap delta and 95% CI.

    The caller must first enforce exact row alignment by ``enrollment_id_hash``
    and require the same ``y_true`` vector.  Resampling row indices jointly is
    what makes this a paired, rather than independent, bootstrap.
    """
    y_true = np.asarray(y_true)
    y_pred_reference = np.asarray(y_pred_reference)
    y_pred_candidate = np.asarray(y_pred_candidate)
    if not (len(y_true) == len(y_pred_reference) == len(y_pred_candidate)):
        raise ValueError("Paired bootstrap requires equal-length prediction vectors.")
    if len(y_true) == 0:
        raise ValueError("Paired bootstrap requires at least one row.")
    rng = np.random.default_rng(seed)
    observed = float(f1_score(y_true, y_pred_candidate, labels=labels, average="macro", zero_division=0)
                     - f1_score(y_true, y_pred_reference, labels=labels, average="macro", zero_division=0))
    deltas = np.empty(repetitions, dtype=float)
    for draw in range(repetitions):
        index = rng.integers(0, len(y_true), size=len(y_true))
        deltas[draw] = (f1_score(y_true[index], y_pred_candidate[index], labels=labels, average="macro", zero_division=0)
                        - f1_score(y_true[index], y_pred_reference[index], labels=labels, average="macro", zero_division=0))
    lower, upper = np.quantile(deltas, [alpha / 2, 1 - alpha / 2])
    # Directional mass around zero, reported descriptively rather than as a
    # model-selection criterion. Selection remains validation-only.
    sign_probability = min(float((deltas <= 0).mean()), float((deltas >= 0).mean())) * 2
    return {
        "metric_name": "macro_f1", "delta_definition": "candidate_minus_reference",
        "estimate": observed, "ci_lower": float(lower), "ci_upper": float(upper),
        "bootstrap_repetitions": int(repetitions), "bootstrap_seed": int(seed),
        "ci_level": float(1 - alpha), "two_sided_sign_probability": min(sign_probability, 1.0),
        "paired_unit": "aligned_enrollment_id_hash_rows",
    }
