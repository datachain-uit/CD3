#!/usr/bin/env python3
"""Post-hoc SEEN/UNSEEN x STRICT/OVERLAP audit from portable prediction rows.

This read-only audit is deliberately independent of enrollment-id hashes and
therefore does not require a prediction salt.  It uses the ``course_id`` and
phase-specific temporal-strict flag already copied into prediction files by
``tools.vastai_train_shared``.  A course is SEEN only when it appears in the
real parent TRAIN file of the same window; it does not mean the offering was
seen.  The script never changes predictions, checkpoints, or source inputs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
from sklearn.metrics import balanced_accuracy_score, f1_score


PHASES = ("P1", "P2", "P3", "P4")
WINDOWS = ("W1", "W2", "W3")
CLASSES = ("c0", "c1", "c2")


def parse() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--model-root", type=Path, required=True,
                        help="Root containing <task>/<window>/<pipeline>/<model>/seed=<seed>.")
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--task", required=True, choices=("CQ", "LO"))
    parser.add_argument("--pipeline-id", default="V0")
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--prediction-salt-file", type=Path,
                        default=Path(os.environ["TEMPO_PREDICTION_SALT_FILE"])
                        if os.environ.get("TEMPO_PREDICTION_SALT_FILE") else None,
                        help="Local private salt file used only to hash evaluation enrollment_id for the join.")
    return parser.parse_args()


def parent_pipeline(pipeline: str) -> str:
    parents = {"V2": "V1", "V3": "V1", "V4": "V1", "V6": "V5", "V7": "V5", "V8": "V5",
               "V10": "V9", "V11": "V9", "V12": "V9", "V14": "V13", "V15": "V13", "V16": "V13"}
    return parents.get(pipeline, pipeline)


def train_path(data_root: Path, window: str, pipeline: str, seed: int) -> Path:
    parent = parent_pipeline(pipeline)
    candidates = ([data_root / "train" / window / pipeline / f"seed={seed}" / "balanced_train.parquet",
                   data_root / "train" / window / pipeline / "balanced_train.parquet"]
                  if pipeline != parent else [data_root / "train" / window / pipeline / "train.parquet"])
    return next((path for path in candidates if path.is_file()), candidates[-1])


def first_present(columns: set[str], candidates: tuple[str, ...], *, source: Path) -> str:
    match = next((column for column in candidates if column in columns), None)
    if match is None:
        raise ValueError(f"{source} lacks any of {candidates}")
    return match


def schema_columns(path: Path) -> set[str]:
    return set(pq.ParquetFile(path).schema_arrow.names)


def evaluation_path(data_root: Path, window: str, pipeline: str, split: str, phase: str) -> Path:
    parent = parent_pipeline(pipeline)
    name = "validation.parquet" if split == "validation" else f"test_{phase}.parquet"
    return data_root / "evaluation" / window / parent / name


def context_join(source: Path, *, salt: str, phase: str) -> pd.DataFrame:
    schema = schema_columns(source)
    course_column = first_present(schema, ("course_id", "context__course_id"), source=source)
    strict_column = first_present(schema, (f"temporal_strict_{phase}", f"context__temporal_strict_{phase}"), source=source)
    context = pd.read_parquet(source, columns=["enrollment_id", course_column, strict_column])
    if context["enrollment_id"].duplicated().any():
        raise ValueError(f"{source}: enrollment_id is not unique")
    return pd.DataFrame({
        "enrollment_id_hash": context["enrollment_id"].astype(str).map(
            lambda value: hashlib.sha256(f"{salt}|{value}".encode()).hexdigest()
        ),
        "course_id": context[course_column].astype("string"),
        "source_strict": pd.to_numeric(context[strict_column], errors="coerce"),
    })


def score(frame: pd.DataFrame) -> dict:
    y_true, y_pred = frame["y_true"].astype(str), frame["y_pred"].astype(str)
    values = {
        "n_eval": int(len(frame)),
        "macro_f1": (float(f1_score(y_true, y_pred, labels=CLASSES, average="macro", zero_division=0))
                     if len(frame) else None),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)) if len(frame) else None,
    }
    for cls in CLASSES:
        values[f"support_{cls}"] = int((y_true == cls).sum())
    return values


def main() -> None:
    args = parse()
    if args.prediction_salt_file is None or not args.prediction_salt_file.is_file():
        raise FileNotFoundError("Provide --prediction-salt-file; the salt value is never logged or exported.")
    salt = args.prediction_salt_file.read_text(encoding="utf-8").strip()
    if not salt:
        raise ValueError("prediction salt file is empty")
    output = args.output_root
    output.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    diagnostics: list[dict] = []
    for window in WINDOWS:
        train = train_path(args.data_root, window, args.pipeline_id, args.seed)
        if not train.is_file():
            raise FileNotFoundError(f"Missing parent TRAIN for {window}: {train}")
        train_schema = schema_columns(train)
        train_course = first_present(train_schema, ("course_id", "context__course_id"), source=train)
        train_courses = set(pd.read_parquet(train, columns=[train_course])[train_course].dropna().astype(str))
        root = args.model_root / args.task / window / args.pipeline_id / args.model_name / f"seed={args.seed}" / "predictions"
        for split in ("validation", "test"):
            for phase in PHASES:
                path = root / f"{split}_{phase}.parquet"
                if not path.is_file():
                    raise FileNotFoundError(f"Missing prediction: {path}")
                frame = pd.read_parquet(path)
                strict_column = f"temporal_strict_{phase}"
                required = {"enrollment_id_hash", strict_column, "y_true", "y_pred"}
                missing = sorted(required.difference(frame.columns))
                if missing:
                    raise ValueError(f"{path} lacks {missing}")
                duplicate_hashes = int(frame["enrollment_id_hash"].duplicated().sum())
                strict = pd.to_numeric(frame[strict_column], errors="coerce")
                invalid_strict = int((~strict.isin([0, 1])).sum())
                if duplicate_hashes or invalid_strict:
                    raise ValueError(f"{path}: duplicate_hashes={duplicate_hashes}, invalid_strict={invalid_strict}")
                source = evaluation_path(args.data_root, window, args.pipeline_id, split, phase)
                if not source.is_file():
                    raise FileNotFoundError(f"Missing evaluation input for prediction join: {source}")
                context = context_join(source, salt=salt, phase=phase)
                frame = frame.merge(context, on="enrollment_id_hash", how="left", validate="one_to_one")
                if frame["course_id"].isna().any() or frame["source_strict"].isna().any():
                    raise ValueError(f"{path}: prediction/source join is incomplete")
                if not strict.eq(frame["source_strict"]).all():
                    raise ValueError(f"{path}: prediction STRICT flag differs from source input")
                frame = frame.assign(
                    course_cohort=frame["course_id"].astype(str).isin(train_courses).map(
                        {True: "SEEN_COURSE", False: "UNSEEN_COURSE"}
                    ),
                    temporal_slice=strict.map({1: "STRICT", 0: "OVERLAP"}),
                )
                diagnostics.append({"window_id": window, "eval_split": split.upper(), "phase_id": phase,
                                    "rows": len(frame), "duplicate_hashes": duplicate_hashes,
                                    "invalid_strict": invalid_strict, "prediction_path": str(path)})
                for cohort in ("SEEN_COURSE", "UNSEEN_COURSE"):
                    for temporal in ("STRICT", "OVERLAP"):
                        subset = frame[(frame.course_cohort == cohort) & (frame.temporal_slice == temporal)]
                        rows.append({"task": args.task, "window_id": window, "pipeline_id": args.pipeline_id,
                                     "model_name": args.model_name, "seed": args.seed,
                                     "eval_split": split.upper(), "phase_id": phase,
                                     "course_cohort": cohort, "temporal_slice": temporal, **score(subset)})
    facts = pd.DataFrame(rows)
    diagnostics_frame = pd.DataFrame(diagnostics)
    facts.to_parquet(output / "seen_unseen_strict_overlap_metrics.parquet", index=False)
    facts.to_csv(output / "seen_unseen_strict_overlap_metrics.csv", index=False)
    diagnostics_frame.to_parquet(output / "prediction_invariants.parquet", index=False)
    summary = {
        "audit": "prediction_course_cohort_strict_overlap_v1",
        "task": args.task, "pipeline_id": args.pipeline_id, "model_name": args.model_name, "seed": args.seed,
        "cells": int(len(facts)), "prediction_files": int(len(diagnostics_frame)),
        "duplicate_hashes": int(diagnostics_frame["duplicate_hashes"].sum()),
        "invalid_strict": int(diagnostics_frame["invalid_strict"].sum()),
        "cohort_definition": "SEEN_COURSE iff course_id occurs in real parent TRAIN of same window",
        "temporal_definition": "STRICT iff phase-specific temporal_strict flag equals 1",
        "salt_required": True,
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
