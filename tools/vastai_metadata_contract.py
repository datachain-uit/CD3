"""Immutable provenance sidecars for portable VastAI model runs."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


PARENT_PIPELINES = {
    "V2": "V1", "V3": "V1", "V4": "V1", "V6": "V5", "V7": "V5", "V8": "V5",
    "V10": "V9", "V11": "V9", "V12": "V9", "V14": "V13", "V15": "V13", "V16": "V13",
}


def detect_runner_git_commit(runner_path: Path) -> str | None:
    """Return HEAD only if the runner bytes exactly match its tracked blob.

    Portable deployments often have no Git checkout; never guess historical
    provenance from the checkout used later to backfill metadata.
    """
    try:
        root = subprocess.run(["git", "-C", str(runner_path.parent), "rev-parse", "--show-toplevel"],
                              check=True, capture_output=True, text=True, timeout=5).stdout.strip()
        relative = runner_path.resolve().relative_to(Path(root).resolve()).as_posix()
        blob = subprocess.run(["git", "-C", root, "show", f"HEAD:{relative}"],
                              check=True, capture_output=True, timeout=5).stdout
        if blob != runner_path.read_bytes():
            return None
        return subprocess.run(["git", "-C", root, "rev-parse", "HEAD"],
                              check=True, capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, ValueError, subprocess.SubprocessError):
        return None

# The portable bundle ships ``release_core`` next to ``model`` (both are plain
# Python without a Modal dependency), so the locked vocabulary is imported rather
# than copied: a copy drifted on 2026-10-12 (LO ``label_threshold_set`` lost the
# ``__EXCLUDE_NO_SCORED_SIGNAL`` suffix), which would have stamped a wrong
# identifier into every LO sidecar or refused every LO run.
_PROJECT_ROOT = next((c for c in (Path(__file__).resolve().parent, Path(__file__).resolve().parents[1])
                      if (c / "release_core").is_dir()), None)
if _PROJECT_ROOT is not None and str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
try:
    from release_core import contracts as release_contracts  # noqa: E402
    from release_core.contracts import RELEASE_SPECS  # noqa: E402
except ImportError as exc:  # The bundle must ship release_core/ next to model/; do not paste the values here.
    raise RuntimeError("portable VastAI bundle must include release_core/ (locked release vocabulary)") from exc

_SHARED_RELEASE_KEYS = ("split_registry_id", "split_version", "phase_version", "label_rule_version", "label_threshold_set")
_EXTRA_RELEASE_FIELDS = {
    "CQ_V2_2": {"feature_dictionary_version": "schema_from_phase_views_v2_2", "scenario": "hybrid"},
    "LO_V3_1": {"feature_dictionary_version": "schema_from_phase_views_v3_1", "scenario": "hybrid"},
}
RELEASE_FIELDS = {
    release_id: {**{key: spec[key] for key in _SHARED_RELEASE_KEYS}, **_EXTRA_RELEASE_FIELDS[release_id]}
    for release_id, spec in RELEASE_SPECS.items()
}


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _release_contract_sha256() -> str:
    """Hash the imported locked vocabulary used to validate this portable run."""
    return _sha256_file(Path(release_contracts.__file__))


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


def train_relative_candidates(window: str, pipeline: str, seed: int) -> list[str]:
    """Return candidate portable TRAIN paths, ordered most-specific first."""
    parent = PARENT_PIPELINES.get(pipeline, pipeline)
    if pipeline == parent:
        return [f"train/{window}/{pipeline}/train.parquet"]
    return [f"train/{window}/{pipeline}/seed={seed}/balanced_train.parquet",
            f"train/{window}/{pipeline}/balanced_train.parquet"]


def augmentation_source_seed(remote_path: str | None) -> int | None:
    identity = _artifact_identity(remote_path)
    seed = (identity or {}).get("seed", "")
    return int(seed) if str(seed).isdigit() else None


def build_contract(*, task: str, data_root: Path, run_dir: Path, manifest: dict[str, Any],
                   runner_path: Path, train_relative: str | None = None) -> dict[str, Any]:
    download, remote_paths, download_hash = load_download_manifest(data_root, task=task)
    pipeline = str(manifest["pipeline_id"])
    window = str(manifest["window_id"])
    parent = PARENT_PIPELINES.get(pipeline, pipeline)
    if train_relative is None:
        train_relative = train_relative_candidates(window, pipeline, int(manifest["seed"]))[-1]
    input_relatives = {
        "train": train_relative,
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
        "model_name": manifest["model_name"], "model_revision": manifest.get("model_revision"),
        "seed": manifest["seed"],
        "input_download_manifest_sha256": download_hash, "sources": sources,
        "runner_sha256": _sha256_file(runner_path),
        "release_contract_sha256": _release_contract_sha256(),
    }
    return {
        "metadata_schema_version": "vastai_model_metadata_contract_v1",
        "portable_run_id": _sha256_bytes(json.dumps(immutable_key, sort_keys=True, separators=(",", ":")).encode()),
        "release": {key: download.get(key) for key in (
            "task", "release_id", "data_release_id", "split_registry_id", "split_version", "phase_version",
            "feature_dictionary_version", "label_rule_version", "label_threshold_set", "scenario")},
        "model_identity": {key: manifest.get(key) for key in (
            "task", "window_id", "pipeline_id", "parent_pipeline", "model_name", "architecture", "model_revision",
            "architecture_metadata", "seed", "protocol", "precision_policy", "batch_size", "micro_batch_size",
            "accumulation_steps", "max_epochs", "early_stopping_patience", "hidden_size", "num_layers", "dropout",
            "learning_rate", "weight_decay", "best_epoch")},
        "execution": {key: manifest.get(key) for key in (
            "execution_backend", "gpu", "gpu_count", "gpu_total_memory_gb", "cuda_capability", "torch_version",
            "cuda_version", "cudnn_version", "cublas_workspace_config", "deterministic_algorithms",
            "energy_measurement")},
        "seed_bundle": {"master_seed": manifest.get("seed"), "seed_model": manifest.get("seed_model"),
                        "seed_dataloader": manifest.get("seed_dataloader"), "seed_preprocess": 20260922,
                        "seed_augmentation": seed_augmentation,
                        "augmentation_seed_policy": manifest.get("augmentation_seed_policy")},
        "lineage": {"input_download_manifest_sha256": download_hash, "runner_sha256": _sha256_file(runner_path),
                    **({"runner_git_commit": manifest["runner_git_commit"]} if manifest.get("runner_git_commit") else {}),
                    "release_contract_sha256": _release_contract_sha256(),
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
