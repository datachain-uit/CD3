"""Immutable provenance sidecars for portable VastAI model runs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


PARENT_PIPELINES = {
    "V2": "V1", "V3": "V1", "V4": "V1", "V6": "V5", "V7": "V5", "V8": "V5",
    "V10": "V9", "V11": "V9", "V12": "V9", "V14": "V13", "V15": "V13", "V16": "V13",
}

# Kept here because the portable VastAI bundle intentionally has no dependency
# on the Modal package tree. These are the same locked vocabularies as
# release_core.contracts.RELEASE_SPECS.
RELEASE_FIELDS = {
    "CQ_V2_2": {"split_registry_id": "split_registry_v2_2_overlap_audit_v1_r2",
                  "split_version": "v2_2", "phase_version": "wide_prefix_v2_2",
                  "feature_dictionary_version": "schema_from_phase_views_v2_2",
                  "label_rule_version": "cq_vector_proximity_v1_zero_activity_policy",
                  "label_threshold_set": "CQ_VECTOR_PROXIMITY_PRIMARY_V1", "scenario": "hybrid"},
    "LO_V3_1": {"split_registry_id": "split_registry_v3_1_scored_signal_excluded_overlap_audit_v1",
                  "split_version": "v3_1", "phase_version": "wide_prefix_v3_1",
                  "feature_dictionary_version": "schema_from_phase_views_v3_1",
                  "label_rule_version": "lo_final_score_catalog_normalized_v3_1",
                  "label_threshold_set": "CATALOG_NORMALIZED_PRIMARY_V3_1", "scenario": "hybrid"},
}


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _artifact_identity(remote_path: str | None) -> dict[str, str] | None:
    if not remote_path:
        return None
    values: dict[str, str] = {"remote_path": remote_path}
    for segment in remote_path.split("/"):
        if "=" in segment:
            key, value = segment.split("=", 1)
            if key in {"pipeline_id", "model_name", "seed", "run_id", "attempt_id", "phase_id"}:
                values[key] = value
    return values


def load_download_manifest(data_root: Path, *, task: str) -> tuple[dict[str, Any], dict[str, str], str]:
    path = data_root / "download_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("task") != task:
        raise ValueError(f"download manifest task mismatch at {path}: {manifest.get('task')!r}")
    required = ("release_id", "data_release_id")
    missing = [key for key in required if not manifest.get(key)]
    if missing:
        raise ValueError(f"download manifest lacks {missing}: {path}")
    locked = RELEASE_FIELDS.get(str(manifest["release_id"]))
    if locked is None:
        raise ValueError(f"unknown portable release: {manifest['release_id']!r}")
    for key, value in locked.items():
        existing = manifest.get(key)
        if existing is not None and existing != value:
            raise ValueError(f"release field mismatch {key}: {existing!r} != {value!r}")
        manifest[key] = value
    paths = {str(item["local_path"]): str(item["remote_path"])
             for item in manifest.get("files", [])
             if item.get("local_path") and item.get("remote_path")}
    return manifest, paths, _sha256_file(path)


def build_contract(*, task: str, data_root: Path, run_dir: Path, manifest: dict[str, Any],
                   runner_path: Path) -> dict[str, Any]:
    download, remote_paths, download_hash = load_download_manifest(data_root, task=task)
    pipeline = str(manifest["pipeline_id"])
    window = str(manifest["window_id"])
    parent = PARENT_PIPELINES.get(pipeline, pipeline)
    train_name = "train.parquet" if pipeline == parent else "balanced_train.parquet"
    input_relatives = {
        "train": f"train/{window}/{pipeline}/{train_name}",
        "validation": f"evaluation/{window}/{parent}/validation.parquet",
        **{phase: f"evaluation/{window}/{parent}/test_{phase}.parquet" for phase in ("P1", "P2", "P3", "P4")},
    }
    missing = [name for name, relative in input_relatives.items() if relative not in remote_paths]
    if missing:
        raise ValueError(f"missing source mapping for {task}/{window}/{pipeline}: {missing}")
    sources = {name: _artifact_identity(remote_paths[relative]) for name, relative in input_relatives.items()}
    augmentation = sources["train"] if pipeline != parent else None
    seed_augmentation = int(augmentation["seed"]) if augmentation and augmentation.get("seed", "").isdigit() else None
    immutable_key = {
        "release_id": download["release_id"], "data_release_id": download["data_release_id"],
        "task": task, "window_id": window, "pipeline_id": pipeline,
        "model_name": manifest["model_name"], "seed": manifest["seed"],
        "input_download_manifest_sha256": download_hash, "sources": sources,
        "runner_sha256": _sha256_file(runner_path),
    }
    return {
        "metadata_schema_version": "vastai_model_metadata_contract_v1",
        "portable_run_id": _sha256_bytes(json.dumps(immutable_key, sort_keys=True, separators=(",", ":")).encode()),
        "release": {key: download.get(key) for key in (
            "task", "release_id", "data_release_id", "split_registry_id", "split_version", "phase_version",
            "feature_dictionary_version", "label_rule_version", "label_threshold_set", "scenario")},
        "model_identity": {key: manifest.get(key) for key in (
            "task", "window_id", "pipeline_id", "parent_pipeline", "model_name", "architecture", "seed",
            "protocol", "precision_policy", "batch_size", "max_epochs", "early_stopping_patience", "best_epoch")},
        "seed_bundle": {"master_seed": manifest.get("seed"), "seed_model": manifest.get("seed_model"),
                        "seed_dataloader": manifest.get("seed_dataloader"), "seed_preprocess": 20260922,
                        "seed_augmentation": seed_augmentation},
        "lineage": {"input_download_manifest_sha256": download_hash, "runner_sha256": _sha256_file(runner_path),
                    "run_manifest_sha256": _sha256_file(run_dir / "run_manifest.json"),
                    "input_sources": sources, "parent_imputation": sources["validation"],
                    "augmentation": augmentation},
        "model_created_at_utc": manifest.get("created_at_utc"),
    }


def write_contract(contract: dict[str, Any], path: Path) -> bool:
    payload = json.dumps(contract, indent=2, sort_keys=True) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != payload:
            raise ValueError(f"refusing to replace divergent immutable sidecar: {path}")
        return False
    path.write_text(payload, encoding="utf-8")
    return True
