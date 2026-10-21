"""Materialize CQ recurrent-grid report facts at family × pipeline × window × phase grain.

The script deliberately keeps TEST and VALIDATION separate.  It joins the
stored model metrics to post-hoc sanity facts (including AccTEMPO and s_ent),
adds class recall, derives the W2 STRICT share from evaluation-slice facts,
and exports a separate training-time/NVML-energy table.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def _parse() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family-root", action="append", required=True,
                        metavar="FAMILY=PATH", help="May be supplied once per model family.")
    parser.add_argument("--audit-root", action="append", required=True,
                        metavar="FAMILY=PATH", help="Directory containing per-family audit parquet facts.")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def _mapping(values: list[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for value in values:
        name, sep, location = value.partition("=")
        if not sep or not name or not location:
            raise ValueError(f"Expected FAMILY=PATH, got {value!r}")
        result[name.upper()] = Path(location)
    return result


def _metrics(root: Path, family: str) -> pd.DataFrame:
    frames = []
    for path in sorted(root.rglob("metrics_overall.parquet")):
        frame = pd.read_parquet(path)
        frame["model_name"] = family
        frames.append(frame)
    if not frames:
        raise FileNotFoundError(f"No metrics_overall.parquet below {root}")
    output = pd.concat(frames, ignore_index=True)
    keys = ["window_id", "pipeline_id", "model_name", "seed", "eval_split", "phase_id"]
    if output.duplicated(keys).any():
        raise ValueError(f"Duplicate metrics fact keys for {family}")
    return output


def _resources(root: Path, family: str) -> pd.DataFrame:
    rows = []
    for path in sorted(root.rglob("run_manifest.json")):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if str(manifest.get("model_name", "")).upper() != family:
            continue
        history_path = path.parent / "train_history.parquet"
        history = pd.read_parquet(history_path)
        if "train_seconds" not in history:
            raise ValueError(f"{history_path}: train_seconds is required for comparable training time")
        row = {key: manifest.get(key) for key in (
            "task", "window_id", "pipeline_id", "model_name", "seed", "elapsed_seconds",
            "energy_gpu_estimated_kwh", "energy_measurement_type", "energy_sample_count",
            "energy_missing_sample_rate", "gpu", "batch_size", "micro_batch_size", "accumulation_steps",
            "execution_backend", "created_at_utc")}
        # Wall-clock elapsed_seconds contains setup/export work.  train_seconds is
        # intentionally the sum of epoch-level training intervals and is the
        # registered comparable-time quantity.
        row["train_seconds"] = float(history["train_seconds"].sum())
        rows.append(row)
    output = pd.DataFrame(rows)
    if len(output) != 51:
        raise ValueError(f"Expected 51 manifests for {family}, found {len(output)}")
    return output


def main() -> None:
    args = _parse()
    roots, audits = _mapping(args.family_root), _mapping(args.audit_root)
    if set(roots) != set(audits):
        raise ValueError("family-root and audit-root must specify the same families")
    args.output.mkdir(parents=True, exist_ok=True)
    detailed, resources = [], []
    for family in sorted(roots):
        metrics = _metrics(roots[family], family)
        audit = audits[family]
        sanity = pd.read_parquet(audit / "sanity_components.parquet")
        slices = pd.read_parquet(audit / "evaluation_slices.parquet")
        sanity["model_name"] = family
        slices["model_name"] = family
        keys = ["window_id", "pipeline_id", "model_name", "seed", "eval_split", "phase_id"]
        columns = keys + ["acctempo_m3", "s_ent", "s_perf", "s_san_plus", "s_eff", "s_leak",
                          "c0_recall", "c1_recall", "c2_recall"]
        missing = set(columns).difference(sanity.columns)
        if missing:
            raise ValueError(f"{family}: missing sanity columns {sorted(missing)}")
        combined = metrics.merge(sanity[columns], on=keys, how="inner", validate="one_to_one")
        if len(combined) != 408:
            raise ValueError(f"{family}: expected 408 TEST/VALIDATION×phase facts, got {len(combined)}")
        w2 = slices[(slices["window_id"] == "W2") & (slices["slice"].isin(["ALL", "STRICT"]))]
        strict = (w2.pivot_table(index=keys, columns="slice", values="n_eval_samples", aggfunc="first")
                    .reset_index())
        strict["w2_strict_share"] = strict["STRICT"] / strict["ALL"]
        combined = combined.merge(strict[keys + ["w2_strict_share"]], on=keys, how="left", validate="one_to_one")
        detailed.append(combined)
        resources.append(_resources(roots[family], family))

    cells = pd.concat(detailed, ignore_index=True)
    required = 4 * 51 * 2 * 4
    if len(cells) != required:
        raise RuntimeError(f"Expected {required} evaluation cells, got {len(cells)}")
    cells.to_parquet(args.output / "cq_family_pipeline_window_phase_metrics.parquet", index=False)
    cells.to_csv(args.output / "cq_family_pipeline_window_phase_metrics.csv", index=False)
    means = (cells.groupby(["model_name", "eval_split", "window_id", "phase_id"], as_index=False)
             [["acctempo_m3", "f1_macro", "balanced_accuracy", "s_ent", "c0_recall", "c1_recall", "c2_recall", "w2_strict_share"]]
             .mean())
    means.to_parquet(args.output / "cq_family_window_phase_mean.parquet", index=False)
    means.to_csv(args.output / "cq_family_window_phase_mean.csv", index=False)

    resource = pd.concat(resources, ignore_index=True)
    if len(resource) != 204:
        raise RuntimeError(f"Expected 204 resources, got {len(resource)}")
    resource.to_parquet(args.output / "cq_resource_per_run.parquet", index=False)
    resource_summary = (resource.groupby(["model_name", "pipeline_id"], as_index=False)
                        .agg(runs=("window_id", "count"), train_seconds_mean=("train_seconds", "mean"),
                             train_seconds_sum=("train_seconds", "sum"), energy_gpu_estimated_kwh_mean=("energy_gpu_estimated_kwh", "mean"),
                             energy_gpu_estimated_kwh_sum=("energy_gpu_estimated_kwh", "sum"),
                             nvml_samples_min=("energy_sample_count", "min"),
                             nvml_missing_rate_max=("energy_missing_sample_rate", "max"),
                             energy_measurement_types=("energy_measurement_type", lambda x: ";".join(sorted(set(map(str, x)))))))
    resource_summary.to_parquet(args.output / "cq_train_time_energy_family_pipeline.parquet", index=False)
    resource_summary.to_csv(args.output / "cq_train_time_energy_family_pipeline.csv", index=False)
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(), "families": sorted(roots),
        "evaluation_cells": int(len(cells)), "resource_runs": int(len(resource)),
        "expected_evaluation_cells": required, "expected_resource_runs": 204,
        "all_energy_nonnull": bool(resource["energy_gpu_estimated_kwh"].notna().all()),
        "energy_measurement_types": sorted(resource["energy_measurement_type"].dropna().unique().tolist()),
        "scope": "CQ seed=42, all pipelines V0-V16, windows W1-W3, phases P1-P4, TEST and VALIDATION",
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
