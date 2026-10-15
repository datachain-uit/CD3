"""Build the exact LO V3.1 model-input download manifest for VastAI.

The immutable LO RNN r2 inventory selects the actual S1/S2 parent for every
W1--W3/V0--V16 cell.  Evaluation inputs are shared by a parent imputer and
are therefore fetched once rather than copied for every balanced pipeline.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
FACTS = ROOT / "_tmp_lo_rnn_r2"
OUT = ROOT / "downloads" / "vastai" / "LO_V3_1_clean_grain_seed42"


def remote(path: str) -> str:
    if not path.startswith("/data/"):
        raise ValueError(f"Expected Modal mount path, got {path!r}")
    return path.removeprefix("/data/")


def main() -> None:
    inventory = pd.read_parquet(FACTS / "run_inventory.parquet")
    if len(inventory) != 51:
        raise ValueError(f"Expected 51 current LO RNN cells, got {len(inventory)}")
    required = {"pipeline_id", "window_id", "train_input_path", "input_root", "data_release_id"}
    missing = required.difference(inventory.columns)
    if missing:
        raise ValueError(f"Inventory misses {sorted(missing)}")
    if inventory.data_release_id.nunique() != 1:
        raise ValueError("Inventory mixes data releases")

    files: dict[str, dict[str, str]] = {}
    for row in inventory.sort_values(["window_id", "pipeline_id"]).itertuples(index=False):
        train = remote(row.train_input_path)
        files[train] = {"kind": "train", "window_id": row.window_id, "pipeline_id": row.pipeline_id}
        parent = remote(row.input_root)
        for name in ("validation.parquet", "test_P1.parquet", "test_P2.parquet", "test_P3.parquet", "test_P4.parquet"):
            path = f"{parent}/model_inputs/{name}"
            files.setdefault(path, {"kind": "shared_evaluation", "window_id": row.window_id,
                                    "pipeline_id": row.pipeline_id})

    counts = {
        "train": sum(item["kind"] == "train" for item in files.values()),
        "shared_evaluation": sum(item["kind"] == "shared_evaluation" for item in files.values()),
        "total": len(files),
    }
    if counts != {"train": 51, "shared_evaluation": 75, "total": 126}:
        raise RuntimeError(f"Unexpected LO download shape: {counts}")

    download_files = []
    for path, metadata in sorted(files.items()):
        matched = re.search(r"window_id=(W[123])/.*?pipeline_id=(V\d+)", path)
        if not matched:
            raise ValueError(f"Could not derive compact local path for {path}")
        window, pipeline = matched.groups()
        local_dir = "train" if metadata["kind"] == "train" else "evaluation"
        download_files.append({"remote_path": path,
                               "local_path": f"{local_dir}/{window}/{pipeline}/{Path(path).name}",
                               **metadata})

    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {"task": "LO", "release_id": "LO_V3_1",
                "data_release_id": str(inventory.data_release_id.iloc[0]),
                "model_cells": 51, "files": download_files, "counts": counts}
    (OUT / "download_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(counts, ensure_ascii=False))


if __name__ == "__main__":
    main()
