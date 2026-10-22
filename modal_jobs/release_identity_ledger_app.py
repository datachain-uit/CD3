"""Materialize read-only release-identity ledgers directly on the Modal Volume.

The job scans only manifests declaring the same logical release as the mounted
input.  It distinguishes other locked releases from an unexpected identity for
the active release, and fails closed for the latter.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import modal


APP_NAME, VOLUME_NAME, MOUNT = "tempo-release-identity-ledger-v1", "tempo-data-v1", "/data"
META_RELEASE = "imputation-v1"

app = modal.App(APP_NAME)
volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=False)
image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("numpy>=1.26", "pandas>=2.2", "pyarrow>=16", "scikit-learn>=1.5")
    .add_local_python_source("imputation_core")
    .add_local_python_source("release_core")
)


def _legacy_inventory(input_root: Path) -> list[dict[str, object]]:
    return [
        {"path": str(path.relative_to(input_root)), "bytes": path.stat().st_size}
        for path in sorted(input_root.rglob("*"))
        if path.is_file() and not path.name.startswith(".")
    ]


def _scan_manifests(root: Path, *, release_id: str, known: dict[str, str]) -> dict[str, object]:
    counts: Counter[str] = Counter()
    examples: list[dict[str, str | None]] = []
    for path in sorted(root.rglob("run_manifest.json")):
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            counts["UNREADABLE"] += 1
            examples.append({"manifest": str(path), "data_release_id": None})
            continue
        if manifest.get("release_id") != release_id:
            counts["OTHER_RELEASE"] += 1
            continue
        identity = manifest.get("data_release_id")
        # Early immutable S2 parents predate the data_release_id field.  Their
        # JSON schema has balance_pipeline, parent_imputation_run_id and P4,
        # rather than a model_name. They are not independently selected by
        # report exporters: a valid S3 manifest names the parent via
        # parent_augmentation_run_id and carries the release identity.
        if (not identity and manifest.get("balance_pipeline") and
                manifest.get("parent_imputation_run_id") and manifest.get("phase_id") == "P4"):
            label = "UNVERSIONED_S2_PARENT"
        else:
            label = known.get(str(identity), "UNMATCHED" if identity else "ABSENT")
        counts[label] += 1
        if label in {"UNMATCHED", "ABSENT", "UNVERSIONED_S2_PARENT"} and len(examples) < 20:
            examples.append({"manifest": str(path), "data_release_id": identity})
    return {"manifests": sum(counts.values()), "by_identity": dict(counts), "examples": examples}


@app.function(image=image, volumes={MOUNT: volume}, cpu=1, memory=1024, timeout=30 * 60)
def materialize_release_identity_ledger(task: str = "CQ", release_id: str = "") -> dict:
    """Write the active release's ledger and fail if a same-release run is unknown."""
    from imputation_core.meta_storage import release_identity_aliases
    from release_core import resolve_release

    if task not in {"CQ", "LO"}:
        raise ValueError("task must be CQ or LO")
    spec = resolve_release(task, release_id)
    volume.reload()
    input_root = Path(MOUNT) / "input" / spec["input_dir"]
    current, known = release_identity_aliases(input_root, task=task)
    legacy_id = next(
        (identity for identity, label in known.items() if label == "LEGACY_WITH_LINEAGE"),
        current["data_release_id"],
    )
    scan = _scan_manifests(
        Path(MOUNT) / f"meta_release={META_RELEASE}" / "L1_runs",
        release_id=spec["release_id"], known=known,
    )
    report = {
        "task": task,
        "release_id": spec["release_id"],
        "input_root": str(input_root),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "data_release_id_current": current["data_release_id"],
        "data_release_id_legacy_with_lineage": legacy_id,
        "identities_differ": legacy_id != current["data_release_id"],
        "materialization_lineage_dirs": current["materialization_lineage_dirs"],
        "n_files_current": len(current["inventory"]["files"]),
        "n_files_with_lineage": len(_legacy_inventory(input_root)),
        "manifest_scan": scan,
    }
    output = (
        Path(MOUNT) / f"meta_release={META_RELEASE}" / "L2_facts" / "release_identity_ledger" /
        f"task={task}" / f"release_id={spec['release_id']}" / "ledger.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    volume.commit()
    bad = scan["by_identity"].get("UNMATCHED", 0) + scan["by_identity"].get("ABSENT", 0) + scan["by_identity"].get("UNREADABLE", 0)
    if bad:
        raise RuntimeError(f"Release identity ledger found {bad} same-release manifests without a known identity: {scan['by_identity']}")
    return {**report, "output": str(output), "complete": True}


@app.local_entrypoint()
def cli(task: str = "CQ", release_id: str = "") -> None:
    print(json.dumps(materialize_release_identity_ledger.remote(task, release_id), indent=2))
