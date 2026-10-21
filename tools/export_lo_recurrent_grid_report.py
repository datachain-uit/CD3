"""Materialize complete LO recurrent-grid report facts without claiming unavailable energy telemetry."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "LO/resuilt/vastai_f2_batch2048_seed42_20261013"
AUDIT = ROOT / "LO/resuilt/review_20261019_window_phase_r2"
OUT = ROOT / "LO/resuilt/lo_recurrent_allfamilies_grid_r2_20261021"
FAMILY_ROOTS = {"RNN": "rnn_seed42", "LSTM": "lstm_seed42", "GRU": "gru_seed42", "BILSTM": "bilstm_seed42"}


def _resources(family: str, root: Path) -> pd.DataFrame:
    rows = []
    for path in sorted(root.rglob("run_manifest.json")):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if str(manifest.get("model_name", "")).upper() != family:
            continue
        history = pd.read_parquet(path.parent / "train_history.parquet")
        if "train_seconds" not in history:
            raise ValueError(f"{path.parent}: missing train_seconds")
        rows.append({
            "task": manifest["task"], "model_name": family, "window_id": manifest["window_id"],
            "pipeline_id": manifest["pipeline_id"], "seed": manifest["seed"],
            "train_seconds": float(history["train_seconds"].sum()), "batch_size": manifest.get("batch_size"),
            "execution_backend": manifest.get("execution_backend"), "gpu": manifest.get("gpu"),
            "energy_measurement": manifest.get("energy_measurement"),
            "energy_measurement_type": manifest.get("energy_measurement_type"),
            "energy_gpu_estimated_kwh": manifest.get("energy_gpu_estimated_kwh"),
        })
    if len(rows) != 51:
        raise ValueError(f"{family}: expected 51 manifests, found {len(rows)}")
    return pd.DataFrame(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sanity = pd.read_parquet(AUDIT / "sanity_long.parquet")
    slices = pd.read_csv(AUDIT / "slice_partition_and_strict_share.csv")
    keys = ["model_name", "window_id", "pipeline_id", "seed", "eval_split", "phase_id"]
    detail = sanity.merge(slices[keys + ["strict_share", "partition_ok"]], on=keys, how="left", validate="one_to_one")
    if len(detail) != 1632 or not detail["partition_ok"].all():
        raise ValueError("LO sanity/slice coverage is incomplete or a slice partition failed")
    detail.to_parquet(OUT / "lo_family_pipeline_window_phase_metrics.parquet", index=False)
    detail.to_csv(OUT / "lo_family_pipeline_window_phase_metrics.csv", index=False)
    mean = (detail.groupby(["model_name", "eval_split", "window_id", "phase_id"], as_index=False)
            [["acctempo_m3", "macro_f1", "balanced_acc", "s_ent", "c0_recall", "c1_recall", "c2_recall", "strict_share"]]
            .mean())
    mean.to_parquet(OUT / "lo_family_window_phase_mean.parquet", index=False)
    mean.to_csv(OUT / "lo_family_window_phase_mean.csv", index=False)
    resources = pd.concat([_resources(name, SOURCE / location) for name, location in FAMILY_ROOTS.items()], ignore_index=True)
    if len(resources) != 204:
        raise RuntimeError("LO resource coverage incomplete")
    resources.to_parquet(OUT / "lo_resource_per_run.parquet", index=False)
    resource_summary = (resources.groupby(["model_name", "pipeline_id"], as_index=False)
                        .agg(runs=("window_id", "count"), train_seconds_mean=("train_seconds", "mean"),
                             train_seconds_sum=("train_seconds", "sum"), batch_size=("batch_size", "first"),
                             telemetry=("energy_measurement", lambda x: ";".join(sorted(set(map(str, x))))),
                             energy_nonnull=("energy_gpu_estimated_kwh", lambda x: int(x.notna().sum()))))
    resource_summary.to_parquet(OUT / "lo_train_time_family_pipeline.parquet", index=False)
    resource_summary.to_csv(OUT / "lo_train_time_family_pipeline.csv", index=False)
    grain = pd.read_csv(ROOT / "LO/resuilt/lo_prediction_grain_20261019/file_audit.csv")
    grain_ok = bool((grain["null_id"].astype(int).eq(0) & grain["duplicate_rows"].astype(int).eq(0) &
                     grain["null_or_invalid_flag"].astype(int).eq(0) & grain["error"].fillna("").eq("")).all())
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(), "evaluation_cells": int(len(detail)),
        "resource_runs": int(len(resources)), "families": sorted(FAMILY_ROOTS), "all_slice_partitions_passed": True,
        "prediction_grain_files": int(len(grain)), "prediction_grain_passed": grain_ok,
        "energy_measurement": "NOT_MEASURED", "energy_gpu_estimated_kwh_available": int(resources.energy_gpu_estimated_kwh.notna().sum()),
        "scope": "LO V3.1, seed 42, V0-V16, W1-W3, P1-P4, TEST and VALIDATION",
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
