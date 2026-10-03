"""Immutable contract audit for LO catalog-normalized V3.1 labels.

This audit reads the V3.1 label artifact only.  It does not alter labels or
splits; its purpose is to record the score formula, exclusions (including the
new no-scored-signal rule), range invariants, and the 19-column proxy contract
used by feature-dictionary and leakage checks.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from pyspark.sql import SparkSession, Window, functions as F

_file_path = globals().get("__file__")
PROJECT_ROOT = Path(_file_path).resolve().parents[1] if _file_path else Path(
    globals().get("PROJECT_ROOT") or os.environ.get("PROJECT_ROOT", "")
)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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
EXPECTED_VERSION = "lo_final_score_catalog_normalized_v3_1"
if P["labels"].get("lo_version") != EXPECTED_VERSION:
    raise ValueError(f"LO V3.1 final-score audit requires lo_version={EXPECTED_VERSION}.")

LABEL_SOURCE = os.environ.get("LO_FINAL_SCORE_LABEL_SOURCE", path_from_config(P, "lo_labels")).rstrip("/")
OUT = os.environ.get(
    "LO_FINAL_SCORE_AUDIT_OUTPUT",
    f"{path_from_config(P, 'task_feature_base').rstrip('/')}/LO/hybrid/final_score_contract_audit_v3_1_scored_signal_excluded",
).rstrip("/")

spark = SparkSession.builder.appName("audit_lo_final_score_contract_v3_1").config(
    "spark.sql.session.timeZone", "UTC"
).getOrCreate()
logger = get_logger("audit_lo_final_score_contract_v3_1", path_from_config(P, "logs"))
started = start_run_timer()
log_run_context(logger, spark, {"label_source": LABEL_SOURCE, "output": OUT, "rule_version": EXPECTED_VERSION})

required = {
    "enrollment_id", "course_id", "proxy_exclusion_reason", "performance_score",
    "tempo_legacy_unclipped_score", "tempo_legacy_score_clipped",
    "LO_performance_label_3", "label_rule_version", "label_threshold_set",
    "video_weight", "assignment_weight", "exam_weight", "course_weight_total",
    "watched_videos", "video_counts", "watch_percent",
    "assignment_problem_catalog_count", "assignment_best_correct_sum", "assignment_ratio_catalog",
    "exam_problem_catalog_count", "exam_problem_attempted_count", "exam_best_correct_sum", "exam_ratio_catalog",
}
labels = spark.read.parquet(LABEL_SOURCE + "/")
missing = required.difference(labels.columns)
if missing:
    raise ValueError(f"LO label artifact is missing required final_score fields: {sorted(missing)}")

eligible = F.col("proxy_exclusion_reason").isNull()
signature = F.concat_ws(
    "+",
    F.when(F.col("video_weight") > 0, F.lit("VIDEO")),
    F.when(F.col("assignment_weight") > 0, F.lit("ASSIGNMENT")),
    F.when(F.col("exam_weight") > 0, F.lit("EXAM")),
)
scored = labels.withColumn("assessment_modality_signature", F.when(eligible, signature).otherwise(F.lit("INELIGIBLE")))

exclusions = (scored.groupBy(F.coalesce(F.col("proxy_exclusion_reason"), F.lit("ELIGIBLE")).alias("proxy_status"))
    .agg(F.count("enrollment_id").alias("enrollment_count"), F.countDistinct("course_id").alias("course_count"))
    .withColumn("enrollment_share", F.col("enrollment_count") / F.sum("enrollment_count").over(Window.partitionBy())))

label_version = (scored.groupBy("label_rule_version", "label_threshold_set")
    .agg(F.count("enrollment_id").alias("enrollment_count"), F.countDistinct("course_id").alias("course_count"),
         F.sum(F.when(eligible, 1).otherwise(0)).alias("eligible_enrollment_count")))

score_range = (scored.filter(eligible).groupBy("assessment_modality_signature").agg(
    F.count("enrollment_id").alias("eligible_enrollment_count"),
    F.expr("percentile_approx(performance_score, 0.5)").alias("final_score_p50"),
    F.expr("percentile_approx(performance_score, 0.9)").alias("final_score_p90"),
    F.expr("percentile_approx(performance_score, 0.99)").alias("final_score_p99"),
    F.min("performance_score").alias("final_score_min"), F.max("performance_score").alias("final_score_max"),
    F.sum(F.when(F.col("performance_score") > 100, 1).otherwise(0)).alias("n_final_score_gt_100"),
    F.sum(F.when(F.col("tempo_legacy_unclipped_score") > 100, 1).otherwise(0)).alias("n_legacy_score_gt_100"),
    F.sum(F.when(F.col("performance_score") < 0, 1).otherwise(0)).alias("n_final_score_lt_0"),
    F.sum(F.when(F.col("LO_performance_label_3") == "E", 1).otherwise(0)).alias("n_E"),
    F.sum(F.when(F.col("LO_performance_label_3") == "G", 1).otherwise(0)).alias("n_G"),
    F.sum(F.when(F.col("LO_performance_label_3") == "I/D", 1).otherwise(0)).alias("n_I_D"),
))

overflow = (scored.filter(eligible)
    .withColumn("legacy_overflow_group", F.when(F.col("tempo_legacy_unclipped_score") > 100, "legacy_score_gt_100").otherwise("legacy_score_lte_100"))
    .groupBy("legacy_overflow_group").agg(
        F.count("enrollment_id").alias("enrollment_count"),
        F.expr("percentile_approx(exam_problem_catalog_count, 0.5)").alias("exam_catalog_count_p50"),
        F.expr("percentile_approx(exam_problem_catalog_count, 0.9)").alias("exam_catalog_count_p90"),
        F.expr("percentile_approx(exam_problem_attempted_count, 0.5)").alias("exam_attempted_problem_count_p50"),
        F.expr("percentile_approx(exam_problem_attempted_count, 0.9)").alias("exam_attempted_problem_count_p90"),
        F.expr("percentile_approx(tempo_legacy_unclipped_score, 0.5)").alias("legacy_score_p50"),
        F.max("tempo_legacy_unclipped_score").alias("legacy_score_max"),
    ))

course_profile = (scored.groupBy("assessment_modality_signature", "video_weight", "assignment_weight", "exam_weight", "course_weight_total")
    .agg(F.countDistinct("course_id").alias("course_count"), F.count("enrollment_id").alias("enrollment_count"),
         F.sum(F.when(eligible, 1).otherwise(0)).alias("eligible_enrollment_count"))
    .withColumn("eligible_enrollment_share", F.try_divide("eligible_enrollment_count", "enrollment_count"))
    .withColumn("score_assembly_profile", F.concat(F.lit("V="), F.col("video_weight"), F.lit("|A="), F.col("assignment_weight"), F.lit("|E="), F.col("exam_weight"))))

proxy_rows = [
    ("performance_score", "persisted_final_score"), ("video_weight", "formula_weight"),
    ("assignment_weight", "formula_weight"), ("exam_weight", "formula_weight"),
    ("course_weight_total", "formula_validity_and_denominator"), ("watched_videos", "video_component_numerator"),
    ("video_counts", "video_component_denominator"), ("watch_percent", "video_component_derived"),
    ("video_catalog_coverage", "video_catalog_derived_proxy"), ("problem_catalog_coverage", "problem_catalog_derived_proxy"),
    ("problem_score_catalog_coverage", "problem_score_catalog_derived_proxy"),
    ("assignment_problem_catalog_count", "assignment_component_denominator"), ("assignment_best_correct_sum", "assignment_component_numerator"),
    ("assignment_ratio_catalog", "assignment_component_derived"), ("exam_problem_catalog_count", "exam_component_denominator"),
    ("exam_best_correct_sum", "exam_component_numerator"), ("exam_ratio_catalog", "exam_component_derived"),
    ("tempo_legacy_unclipped_score", "sensitivity_score_only"), ("tempo_legacy_score_clipped", "sensitivity_score_only"),
]
proxy = spark.createDataFrame(proxy_rows, ["canonical_column", "final_score_role"]).withColumn(
    "required_dictionary_action", F.lit("exclude_model_and_imputer_predictors")
).withColumn("suffix_policy", F.lit("apply_to_unsuffixed_and_all_phase_suffix_variants")).withColumn("is_label_proxy_required", F.lit(1))

semantics = spark.createDataFrame([(
    "LO", "LO_performance_label_3", "performance_score", "final_score",
    "activity_derived_weighted_score__exclude_no_scored_signal_courses",
    "not_an_independently_observed_final_grade",
    "video_weight*watch_percent + assignment_weight*assignment_ratio_catalog + exam_weight*exam_ratio_catalog",
    "E: 85<=final_score<=100; G: 60<=final_score<85; I/D: final_score<60",
    "exam_problem=problem in last hierarchical chapter when exam_weight>0", EXPECTED_VERSION,
)], ["task", "label_field", "persisted_score_field", "semantic_score_name", "score_semantics", "final_grade_claim", "formula", "class_thresholds", "exam_partition_rule", "contract_version"])

for name, frame, keys in (
    ("label_semantics_contract", semantics, ("task",)), ("label_version_summary", label_version, ("label_rule_version",)),
    ("exclusion_reason_summary", exclusions, ("proxy_status",)), ("proxy_feature_contract", proxy, ("canonical_column",)),
    ("score_range_by_profile", score_range, ("assessment_modality_signature",)),
    ("legacy_overflow_mechanism", overflow, ("legacy_overflow_group",)),
    ("course_scoring_profile", course_profile, ("assessment_modality_signature",)),
):
    path = f"{OUT}/{name}/"
    write_parquet(frame, path)
    rows = log_dataframe(logger, name, frame, keys)
    log_write(logger, name, path, rows)

log_event(logger, "lo_final_score_contract_v3_1_written", proxy_field_count=len(proxy_rows))
log_run_finished(logger, started)
flush_json_log(logger, spark)
