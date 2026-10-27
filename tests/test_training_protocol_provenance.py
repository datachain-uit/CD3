"""Training-protocol provenance after 044d6c7: contract identity, ingest uniformity, shard verification, D-23 criterion."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import f2_shard_plan as shard_mod  # noqa: E402
import vastai_metadata_contract as contract_mod  # noqa: E402


def test_registered_protocol_leaves_the_identity_key_unchanged_and_a_pilot_protocol_separates_it() -> None:
    registered = {"learning_rate": 1e-3}                      # pre-044d6c7 manifests carry no warm-up / clip keys
    assert contract_mod.training_protocol(registered) == contract_mod.REGISTERED_TRAINING_PROTOCOL
    d23 = {"learning_rate": 3e-4, "warmup_epochs": 1, "gradient_clip_norm": 1.0, "run_purpose": "STABILITY_PILOT_D23"}
    assert contract_mod.training_protocol(d23) != contract_mod.REGISTERED_TRAINING_PROTOCOL
    assert contract_mod.training_protocol({"learning_rate": 1e-3, "warmup_epochs": 0, "gradient_clip_norm": None,
                                           "run_purpose": "PRIMARY_GRID"}) == contract_mod.REGISTERED_TRAINING_PROTOCOL


def _ingest_module(tmp_path: Path):
    # ``tests`` is also an installed third-party package in some environments;
    # loading the sibling helper by file path keeps this test bound to CD3.
    spec = importlib.util.spec_from_file_location(
        "cd3_test_vastai_ingest_and_verify",
        ROOT / "tests" / "test_vastai_ingest_and_verify.py",
    )
    helper = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(helper)
    return helper._load_ingest_module(tmp_path)


def _contract(runner: str = "sha256:" + "a" * 64, **protocol) -> dict:
    return {"lineage": {"runner_sha256": runner, "release_contract_sha256": "sha256:" + "b" * 64},
            "execution": {"gpu": "NVIDIA L4"},
            "model_identity": {"model_revision": "patchtst_channel_independent_v2_1_math_sdp", "learning_rate": 1e-3,
                               "static_layout_policy": "current", "batch_size": 2048, "accumulation_steps": 4},
            **({"training_protocol": protocol} if protocol else {})}


def test_ingest_requires_one_training_protocol_and_refuses_pilot_runs(tmp_path: Path) -> None:
    module = _ingest_module(tmp_path)
    registered = {("PATCHTST", "W1", "V1"): {"contract": _contract(), "path": tmp_path / "a"},
                  ("PATCHTST", "W1", "V2"): {"contract": _contract(learning_rate=1e-3, warmup_epochs=0, gradient_clip_norm=None,
                                                                   run_purpose="PRIMARY_GRID"), "path": tmp_path / "b"}}
    summary = module.assert_uniform_execution(registered)   # an old contract and a new registered one agree
    assert summary["training_protocol"]["learning_rate"] == pytest.approx(1e-3) and summary["training_protocol"]["warmup_epochs"] == 0
    mixed = dict(registered)
    mixed[("PATCHTST", "W1", "V3")] = {"contract": _contract(learning_rate=3e-4, warmup_epochs=1, gradient_clip_norm=1.0,
                                                             run_purpose="PRIMARY_GRID"), "path": tmp_path / "c"}
    with pytest.raises(ValueError, match="training protocols"):
        module.assert_uniform_execution(mixed)
    pilots = {("PATCHTST", "W2", "V0"): {"contract": _contract(learning_rate=3e-4, warmup_epochs=1, gradient_clip_norm=1.0,
                                                               run_purpose="STABILITY_PILOT_D23"), "path": tmp_path / "d"}}
    with pytest.raises(ValueError, match="non-primary"):
        module.assert_uniform_execution(pilots)


def _write_run(root: Path, cell: dict, **overrides) -> None:
    directory = shard_mod.run_dir(root, cell)
    directory.mkdir(parents=True, exist_ok=True)
    manifest = {"run_status": "SUCCESS", "runner_git_commit": "af079d8", "model_revision": "patchtst_channel_independent_v2_1_math_sdp",
                "static_layout_policy": "current", "reference_layout_sha256": None, "batch_size": 2048, "micro_batch_size": 512,
                "accumulation_steps": 4, "seed": cell["seed"], "learning_rate": 1e-3, **overrides}
    (directory / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_shard_verify_flags_a_mixed_or_non_primary_training_protocol(tmp_path: Path) -> None:
    plan = shard_mod.build_plan("CQ", "PATCHTST", 42, 1, windows=("W1",), pipelines=("V1", "V2", "V3"))
    root = tmp_path / "runs"
    _write_run(root, plan["cells"][0])                                                    # pre-044d6c7 style manifest
    _write_run(root, plan["cells"][1], warmup_epochs=0, gradient_clip_norm=None, run_purpose="PRIMARY_GRID")
    _write_run(root, plan["cells"][2], warmup_epochs=0, gradient_clip_norm=None, run_purpose="PRIMARY_GRID")
    assert shard_mod.verify(plan, root, expect_static_layout_policy="current")["complete"]
    _write_run(root, plan["cells"][2], learning_rate=3e-4, warmup_epochs=1, gradient_clip_norm=1.0, run_purpose="STABILITY_PILOT_D23")
    report = shard_mod.verify(plan, root, expect_static_layout_policy="current")
    assert set(report["non_uniform"]) >= {"learning_rate", "warmup_epochs", "gradient_clip_norm", "run_purpose"}
    assert report["run_purpose_mismatch"] == ["W1/V3"] and not report["complete"]


def test_f2_report_gate_rejects_an_unregistered_optimisation_protocol(tmp_path: Path) -> None:
    pytest.importorskip("docx")
    spec = importlib.util.spec_from_file_location("patchtst_report_gate", ROOT / "tools" / "build_cq_current_recurrent_patchtst_report.py")
    report_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(report_mod)
    base = {"model_revision": "patchtst_channel_independent_v2_1_math_sdp", "batch_size": 2048, "micro_batch_size": 512,
            "accumulation_steps": 4, "static_ablation": "none", "run_purpose": "PRIMARY_GRID", "pipeline_id": "V0",
            "model_name": "PATCHTST", "seed": 42, "static_layout_policy": "current", "reference_layout_sha256": None,
            "runner_git_commit": "af079d8", "best_epoch": 2, "elapsed_seconds": 1.0, "energy_measurement_type": "NVML",
            "energy_gpu_estimated_kwh": 0.1, "nvml_gpu_name": "NVIDIA L4", "test_rows": {"P1": 1}, "learning_rate": 1e-3}
    for window in report_mod.WINDOWS:
        (tmp_path / window).mkdir()
        (tmp_path / window / "run_manifest.json").write_text(json.dumps({**base, "window_id": window}), encoding="utf-8")
        (tmp_path / window / "feature_layout.json").write_text("{}", encoding="utf-8")
    assert len(report_mod.patchtst_provenance(tmp_path)) == 3                      # registered protocol, keys absent -> defaults
    (tmp_path / "W2" / "run_manifest.json").write_text(json.dumps({**base, "window_id": "W2", "learning_rate": 3e-4,
                                                                   "warmup_epochs": 1, "gradient_clip_norm": 1.0}), encoding="utf-8")
    with pytest.raises(ValueError, match="learning_rate"):
        report_mod.patchtst_provenance(tmp_path)


def test_d23_criterion_is_evaluated_on_the_validation_curve() -> None:
    spec = importlib.util.spec_from_file_location("d23_report", ROOT / "tools" / "build_cq_d23_configuration_report.py")
    pytest.importorskip("docx")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    oscillating = pd.DataFrame({"epoch": [1, 2, 3, 4, 5, 6], "validation_macro_f1_mean_p1_p4": [0.76, 0.61, 0.74, 0.73, 0.75, 0.71],
                                "validation_cross_entropy_mean_p1_p4": [0.09] * 6, "train_cross_entropy_mean_p1_p4": [0.20, 0.43, 0.25, 0.10, 0.15, 0.09]})
    stats = mod.stability_statistics(oscillating, best_epoch=1)
    assert stats["selected_epoch"] == 1 and stats["train_ce_spike_epochs"] == [2] and stats["max_abs_step"] == pytest.approx(0.15)
    assert not mod.d23_criterion_met(stats)
    improving = pd.DataFrame({"epoch": [1, 2, 3, 4], "validation_macro_f1_mean_p1_p4": [0.60, 0.66, 0.70, 0.69],
                              "validation_cross_entropy_mean_p1_p4": [0.1] * 4, "train_cross_entropy_mean_p1_p4": [0.3, 0.2, 0.15, 0.12]})
    stats = mod.stability_statistics(improving, best_epoch=3)
    assert stats["criterion_selected_epoch_gt_1"] and stats["criterion_unimodal_no_spike"] and mod.d23_criterion_met(stats)
    # a clean early peak (selection at epoch 1, steady decline afterwards, no spike) is stable optimisation meeting drift
    drift = pd.DataFrame({"epoch": [1, 2, 3, 4, 5, 6], "validation_macro_f1_mean_p1_p4": [0.76, 0.75, 0.74, 0.74, 0.72, 0.71],
                          "validation_cross_entropy_mean_p1_p4": [0.09] * 6, "train_cross_entropy_mean_p1_p4": [0.20, 0.15, 0.12, 0.10, 0.09, 0.09]})
    stats = mod.stability_statistics(drift, best_epoch=1)
    assert not stats["criterion_selected_epoch_gt_1"] and stats["criterion_unimodal_no_spike"] and mod.d23_criterion_met(stats)
    table = mod.stability_comparison({"D23 W2": stats})
    assert table.loc[0, "Tiêu chí D-23 (b)"] == "ĐẠT"
