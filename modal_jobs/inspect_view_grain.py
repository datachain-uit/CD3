"""Read-only enrollment-grain audit for locked CQ/LO views and V0 inputs.

The job determines whether a logical table contains exactly one row per
``enrollment_id``. It never writes to the Modal Volume.
"""
from __future__ import annotations

import json
from pathlib import Path

import modal

APP_NAME, VOLUME_NAME, MOUNT = "tempo-view-grain-audit", "tempo-data-v1", "/data"
META_RELEASE, SEED_IMPUTATION = "imputation-v1", 20260922
REGIME = {"CQ": "CQ_RAW_EARLY", "LO": "LO_FULL_EARLY"}
LABEL = {"CQ": "CQ_label_final", "LO": "LO_performance_label_3"}

app = modal.App(APP_NAME)
volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=False)
image = (modal.Image.debian_slim(python_version="3.12")
         .pip_install("pandas>=2.2", "pyarrow>=16")
         .add_local_python_source("release_core"))


def _first_existing(root: Path, names: tuple[str, ...]) -> Path | None:
    for name in names:
        candidate = root / name
        if candidate.exists():
            return candidate
        nested = candidate / name
        if nested.exists():
            return nested
    return None


def _parquet_files(path: Path) -> list[str]:
    if path.is_file():
        return [path.name]
    return sorted(str(item.relative_to(path)) for item in path.rglob("*.parquet"))


def _locked_input_root(task: str, release_id: str) -> tuple[Path, dict]:
    from release_core import resolve_release, validate_release_manifest
    spec = resolve_release(task, release_id)
    root = Path(MOUNT) / "input" / spec["input_dir"]
    manifest_path = root / "release_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Missing release_manifest.json under {root}")
    validate_release_manifest(json.loads(manifest_path.read_text(encoding="utf-8")), spec, source=str(manifest_path))
    return root, spec


def _grain(path: Path, label: str, filters: list[tuple[str, str]] | None = None) -> dict:
    """Return row grain and duplicate diagnostics for one logical table."""
    import pyarrow.dataset as ds

    print(json.dumps({"event": "grain_table_read_started", "path": str(path), "filters": filters or []}), flush=True)
    dataset = ds.dataset(str(path), format="parquet", partitioning="hive")
    names = set(dataset.schema.names)
    selected = [column for column in ("enrollment_id", label, "window", "split", "offering_id", "timeline_source")
                if column in names]
    expression = None
    for column, value in filters or []:
        if column not in names:
            continue
        term = ds.field(column) == value
        expression = term if expression is None else expression & term
    frame = dataset.to_table(columns=selected, filter=expression).to_pandas()
    print(json.dumps({"event": "grain_table_read_complete", "path": str(path), "rows": int(len(frame))}), flush=True)
    files = _parquet_files(path)
    result: dict = {
        "rows": int(len(frame)),
        "columns_read": selected,
        "parquet_file_count": len(files),
        "parquet_files_head": files[:20],
        "parquet_files_truncated": len(files) > 20,
    }
    if "enrollment_id" not in frame:
        result["error"] = "enrollment_id column not found"
        return result

    counts = frame["enrollment_id"].value_counts()
    result.update({
        "distinct_enrollment_id": int(counts.size),
        "rows_per_enrollment_max": int(counts.max()) if counts.size else 0,
        "rows_per_enrollment_hist": {str(key): int(value) for key, value in counts.value_counts().sort_index().items()},
        "ratio_rows_over_distinct": round(float(len(frame)) / float(counts.size), 4) if counts.size else None,
    })
    print(json.dumps({"event": "grain_table_summary", "path": str(path),
                      "distinct_enrollment_id": result["distinct_enrollment_id"],
                      "ratio_rows_over_distinct": result["ratio_rows_over_distinct"]}), flush=True)
    duplicate_ids = counts[counts > 1].index
    result["enrollments_with_duplicates"] = int(len(duplicate_ids))
    if not len(duplicate_ids):
        return result

    duplicate_rows = frame[frame["enrollment_id"].isin(duplicate_ids)]
    if label in duplicate_rows:
        result["duplicates_with_conflicting_label"] = int(
            (duplicate_rows.groupby("enrollment_id")[label].nunique() > 1).sum()
        )
    for column, output_name in (("timeline_source", "duplicates_with_two_timeline_sources"),
                                ("offering_id", "duplicates_with_two_offering_ids")):
        if column in duplicate_rows:
            result[output_name] = int((duplicate_rows.groupby("enrollment_id")[column].nunique() > 1).sum())
    result["duplicate_rows_identical_on_columns_read"] = int(duplicate_rows.duplicated(keep=False).sum())
    result["duplicate_examples"] = (
        duplicate_rows.sort_values("enrollment_id").head(6).astype(str).to_dict("records")
    )
    return result


