"""Read-only audit of phase-prefix parity and W1/P1 course shift.

This tool is deliberately local and does not train a model, mutate a release,
or materialize model inputs.  It answers the first diagnostic question raised
by the LO clean-grain review:

* which fields are passed through the static branch;
* whether P1 test-prefix files mask every future-phase dynamic field;
* whether W1/P1 TEST contains courses not present in W1 TRAIN; and
* how the already-produced W1/P1 predictions behave by class and evaluation
  slice.

The semantic role assigned to a static field is a review aid, not a claim that
the field is leakage-safe.  The emitted ``manual_review_required`` column is
there so a protocol owner can explicitly approve the field dictionary.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from sklearn.metrics import balanced_accuracy_score, f1_score


PHASES = ("P1", "P2", "P3", "P4")
LABEL_COLUMN = "LO_performance_label_3"
CLASS_TOKEN_TO_LABEL = {"c0": "I/D", "c1": "G", "c2": "E"}


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _parquet_files(root: Path) -> list[Path]:
    files = sorted(root.rglob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"No parquet files below {root}")
    return files


def _find_single_dir(root: Path, prefix: str) -> Path:
    if root.is_dir() and root.name == prefix:
        return root
    matches = sorted(p for p in root.rglob("*") if p.is_dir() and p.name == prefix)
    if not matches:
        raise FileNotFoundError(f"Could not locate {prefix!r} below {root}")
    # Prefer the deepest directory: downloaded archives contain an outer and
    # inner directory with the same release name.
    return max(matches, key=lambda item: len(item.parts))


def _classify_static(name: str) -> tuple[str, bool, str]:
    lowered = name.lower()
    if lowered in {"split_rule_version", "timeline_source", "window_duration_seconds"}:
        return "release_or_timeline_context", True, "Protocol/context field; approve explicitly."
    if any(token in lowered for token in ("label", "score", "performance", "final", "decision", "proxy")):
        return "label_or_outcome_risk", True, "Potential outcome/label-derived field."
    if any(token in lowered for token in ("course", "offering", "teacher", "school", "resource")):
        return "catalog_or_group_metadata", True, "Metadata may encode cohort/course identity."
    if any(token in lowered for token in ("cutoff", "future", "end_date", "availability")):
        return "time_or_availability_risk", True, "Verify availability at prediction time."
    if lowered in {"gender", "year_of_birth", "age_at_enroll", "ex_counts"}:
        return "enrollment_static_metadata", True, "Static field; approve feature semantics."
    return "other_static", True, "Static field; approve feature semantics."


def _iter_selected_rows(paths: Iterable[Path], columns: list[str]) -> Iterable[pd.DataFrame]:
    """Read only selected columns, one row group at a time to stay RAM-safe."""
    for path in paths:
        parquet = pq.ParquetFile(path)
        available = [column for column in columns if column in parquet.schema_arrow.names]
        for row_group in range(parquet.num_row_groups):
            yield parquet.read_row_group(row_group, columns=available).to_pandas()


def _phase_suffix(column: str) -> str | None:
    for phase in PHASES:
        if column.endswith(f"_{phase}"):
            return phase
    return None


def _prefix_schema_audit(prefix_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for phase_index, phase in enumerate(PHASES, start=1):
        phase_dir = _find_single_dir(prefix_root / phase, phase)
        first = _parquet_files(phase_dir)[0]
        parquet = pq.ParquetFile(first)
        columns = parquet.schema_arrow.names
        future_dynamic = [
            name for name in columns
            if (suffix := _phase_suffix(name)) is not None
            and not name.startswith("phase_available_")
            and PHASES.index(suffix) + 1 > phase_index
        ]
        # Only a small, deterministic sample is needed for this structural
        # assertion; missing future dynamic fields should be all null.
        sampled = parquet.read_row_group(0, columns=future_dynamic).to_pandas() if future_dynamic else pd.DataFrame()
        non_null_future = int(sampled.notna().sum().sum()) if not sampled.empty else 0
        rows.append({
            "phase_id": phase,
            "source_file": str(first),
            "n_columns": len(columns),
            "future_phase_columns": len(future_dynamic),
            "sample_rows_checked": len(sampled),
            "future_phase_non_null_cells_sample": non_null_future,
            "future_mask_ok_sample": non_null_future == 0,
        })
    return rows


def _static_prefix_parity(prefix_root: Path, static_columns: list[str]) -> pd.DataFrame:
    """Verify that test static fields are unchanged from P1 through P4.

    TEST prefix files are expected to blank *future phase fields*, not mutate
    the release/static branch.  This checks the whole downloaded test cohort,
    keyed by enrollment_id, without loading the wide dynamic matrix.
    """
    selected = ["enrollment_id", *static_columns]
    frames: dict[str, pd.DataFrame] = {}
    for phase in PHASES:
        phase_dir = _find_single_dir(prefix_root / phase, phase)
        parts = []
        for batch in _iter_selected_rows(_parquet_files(phase_dir), selected):
            parts.append(batch)
        frame = pd.concat(parts, ignore_index=True)
        if frame["enrollment_id"].duplicated().any():
            raise ValueError(f"{phase} test prefix violates enrollment grain.")
        frames[phase] = frame.set_index("enrollment_id").sort_index()
    reference = frames["P1"]
    rows: list[dict[str, Any]] = []
    for phase in PHASES[1:]:
        candidate = frames[phase].reindex(reference.index)
        if not candidate.index.equals(reference.index) or len(frames[phase]) != len(reference):
            raise ValueError(f"{phase} prefix does not have the P1 enrollment cohort.")
        for column in static_columns:
            equal = reference[column].eq(candidate[column]) | (reference[column].isna() & candidate[column].isna())
            rows.append({
                "reference_phase": "P1", "comparison_phase": phase,
                "column": column, "n_rows": len(reference),
                "n_mismatched": int((~equal).sum()), "values_identical": bool(equal.all()),
            })
    return pd.DataFrame(rows)


def _course_cohort_audit(phase_root: Path, prefix_root: Path) -> pd.DataFrame:
    phase_files = _parquet_files(phase_root)
    train_courses: set[str] = set()
    validation_summary: Counter[tuple[str, str]] = Counter()
    selected = ["window", "split", "course_id", LABEL_COLUMN]
    for batch in _iter_selected_rows(phase_files, selected):
        batch = batch.loc[batch["window"].eq("W1")]
        train = batch.loc[batch["split"].eq("train")]
        train_courses.update(train["course_id"].dropna().astype(str))
        validation = batch.loc[batch["split"].eq("validation")]
        validation_summary.update(("VALIDATION", str(label)) for label in validation[LABEL_COLUMN].fillna("<NULL>"))

    p1_dir = _find_single_dir(prefix_root / "P1", "P1")
    test_batches = []
    for batch in _iter_selected_rows(_parquet_files(p1_dir), selected):
        test_batches.append(batch.loc[(batch["window"].eq("W1")) & (batch["split"].eq("test"))])
    test = pd.concat(test_batches, ignore_index=True)
    test["course_cohort"] = np.where(test["course_id"].astype(str).isin(train_courses), "SEEN_COURSE", "UNSEEN_COURSE")
    grouped = (test.groupby(["course_cohort", LABEL_COLUMN], dropna=False).size()
        .rename("n_rows").reset_index())
    grouped["n_total_cohort"] = grouped.groupby("course_cohort")["n_rows"].transform("sum")
    grouped["share_within_cohort"] = grouped["n_rows"] / grouped["n_total_cohort"]
    grouped["n_train_courses"] = len(train_courses)
    return grouped


def _prediction_tables(model_root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    class_rows: list[dict[str, Any]] = []
    overall_rows: list[dict[str, Any]] = []
    for path in sorted(model_root.rglob("predictions/*.parquet")):
        if path.name not in {"test_P1.parquet", "validation_P1.parquet"}:
            continue
        required = {"window_id", "pipeline_id", "model_name", "eval_split", "phase_id", "y_true", "y_pred"}
        schema_names = set(pq.ParquetFile(path).schema_arrow.names)
        if not required.issubset(schema_names):
            continue
        frame = pd.read_parquet(path, columns=sorted(required))
        if frame.empty:
            continue
        frame = frame.loc[frame["window_id"].eq("W1") & frame["phase_id"].eq("P1")]
        if frame.empty:
            continue
        metadata = frame.iloc[0]
        # VastAI exports preserve the registry class token (for example
        # ``c0``) rather than assuming an integer class encoding.
        true = frame["y_true"].astype(str)
        pred = frame["y_pred"].astype(str)
        base = {
            "source_file": str(path),
            "model_name": metadata["model_name"],
            "pipeline_id": metadata["pipeline_id"],
            "eval_split": metadata["eval_split"],
            "phase_id": metadata["phase_id"],
            "n_rows": len(frame),
            "macro_f1": f1_score(true, pred, average="macro", zero_division=0),
            "balanced_accuracy": balanced_accuracy_score(true, pred),
        }
        overall_rows.append(base)
        for label in sorted(set(true).union(set(pred))):
            support = int((true == label).sum())
            class_rows.append({
                **base,
                "class_index": str(label),
                "class_label": CLASS_TOKEN_TO_LABEL.get(str(label), str(label)),
                "support": support,
                "predicted_count": int((pred == label).sum()),
                "recall": float(((true == label) & (pred == label)).sum() / support) if support else np.nan,
            })
    return pd.DataFrame(class_rows), pd.DataFrame(overall_rows)


def _layouts(model_root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    signatures: Counter[str] = Counter()
    columns: dict[str, dict[str, Any]] = {}
    for path in sorted(model_root.rglob("feature_layout.json")):
        layout = _read_json(path)
        static = sorted(layout.get("static_columns", []))
        masks = sorted(layout.get("mask_static_columns", []))
        signature_payload = {"static_columns": static, "mask_static_columns": masks}
        signature = hashlib.sha256(json.dumps(signature_payload, sort_keys=True).encode()).hexdigest()[:16]
        signatures[signature] += 1
        for name in static:
            role, review, rationale = _classify_static(name)
            record = columns.setdefault(name, {
                "column": name, "semantic_role": role,
                "manual_review_required": review, "review_rationale": rationale,
                "layout_count": 0, "mask_column_present": False,
            })
            record["layout_count"] += 1
            record["mask_column_present"] = record["mask_column_present"] or f"missing__{name}" in masks
    return pd.DataFrame(list(columns.values())).sort_values("column"), pd.DataFrame([
        {"layout_signature": sig, "n_layouts": count} for sig, count in signatures.items()
    ]).sort_values("layout_signature")


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, quoting=csv.QUOTE_MINIMAL)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-root", type=Path, required=True,
                        help="Downloaded checked feature release containing phase/test-prefix views.")
    parser.add_argument("--model-root", type=Path, required=True,
                        help="Downloaded VastAI/Modal model-result tree with feature_layout and predictions.")
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()

    args.output_root.mkdir(parents=True, exist_ok=True)
    phase_root = _find_single_dir(args.feature_root, "phase_views_v3_1_scored_signal_excluded")
    prefix_root = _find_single_dir(args.feature_root, "test_prefix_views_v3_1_scored_signal_excluded")

    static_columns, signatures = _layouts(args.model_root)
    prefix_audit = pd.DataFrame(_prefix_schema_audit(prefix_root))
    static_parity = _static_prefix_parity(prefix_root, static_columns["column"].tolist())
    cohort = _course_cohort_audit(phase_root, prefix_root)
    per_class, overall = _prediction_tables(args.model_root)

    _write_csv(static_columns, args.output_root / "static_columns.csv")
    _write_csv(signatures, args.output_root / "layout_signatures.csv")
    _write_csv(prefix_audit, args.output_root / "test_prefix_mask_audit.csv")
    _write_csv(static_parity, args.output_root / "test_prefix_static_parity_audit.csv")
    _write_csv(cohort, args.output_root / "w1_p1_course_cohort_label_support.csv")
    _write_csv(per_class, args.output_root / "w1_p1_per_class_predictions.csv")
    _write_csv(overall, args.output_root / "w1_p1_prediction_summary.csv")
    summary = {
        "audit": "local_read_only_prefix_validation_alignment_v1",
        "phase_view_root": str(phase_root),
        "test_prefix_root": str(prefix_root),
        "model_root": str(args.model_root),
        "layout_count": int(signatures["n_layouts"].sum()) if not signatures.empty else 0,
        "layout_signature_count": int(len(signatures)),
        "static_column_count": int(len(static_columns)),
        "static_columns_requiring_manual_review": int(static_columns["manual_review_required"].sum()) if not static_columns.empty else 0,
        "prefix_future_mask_all_samples_ok": bool(prefix_audit["future_mask_ok_sample"].all()),
        "test_static_prefix_parity_ok": bool(static_parity["values_identical"].all()),
        "w1_p1_prediction_cells": int(len(overall)),
        "notes": [
            "The audit does not infer causal leakage from a column name.",
            "Validation is transformed phase-wise by the model layout; this audit verifies source prefix masking and reports the static branch for explicit protocol review.",
            "Checkpoint reselection requires model rerun only if the protocol owner decides the validation contract must change.",
        ],
    }
    (args.output_root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
