"""Read-only completeness and integrity audit for portable VastAI model runs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


PHASES = ("P1", "P2", "P3", "P4")


def parse() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True,
                        help=".../runs/lstm_seed42/<TASK>/W1")
    parser.add_argument("--task", choices=("CQ", "LO"), required=True)
    parser.add_argument("--window", default="W1")
    parser.add_argument("--model-name", default="LSTM")
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def check_run(run_dir: Path, *, task: str, window: str, pipeline: str,
              model_name: str, seed: int) -> list[str]:
    errors: list[str] = []
    required = ("run_manifest.json", "model.pt", "feature_layout.json", "train_history.parquet",
                "metrics_overall.parquet")
    for name in required:
        if not (run_dir / name).is_file():
            errors.append(f"missing:{name}")
    if errors:
        return errors

    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    expected = {"task": task, "window_id": window, "pipeline_id": pipeline,
                "model_name": model_name, "seed": seed}
    for name, value in expected.items():
        if manifest.get(name) != value:
            errors.append(f"manifest:{name}={manifest.get(name)!r}, expected={value!r}")

    history = pd.read_parquet(run_dir / "train_history.parquet")
    if history.empty:
        errors.append("empty:train_history")
    metrics = pd.read_parquet(run_dir / "metrics_overall.parquet")
    expected_metric_keys = {(split, phase) for split in ("VALIDATION", "TEST") for phase in PHASES}
    actual_metric_keys = set(zip(metrics.get("eval_split", ()), metrics.get("phase_id", ())))
    if len(metrics) != 8 or actual_metric_keys != expected_metric_keys:
        errors.append(f"metrics_keys:rows={len(metrics)}, keys={sorted(actual_metric_keys)}")
    numeric = metrics.select_dtypes(include="number")
    if numeric.isna().any().any():
        errors.append("nan:metrics")

    for split, expected_rows in (("validation", manifest.get("validation_rows")), ("test", None)):
        for phase in PHASES:
            path = run_dir / "predictions" / f"{split}_{phase}.parquet"
            if not path.is_file():
                errors.append(f"missing:predictions/{split}_{phase}.parquet")
                continue
            frame = pd.read_parquet(path)
            rows = expected_rows if split == "validation" else manifest.get("test_rows", {}).get(phase)
            if rows is None or len(frame) != rows:
                errors.append(f"rows:{split}_{phase}={len(frame)}, expected={rows}")
            probability_columns = sorted(column for column in frame if column.startswith("prob_c"))
            if len(probability_columns) < 2:
                errors.append(f"probabilities:{split}_{phase}:columns={probability_columns}")
                continue
            probabilities = frame[probability_columns].to_numpy(dtype=float)
            if not np.isfinite(probabilities).all():
                errors.append(f"nan_or_inf:{split}_{phase}:probabilities")
            elif not np.allclose(probabilities.sum(axis=1), 1.0, atol=1e-3):
                errors.append(f"probability_sum:{split}_{phase}")
    return errors


def main() -> None:
    args = parse()
    records = []
    failures = []
    for index in range(17):
        pipeline = f"V{index}"
        run_dir = args.root / pipeline / args.model_name / f"seed={args.seed}"
        errors = check_run(run_dir, task=args.task, window=args.window, pipeline=pipeline,
                           model_name=args.model_name, seed=args.seed)
        record = {"pipeline_id": pipeline, "run_dir": str(run_dir), "ok": not errors,
                  "errors": errors}
        records.append(record)
        if errors:
            failures.append(record)
    report = {"task": args.task, "window": args.window, "model_name": args.model_name,
              "seed": args.seed, "expected_runs": 17, "passed_runs": 17 - len(failures),
              "failed_runs": len(failures), "records": records}
    report_path = args.root / "vastai_w1_integrity_audit.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in report if key != "records"}, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
