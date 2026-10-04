"""Read-only readiness audit for the immutable LO/CQ recurrent-model inputs.

This app deliberately writes nothing to the Volume.  It resolves parent
imputation and balanced-train artifacts using the same immutable layout as
``model_app.py`` so a grid can be checked before an L4 is allocated.
"""
from __future__ import annotations

import json
from pathlib import Path

import modal


APP_NAME, VOLUME_NAME, MOUNT = "tempo-model-preflight-v1", "tempo-data-v1", "/data"
META_RELEASE, IMPUTATION_SEED = "imputation-v1", 20260922
REGIME = {"CQ": "CQ_RAW_EARLY", "LO": "LO_FULL_EARLY"}
PARENTS = {"V2": "V1", "V3": "V1", "V4": "V1", "V6": "V5", "V7": "V5", "V8": "V5",
           "V10": "V9", "V11": "V9", "V12": "V9", "V14": "V13", "V15": "V13", "V16": "V13"}

app = modal.App(APP_NAME)
volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)
image = modal.Image.debian_slim(python_version="3.12").add_local_python_source("release_core")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_parent(task: str, window: str, pipeline: str, spec: dict[str, str]) -> tuple[Path | None, dict | None, str | None]:
    root = (Path(MOUNT) / f"meta_release={META_RELEASE}" / "L1_runs" / f"task={task}" /
            f"feature_regime={REGIME[task]}" / f"window_id={window}" / f"pipeline_id={pipeline}" /
            "model_name=IMPUTATION_ONLY" / f"seed={IMPUTATION_SEED}")
    candidates = sorted(root.glob("run_id=*/attempt_id=*/run_manifest.json"),
                        key=lambda item: item.stat().st_mtime, reverse=True)
    for manifest_path in candidates:
        manifest = _read_json(manifest_path)
        input_root = manifest_path.parent / "model_inputs"
        if manifest.get("run_status") != "SUCCESS" or not (input_root / "train.parquet").exists():
            continue
        if any(manifest.get(field) != spec[field] for field in
               ("release_id", "split_registry_id", "split_version", "phase_version")):
            continue
        missing = [name for name in ("train.parquet", "validation.parquet", "test_P1.parquet", "test_P2.parquet", "test_P3.parquet", "test_P4.parquet")
                   if not (input_root / name).exists()]
        if missing:
            return None, manifest, f"missing model inputs: {missing}"
        return manifest_path.parent, manifest, None
    return None, None, "no successful immutable parent run matching the requested release"


def _find_balanced(task: str, window: str, pipeline: str, *, spec: dict[str, str], augmentation_seed: int) -> tuple[Path | None, dict | None, str | None]:
    root = (Path(MOUNT) / f"meta_release={META_RELEASE}" / "L1_runs" / f"task={task}" /
            f"feature_regime={REGIME[task]}" / f"window_id={window}" / "phase_id=P4" /
            f"pipeline_id={pipeline}" / "model_name=BALANCED_TRAIN_ONLY" / f"seed={augmentation_seed}")
    candidates = sorted(root.glob("run_id=*/attempt_id=*/run_manifest.json"),
                        key=lambda item: item.stat().st_mtime, reverse=True)
    for manifest_path in candidates:
        manifest = _read_json(manifest_path)
        train = manifest_path.parent / "balanced_train.parquet"
        if manifest.get("run_status") != "SUCCESS" or not train.exists():
            continue
        if manifest.get("parent_pipeline") != PARENTS[pipeline]:
            return None, manifest, "parent_pipeline does not match the registered V mapping"
        if int(manifest.get("seed", -1)) != augmentation_seed:
            return None, manifest, "augmentation seed does not match requested seed"
        if manifest.get("validation_test_touched") is not False:
            return None, manifest, "augmentation illegally touched validation or test"
        if any(manifest.get(field) != spec[field] for field in
               ("release_id", "split_registry_id", "split_version", "phase_version")):
            return None, manifest, "balanced TRAIN belongs to a different release"
        return train, manifest, None
    return None, None, "no successful balanced TRAIN artifact"


