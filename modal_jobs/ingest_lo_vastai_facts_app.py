"""Ingest audited LO VastAI facts into the immutable L2 fact store.

The job imports *facts only*: it never uploads or rewrites training inputs,
checkpoints, or prediction matrices.  Every imported row receives the
portable run identity from its ``metadata_contract.json`` and is labelled as
an external VastAI execution.  A compact receipt is stored in L0 so that an
L2 fact can be traced to the exact local audit bundle that supplied it.

Set ``LO_VASTAI_AUDIT_ROOT`` and ``LO_VASTAI_ARTIFACT_ROOT`` before invoking
this Modal app when the local bundle is not at the documented default path.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import modal


APP_NAME, VOLUME_NAME, MOUNT = "tempo-ingest-lo-vastai-facts-v1", "tempo-data-v1", "/data"
META_RELEASE = "imputation-v1"
TASK, REGIME, RELEASE_ID = "LO", "LO_FULL_EARLY", "LO_V3_1"
SEED = 42
EXTERNAL_STAGE = "S3_MODEL_EXTERNAL_VASTAI"
FAMILIES = ("RNN", "LSTM", "GRU", "BILSTM")
EXPECTED_PER_FAMILY = {
    "canonical_s_leak": 120,
    "sanity_components": 408,
    "metrics_per_class": 1224,
    "bootstrap_metrics_per_class": 3672,
    "evaluation_slices": 1224,
    "checkpoint_selection": 51,
}

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE = PROJECT_ROOT / "LO" / "resuilt" / "vastai_f2_batch2048_seed42_20261013"
AUDIT_LOCAL_ROOT = Path(os.environ.get("LO_VASTAI_AUDIT_ROOT", DEFAULT_BUNDLE / "audits")).resolve()
ARTIFACT_LOCAL_ROOT = Path(os.environ.get("LO_VASTAI_ARTIFACT_ROOT", DEFAULT_BUNDLE)).resolve()
if not AUDIT_LOCAL_ROOT.is_dir():
    raise FileNotFoundError(f"LO_VASTAI_AUDIT_ROOT does not exist: {AUDIT_LOCAL_ROOT}")
if not ARTIFACT_LOCAL_ROOT.is_dir():
    raise FileNotFoundError(f"LO_VASTAI_ARTIFACT_ROOT does not exist: {ARTIFACT_LOCAL_ROOT}")


def _metadata_only(path: Path) -> bool:
    """Ignore all large external artifacts except metadata contracts."""
    return path.is_file() and path.name not in {"metadata_contract.json", "run_manifest.json"}


app = modal.App(APP_NAME)
volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=False)
image = (modal.Image.debian_slim(python_version="3.12")
         .pip_install("pandas>=2.2", "pyarrow>=16")
         .add_local_dir(AUDIT_LOCAL_ROOT, remote_path="/audit_source")
         .add_local_dir(ARTIFACT_LOCAL_ROOT, remote_path="/artifact_source", ignore=_metadata_only))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return f"sha256:{digest.hexdigest()}"


def _portable_id(contract: dict) -> str:
    value = str(contract.get("portable_run_id", ""))
    if not value.startswith("sha256:") or len(value) != 71:
        raise ValueError("metadata contract has no valid portable_run_id")
    return value.removeprefix("sha256:")


def _load_contract_index(root: Path) -> dict[tuple[str, str, str], dict]:
    index: dict[tuple[str, str, str], dict] = {}
    for path in root.rglob("metadata_contract.json"):
        contract = json.loads(path.read_text(encoding="utf-8"))
        identity, release = contract.get("model_identity", {}), contract.get("release", {})
        key = (str(identity.get("model_name")), str(identity.get("window_id")), str(identity.get("pipeline_id")))
        if key[0] not in FAMILIES:
            continue
        if identity.get("task") != TASK or int(identity.get("seed", -1)) != SEED:
            raise ValueError(f"Unexpected identity in {path}: {identity}")
        if release.get("release_id") != RELEASE_ID or release.get("feature_dictionary_version") != "schema_from_phase_views_v3_1":
            raise ValueError(f"Wrong LO release in {path}: {release}")
        if key in index:
            raise ValueError(f"Duplicate metadata contract for {key}")
        index[key] = {"contract": contract, "path": path, "portable_run_id": _portable_id(contract)}
    expected = {(family, f"W{window}", f"V{pipeline}")
                for family in FAMILIES for window in range(1, 4) for pipeline in range(17)}
    if set(index) != expected:
        missing, extra = sorted(expected.difference(index)), sorted(set(index).difference(expected))
        raise ValueError(f"Expected 204 LO metadata contracts; missing={missing[:3]}, extra={extra[:3]}")
    return index


def _fact_path(base: Path, fact_name: str, row: dict) -> Path:
    common = base / fact_name / f"task={TASK}" / f"feature_regime={REGIME}"
    if fact_name in {"sanity_components", "metrics_per_class", "bootstrap_metrics_per_class",
                     "checkpoint_selection", "evaluation_slices"}:
        # VastAI did not create L1 model roots on this Volume.  Keep the
        # complete run/phase/split keys as columns, while partitioning this
        # imported external evidence by backend, family and window.  This is
        # both queryable and prevents accidental collision with S3_MODEL
        # partitions written by Modal-native runs.
        return (common / f"execution_backend=vastai_portable_runner" /
                f"model_name={row['model_name']}" / f"seed={SEED}" /
                f"window_id={row['window_id']}" / "part-00000.parquet")
    if fact_name == "canonical_s_leak":
        return (common / "execution_backend=vastai_portable_runner" /
                f"seed={SEED}" / f"window_id={row['window_id']}" / "part-00000.parquet")
    raise ValueError(f"Unsupported fact {fact_name}")


def _write_idempotent(frame, path: Path) -> str:
    import pandas as pd
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        current = pd.read_parquet(path)
        # Parquet byte layout is not stable across writers; use a canonical
        # value comparison before accepting an existing immutable partition.
        if current.equals(frame):
            return "already_present"
        raise FileExistsError(f"Refusing to overwrite a non-identical L2 fact: {path}")
    frame.to_parquet(path, index=False)
    return "written"


def _load_family_facts(audit_root: Path, family: str, contract_index: dict) -> dict[str, object]:
    import pandas as pd
    root = audit_root / TASK / family / f"seed={SEED}" / TASK / family / f"seed={SEED}"
    if not root.is_dir():
        raise FileNotFoundError(f"Missing audit root: {root}")
    loaded = {name: pd.read_parquet(root / f"{name}.parquet") for name in EXPECTED_PER_FAMILY}
    for name, frame in loaded.items():
        if len(frame) != EXPECTED_PER_FAMILY[name]:
            raise ValueError(f"{family}/{name}: expected {EXPECTED_PER_FAMILY[name]} rows, got {len(frame)}")
        if set(frame["task"].astype(str)) != {TASK} or set(frame.get("model_name", pd.Series([family])).astype(str)) != {family}:
            raise ValueError(f"{family}/{name}: task/model identity mismatch")
        if "pipeline_id" not in frame.columns and name != "canonical_s_leak":
            raise ValueError(f"{family}/{name}: pipeline_id missing")
    for name, frame in loaded.items():
        if name == "canonical_s_leak":
            continue
        keys = list(zip(frame["model_name"].astype(str), frame["window_id"].astype(str), frame["pipeline_id"].astype(str)))
        missing = set(keys).difference(contract_index)
        if missing:
            raise ValueError(f"{family}/{name}: no metadata contract for {sorted(missing)[:3]}")
        frame["run_id"] = [contract_index[key]["portable_run_id"] for key in keys]
        frame["attempt_id"] = "vastai_f2_seed42_clean_20261013"
        frame["execution_backend"] = "vastai_portable_runner"
        frame["fact_source"] = "vastai_posthoc_audit_shared_v1"
        frame["l2_ingest_layout"] = "external_vastai_compact_v1"
        frame["external_metadata_contract_sha256"] = [
            _sha256(contract_index[key]["path"]) for key in keys
        ]
    return loaded


@app.function(image=image, volumes={MOUNT: volume}, cpu=4, memory=16384, timeout=60 * 60)
def ingest_lo_vastai_facts() -> str:
    """Validate and append the complete LO F1/seed42 fact bundle to L2."""
    import pandas as pd

    audit_root, artifact_root = Path("/audit_source"), Path("/artifact_source")
    contracts = _load_contract_index(artifact_root)
    base = Path(MOUNT) / f"meta_release={META_RELEASE}"
    facts_base = base / "L2_facts"
    receipt_root = base / "L0_registry" / "external_fact_ingests" / "task=LO" / "ingest_id=vastai_f2_seed42_clean_20261013"
    receipt_root.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {"written": 0, "already_present": 0}
    family_rows: dict[str, dict[str, int]] = {}
    canonical_frames = []
    for family in FAMILIES:
        loaded = _load_family_facts(audit_root, family, contracts)
        family_rows[family] = {name: len(frame) for name, frame in loaded.items()}
        canonical_frames.append(loaded.pop("canonical_s_leak"))
        for fact_name, frame in loaded.items():
            # Store one compact immutable partition for a run when that fact
            # naturally spans phases/slices; otherwise preserve phase/split.
            partition_columns = ["window_id"]
            for _, part in frame.groupby(partition_columns, dropna=False, sort=True):
                row = part.iloc[0].to_dict()
                result = _write_idempotent(part.reset_index(drop=True), _fact_path(facts_base, fact_name, row))
                counts[result] += 1

    # canonical_s_leak is independent of recurrent family.  All four audit
    # invocations must agree; only one canonical row enters L2 per key.
    canonical = pd.concat(canonical_frames, ignore_index=True)
    canonical_keys = ["window_id", "parent_pipeline", "eval_split", "phase_id"]
    canonical = canonical.sort_values(canonical_keys, kind="stable")
    canonical_rows = []
    for _, part in canonical.groupby(canonical_keys, dropna=False, sort=True):
        comparable = part.drop(columns=[], errors="ignore")
        numeric = comparable.select_dtypes(include="number").columns
        if any(comparable[column].nunique(dropna=False) > 1 for column in comparable.columns if column not in numeric):
            raise ValueError(f"Non-canonical nonnumeric leakage fact for {part.iloc[0][canonical_keys].to_dict()}")
        for column in numeric:
            if (comparable[column].max() - comparable[column].min()) > 1e-12:
                raise ValueError(f"Non-canonical numeric leakage fact {column} for {part.iloc[0][canonical_keys].to_dict()}")
        one = part.iloc[[0]].copy().reset_index(drop=True)
        one["fact_source"] = "vastai_posthoc_audit_shared_v1"
        one["execution_backend"] = "vastai_portable_runner"
        one["l2_ingest_layout"] = "external_vastai_compact_v1"
        canonical_rows.append(one)
    canonical_unique = pd.concat(canonical_rows, ignore_index=True)
    for _, one in canonical_unique.groupby(["window_id"], dropna=False, sort=True):
        result = _write_idempotent(one.reset_index(drop=True), _fact_path(facts_base, "canonical_s_leak", one.iloc[0].to_dict()))
        counts[result] += 1

    receipt = {
        "ingest_id": "vastai_f2_seed42_clean_20261013",
        "task": TASK,
        "release_id": RELEASE_ID,
        "feature_regime": REGIME,
        "seed": SEED,
        "execution_backend": "vastai_portable_runner",
        "source_audit_root": str(AUDIT_LOCAL_ROOT),
        "source_artifact_root": str(ARTIFACT_LOCAL_ROOT),
        "source_audit_tree_sha256": _sha256(Path("/audit_source") / TASK / "RNN" / f"seed={SEED}" / TASK / "RNN" / f"seed={SEED}" / "sanity_components.parquet"),
        "contract_count": len(contracts),
        "families": family_rows,
        "partitions": counts,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (receipt_root / "receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    volume.commit()
    # A string return supports ``modal run --write-result``.  That gives a
    # local, machine-readable receipt even with CLI versions that do not print
    # a remote function's structured return value.
    return json.dumps(receipt, indent=2)


@app.function(image=image, volumes={MOUNT: volume}, cpu=1, memory=2048, timeout=20 * 60)
def ingest_status() -> str:
    """Read-only completeness check for the external LO F1 fact ingest."""
    import pandas as pd

    base = Path(MOUNT) / f"meta_release={META_RELEASE}"
    receipt = base / "L0_registry" / "external_fact_ingests" / "task=LO" / "ingest_id=vastai_f2_seed42_clean_20261013" / "receipt.json"
    # Compact external layout: one fact partition per recurrent family and
    # window; canonical S_leak is shared across families.
    expected_files = {"sanity_components": 4 * 3,
                      "metrics_per_class": 4 * 3,
                      "bootstrap_metrics_per_class": 4 * 3,
                      "checkpoint_selection": 4 * 3,
                      "evaluation_slices": 4 * 3,
                      "canonical_s_leak": 3}
    actual: dict[str, int] = {}
    for fact_name in expected_files:
        root = (base / "L2_facts" / fact_name / "task=LO" /
                f"feature_regime={REGIME}" / "execution_backend=vastai_portable_runner")
        actual[fact_name] = len(list(root.rglob("*.parquet"))) if root.is_dir() else 0
    return json.dumps({
        "receipt_exists": receipt.is_file(),
        "receipt": json.loads(receipt.read_text(encoding="utf-8")) if receipt.is_file() else None,
        "expected_minimum_partitions": expected_files,
        "actual_task_partitions": actual,
    }, indent=2)


@app.local_entrypoint()
def cli(mode: str = "ingest") -> None:
    if mode == "ingest":
        result = ingest_lo_vastai_facts.remote()
    elif mode == "status":
        result = ingest_status.remote()
    else:
        raise ValueError("mode must be ingest or status")
    print(result)
