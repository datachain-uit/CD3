"""Audit the proposed video/problem-only ACELO rule without rebuilding labels.

Reads the already materialized V3 component artifact and canonical V3 vector
labels.  It writes only audit outputs; no label, feature, or view is changed.
"""
import os
import sys
from pathlib import Path

PROJECT_ROOT = os.environ.get("PROJECT_ROOT") or str(Path(__file__).resolve().parents[1])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from pyspark.sql import SparkSession, Window, functions as F

from common.pipeline_logging import (
    flush_json_log,
    get_logger,
    log_dataframe,
    log_event,
    log_run_context,
    log_run_finished,
    log_write,
    start_run_timer,
    write_parquet,
)
from common.protocol_config import load_protocol_config, path_from_config


PROTOCOL = load_protocol_config()
BASE = PROTOCOL["output_base"]
COMPONENT_SOURCE = path_from_config(PROTOCOL, "cq_label_components") + "/"
CANONICAL_SOURCE = path_from_config(PROTOCOL, "cq_labels") + "/"
OUTPUT_BASE = f"{BASE}/labels/cq_labels_v1_component_audit/"
LABEL_VERSION = "cq_vector_proximity_v1"

spark = (
    SparkSession.builder.appName("audit_cq_acelo_video_problem_only_v3")
    .config("spark.sql.session.timeZone", "UTC")
    .getOrCreate()
)
logger = get_logger("audit_cq_acelo_video_problem_only_v3", f"{BASE}/logs")
started = start_run_timer()
log_run_context(
    logger,
    spark,
    {
        "label_version": LABEL_VERSION,
        "component_source": COMPONENT_SOURCE,
        "canonical_source": CANONICAL_SOURCE,
        "output": OUTPUT_BASE,
        "purpose": "counterfactual audit only; no labels are rebuilt",
        "proposed_acelo": "(video_weight*video_watch_ratio + problem_weight*problem_score_ratio) / (video_weight + problem_weight)",
    },
)

components = spark.read.parquet(COMPONENT_SOURCE)
canonical = spark.read.parquet(CANONICAL_SOURCE).select(
    "enrollment_id", "CQ_label_final", "cq_exclusion_reason"
)
required = {
    "enrollment_id", "course_id", "assessment_weight_source", "course_modality",
    "effective_video_weight", "effective_problem_weight", "effective_comment_weight",
    "video_watch_ratio", "problem_score_ratio", "ACELO_personal",
    "COELO_personal", "AFELO_personal",
}
missing = sorted(required.difference(components.columns))
if missing:
    raise ValueError("Missing V3 component columns: " + ", ".join(missing))

video_problem_weight = (
    F.coalesce(F.col("effective_video_weight"), F.lit(0.0))
    + F.coalesce(F.col("effective_problem_weight"), F.lit(0.0))
)
proposed_acelo = F.when(
    video_problem_weight > 0,
    F.try_divide(
        F.coalesce(F.col("effective_video_weight"), F.lit(0.0))
        * F.coalesce(F.col("video_watch_ratio"), F.lit(0.0))
        + F.coalesce(F.col("effective_problem_weight"), F.lit(0.0))
        * F.coalesce(F.col("problem_score_ratio"), F.lit(0.0)),
        video_problem_weight,
    ),
)

audited = (
    components.join(canonical, "enrollment_id", "left")
    .withColumn("video_problem_effective_weight", video_problem_weight)
    .withColumn("ACELO_video_problem_only", proposed_acelo)
    .withColumn(
        "ACELO_comment_contribution",
        F.col("ACELO_personal") - F.col("ACELO_video_problem_only"),
    )
    .withColumn(
        "counterfactual_distance",
        F.when(
            F.col("COELO_personal").isNotNull()
            & F.col("AFELO_personal").isNotNull()
            & F.col("ACELO_video_problem_only").isNotNull(),
            F.sqrt(
                F.pow(F.lit(1.0) - F.col("COELO_personal"), 2)
                + F.pow(F.lit(1.0) - F.col("AFELO_personal"), 2)
                + F.pow(F.lit(1.0) - F.col("ACELO_video_problem_only"), 2)
            ),
        ),
    )
    .withColumn(
        "counterfactual_proximity",
        F.when(
            F.col("counterfactual_distance").isNotNull(),
            F.lit(1.0) - F.col("counterfactual_distance") / F.sqrt(F.lit(3.0)),
        ),
    )
    .withColumn(
        "counterfactual_label",
        F.when(F.col("counterfactual_proximity").isNull(), F.lit(None).cast("string"))
        .when(F.col("counterfactual_proximity") < F.lit(0.10), F.lit("warning"))
        .when(F.col("counterfactual_proximity") < F.lit(0.30), F.lit("average"))
        .otherwise(F.lit("good")),
    )
)

