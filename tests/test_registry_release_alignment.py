"""Regression tests for registry/release identity and subgroup support rules."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for extra in (ROOT, ROOT / "LO"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import registries  # noqa: E402
from metrics_core.evaluation import classification_metrics  # noqa: E402
from release_core.contracts import RELEASE_SPECS  # noqa: E402


def test_label_and_split_identifiers_equal_release_specs():
    registries.validate_release_alignment()
    for release_id, spec in RELEASE_SPECS.items():
        task = spec["task"]
        assert registries.LABEL_ARTIFACTS[task]["label_threshold_set"] == spec["label_threshold_set"], release_id
        assert registries.LABEL_ARTIFACTS[task]["label_rule_version"] == spec["label_rule_version"], release_id
        assert registries.SPLIT_REGISTRY["tasks"][task]["split_version"] == spec["split_version"], release_id
        assert registries.SPLIT_REGISTRY["tasks"][task]["registry_id"] == spec["split_registry_id"], release_id


def test_closed_decisions_have_unique_ids_and_seed_contract_is_locked():
    ids = [item["id"] for item in registries.PENDING_DECISIONS]
    assert len(ids) == len(set(ids))
    assert all(str(item.get("status", "")).startswith("CLOSED") for item in registries.PENDING_DECISIONS)
    assert registries.EXPERIMENT_SEEDS["augmentation_policy"] == "MATCH_MASTER_SEED"
    assert registries.EXPERIMENT_SEEDS["role_seeds"]["seed_preprocess"] == 20260922


def test_small_subgroup_flag_follows_registered_rule():
    rng = np.random.default_rng(0)
    y = np.array([0] * 40 + [1] * 6 + [2] * 5)
    assert classification_metrics(y, rng.dirichlet(np.ones(3), size=len(y)))["small_subgroup_flag"] is False
    y_low_support = np.array([0] * 40 + [1] * 6 + [2] * 4)
    assert classification_metrics(y_low_support, rng.dirichlet(np.ones(3), size=len(y_low_support)))["small_subgroup_flag"] is True
    y_few_rows = np.array([0] * 10 + [1] * 10 + [2] * 9)
    assert classification_metrics(y_few_rows, rng.dirichlet(np.ones(3), size=len(y_few_rows)))["small_subgroup_flag"] is True
