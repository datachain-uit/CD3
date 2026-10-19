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
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pyarrow.compute as pc
from sklearn.metrics import balanced_accuracy_score, f1_score

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from LO.registries import STATIC_FEATURE_CONTRACT  # noqa: E402

PHASES = ("P1", "P2", "P3", "P4")
TASK_SPECS = {
    "LO": {
        "label_column": "LO_performance_label_3",
        "class_token_to_label": {"c0": "I/D", "c1": "G", "c2": "E"},
        "phase_view_dir": "phase_views_v3_1_scored_signal_excluded",
        "test_prefix_dir": "test_prefix_views_v3_1_scored_signal_excluded",
    },
    "CQ": {
        "label_column": "CQ_label_final",
        "class_token_to_label": {"c0": "warning", "c1": "average", "c2": "good"},
        "phase_view_dir": "phase_views_v2_2",
        "test_prefix_dir": "test_prefix_views_v2_2",
    },
}
STATIC_FIELD_CONTRACT = {name: (field["definition"], field["available"], field["disposition"])
                         for name, field in STATIC_FEATURE_CONTRACT["fields"].items()}


def _macro_scores(true: pd.Series, pred: pd.Series) -> dict[str, Any]:
    present = sorted(set(true).union(pred))
    return {
        "macro_f1": f1_score(true, pred, labels=["c0", "c1", "c2"], average="macro", zero_division=0),
        "macro_f1_present_classes": f1_score(true, pred, labels=present, average="macro", zero_division=0),
        "n_classes_present_true": int(true.nunique()),
        "n_classes_present_pred": int(pred.nunique()),
        "macro_f1_convention": "fixed_k3_zero_division_0 | present_classes",
        "balanced_accuracy": balanced_accuracy_score(true, pred),
    }


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


