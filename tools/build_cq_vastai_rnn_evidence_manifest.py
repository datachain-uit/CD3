"""Create a compact download manifest for immutable CQ RNN comparison evidence.

The local r2 export already retains aggregate metrics, sanity, calibration,
bootstrap and resource facts.  This manifest fetches only the run provenance
and row-level predictions needed for paired RNN-versus-new-model analyses.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
FACTS = ROOT / "_tmp_cq_rnn_r3_facts" / "report_id=RNN_seed42_v2_2_clean_20261007_r2"
OUT = ROOT / "downloads" / "vastai" / "CQ_V2_2_clean_grain_seed42" / "rnn_evidence"


def remote(path: str) -> str:
    if not path.startswith("/data/"):
        raise ValueError(f"Expected Modal mount path, got {path!r}")
    return path.removeprefix("/data/")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--windows", nargs="+", default=["W1"])
    parser.add_argument("--pipelines", nargs="+", default=["V0"])
    parser.add_argument("--include-validation", action="store_true")
    args = parser.parse_args()

    inventory = pd.read_parquet(FACTS / "run_inventory.parquet")
    selected = inventory[
        inventory.window_id.isin(args.windows) & inventory.pipeline_id.isin(args.pipelines)
    ].sort_values(["window_id", "pipeline_id"])
    expected = len(args.windows) * len(args.pipelines)
    if len(selected) != expected:
        raise ValueError(f"Selected {len(selected)} RNN cells; expected {expected}. Check windows/pipelines.")
    if selected.data_release_id.nunique() != 1:
        raise ValueError("RNN evidence selection mixes data releases")

    files = []
    for row in selected.itertuples(index=False):
        root = (
            f"meta_release=imputation-v1/L1_runs/task=CQ/feature_regime=CQ_RAW_EARLY/"
            f"window_id={row.window_id}/pipeline_id={row.pipeline_id}/model_name=RNN/seed=42/"
            f"run_id={row.run_id}/attempt_id={row.attempt_id}"
        )
        local_root = f"{row.window_id}/{row.pipeline_id}/seed42"
        for name in ("run_manifest.json", "feature_layout.json", "train_history.parquet", "timing.parquet"):
            files.append({"remote_path": f"{root}/{name}", "local_path": f"{local_root}/{name}", "kind": "provenance"})
        splits = ["TEST"] + (["VALIDATION"] if args.include_validation else [])
        for split in splits:
            for phase in ("P1", "P2", "P3", "P4"):
                files.append({
                    "remote_path": f"{root}/predictions/eval_split={split}/phase_id={phase}/part-00000.parquet",
                    "local_path": f"{local_root}/predictions/{split}/phase_id={phase}.parquet",
                    "kind": "prediction",
                })

    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {
        "task": "CQ", "model_name": "RNN", "seed": 42,
        "release_id": "CQ_V2_2", "data_release_id": selected.data_release_id.iloc[0],
        "source_report_export": str(FACTS.relative_to(ROOT)),
        "aggregate_facts_already_local": [path.name for path in FACTS.glob("*.parquet")],
        "selected_cells": selected[["window_id", "pipeline_id", "run_id", "attempt_id"]].to_dict("records"),
        "files": files,
    }
    (OUT / "download_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"cells": len(selected), "files": len(files), "prediction_files": sum(x["kind"] == "prediction" for x in files)}))


if __name__ == "__main__":
    main()
