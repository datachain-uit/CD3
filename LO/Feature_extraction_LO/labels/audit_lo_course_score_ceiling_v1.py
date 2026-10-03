"""Audit observed final-score ceilings at course level for LO V3.

This audit is deliberately non-mutating: it reads the immutable LO V3 label
artifact and identifies courses whose *observed* activity-derived score cannot
reach the operational thresholds.  It also identifies the narrower proposed
``no_scored_signal_in_course`` exclusion: a course with an eligible weighted
assignment/exam component but no observed attempt in any such component.

The detailed output is the decision ledger to review before adding that reason
to ``build_lo_labels.py`` and rebuilding the LO split/views.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_file_path = globals().get("__file__")
if _file_path:
    _parent = Path(_file_path).resolve().parent
    PROJECT_ROOT = _parent.parent if (_parent.parent / "common").is_dir() else _parent
else:
    _configured_root = globals().get("PROJECT_ROOT") or os.environ.get("PROJECT_ROOT")
    PROJECT_ROOT = Path(_configured_root) if _configured_root else None
def _is_project_root(path: Path | None) -> bool:
    """Accept canonical ``common/`` and legacy flat Workspace layouts."""
    return bool(path) and ((path / "common").is_dir() or (path / "protocol_config.py").is_file())


if not _is_project_root(PROJECT_ROOT):
    # The Databricks Workspace has been used in both a canonical repository
    # layout and a flattened LO/ layout.  Resolve either without importing an
    # unrelated common package from a previous notebook execution.
    try:
        _notebook = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
        _workspace_path = Path("/Workspace") / _notebook.lstrip("/")
        PROJECT_ROOT = next(parent for parent in _workspace_path.parents if _is_project_root(parent))
    except Exception as error:
        raise RuntimeError(
            "Set PROJECT_ROOT to the LO directory containing either common/ or protocol_config.py, plus labels/."
        ) from error
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pyspark.sql import SparkSession, functions as F

try:
    from common.pipeline_logging import (
        flush_json_log, get_logger, log_dataframe, log_event, log_run_context,
        log_run_finished, log_write, start_run_timer, write_parquet,
    )
    from common.protocol_config import load_protocol_config, path_from_config
except ModuleNotFoundError:
    from pipeline_logging import (
        flush_json_log, get_logger, log_dataframe, log_event, log_run_context,
        log_run_finished, log_write, start_run_timer, write_parquet,
    )
    from protocol_config import load_protocol_config, path_from_config


PROTOCOL = load_protocol_config()
EXPECTED_VERSION = "lo_final_score_catalog_normalized_v3_1"
if PROTOCOL["labels"].get("lo_version") != EXPECTED_VERSION:
    raise ValueError(f"Course-ceiling audit requires lo_version={EXPECTED_VERSION}.")

LABEL_SOURCE = os.environ.get("LO_CEILING_LABEL_SOURCE", path_from_config(PROTOCOL, "lo_labels")).rstrip("/")
OUTPUT = os.environ.get(
    "LO_CEILING_AUDIT_OUTPUT",
    f"{PROTOCOL['output_base']}/labels/lo_labels_v3_1_scored_signal_excluded_audit/course_score_ceiling_v3_1",
).rstrip("/")

spark = SparkSession.builder.appName("audit_lo_course_score_ceiling_v1").config(
    "spark.sql.session.timeZone", "UTC"
).getOrCreate()
logger = get_logger("audit_lo_course_score_ceiling_v1", f"{PROTOCOL['output_base']}/logs")
started = start_run_timer()
log_run_context(logger, spark, {
    "label_source": LABEL_SOURCE,
    "output": OUTPUT,
    "label_rule_version": EXPECTED_VERSION,
    "ceiling_definition": "max observed primary performance_score among proxy-eligible enrollments in a course",
    "proposed_exclusion": (
        "no_scored_signal_in_course = eligible course with positive assignment or exam weight "
        "and zero observed attempts for every positively weighted graded component"
    ),
})

required = {
    "course_id", "enrollment_id", "proxy_exclusion_reason", "performance_score",
    "video_weight", "assignment_weight", "exam_weight", "watched_videos",
    "assignment_problem_attempted_count", "exam_problem_attempted_count",
}
labels = spark.read.parquet(LABEL_SOURCE + "/")
missing = required.difference(labels.columns)
if missing:
    raise ValueError(f"LO label artifact missing course-ceiling fields: {sorted(missing)}")

eligible = F.col("proxy_exclusion_reason").isNull()
graded_component = (F.col("assignment_weight") > 0) | (F.col("exam_weight") > 0)
weighted_graded_attempt = (
    ((F.col("assignment_weight") > 0) & (F.coalesce(F.col("assignment_problem_attempted_count"), F.lit(0)) > 0))
    | ((F.col("exam_weight") > 0) & (F.coalesce(F.col("exam_problem_attempted_count"), F.lit(0)) > 0))
)
weighted_activity_signal = (
    ((F.col("video_weight") > 0) & (F.coalesce(F.col("watched_videos"), F.lit(0)) > 0))
    | weighted_graded_attempt
)

course = (
    labels.groupBy("course_id")
    .agg(
        F.count("enrollment_id").alias("raw_enrollment_count"),
        F.sum(F.when(eligible, 1).otherwise(0)).cast("long").alias("eligible_enrollment_count"),
        F.max(F.when(eligible, F.col("performance_score"))).alias("course_score_ceiling_observed"),
        F.max(F.when(eligible, F.col("video_weight"))).alias("video_weight"),
        F.max(F.when(eligible, F.col("assignment_weight"))).alias("assignment_weight"),
        F.max(F.when(eligible, F.col("exam_weight"))).alias("exam_weight"),
        F.max(F.when(eligible & graded_component, 1).otherwise(0)).alias("has_weighted_graded_component"),
        F.max(F.when(eligible & weighted_graded_attempt, 1).otherwise(0)).alias("has_observed_weighted_graded_attempt"),
        F.max(F.when(eligible & weighted_activity_signal, 1).otherwise(0)).alias("has_observed_weighted_activity_signal"),
        F.max(F.when(eligible, F.coalesce(F.col("watched_videos"), F.lit(0)))).alias("max_watched_videos"),
        F.max(F.when(eligible, F.coalesce(F.col("assignment_problem_attempted_count"), F.lit(0)))).alias("max_assignment_problem_attempted_count"),
        F.max(F.when(eligible, F.coalesce(F.col("exam_problem_attempted_count"), F.lit(0)))).alias("max_exam_problem_attempted_count"),
    )
    .withColumn("eligible_course", F.col("eligible_enrollment_count") > 0)
    .withColumn("ceiling_lt_60", F.col("eligible_course") & (F.col("course_score_ceiling_observed") < 60))
    .withColumn("ceiling_lt_85", F.col("eligible_course") & (F.col("course_score_ceiling_observed") < 85))
    .withColumn(
        "proposed_no_scored_signal_in_course",
        F.col("eligible_course")
        & (F.col("has_weighted_graded_component") == 1)
        & (F.col("has_observed_weighted_graded_attempt") == 0),
    )
    .withColumn(
        "decision_status",
        F.when(F.col("proposed_no_scored_signal_in_course"), F.lit("PROPOSED_EXCLUDE"))
        .when(F.col("ceiling_lt_60"), F.lit("REVIEW_CEILING_LT_60"))
        .when(F.col("ceiling_lt_85"), F.lit("REVIEW_CEILING_LT_85"))
        .otherwise(F.lit("NO_CEILING_FLAG")),
    )
)

summary = course.agg(
    F.count("course_id").alias("course_count_all"),
    F.sum("raw_enrollment_count").alias("enrollment_count_all"),
    F.sum(F.when(F.col("eligible_course"), 1).otherwise(0)).alias("eligible_course_count"),
    F.sum("eligible_enrollment_count").alias("eligible_enrollment_count"),
    F.sum(F.when(F.col("ceiling_lt_60"), 1).otherwise(0)).alias("course_count_ceiling_lt_60"),
    F.sum(F.when(F.col("ceiling_lt_60"), F.col("eligible_enrollment_count")).otherwise(0)).alias("enrollment_count_ceiling_lt_60"),
    F.sum(F.when(F.col("ceiling_lt_85"), 1).otherwise(0)).alias("course_count_ceiling_lt_85"),
    F.sum(F.when(F.col("ceiling_lt_85"), F.col("eligible_enrollment_count")).otherwise(0)).alias("enrollment_count_ceiling_lt_85"),
    F.sum(F.when(F.col("proposed_no_scored_signal_in_course"), 1).otherwise(0)).alias("course_count_proposed_exclude"),
    F.sum(F.when(F.col("proposed_no_scored_signal_in_course"), F.col("eligible_enrollment_count")).otherwise(0)).alias("enrollment_count_proposed_exclude"),
).withColumn(
    "share_eligible_enrollments_proposed_exclude",
    F.try_divide("enrollment_count_proposed_exclude", "eligible_enrollment_count"),
)

by_weights = course.groupBy("video_weight", "assignment_weight", "exam_weight", "decision_status").agg(
    F.count("course_id").alias("course_count"),
    F.sum("eligible_enrollment_count").alias("eligible_enrollment_count"),
    F.min("course_score_ceiling_observed").alias("ceiling_min"),
    F.expr("percentile_approx(course_score_ceiling_observed, 0.5)").alias("ceiling_p50"),
    F.max("course_score_ceiling_observed").alias("ceiling_max"),
)

manifest = spark.createDataFrame([(
    EXPECTED_VERSION, LABEL_SOURCE, OUTPUT,
    "max eligible performance_score per course",
    "positive weighted assignment/exam component with zero course-wide observed attempt",
)], ["label_rule_version", "label_source", "output", "course_score_ceiling_definition", "proposed_no_scored_signal_definition"])

for name, frame, keys in (
    ("course_score_ceiling_by_course", course.orderBy("decision_status", "course_id"), ("course_id",)),
    ("course_score_ceiling_summary", summary, ()),
    ("course_score_ceiling_by_weights", by_weights, ("decision_status",)),
    ("audit_manifest", manifest, ()),
):
    path = f"{OUTPUT}/{name}/"
    write_parquet(frame, path)
    rows = log_dataframe(logger, name, frame, keys)
    log_write(logger, name, path, rows)

log_event(logger, "lo_course_score_ceiling_audit_written")
log_run_finished(logger, started)
flush_json_log(logger, spark)
