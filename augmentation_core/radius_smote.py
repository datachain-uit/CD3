"""TEMPO-compatible Radius-SMOTE: interpolate inside minority radius neighborhoods."""
from __future__ import annotations

import numpy as np
from sklearn.neighbors import NearestNeighbors

from .cdsmote import _merge
from .contracts import (DEFAULT_IR_TARGET, DEFAULT_MAX_EXPANSION_PER_CLASS,
                        SAMPLING_STRATEGY_ID, SyntheticBatch, generation_plan,
                        validate_train_matrix)


class RadiusSMOTE:
    method = "RADIUS_SMOTE"

    def __init__(self, radius: float = 0.092, random_state: int = 20260922,
                 ir_target: int = DEFAULT_IR_TARGET,
                 max_expansion_per_class: int = DEFAULT_MAX_EXPANSION_PER_CLASS):
        self.radius = radius
        self.random_state = random_state
        self.ir_target = ir_target
        self.max_expansion_per_class = max_expansion_per_class
        self.sampling_strategy_id = SAMPLING_STRATEGY_ID
        self.plan: dict[str, object] = {}
        self.audit: dict[str, object] = {}

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
        fallback_total = generated_total = 0
        for label, count in counts.items():
            n_generate = to_generate[label]
            if label == majority or n_generate <= 0:
                continue
            group = np.flatnonzero(labels == label)
            if len(group) < 2:
                raise ValueError(
                    f"IR10_K10 requires {n_generate} synthetic rows for class {label!r}, "
                    "but fewer than two real TRAIN rows are available."
                )
            local_values = values[group]
            within = NearestNeighbors(radius=self.radius, algorithm="ball_tree").fit(local_values).radius_neighbors(local_values, return_distance=False)
            fallback = NearestNeighbors(n_neighbors=2, algorithm="ball_tree").fit(local_values).kneighbors(local_values, return_distance=False)[:, 1]
            local_a = rng.integers(0, len(group), size=n_generate)
            local_b = np.empty(len(local_a), dtype=int)
            for i, source in enumerate(local_a):
                candidates = within[source][within[source] != source]
                if len(candidates):
                    local_b[i] = rng.choice(candidates)
                else:
                    local_b[i] = fallback[source]
                    fallback_total += 1
                generated_total += 1
            a, b = group[local_a], group[local_b]
            alpha = rng.random(len(a), dtype=np.float32)
            batches.append(SyntheticBatch(values=values[a] + alpha[:, None] * (values[b] - values[a]),
                                          labels=np.full(len(a), label), parent_a=a, parent_b=b,
                                          alpha=alpha, method=self.method))
        self.audit = {
            "radius": self.radius,
            "radius_space": "scaled_numeric_model_input",
            "fallback_nearest_neighbour_rows": fallback_total,
            "fallback_nearest_neighbour_rate": fallback_total / generated_total if generated_total else 0.0,
        }
        return _merge(batches, values.shape[1], labels.dtype, self.method)
