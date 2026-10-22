#!/usr/bin/env python3
"""Audit both valid ``data_release_id`` values around the lineage-sidecar change.

The current inventory deliberately excludes ``materialization_lineage_*`` from
the predictive input identity.  Historical manifests created while those files
were included can still describe the same frozen release.  This read-only tool
records both identities and classifies every manifest as CURRENT,
LEGACY_WITH_LINEAGE, or UNMATCHED.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from imputation_core.meta_storage import release_identity_aliases


def inventory_with_lineage(input_root: Path) -> list[dict[str, Any]]:
    """Return the pre-sidecar-exclusion inventory, including every payload file."""
    entries: list[dict[str, Any]] = []
    for path in sorted(input_root.rglob("*")):
        if path.is_file() and not path.name.startswith("."):
            entries.append({"path": str(path.relative_to(input_root)), "bytes": path.stat().st_size})
    return entries


def ledger(input_root: Path, task: str) -> dict[str, Any]:
    """Compute current and historical identities at the *canonical* release path."""
    current, aliases = release_identity_aliases(input_root, task=task)
    legacy_entries = inventory_with_lineage(input_root)
    legacy_id = next(
        (identity for identity, label in aliases.items() if label == "LEGACY_WITH_LINEAGE"),
        current["data_release_id"],
    )
    return {
        "task": task,
        "release_id": current["release_id"],
        "root": str(input_root),
        "data_release_id_current": current["data_release_id"],
        "data_release_id_legacy_with_lineage": legacy_id,
        "identities_differ": legacy_id != current["data_release_id"],
        "materialization_lineage_dirs": current["materialization_lineage_dirs"],
        "n_files_current": len(current["inventory"]["files"]),
        "n_files_with_lineage": len(legacy_entries),
        "rule": "current excludes lineage sidecars; legacy includes every non-hidden file",
    }


def scan_manifests(root: Path, known: dict[str, str], *, release_id: str) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    unmatched: list[dict[str, str | None]] = []
    for path in sorted(root.rglob("run_manifest.json")):
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            counts["UNREADABLE"] += 1
            continue
        if manifest.get("release_id") != release_id:
            counts["OTHER_RELEASE"] += 1
            continue
        value = manifest.get("data_release_id")
        if (not value and manifest.get("balance_pipeline") and
                manifest.get("parent_imputation_run_id") and manifest.get("phase_id") == "P4"):
            label = "UNVERSIONED_S2_PARENT"
        else:
            label = known.get(str(value), "UNMATCHED" if value else "ABSENT")
        counts[label] += 1
        if label in {"UNMATCHED", "ABSENT", "UNVERSIONED_S2_PARENT"}:
            unmatched.append({"manifest": str(path), "data_release_id": value})
    return {"manifests": sum(counts.values()), "by_identity": dict(counts), "unmatched": unmatched[:20]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-root", required=True, type=Path)
    parser.add_argument("--task", required=True, choices=("CQ", "LO"))
    parser.add_argument("--manifests", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    report = ledger(args.release_root, args.task)
    if args.manifests:
        known = {
            report["data_release_id_current"]: "CURRENT",
            report["data_release_id_legacy_with_lineage"]: "LEGACY_WITH_LINEAGE",
        }
        report["manifest_scan"] = scan_manifests(
            args.manifests, known, release_id=report["release_id"],
        )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    scan = report.get("manifest_scan", {}).get("by_identity", {})
    return 1 if scan.get("UNMATCHED") or scan.get("ABSENT") or scan.get("UNREADABLE") else 0


if __name__ == "__main__":
    raise SystemExit(main())
