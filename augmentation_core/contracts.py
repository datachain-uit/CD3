"""Shared data contracts for the three TEMPO-compatible balancers."""
from __future__ import annotations

from dataclasses import dataclass
from math import ceil

import numpy as np


# Registered primary policy: the majority class is never undersampled.  A
# minority class may approach an imbalance ratio of 10:1, but may never grow
# beyond ten times its observed TRAIN support.
SAMPLING_STRATEGY_ID = "IR10_K10"
DEFAULT_IR_TARGET = 10
DEFAULT_MAX_EXPANSION_PER_CLASS = 10


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


def sampling_targets(count_by_class: dict[object, int], *, ir_target: int = DEFAULT_IR_TARGET,
                     max_expansion_per_class: int = DEFAULT_MAX_EXPANSION_PER_CLASS) -> dict[object, int]:
    """Return registered IR-target-with-cap post-balance counts per class."""
    if not count_by_class:
        raise ValueError("count_by_class must not be empty")
    if ir_target < 1 or max_expansion_per_class < 1:
        raise ValueError("ir_target and max_expansion_per_class must be >= 1")
    n_max = max(int(count) for count in count_by_class.values())
    return {
        label: int(min(max(int(count), ceil(n_max / ir_target)),
                         max_expansion_per_class * int(count)))
        for label, count in count_by_class.items()
    }


def generation_plan(y: np.ndarray, *, ir_target: int = DEFAULT_IR_TARGET,
                    max_expansion_per_class: int = DEFAULT_MAX_EXPANSION_PER_CLASS) -> tuple[object, dict[object, int], dict[object, int]]:
    """Return majority label, observed counts, and exact synthetic counts."""
    majority, _, counts = minority_targets(y)
    targets = sampling_targets(counts, ir_target=ir_target,
                               max_expansion_per_class=max_expansion_per_class)
    return majority, counts, {label: max(targets[label] - counts[label], 0) for label in counts}


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
