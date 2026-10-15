"""Portable-backend ingestion helpers: hash-verified resources, uniform execution, grain check."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import types
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


def _load_ingest_module(tmp_path: Path):
    """Import the Modal app module without Modal: stub the SDK and point the bundle roots at tmp dirs."""
    (tmp_path / "audits").mkdir(exist_ok=True)
    stub = types.ModuleType("modal")

    class _Image:
        @staticmethod
        def debian_slim(**_):
            return _Image()

        def pip_install(self, *_, **__):
            return self

        def add_local_dir(self, *_, **__):
            return self

    class _App:
        def __init__(self, *_: object, **__: object) -> None:
            pass

        def function(self, **_):
            return lambda fn: fn

        def local_entrypoint(self):
            return lambda fn: fn

    class _Volume:
        @staticmethod
        def from_name(*_, **__):
            return object()

    stub.Image, stub.App, stub.Volume = _Image, _App, _Volume
    saved = sys.modules.get("modal")
    sys.modules["modal"] = stub
    import os
    os.environ["LO_VASTAI_AUDIT_ROOT"] = str(tmp_path / "audits")
    os.environ["LO_VASTAI_ARTIFACT_ROOT"] = str(tmp_path)
    try:
        spec = importlib.util.spec_from_file_location("ingest_lo_vastai_facts_app",
                                                      ROOT / "modal_jobs" / "ingest_lo_vastai_facts_app.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        if saved is not None:
            sys.modules["modal"] = saved
        else:
            sys.modules.pop("modal", None)
    return module


def _write_run(run_dir: Path, *, gpu: str = "NVIDIA L4", runner: str = "sha256:" + "a" * 64, with_history: bool = True) -> tuple[dict, Path]:
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"elapsed_seconds": 300.5, "peak_ram_mb": 21000.0, "gpu": gpu, "torch_version": "2.4.0+cu121",
                "batch_size": 2048, "micro_batch_size": 2048, "accumulation_steps": 1, "best_epoch": 3,
                "model_revision": "recurrent_shared_phase_v2_4_prefixsafe_epoch50",
                "energy_measurement": "ESTIMATED", "energy_measurement_type": "NVML_POWER_SAMPLING_ESTIMATE",
                "energy_gpu_estimated_kwh": 0.0012, "energy_gpu_run_kwh": None, "energy_sample_count": 300,
                "energy_sampling_interval_seconds": 1.0, "energy_missing_sample_rate": 0.0}
    manifest_path = run_dir / "run_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    digest = "sha256:" + hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    if with_history:
        pd.DataFrame({"epoch": [1, 2, 3], "train_seconds": [90.0, 95.0, 100.0]}).to_parquet(run_dir / "train_history.parquet", index=False)
    contract = {"lineage": {"run_manifest_sha256": digest, "runner_sha256": runner, "release_contract_sha256": "sha256:" + "b" * 64},
                "execution": {"gpu": gpu}}
    contract_path = run_dir / "metadata_contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    return contract, contract_path


def test_resources_come_from_the_hash_verified_run_manifest(tmp_path: Path) -> None:
    module = _load_ingest_module(tmp_path)
    contract, contract_path = _write_run(tmp_path / "LO" / "W1" / "V0" / "RNN" / "seed=42")
    resources = module.run_resources(contract, contract_path)
    assert resources["elapsed_seconds"] == 300.5 and resources["gpu"] == "NVIDIA L4"
    assert resources["train_seconds"] == pytest.approx(285.0) and resources["epochs_run"] == 3
    assert resources["energy_measurement_type"] == "NVML_POWER_SAMPLING_ESTIMATE" and resources["energy_gpu_run_kwh"] is None
    assert resources["model_revision"] == "recurrent_shared_phase_v2_4_prefixsafe_epoch50"
    # tampering with the manifest after the sidecar was written is refused
    manifest_path = contract_path.parent / "run_manifest.json"
    edited = json.loads(manifest_path.read_text()); edited["elapsed_seconds"] = 1.0
    manifest_path.write_text(json.dumps(edited), encoding="utf-8")
    with pytest.raises(ValueError, match="differs from the sidecar hash"):
        module.run_resources(contract, contract_path)


def test_uniform_execution_requires_one_runner_revision_and_the_registered_gpu(tmp_path: Path) -> None:
    module = _load_ingest_module(tmp_path)
    a = _write_run(tmp_path / "LO" / "W1" / "V0" / "RNN" / "seed=42")
    b = _write_run(tmp_path / "LO" / "W1" / "V1" / "RNN" / "seed=42")
    contracts = {("RNN", "W1", "V0"): {"contract": a[0], "path": a[1]}, ("RNN", "W1", "V1"): {"contract": b[0], "path": b[1]}}
    summary = module.assert_uniform_execution(contracts)
    assert summary["gpu"] == ["NVIDIA L4"] and summary["runner_sha256"].startswith("sha256:a")
    c = _write_run(tmp_path / "LO" / "W1" / "V2" / "RNN" / "seed=42", runner="sha256:" + "c" * 64)
    contracts[("RNN", "W1", "V2")] = {"contract": c[0], "path": c[1]}
    with pytest.raises(ValueError, match="runner revisions"):
        module.assert_uniform_execution(contracts)
    d = _write_run(tmp_path / "LO" / "W1" / "V3" / "RNN" / "seed=42", gpu="NVIDIA A10")
    with pytest.raises(ValueError, match="GPUs other than"):
        module.assert_uniform_execution({("RNN", "W1", "V3"): {"contract": d[0], "path": d[1]}, ("RNN", "W1", "V0"): contracts[("RNN", "W1", "V0")]})


def test_input_verifier_flags_duplicate_enrollments() -> None:
    from vastai_verify_parquet_inputs import grain_violation
    clean = pa.table({"enrollment_id": ["e1", "e2", "e3"], "x": [1.0, 2.0, 3.0]})
    duplicated = pa.table({"enrollment_id": ["e1", "e1", "e3"], "x": [1.0, 2.0, 3.0]})
    assert grain_violation(clean) is None
    assert grain_violation(duplicated) == "rows=3 distinct enrollment_id=2"
    assert grain_violation(pa.table({"x": [1.0]})) == "no enrollment_id column"
