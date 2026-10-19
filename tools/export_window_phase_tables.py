#!/usr/bin/env python3
"""Window x phase tables from an L2 report export (the table grain the registry requires).

Reads the long metric/sanity facts written by ``modal_jobs/export_lo_vastai_facts.py`` (one row per
task x window x phase x pipeline x family x split) and writes, per family and split, one table per metric
with pipelines as rows and W1/P1 ... W3/P4 as columns, plus a group summary (imputer-only vs balanced,
per window x phase) and a phase-trend table (P4 minus P1 per window).  Nothing is pooled across families
or windows unless the output file name says so, and every pooled file carries ``averaging_rule``.

Usage::

    python tools/export_window_phase_tables.py --metrics metrics_test_long.parquet \
        [--sanity sanity_test_long.parquet] --out tables/CQ_test [--metric acctempo_m3 --metric f1_macro ...]

Default metrics: acctempo_m3, f1_macro, balanced_acc, s_perf, s_san_plus, s_ent (the last three from the
sanity facts when a separate sanity file is given; otherwise from the metrics file when present).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

KEYS = ["window_id", "phase_id", "pipeline_id", "model_name"]
DEFAULT_METRICS = ["acctempo_m3", "f1_macro", "balanced_acc", "s_perf", "s_san_plus", "s_ent"]
IMPUTER_ONLY = ("V0", "V1", "V5", "V9", "V13")
PHASES = ("P1", "P2", "P3", "P4")
WINDOWS = ("W1", "W2", "W3")


def _pipeline_order(pipelines: list[str]) -> list[str]:
    return sorted(set(pipelines), key=lambda p: int(p[1:]) if p[1:].isdigit() else 99)


def load_long(metrics_path: Path, sanity_path: Path | None) -> pd.DataFrame:
    metrics = pd.read_parquet(metrics_path)
    def check_scope(frame: pd.DataFrame, name: str) -> dict:
        scope = {}
        for col in ("task", "seed"):
            if col in frame:
                if frame[col].isna().any() or frame[col].nunique() != 1:
                    raise ValueError(f"{name} contains null or mixed {col}; filter to one task and seed")
                scope[col] = frame[col].iloc[0]
        return scope
    metric_scope = check_scope(metrics, "metrics")
    missing = [k for k in KEYS + ["eval_split"] if k not in metrics.columns]
    if missing:
        raise ValueError(f"metrics facts miss {missing}")
    if sanity_path is not None:
        sanity = pd.read_parquet(sanity_path)
        sanity_scope = check_scope(sanity, "sanity")
        if metric_scope != sanity_scope:
            raise ValueError("metrics and sanity task/seed scopes do not match")
        extra = [c for c in sanity.columns if c not in metrics.columns and c not in KEYS + ["eval_split"]]
        metrics = metrics.merge(sanity[KEYS + ["eval_split"] + extra], on=KEYS + ["eval_split"], how="left", validate="one_to_one")
    if metrics.duplicated(KEYS + ["eval_split"]).any():
        raise ValueError("duplicate (window, phase, pipeline, family, split) rows")
    return metrics


def wide_table(frame: pd.DataFrame, metric: str) -> pd.DataFrame:
    table = frame.pivot_table(index="pipeline_id", columns=["window_id", "phase_id"], values=metric, aggfunc="first")
    table = table.reindex(_pipeline_order(list(table.index)))
    table.columns = [f"{w}/{p}" for w, p in table.columns]
    return table


def group_summary(frame: pd.DataFrame, metric: str) -> pd.DataFrame:
    work = frame.assign(group=frame["pipeline_id"].map(lambda p: "imputer_only" if p in IMPUTER_ONLY else "balanced"))
    out = (work.groupby(["model_name", "group", "window_id", "phase_id"], as_index=False)[metric]
               .agg(mean="mean", n_pipelines="size"))
    out["averaging_rule"] = f"mean of per-cell {metric} over the pipelines of the group; one family, one window, one phase"
    return out


def phase_trend(frame: pd.DataFrame, metric: str) -> pd.DataFrame:
    rows = []
    for (family, window, pipeline), cell in frame.groupby(["model_name", "window_id", "pipeline_id"]):
        by_phase = cell.set_index("phase_id")[metric]
        if {"P1", "P4"} <= set(by_phase.index):
            rows.append({"model_name": family, "window_id": window, "pipeline_id": pipeline,
                         "P1": float(by_phase["P1"]), "P4": float(by_phase["P4"]),
                         "P4_minus_P1": float(by_phase["P4"] - by_phase["P1"]),
                         "group": "imputer_only" if pipeline in IMPUTER_ONLY else "balanced"})
    return pd.DataFrame(rows)


def export(long: pd.DataFrame, out: Path, metrics: list[str]) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    written: dict[str, int] = {}
    available = [m for m in metrics if m in long.columns]
    for (family, split), frame in long.groupby(["model_name", "eval_split"]):
        for metric in available:
            table = wide_table(frame, metric)
            name = f"{family}_{split}_{metric}_window_phase.csv"
            table.to_csv(out / name)
            written[name] = int(table.size)
    for split, frame in long.groupby("eval_split"):
        for metric in available:
            summary = group_summary(frame, metric)
            summary.to_csv(out / f"GROUP_{split}_{metric}_imputer_vs_balanced.csv", index=False)
            trend = phase_trend(frame, metric)
            trend.to_csv(out / f"TREND_{split}_{metric}_P4_minus_P1.csv", index=False)
    receipt = {"metrics": available, "missing_metrics": [m for m in metrics if m not in long.columns],
               "families": sorted(long["model_name"].unique().tolist()), "splits": sorted(long["eval_split"].unique().tolist()),
               "windows": sorted(long["window_id"].unique().tolist()), "phases": sorted(long["phase_id"].unique().tolist()),
               "n_rows": int(len(long)), "files": written,
               "grain": "one value per family x window x phase x pipeline x split; GROUP_* and TREND_* files are the only aggregates"}
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--metrics", type=Path, required=True, help="metrics_<split>_long.parquet from the L2 export")
    parser.add_argument("--sanity", type=Path, default=None, help="sanity_<split>_long.parquet (adds s_* columns)")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--metric", action="append", default=None, help="metric column(s); default: " + ", ".join(DEFAULT_METRICS))
    args = parser.parse_args(argv)
    long = load_long(args.metrics, args.sanity)
    receipt = export(long, args.out, args.metric or DEFAULT_METRICS)
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
