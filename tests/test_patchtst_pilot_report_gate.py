"""The PatchTST pilot report must read and enforce the manifest contract."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
pytest.importorskip("docx")
spec = importlib.util.spec_from_file_location(
    "patchtst_report", ROOT / "tools" / "build_cq_current_recurrent_patchtst_report.py"
)
report_mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = report_mod
assert spec.loader is not None
spec.loader.exec_module(report_mod)

MANIFEST = {
    "model_revision": "patchtst_channel_independent_v2_1_math_sdp",
    "batch_size": 2048,
    "micro_batch_size": 512,
    "accumulation_steps": 4,
    "static_ablation": "none",
    "run_purpose": "PRIMARY_GRID",
    "pipeline_id": "V0",
    "model_name": "PATCHTST",
    "seed": 42,
    "static_layout_policy": "current",
    "reference_layout_sha256": None,
    "runner_git_commit": "abc123",
    "best_epoch": 2,
    "elapsed_seconds": 123.4,
    "energy_measurement_type": "NVML_POWER_SAMPLING_ESTIMATE",
    "energy_gpu_estimated_kwh": 0.0123,
    "nvml_gpu_name": "NVIDIA L4",
    "train_rows": 10,
    "validation_rows": 5,
    "test_rows": {"P1": 7},
}


def _write_pilot(root: Path, overrides: dict[str, dict] | None = None) -> None:
    for window in report_mod.WINDOWS:
        manifest = {**MANIFEST, "window_id": window, **(overrides or {}).get(window, {})}
        path = root / window
        path.mkdir(parents=True, exist_ok=True)
        (path / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (path / "feature_layout.json").write_text(json.dumps({"layout": "current"}), encoding="utf-8")
        pd.DataFrame({
            "epoch": [1, 2, 3],
            "train_cross_entropy_mean_p1_p4": [0.9, 0.8, 0.7],
            "validation_macro_f1_mean_p1_p4": [0.5, 0.6, 0.55],
            "validation_cross_entropy_mean_p1_p4": [0.8, 0.7, 0.75],
            "epoch_seconds": [1.0, 1.0, 1.0],
        }).to_parquet(path / "train_history.parquet", index=False)


def test_conforming_pilot_has_three_receipts_and_marks_selected_epoch(tmp_path: Path) -> None:
    _write_pilot(tmp_path)
    assert report_mod.patchtst_provenance(tmp_path).window_id.tolist() == ["W1", "W2", "W3"]
    history = report_mod.patchtst_history(tmp_path)
    assert history.loc[history.selected == "YES", "epoch"].tolist() == [2, 2, 2]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("accumulation_steps", 1),
        ("micro_batch_size", 2048),
        ("model_revision", "patchtst_v1"),
        ("static_ablation", "no_static"),
        ("run_purpose", "EXPLORATORY_STATIC_ABLATION"),
        ("pipeline_id", "V8"),
    ],
)
def test_protocol_deviation_fails_closed(tmp_path: Path, field: str, value: object) -> None:
    _write_pilot(tmp_path, {"W2": {field: value}})
    with pytest.raises(ValueError, match="deviates|identity"):
        report_mod.patchtst_provenance(tmp_path)


def test_mixed_layout_or_commit_fails_closed(tmp_path: Path) -> None:
    _write_pilot(tmp_path, {"W3": {
        "static_layout_policy": "historical_reference",
        "reference_layout_sha256": "sha256:" + "a" * 64,
    }})
    with pytest.raises(ValueError, match="static_layout_policy"):
        report_mod.patchtst_provenance(tmp_path)
    _write_pilot(tmp_path, {"W1": {"runner_git_commit": "other"}})
    with pytest.raises(ValueError, match="runner_git_commit"):
        report_mod.patchtst_provenance(tmp_path)


def test_missing_manifest_is_not_silently_blank(tmp_path: Path) -> None:
    _write_pilot(tmp_path)
    (tmp_path / "W2" / "run_manifest.json").unlink()
    with pytest.raises(FileNotFoundError):
        report_mod.patchtst_provenance(tmp_path)
