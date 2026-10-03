"""Build the LO V3 primary and sensitivity activity-derived labels.

This is intentionally *not* ``labels/lo_final``.  The available sources do
not contain observed completion, final grade, or dropout.  The output is an
explicitly named behavioural-performance label.  It is the accepted
operational LO target for this pipeline, while remaining distinct from a
directly observed completion/grade/dropout outcome.  No-timeline enrollments use the same
enrollment-anchored pseudo-offering policy as the hybrid feature scenario.

The PRIMARY score uses one best automatic score per catalog problem; an
unattempted catalog problem contributes zero.  This makes every component a
ratio in [0, 1] and makes the weighted score structurally bounded in [0, 100].
The TEMPO aggregation is emitted separately as a clipped sensitivity label.

* ``E`` (Excellent): 85 <= score <= 100
* ``G`` (Good): 60 <= score < 85
* ``I/D`` (Inactive/Dropout): score < 60

``I/D`` is a legacy operational performance band. It must not be interpreted
as an observed dropout outcome.

Exercises in a course's final chapter are the exam set when that course has a
positive exam weight.
"""
import sys
import os
from pathlib import Path

_file_path = globals().get("__file__")
if _file_path:
    _script_parent = Path(_file_path).resolve().parent
    PROJECT_ROOT = (_script_parent if ((_script_parent / "common").is_dir() or (_script_parent / "protocol_config.py").is_file())
                    else Path(_file_path).resolve().parents[1])
