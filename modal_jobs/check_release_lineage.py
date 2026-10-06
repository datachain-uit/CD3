"""Read-only local validation of an immutable CQ/LO input release."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED = ("task", "release_id", "split_registry_id", "split_version", "phase_version",
            "feature_dictionary_version", "label_rule_version", "label_threshold_set")


def rows(directory: Path) -> list[dict]:
    files = sorted(directory.rglob("*.parquet"))
    if not files:
        raise SystemExit(f"[lineage] no Parquet files under {directory}")
    import pyarrow.parquet as pq
    return [row for file in files for row in pq.read_table(file).to_pylist()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", required=True, choices=("CQ", "LO"))
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--lineage", required=True, type=Path)
    parser.add_argument("--phase-views", required=True, type=Path)
    parser.add_argument("--test-prefixes", required=True, type=Path)
    parser.add_argument("--allow-missing-success-marker", action="store_true")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    missing = [field for field in REQUIRED if not manifest.get(field)]
    if missing or manifest["task"] != args.task or manifest["release_id"] != args.release_id:
        raise SystemExit(f"[manifest] invalid for {args.task}/{args.release_id}: missing={missing}")
    lineage = rows(args.lineage)
    by_source = {row.get("source_name"): row for row in lineage}
    features = by_source.get("features")
    if not features:
        raise SystemExit("[lineage] missing features row")
    if {row.get("task") for row in lineage} != {args.task}:
        raise SystemExit("[lineage] task does not match uploader task")
    if int(features.get("exact_duplicates_collapsed", -1)) != 0:
        raise SystemExit("[lineage] feature release has collapsed duplicates")
    if int(features.get("rows_before", 0)) != int(features.get("rows_after_exact_deduplication", -1)):
        raise SystemExit("[lineage] features rows_before differs from rows_after_exact_deduplication")
    feature_source = features.get("feature_source")
    if feature_source is not None and "cumulative_phase_features_v2" not in str(feature_source):
        raise SystemExit(f"[lineage] unexpected feature_source={feature_source!r}")
    markers = [args.phase_views] + [args.test_prefixes / phase for phase in ("P1", "P2", "P3", "P4")]
    missing_markers = [str(path) for path in markers if not (path / "_SUCCESS").is_file()]
    if missing_markers and not args.allow_missing_success_marker:
        raise SystemExit(f"[markers] missing _SUCCESS: {missing_markers}")
    if missing_markers:
        print(f"[markers] warning; hand-copied release has no _SUCCESS: {missing_markers}")
    print(f"[release] OK {args.task}/{args.release_id}; features={features['rows_after_exact_deduplication']} "
          f"lineage_source={feature_source or 'legacy-hash-only'}")


if __name__ == "__main__":
    main()
