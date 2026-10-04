"""Release contracts; a CLI selects an ID, while the uploaded manifest proves it.

The values here are controlled vocabulary, not a substitute for provenance.
Every worker validates the matching ``release_manifest.json`` before reading
data and persists the resolved fields into its own immutable run manifest.
"""
from __future__ import annotations

from typing import Any


RELEASE_SPECS: dict[str, dict[str, str]] = {
    "CQ_V2_2": {
        "task": "CQ",
        "input_dir": "CQ_v2_2",
        "split_version": "v2_2",
        "phase_version": "wide_prefix_v2_2",
        "phase_views_dir": "phase_views_v2_2",
        "test_prefix_views_dir": "test_prefix_views_v2_2",
        "split_registry_id": "split_registry_v2_2_overlap_audit_v1_r2",
        "label_rule_version": "cq_vector_proximity_v1_zero_activity_policy",
        "label_threshold_set": "CQ_VECTOR_PROXIMITY_PRIMARY_V1",
    },
    "LO_V3_1": {
        "task": "LO",
        "input_dir": "LO_v3_1",
        "split_version": "v3_1",
        "phase_version": "wide_prefix_v3_1",
        "phase_views_dir": "phase_views_v3_1_scored_signal_excluded",
        "test_prefix_views_dir": "test_prefix_views_v3_1_scored_signal_excluded",
        "split_registry_id": "split_registry_v3_1_scored_signal_excluded_overlap_audit_v1",
        "label_rule_version": "lo_final_score_catalog_normalized_v3_1",
        "label_threshold_set": "CATALOG_NORMALIZED_PRIMARY_V3_1__EXCLUDE_NO_SCORED_SIGNAL",
    },
}


def default_release_id(task: str) -> str:
    matches = [release_id for release_id, spec in RELEASE_SPECS.items() if spec["task"] == task]
    if len(matches) != 1:
        raise ValueError(f"No unique default release for task={task!r}")
    return matches[0]


def resolve_release(task: str, release_id: str = "") -> dict[str, str]:
    """Return the controlled release spec and reject a task/release mismatch."""
    selected = release_id or default_release_id(task)
    try:
        spec = RELEASE_SPECS[selected]
    except KeyError as error:
        raise ValueError(f"Unknown release_id={selected!r}; choose one of {sorted(RELEASE_SPECS)}") from error
    if spec["task"] != task:
        raise ValueError(f"release_id={selected} belongs to task={spec['task']}, not task={task}")
    return {"release_id": selected, **spec}


def validate_release_manifest(manifest: dict[str, Any], spec: dict[str, str], *, source: str) -> None:
    """Ensure uploaded input identifies exactly the selected immutable release."""
    required = ("task", "release_id", "split_registry_id", "split_version", "phase_version",
                "feature_dictionary_version", "label_rule_version", "label_threshold_set")
    missing = [field for field in required if not manifest.get(field)]
    if missing:
        raise ValueError(f"Release manifest lacks required fields at {source}: {missing}")
    mismatches = {
        field: (manifest.get(field), spec[field])
        for field in ("task", "release_id", "split_registry_id", "split_version", "phase_version",
                      "label_rule_version", "label_threshold_set")
        if manifest.get(field) != spec[field]
    }
    if mismatches:
        raise ValueError(f"Release manifest does not match {spec['release_id']} at {source}: {mismatches}")