else:
    _configured_root = globals().get("PROJECT_ROOT") or os.environ.get("PROJECT_ROOT")
    PROJECT_ROOT = Path(_configured_root) if _configured_root else None
    if PROJECT_ROOT is None or not (PROJECT_ROOT / "common").is_dir():
        try:
            _notebook = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
            _workspace_path = Path("/Workspace") / _notebook.lstrip("/")
            PROJECT_ROOT = next(parent for parent in _workspace_path.parents if (parent / "common").is_dir())
        except Exception as error:
            # Support both the canonical repository layout and the flattened
            # Workspace layout previously used by the Databricks Python task.
            _roots = Path("/Workspace/Users")
            _candidates = []
            for _pattern in ("*/LO/Feature_extraction_LO", "*/feature_extract", "*/feature_extraction"):
                _candidates.extend(path for path in _roots.glob(_pattern) if (path / "common").is_dir())
            _candidates = list(dict.fromkeys(_candidates))
            if len(_candidates) == 1:
                PROJECT_ROOT = _candidates[0]
            else:
                raise RuntimeError(
                    "Cannot locate a unique LO project root containing common/. Set PROJECT_ROOT to "
                    "the absolute Workspace directory containing common/."
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
    # Legacy Databricks workspace layout keeps shared modules directly in LO/.
    from pipeline_logging import (
        flush_json_log, get_logger, log_dataframe, log_event, log_run_context,
        log_run_finished, log_write, start_run_timer, write_parquet,
    )
    from protocol_config import load_protocol_config, path_from_config


PROTOCOL = load_protocol_config()
RAW_BASE = PROTOCOL["raw_base"]
OUTPUT_BASE = PROTOCOL["output_base"]
ANALYSIS_BASE = path_from_config(PROTOCOL, "analysis_base")
# Older Workspace protocol files predate the LO V1 metadata fields.  Keep the
# label artifact runnable during that transition; the values are the locked V1
# protocol defaults and are also present in the current config.
EXPECTED_LABEL_RULE_VERSION = "lo_final_score_catalog_normalized_v3_1"
EXPECTED_LO_DECISION = "primary_catalog_normalized_activity_score_label__exclude_no_scored_signal_courses"
LABEL_RULE_VERSION = PROTOCOL["labels"].get("lo_version")
LO_DECISION = PROTOCOL["labels"].get("lo_decision")
if LABEL_RULE_VERSION != EXPECTED_LABEL_RULE_VERSION or LO_DECISION != EXPECTED_LO_DECISION:
    raise ValueError(
        "LO V3.1 label build requires experiment_protocol_config.yaml with "
        "lo_version=lo_final_score_catalog_normalized_v3_1 and "
        "lo_decision=primary_catalog_normalized_activity_score_label__exclude_no_scored_signal_courses."
    )
SENSITIVITY_LABEL_VERSION = PROTOCOL["labels"].get("lo_sensitivity_version")
SENSITIVITY_DECISION = PROTOCOL["labels"].get("lo_sensitivity_decision")
if (SENSITIVITY_LABEL_VERSION != "lo_tempo_legacy_clip_v3_1" or
        SENSITIVITY_DECISION != "sensitivity_tempo_legacy_score_clipped_at_100"):
    raise ValueError(
        "LO V3.1 requires lo_sensitivity_version=lo_tempo_legacy_clip_v3_1 and "
        "lo_sensitivity_decision=sensitivity_tempo_legacy_score_clipped_at_100."
    )
AUDIT_BASE = f"{OUTPUT_BASE}/labels/lo_labels_v3_1_scored_signal_excluded_audit/"

spark = SparkSession.builder.appName("build_lo_labels_v3_1_scored_signal_excluded").config(
    "spark.sql.session.timeZone", "UTC"
).getOrCreate()
logger = get_logger("build_lo_labels_v3_1_scored_signal_excluded", f"{OUTPUT_BASE}/logs")
log_run_context(
    logger,
    spark,
    {
        "rule_version": LABEL_RULE_VERSION,
        "decision": LO_DECISION,
        "semantic_scope": PROTOCOL["labels"]["lo_semantics"],
        "label_schedule_policy": "course-specific shifted schedule; enrollment-anchored pseudo-offering for no-timeline enrollments",
    },
)
started = start_run_timer()

enrollments = spark.read.parquet(f"{OUTPUT_BASE}/enrollments/")
videos = spark.read.parquet(f"{OUTPUT_BASE}/video_events_clean/")
problems = spark.read.parquet(f"{OUTPUT_BASE}/problem_events_clean/")
course_summary = spark.read.parquet(f"{OUTPUT_BASE}/course_summary/")
problem_catalog = spark.read.parquet(f"{OUTPUT_BASE}/course_problem_catalog/")

# Keep the source weights used by the LO reference.  ScoreStruct is not used:
# it does not expose the separate ``exam`` component required by this rule.
course_weights = (
    spark.read.option("header", True).option("quote", '"').option("escape", '"').option("multiLine", True)
    .csv(f"{RAW_BASE}/course_limit.csv")
    .select(
        "course_id",
        F.coalesce(F.col("video").cast("double"), F.lit(0.0)).alias("video_weight"),
        F.coalesce(F.col("assignment").cast("double"), F.lit(0.0)).alias("assignment_weight"),
        F.coalesce(F.col("exam").cast("double"), F.lit(0.0)).alias("exam_weight"),
    )
    .withColumn("course_weight_total", F.col("video_weight") + F.col("assignment_weight") + F.col("exam_weight"))
    .dropDuplicates(["course_id"])
)

# Final outcome observation time follows the same offering/proxy schedule as
# the hybrid feature scenario.  It is a schedule-derived proxy, not an
# observed completion timestamp.  The previous global-template/month-end
# fallback covered only a subset of no-timeline enrollments; the anchored
# table covers every no-timeline enrollment with a non-null enroll_time.
timeline_times = (
    spark.read.parquet(f"{ANALYSIS_BASE}/shifted_offering_assignments/")
    .select("enrollment_id", F.to_timestamp(F.date_add("offering_end_date", 1)).alias("label_availability_time"))
    .withColumn("label_availability_source", F.lit("course_specific_timeline"))
)
anchored_fallback_times = (
    spark.read.parquet(f"{ANALYSIS_BASE}/enrollment_anchored_pseudo_offering_assignments/")
    .select(
        "enrollment_id",
        F.to_timestamp(F.date_add("pseudo_end_date", 1)).alias("label_availability_time"),
    )
    .withColumn("label_availability_source", F.lit("enrollment_anchored_proxy"))
)
global_fallback_times = (
    spark.read.parquet(f"{ANALYSIS_BASE}/global_template_offering_assignments/")
    .select(
        "enrollment_id",
        F.to_timestamp(F.date_add("offering_end_date", 1)).alias("label_availability_time"),
    )
    .withColumn("label_availability_source", F.lit("global_template_fallback"))
    .join(anchored_fallback_times.select("enrollment_id"), "enrollment_id", "left_anti")
)
fallback_times = anchored_fallback_times.unionByName(global_fallback_times)
label_times = timeline_times.unionByName(fallback_times).dropDuplicates(["enrollment_id"])

# Source notebook: for courses with exam>0, all exercises under their last
# hierarchical chapter are exam exercises.  Cast only numeric chapter tokens;
# malformed/missing chapters cannot be classified as exam exercises.
chapter_catalog = (
    problem_catalog.select("course_id", "problem_id", "exercise_id", "chapter")
    .withColumn("chapter_parts", F.expr("transform(split(chapter, '\\\\.'), x -> try_cast(x as int))"))
    .filter("chapter IS NOT NULL AND NOT exists(chapter_parts, x -> x IS NULL)")
)
exam_eligible = chapter_catalog.join(
    course_weights.filter(F.col("exam_weight") > 0).select("course_id"), "course_id", "inner"
)
last_chapter = exam_eligible.groupBy("course_id").agg(F.max("chapter_parts").alias("last_chapter_parts"))
exam_problem_ids = (
    exam_eligible.join(last_chapter, "course_id", "inner")
    .filter(F.col("chapter_parts") == F.col("last_chapter_parts"))
    .select("course_id", "problem_id", F.lit(1).alias("is_exam_problem"))
    .dropDuplicates(["course_id", "problem_id"])
)

# The V3 denominators are catalog counts, not counts of submitted attempts.
# This makes an unattempted graded problem contribute zero and prevents a
# course with many exam questions from inflating final_score above 100.
catalog_problem_flags = (
    problem_catalog.select("course_id", "problem_id")
    .dropDuplicates(["course_id", "problem_id"])
    .join(exam_problem_ids, ["course_id", "problem_id"], "left")
    .withColumn("is_exam_problem", F.coalesce("is_exam_problem", F.lit(0)))
)
catalog_counts = (
    catalog_problem_flags.groupBy("course_id")
    .agg(
        F.sum(F.when(F.col("is_exam_problem") == 1, 1).otherwise(0)).alias("exam_problem_catalog_count"),
        F.sum(F.when(F.col("is_exam_problem") == 0, 1).otherwise(0)).alias("assignment_problem_catalog_count"),
    )
)

# Score fraction is the available automatic grading result at submit time.
# One submitted record is one observation, matching the reference aggregation.
problem_scores = (
    problems.select("enrollment_id", "user_id", "course_id", "problem_id", "event_time", "score", "full_score")
    .join(exam_problem_ids, ["course_id", "problem_id"], "left")
    .withColumn("is_exam_problem", F.coalesce("is_exam_problem", F.lit(0)))
    .withColumn("correct_ratio", F.when(F.col("full_score") == 0, F.lit(1.0)).otherwise(F.least(F.lit(1.0), F.greatest(F.lit(0.0), F.col("score").cast("double") / F.col("full_score").cast("double")))))
)
# Retain the legacy attempt-level summaries for the sensitivity label, but
# calculate PRIMARY from a single best automatic grade per catalog problem.
best_problem_scores = (
    problem_scores.groupBy("enrollment_id", "user_id", "course_id", "problem_id", "is_exam_problem")
    .agg(F.max("correct_ratio").alias("best_correct_ratio"), F.max("event_time").alias("problem_last_event_time"))
)
catalog_normalized_summary = (
    best_problem_scores.groupBy("enrollment_id", "user_id", "course_id")
    .agg(
        F.sum(F.when(F.col("is_exam_problem") == 1, F.col("best_correct_ratio")).otherwise(0.0)).alias("exam_best_correct_sum"),
        F.sum(F.when(F.col("is_exam_problem") == 0, F.col("best_correct_ratio")).otherwise(0.0)).alias("assignment_best_correct_sum"),
        F.sum(F.when(F.col("is_exam_problem") == 1, 1).otherwise(0)).alias("exam_problem_attempted_count"),
        F.sum(F.when(F.col("is_exam_problem") == 0, 1).otherwise(0)).alias("assignment_problem_attempted_count"),
    )
)
exam_summary = (
    problem_scores.filter(F.col("is_exam_problem") == 1)
    .groupBy("enrollment_id", "user_id", "course_id")
    .agg(
        F.count("problem_id").alias("exam_attempt_count"),
        F.sum("correct_ratio").alias("total_correct_ratio_exam"),
        F.avg("correct_ratio").alias("average_correct_ratio_exam"),
        F.max("event_time").alias("exam_last_event_time"),
    )
)
assignment_summary = (
    problem_scores.filter(F.col("is_exam_problem") == 0)
    .groupBy("enrollment_id", "user_id", "course_id")
    .agg(
        F.count("problem_id").alias("assignment_attempt_count"),
        F.sum("correct_ratio").alias("total_correct_ratio_assignment"),
        F.avg("correct_ratio").alias("average_correct_ratio_assignment"),
        F.max("event_time").alias("assignment_last_event_time"),
    )
)
video_summary = videos.groupBy("enrollment_id", "user_id", "course_id").agg(
    F.countDistinct("resource_id").alias("watched_videos"), F.max("event_time").alias("video_last_event_time")
)

# V3.1 cohort decision: do not infer I/D from an absent graded-data source.
# A course is excluded only when it has a positively weighted assignment and/or
# exam component and no enrollment has an observed attempt in any such
# component.  Attempts in a zero-weight component intentionally do not rescue
# the course (e.g., assignment attempts in an exam-only course).
course_scored_signal = (
    course_weights.select("course_id", "assignment_weight", "exam_weight")
    .join(
        assignment_summary.groupBy("course_id").agg(
            F.max(F.when(F.col("assignment_attempt_count") > 0, 1).otherwise(0)).alias("has_assignment_attempt"),
        ),
        "course_id", "left",
    )
    .join(
        exam_summary.groupBy("course_id").agg(
            F.max(F.when(F.col("exam_attempt_count") > 0, 1).otherwise(0)).alias("has_exam_attempt"),
        ),
        "course_id", "left",
    )
    .fillna(0, subset=["has_assignment_attempt", "has_exam_attempt"])
    .withColumn(
        "no_scored_signal_in_course",
        (((F.col("assignment_weight") > 0) | (F.col("exam_weight") > 0))
         & ~(((F.col("assignment_weight") > 0) & (F.col("has_assignment_attempt") == 1))
             | ((F.col("exam_weight") > 0) & (F.col("has_exam_attempt") == 1)))).cast("int"),
    )
    .select("course_id", "no_scored_signal_in_course")
)

base = (
    enrollments.select("enrollment_id", "user_id", "course_id")
    .join(course_weights, "course_id", "left")
    .join(course_summary.select("course_id", "video_counts"), "course_id", "left")
    .join(catalog_counts, "course_id", "left")
    .join(video_summary, ["enrollment_id", "user_id", "course_id"], "left")
    .join(exam_summary, ["enrollment_id", "user_id", "course_id"], "left")
    .join(assignment_summary, ["enrollment_id", "user_id", "course_id"], "left")
    .join(catalog_normalized_summary, ["enrollment_id", "user_id", "course_id"], "left")
    .join(label_times, "enrollment_id", "left")
    .join(course_scored_signal, "course_id", "left")
    .withColumn(
        "proxy_exclusion_reason",
        F.when(F.col("label_availability_time").isNull(), F.lit("missing_schedule_assignment"))
        .when(F.col("course_weight_total").isNull(), F.lit("missing_course_limit_weights"))
        .when(F.col("course_weight_total") <= 0, F.lit("nonpositive_course_weight_total"))
        .when(F.col("course_weight_total") != 100, F.lit("course_weight_total_not_100"))
        .when((F.col("video_weight") > 0) & (F.coalesce(F.col("video_counts"), F.lit(0)) <= 0), F.lit("missing_video_catalog"))
        .when((F.col("assignment_weight") > 0) & (F.coalesce(F.col("assignment_problem_catalog_count"), F.lit(0)) <= 0), F.lit("missing_assignment_problem_catalog"))
        .when((F.col("exam_weight") > 0) & (F.coalesce(F.col("exam_problem_catalog_count"), F.lit(0)) <= 0), F.lit("missing_exam_problem_catalog"))
        .when(F.coalesce(F.col("no_scored_signal_in_course"), F.lit(0)) == 1, F.lit("no_scored_signal_in_course")),
    )
    .fillna(0, subset=[
        "video_weight", "assignment_weight", "exam_weight", "course_weight_total", "video_counts", "watched_videos",
        "exam_attempt_count", "total_correct_ratio_exam", "average_correct_ratio_exam",
        "assignment_attempt_count", "total_correct_ratio_assignment", "average_correct_ratio_assignment",
        "exam_problem_catalog_count", "assignment_problem_catalog_count",
        "exam_best_correct_sum", "assignment_best_correct_sum",
        "exam_problem_attempted_count", "assignment_problem_attempted_count",
    ])
    .withColumn("watch_percent", F.least(F.lit(1.0), F.coalesce(F.try_divide("watched_videos", "video_counts"), F.lit(0.0))))
    # Retained only for the separately emitted TEMPO legacy-clip sensitivity.
    .withColumn(
        "assignment_ratio_used",
        F.when(
            (F.col("assignment_weight") > 0) & (F.col("assignment_attempt_count") == 0) & (F.col("exam_attempt_count") > 0),
            F.col("average_correct_ratio_exam"),
        ).otherwise(F.col("average_correct_ratio_assignment")),
    )
    .withColumn(
        "tempo_legacy_unclipped_score",
        F.when(
            F.col("proxy_exclusion_reason").isNull(),
            F.col("video_weight") * F.col("watch_percent")
            + F.col("assignment_weight") * F.col("assignment_ratio_used")
            + F.col("exam_weight") * F.col("total_correct_ratio_exam"),
        ),
    )
    .withColumn("assignment_ratio_catalog", F.least(F.lit(1.0), F.greatest(F.lit(0.0), F.coalesce(F.try_divide("assignment_best_correct_sum", "assignment_problem_catalog_count"), F.lit(0.0)))))
    .withColumn("exam_ratio_catalog", F.least(F.lit(1.0), F.greatest(F.lit(0.0), F.coalesce(F.try_divide("exam_best_correct_sum", "exam_problem_catalog_count"), F.lit(0.0)))))
    .withColumn(
        "performance_score",
        F.when(
            F.col("proxy_exclusion_reason").isNull(),
            F.col("video_weight") * F.col("watch_percent")
            + F.col("assignment_weight") * F.col("assignment_ratio_catalog")
            + F.col("exam_weight") * F.col("exam_ratio_catalog"),
        ),
    )
    .withColumn("tempo_legacy_score_clipped", F.least(F.lit(100.0), F.col("tempo_legacy_unclipped_score")))
    .withColumn("outcome_event_time", F.greatest("video_last_event_time", "assignment_last_event_time", "exam_last_event_time"))
    # PRIMARY is monotone because performance_score is structurally in [0,100].
    .withColumn("LO_performance_label_3", F.when(F.col("proxy_exclusion_reason").isNotNull(), F.lit(None).cast("string")).when((F.col("performance_score") >= 85) & (F.col("performance_score") <= 100), "E").when((F.col("performance_score") >= 60) & (F.col("performance_score") < 85), "G").otherwise("I/D"))
    .withColumn("LO_performance_label_5", F.lit(None).cast("string"))
    .withColumn("label_rule_version", F.lit(LABEL_RULE_VERSION))
    .withColumn("label_threshold_set", F.lit("CATALOG_NORMALIZED_PRIMARY_V3_1__EXCLUDE_NO_SCORED_SIGNAL"))
    .withColumn("decision", F.lit(LO_DECISION))
    .withColumn("proxy_reason", F.lit(PROTOCOL["labels"]["lo_semantics"]))
)

artifact = base.select(
    "enrollment_id", "user_id", "course_id", "video_weight", "assignment_weight", "exam_weight", "course_weight_total",
    "watched_videos", "video_counts", "watch_percent", "exam_attempt_count", "total_correct_ratio_exam",
    "average_correct_ratio_exam", "assignment_attempt_count", "total_correct_ratio_assignment",
    "average_correct_ratio_assignment", "assignment_ratio_used",
    "exam_problem_catalog_count", "assignment_problem_catalog_count",
    "exam_best_correct_sum", "assignment_best_correct_sum",
    "exam_problem_attempted_count", "assignment_problem_attempted_count",
    "assignment_ratio_catalog", "exam_ratio_catalog",
    "tempo_legacy_unclipped_score", "tempo_legacy_score_clipped", "performance_score",
    "LO_performance_label_3", "LO_performance_label_5", "outcome_event_time",
    "label_availability_time", "label_availability_source",
    F.when(F.col("label_availability_time").isNotNull(), F.lit("assigned_schedule"))
        .otherwise(F.lit("unassigned_schedule")).alias("label_schedule_assignment_status"),
    "label_rule_version", "label_threshold_set", "decision", "proxy_reason", "proxy_exclusion_reason",
)
output_path = path_from_config(PROTOCOL, "lo_labels") + "/"
write_parquet(artifact, output_path)
rows = log_dataframe(logger, "lo_performance_proxy", artifact, ("enrollment_id",))
sensitivity_artifact = (
    artifact
    .withColumn("performance_score", F.col("tempo_legacy_score_clipped"))
    .withColumn(
        "LO_performance_label_3",
        F.when(F.col("proxy_exclusion_reason").isNotNull(), F.lit(None).cast("string"))
        .when(F.col("tempo_legacy_score_clipped") >= 85, F.lit("E"))
        .when(F.col("tempo_legacy_score_clipped") >= 60, F.lit("G"))
        .otherwise(F.lit("I/D")),
    )
    .withColumn("label_rule_version", F.lit(SENSITIVITY_LABEL_VERSION))
    .withColumn("label_threshold_set", F.lit("TEMPO_LEGACY_CLIP_V3_1__EXCLUDE_NO_SCORED_SIGNAL"))
    .withColumn("decision", F.lit(SENSITIVITY_DECISION))
    .withColumn(
        "proxy_reason",
        F.lit("TEMPO legacy attempt-level score clipped at 100; sensitivity only, not PRIMARY."),
    )
)
sensitivity_output_path = path_from_config(PROTOCOL, "lo_labels_sensitivity") + "/"
write_parquet(sensitivity_artifact, sensitivity_output_path)
sensitivity_rows = log_dataframe(logger, "lo_tempo_legacy_clip_sensitivity", sensitivity_artifact, ("enrollment_id",))
label_invariants = artifact.agg(
    F.sum(F.when((F.col("proxy_exclusion_reason").isNull()) & ((F.col("performance_score") < 0) | (F.col("performance_score") > 100)), 1).otherwise(0)).alias("primary_score_out_of_range"),
    F.sum(F.when((F.col("LO_performance_label_3") == "E") & ~((F.col("performance_score") >= 85) & (F.col("performance_score") <= 100)), 1).otherwise(0)).alias("primary_e_band_violation"),
    F.sum(F.when((F.col("LO_performance_label_3") == "G") & ~((F.col("performance_score") >= 60) & (F.col("performance_score") < 85)), 1).otherwise(0)).alias("primary_g_band_violation"),
).crossJoin(sensitivity_artifact.agg(
    F.sum(F.when((F.col("proxy_exclusion_reason").isNull()) & ((F.col("performance_score") < 0) | (F.col("performance_score") > 100)), 1).otherwise(0)).alias("sensitivity_score_out_of_range")
))
if label_invariants.filter(
    (F.col("primary_score_out_of_range") != 0)
    | (F.col("primary_e_band_violation") != 0)
    | (F.col("primary_g_band_violation") != 0)
    | (F.col("sensitivity_score_out_of_range") != 0)
).limit(1).count():
    raise RuntimeError("LO V3 label invariants failed: normalized/clip score or threshold-band violation.")
write_parquet(label_invariants, f"{AUDIT_BASE}label_invariants/")
label_distribution_3 = (
    artifact.groupBy(
        F.coalesce(F.col("LO_performance_label_3"), F.lit("NULL")).alias("label"),
        F.coalesce(F.col("label_availability_source"), F.lit("unassigned")).alias("schedule_source"),
    )
    .agg(
        F.count("enrollment_id").alias("enrollment_count"),
        F.countDistinct("user_id").alias("user_count"),
        F.countDistinct("course_id").alias("course_count"),
        F.avg("performance_score").alias("performance_score_mean"),
    )
    .withColumn("label_rule_version", F.lit(LABEL_RULE_VERSION))
    .orderBy("schedule_source", "label")
)
label_distribution_5 = (
    artifact.groupBy(
        F.coalesce(F.col("LO_performance_label_5"), F.lit("NULL")).alias("label"),
        F.coalesce(F.col("label_availability_source"), F.lit("unassigned")).alias("schedule_source"),
    )
    .agg(
        F.count("enrollment_id").alias("enrollment_count"),
        F.countDistinct("user_id").alias("user_count"),
        F.countDistinct("course_id").alias("course_count"),
        F.avg("performance_score").alias("performance_score_mean"),
    )
    .withColumn("label_rule_version", F.lit(LABEL_RULE_VERSION))
    .orderBy("schedule_source", "label")
)
label_schedule_summary = (
    artifact.groupBy("label_availability_source", "label_schedule_assignment_status", "proxy_exclusion_reason")
    .agg(F.count("enrollment_id").alias("enrollment_count"))
)
write_parquet(label_distribution_3, f"{AUDIT_BASE}label_distribution_3/")
write_parquet(label_distribution_5, f"{AUDIT_BASE}label_distribution_5/")
label_3_rows = log_dataframe(logger, "lo_performance_label_distribution_3", label_distribution_3, ("schedule_source", "label"))
label_5_rows = log_dataframe(logger, "lo_performance_label_distribution_5", label_distribution_5, ("schedule_source", "label"))
log_dataframe(
    logger,
    "lo_proxy_schedule_assignment_summary",
    label_schedule_summary,
    ("label_availability_source", "label_schedule_assignment_status", "proxy_exclusion_reason"),
)
log_write(logger, "lo_labels_v3_1_scored_signal_excluded", output_path, rows)
log_write(logger, "lo_labels_v3_1_tempo_legacy_clip", sensitivity_output_path, sensitivity_rows)
log_write(logger, "lo_v3_1_label_invariants", f"{AUDIT_BASE}label_invariants/", log_dataframe(logger, "lo_v3_1_label_invariants", label_invariants, ()))
log_write(logger, "lo_performance_label_distribution_3", f"{AUDIT_BASE}label_distribution_3/", label_3_rows)
log_write(logger, "lo_performance_label_distribution_5", f"{AUDIT_BASE}label_distribution_5/", label_5_rows)
log_event(
    logger,
    "lo_labels_v3_1_written",
    primary_rows=rows,
    sensitivity_rows=sensitivity_rows,
    decision=LO_DECISION,
    primary_rule="catalog_normalized_best_per_problem",
    sensitivity_rule="tempo_legacy_clip",
)
log_run_finished(logger, started)
flush_json_log(logger, spark)
