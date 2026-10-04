"""TEMPO-compatible Radius-SMOTE: interpolate inside minority radius neighborhoods."""
from __future__ import annotations

import numpy as np
from sklearn.neighbors import NearestNeighbors

from .cdsmote import _merge
from .contracts import SyntheticBatch, minority_targets, validate_train_matrix


class RadiusSMOTE:
    method = "RADIUS_SMOTE"

    def __init__(self, radius: float = 0.092, random_state: int = 20260922):
        self.radius = radius
        self.random_state = random_state

    def fit_resample(self, x, y) -> SyntheticBatch:
        values, labels = validate_train_matrix(x, y)
        rng = np.random.default_rng(self.random_state)
        majority, majority_count, counts = minority_targets(labels)
        batches: list[SyntheticBatch] = []
        for label, count in counts.items():
            if label == majority or count >= majority_count:
                continue
            group = np.flatnonzero(labels == label)
            if len(group) < 2:
                continue
            local_values = values[group]
            within = NearestNeighbors(radius=self.radius, algorithm="ball_tree").fit(local_values).radius_neighbors(local_values, return_distance=False)
            fallback = NearestNeighbors(n_neighbors=2, algorithm="ball_tree").fit(local_values).kneighbors(local_values, return_distance=False)[:, 1]
            local_a = rng.integers(0, len(group), size=majority_count - count)
            local_b = np.empty(len(local_a), dtype=int)
            for i, source in enumerate(local_a):
                candidates = within[source][within[source] != source]
                local_b[i] = rng.choice(candidates) if len(candidates) else fallback[source]
            a, b = group[local_a], group[local_b]
            alpha = rng.random(len(a), dtype=np.float32)
            batches.append(SyntheticBatch(values=values[a] + alpha[:, None] * (values[b] - values[a]),
                                          labels=np.full(len(a), label), parent_a=a, parent_b=b,
                                          alpha=alpha, method=self.method))
        return _merge(batches, values.shape[1], labels.dtype, self.method)
