"""Stage task-owned temporal splits for train-only preprocessing/imputation.

Run through a task wrapper, for example:
``python -m imputation.prepare --scenario hybrid --window W1 --test-phase P1``.
The job writes V1 raw+mask data only.  It deliberately does not fit an
encoder, scaler or imputer: those states must be fitted on the real train
split of the selected run, never on validation/test.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone

from pyspark.sql import SparkSession, functions as F

from common.pipeline_logging import (
    flush_json_log, get_logger, log_dataframe, log_event, log_run_context,
    log_run_finished, log_write, start_run_timer, write_parquet,
)
from common.protocol_config import load_protocol_config, path_from_config


TASK_SPECS = {
    "CQ": {"label": "CQ_label_final", "task_values": ("CQ",)},
    "LO": {"label": "LO_performance_label_3", "task_values": ("LO_operational",)},
}
SPLITS = {
    "W1": {"train": ("A",), "validation": ("B",), "test": ("C",)},
    "W2": {"train": ("A", "B", "C"), "validation": ("D",), "test": ("E",)},
    "W3": {"train": ("A", "B", "C", "D", "E"), "validation": ("F",), "test": ("G",)},
}
PHASES = ("P1", "P2", "P3", "P4")
VIEW_RELEASES = {"CQ": "phase_views_v2_2", "LO": "phase_views_v3_1_scored_signal_excluded"}
PROVENANCE_COLUMNS = {
    "enrollment_id", "user_id", "course_id", "offering_id", "task", "window", "split", "split_id", "phase",
    "temporal_block", "timeline_source", "prefix_parent_id", "prediction_phase",
    "label_availability_time", "label_availability_source", "label_rule_version",
    # CQ vector-label provenance.  These values define the target and must
    # never be exposed as model predictors.
    "COELO_final", "AFELO_final", "ACELO_final", "CQ_label_vector",
    "CQ_distance_euclidean_final", "CQ_proximity_final",
    "TRIAD_distance_final", "observed_dimension_mask",
    "cq_exclusion_reason", "proxy_exclusion_reason", "decision", "proxy_reason",
    "prediction_cutoff_time", "performance_score", "primary_risk_set",
    "outcome_observed_at_cutoff", "label_available_by_cutoff",
}


def parser(default_task: str) -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--task", choices=tuple(TASK_SPECS), default=default_task)
    result.add_argument("--scenario", choices=("hybrid",), default="hybrid")
    result.add_argument("--window", choices=tuple(SPLITS), required=True)
    result.add_argument("--test-phase", choices=PHASES, required=True)
    result.add_argument("--view-source", default="", help="Absolute immutable phase-view directory; defaults to the locked task release.")
    result.add_argument("--seed", type=int, default=20260915)
    return result


def model_columns(dataframe, label_column: str, prediction_phase: str) -> list[str]:
    """Return only columns observable at the selected prediction phase."""
    phase_index = PHASES.index(prediction_phase)
    future_suffixes = tuple(f"_P{index}" for index in range(phase_index + 2, len(PHASES) + 1))
    columns = []
    for field in dataframe.schema.fields:
        name = field.name
        data_type = field.dataType.simpleString()
        if name in PROVENANCE_COLUMNS or name == label_column:
            continue
        if name.startswith("label_available_by_") or name.startswith("outcome_"):
            continue
        if name.startswith("LO_performance_label_") or name.startswith("CQ_label_"):
            continue
        if data_type == "timestamp" or data_type == "date":
            continue
        # Future phase slots are structurally unavailable, not missing values.
        # They are excluded before any imputer can fit or transform them.
        if name.endswith(future_suffixes):
            continue
        columns.append(name)
    return columns


def main(default_task: str) -> None:
    args = parser(default_task).parse_args()
    protocol = load_protocol_config()
    task_spec = TASK_SPECS[args.task]
    label_column = task_spec["label"]
    base = path_from_config(protocol, "task_feature_base")
    input_path = args.view_source.rstrip("/") or f"{base}/{args.task}/{args.scenario}/{VIEW_RELEASES[args.task]}"
    if input_path.endswith("phase_views_v1"):
        raise ValueError("phase_views_v1 is retired for active experiments; provide a locked versioned view source.")
    output_base = f"{base}/{args.task}/{args.scenario}/imputation_v1/{args.window}/{args.test_phase}/raw"

    spark = SparkSession.builder.appName(f"prepare_{args.task.lower()}_imputation").config(
        "spark.sql.session.timeZone", "UTC"
    ).getOrCreate()
    logger = get_logger(f"prepare_{args.task.lower()}_imputation", path_from_config(protocol, "logs"))
    log_run_context(logger, spark, vars(args) | {"input_path": input_path, "output_base": output_base})
    started = start_run_timer()

    source = spark.read.parquet(input_path)
    required = {"split_id", "phase", label_column, *task_spec["task_values"]}
    missing = {label_column, "split_id", "phase"}.difference(source.columns)
    if missing:
        raise ValueError(f"Input is missing required columns: {sorted(missing)}")
    if "task" in source.columns:
        source = source.filter(F.col("task").isin(*task_spec["task_values"]))
    source = source.filter(
        F.col(label_column).isNotNull()
        & (F.col("window") == F.lit(args.window))
        & (F.col("phase") == F.lit(args.test_phase))
    )
    duplicate = source.groupBy("enrollment_id").count().filter(F.col("count") > 1)
    if duplicate.limit(1).count():
        raise ValueError("Input view violates one-row-per-enrollment grain; run the release grain audit before staging.")

    features = model_columns(source, label_column, args.test_phase)
    if not features:
        raise ValueError("No usable model columns after provenance/label exclusion")
    feature_hash = hashlib.sha256("\n".join(features).encode("utf-8")).hexdigest()
    selected = source.select(*[column for column in source.columns if column in PROVENANCE_COLUMNS], label_column, *features)

    split_frames = {}
    for split_name in ("train", "validation", "test"):
        frame = selected.filter(F.col("split_id") == F.lit(split_name))
        split_frames[split_name] = frame

    metadata_columns = [column for column in selected.columns if column in PROVENANCE_COLUMNS]
    for split_name, frame in split_frames.items():
        model_input = frame.select(label_column, *features)
        provenance = frame.select(*metadata_columns, label_column)
        model_path = f"{output_base}/{split_name}/model_input/"
        provenance_path = f"{output_base}/{split_name}/provenance/"
        write_parquet(model_input, model_path)
        write_parquet(provenance, provenance_path)
        rows = log_dataframe(logger, f"{args.task}_{args.window}_{args.test_phase}_{split_name}_v0", model_input, (label_column,))
        log_write(logger, f"{args.task}_{args.window}_{args.test_phase}_{split_name}_model_input", model_path, rows)

    summary = None
    for split_name, frame in split_frames.items():
        current = frame.groupBy(label_column).agg(F.count(F.lit(1)).alias("row_count")).withColumn("split", F.lit(split_name))
        summary = current if summary is None else summary.unionByName(current)
    summary = summary.withColumn("task", F.lit(args.task)).withColumn("scenario", F.lit(args.scenario)).withColumn("window", F.lit(args.window)).withColumn("test_phase", F.lit(args.test_phase))
    summary_path = f"{output_base}/audit/class_distribution/"
    write_parquet(summary, summary_path)
    summary_rows = log_dataframe(logger, f"{args.task}_{args.window}_{args.test_phase}_imputation_split_summary", summary, ("split", label_column))
    log_write(logger, f"{args.task}_{args.window}_{args.test_phase}_imputation_split_summary", summary_path, summary_rows)

    manifest = {
        "task": args.task, "scenario": args.scenario, "window": args.window,
        "test_phase": args.test_phase, "pipeline_variant": "raw_v1",
        "seed": args.seed, "label_column": label_column, "feature_count": len(features),
        "feature_list_sha256": feature_hash, "input_path": input_path,
        "fit_policy": "raw staging only; the later preprocessor fit uses TRAIN_POOLED_P1_P4 and transforms validation/test only",
        "phase_policy": "all three splits use only the requested prediction_phase; future-phase columns are excluded as structurally unavailable, never imputed",
        "augmentation_policy": "any augmentation or resampling is train-only after preprocessing",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    manifest_path = f"{output_base}/manifest/"
    spark.createDataFrame([(json.dumps(manifest, ensure_ascii=False),)], "json string").write.mode("overwrite").text(manifest_path)
    log_event(logger, "imputation_v1_staged", **manifest, output_base=output_base)
    log_run_finished(logger, started)
    flush_json_log(logger, spark)


if __name__ == "__main__":
    main("CQ")
