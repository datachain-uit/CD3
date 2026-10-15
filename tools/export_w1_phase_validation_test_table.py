"""Export a provenance-checked W1 VALIDATION/TEST P1--P4 metric table.

The input parquet facts must have the standard model metric keys.  This tool
does not average across incompatible model families: family remains in each
cell-level row; the companion summary explicitly reports its averaging rule.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


KEYS = ["task", "window_id", "phase_id", "pipeline_id", "model_name", "run_id"]
METRICS = ["n_rows", "accuracy", "balanced_accuracy", "f1_macro", "f1_weighted", "mcc"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    test, validation = pd.read_parquet(args.test), pd.read_parquet(args.validation)
    required = set(KEYS + METRICS + ["eval_split"])
    for name, frame in (("test", test), ("validation", validation)):
        missing = required.difference(frame.columns)
        if missing:
            raise ValueError(f"{name} metric facts miss {sorted(missing)}")
    frames = []
    for frame, split in ((test, "TEST"), (validation, "VALIDATION")):
        subset = frame.loc[(frame["window_id"] == "W1") & frame["phase_id"].isin(("P1", "P2", "P3", "P4"))].copy()
        if not subset["eval_split"].eq(split).all():
            raise ValueError(f"{split} input contains another evaluation split")
        frames.append(subset)
    cells = pd.concat(frames, ignore_index=True).sort_values(["eval_split", "phase_id", "model_name", "pipeline_id"])
    if cells.duplicated(KEYS + ["eval_split"]).any():
        raise ValueError("Duplicate metric cell in inputs")
    args.output.mkdir(parents=True, exist_ok=True)
    cells.to_csv(args.output / "w1_validation_test_p1_p4_cells.csv", index=False)
    summary = (cells.groupby(["task", "eval_split", "phase_id", "model_name"], dropna=False)
        .agg(n_cells=("run_id", "size"), mean_n_rows=("n_rows", "mean"),
             macro_f1=("f1_macro", "mean"), balanced_accuracy=("balanced_accuracy", "mean"),
             accuracy=("accuracy", "mean"), mcc=("mcc", "mean"))
        .reset_index())
    summary["averaging_rule"] = "mean_of_per_cell_values_within_model_family"
    summary.to_csv(args.output / "w1_validation_test_p1_p4_summary.csv", index=False)
    receipt = {
        "audit": "w1_validation_test_phase_table_v1",
        "test_source": str(args.test), "validation_source": str(args.validation),
        "cell_rows": len(cells), "summary_rows": len(summary),
        "test_run_ids": int(test["run_id"].nunique()),
        "validation_run_ids": int(validation["run_id"].nunique()),
        "shared_run_ids": int(len(set(test["run_id"]).intersection(validation["run_id"]))),
        "averaging_rule": "mean_of_per_cell_values_within_model_family",
    }
    (args.output / "receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
