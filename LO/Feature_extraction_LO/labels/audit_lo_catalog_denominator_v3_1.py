"""Audit whether LO V3.1 catalog denominators reflect usable scored content.

This is a read-only decision audit.  It compares every course's assignment and
exam problem catalog with the set of catalog problems that received at least
one automatic-score attempt from any enrollment.  It also joins the frozen
LO V3.1 label artifact and, when supplied, its split manifest.  Nothing here
changes labels, split assignments, or feature views.

Outputs:
* ``course_catalog_activity``: one row/course; the review ledger.
* ``ceiling_band_summary``: <60, 60--<85, >=85 score-ceiling bands.
* ``course_activity_summary``: active-catalog distributions by ceiling band.
* ``slice_ceiling_coverage``: A/T1/T2/T3 enrollment coverage for >=60/>=85.

Set ``LO_CATALOG_MANIFEST_SOURCE`` to a manifest containing ``course_id``
and either ``rolling_block`` or a block/window assignment.  The audit still
runs without it, but intentionally omits the slice table.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_file = globals().get("__file__")
PROJECT_ROOT = Path(_file).resolve().parents[1] if _file else Path(
    globals().get("PROJECT_ROOT") or os.environ.get("PROJECT_ROOT", "")
)


def _is_project_root(path: Path) -> bool:
    return (path / "common").is_dir() or (path / "protocol_config.py").is_file()


# Both layouts exist in the Workspace: either ``.../LO`` is the project root,
# or it is the parent directory of ``Feature_extraction_LO``.  Accept both so
# a notebook never silently imports a stale global ``common`` package.
if not _is_project_root(PROJECT_ROOT):
    for child in ("Feature_extraction_LO", "feature_extraction", "feature_extract"):
        candidate = PROJECT_ROOT / child
        if _is_project_root(candidate):
            PROJECT_ROOT = candidate
            break
if not _is_project_root(PROJECT_ROOT):
    raise RuntimeError(
        "Set PROJECT_ROOT to Feature_extraction_LO (or its parent LO directory) containing common/ or protocol_config.py."
    )
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pyspark.sql import SparkSession, Window, functions as F

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


P = load_protocol_config()
EXPECTED = "lo_final_score_catalog_normalized_v3_1"
if P["labels"].get("lo_version") != EXPECTED:
    raise ValueError(f"Catalog audit requires lo_version={EXPECTED}.")

OUT_BASE = P["output_base"].rstrip("/")
RAW_BASE = P["raw_base"].rstrip("/")
ANALYSIS_BASE = path_from_config(P, "analysis_base").rstrip("/")
LABEL_SOURCE = os.environ.get("LO_CATALOG_LABEL_SOURCE", path_from_config(P, "lo_labels")).rstrip("/")
MANIFEST_SOURCE = os.environ.get("LO_CATALOG_MANIFEST_SOURCE", "").rstrip("/")
WINDOWS_SOURCE = os.environ.get(
    "LO_CATALOG_WINDOWS_SOURCE", f"{OUT_BASE}/features/scenarios/hybrid/enrollment_windows"
).rstrip("/")
OUT = os.environ.get(
    "LO_CATALOG_AUDIT_OUTPUT",
    f"{OUT_BASE}/tasks/LO/hybrid/catalog_denominator_audit_v3_1",
).rstrip("/")

spark = SparkSession.builder.appName("audit_lo_catalog_denominator_v3_1").config(
    "spark.sql.session.timeZone", "UTC"
).getOrCreate()
logger = get_logger("audit_lo_catalog_denominator_v3_1", path_from_config(P, "logs"))
started = start_run_timer()
log_run_context(logger, spark, {
    "label_source": LABEL_SOURCE, "manifest_source": MANIFEST_SOURCE or None,
    "output": OUT, "rule_version": EXPECTED,
    "active_definition": "distinct catalog problem with >=1 cleaned automatic-score event in its course",
})

labels = spark.read.parquet(LABEL_SOURCE + "/")
required = {"course_id", "enrollment_id", "proxy_exclusion_reason", "performance_score",
            "assignment_weight", "exam_weight"}
missing = required.difference(labels.columns)
if missing:
    raise ValueError(f"LO label artifact missing fields: {sorted(missing)}")
eligible = labels.filter(F.col("proxy_exclusion_reason").isNull()).select(
    "course_id", "enrollment_id", "performance_score"
)

# Do not re-parse ``course_limit.csv`` here.  Some raw rows carry malformed
# CSV fields (for example a season-list in a numeric position), while the
# immutable V3.1 label artifact already contains the validated weights that
# actually governed its score formula.  Reading them from that artifact keeps
# this audit source-faithful and avoids a second, inconsistent parser.
weights = (labels.groupBy("course_id").agg(
    F.max(F.col("assignment_weight").cast("double")).alias("assignment_weight"),
    F.max(F.col("exam_weight").cast("double")).alias("exam_weight"),
).fillna(0.0, subset=["assignment_weight", "exam_weight"]))
catalog = spark.read.parquet(f"{OUT_BASE}/course_problem_catalog/").select(
    "course_id", "problem_id", "chapter"
).dropDuplicates(["course_id", "problem_id"])

# Same final-chapter exam partition as the V3.1 label builder.
chapter = (catalog.filter(F.col("chapter").isNotNull())
    .withColumn("parts", F.expr("transform(split(chapter, '\\\\.'), x -> try_cast(x as int))"))
    .filter("NOT exists(parts, x -> x IS NULL)"))
exam_courses = chapter.join(weights.filter(F.col("exam_weight") > 0).select("course_id"), "course_id")
last = exam_courses.groupBy("course_id").agg(F.max("parts").alias("last_parts"))
exam = (exam_courses.join(last, "course_id").filter(F.col("parts") == F.col("last_parts"))
    .select("course_id", "problem_id").withColumn("is_exam", F.lit(1)))
flagged = (catalog.select("course_id", "problem_id").join(exam, ["course_id", "problem_id"], "left")
    .withColumn("is_exam", F.coalesce("is_exam", F.lit(0))))

# ``problem_events_clean`` is also the source used by the label builder; no
# learner-level synthetic/derived data can influence this audit.
attempted = (spark.read.parquet(f"{OUT_BASE}/problem_events_clean/")
    .select("course_id", "problem_id").dropDuplicates(["course_id", "problem_id"])
    .withColumn("is_active_catalog_problem", F.lit(1)))
activity = flagged.join(attempted, ["course_id", "problem_id"], "left").withColumn(
    "is_active_catalog_problem", F.coalesce("is_active_catalog_problem", F.lit(0))
)
catalog_course = (activity.groupBy("course_id").agg(
    F.sum(F.when(F.col("is_exam") == 0, 1).otherwise(0)).alias("assignment_catalog_problem_count"),
    F.sum(F.when(F.col("is_exam") == 1, 1).otherwise(0)).alias("exam_catalog_problem_count"),
    F.sum(F.when((F.col("is_exam") == 0) & (F.col("is_active_catalog_problem") == 1), 1).otherwise(0)).alias("assignment_active_catalog_problem_count"),
    F.sum(F.when((F.col("is_exam") == 1) & (F.col("is_active_catalog_problem") == 1), 1).otherwise(0)).alias("exam_active_catalog_problem_count"),
))
label_course = eligible.groupBy("course_id").agg(
    F.count("enrollment_id").alias("eligible_enrollment_count"),
    F.max("performance_score").alias("course_score_ceiling_observed")
)
course = (label_course.join(weights, "course_id", "left").join(catalog_course, "course_id", "left")
    .fillna(0, subset=["assignment_catalog_problem_count", "exam_catalog_problem_count",
                        "assignment_active_catalog_problem_count", "exam_active_catalog_problem_count"])
    .withColumn("assignment_active_catalog_ratio", F.try_divide("assignment_active_catalog_problem_count", "assignment_catalog_problem_count"))
    .withColumn("exam_active_catalog_ratio", F.try_divide("exam_active_catalog_problem_count", "exam_catalog_problem_count"))
    # A catalog is relevant only when its component has positive weight in the
    # actual V3.1 formula.  A video-only course may still have stale problem
    # catalog rows; those rows must not manufacture a zero active ratio.
    .withColumn("scored_catalog_problem_count",
        F.when(F.col("assignment_weight") > 0, F.col("assignment_catalog_problem_count")).otherwise(0)
        + F.when(F.col("exam_weight") > 0, F.col("exam_catalog_problem_count")).otherwise(0))
    .withColumn("active_scored_catalog_problem_count",
        F.when(F.col("assignment_weight") > 0, F.col("assignment_active_catalog_problem_count")).otherwise(0)
        + F.when(F.col("exam_weight") > 0, F.col("exam_active_catalog_problem_count")).otherwise(0))
    .withColumn("active_scored_catalog_ratio", F.try_divide("active_scored_catalog_problem_count", "scored_catalog_problem_count"))
    .withColumn("ceiling_band", F.when(F.col("course_score_ceiling_observed") < 60, "LT_60")
        .when(F.col("course_score_ceiling_observed") < 85, "GE_60_LT_85").otherwise("GE_85"))
)

band = (course.groupBy("ceiling_band").agg(
    F.count("course_id").alias("course_count"), F.sum("eligible_enrollment_count").alias("enrollment_count"),
    F.expr("percentile_approx(active_scored_catalog_ratio, 0.5)").alias("active_scored_catalog_ratio_p50"),
    F.expr("percentile_approx(active_scored_catalog_ratio, 0.9)").alias("active_scored_catalog_ratio_p90"),
    F.avg("active_scored_catalog_ratio").alias("active_scored_catalog_ratio_mean"),
    F.sum(F.when(F.col("active_scored_catalog_problem_count") == 0, 1).otherwise(0)).alias("course_count_zero_active_scored_catalog"),
).withColumn("enrollment_share", F.col("enrollment_count") / F.sum("enrollment_count").over(Window.partitionBy())))

summary = course.agg(
    F.count("course_id").alias("course_count"), F.sum("eligible_enrollment_count").alias("eligible_enrollment_count"),
    F.sum(F.when(F.col("course_score_ceiling_observed") < 60, F.col("eligible_enrollment_count")).otherwise(0)).alias("enrollments_ceiling_lt_60"),
    F.sum(F.when(F.col("course_score_ceiling_observed") < 85, F.col("eligible_enrollment_count")).otherwise(0)).alias("enrollments_ceiling_lt_85"),
    F.sum(F.when(F.col("course_score_ceiling_observed") >= 60, F.col("eligible_enrollment_count")).otherwise(0)).alias("enrollments_ceiling_ge_60"),
    F.sum(F.when(F.col("course_score_ceiling_observed") >= 85, F.col("eligible_enrollment_count")).otherwise(0)).alias("enrollments_ceiling_ge_85"),
).withColumn("share_enrollments_ceiling_ge_60", F.try_divide("enrollments_ceiling_ge_60", "eligible_enrollment_count")) \
 .withColumn("share_enrollments_ceiling_ge_85", F.try_divide("enrollments_ceiling_ge_85", "eligible_enrollment_count"))

outputs = [("course_catalog_activity", course.orderBy("course_id"), ("course_id",)),
           ("ceiling_band_summary", band, ("ceiling_band",)),
           ("summary", summary, ())]
if MANIFEST_SOURCE:
    manifest = spark.read.parquet(MANIFEST_SOURCE + "/")
    unit_cols = ["offering_id", "timeline_source"]
    required_manifest = set(unit_cols + ["rolling_block"])
    missing_manifest = sorted(required_manifest.difference(manifest.columns))
    if missing_manifest:
        raise ValueError(
            "LO_CATALOG_MANIFEST_SOURCE must point to the registry's manifest/ "
            f"(not a materialized split manifest). Missing: {missing_manifest}"
        )

    # Rebuild the enrollment -> offering/timeline lookup *exactly* as the
    # V3 split builder does.  In particular, ``timeline_source`` comes from
    # enrollment_windows, not from the schedule fallback: they can differ for
    # hybrid fallback enrollments.  The registry itself is offering-level,
    # hence it should not be expected to contain course_id/enrollment_id.
    windows = (spark.read.parquet(WINDOWS_SOURCE + "/")
        .select("enrollment_id", F.col("offering_id").cast("string").alias("window_offering_id"),
                F.col("timeline_source").alias("window_timeline_source"))
        .dropDuplicates(["enrollment_id"]))
    timeline = (spark.read.parquet(f"{ANALYSIS_BASE}/shifted_offering_assignments/")
        .select("enrollment_id", F.col("offering_id").cast("string").alias("schedule_offering_id"))
        .withColumn("schedule_timeline_source", F.lit("course_specific_timeline")))
    anchored = (spark.read.parquet(f"{ANALYSIS_BASE}/enrollment_anchored_pseudo_offering_assignments/")
        .select("enrollment_id", F.col("pseudo_offering_id").cast("string").alias("schedule_offering_id"))
        .withColumn("schedule_timeline_source", F.lit("enrollment_anchored_proxy")))
    fallback = (spark.read.parquet(f"{ANALYSIS_BASE}/global_template_offering_assignments/")
        .select("enrollment_id", F.col("offering_id").cast("string").alias("schedule_offering_id"))
        .withColumn("schedule_timeline_source", F.lit("global_template_fallback"))
        .join(anchored.select("enrollment_id"), "enrollment_id", "left_anti"))
    schedules = timeline.unionByName(anchored).unionByName(fallback).dropDuplicates(["enrollment_id"])
    enrollment_units = (windows.join(schedules, "enrollment_id", "inner")
        .select("enrollment_id",
            F.coalesce("window_offering_id", "schedule_offering_id").alias("offering_id"),
            F.col("window_timeline_source").alias("timeline_source")))
    blocks = manifest.select(*unit_cols, "rolling_block").dropDuplicates(unit_cols + ["rolling_block"])
    if blocks.groupBy(*unit_cols).count().filter(F.col("count") != 1).limit(1).count():
        raise ValueError("Registry manifest maps an offering/timeline unit to more than one rolling block.")
    temporal_slice = (F.when(F.col("rolling_block") == "A", "A")
        .when(F.col("rolling_block").isin("B", "C"), "T1")
        .when(F.col("rolling_block").isin("D", "E"), "T2")
        .when(F.col("rolling_block").isin("F", "G"), "T3")
        .otherwise("UNASSIGNED"))
    slices = (eligible.select("enrollment_id", "course_id")
        .join(enrollment_units, "enrollment_id", "left")
        .join(blocks, unit_cols, "left")
        .withColumn("slice", temporal_slice)
        .join(course.select("course_id", "course_score_ceiling_observed"), "course_id")
        .groupBy("slice").agg(F.count("enrollment_id").alias("enrollment_count"),
            F.sum(F.when(F.col("course_score_ceiling_observed") >= 60, 1).otherwise(0)).alias("enrollment_count_ceiling_ge_60"),
            F.sum(F.when(F.col("course_score_ceiling_observed") >= 85, 1).otherwise(0)).alias("enrollment_count_ceiling_ge_85"))
        .withColumn("share_ceiling_ge_60", F.try_divide("enrollment_count_ceiling_ge_60", "enrollment_count"))
        .withColumn("share_ceiling_ge_85", F.try_divide("enrollment_count_ceiling_ge_85", "enrollment_count")))
    unassigned = slices.filter(F.col("slice") == "UNASSIGNED").agg(
        F.first("enrollment_count").alias("n_unassigned")
    ).collect()[0]["n_unassigned"]
    if unassigned:
        raise ValueError(
            f"Registry/label release mismatch: {unassigned} eligible enrollments are UNASSIGNED. "
            "Point LO_CATALOG_MANIFEST_SOURCE to the V3.1 registry manifest before interpreting slice results."
        )
    outputs.append(("slice_ceiling_coverage", slices, ("slice",)))

for name, frame, keys in outputs:
    path = f"{OUT}/{name}/"
    write_parquet(frame, path)
    log_write(logger, name, path, log_dataframe(logger, name, frame, keys))
log_event(logger, "lo_catalog_denominator_audit_written", manifest_joined=bool(MANIFEST_SOURCE))
log_run_finished(logger, started)
flush_json_log(logger, spark)