weight_summary = audited.groupBy("assessment_weight_source", "course_modality").agg(
    F.count("enrollment_id").alias("enrollment_count"),
    F.countDistinct("course_id").alias("course_count"),
    F.avg("effective_video_weight").alias("video_weight_mean"),
    F.avg("effective_problem_weight").alias("problem_weight_mean"),
    F.avg("effective_comment_weight").alias("comment_weight_mean"),
    F.avg("video_problem_effective_weight").alias("video_problem_weight_mean"),
    F.sum(F.when(F.col("effective_comment_weight") > 0, 1).otherwise(0)).alias("comment_weighted_enrollment_count"),
).withColumn(
    "comment_weighted_enrollment_ratio",
    F.try_divide(F.col("comment_weighted_enrollment_count"), F.col("enrollment_count")),
)

impact_summary = audited.agg(
    F.count("enrollment_id").alias("component_enrollment_count"),
    F.sum(F.when(F.col("effective_comment_weight") > 0, 1).otherwise(0)).alias("comment_weighted_enrollment_count"),
    F.avg("ACELO_personal").alias("current_acelo_mean"),
    F.avg("ACELO_video_problem_only").alias("proposed_acelo_mean"),
    F.avg("ACELO_comment_contribution").alias("mean_acelo_change_current_minus_proposed"),
    F.sum(F.when(F.abs(F.col("ACELO_comment_contribution")) > F.lit(0.0000001), 1).otherwise(0)).alias("acelo_changed_enrollment_count"),
    F.sum(F.when(F.col("CQ_label_final").isNotNull(), 1).otherwise(0)).alias("current_canonical_labeled_count"),
    F.sum(F.when(F.col("CQ_label_final").isNotNull() & F.col("counterfactual_label").isNotNull(), 1).otherwise(0)).alias("comparable_labeled_count"),
    F.sum(F.when((F.col("CQ_label_final") != F.col("counterfactual_label")) & F.col("CQ_label_final").isNotNull() & F.col("counterfactual_label").isNotNull(), 1).otherwise(0)).alias("label_changed_count"),
)

label_transition = (
    audited.filter(F.col("CQ_label_final").isNotNull() & F.col("counterfactual_label").isNotNull())
    .groupBy("CQ_label_final", "counterfactual_label")
    .agg(F.count("enrollment_id").alias("enrollment_count"))
    .withColumn("from_label", F.col("CQ_label_final"))
    .withColumn(
        "from_label_ratio",
        F.try_divide(F.col("enrollment_count"), F.sum("enrollment_count").over(Window.partitionBy("CQ_label_final"))),
    )
    .orderBy("from_label", "counterfactual_label")
)

impact_by_current_label = (
    audited.filter(F.col("CQ_label_final").isNotNull())
    .groupBy("CQ_label_final")
    .agg(
        F.count("enrollment_id").alias("enrollment_count"),
        F.avg("ACELO_personal").alias("current_acelo_mean"),
        F.avg("ACELO_video_problem_only").alias("proposed_acelo_mean"),
        F.avg("ACELO_comment_contribution").alias("mean_acelo_change_current_minus_proposed"),
        F.sum(F.when(F.abs(F.col("ACELO_comment_contribution")) > F.lit(0.0000001), 1).otherwise(0)).alias("acelo_changed_enrollment_count"),
        F.sum(F.when(F.col("CQ_label_final") != F.col("counterfactual_label"), 1).otherwise(0)).alias("label_changed_count"),
    )
    .withColumn("label", F.col("CQ_label_final"))
)

for name, dataframe, keys in (
    ("weight_summary", weight_summary, ("assessment_weight_source", "course_modality")),
    ("impact_summary", impact_summary, ()),
    ("impact_by_current_label", impact_by_current_label, ("label",)),
    ("label_transition", label_transition, ("from_label", "counterfactual_label")),
):
    output = f"{OUTPUT_BASE}{name}/"
    write_parquet(dataframe, output)
    rows = log_dataframe(logger, name, dataframe, keys)
    log_write(logger, name, output, rows)

log_event(logger, "acelo_video_problem_only_audit_complete")
log_run_finished(logger, started)
flush_json_log(logger, spark)
