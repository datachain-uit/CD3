"""Build the exact clean-grain CQ model-input download manifest for VastAI.

The r2 RNN inventory is authoritative: it identifies the actual selected S1
and S2 parents for every W1--W3/V0--V16 seed-42 model cell.  Validation and
test inputs are deduplicated by their parent imputer root.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
FACTS = ROOT / "_tmp_cq_rnn_r3_facts" / "report_id=RNN_seed42_v2_2_clean_20261007_r2"
OUT = ROOT / "downloads" / "vastai" / "CQ_V2_2_clean_grain_seed42"


def remote(path: str) -> str:
    if not path.startswith("/data/"):
        raise ValueError(f"Expected Modal mount path, got {path!r}")
    return path.removeprefix("/data/")


def main() -> None:
    inventory = pd.read_parquet(FACTS / "run_inventory.parquet")
    if len(inventory) != 51:
        raise ValueError(f"Expected 51 current CQ RNN cells, got {len(inventory)}")
    required = {"pipeline_id", "window_id", "train_input_path", "input_root", "data_release_id"}
    missing = required.difference(inventory.columns)
    if missing:
        raise ValueError(f"Inventory misses {sorted(missing)}")
    if inventory.data_release_id.nunique() != 1:
        raise ValueError("Inventory mixes data releases")

    files: dict[str, dict[str, str]] = {}
    for row in inventory.sort_values(["window_id", "pipeline_id"]).itertuples(index=False):
        train = remote(row.train_input_path)
        files[train] = {
            "kind": "train",
            "window_id": row.window_id,
            "pipeline_id": row.pipeline_id,
        }
        parent = remote(row.input_root)
        for name in ("validation.parquet", "test_P1.parquet", "test_P2.parquet", "test_P3.parquet", "test_P4.parquet"):
            path = f"{parent}/model_inputs/{name}"
            files.setdefault(path, {
                "kind": "shared_evaluation",
                "window_id": row.window_id,
                "pipeline_id": row.pipeline_id,
            })

    if sum(item["kind"] == "train" for item in files.values()) != 51:
        raise ValueError("Expected one TRAIN input for every model cell")
    if sum(item["kind"] == "shared_evaluation" for item in files.values()) != 75:
        raise ValueError("Expected 15 parent imputers × five shared evaluation inputs")

    OUT.mkdir(parents=True, exist_ok=True)
    download_files = []
    for path, metadata in sorted(files.items()):
        matched = re.search(r"window_id=(W[123])/.*?pipeline_id=(V\d+)", path)
        if not matched:
            raise ValueError(f"Could not derive compact local path for {path}")
        window, pipeline = matched.groups()
        filename = Path(path).name
        local_dir = "train" if metadata["kind"] == "train" else "evaluation"
        # A compact tree prevents Windows MAX_PATH failures while retaining
        # the complete immutable Modal path in this manifest.
        download_files.append({
            "remote_path": path,
            "local_path": f"{local_dir}/{window}/{pipeline}/{filename}",
            **metadata,
        })

    manifest = {
        "task": "CQ",
        "release_id": "CQ_V2_2",
        "data_release_id": str(inventory.data_release_id.iloc[0]),
        "model_cells": 51,
        "files": download_files,
        "counts": {
            "train": sum(item["kind"] == "train" for item in files.values()),
            "shared_evaluation": sum(item["kind"] == "shared_evaluation" for item in files.values()),
            "total": len(files),
        },
    }
    (OUT / "download_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
