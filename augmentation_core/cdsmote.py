"""TEMPO-compatible CD-SMOTE: interpolate inside minority K-Means clusters."""
from __future__ import annotations

import numpy as np
from sklearn.cluster import KMeans
from sklearn.neighbors import NearestNeighbors

from .contracts import (DEFAULT_IR_TARGET, DEFAULT_MAX_EXPANSION_PER_CLASS,
                        SAMPLING_STRATEGY_ID, SyntheticBatch, allocate,
                        generation_plan, validate_train_matrix)


class CDSmote:
    """Cluster-decomposition SMOTE from TEMPO CQ, generalized to CQ and LO.

    Each minority label is clustered independently. Interpolation only occurs
    between members of one minority cluster, never through majority geometry.
    """

    method = "CDSMOTE"

    def __init__(self, n_clusters: int = 5, random_state: int = 20260922,
                 ir_target: int = DEFAULT_IR_TARGET,
                 max_expansion_per_class: int = DEFAULT_MAX_EXPANSION_PER_CLASS):
        self.n_clusters = n_clusters
        self.random_state = random_state
        self.ir_target = ir_target
        self.max_expansion_per_class = max_expansion_per_class
        self.sampling_strategy_id = SAMPLING_STRATEGY_ID
        self.plan: dict[str, object] = {}

    def fit_resample(self, x, y) -> SyntheticBatch:
        values, labels = validate_train_matrix(x, y)
        rng = np.random.default_rng(self.random_state)
        majority, counts, to_generate = generation_plan(
            labels, ir_target=self.ir_target,
            max_expansion_per_class=self.max_expansion_per_class,
        )
        self.plan = {
            "sampling_strategy_id": self.sampling_strategy_id,
            "ir_target": self.ir_target,
            "max_expansion_per_class": self.max_expansion_per_class,
            "class_counts_before": {str(key): int(value) for key, value in counts.items()},
            "synthetic_target_per_class": {str(key): int(value) for key, value in to_generate.items()},
        }
        batches: list[SyntheticBatch] = []
        for label, count in counts.items():
            n_generate = to_generate[label]
            if label == majority or n_generate <= 0:
                continue
            global_idx = np.flatnonzero(labels == label)
            if len(global_idx) < 2:
                raise ValueError(
                    f"IR10_K10 requires {n_generate} synthetic rows for class {label!r}, "
                    "but fewer than two real TRAIN rows are available."
                )
            n_clusters = min(self.n_clusters, max(1, len(global_idx) // 2))
            cluster_id = KMeans(n_clusters=n_clusters, n_init=10, random_state=self.random_state).fit_predict(values[global_idx])
            members = [global_idx[cluster_id == cluster] for cluster in range(n_clusters)]
            viable = [group for group in members if len(group) >= 2]
            if not viable:
                viable = [global_idx]
            quotas = allocate(n_generate, np.asarray([len(group) for group in viable]))
            parent_a, parent_b = [], []
            for group, quota in zip(viable, quotas):
                if quota == 0:
                    continue
                left = rng.choice(group, size=quota, replace=True)
                right = rng.choice(group, size=quota, replace=True)
                same = left == right
                if same.any():
                    nn = NearestNeighbors(n_neighbors=2).fit(values[group])
                    local = np.searchsorted(group, left[same])
                    right[same] = group[nn.kneighbors(values[left[same]], return_distance=False)[:, 1]]
                parent_a.append(left)
                parent_b.append(right)
            a, b = np.concatenate(parent_a), np.concatenate(parent_b)
            alpha = rng.random(len(a), dtype=np.float32)
            batches.append(SyntheticBatch(values=values[a] + alpha[:, None] * (values[b] - values[a]),
                                          labels=np.full(len(a), label), parent_a=a, parent_b=b,
                                          alpha=alpha, method=self.method))
        return _merge(batches, values.shape[1], labels.dtype, self.method)


def _merge(batches, n_features, label_dtype, method):
    if not batches:
        return SyntheticBatch(np.empty((0, n_features), dtype=np.float32), np.empty(0, dtype=label_dtype),
                              np.empty(0, dtype=int), np.empty(0, dtype=int), np.empty(0, dtype=np.float32), method)
    return SyntheticBatch(np.vstack([b.values for b in batches]), np.concatenate([b.labels for b in batches]),
                          np.concatenate([b.parent_a for b in batches]), np.concatenate([b.parent_b for b in batches]),
                          np.concatenate([b.alpha for b in batches]), method)
