#!/usr/bin/env python3
"""Deterministic shard plan for running a model grid on several VastAI instances at once.

The existing launchers (``tools/vastai_run_cq_patchtst_grid.sh``, ``tools/vastai_run_family.sh``) walk every
cell sequentially and skip a cell only when its run directory exists on the *local* disk, so two instances
started with the same script would train the same cells twice.  This tool assigns every cell of a grid to
exactly one shard (``cell_index % shard_count``), writes the plan with its sha256 so that the ingest can
prove that the union of the shards is the whole grid, and verifies a run root against the plan.

Plan::

    python tools/f2_shard_plan.py plan --task CQ --model-name PATCHTST --seed 42 --shard-count 6 \
        --exclude-completed <pilot run root> --out shard_plan.json

Verify (after the shards were downloaded under one run root)::

    python tools/f2_shard_plan.py verify --plan shard_plan.json --run-root <root> \
        --expect-static-layout-policy current

``verify`` exits 1 when a planned cell has no SUCCESS manifest, when a manifest is found for a cell that is
not in the plan, or when the runs do not share one runner commit, model revision, layout policy, batch
contract and seed (the same uniform-execution rule the L2 ingest asserts).
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

WINDOWS = ("W1", "W2", "W3")
PIPELINES = tuple(f"V{i}" for i in range(17))
UNIFORM_FIELDS = ("runner_git_commit", "model_revision", "static_layout_policy", "reference_layout_sha256",
                  "batch_size", "micro_batch_size", "accumulation_steps", "seed",
                  # training protocol (per-run options since 044d6c7) and the static contract id (8d105db)
                  "learning_rate", "warmup_epochs", "gradient_clip_norm", "run_purpose", "static_feature_contract_id")
# Manifests written before these options existed ran the registered values.
FIELD_DEFAULTS = {"warmup_epochs": 0, "gradient_clip_norm": None, "run_purpose": "PRIMARY_GRID", "learning_rate": 1e-3}


def canonical_cells(task: str, model_name: str, seed: int, *, windows=WINDOWS, pipelines=PIPELINES) -> list[dict[str, Any]]:
    """Window-major, pipeline-minor order; the order is part of the plan identity."""
    return [{"task": task, "window_id": window, "pipeline_id": pipeline, "model_name": model_name, "seed": seed}
            for window in windows for pipeline in pipelines]


def run_dir(root: Path, cell: dict[str, Any]) -> Path:
    return root / cell["task"] / cell["window_id"] / cell["pipeline_id"] / cell["model_name"] / f"seed={cell['seed']}"


def completed(root: Path, cell: dict[str, Any]) -> bool:
    manifest = run_dir(root, cell) / "run_manifest.json"
    if not manifest.is_file():
        return False
    try:
        return json.loads(manifest.read_text(encoding="utf-8")).get("run_status", "SUCCESS") == "SUCCESS"
    except (OSError, ValueError):
        return False


def build_plan(task: str, model_name: str, seed: int, shard_count: int, *,
               exclude_completed: Path | None = None, windows=WINDOWS, pipelines=PIPELINES) -> dict[str, Any]:
    if shard_count < 1:
        raise ValueError("shard_count must be >= 1")
    cells = canonical_cells(task, model_name, seed, windows=windows, pipelines=pipelines)
    excluded = [cell for cell in cells if exclude_completed is not None and completed(exclude_completed, cell)]
    remaining = [cell for cell in cells if cell not in excluded]
    for index, cell in enumerate(remaining):
        cell["cell_index"] = index
        cell["shard"] = index % shard_count
    payload = {
        "plan_version": "f2_shard_plan_v1", "task": task, "model_name": model_name, "seed": seed,
        "shard_count": shard_count, "grid_cells": len(cells), "excluded_completed": len(excluded),
        "excluded": [{k: c[k] for k in ("window_id", "pipeline_id")} for c in excluded],
        "cells": remaining,
        "shards": {str(k): [c["cell_index"] for c in remaining if c["shard"] == k] for k in range(shard_count)},
    }
    payload["plan_sha256"] = "sha256:" + hashlib.sha256(
        json.dumps({k: v for k, v in payload.items()}, sort_keys=True).encode("utf-8")).hexdigest()
    return payload


def shard_cells(plan: dict[str, Any], shard: int) -> list[dict[str, Any]]:
    if not 0 <= shard < plan["shard_count"]:
        raise ValueError(f"shard {shard} outside 0..{plan['shard_count'] - 1}")
    return [cell for cell in plan["cells"] if cell["shard"] == shard]


def verify(plan: dict[str, Any], run_root: Path, *, expect_static_layout_policy: str | None = None,
           expect_run_purpose: str = "PRIMARY_GRID") -> dict[str, Any]:
    missing: list[dict[str, str]] = []
    manifests: dict[str, dict[str, Any]] = {}
    for cell in plan["cells"]:
        path = run_dir(run_root, cell) / "run_manifest.json"
        if not completed(run_root, cell):
            missing.append({"window_id": cell["window_id"], "pipeline_id": cell["pipeline_id"]})
            continue
        manifests[f"{cell['window_id']}/{cell['pipeline_id']}"] = json.loads(path.read_text(encoding="utf-8"))
    planned = {(c["window_id"], c["pipeline_id"]) for c in plan["cells"]}
    excluded = {(c["window_id"], c["pipeline_id"]) for c in plan["excluded"]}
    unplanned = []
    for path in sorted(run_root.rglob("run_manifest.json")):
        parts = path.parts  # .../<task>/<window>/<pipeline>/<model>/seed=<seed>/run_manifest.json
        if len(parts) < 6:
            continue
        same_grid = (parts[-6] == plan["task"] and parts[-3] == plan["model_name"] and parts[-2] == f"seed={plan['seed']}")
        if same_grid and (parts[-5], parts[-4]) not in planned and (parts[-5], parts[-4]) not in excluded:
            unplanned.append(str(path))
    values = {field: sorted({str(m.get(field, FIELD_DEFAULTS.get(field))) for m in manifests.values()})
              for field in UNIFORM_FIELDS}
    non_uniform = {field: vals for field, vals in values.items() if len(vals) > 1}
    policy_mismatch = []
    if expect_static_layout_policy is not None:
        policy_mismatch = [key for key, m in manifests.items() if m.get("static_layout_policy") != expect_static_layout_policy]
    purpose_mismatch = [key for key, m in manifests.items()
                        if (m.get("run_purpose") or "PRIMARY_GRID") != expect_run_purpose]
    report = {
        "plan_sha256": plan["plan_sha256"], "planned": len(plan["cells"]), "found": len(manifests),
        "missing": missing, "unplanned_manifests": unplanned, "non_uniform": non_uniform,
        "static_layout_policy_mismatch": policy_mismatch,
        "run_purpose_mismatch": purpose_mismatch,
        "uniform_values": {field: vals[0] if len(vals) == 1 else None for field, vals in values.items()},
        "histories_present": sum((run_dir(run_root, c) / "train_history.parquet").is_file() for c in plan["cells"]),
    }
    report["complete"] = not (missing or unplanned or non_uniform or policy_mismatch or purpose_mismatch)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("--task", required=True, choices=("CQ", "LO"))
    plan.add_argument("--model-name", required=True)
    plan.add_argument("--seed", type=int, required=True)
    plan.add_argument("--shard-count", type=int, required=True)
    plan.add_argument("--exclude-completed", type=Path, default=None, help="run root whose SUCCESS cells are left out (e.g. the pilot)")
    plan.add_argument("--out", type=Path, required=True)
    cells = sub.add_parser("cells", help="print the cells of one shard as 'window pipeline' lines for a shell loop")
    cells.add_argument("--plan", type=Path, required=True)
    cells.add_argument("--shard", type=int, required=True)
    ver = sub.add_parser("verify")
    ver.add_argument("--plan", type=Path, required=True)
    ver.add_argument("--run-root", type=Path, required=True)
    ver.add_argument("--expect-static-layout-policy", default=None)
    ver.add_argument("--expect-run-purpose", default="PRIMARY_GRID",
                     help="pilot and ablation runs (STABILITY_PILOT_D23, EXPLORATORY_STATIC_ABLATION) never complete a grid")
    ver.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.command == "plan":
        payload = build_plan(args.task, args.model_name, args.seed, args.shard_count, exclude_completed=args.exclude_completed)
        args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(json.dumps({k: payload[k] for k in ("plan_sha256", "grid_cells", "excluded_completed", "shard_count")}))
        print(json.dumps({k: len(v) for k, v in payload["shards"].items()}))
        return 0
    loaded = json.loads(args.plan.read_text(encoding="utf-8"))
    if args.command == "cells":
        for cell in shard_cells(loaded, args.shard):
            print(cell["window_id"], cell["pipeline_id"])
        return 0
    report = verify(loaded, args.run_root, expect_static_layout_policy=args.expect_static_layout_policy,
                    expect_run_purpose=args.expect_run_purpose)
    if args.out is not None:
        args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
