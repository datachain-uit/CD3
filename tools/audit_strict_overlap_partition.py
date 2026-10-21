"""Fast, prediction-level audit for STRICT/OVERLAP partition invariants.

Unlike ``vastai_audit_shared.py`` this utility does not recompute metrics or
bootstrap confidence intervals.  It streams the three columns required to
prove the invariant for every stored prediction file:

* no missing or duplicate prediction identifier;
* the phase-specific STRICT flag is binary; and
* the confusion matrix of STRICT plus OVERLAP equals ALL exactly.

It is intentionally suitable for re-auditing an already evaluated grid.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq


def _parse() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def _phase_from_path(path: Path) -> tuple[str, str]:
    stem = path.stem
    split, phase = stem.rsplit("_", 1)
    return split.upper(), phase.upper()


def _audit_file(path: Path, *, expected_model: str, expected_seed: int) -> dict:
    split, phase = _phase_from_path(path)
    strict_name = f"temporal_strict_{phase}"
    parquet = pq.ParquetFile(path)
    required = {"enrollment_id_hash", "y_true", "y_pred", strict_name}
    missing = required.difference(parquet.schema_arrow.names)
    if missing:
        raise ValueError(f"{path}: missing columns {sorted(missing)}")

    identifiers: set[str] = set()
    all_cm = np.zeros((3, 3), dtype=np.int64)
    strict_cm = np.zeros((3, 3), dtype=np.int64)
    overlap_cm = np.zeros((3, 3), dtype=np.int64)
    rows = 0
    class_index: dict[str, int] = {}
    invalid_flags = 0
    null_ids = 0
    duplicate_ids = 0
    identity: dict[str, object] | None = None

    columns = ["task", "window_id", "pipeline_id", "model_name", "seed", "eval_split", "phase_id",
               "enrollment_id_hash", "y_true", "y_pred", strict_name]
    present = [column for column in columns if column in parquet.schema_arrow.names]
    for batch in parquet.iter_batches(columns=present, batch_size=131_072):
        frame = batch.to_pandas()
        if identity is None:
            identity = {key: frame[key].iloc[0] for key in
                        ("task", "window_id", "pipeline_id", "model_name", "seed", "eval_split", "phase_id")}
            if str(identity["model_name"]).upper() != expected_model.upper() or int(identity["seed"]) != expected_seed:
                raise ValueError(f"{path}: identity does not match requested model/seed: {identity}")
        ids = frame["enrollment_id_hash"]
        null_ids += int(ids.isna().sum())
        clean_ids = ids.dropna().astype(str)
        duplicate_ids += int(clean_ids.duplicated().sum())
        duplicate_ids += sum(value in identifiers for value in clean_ids)
        identifiers.update(clean_ids)

        labels = pd.concat([frame["y_true"], frame["y_pred"]], ignore_index=True).dropna().astype(str).unique()
        for label in labels:
            if label not in class_index:
                if len(class_index) >= 3:
                    raise ValueError(f"{path}: more than three classes")
                class_index[label] = len(class_index)
        flags = pd.to_numeric(frame[strict_name], errors="coerce")
        valid = flags.isin([0, 1])
        invalid_flags += int((~valid).sum())
        if not valid.all():
            continue
        true = frame["y_true"].astype(str).map(class_index).to_numpy()
        pred = frame["y_pred"].astype(str).map(class_index).to_numpy()
        flag_values = flags.to_numpy(dtype=np.int8)
        np.add.at(all_cm, (true, pred), 1)
        np.add.at(strict_cm, (true[flag_values == 1], pred[flag_values == 1]), 1)
        np.add.at(overlap_cm, (true[flag_values == 0], pred[flag_values == 0]), 1)
        rows += len(frame)

    if identity is None:
        raise ValueError(f"{path}: empty prediction file")
    passed = null_ids == duplicate_ids == invalid_flags == 0 and np.array_equal(all_cm, strict_cm + overlap_cm)
    return {
        **identity, "source_file": str(path), "rows": rows, "distinct_enrollment_id_hash": len(identifiers),
        "null_identifier_rows": null_ids, "duplicate_identifier_rows": duplicate_ids,
        "invalid_strict_flag_rows": invalid_flags, "strict_rows": int(strict_cm.sum()),
        "overlap_rows": int(overlap_cm.sum()), "all_confusion_matrix": all_cm.tolist(),
        "strict_confusion_matrix": strict_cm.tolist(), "overlap_confusion_matrix": overlap_cm.tolist(),
        "partition_exact": bool(np.array_equal(all_cm, strict_cm + overlap_cm)), "passed": bool(passed),
    }


def main() -> None:
    args = _parse()
    files = sorted(args.run_root.rglob("predictions/*.parquet"))
    if not files:
        raise FileNotFoundError(f"No prediction parquet files below {args.run_root}")
    rows = [_audit_file(path, expected_model=args.model_name, expected_seed=args.seed) for path in files]
    facts = pd.DataFrame(rows).sort_values(["window_id", "pipeline_id", "eval_split", "phase_id"])
    args.output.mkdir(parents=True, exist_ok=True)
    facts.to_parquet(args.output / "strict_overlap_partition_cells.parquet", index=False)
    facts.drop(columns=["all_confusion_matrix", "strict_confusion_matrix", "overlap_confusion_matrix"]).to_csv(
        args.output / "strict_overlap_partition_cells.csv", index=False)
    summary = {
        "audit": "strict_overlap_prediction_partition_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_root": str(args.run_root), "model_name": args.model_name, "seed": args.seed,
        "files": int(len(facts)), "runs": int(facts[["window_id", "pipeline_id"]].drop_duplicates().shape[0]),
        "rows": int(facts["rows"].sum()), "failed_cells": int((~facts["passed"]).sum()),
        "all_passed": bool(facts["passed"].all()),
        "by_split": facts.groupby("eval_split", dropna=False)["passed"].agg(["count", "sum"]).to_dict("index"),
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    if not summary["all_passed"]:
        raise SystemExit("STRICT/OVERLAP partition audit failed")


if __name__ == "__main__":
    main()
