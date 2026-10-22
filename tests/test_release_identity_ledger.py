"""Regression coverage for the lineage-sidecar identity transition."""
from __future__ import annotations

import json
from pathlib import Path

from imputation_core.meta_storage import release_identity_aliases, release_inventory
from tools.release_identity_ledger import ledger, scan_manifests


SIDECAR = {
    "task": "CQ",
    "release_id": "CQ_V2_2",
    "split_registry_id": "split_registry_v2_2_overlap_audit_v1_r2",
    "split_version": "v2_2",
    "phase_version": "wide_prefix_v2_2",
    "feature_dictionary_version": "schema_from_phase_views_v2_2",
    "label_rule_version": "cq_vector_proximity_v1_zero_activity_policy",
    "label_threshold_set": "CQ_VECTOR_PROXIMITY_PRIMARY_V1",
}


def _make_release(root: Path, *, lineage: bool) -> None:
    (root / "phase_views_v2_2").mkdir(parents=True)
    (root / "phase_views_v2_2" / "part-0.parquet").write_bytes(b"x" * 10)
    (root / "release_manifest.json").write_text(json.dumps(SIDECAR), encoding="utf-8")
    if lineage:
        (root / "materialization_lineage_v2_2").mkdir()
        (root / "materialization_lineage_v2_2" / "lineage.json").write_text("{}", encoding="utf-8")


def test_lineage_is_excluded_from_current_identity_but_accepted_as_legacy(tmp_path: Path) -> None:
    bare, with_lineage = tmp_path / "bare", tmp_path / "with_lineage"
    _make_release(bare, lineage=False)
    _make_release(with_lineage, lineage=True)

    assert release_inventory(bare, task="CQ")["inventory"]["files"] == release_inventory(
        with_lineage, task="CQ"
    )["inventory"]["files"]
    current, aliases = release_identity_aliases(with_lineage, task="CQ")
    assert aliases[current["data_release_id"]] == "CURRENT"
    assert "LEGACY_WITH_LINEAGE" in aliases.values()
    report = ledger(with_lineage, "CQ")
    assert report["identities_differ"] is True


def test_scan_labels_only_known_active_release_identities(tmp_path: Path) -> None:
    release_root = tmp_path / "release"
    _make_release(release_root, lineage=True)
    report = ledger(release_root, "CQ")
    manifests = tmp_path / "runs"
    for name, value in (
        ("current", report["data_release_id_current"]),
        ("legacy", report["data_release_id_legacy_with_lineage"]),
        ("bad", "sha256:unmatched"),
        ("other", "sha256:other"),
    ):
        path = manifests / name / "run_manifest.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"release_id": "OTHER" if name == "other" else "CQ_V2_2", "data_release_id": value}), encoding="utf-8")
    known = {
        report["data_release_id_current"]: "CURRENT",
        report["data_release_id_legacy_with_lineage"]: "LEGACY_WITH_LINEAGE",
    }
    scan = scan_manifests(manifests, known, release_id="CQ_V2_2")
    assert scan["by_identity"] == {
        "CURRENT": 1,
        "LEGACY_WITH_LINEAGE": 1,
        "UNMATCHED": 1,
        "OTHER_RELEASE": 1,
    }
