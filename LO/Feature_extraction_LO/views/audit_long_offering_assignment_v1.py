"""Audit long offerings, assignment uniqueness, and P1--P4 strictness for LO.

This is an audit of the immutable V2.2 overlap-audit R2 registry.  It does
not create a split or alter assignments.  The output is deliberately small,
aggregate-only evidence for the split-closure report.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from pyspark.sql import SparkSession, functions as F

PROJECT_ROOT = os.environ.get("PROJECT_ROOT") or str(Path(__file__).resolve().parents[1])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from common.pipeline_logging import (flush_json_log, get_logger, log_dataframe,
        log_event, log_run_context, log_run_finished, log_write, start_run_timer,
        write_parquet)
    from common.protocol_config import load_protocol_config, path_from_config
except ModuleNotFoundError:
    from pipeline_logging import (flush_json_log, get_logger, log_dataframe,
        log_event, log_run_context, log_run_finished, log_write, start_run_timer,
        write_parquet)
    from protocol_config import load_protocol_config, path_from_config

TASK = "LO"
P = load_protocol_config()
TASK_BASE = path_from_config(P, "task_feature_base").rstrip("/")
REGISTRY_SOURCE = os.environ.get(
    "SPLIT_LONG_AUDIT_REGISTRY_SOURCE",
    f"{TASK_BASE}/{TASK}/hybrid/split_registry_v2_2_overlap_audit_v1_r2",
).rstrip("/")
OUT = os.environ.get(
    "SPLIT_LONG_AUDIT_OUTPUT",
    f"{TASK_BASE}/{TASK}/hybrid/long_offering_assignment_audit_v1",
).rstrip("/")
AUDIT_RELEASE = os.environ.get("SPLIT_LONG_AUDIT_RELEASE", "v3_1_scored_signal_excluded")

spark = (SparkSession.builder.appName("audit_lo_long_offering_assignment_v1")
    .config("spark.sql.session.timeZone", "UTC").getOrCreate())
logger = get_logger("audit_lo_long_offering_assignment_v1", path_from_config(P, "logs"))
started = start_run_timer()
log_run_context(logger, spark, {
    "task": TASK, "registry_source": REGISTRY_SOURCE, "output": OUT,
    "long_offering_threshold_days": 270,
    "release": AUDIT_RELEASE,
    "contract": "aggregate_audit_only__does_not_modify_split_assignments",
})

manifest = spark.read.parquet(f"{REGISTRY_SOURCE}/manifest/")
context = spark.read.parquet(f"{REGISTRY_SOURCE}/temporal_strict_context/")
unit_cols = ["offering_id", "timeline_source"]
required_manifest = set(unit_cols + ["rolling_block", "offering_start_date", "offering_end_date", "n"])
required_context = set(unit_cols + ["enrollment_id", "window_id", "split"] + [f"temporal_strict_P{i}" for i in range(1, 5)])
missing = sorted(required_manifest.difference(manifest.columns))
if missing:
    raise ValueError(f"Manifest missing required columns: {missing}")
missing = sorted(required_context.difference(context.columns))
if missing:
    raise ValueError(f"Strict context missing required columns: {missing}")

slice_expr = (F.when(F.col("rolling_block") == "A", "A")
    .when(F.col("rolling_block").isin("B", "C"), "T1")
    .when(F.col("rolling_block").isin("D", "E"), "T2")
    .when(F.col("rolling_block").isin("F", "G"), "T3")
    .otherwise("UNASSIGNED"))
units = (manifest.select(*unit_cols, "rolling_block", "offering_start_date", "offering_end_date", "n")
    .dropDuplicates(unit_cols + ["rolling_block", "offering_start_date", "offering_end_date", "n"])
    .withColumn("temporal_slice", slice_expr)
    .withColumn("duration_days", F.datediff("offering_end_date", "offering_start_date"))
    .withColumn("long_offering_flag", (F.col("duration_days") > F.lit(270)).cast("int")))

duration_by_timeline = (units.groupBy("timeline_source").agg(
    F.count("*").alias("offering_count"), F.sum("n").alias("enrollment_count"),
    F.expr("percentile_approx(duration_days, 0.5)").alias("duration_days_p50"),
    F.expr("percentile_approx(duration_days, 0.9)").alias("duration_days_p90"),
    F.max("duration_days").alias("duration_days_max"),
    F.sum("long_offering_flag").alias("n_long_offerings"),
    F.sum(F.when(F.col("long_offering_flag") == 1, F.col("n")).otherwise(0)).alias("long_offering_enrollment_count"))
    .withColumn("long_offering_enrollment_share", F.try_divide("long_offering_enrollment_count", "enrollment_count"))
    .withColumn("task", F.lit(TASK)))

slice_assignment_summary = (units.groupBy("temporal_slice", "timeline_source").agg(
    F.count("*").alias("offering_timeline_count"), F.sum("n").alias("enrollment_count"),
    F.sum("long_offering_flag").alias("n_long_offerings"),
    F.sum(F.when(F.col("long_offering_flag") == 1, F.col("n")).otherwise(0)).alias("long_offering_enrollment_count"))
    .withColumn("long_offering_enrollment_share", F.try_divide("long_offering_enrollment_count", "enrollment_count"))
    .withColumn("task", F.lit(TASK)))

# ``n`` is the enrollment mass of one offering_id x timeline_source unit.
# Its distribution answers whether near-identical validation/test label shares
# are produced by many tiny units rather than genuinely independent courses.
unit_size_distribution = (units.groupBy("temporal_slice", "timeline_source").agg(
    F.count("*").alias("offering_timeline_count"),
    F.sum("n").alias("enrollment_count"),
    F.expr("percentile_approx(n, 0.5)").alias("unit_enrollment_p50"),
    F.expr("percentile_approx(n, 0.9)").alias("unit_enrollment_p90"),
    F.max("n").alias("unit_enrollment_max"),
    F.sum(F.when(F.col("n") <= 5, 1).otherwise(0)).alias("n_units_le_5"),
    F.sum(F.when(F.col("n") <= 5, F.col("n")).otherwise(0)).alias("enrollment_count_units_le_5"))
    .withColumn("share_units_le_5", F.try_divide("n_units_le_5", "offering_timeline_count"))
    .withColumn("share_enrollments_units_le_5", F.try_divide("enrollment_count_units_le_5", "enrollment_count"))
    .withColumn("task", F.lit(TASK)))

unit_lookup = units.select(*unit_cols, "rolling_block").dropDuplicates(unit_cols + ["rolling_block"])
assignment = context.select("enrollment_id", "window_id", "split", *unit_cols).join(unit_lookup, unit_cols, "left")
unknown_block = assignment.filter(F.col("rolling_block").isNull()).count()
per_enrollment = assignment.groupBy("enrollment_id").agg(F.countDistinct("rolling_block").alias("n_rolling_blocks"))
per_window_enrollment = assignment.groupBy("window_id", "enrollment_id").agg(F.countDistinct("split").alias("n_splits_in_window"))
unit_multi_block = units.groupBy(*unit_cols).agg(F.countDistinct("rolling_block").alias("n_rolling_blocks")).filter(F.col("n_rolling_blocks") > 1).count()
assignment_qa = spark.createDataFrame([(
    TASK,
    assignment.select("enrollment_id").distinct().count(),
    assignment.count(),
    per_enrollment.filter(F.col("n_rolling_blocks") > 1).count(),
    per_window_enrollment.filter(F.col("n_splits_in_window") > 1).count(),
    unit_multi_block, unknown_block,
)], "task string, distinct_enrollment_count long, context_row_count long, n_enrollments_multiple_rolling_blocks long, n_enrollments_multiple_splits_same_window long, n_offering_timeline_multiple_rolling_blocks long, n_context_rows_without_block long")
assignment_qa = assignment_qa.withColumn("assignment_qa_pass", (
    (F.col("n_enrollments_multiple_rolling_blocks") == 0) &
    (F.col("n_enrollments_multiple_splits_same_window") == 0) &
    (F.col("n_offering_timeline_multiple_rolling_blocks") == 0) &
    (F.col("n_context_rows_without_block") == 0)).cast("int"))

strict_by_phase = None
for phase in ("P1", "P2", "P3", "P4"):
    frame = (context.groupBy("window_id", "split").agg(
        F.countDistinct("enrollment_id").alias("enrollment_count"),
        F.avg(F.col(f"temporal_strict_{phase}")).alias("temporal_strict_share"))
        .withColumn("phase_id", F.lit(phase))
        .withColumn("p_cutoff_overlap_share", F.lit(1.0) - F.col("temporal_strict_share"))
        .withColumn("strict_definition", F.lit("cutoff_time_phase_gte_tau_w"))
        .withColumn("task", F.lit(TASK)))
    strict_by_phase = frame if strict_by_phase is None else strict_by_phase.unionByName(frame)

audit_manifest = spark.createDataFrame([(
    TASK, REGISTRY_SOURCE, AUDIT_RELEASE,
    270, "A__T1=B_C__T2=D_E__T3=F_G",
    "enrollment_id_unique_rolling_block__one_split_per_window",
    "cutoff_time_phase_gte_tau_w",
)], "task string, registry_source string, source_release string, long_offering_threshold_days int, temporal_slice_mapping string, assignment_invariant string, strictness_definition string")

for name, frame in (
    ("duration_by_timeline", duration_by_timeline),
    ("slice_assignment_summary", slice_assignment_summary),
    ("unit_size_distribution", unit_size_distribution),
    ("enrollment_assignment_qa", assignment_qa),
    ("strict_by_window_split_phase", strict_by_phase),
    ("audit_manifest", audit_manifest),
):
    path = f"{OUT}/{name}/"
    write_parquet(frame, path)
    log_write(logger, name, path, log_dataframe(logger, name, frame, tuple(frame.columns[:1])))
log_event(logger, "long_offering_assignment_audit_complete", assignment_qa_pass=assignment_qa.first()["assignment_qa_pass"])
log_run_finished(logger, started)
flush_json_log(logger, spark)