def _latest_v0_inputs(task: str, window: str, *, spec: dict[str, str]) -> Path | None:
    root = (Path(MOUNT) / f"meta_release={META_RELEASE}" / "L1_runs" / f"task={task}" /
            f"feature_regime={REGIME[task]}" / f"window_id={window}" / "pipeline_id=V0" /
            "model_name=IMPUTATION_ONLY" / f"seed={SEED_IMPUTATION}")
    candidates = sorted(root.glob("run_id=*/attempt_id=*/run_manifest.json"),
                        key=lambda path: path.stat().st_mtime, reverse=True)
    for manifest_path in candidates:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        inputs = manifest_path.parent / "model_inputs"
        if (manifest.get("run_status") == "SUCCESS" and (inputs / "train.parquet").exists() and
                all(manifest.get(field) == spec[field] for field in
                    ("release_id", "split_registry_id", "split_version", "phase_version"))):
            return inputs
    return None


@app.function(image=image, volumes={MOUNT: volume}, cpu=4, memory=32768, timeout=60 * 60)
def audit(task: str = "CQ", window: str = "", scope: str = "all", release_id: str = "") -> dict:
    if task not in REGIME:
        raise ValueError("task must be CQ or LO")
    allowed_scopes = {"all", "release_train", "release_validation", "release_test", "v0_train", "v0_validation", "v0_test"}
    if scope not in allowed_scopes:
        raise ValueError(f"scope must be one of {sorted(allowed_scopes)}")
    windows = (window,) if window else ("W1", "W2", "W3")
    if any(item not in {"W1", "W2", "W3"} for item in windows):
        raise ValueError("window must be empty, W1, W2, or W3")
    print(json.dumps({"event": "grain_audit_started", "task": task, "window": window or "ALL", "scope": scope}), flush=True)
    volume.reload()
    input_root, spec = _locked_input_root(task, release_id)
    phase_root = input_root / spec["phase_views_dir"]
    test_root = input_root / spec["test_prefix_views_dir"]
    report: dict = {
        "task": task,
        "release_id": spec["release_id"], "split_registry_id": spec["split_registry_id"],
        "input_root": str(input_root),
        "phase_views_dir": str(phase_root) if phase_root else None,
        "test_prefix_dir": str(test_root) if test_root else None,
        "release_views": {},
        "v0_model_inputs": {},
    }
    wants_release = scope in {"all", "release_train", "release_validation", "release_test"}
    if wants_release and (phase_root is None or test_root is None):
        report["error"] = "release view or test-prefix directory not found"
        report["verdict"] = "INPUT_VIEWS_NOT_FOUND"
        return report
    for scoped_window in windows:
        if phase_root and scope in {"all", "release_train", "release_validation"}:
            splits = (("train",) if scope == "release_train" else
                      ("validation",) if scope == "release_validation" else ("train", "validation"))
            for split in splits:
                report["release_views"][f"{scoped_window}/{split}"] = _grain(
                    phase_root, LABEL[task], [("window", scoped_window), ("split", split)]
                )
        if test_root and scope in {"all", "release_test"}:
            for phase in ("P1", "P2", "P3", "P4"):
                folder = test_root / phase
                if folder.exists():
                    report["release_views"][f"{scoped_window}/test_{phase}"] = _grain(
                        folder, LABEL[task], [("window", scoped_window), ("split", "test")]
                    )
        if scope not in {"all", "v0_train", "v0_validation", "v0_test"}:
            continue
        inputs = _latest_v0_inputs(task, scoped_window, spec=spec)
        if inputs is None:
            report["v0_model_inputs"][scoped_window] = {"error": "no SUCCESS V0 model_inputs"}
            continue
        names = (("train",) if scope == "v0_train" else
                 ("validation",) if scope == "v0_validation" else
                 (("test_P1", "test_P2", "test_P3", "test_P4") if scope == "v0_test" else
                  ("train", "validation", "test_P1", "test_P2", "test_P3", "test_P4")))
        for name in names:
            path = inputs / f"{name}.parquet"
            if path.exists():
                report["v0_model_inputs"][f"{scoped_window}/{name}"] = _grain(path, LABEL[task])

    flagged = {
        key: value.get("ratio_rows_over_distinct")
        for section in ("release_views", "v0_model_inputs")
        for key, value in report[section].items()
        if isinstance(value, dict) and (value.get("ratio_rows_over_distinct") or 1.0) > 1.0
    }
    report["tables_with_duplicate_enrollments"] = flagged
    report["verdict"] = "GRAIN_OK" if not flagged else "DUPLICATE_ENROLLMENT_ROWS_PRESENT"
    return report


@app.local_entrypoint()
def cli(task: str = "CQ", window: str = "", scope: str = "all", release_id: str = "") -> None:
    print(json.dumps({"event": "grain_audit_submitted", "task": task, "window": window or "ALL", "scope": scope,
                      "release_id": release_id or "DEFAULT_FOR_TASK"}), flush=True)
    print(json.dumps(audit.remote(task, window, scope, release_id), indent=2, ensure_ascii=False, default=str))