def _prefix_schema_audit(prefix_root: Path, *, full_scan: bool = False) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for phase_index, phase in enumerate(PHASES, start=1):
        phase_dir = _find_single_dir(prefix_root / phase, phase)
        files = _parquet_files(phase_dir)
        first = files[0]
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
        non_null_future = rows_checked = cells_checked = 0
        for path in (files if full_scan else files[:1]):
            source = pq.ParquetFile(path)
            if source.schema_arrow.names != columns:
                raise ValueError(f"Inconsistent prefix schema: {path}")
            groups = range(source.num_row_groups) if full_scan else range(min(1, source.num_row_groups))
            for row_group in groups:
                rows_checked += source.metadata.row_group(row_group).num_rows
                cells_checked += source.metadata.row_group(row_group).num_rows * len(future_dynamic)
                if future_dynamic:
                    for batch in source.iter_batches(batch_size=8192, row_groups=[row_group], columns=future_dynamic):
                        non_null_future += sum(len(col) - int(pc.sum(pc.is_null(col, nan_is_null=True)).as_py()) for col in batch.columns)
        rows.append({
            "phase_id": phase,
            "source_file": str(first),
            "n_columns": len(columns),
            "future_phase_columns": len(future_dynamic),
            "sample_rows_checked": rows_checked,
            "files_checked": len(files) if full_scan else 1,
            "scan_scope": "all_files_all_row_groups" if full_scan else "first_file_row_group_0",
            "future_phase_cells_checked": cells_checked,
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


def _course_cohort_audit(phase_root: Path, prefix_root: Path, label_column: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    phase_files = _parquet_files(phase_root)
    train_courses: set[str] = set()
    validation_summary: Counter[tuple[str, str]] = Counter()
    selected = ["window", "split", "course_id", "enrollment_id", label_column, "temporal_strict_P1"]
    for batch in _iter_selected_rows(phase_files, selected):
        batch = batch.loc[batch["window"].eq("W1")]
        train = batch.loc[batch["split"].eq("train")]
        train_courses.update(train["course_id"].dropna().astype(str))
        validation = batch.loc[batch["split"].eq("validation")]
        validation_summary.update(("VALIDATION", str(label)) for label in validation[label_column].fillna("<NULL>"))

    p1_dir = _find_single_dir(prefix_root / "P1", "P1")
    test_batches = []
    for batch in _iter_selected_rows(_parquet_files(p1_dir), selected):
        test_batches.append(batch.loc[(batch["window"].eq("W1")) & (batch["split"].eq("test"))])
    test = pd.concat(test_batches, ignore_index=True)
    test["course_cohort"] = np.where(test["course_id"].astype(str).isin(train_courses), "SEEN_COURSE", "UNSEEN_COURSE")
    grouped = (test.groupby(["course_cohort", label_column], dropna=False).size()
        .rename("n_rows").reset_index())
    grouped["n_total_cohort"] = grouped.groupby("course_cohort")["n_rows"].transform("sum")
    grouped["share_within_cohort"] = grouped["n_rows"] / grouped["n_total_cohort"]
    grouped["n_train_courses"] = len(train_courses)
    return grouped, test


def _prediction_tables(model_root: Path, class_token_to_label: dict[str, str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    class_rows: list[dict[str, Any]] = []
    overall_rows: list[dict[str, Any]] = []
    for path in sorted(model_root.rglob("predictions/*.parquet")):
        if "W1" not in path.parts or path.name not in {"test_P1.parquet", "validation_P1.parquet"}:
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
            **_macro_scores(true, pred),
        }
        overall_rows.append(base)
        for label in sorted(set(true).union(set(pred))):
            support = int((true == label).sum())
            class_rows.append({
                **base,
                "class_index": str(label),
                "class_label": class_token_to_label.get(str(label), str(label)),
                "support": support,
                "predicted_count": int((pred == label).sum()),
                "recall": float(((true == label) & (pred == label)).sum() / support) if support else np.nan,
            })
    return pd.DataFrame(class_rows), pd.DataFrame(overall_rows)


def _all_phase_prediction_summary(model_root: Path) -> pd.DataFrame:
    """Return the requested W1 VALIDATION/TEST P1--P4 table by model cell."""
    rows: list[dict[str, Any]] = []
    required = {"window_id", "pipeline_id", "model_name", "eval_split", "phase_id", "y_true", "y_pred"}
    for path in sorted(model_root.rglob("predictions/*.parquet")):
        if "W1" not in path.parts or path.name not in {f"{split}_{phase}.parquet" for split in ("test", "validation") for phase in PHASES}:
            continue
        if not required.issubset(pq.ParquetFile(path).schema_arrow.names):
            continue
        frame = pd.read_parquet(path, columns=sorted(required))
        if frame.empty or not frame["window_id"].eq("W1").all():
            continue
        meta = frame.iloc[0]
        true, pred = frame["y_true"].astype(str), frame["y_pred"].astype(str)
        rows.append({
            "source_file": str(path), "model_name": meta["model_name"],
            "pipeline_id": meta["pipeline_id"], "eval_split": meta["eval_split"],
            "phase_id": meta["phase_id"], "n_rows": len(frame),
            **_macro_scores(true, pred),
        })
    return pd.DataFrame(rows)


def _w1_p1_slice_metrics(model_root: Path, context: pd.DataFrame, label_column: str,
                          class_token_to_label: dict[str, str]) -> pd.DataFrame:
    """Score W1/P1 predictions by course novelty and STRICT/OVERLAP.

    Join by the same salted enrollment hash used by the VastAI runner.
    Equal ordered labels alone cannot establish enrollment-level alignment.
    """
    label_to_token = {label: token for token, label in class_token_to_label.items()}
    salt = os.environ.get("TEMPO_PREDICTION_SALT")
    if not salt:
        raise ValueError("Set TEMPO_PREDICTION_SALT to the original VastAI prediction salt for verified enrollment alignment.")
    context = context.copy()
    context["enrollment_id_hash"] = context["enrollment_id"].astype("string").map(
        lambda value: hashlib.sha256(f"{salt}|{value}".encode()).hexdigest()
    )
    if context["enrollment_id_hash"].duplicated().any():
        raise ValueError("Duplicate enrollment hashes in W1/P1 context.")
    context = context.set_index("enrollment_id_hash")
    context["temporal_slice"] = np.where(pd.to_numeric(context["temporal_strict_P1"], errors="coerce").fillna(0).eq(1), "STRICT", "OVERLAP")
    rows: list[dict[str, Any]] = []
    for path in sorted(model_root.rglob("predictions/test_P1.parquet")):
        if "W1" not in path.parts:
            continue
        frame = pd.read_parquet(path, columns=["enrollment_id_hash", "window_id", "pipeline_id", "model_name", "eval_split", "phase_id", "y_true", "y_pred"])
        frame = frame.loc[frame["window_id"].eq("W1")]
        if frame.empty:
            continue
        if frame["enrollment_id_hash"].duplicated().any() or len(frame) != len(context):
            raise ValueError(f"Cannot attach W1/P1 context: duplicate hashes or row count mismatch in {path}")
        aligned = context.reindex(frame["enrollment_id_hash"])
        if aligned[label_column].isna().any():
            raise ValueError(f"Cannot attach W1/P1 context: unmatched enrollment hash in {path}")
        expected = aligned[label_column].map(label_to_token).astype(str).to_numpy()
        if not np.array_equal(frame["y_true"].astype(str).to_numpy(), expected):
            raise ValueError(f"Cannot attach W1/P1 context: matched enrollment label mismatch in {path}")
        frame = frame.assign(
            course_cohort=aligned["course_cohort"].to_numpy(),
            temporal_slice=aligned["temporal_slice"].to_numpy(),
        )
        metadata = frame.iloc[0]
        for axis in ("course_cohort", "temporal_slice"):
            for group, subset in frame.groupby(axis, dropna=False):
                true, pred = subset["y_true"].astype(str), subset["y_pred"].astype(str)
                rows.append({
                    "source_file": str(path), "model_name": metadata["model_name"],
                    "pipeline_id": metadata["pipeline_id"], "axis": axis,
                    "slice": str(group), "n_rows": len(subset),
                    **_macro_scores(true, pred),
                    "row_alignment": "salted_enrollment_hash_and_label_match",
                })
    return pd.DataFrame(rows)


def _layouts(model_root: Path, *, task: str = "LO") -> tuple[pd.DataFrame, pd.DataFrame]:
    if task == "CQ":
        from CQ.registries import STATIC_FEATURE_CONTRACT as cq_contract
        field_contract = {name: (field["definition"], field["available"], field["disposition"])
                          for name, field in cq_contract["fields"].items()}
    else:
        field_contract = STATIC_FIELD_CONTRACT
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
                "definition": field_contract.get(name, ("Undocumented static field.", "manual review", "REVIEW"))[0],
                "availability_contract": field_contract.get(name, ("Undocumented static field.", "manual review", "REVIEW"))[1],
                "protocol_disposition": field_contract.get(name, ("Undocumented static field.", "manual review", "REVIEW"))[2],
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
    parser.add_argument("--task", choices=sorted(TASK_SPECS), default="LO",
                        help="Locked task contract that determines label and view-release names.")
    parser.add_argument("--full-scan", action="store_true", help="Scan all TEST prefix files and row groups.")
    args = parser.parse_args()

    args.output_root.mkdir(parents=True, exist_ok=True)
    spec = TASK_SPECS[args.task]
    phase_root = _find_single_dir(args.feature_root, spec["phase_view_dir"])
    prefix_root = _find_single_dir(args.feature_root, spec["test_prefix_dir"])

    static_columns, signatures = _layouts(args.model_root, task=args.task)
    prefix_audit = pd.DataFrame(_prefix_schema_audit(prefix_root, full_scan=args.full_scan))
    static_parity = _static_prefix_parity(prefix_root, static_columns["column"].tolist())
    cohort, test_context = _course_cohort_audit(phase_root, prefix_root, spec["label_column"])
    per_class, overall = _prediction_tables(args.model_root, spec["class_token_to_label"])
    all_phase_summary = _all_phase_prediction_summary(args.model_root)
    p1_slices = _w1_p1_slice_metrics(
        args.model_root, test_context, spec["label_column"], spec["class_token_to_label"]
    )

    _write_csv(static_columns, args.output_root / "static_columns.csv")
    _write_csv(signatures, args.output_root / "layout_signatures.csv")
    _write_csv(prefix_audit, args.output_root / "test_prefix_mask_audit.csv")
    _write_csv(static_parity, args.output_root / "test_prefix_static_parity_audit.csv")
    _write_csv(cohort, args.output_root / "w1_p1_course_cohort_label_support.csv")
    _write_csv(per_class, args.output_root / "w1_p1_per_class_predictions.csv")
    _write_csv(overall, args.output_root / "w1_p1_prediction_summary.csv")
    _write_csv(all_phase_summary, args.output_root / "w1_validation_test_p1_p4_summary.csv")
    _write_csv(p1_slices, args.output_root / "w1_p1_seen_unseen_strict_overlap_metrics.csv")
    summary = {
        "audit": "local_read_only_prefix_validation_alignment_v1",
        "task": args.task,
        "phase_view_root": str(phase_root),
        "test_prefix_root": str(prefix_root),
        "model_root": str(args.model_root),
        "layout_count": int(signatures["n_layouts"].sum()) if not signatures.empty else 0,
        "layout_signature_count": int(len(signatures)),
        "static_column_count": int(len(static_columns)),
        "static_columns_requiring_manual_review": int(static_columns["manual_review_required"].sum()) if not static_columns.empty else 0,
        "prefix_future_mask_all_samples_ok": bool(prefix_audit["future_mask_ok_sample"].all()),
        "prefix_scan_scope": "all_files_all_row_groups" if args.full_scan else "first_file_row_group_0",
        "macro_f1_convention": "fixed_k3_zero_division_0 with present-class macro reported beside it",
        "test_static_prefix_parity_ok": bool(static_parity["values_identical"].all()),
        "w1_p1_prediction_cells": int(len(overall)),
        "w1_p1_slice_metric_cells": int(len(p1_slices)),
        "w1_validation_test_p1_p4_cells": int(len(all_phase_summary)),
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
