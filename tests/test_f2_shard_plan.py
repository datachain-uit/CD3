"""A shard plan partitions the remaining cells exactly once and the verifier fails closed on gaps, extras and mixed runners."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import f2_shard_plan as shard_mod  # noqa: E402


def _write_run(root: Path, cell: dict, **overrides) -> None:
    directory = shard_mod.run_dir(root, cell)
    directory.mkdir(parents=True, exist_ok=True)
    manifest = {"run_status": "SUCCESS", "runner_git_commit": "7886a85", "model_revision": "patchtst_channel_independent_v2_1_math_sdp",
                "static_layout_policy": "current", "reference_layout_sha256": None, "batch_size": 2048, "micro_batch_size": 512,
                "accumulation_steps": 4, "seed": cell["seed"], **overrides}
    (directory / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (directory / "train_history.parquet").write_bytes(b"\x00")


def test_pilot_cells_are_excluded_and_every_remaining_cell_lands_in_exactly_one_shard(tmp_path: Path) -> None:
    pilot = tmp_path / "pilot"
    for window in shard_mod.WINDOWS:
        _write_run(pilot, {"task": "CQ", "window_id": window, "pipeline_id": "V0", "model_name": "PATCHTST", "seed": 42})
    plan = shard_mod.build_plan("CQ", "PATCHTST", 42, 6, exclude_completed=pilot)
    assert plan["grid_cells"] == 51 and plan["excluded_completed"] == 3 and len(plan["cells"]) == 48
    assert sorted(len(v) for v in plan["shards"].values()) == [8] * 6
    seen = [(c["window_id"], c["pipeline_id"]) for c in plan["cells"]]
    assert len(set(seen)) == 48 and ("W1", "V0") not in seen
    assert [c["cell_index"] for c in shard_mod.shard_cells(plan, 0)] == list(range(0, 48, 6))
    again = shard_mod.build_plan("CQ", "PATCHTST", 42, 6, exclude_completed=pilot)
    assert again["plan_sha256"] == plan["plan_sha256"]


def test_verify_reports_missing_unplanned_and_non_uniform_runs(tmp_path: Path) -> None:
    plan = shard_mod.build_plan("CQ", "PATCHTST", 42, 2, windows=("W1",), pipelines=("V1", "V2", "V3"))
    root = tmp_path / "runs"
    for cell in plan["cells"][:2]:
        _write_run(root, cell)
    report = shard_mod.verify(plan, root, expect_static_layout_policy="current")
    assert report["found"] == 2 and report["missing"] == [{"window_id": "W1", "pipeline_id": "V3"}] and not report["complete"]
    _write_run(root, plan["cells"][2], runner_git_commit="deadbeef")
    _write_run(root, {"task": "CQ", "window_id": "W1", "pipeline_id": "V9", "model_name": "PATCHTST", "seed": 42})
    report = shard_mod.verify(plan, root, expect_static_layout_policy="historical_reference")
    assert report["missing"] == [] and len(report["unplanned_manifests"]) == 1
    assert report["non_uniform"] == {"runner_git_commit": ["7886a85", "deadbeef"]}
    assert len(report["static_layout_policy_mismatch"]) == 3 and not report["complete"]


def test_cli_round_trip(tmp_path: Path) -> None:
    out = tmp_path / "plan.json"
    assert shard_mod.main(["plan", "--task", "LO", "--model-name", "PATCHTST", "--seed", "43", "--shard-count", "3", "--out", str(out)]) == 0
    plan = json.loads(out.read_text(encoding="utf-8"))
    assert plan["grid_cells"] == 51 and plan["excluded_completed"] == 0 and sorted(len(v) for v in plan["shards"].values()) == [17, 17, 17]
    root = tmp_path / "runs"
    for cell in plan["cells"]:
        _write_run(root, cell)
    assert shard_mod.main(["verify", "--plan", str(out), "--run-root", str(root), "--expect-static-layout-policy", "current"]) == 0
    assert shard_mod.main(["cells", "--plan", str(out), "--shard", "2"]) == 0
