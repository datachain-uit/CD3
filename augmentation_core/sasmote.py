"""Scalable multiclass Self-Inspected Adaptive SMOTE (SASMOTE).

This implements the two defining operations from Kosolwattana et al. (2023):
visible-neighbour selection followed by random-forest self-inspection. The
paper describes a binary problem; ``SASmote`` applies it one-vs-rest for every
minority label. Inspector training is bounded and recorded in ``audit`` because
a literal one-inspector-per-majority-partition construction would require tens
to hundreds of forests on the CQ/LO training sets.
"""
from __future__ import annotations

from math import ceil

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.neighbors import NearestNeighbors

from .cdsmote import _merge
from .contracts import (DEFAULT_IR_TARGET, DEFAULT_MAX_EXPANSION_PER_CLASS,
                        SAMPLING_STRATEGY_ID, SyntheticBatch, generation_plan,
                        validate_train_matrix)


class SASmote:
    """Self-Inspected Adaptive SMOTE, generalized to multiclass data.

    Synthetic candidates interpolate only between a minority point and one of
    its *visible* minority neighbours. For target class ``c``, inspectors
    distinguish ``c`` from all other labels; a candidate is retained only when
    no more than ``uncertainty_threshold`` inspectors predict non-``c``.
    """

    method = "SASMOTE"
    algorithm = "SASMOTE_self_inspected_adaptive_v1"

    def __init__(
        self,
        visible_k: int = 16,
        max_inspectors: int = 4,
        inspector_trees: int = 16,
        inspector_n_jobs: int = 8,
        uncertainty_threshold: float = 0.5,
        candidate_batch_size: int = 262_144,
        max_candidate_rounds: int = 32,
        random_state: int = 20260922,
        ir_target: int = DEFAULT_IR_TARGET,
        max_expansion_per_class: int = DEFAULT_MAX_EXPANSION_PER_CLASS,
    ):
        if visible_k < 1 or max_inspectors < 1 or inspector_trees < 1 or inspector_n_jobs < 1:
            raise ValueError("visible_k, max_inspectors, inspector_trees, and inspector_n_jobs must be positive")
        if not 0.0 <= uncertainty_threshold <= 1.0:
            raise ValueError("uncertainty_threshold must be in [0, 1]")
        self.visible_k = visible_k
        self.max_inspectors = max_inspectors
        self.inspector_trees = inspector_trees
        self.inspector_n_jobs = inspector_n_jobs
        self.uncertainty_threshold = uncertainty_threshold
        self.candidate_batch_size = candidate_batch_size
        self.max_candidate_rounds = max_candidate_rounds
        self.random_state = random_state
        self.ir_target = ir_target
        self.max_expansion_per_class = max_expansion_per_class
        self.sampling_strategy_id = SAMPLING_STRATEGY_ID
        self.plan: dict[str, object] = {}
        self.audit: dict[str, object] = {}
        self._acceptance: dict[str, dict[str, float | int]] = {}

    @staticmethod
    def _visible_neighbour_positions(values: np.ndarray, k: int) -> list[np.ndarray]:
        """Return visible neighbours under Eq. (1) of the SASMOTE paper.

        ``y`` is visible from ``x`` iff every other KNN point ``z`` satisfies
        ``<x-z, y-z> >= 0``. Empty sets fall back to the closest KNN, so every
        minority point can still contribute a candidate.
        """
        if len(values) < 2:
            return [np.empty(0, dtype=np.int64) for _ in range(len(values))]
        # sklearn excludes the query point when ``X=None``.  Therefore the
        # requested count must be at most n_samples-1 and is already the
        # desired number of other neighbours.
        n_neighbors = min(k, len(values) - 1)
        nearest = NearestNeighbors(n_neighbors=n_neighbors, algorithm="brute", n_jobs=-1)
        neighbours = nearest.fit(values).kneighbors(return_distance=False)
        result: list[np.ndarray] = []
        for index, row in enumerate(neighbours):
            row = row[row != index]
            if len(row) == 0:
                result.append(np.empty(0, dtype=np.int64))
                continue
            points = values[row]
            z = points[None, :, :]
            candidate = points[:, None, :]
            dot = ((values[index] - z) * (candidate - z)).sum(axis=2)
            visible = row[np.all(dot >= -1e-6, axis=1)]
            result.append(visible if len(visible) else row[:1])
        return result

    def _inspectors(self, values: np.ndarray, positive: np.ndarray, negative: np.ndarray,
                    rng: np.random.Generator) -> tuple[list[RandomForestClassifier], dict[str, object]]:
        """Train bounded balanced one-vs-rest RF inspectors.

        The original binary paper partitions all majority rows into balanced
        groups. On these multi-million-row datasets that can imply O(100)
        forests per target. We retain the method's balanced-inspector rule, but
        cap the count and record the majority coverage explicitly.
        """
        requested = ceil(len(negative) / len(positive))
        n_inspectors = min(requested, self.max_inspectors)
        models: list[RandomForestClassifier] = []
        used_negative: set[int] = set()
        for ordinal in range(n_inspectors):
            selected_negative = rng.choice(negative, size=len(positive), replace=False)
            used_negative.update(selected_negative.tolist())
            indices = np.concatenate([positive, selected_negative])
            labels = np.concatenate([np.ones(len(positive), dtype=np.int8), np.zeros(len(positive), dtype=np.int8)])
            model = RandomForestClassifier(
                n_estimators=self.inspector_trees,
                min_samples_leaf=2,
                max_features="sqrt",
                n_jobs=self.inspector_n_jobs,
                random_state=self.random_state + ordinal,
            )
            model.fit(values[indices], labels)
            models.append(model)
        return models, {
            "inspectors_requested_by_paper_partition": requested,
            "inspectors_fitted": n_inspectors,
            "inspector_cap_applied": requested > n_inspectors,
            "majority_rows_seen_by_inspectors": len(used_negative),
            "majority_coverage": len(used_negative) / len(negative),
        }

    def _accepted_candidates(self, values: np.ndarray, minority: np.ndarray,
                             visible: list[np.ndarray], inspectors: list[RandomForestClassifier],
                             label: object, n_needed: int, rng: np.random.Generator) -> SyntheticBatch:
        accepted_values, accepted_a, accepted_b, accepted_alpha = [], [], [], []
        remaining = n_needed
        generated = accepted = 0
        for _ in range(self.max_candidate_rounds):
            if remaining <= 0:
                break
            n_candidates = min(self.candidate_batch_size, max(remaining * 2, 4096))
            local_a = rng.integers(0, len(minority), size=n_candidates)
            local_b = np.fromiter(
                (rng.choice(visible[position]) for position in local_a), dtype=np.int64, count=n_candidates
            )
            a, b = minority[local_a], minority[local_b]
            alpha = rng.random(n_candidates, dtype=np.float32)
            candidates = values[a] + alpha[:, None] * (values[b] - values[a])
            non_target_votes = np.zeros(n_candidates, dtype=np.int16)
            for inspector in inspectors:
                non_target_votes += inspector.predict(candidates) == 0
            keep = (non_target_votes / len(inspectors)) <= self.uncertainty_threshold
            keep_indices = np.flatnonzero(keep)[:remaining]
            if len(keep_indices):
                accepted_values.append(candidates[keep_indices])
                accepted_a.append(a[keep_indices])
                accepted_b.append(b[keep_indices])
                accepted_alpha.append(alpha[keep_indices])
                accepted += len(keep_indices)
                remaining -= len(keep_indices)
            generated += n_candidates
            print(
                f"[SASMOTE] label={label} candidates={generated} accepted={accepted} remaining={remaining}",
                flush=True,
            )
        if remaining:
            raise RuntimeError(
                f"SASMOTE could not obtain {n_needed} accepted samples for label {label!r}; "
                f"accepted={accepted}, generated={generated}. Increase max_candidate_rounds or relax threshold."
            )
        self._acceptance[str(label)] = {
            "candidates_generated": int(generated),
            "candidates_accepted": int(accepted),
            "candidate_acceptance_rate": float(accepted / generated),
        }
        return SyntheticBatch(
            values=np.vstack(accepted_values), labels=np.full(n_needed, label),
            parent_a=np.concatenate(accepted_a), parent_b=np.concatenate(accepted_b),
            alpha=np.concatenate(accepted_alpha), method=self.method,
        )

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
        audit_labels: dict[str, object] = {}
        for label, count in counts.items():
            n_generate = to_generate[label]
            if label == majority or n_generate <= 0:
                continue
            minority = np.flatnonzero(labels == label)
            non_target = np.flatnonzero(labels != label)
            if len(minority) < 2:
                raise ValueError(
                    f"IR10_K10 requires {n_generate} synthetic rows for class {label!r}, "
                    "but fewer than two real TRAIN rows are available."
                )
            print(f"[SASMOTE] label={label} stage=visible_neighbour_search rows={len(minority)}", flush=True)
            visible = self._visible_neighbour_positions(values[minority], self.visible_k)
            print(f"[SASMOTE] label={label} stage=inspector_fit", flush=True)
            inspectors, inspector_audit = self._inspectors(values, minority, non_target, rng)
            print(f"[SASMOTE] label={label} stage=candidate_generation target={n_generate}", flush=True)
            batches.append(self._accepted_candidates(values, minority, visible, inspectors, label, n_generate, rng))
            visible_counts = np.asarray([len(item) for item in visible], dtype=float)
            audit_labels[str(label)] = {
                "minority_rows": int(len(minority)), "non_target_rows": int(len(non_target)),
                "synthetic_target": int(n_generate), "visible_k": int(min(self.visible_k, len(minority) - 1)),
                "visible_neighbours_mean": float(visible_counts.mean()),
                "visible_neighbours_min": int(visible_counts.min()), **inspector_audit,
                **self._acceptance[str(label)],
            }
        self.audit = {
            "algorithm": self.algorithm,
            "sampling_strategy": self.plan,
            "paper": "Kosolwattana_et_al_2023_doi:10.1186/s13040-023-00330-4",
            "multiclass_strategy": "one_vs_rest_per_minority_label",
            "visible_k_requested": self.visible_k,
            "uncertainty_threshold": self.uncertainty_threshold,
            "inspector_trees": self.inspector_trees,
            "inspector_n_jobs": self.inspector_n_jobs,
            "max_inspectors": self.max_inspectors,
            "candidate_batch_size": self.candidate_batch_size,
            "labels": audit_labels,
        }
        return _merge(batches, values.shape[1], labels.dtype, self.method)
