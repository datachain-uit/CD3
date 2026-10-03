"""Clean course score-component proportions into reusable course metadata."""
from pyspark.sql import SparkSession, functions as F

from common.pipeline_logging import (
    flush_json_log, get_logger, log_dataframe, log_run_context, log_run_finished,
    log_write, start_run_timer, write_parquet,
)
from common.protocol_config import load_protocol_config

PROTOCOL = load_protocol_config()
RAW_BASE = PROTOCOL["raw_base"]
OUTPUT_BASE = PROTOCOL["output_base"]
SCORE_STRUCTURE_PATH = f"{RAW_BASE}/course_ScoreStruct.csv"
VALID_ACTIVITIES = ("video", "assignment", "discussion", "article", "reading")
ASSESSMENT_MAPPING_POLICY = {
    "video": "video",
    "assignment": "problem_assignment",
    "discussion": "comment",
    "article": "excluded_temporarily",
    "reading": "problem_assignment",
}

spark = SparkSession.builder.appName("process_course_score_structure").config(
    "spark.sql.session.timeZone", "UTC"
).getOrCreate()
logger = get_logger("process_course_score_structure", f"{OUTPUT_BASE}/logs")
log_run_context(logger, spark, {
    "score_structure_path": SCORE_STRUCTURE_PATH,
    "output_base": OUTPUT_BASE,
    "assessment_mapping_policy": ASSESSMENT_MAPPING_POLICY,
})
started = start_run_timer()

active_courses = spark.read.parquet(f"{OUTPUT_BASE}/course_summary/").select("course_id")
raw = spark.read.option("header", True).option("mode", "PERMISSIVE").csv(SCORE_STRUCTURE_PATH)
raw_normalized = raw.select(
    F.trim(F.col("id")).alias("course_id"),
    F.lower(F.trim(F.col("activities"))).alias("activity_type"),
    F.col("point").alias("point_raw"),
    F.col("proportion").cast("double").alias("score_proportion"),
)
log_dataframe(logger, "course_score_structure_raw", raw_normalized, ("course_id", "activity_type"))

invalid = (
    raw_normalized.filter(
        F.col("course_id").isNull()
        | F.col("activity_type").isNull()
        | ~F.col("activity_type").isin(*VALID_ACTIVITIES)
        | F.col("score_proportion").isNull()
        | (F.col("score_proportion") < 0)
        | (F.col("score_proportion") > 100)
    )
    .withColumn(
        "exclusion_reason",
        F.when(F.col("course_id").isNull(), "missing_course_id")
        .when(F.col("activity_type").isNull() | ~F.col("activity_type").isin(*VALID_ACTIVITIES), "invalid_activity_type")
        .otherwise("invalid_score_proportion"),
    )
)
valid = raw_normalized.filter(
    F.col("course_id").isNotNull()
    & F.col("activity_type").isin(*VALID_ACTIVITIES)
    & F.col("score_proportion").isNotNull()
    & (F.col("score_proportion") >= 0)
    & (F.col("score_proportion") <= 100)
)
inactive = valid.join(active_courses, "course_id", "left_anti").withColumn(
    "exclusion_reason", F.lit("course_not_in_active_course_summary")
)
active = valid.join(active_courses, "course_id", "inner")
deduped = active.dropDuplicates(["course_id", "activity_type", "score_proportion", "point_raw"])
duplicates = active.exceptAll(deduped).withColumn("exclusion_reason", F.lit("duplicate_exact_score_component"))

clean = deduped
pivoted = clean.groupBy("course_id").pivot("activity_type", list(VALID_ACTIVITIES)).agg(F.sum("score_proportion"))
summary = (
    pivoted.join(clean.groupBy("course_id").agg(
        F.countDistinct("activity_type").alias("score_component_count"),
        F.sum("score_proportion").alias("score_structure_total_weight"),
    ), "course_id", "inner")
    .fillna(0.0, list(VALID_ACTIVITIES))
    .withColumnRenamed("video", "score_weight_video")
    # Keep the original components for audit, then expose mapped weights used
    # by the label builders.  Reading contributes to assignment/problem;
    # discussion contributes to comment; article is intentionally excluded
    # until a reliable article interaction source is available.
    .withColumnRenamed("assignment", "score_weight_assignment_raw")
    .withColumnRenamed("discussion", "score_weight_discussion_raw")
    .withColumnRenamed("article", "score_weight_article_raw")
    .withColumnRenamed("reading", "score_weight_reading_raw")
    .withColumn(
        "score_weight_assignment",
        F.col("score_weight_assignment_raw") + F.col("score_weight_reading_raw"),
    )
    .withColumn("score_weight_comment", F.col("score_weight_discussion_raw"))
    .withColumn("score_weight_article_excluded", F.col("score_weight_article_raw"))
    .withColumn(
        "score_weight_observable",
        F.col("score_weight_video")
        + F.col("score_weight_assignment")
        + F.col("score_weight_comment"),
    )
    # All non-article components now have an explicit observable mapping.
    # Article weight is retained for audit but deliberately removed from the
    # denominator used by CQ/ACELO.
    .withColumn("score_weight_unobserved", F.lit(0.0))
    .withColumn(
        "score_structure_mapped_total_weight",
        F.col("score_weight_observable"),
    )
    .withColumn(
        "assessment_mapping_policy",
        F.lit("discussion_to_comment__reading_to_assignment__article_excluded"),
    )
    .withColumn("has_score_structure", F.lit(1))
)
exclusions = invalid.unionByName(inactive).unionByName(duplicates)

clean_path = f"{OUTPUT_BASE}/course_score_structure_clean/"
summary_path = f"{OUTPUT_BASE}/course_score_structure_summary/"
exclusion_path = f"{OUTPUT_BASE}/course_score_structure_exclusion_log/"
write_parquet(clean, clean_path)
write_parquet(summary, summary_path)
write_parquet(exclusions, exclusion_path)
log_write(logger, "course_score_structure_clean", clean_path, log_dataframe(logger, "course_score_structure_clean_output", clean, ("course_id", "activity_type")))
log_write(logger, "course_score_structure_summary", summary_path, log_dataframe(logger, "course_score_structure_summary_output", summary, ("course_id",)))
log_write(logger, "course_score_structure_exclusion_log", exclusion_path, log_dataframe(logger, "course_score_structure_exclusion_log_output", exclusions, ("course_id", "activity_type")))
log_run_finished(logger, started)
flush_json_log(logger, spark)
