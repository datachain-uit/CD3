"""Shared data contracts for the three TEMPO-compatible balancers."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class SyntheticBatch:
    """Synthetic numeric vectors plus auditable parent lineage.

    ``parent_a`` and ``parent_b`` are row positions in the input TRAIN view.
    The caller is responsible for using the same phase in one invocation.
    """

    values: np.ndarray
    labels: np.ndarray
    parent_a: np.ndarray
    parent_b: np.ndarray
    alpha: np.ndarray
    method: str


def validate_train_matrix(x, y) -> tuple[np.ndarray, np.ndarray]:
    values = np.asarray(x, dtype=np.float32)
    labels = np.asarray(y)
    if values.ndim != 2 or len(values) != len(labels):
        raise ValueError("x must be a 2-D matrix with one label per row")
    if len(values) == 0:
        raise ValueError("cannot balance an empty TRAIN view")
    if not np.isfinite(values).all():
        raise ValueError("balancing requires finite post-imputation numeric values")
    return values, labels


def minority_targets(y: np.ndarray) -> tuple[object, int, dict[object, int]]:
    classes, counts = np.unique(y, return_counts=True)
    count_by_class = dict(zip(classes.tolist(), counts.tolist()))
    majority = classes[int(np.argmax(counts))]
    return majority, int(counts.max()), count_by_class


def allocate(total: int, weights: np.ndarray) -> np.ndarray:
    """Allocate exactly ``total`` items proportionally with deterministic remainder."""
    if total <= 0:
        return np.zeros(len(weights), dtype=int)
    raw = total * weights / weights.sum()
    result = np.floor(raw).astype(int)
    remainder = total - int(result.sum())
    if remainder:
        order = np.argsort(-(raw - result), kind="stable")
        result[order[:remainder]] += 1
    return result


def synthetic_available_mask(available_mask: np.ndarray, parent_a: np.ndarray,
                             parent_b: np.ndarray) -> np.ndarray:
    """Required synthetic mask rule: INTERSECTION_OF_PARENTS."""
    source = np.asarray(available_mask, dtype=bool)
    return np.logical_and(source[parent_a], source[parent_b]).astype("int8")


def synthetic_missing_mask(missing_mask: np.ndarray, parent_a: np.ndarray,
                           parent_b: np.ndarray) -> np.ndarray:
    """A value is marked missing if either parent value was missing originally."""
    source = np.asarray(missing_mask, dtype=bool)
    return np.logical_or(source[parent_a], source[parent_b]).astype("int8")
