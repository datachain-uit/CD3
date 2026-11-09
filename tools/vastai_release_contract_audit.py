#!/usr/bin/env python3
"""Read-only contract audit for a downloaded VastAI release bundle and its runs.

This verifies the identity recorded in ``download_manifest.json`` against each
VastAI ``run_manifest.json``.  It intentionally does not recompute a Modal
release identity: a Vast bundle contains model inputs, not the full immutable
phase-view release and lineage sidecars required for that calculation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


FIELDS = ("task", "release_id", "data_release_id", "split_version", "phase_version")


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def audit(data_root: Path, run_root: Path) -> dict:
    download_path = data_root / "download_manifest.json"
    source = load_json(download_path)
    # Older download manifests lock only the release/data identity.  An absent
    # optional field is not evidence of a mismatch in a later run manifest.
    expected = {field: source.get(field) for field in FIELDS if source.get(field) is not None}
    download_sha256 = "sha256:" + hashlib.sha256(download_path.read_bytes()).hexdigest()
    counts: Counter[str] = Counter()
    mismatches: list[dict[str, object]] = []
    rows: list[dict[str, object]] = []
    for path in sorted(run_root.rglob("run_manifest.json")):
        try:
            manifest = load_json(path)
        except (OSError, ValueError) as error:
            counts["UNREADABLE"] += 1
            mismatches.append({"path": str(path), "reason": str(error)})
            continue
        contract_path = path.parent / "metadata_contract.json"
        if not contract_path.is_file():
            counts["MISSING_CONTRACT"] += 1
            mismatches.append({"path": str(path), "reason": "metadata_contract.json is missing"})
            continue
        try:
            contract = load_json(contract_path)
        except (OSError, ValueError) as error:
            counts["UNREADABLE_CONTRACT"] += 1
            mismatches.append({"path": str(contract_path), "reason": str(error)})
            continue
        release = contract.get("release", {})
        differing = {field: {"expected": value, "actual": release.get(field)}
                     for field, value in expected.items() if value != release.get(field)}
        contract_download_sha = contract.get("lineage", {}).get("input_download_manifest_sha256")
        if contract_download_sha != download_sha256:
            differing["input_download_manifest_sha256"] = {
                "expected": download_sha256, "actual": contract_download_sha,
            }
        status = "MATCH" if not differing else "MISMATCH"
        counts[status] += 1
        rows.append({
            "path": str(path), "status": status, "run_status": manifest.get("run_status"),
            "window_id": manifest.get("window_id"), "pipeline_id": manifest.get("pipeline_id"),
            "model_name": manifest.get("model_name"), "seed": manifest.get("master_seed"),
        })
        if differing and len(mismatches) < 20:
            mismatches.append({"path": str(path), "differences": differing})
    return {
        "audit_type": "vastai_download_manifest_contract_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "data_root": str(data_root), "run_root": str(run_root), "expected_release": expected,
        "download_manifest_sha256": download_sha256,
        "run_manifest_counts": dict(counts), "rows": rows, "mismatch_examples": mismatches,
        "complete": not any(counts.get(name) for name in ("MISMATCH", "UNREADABLE", "MISSING_CONTRACT", "UNREADABLE_CONTRACT")),
        "scope_note": "Checks declared download identity only; Modal CURRENT/LEGACY lineage identity needs the full canonical Modal release.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    report = audit(args.data_root, args.run_root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key not in {"rows", "mismatch_examples"}}, indent=2))
    if not report["complete"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