@app.function(image=image, volumes={MOUNT: volume}, cpu=1, memory=512, timeout=300)
def preflight(task: str = "LO", augmentation_seed: int = 42, release_id: str = "") -> dict:
    from release_core import resolve_release, validate_release_manifest
    if task not in REGIME:
        raise ValueError("task must be CQ or LO")
    spec = resolve_release(task, release_id)
    source = Path(MOUNT) / "input" / spec["input_dir"]
    release_manifest = _read_json(source / "release_manifest.json")
    raw_phase = source / spec["phase_views_dir"]
    raw_test = source / spec["test_prefix_views_dir"]
    source_errors = []
    try:
        validate_release_manifest(release_manifest, spec, source=str(source / "release_manifest.json"))
    except ValueError as error:
        source_errors.append(str(error))
    if not raw_phase.exists():
        source_errors.append(f"missing phase view: {raw_phase}")
    for prefix in ("P1", "P2", "P3", "P4"):
        if not (raw_test / prefix).exists():
            source_errors.append(f"missing test prefix: {raw_test / prefix}")

    cells = []
    for window in ("W1", "W2", "W3"):
        parents: dict[str, tuple[Path | None, dict | None, str | None]] = {}
        for pipeline in ("V0", "V1", "V5", "V9", "V13"):
            parents[pipeline] = _find_parent(task, window, pipeline, spec)
        for pipeline in (f"V{i}" for i in range(17)):
            parent = PARENTS.get(pipeline, pipeline)
            parent_path, parent_manifest, error = parents[parent]
            result = {"task": task, "window_id": window, "pipeline_id": pipeline,
                      "parent_pipeline": parent, "ready": False, "reason": error}
            if error is None:
                result["parent_run_id"] = parent_manifest["run_id"]
                result["parent_attempt_id"] = parent_manifest["attempt_id"]
                if pipeline == parent:
                    result["ready"] = True
                else:
                    train, augmented, balance_error = _find_balanced(
                        task, window, pipeline, spec=spec, augmentation_seed=augmentation_seed
                    )
                    result["ready"] = balance_error is None
                    result["reason"] = balance_error
                    if augmented:
                        result["augmentation_run_id"] = augmented.get("run_id")
                        result["augmentation_attempt_id"] = augmented.get("attempt_id")
            cells.append(result)
    return {"task": task, "release_id": spec["release_id"], "split_registry_id": spec["split_registry_id"],
            "augmentation_seed": augmentation_seed, "split_version": spec["split_version"], "phase_version": spec["phase_version"],
            "source_ready": not source_errors, "source_errors": source_errors,
            "release_manifest": release_manifest,
            "cells": cells, "ready_cells": sum(item["ready"] for item in cells),
            "total_cells": len(cells)}


@app.function(image=image, volumes={MOUNT: volume}, cpu=1, memory=512, timeout=300)
def model_status(task: str = "LO", model_name: str = "RNN", seed: int = 42, release_id: str = "") -> dict:
    """Read only status audit of completed recurrent-model cells."""
    from release_core import resolve_release
    if task not in REGIME:
        raise ValueError("task must be CQ or LO")
    spec = resolve_release(task, release_id)
    cells = []
    for window in ("W1", "W2", "W3"):
        for pipeline in (f"V{i}" for i in range(17)):
            root = (Path(MOUNT) / f"meta_release={META_RELEASE}" / "L1_runs" / f"task={task}" /
                    f"feature_regime={REGIME[task]}" / f"window_id={window}" / f"pipeline_id={pipeline}" /
                    f"model_name={model_name}" / f"seed={seed}")
            candidates = sorted(root.glob("run_id=*/attempt_id=*/run_manifest.json"),
                                key=lambda item: item.stat().st_mtime, reverse=True)
            result = {"task": task, "window_id": window, "pipeline_id": pipeline,
                      "model_name": model_name, "seed": seed, "ready": False, "reason": "no run manifest"}
            for path in candidates:
                manifest = _read_json(path)
                if manifest.get("run_status") != "SUCCESS":
                    continue
                if any(manifest.get(field) != spec[field] for field in
                       ("release_id", "split_registry_id", "split_version", "phase_version")):
                    result["reason"] = "successful run belongs to a different release"
                    break
                required = [path.parent / "SUCCESS", path.parent / "checkpoint", path.parent / "train_history.parquet",
                            path.parent / "feature_layout.json"]
                required += [path.parent / "predictions" / f"eval_split={eval_split}" / f"phase_id={prefix}" / "part-00000.parquet"
                             for eval_split in ("VALIDATION", "TEST") for prefix in ("P1", "P2", "P3", "P4")]
                missing = [str(item.relative_to(path.parent)) for item in required if not item.exists()]
                if missing:
                    result["reason"] = f"missing artifacts: {missing}"
                    break
                result.update({"ready": True, "reason": None, "run_id": manifest.get("run_id"),
                               "attempt_id": manifest.get("attempt_id"), "best_epoch": manifest.get("best_epoch"),
                               "train_rows": manifest.get("train_rows"), "validation_rows": manifest.get("validation_rows"),
                               "test_rows": manifest.get("test_rows"), "parent_augmentation_run_id": manifest.get("parent_augmentation_run_id")})
                break
            cells.append(result)
    return {"task": task, "model_name": model_name, "seed": seed,
            "release_id": spec["release_id"], "split_registry_id": spec["split_registry_id"],
            "split_version": spec["split_version"], "phase_version": spec["phase_version"], "cells": cells,
            "ready_cells": sum(item["ready"] for item in cells), "total_cells": len(cells)}


@app.local_entrypoint()
def cli(task: str = "LO", mode: str = "inputs", model_name: str = "RNN", seed: int = 42,
        augmentation_seed: int = 42, release_id: str = "") -> None:
    if mode == "inputs":
        value = preflight.remote(task, augmentation_seed, release_id)
    elif mode == "models":
        value = model_status.remote(task, model_name, seed, release_id)
    else:
        raise ValueError("mode must be inputs or models")
    print(json.dumps(value, indent=2, sort_keys=True))
