"""TEMPO-compatible CD-SMOTE: interpolate inside minority K-Means clusters."""
from __future__ import annotations

import numpy as np
from sklearn.cluster import KMeans
from sklearn.neighbors import NearestNeighbors

from .contracts import SyntheticBatch, allocate, minority_targets, validate_train_matrix


class CDSmote:
    """Cluster-decomposition SMOTE from TEMPO CQ, generalized to CQ and LO.

    Each minority label is clustered independently. Interpolation only occurs
    between members of one minority cluster, never through majority geometry.
    """

    method = "CDSMOTE"

    def __init__(self, n_clusters: int = 5, random_state: int = 20260922):
        self.n_clusters = n_clusters
        self.random_state = random_state

    def fit_resample(self, x, y) -> SyntheticBatch:
        values, labels = validate_train_matrix(x, y)
        rng = np.random.default_rng(self.random_state)
        majority, majority_count, counts = minority_targets(labels)
        batches: list[SyntheticBatch] = []
        for label, count in counts.items():
            if label == majority or count >= majority_count:
                continue
            global_idx = np.flatnonzero(labels == label)
            n_generate = majority_count - count
            if len(global_idx) < 2:
                continue
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
