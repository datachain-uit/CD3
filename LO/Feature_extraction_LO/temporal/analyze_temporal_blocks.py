"""Profile course-time coverage and propose A-G rolling-window blocks.

This stage builds the locked grouped A–G temporal split.  The configured
label availability time is ``offering_end_date + 1 day``, so ordering by the
offering end is equivalent while preserving date-level grouping.
"""

import pandas as pd

from pyspark.sql import SparkSession, Window, functions as F
from pyspark.sql.types import DateType, IntegerType, StringType, StructField

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
RAW_BASE = PROTOCOL["raw_base"]
OUTPUT_BASE = PROTOCOL["output_base"]
COURSE_LIMIT_PATH = f"{RAW_BASE}/course_limit.csv"
COURSE_CATALOG_PATH = f"{RAW_BASE}/3/course.json"

# A=70%; B-G are 5% each. The allocation is by enrollment count and never
# splits a course across blocks. Actual percentages are reported, not forced.
_running_block_ratio = 0.0
BLOCK_BOUNDARIES = []
for _block, _ratio in PROTOCOL["temporal_blocks"].items():
    _running_block_ratio += float(_ratio)
    BLOCK_BOUNDARIES.append((_block, _running_block_ratio))
BLOCK_BOUNDARIES = tuple(BLOCK_BOUNDARIES)
BLOCK_TARGET_RATIOS = {block: float(ratio) for block, ratio in PROTOCOL["temporal_blocks"].items()}
MONTH_TEMPLATE_MIN_RUNS = 10
# Used only when a course has no reliable start-month template.  This is the
# median *single offering* duration from observed schedule runs, not the span
# between the first and last enrollment observed in the collection period.
PSEUDO_OFFERING_FALLBACK_DURATION_DAYS = 131
QUANTILE_SPECS = (
    (0, 0.00, "p00"), (1, 0.01, "p01"), (5, 0.05, "p05"),
    (10, 0.10, "p10"), (25, 0.25, "p25"), (50, 0.50, "p50"),
    (75, 0.75, "p75"), (90, 0.90, "p90"), (95, 0.95, "p95"),
    (99, 0.99, "p99"), (100, 1.00, "p100"),
)
QUANTILE_ARRAY_SQL = "array(" + ", ".join(str(item[1]) for item in QUANTILE_SPECS) + ")"


def temporal_block_expression(fraction_column):
    """Build the A–G allocation expression from the locked config ratios."""
    expression = F.lit(BLOCK_BOUNDARIES[-1][0])
    for block, boundary in reversed(BLOCK_BOUNDARIES[:-1]):
        expression = F.when(F.col(fraction_column) <= F.lit(boundary), F.lit(block)).otherwise(expression)
    return expression


def target_ratio_expression(block_column="temporal_block"):
    entries = []
    for block, ratio in BLOCK_TARGET_RATIOS.items():
        entries.extend((F.lit(block), F.lit(ratio)))
    return F.element_at(F.create_map(*entries), F.col(block_column))


spark = (
    SparkSession.builder.appName("analyze_temporal_blocks")
    .config("spark.sql.session.timeZone", "UTC")
    .getOrCreate()
)
logger = get_logger("analyze_temporal_blocks", f"{OUTPUT_BASE}/logs")
log_run_context(
    logger,
    spark,
    {
        "course_limit_path": COURSE_LIMIT_PATH,
        "course_catalog_path": COURSE_CATALOG_PATH,
        "enrollments_path": f"{OUTPUT_BASE}/enrollments/",
        "block_boundaries": dict(BLOCK_BOUNDARIES),
        "ordering_field": PROTOCOL["split"]["ordering_field"],
        "pseudo_offering_policy": "first unassigned enrollment month anchors sequential pseudo-offerings; month template or 131-day fallback",
    },
)
run_started_at = start_run_timer()
quantile_lookup = spark.createDataFrame(
    [(item[0], item[1], item[2]) for item in QUANTILE_SPECS],
    ["quantile_index", "quantile", "percentile"],
)


def quantile_profile(df, value_column, metric, population):
    """Return a long percentile table, including tails needed for split audit."""
    aggregate = (
        df.filter(F.col(value_column).isNotNull())
        .agg(
            F.count("*").alias("sample_count"),
            F.avg(value_column).alias("mean_value"),
            F.stddev(value_column).alias("stddev_value"),
            F.min(value_column).alias("min_value"),
            F.max(value_column).alias("max_value"),
            F.expr(f"percentile_approx(`{value_column}`, {QUANTILE_ARRAY_SQL}, 10000)").alias("quantile_values"),
        )
    )
    return (
        aggregate.select(
            "sample_count", "mean_value", "stddev_value", "min_value", "max_value",
            F.posexplode("quantile_values").alias("quantile_index", "quantile_value"),
        )
        .join(F.broadcast(quantile_lookup), "quantile_index", "inner")
        .withColumn("metric", F.lit(metric))
        .withColumn("population", F.lit(population))
        .select(
            "population", "metric", "percentile", "quantile", "quantile_value",
            "sample_count", "mean_value", "stddev_value", "min_value", "max_value",
        )
    )

enrollments = spark.read.parquet(f"{OUTPUT_BASE}/enrollments/")
course_enrollment_counts = enrollments.groupBy("course_id").agg(F.count("*").alias("enrollment_count"))

# This is an observed enrollment-time span, not an official course duration.
# It is used only to assess whether enrollment chronology has useful temporal
# resolution where course schedule metadata is absent.
course_enrollment_time_summary = (
    enrollments.groupBy("course_id")
    .agg(
        F.count("*").alias("enrollment_count"),
        F.min("enroll_time").alias("first_enroll_time"),
        F.max("enroll_time").alias("last_enroll_time"),
    )
    .withColumn("observed_enrollment_span_days", F.datediff("last_enroll_time", "first_enroll_time"))
    .withColumn("first_enroll_month", F.date_trunc("month", "first_enroll_time"))
    .withColumn("last_enroll_month", F.date_trunc("month", "last_enroll_time"))
)
enrollment_time_overview = course_enrollment_time_summary.agg(
    F.countDistinct("course_id").alias("course_count"),
    F.sum("enrollment_count").alias("enrollment_count"),
    F.min("first_enroll_time").alias("earliest_first_enroll_time"),
    F.max("last_enroll_time").alias("latest_last_enroll_time"),
    F.avg("observed_enrollment_span_days").alias("avg_observed_enrollment_span_days"),
    F.expr("percentile_approx(observed_enrollment_span_days, 0.5)").alias("median_observed_enrollment_span_days"),
    F.expr("percentile_approx(observed_enrollment_span_days, 0.25)").alias("p25_observed_enrollment_span_days"),
    F.expr("percentile_approx(observed_enrollment_span_days, 0.75)").alias("p75_observed_enrollment_span_days"),
)
first_enroll_month_distribution = (
    course_enrollment_time_summary.groupBy("first_enroll_month")
    .agg(F.countDistinct("course_id").alias("course_count"), F.sum("enrollment_count").alias("enrollment_count"))
    .withColumn("boundary", F.lit("first_enroll_time"))
    .withColumnRenamed("first_enroll_month", "enrollment_month")
)
last_enroll_month_distribution = (
    course_enrollment_time_summary.groupBy("last_enroll_month")
    .agg(F.countDistinct("course_id").alias("course_count"), F.sum("enrollment_count").alias("enrollment_count"))
    .withColumn("boundary", F.lit("last_enroll_time"))
    .withColumnRenamed("last_enroll_month", "enrollment_month")
)
course_enrollment_month_distribution = first_enroll_month_distribution.unionByName(last_enroll_month_distribution).orderBy(
    "boundary", "enrollment_month"
)

def parse_course_date_array(column_name: str):
    """Extract date tokens even when the source Python-like list is malformed."""
    raw_value = F.coalesce(F.col(column_name), F.lit(""))
    # Keep only digits and hyphens. Everything else becomes a separator, so
    # broken quotes/brackets/commas cannot invalidate an otherwise valid date.
    date_tokens = F.split(F.regexp_replace(raw_value, r"[^0-9-]+", ","), ",")
    parsed_dates = F.transform(date_tokens, lambda value: F.try_to_timestamp(value))
    return F.filter(parsed_dates, lambda value: value.isNotNull())


# `course_limit.csv` may hold one date or a malformed Python-like list of
# dates. A course remains the split group here, so use its earliest listed
# start and latest listed end.
def parse_course_date_range(column_name: str, take_latest: bool):
    parsed_dates = parse_course_date_array(column_name)
    return F.array_max(parsed_dates) if take_latest else F.array_min(parsed_dates)


def parse_string_array(column_name: str):
    raw_value = F.coalesce(F.col(column_name), F.lit(""))
    season_tokens = F.split(F.regexp_replace(F.lower(raw_value), r"[^a-z]+", ","), ",")
    season_tokens = F.filter(season_tokens, lambda value: F.length(value) > 0)
    return F.transform(
        season_tokens,
        lambda value: F.when(value == "sprin", F.lit("spring")).otherwise(value),
    )


course_limit_rows = (
    spark.read.option("header", True)
    .option("quote", '"')
    .option("escape", '"')
    .option("multiLine", True)
    .option("mode", "PERMISSIVE")
    .csv(COURSE_LIMIT_PATH)
    .select(
        F.when(F.col("course_id").startswith("C_"), F.col("course_id"))
        .otherwise(F.concat(F.lit("C_"), F.col("course_id")))
        .alias("course_id"),
        parse_course_date_range("start_date", take_latest=False).alias("course_start_time"),
        parse_course_date_range("end_date", take_latest=True).alias("course_end_time"),
        parse_course_date_array("start_date").alias("start_date_values"),
        parse_course_date_array("end_date").alias("end_date_values"),
        parse_string_array("season").alias("season_values"),
        F.trim(F.col("name")).alias("course_limit_name"),
        F.col("season").alias("season"),
        F.col("type").alias("course_type"),
    )
    .filter(F.col("course_id").isNotNull())
    .dropDuplicates()
)

# The time-split analysis is at course level, but schedule duration must retain
# every source row: the same course can be represented by several offerings.
course_limit = course_limit_rows.groupBy("course_id").agg(
    F.min("course_start_time").alias("course_start_time"),
    F.max("course_end_time").alias("course_end_time"),
    F.first("course_limit_name", ignorenulls=True).alias("course_limit_name"),
    F.first("season", ignorenulls=True).alias("season"),
    F.first("course_type", ignorenulls=True).alias("course_type"),
)

# Preserve the date-list pairing as schedule/run metadata. This is audit-only
# until alignment with enrollment records has been established.
course_schedule_array_alignment_audit = (
    course_limit_rows.select(
        "course_id",
        "course_limit_name",
        "season",
        F.size("start_date_values").alias("start_date_count"),
        F.size("end_date_values").alias("end_date_count"),
        F.size("season_values").alias("season_count"),
    )
    .withColumn(
        "array_alignment_status",
        F.when(
            (F.col("start_date_count") == F.col("end_date_count"))
            & (F.col("start_date_count") == F.col("season_count")),
            F.lit("aligned"),
        ).when(F.col("start_date_count") == F.col("end_date_count"), F.lit("season_count_mismatch"))
        .otherwise(F.lit("date_count_mismatch")),
    )
)
course_schedule_runs = (
    course_limit_rows.select(
        "course_id",
        "course_limit_name",
        "season_values",
        F.size("season_values").alias("season_value_count"),
        F.posexplode(F.arrays_zip("start_date_values", "end_date_values")).alias("schedule_index", "date_pair"),
    )
    .select(
        "course_id",
        "course_limit_name",
        "schedule_index",
        # A single season on a source row applies to all date pairs on that row;
        # otherwise season[i] is paired with start_date[i]/end_date[i].
        F.when(F.col("season_value_count") == 1, F.get(F.col("season_values"), F.lit(0)))
        .otherwise(F.get(F.col("season_values"), F.col("schedule_index")))
        .alias("season"),
        F.col("date_pair.start_date_values").alias("run_start_time"),
        F.col("date_pair.end_date_values").alias("run_end_time"),
    )
    .filter(
        F.col("run_start_time").isNotNull()
        & F.col("run_end_time").isNotNull()
        & (F.col("run_end_time") >= F.col("run_start_time"))
    )
    .withColumn("run_duration_days", F.datediff("run_end_time", "run_start_time"))
    .withColumn(
        "schedule_run_id",
        F.sha2(
            F.concat_ws(
                "||",
                "course_id",
                F.col("schedule_index").cast("string"),
                F.date_format("run_start_time", "yyyy-MM-dd"),
                F.date_format("run_end_time", "yyyy-MM-dd"),
            ),
            256,
        ),
    )
)

# Calendar-month view of each offering. A run is expanded only to the months
# it actually touches; active_days_in_month prevents partial months at either
# end from being counted as full months.
course_run_months = (
    course_schedule_runs.withColumn("run_start_month", F.to_date(F.date_trunc("month", "run_start_time")))
    .withColumn("run_end_month", F.to_date(F.date_trunc("month", "run_end_time")))
    .withColumn("month_sequence", F.sequence("run_start_month", "run_end_month", F.expr("interval 1 month")))
    .withColumn("calendar_month", F.explode("month_sequence"))
    .withColumn("active_period_start", F.greatest(F.to_date("run_start_time"), F.col("calendar_month")))
    .withColumn("active_period_end", F.least(F.to_date("run_end_time"), F.last_day("calendar_month")))
    .withColumn("active_days_in_month", F.datediff("active_period_end", "active_period_start") + F.lit(1))
    .withColumn("months_covered", F.size("month_sequence"))
)
course_run_active_month_distribution = (
    course_run_months.groupBy("calendar_month")
    .agg(
        F.countDistinct("schedule_run_id").alias("active_schedule_run_count"),
        F.countDistinct("course_id").alias("active_course_count"),
        F.sum("active_days_in_month").alias("active_run_days"),
    )
    .orderBy("calendar_month")
)
course_run_start_month_distribution = (
    course_schedule_runs.withColumn("start_month", F.to_date(F.date_trunc("month", "run_start_time")))
    .groupBy("start_month")
    .agg(
        F.countDistinct("schedule_run_id").alias("schedule_run_count"),
        F.countDistinct("course_id").alias("course_count"),
    )
    .orderBy("start_month")
)
course_run_month_span_distribution = (
    course_run_months.select("schedule_run_id", "course_id", "months_covered", "run_duration_days")
    .dropDuplicates(["schedule_run_id"])
    .groupBy("months_covered")
    .agg(
        F.count("*").alias("schedule_run_count"),
        F.countDistinct("course_id").alias("course_count"),
        F.avg("run_duration_days").alias("avg_run_duration_days"),
    )
    .orderBy("months_covered")
)
# Most common offering template for each calendar start month. It is a prior
# for analysis only, never a substitute for an observed course schedule.
schedule_templates = (
    course_run_months.select(
        "schedule_run_id",
        F.month("run_start_time").alias("template_start_month"),
        "months_covered",
        F.dayofmonth("run_start_time").alias("template_start_day"),
        F.dayofmonth("run_end_time").alias("template_end_day"),
    )
    .dropDuplicates(["schedule_run_id"])
    .groupBy("template_start_month", "months_covered", "template_start_day", "template_end_day")
    .agg(F.count("*").alias("template_run_count"))
)
template_rank_window = Window.partitionBy("template_start_month").orderBy(
    F.desc("template_run_count"), F.desc("months_covered")
)
dominant_schedule_template_by_start_month = (
    schedule_templates.withColumn("template_rank", F.row_number().over(template_rank_window))
    .filter(F.col("template_rank") == 1)
    .drop("template_rank")
)
reliable_schedule_template_by_start_month = dominant_schedule_template_by_start_month.filter(
    F.col("template_run_count") >= F.lit(MONTH_TEMPLATE_MIN_RUNS)
)
course_run_duration_overview = course_schedule_runs.agg(
    F.count("*").alias("schedule_run_count"),
    F.countDistinct("course_id").alias("course_count"),
    F.avg("run_duration_days").alias("avg_run_duration_days"),
    F.expr("percentile_approx(run_duration_days, 0.5)").alias("median_run_duration_days"),
    F.expr("percentile_approx(run_duration_days, 0.25)").alias("p25_run_duration_days"),
    F.expr("percentile_approx(run_duration_days, 0.75)").alias("p75_run_duration_days"),
)
course_run_season_summary = (
    course_schedule_runs.groupBy(F.coalesce(F.col("season"), F.lit("unknown")).alias("season"))
    .agg(
        F.count("*").alias("schedule_run_count"),
        F.countDistinct("course_id").alias("course_count"),
        F.avg("run_duration_days").alias("avg_run_duration_days"),
        F.min("run_start_time").alias("min_run_start_time"),
        F.max("run_end_time").alias("max_run_end_time"),
    )
    .orderBy("season")
)

# Analysis only: test whether each learner enrollment can be located in a
# scheduled offering of the same course.  No split or offering assignment is
# created here. Identical intervals are deduplicated before matching so a
# repeated metadata row does not turn one match into an artificial ambiguity.
course_run_intervals = course_schedule_runs.select(
    "course_id", "run_start_time", "run_end_time"
).dropDuplicates()
enrollment_run_candidates = (
    enrollments.select("enrollment_id", "course_id", "enroll_time")
    .join(course_run_intervals, "course_id", "inner")
    .filter(
        F.col("enroll_time").isNotNull()
        & (F.col("enroll_time") >= F.col("run_start_time"))
        & (F.col("enroll_time") <= F.col("run_end_time"))
    )
    .select("enrollment_id", "course_id", "run_start_time", "run_end_time")
    .dropDuplicates()
)
enrollment_run_match_counts = enrollment_run_candidates.groupBy("enrollment_id").agg(
    F.count("*").alias("matching_run_count")
)
enrollment_course_run_match_status = (
    enrollments.select("enrollment_id", "course_id", "enroll_time")
    .join(enrollment_run_match_counts, "enrollment_id", "left")
    .withColumn("matching_run_count", F.coalesce(F.col("matching_run_count"), F.lit(0)))
    .withColumn(
        "run_match_status",
        F.when(F.col("enroll_time").isNull(), F.lit("missing_enroll_time"))
        .when(F.col("matching_run_count") == 0, F.lit("unmatched"))
        .when(F.col("matching_run_count") == 1, F.lit("matched_one_run"))
        .otherwise(F.lit("matched_multiple_runs")),
    )
)
enrollment_course_run_match_totals = enrollment_course_run_match_status.agg(
    F.count("*").alias("total_enrollment_count")
)
enrollment_course_run_match_summary = (
    enrollment_course_run_match_status.groupBy("run_match_status")
    .agg(
        F.count("*").alias("enrollment_count"),
        F.countDistinct("course_id").alias("course_count"),
        F.avg("matching_run_count").alias("avg_matching_run_count"),
    )
    .crossJoin(enrollment_course_run_match_totals)
    .withColumn("enrollment_ratio", F.col("enrollment_count") / F.col("total_enrollment_count"))
    .drop("total_enrollment_count")
    .orderBy("run_match_status")
)
course_enrollment_run_match_summary = (
    enrollment_course_run_match_status.groupBy("course_id")
    .agg(
        F.count("*").alias("enrollment_count"),
        F.sum(F.when(F.col("run_match_status") == "matched_one_run", 1).otherwise(0)).alias("matched_one_run_count"),
        F.sum(F.when(F.col("run_match_status") == "matched_multiple_runs", 1).otherwise(0)).alias("matched_multiple_runs_count"),
        F.sum(F.when(F.col("run_match_status") == "unmatched", 1).otherwise(0)).alias("unmatched_count"),
        F.sum(F.when(F.col("run_match_status") == "missing_enroll_time", 1).otherwise(0)).alias("missing_enroll_time_count"),
    )
    .withColumn(
        "matched_one_run_ratio",
        F.col("matched_one_run_count") / F.col("enrollment_count"),
    )
)

course_catalog = (
    spark.read.json(COURSE_CATALOG_PATH)
    .select(F.col("id").alias("course_id"), F.trim(F.col("name")).alias("course_name"))
    .filter(F.col("course_id").isNotNull())
    .dropDuplicates(["course_id"])
)

active_courses = course_enrollment_counts.join(course_limit, "course_id", "left")
courses_without_schedule = active_courses.join(
    course_run_intervals.select("course_id").dropDuplicates(), "course_id", "left_anti"
)
missing_schedule_enrollment_profile = (
    enrollments.join(courses_without_schedule.select("course_id"), "course_id", "inner")
    .groupBy("course_id")
    .agg(
        F.count("*").alias("enrollment_count"),
        F.min("enroll_time").alias("first_enroll_time"),
        F.max("enroll_time").alias("last_enroll_time"),
    )
    .withColumn("observed_enrollment_span_days", F.datediff("last_enroll_time", "first_enroll_time"))
)

# These distributions describe when enrollments were observed for courses with
# no valid schedule metadata. They must not be interpreted as course opening
# dates: the collection window can truncate the true first enrollment.
no_schedule_enrollment_events = (
    enrollments.join(courses_without_schedule.select("course_id"), "course_id", "inner")
    .filter(F.col("enroll_time").isNotNull())
    .withColumn("enrollment_month", F.to_date(F.date_trunc("month", "enroll_time")))
    .withColumn("enrollment_year", F.year("enroll_time"))
    .withColumn("month_of_year", F.month("enroll_time"))
    .withColumn("day_of_month", F.dayofmonth("enroll_time"))
)
no_schedule_enrollment_total = no_schedule_enrollment_events.agg(
    F.count("*").alias("total_enrollment_count")
)
no_schedule_enrollment_overview = (
    no_schedule_enrollment_events.agg(
        F.count("*").alias("enrollment_count"),
        F.countDistinct("course_id").alias("course_count"),
        F.countDistinct("user_id").alias("user_count"),
        F.min("enroll_time").alias("earliest_enroll_time"),
        F.max("enroll_time").alias("latest_enroll_time"),
    )
)
no_schedule_enrollment_year_month_distribution = (
    no_schedule_enrollment_events.groupBy("enrollment_month")
    .agg(
        F.count("*").alias("enrollment_count"),
        F.countDistinct("course_id").alias("course_count"),
        F.countDistinct("user_id").alias("user_count"),
    )
    .crossJoin(no_schedule_enrollment_total)
    .withColumn("enrollment_ratio", F.col("enrollment_count") / F.col("total_enrollment_count"))
    .drop("total_enrollment_count")
    .orderBy("enrollment_month")
)
no_schedule_enrollment_month_of_year_distribution = (
    no_schedule_enrollment_events.groupBy("month_of_year")
    .agg(
        F.count("*").alias("enrollment_count"),
        F.countDistinct("course_id").alias("course_count"),
        F.countDistinct("user_id").alias("user_count"),
    )
    .crossJoin(no_schedule_enrollment_total)
    .withColumn("enrollment_ratio", F.col("enrollment_count") / F.col("total_enrollment_count"))
    .drop("total_enrollment_count")
    .orderBy("month_of_year")
)
no_schedule_enrollment_day_of_month_distribution = (
    no_schedule_enrollment_events.groupBy("day_of_month")
    .agg(
        F.count("*").alias("enrollment_count"),
        F.countDistinct("course_id").alias("course_count"),
    )
    .crossJoin(no_schedule_enrollment_total)
    .withColumn("enrollment_ratio", F.col("enrollment_count") / F.col("total_enrollment_count"))
    .drop("total_enrollment_count")
    .orderBy("day_of_month")
)

# A month is a defensible observed-time cohort, unlike first_enroll_time which
# is affected by left truncation.  This is still a pseudo-offering: it does
# not assert that the course opened in that month.  A (course, month) cohort
# remains indivisible when it is allocated to a temporal block.
no_schedule_monthly_cohorts = (
    no_schedule_enrollment_events.groupBy("course_id", "enrollment_month")
    .agg(
        F.count("*").alias("enrollment_count"),
        F.countDistinct("user_id").alias("user_count"),
        F.min("enroll_time").alias("first_enroll_time_in_month"),
        F.max("enroll_time").alias("last_enroll_time_in_month"),
    )
    .withColumn(
        "pseudo_offering_id",
        F.concat_ws("__enrollment_month__", "course_id", F.date_format("enrollment_month", "yyyy-MM")),
    )
    .withColumn("timeline_source", F.lit("enrollment_month_proxy"))
)
no_schedule_cohort_allocation_window = (
    Window.orderBy("enrollment_month", "course_id")
    .rowsBetween(Window.unboundedPreceding, Window.currentRow)
)
no_schedule_monthly_cohort_blocks = (
    no_schedule_monthly_cohorts.crossJoin(no_schedule_enrollment_total)
    .withColumn("cumulative_enrollment_count", F.sum("enrollment_count").over(no_schedule_cohort_allocation_window))
    .withColumn(
        "enrollment_midpoint_fraction",
        (F.col("cumulative_enrollment_count") - F.col("enrollment_count") / F.lit(2.0))
        / F.col("total_enrollment_count"),
    )
    # course_id breaks ties inside a month only. Thus ordering is strict across
    # months and balanced/deterministic, rather than temporal, inside a month.
    .withColumn(
        "temporal_block",
        temporal_block_expression("enrollment_midpoint_fraction"),
    )
    .drop("total_enrollment_count")
)

# Preferred alternative for a month-based evaluation: never split a calendar
# month at all.  This sacrifices an exact 70/5/… ratio in exchange for an
# unambiguous temporal boundary.  The midpoint rule chooses the nearest target
# block for each whole month.
no_schedule_month_allocation_window = (
    Window.orderBy("enrollment_month")
    .rowsBetween(Window.unboundedPreceding, Window.currentRow)
)
no_schedule_strict_month_lookup = (
    no_schedule_monthly_cohorts.groupBy("enrollment_month")
    .agg(F.sum("enrollment_count").alias("enrollment_count"))
    .crossJoin(no_schedule_enrollment_total)
    .withColumn("cumulative_enrollment_count", F.sum("enrollment_count").over(no_schedule_month_allocation_window))
    .withColumn(
        "enrollment_midpoint_fraction",
        (F.col("cumulative_enrollment_count") - F.col("enrollment_count") / F.lit(2.0))
        / F.col("total_enrollment_count"),
    )
    .withColumn(
        "temporal_block",
        temporal_block_expression("enrollment_midpoint_fraction"),
    )
    .drop("total_enrollment_count")
)
no_schedule_strict_month_cohort_blocks = no_schedule_monthly_cohorts.join(
    no_schedule_strict_month_lookup.select("enrollment_month", "temporal_block"),
    "enrollment_month",
    "inner",
)
no_schedule_strict_month_block_summary = (
    no_schedule_strict_month_cohort_blocks.groupBy("temporal_block")
    .agg(
        F.countDistinct("pseudo_offering_id").alias("pseudo_offering_count"),
        F.countDistinct("course_id").alias("course_count"),
        F.countDistinct("enrollment_month").alias("month_count"),
        F.sum("enrollment_count").alias("enrollment_count"),
        F.min("enrollment_month").alias("min_enrollment_month"),
        F.max("enrollment_month").alias("max_enrollment_month"),
    )
    .crossJoin(no_schedule_enrollment_total)
    .withColumn("realized_enrollment_ratio", F.col("enrollment_count") / F.col("total_enrollment_count"))
    .drop("total_enrollment_count")
    .orderBy("temporal_block")
)
no_schedule_monthly_cohort_block_summary = (
    no_schedule_monthly_cohort_blocks.groupBy("temporal_block")
    .agg(
        F.countDistinct("pseudo_offering_id").alias("pseudo_offering_count"),
        F.countDistinct("course_id").alias("course_count"),
        F.countDistinct("enrollment_month").alias("month_count"),
        F.sum("enrollment_count").alias("enrollment_count"),
        F.min("enrollment_month").alias("min_enrollment_month"),
        F.max("enrollment_month").alias("max_enrollment_month"),
    )
    .crossJoin(no_schedule_enrollment_total)
    .withColumn("realized_enrollment_ratio", F.col("enrollment_count") / F.col("total_enrollment_count"))
    .drop("total_enrollment_count")
    .orderBy("temporal_block")
)
# Month-level candidate only: first enrollment supplies the calendar-month
# anchor, and a sufficiently common observed template supplies the duration.
# It deliberately does not invent exact start/end days.
missing_schedule_month_bucket_analysis = (
    missing_schedule_enrollment_profile.withColumn("anchor_month", F.month("first_enroll_time"))
    .join(
        reliable_schedule_template_by_start_month,
        F.col("anchor_month") == F.col("template_start_month"),
        "left",
    )
    .withColumn(
        "inferred_start_month",
        F.when(F.col("template_start_month").isNotNull(), F.to_date(F.date_trunc("month", "first_enroll_time"))),
    )
    .withColumn(
        "inferred_end_month",
        F.when(F.col("inferred_start_month").isNotNull(), F.add_months("inferred_start_month", F.col("months_covered") - 1)),
    )
    .withColumn(
        "inference_status",
        F.when(F.col("template_start_month").isNull(), F.lit("no_reliable_month_template"))
        .otherwise(F.lit("monthly_template_candidate")),
    )
    .select(
        "course_id", "enrollment_count", "first_enroll_time", "last_enroll_time", "observed_enrollment_span_days",
        "anchor_month", "template_start_month", "months_covered", "template_run_count",
        "inferred_start_month", "inferred_end_month", "inference_status",
    )
)
missing_schedule_month_bucket_summary = (
    missing_schedule_month_bucket_analysis.groupBy(
        "inference_status", "inferred_start_month", "inferred_end_month", "months_covered"
    )
    .agg(F.countDistinct("course_id").alias("course_count"), F.sum("enrollment_count").alias("enrollment_count"))
    .orderBy("inferred_start_month", "inference_status")
)

# ---------------------------------------------------------------------------
# Enrollment-anchored pseudo-offerings for courses without schedule metadata.
#
# A single course can have enrollment records spread across many real runs.
# Therefore the first enrollment of the entire course must not define one
# multi-year interval.  Instead, the first *unassigned* enrollment anchors an
# offering; enrollment records through that offering's inferred end date are
# assigned to it, then the next unassigned record starts the next offering.
# This is a simulation aid for temporal features, never an observed schedule.
# ---------------------------------------------------------------------------
month_template_rows = reliable_schedule_template_by_start_month.select(
    "template_start_month", "months_covered"
).collect()
MONTH_TO_TEMPLATE_MONTHS = {
    int(row["template_start_month"]): int(row["months_covered"])
    for row in month_template_rows
}

pseudo_input = no_schedule_enrollment_events.select(
    "enrollment_id", "user_id", "course_id", "enroll_time"
)
pseudo_schema = (
    pseudo_input.schema
    .add(StructField("pseudo_offering_id", StringType(), nullable=False))
    .add(StructField("pseudo_sequence", IntegerType(), nullable=False))
    .add(StructField("pseudo_start_date", DateType(), nullable=False))
    .add(StructField("pseudo_end_date", DateType(), nullable=False))
    .add(StructField("duration_days", IntegerType(), nullable=False))
    .add(StructField("duration_source", StringType(), nullable=False))
    .add(StructField("anchor_enrollment_id", pseudo_input.schema["enrollment_id"].dataType, nullable=False))
    .add(StructField("anchor_enroll_time", pseudo_input.schema["enroll_time"].dataType, nullable=False))
    .add(StructField("timeline_source", StringType(), nullable=False))
)


def assign_enrollment_anchored_pseudo_offerings(pdf: pd.DataFrame) -> pd.DataFrame:
    """Assign sequential inferred offerings inside one course.

    The function runs per course through ``applyInPandas``.  It intentionally
    anchors only on an observed enrollment, never on a fabricated calendar
    date.  Exact day-level template dates are not asserted: reliable templates
    use full calendar months, while the 131-day fallback preserves the
    schedule-run median under Spark's ``datediff`` convention.
    """
    pdf = pdf.sort_values(["enroll_time", "enrollment_id"], kind="stable").reset_index(drop=True)
    records = []
    cursor = 0
    sequence = 0
    while cursor < len(pdf):
        anchor = pdf.iloc[cursor]
        start = pd.Timestamp(anchor["enroll_time"]).normalize()
        template_months = MONTH_TO_TEMPLATE_MONTHS.get(int(start.month))
        if template_months is not None:
            # E.g. 01 Jan plus 7 calendar months minus one day = 31 Jul.
            end = start + pd.DateOffset(months=template_months) - pd.Timedelta(days=1)
            duration_days = int((end - start).days)
            duration_source = "reliable_start_month_template"
        else:
            end = start + pd.Timedelta(days=PSEUDO_OFFERING_FALLBACK_DURATION_DAYS)
            duration_days = PSEUDO_OFFERING_FALLBACK_DURATION_DAYS
            duration_source = "schedule_run_median_fallback"

        sequence += 1
        next_cursor = cursor
        while next_cursor < len(pdf) and pd.Timestamp(pdf.iloc[next_cursor]["enroll_time"]) <= end:
            row = pdf.iloc[next_cursor]
            records.append({
                "enrollment_id": row["enrollment_id"],
                "user_id": row["user_id"],
                "course_id": row["course_id"],
                "enroll_time": row["enroll_time"],
                "pseudo_offering_id": f"{row['course_id']}__enrollment_anchor__{start:%Y-%m-%d}__{sequence:03d}",
                "pseudo_sequence": sequence,
                "pseudo_start_date": start.date(),
                "pseudo_end_date": end.date(),
                "duration_days": duration_days,
                "duration_source": duration_source,
                "anchor_enrollment_id": anchor["enrollment_id"],
                "anchor_enroll_time": anchor["enroll_time"],
                "timeline_source": "enrollment_anchored_proxy",
            })
            next_cursor += 1
        cursor = next_cursor
    return pd.DataFrame(records)


enrollment_anchored_pseudo_offering_assignments = pseudo_input.groupBy("course_id").applyInPandas(
    assign_enrollment_anchored_pseudo_offerings,
    schema=pseudo_schema,
)

# Actual learning activity is intentionally narrower than a comment: a learner
# is active here only when at least one video or problem event occurs inside the
# inferred offering interval.  The event processors already require event_time
# >= enroll_time; the interval filter adds the pseudo-offering end boundary.
pseudo_event_bounds = enrollment_anchored_pseudo_offering_assignments.select(
    "enrollment_id", "pseudo_offering_id", "pseudo_start_date", "pseudo_end_date"
)
video_active_enrollments = (
    spark.read.parquet(f"{OUTPUT_BASE}/video_events_clean/")
    .select("enrollment_id", "event_time")
    .join(pseudo_event_bounds, "enrollment_id", "inner")
    .filter(
        (F.col("event_time") >= F.to_timestamp("pseudo_start_date"))
        & (F.col("event_time") < F.to_timestamp(F.date_add("pseudo_end_date", 1)))
    )
    .select("enrollment_id", F.lit(1).alias("video_active"))
    .dropDuplicates(["enrollment_id"])
)
problem_active_enrollments = (
    spark.read.parquet(f"{OUTPUT_BASE}/problem_events_clean/")
    .select("enrollment_id", "availability_time")
    .join(pseudo_event_bounds, "enrollment_id", "inner")
    .filter(
        (F.col("availability_time") >= F.to_timestamp("pseudo_start_date"))
        & (F.col("availability_time") < F.to_timestamp(F.date_add("pseudo_end_date", 1)))
    )
    .select("enrollment_id", F.lit(1).alias("problem_active"))
    .dropDuplicates(["enrollment_id"])
)
enrollment_anchored_activity = (
    enrollment_anchored_pseudo_offering_assignments
    .join(video_active_enrollments, "enrollment_id", "left")
    .join(problem_active_enrollments, "enrollment_id", "left")
    .withColumn("video_active", F.coalesce("video_active", F.lit(0)))
    .withColumn("problem_active", F.coalesce("problem_active", F.lit(0)))
    .withColumn("learning_active", F.greatest("video_active", "problem_active"))
)
enrollment_anchored_pseudo_offering_summary = (
    enrollment_anchored_activity.groupBy(
        "course_id", "pseudo_offering_id", "pseudo_sequence", "pseudo_start_date", "pseudo_end_date",
        "duration_days", "duration_source", "timeline_source",
    )
    .agg(
        F.count("*").alias("enrollment_count"),
        F.countDistinct("user_id").alias("enrolled_user_count"),
        F.sum("video_active").alias("video_active_enrollment_count"),
        F.sum("problem_active").alias("problem_active_enrollment_count"),
        F.sum("learning_active").alias("learning_active_enrollment_count"),
        F.countDistinct(F.when(F.col("learning_active") == 1, F.col("user_id"))).alias("learning_active_user_count"),
    )
    .withColumn("learning_active_enrollment_ratio", F.col("learning_active_enrollment_count") / F.col("enrollment_count"))
    .withColumn("learning_active_user_ratio", F.col("learning_active_user_count") / F.col("enrolled_user_count"))
)
enrollment_anchored_activity_overview = enrollment_anchored_activity.agg(
    F.countDistinct("course_id").alias("course_count"),
    F.countDistinct("pseudo_offering_id").alias("pseudo_offering_count"),
    F.count("*").alias("enrollment_count"),
    F.countDistinct("user_id").alias("enrolled_user_count"),
    F.sum("video_active").alias("video_active_enrollment_count"),
    F.sum("problem_active").alias("problem_active_enrollment_count"),
    F.sum("learning_active").alias("learning_active_enrollment_count"),
    F.countDistinct(F.when(F.col("learning_active") == 1, F.col("user_id"))).alias("learning_active_user_count"),
    F.avg("duration_days").alias("assignment_weighted_avg_duration_days"),
    F.expr("percentile_approx(duration_days, 0.5)").alias("assignment_weighted_median_duration_days"),
).withColumn("learning_active_enrollment_ratio", F.col("learning_active_enrollment_count") / F.col("enrollment_count")) \
 .withColumn("learning_active_user_ratio", F.col("learning_active_user_count") / F.col("enrolled_user_count"))
enrollment_anchored_duration_source_summary = (
    enrollment_anchored_pseudo_offering_summary.groupBy("duration_source", "duration_days")
    .agg(
        F.countDistinct("pseudo_offering_id").alias("pseudo_offering_count"),
        F.countDistinct("course_id").alias("course_count"),
        F.sum("enrollment_count").alias("enrollment_count"),
        F.sum("learning_active_enrollment_count").alias("learning_active_enrollment_count"),
    )
    .withColumn("learning_active_enrollment_ratio", F.col("learning_active_enrollment_count") / F.col("enrollment_count"))
    .orderBy("duration_source", "duration_days")
)
missing_time = active_courses.filter(F.col("course_end_time").isNull())
eligible_courses = active_courses.filter(F.col("course_end_time").isNotNull())
courses_with_schedule = (
    eligible_courses.filter(
        F.col("course_start_time").isNotNull() & (F.col("course_end_time") >= F.col("course_start_time"))
    )
    .withColumn("course_schedule_span_days", F.datediff("course_end_time", "course_start_time"))
    .withColumn("course_start_month", F.date_trunc("month", "course_start_time"))
    .withColumn("course_end_month", F.date_trunc("month", "course_end_time"))
)
course_schedule_overview = courses_with_schedule.agg(
    F.countDistinct("course_id").alias("course_count_with_valid_start_end"),
    F.sum("enrollment_count").alias("enrollment_count_with_valid_start_end"),
    F.avg("course_schedule_span_days").alias("avg_course_schedule_span_days"),
    F.expr("percentile_approx(course_schedule_span_days, 0.5)").alias("median_course_schedule_span_days"),
    F.expr("percentile_approx(course_schedule_span_days, 0.25)").alias("p25_course_schedule_span_days"),
    F.expr("percentile_approx(course_schedule_span_days, 0.75)").alias("p75_course_schedule_span_days"),
    F.min("course_start_time").alias("earliest_course_start_time"),
    F.max("course_end_time").alias("latest_course_end_time"),
)
course_start_month_distribution = (
    courses_with_schedule.groupBy("course_start_month")
    .agg(F.countDistinct("course_id").alias("course_count"), F.sum("enrollment_count").alias("enrollment_count"))
    .withColumn("boundary", F.lit("course_start_time"))
    .withColumnRenamed("course_start_month", "course_month")
)
course_end_month_distribution_with_start = (
    courses_with_schedule.groupBy("course_end_month")
    .agg(F.countDistinct("course_id").alias("course_count"), F.sum("enrollment_count").alias("enrollment_count"))
    .withColumn("boundary", F.lit("course_end_time"))
    .withColumnRenamed("course_end_month", "course_month")
)
course_schedule_month_distribution = course_start_month_distribution.unionByName(
    course_end_month_distribution_with_start
).orderBy("boundary", "course_month")

# Trial chronological allocation on every course with either an observed
# schedule or a reliable month-level bucket. A course remains indivisible;
# course_id is only a deterministic tie-breaker for identical end dates.
observed_timeline_population = courses_with_schedule.select(
    "course_id",
    "enrollment_count",
    F.to_date("course_start_time").alias("timeline_start_date"),
    F.to_date("course_end_time").alias("timeline_end_date"),
    F.lit("observed_schedule").alias("timeline_source"),
)
bucket_timeline_population = (
    missing_schedule_month_bucket_analysis.filter(F.col("inference_status") == "monthly_template_candidate")
    .select(
        "course_id",
        "enrollment_count",
        F.col("inferred_start_month").alias("timeline_start_date"),
        F.last_day("inferred_end_month").alias("timeline_end_date"),
        F.lit("inferred_month_bucket").alias("timeline_source"),
    )
)
unified_timeline_population = observed_timeline_population.unionByName(bucket_timeline_population)
total_unified_timeline_enrollments = (
    unified_timeline_population.agg(F.sum("enrollment_count").alias("n")).first()["n"] or 0
)
if total_unified_timeline_enrollments == 0:
    raise ValueError("No course has an observed or reliable inferred timeline.")

unified_order_window = Window.orderBy("timeline_end_date", "course_id").rowsBetween(
    Window.unboundedPreceding, Window.currentRow
)
unified_temporal_block_candidates = (
    unified_timeline_population.withColumn(
        "cumulative_enrollment_count", F.sum("enrollment_count").over(unified_order_window)
    )
    .withColumn(
        "enrollment_midpoint_fraction",
        (F.col("cumulative_enrollment_count") - F.col("enrollment_count") / F.lit(2.0))
        / F.lit(float(total_unified_timeline_enrollments)),
    )
    .withColumn(
        "temporal_block",
        temporal_block_expression("enrollment_midpoint_fraction"),
    )
)
unified_temporal_block_summary = (
    unified_temporal_block_candidates.groupBy("temporal_block")
    .agg(
        F.countDistinct("course_id").alias("course_count"),
        F.sum("enrollment_count").alias("enrollment_count"),
        F.min("timeline_start_date").alias("min_timeline_start_date"),
        F.max("timeline_end_date").alias("max_timeline_end_date"),
    )
    .withColumn("realized_enrollment_ratio", F.col("enrollment_count") / F.lit(float(total_unified_timeline_enrollments)))
    .withColumn("target_enrollment_ratio", target_ratio_expression())
    .orderBy("temporal_block")
)
unified_temporal_block_source_summary = (
    unified_temporal_block_candidates.groupBy("temporal_block", "timeline_source")
    .agg(F.countDistinct("course_id").alias("course_count"), F.sum("enrollment_count").alias("enrollment_count"))
    .orderBy("temporal_block", "timeline_source")
)

total_enrollments = eligible_courses.agg(F.sum("enrollment_count").alias("n")).first()["n"] or 0
if total_enrollments == 0:
    raise ValueError("No active course with a parseable end_date; cannot form temporal blocks.")

order_window = Window.orderBy("course_end_time", "course_id").rowsBetween(Window.unboundedPreceding, Window.currentRow)
candidate_blocks = (
    eligible_courses.withColumn("cumulative_enrollment_count", F.sum("enrollment_count").over(order_window))
    .withColumn(
        "enrollment_midpoint_fraction",
        (F.col("cumulative_enrollment_count") - F.col("enrollment_count") / F.lit(2.0)) / F.lit(float(total_enrollments)),
    )
    .withColumn(
        "temporal_block",
        temporal_block_expression("enrollment_midpoint_fraction"),
    )
    .select(
        "temporal_block",
        "course_id",
        "course_start_time",
        "course_end_time",
        "season",
        "course_type",
        "enrollment_count",
        "cumulative_enrollment_count",
        "enrollment_midpoint_fraction",
    )
)

block_summary = (
    candidate_blocks.groupBy("temporal_block")
    .agg(
        F.countDistinct("course_id").alias("course_count"),
        F.sum("enrollment_count").alias("enrollment_count"),
        F.min("course_start_time").alias("min_course_start_time"),
        F.max("course_end_time").alias("max_course_end_time"),
    )
    .withColumn("realized_enrollment_ratio", F.col("enrollment_count") / F.lit(float(total_enrollments)))
    .withColumn("target_enrollment_ratio", target_ratio_expression())
    .orderBy("temporal_block")
)

# A single long-form table makes the spread and tail behaviour auditable
# without requiring users to infer it from mean/median-only summaries.
quantile_profiles = quantile_profile(
    course_enrollment_time_summary, "observed_enrollment_span_days",
    "observed_enrollment_span_days", "all_courses_with_enrollments",
)
for profile in (
    quantile_profile(course_enrollment_counts, "enrollment_count", "enrollment_count", "all_courses_with_enrollments"),
    quantile_profile(course_schedule_runs, "run_duration_days", "schedule_run_duration_days", "valid_schedule_runs"),
    quantile_profile(courses_with_schedule, "course_schedule_span_days", "course_schedule_span_days", "courses_with_observed_schedule"),
    quantile_profile(missing_schedule_enrollment_profile, "observed_enrollment_span_days", "observed_enrollment_span_days", "courses_without_schedule"),
    quantile_profile(candidate_blocks, "enrollment_count", "enrollment_count", "timeline_only_course_candidates"),
    quantile_profile(unified_temporal_block_candidates, "enrollment_count", "enrollment_count", "hybrid_course_candidates"),
):
    quantile_profiles = quantile_profiles.unionByName(profile)
quantile_profiles = quantile_profiles.orderBy("population", "metric", "quantile")

monthly_distribution = (
    eligible_courses.groupBy(F.date_trunc("month", "course_end_time").alias("course_end_month"))
    .agg(
        F.countDistinct("course_id").alias("course_count"),
        F.sum("enrollment_count").alias("enrollment_count"),
    )
    .withColumn("enrollment_ratio", F.col("enrollment_count") / F.lit(float(total_enrollments)))
    .orderBy("course_end_month")
)

# Name matching is audit-only. Identical names do not prove identical course
# runs, so this output must never be used to impute a missing end date.
normalize_name = lambda column: F.lower(F.trim(F.regexp_replace(column, r"\s+", " ")))
dated_name_lookup = (
    course_limit.filter(F.col("course_end_time").isNotNull() & F.col("course_limit_name").isNotNull())
    .withColumn("normalized_course_name", normalize_name(F.col("course_limit_name")))
    .groupBy("normalized_course_name")
    .agg(
        F.countDistinct("course_id").alias("dated_course_id_count"),
        F.min("course_end_time").alias("candidate_min_end_time"),
        F.max("course_end_time").alias("candidate_max_end_time"),
    )
)
course_name_time_match_audit = (
    missing_time.select("course_id", "enrollment_count")
    .join(course_catalog, "course_id", "left")
    .withColumn("normalized_course_name", normalize_name(F.col("course_name")))
    .join(dated_name_lookup, "normalized_course_name", "left")
    .withColumn(
        "name_time_match_status",
        F.when(F.col("course_name").isNull() | (F.length("normalized_course_name") == 0), F.lit("missing_catalog_name"))
        .when(F.col("dated_course_id_count").isNull(), F.lit("no_dated_name_match"))
        .when(F.col("dated_course_id_count") == 1, F.lit("one_dated_course_name_match"))
        .otherwise(F.lit("multiple_dated_course_name_matches")),
    )
    .select(
        "course_id",
        "course_name",
        "enrollment_count",
        "name_time_match_status",
        "dated_course_id_count",
        "candidate_min_end_time",
        "candidate_max_end_time",
    )
)

log_event(
    logger,
    "temporal_block_policy",
    policy="A=70%, B-G=5% by enrollment midpoint; course boundaries are indivisible",
    required_final_ordering=PROTOCOL["split"]["ordering_field"],
)
candidate_rows = log_dataframe(logger, "temporal_block_candidates", candidate_blocks, ("course_id", "temporal_block"))
summary_rows = log_dataframe(logger, "temporal_block_summary", block_summary, ("temporal_block",))
quantile_profile_rows = log_dataframe(logger, "temporal_quantile_profiles", quantile_profiles, ("population", "metric", "percentile"))
monthly_rows = log_dataframe(logger, "course_end_month_distribution", monthly_distribution, ("course_end_month",))
unified_candidate_rows = log_dataframe(
    logger, "unified_temporal_block_candidates", unified_temporal_block_candidates, ("course_id", "temporal_block")
)
unified_summary_rows = log_dataframe(
    logger, "unified_temporal_block_summary", unified_temporal_block_summary, ("temporal_block",)
)
unified_source_rows = log_dataframe(
    logger, "unified_temporal_block_source_summary", unified_temporal_block_source_summary, ("temporal_block", "timeline_source")
)
missing_rows = log_dataframe(logger, "courses_missing_end_time", missing_time, ("course_id",))
schedule_overview_rows = log_dataframe(logger, "course_schedule_overview", course_schedule_overview)
schedule_month_rows = log_dataframe(logger, "course_schedule_month_distribution", course_schedule_month_distribution, ("boundary", "course_month"))
alignment_rows = log_dataframe(logger, "course_schedule_array_alignment_audit", course_schedule_array_alignment_audit, ("course_id", "array_alignment_status"))
run_rows = log_dataframe(logger, "course_schedule_runs", course_schedule_runs, ("course_id", "season"))
active_month_rows = log_dataframe(
    logger, "course_run_active_month_distribution", course_run_active_month_distribution, ("calendar_month",)
)
start_month_rows = log_dataframe(
    logger, "course_run_start_month_distribution", course_run_start_month_distribution, ("start_month",)
)
month_span_rows = log_dataframe(
    logger, "course_run_month_span_distribution", course_run_month_span_distribution, ("months_covered",)
)
template_rows = log_dataframe(
    logger, "dominant_schedule_template_by_start_month", dominant_schedule_template_by_start_month, ("template_start_month",)
)
run_overview_rows = log_dataframe(logger, "course_run_duration_overview", course_run_duration_overview)
run_season_rows = log_dataframe(logger, "course_run_season_summary", course_run_season_summary, ("season",))
run_match_rows = log_dataframe(logger, "enrollment_course_run_match_summary", enrollment_course_run_match_summary, ("run_match_status",))
course_run_match_rows = log_dataframe(logger, "course_enrollment_run_match_summary", course_enrollment_run_match_summary, ("course_id",))
missing_schedule_profile_rows = log_dataframe(
    logger, "missing_schedule_enrollment_profile", missing_schedule_enrollment_profile, ("course_id",)
)
no_schedule_overview_rows = log_dataframe(
    logger, "no_schedule_enrollment_overview", no_schedule_enrollment_overview
)
no_schedule_year_month_rows = log_dataframe(
    logger,
    "no_schedule_enrollment_year_month_distribution",
    no_schedule_enrollment_year_month_distribution,
    ("enrollment_month",),
)
no_schedule_month_of_year_rows = log_dataframe(
    logger,
    "no_schedule_enrollment_month_of_year_distribution",
    no_schedule_enrollment_month_of_year_distribution,
    ("month_of_year",),
)
no_schedule_day_of_month_rows = log_dataframe(
    logger,
    "no_schedule_enrollment_day_of_month_distribution",
    no_schedule_enrollment_day_of_month_distribution,
    ("day_of_month",),
)
no_schedule_monthly_cohort_rows = log_dataframe(
    logger,
    "no_schedule_monthly_cohorts",
    no_schedule_monthly_cohorts,
    ("course_id", "enrollment_month"),
)
no_schedule_monthly_cohort_block_rows = log_dataframe(
    logger,
    "no_schedule_monthly_cohort_blocks",
    no_schedule_monthly_cohort_blocks,
    ("pseudo_offering_id", "temporal_block"),
)
no_schedule_strict_month_lookup_rows = log_dataframe(
    logger,
    "no_schedule_strict_month_lookup",
    no_schedule_strict_month_lookup,
    ("enrollment_month", "temporal_block"),
)
no_schedule_strict_month_cohort_block_rows = log_dataframe(
    logger,
    "no_schedule_strict_month_cohort_blocks",
    no_schedule_strict_month_cohort_blocks,
    ("pseudo_offering_id", "temporal_block"),
)
no_schedule_strict_month_block_summary_rows = log_dataframe(
    logger,
    "no_schedule_strict_month_block_summary",
    no_schedule_strict_month_block_summary,
    ("temporal_block",),
)
no_schedule_monthly_cohort_block_summary_rows = log_dataframe(
    logger,
    "no_schedule_monthly_cohort_block_summary",
    no_schedule_monthly_cohort_block_summary,
    ("temporal_block",),
)
month_bucket_rows = log_dataframe(
    logger, "missing_schedule_month_bucket_analysis", missing_schedule_month_bucket_analysis, ("course_id",)
)
month_bucket_summary_rows = log_dataframe(
    logger, "missing_schedule_month_bucket_summary", missing_schedule_month_bucket_summary, ("inference_status", "inferred_start_month")
)
enrollment_anchored_assignments_rows = log_dataframe(
    logger,
    "enrollment_anchored_pseudo_offering_assignments",
    enrollment_anchored_pseudo_offering_assignments,
    ("enrollment_id", "pseudo_offering_id"),
)
enrollment_anchored_summary_rows = log_dataframe(
    logger,
    "enrollment_anchored_pseudo_offering_summary",
    enrollment_anchored_pseudo_offering_summary,
    ("pseudo_offering_id",),
)
enrollment_anchored_activity_rows = log_dataframe(
    logger,
    "enrollment_anchored_activity_overview",
    enrollment_anchored_activity_overview,
)
enrollment_anchored_duration_rows = log_dataframe(
    logger,
    "enrollment_anchored_duration_source_summary",
    enrollment_anchored_duration_source_summary,
    ("duration_source", "duration_days"),
)
enrollment_time_rows = log_dataframe(logger, "course_enrollment_time_summary", course_enrollment_time_summary, ("course_id",))
enrollment_overview_rows = log_dataframe(logger, "enrollment_time_overview", enrollment_time_overview)
enrollment_month_rows = log_dataframe(logger, "course_enrollment_month_distribution", course_enrollment_month_distribution, ("boundary", "enrollment_month"))
name_match_rows = log_dataframe(
    logger,
    "course_name_time_match_audit",
    course_name_time_match_audit,
    ("course_id", "name_time_match_status"),
)

analysis_base = path_from_config(PROTOCOL, "analysis_base")
candidate_path = f"{analysis_base}/temporal_block_candidates/"
summary_path = f"{analysis_base}/temporal_block_summary/"
quantile_profile_path = f"{analysis_base}/temporal_quantile_profiles/"
monthly_path = f"{analysis_base}/course_end_month_distribution/"
unified_candidate_path = f"{analysis_base}/unified_temporal_block_candidates/"
unified_summary_path = f"{analysis_base}/unified_temporal_block_summary/"
unified_source_path = f"{analysis_base}/unified_temporal_block_source_summary/"
missing_path = f"{analysis_base}/courses_missing_end_time/"
schedule_overview_path = f"{analysis_base}/course_schedule_overview/"
schedule_month_path = f"{analysis_base}/course_schedule_month_distribution/"
alignment_path = f"{analysis_base}/course_schedule_array_alignment_audit/"
run_path = f"{analysis_base}/course_schedule_runs/"
active_month_path = f"{analysis_base}/course_run_active_month_distribution/"
start_month_path = f"{analysis_base}/course_run_start_month_distribution/"
month_span_path = f"{analysis_base}/course_run_month_span_distribution/"
template_path = f"{analysis_base}/dominant_schedule_template_by_start_month/"
run_overview_path = f"{analysis_base}/course_run_duration_overview/"
run_season_path = f"{analysis_base}/course_run_season_summary/"
run_match_path = f"{analysis_base}/enrollment_course_run_match_summary/"
course_run_match_path = f"{analysis_base}/course_enrollment_run_match_summary/"
missing_schedule_profile_path = f"{analysis_base}/missing_schedule_enrollment_profile/"
no_schedule_overview_path = f"{analysis_base}/no_schedule_enrollment_overview/"
no_schedule_year_month_path = f"{analysis_base}/no_schedule_enrollment_year_month_distribution/"
no_schedule_month_of_year_path = f"{analysis_base}/no_schedule_enrollment_month_of_year_distribution/"
no_schedule_day_of_month_path = f"{analysis_base}/no_schedule_enrollment_day_of_month_distribution/"
no_schedule_monthly_cohort_path = f"{analysis_base}/no_schedule_monthly_cohorts/"
no_schedule_monthly_cohort_block_path = f"{analysis_base}/no_schedule_monthly_cohort_blocks/"
no_schedule_monthly_cohort_block_summary_path = f"{analysis_base}/no_schedule_monthly_cohort_block_summary/"
no_schedule_strict_month_lookup_path = f"{analysis_base}/no_schedule_strict_month_lookup/"
no_schedule_strict_month_cohort_block_path = f"{analysis_base}/no_schedule_strict_month_cohort_blocks/"
no_schedule_strict_month_block_summary_path = f"{analysis_base}/no_schedule_strict_month_block_summary/"
month_bucket_path = f"{analysis_base}/missing_schedule_month_bucket_analysis/"
month_bucket_summary_path = f"{analysis_base}/missing_schedule_month_bucket_summary/"
enrollment_anchored_assignments_path = f"{analysis_base}/enrollment_anchored_pseudo_offering_assignments/"
enrollment_anchored_summary_path = f"{analysis_base}/enrollment_anchored_pseudo_offering_summary/"
enrollment_anchored_activity_path = f"{analysis_base}/enrollment_anchored_activity_overview/"
enrollment_anchored_duration_path = f"{analysis_base}/enrollment_anchored_duration_source_summary/"
name_match_path = f"{analysis_base}/course_name_time_match_audit/"
enrollment_time_path = f"{analysis_base}/course_enrollment_time_summary/"
enrollment_overview_path = f"{analysis_base}/enrollment_time_overview/"
enrollment_month_path = f"{analysis_base}/course_enrollment_month_distribution/"
write_parquet(candidate_blocks, candidate_path)
write_parquet(block_summary, summary_path)
write_parquet(quantile_profiles, quantile_profile_path)
write_parquet(monthly_distribution, monthly_path)
write_parquet(unified_temporal_block_candidates, unified_candidate_path)
write_parquet(unified_temporal_block_summary, unified_summary_path)
write_parquet(unified_temporal_block_source_summary, unified_source_path)
write_parquet(missing_time, missing_path)
write_parquet(course_schedule_overview, schedule_overview_path)
write_parquet(course_schedule_month_distribution, schedule_month_path)
write_parquet(course_schedule_array_alignment_audit, alignment_path)
write_parquet(course_schedule_runs, run_path)
write_parquet(course_run_active_month_distribution, active_month_path)
write_parquet(course_run_start_month_distribution, start_month_path)
write_parquet(course_run_month_span_distribution, month_span_path)
write_parquet(dominant_schedule_template_by_start_month, template_path)
write_parquet(course_run_duration_overview, run_overview_path)
write_parquet(course_run_season_summary, run_season_path)
write_parquet(enrollment_course_run_match_summary, run_match_path)
write_parquet(course_enrollment_run_match_summary, course_run_match_path)
write_parquet(missing_schedule_enrollment_profile, missing_schedule_profile_path)
write_parquet(no_schedule_enrollment_overview, no_schedule_overview_path)
write_parquet(no_schedule_enrollment_year_month_distribution, no_schedule_year_month_path)
write_parquet(no_schedule_enrollment_month_of_year_distribution, no_schedule_month_of_year_path)
write_parquet(no_schedule_enrollment_day_of_month_distribution, no_schedule_day_of_month_path)
write_parquet(no_schedule_monthly_cohorts, no_schedule_monthly_cohort_path)
write_parquet(no_schedule_monthly_cohort_blocks, no_schedule_monthly_cohort_block_path)
write_parquet(no_schedule_monthly_cohort_block_summary, no_schedule_monthly_cohort_block_summary_path)
write_parquet(no_schedule_strict_month_lookup, no_schedule_strict_month_lookup_path)
write_parquet(no_schedule_strict_month_cohort_blocks, no_schedule_strict_month_cohort_block_path)
write_parquet(no_schedule_strict_month_block_summary, no_schedule_strict_month_block_summary_path)
write_parquet(missing_schedule_month_bucket_analysis, month_bucket_path)
write_parquet(missing_schedule_month_bucket_summary, month_bucket_summary_path)
write_parquet(enrollment_anchored_pseudo_offering_assignments, enrollment_anchored_assignments_path)
write_parquet(enrollment_anchored_pseudo_offering_summary, enrollment_anchored_summary_path)
write_parquet(enrollment_anchored_activity_overview, enrollment_anchored_activity_path)
write_parquet(enrollment_anchored_duration_source_summary, enrollment_anchored_duration_path)
write_parquet(course_name_time_match_audit, name_match_path)
write_parquet(course_enrollment_time_summary, enrollment_time_path)
write_parquet(enrollment_time_overview, enrollment_overview_path)
write_parquet(course_enrollment_month_distribution, enrollment_month_path)
log_write(logger, "temporal_block_candidates", candidate_path, candidate_rows)
log_write(logger, "temporal_block_summary", summary_path, summary_rows)
log_write(logger, "temporal_quantile_profiles", quantile_profile_path, quantile_profile_rows)
log_write(logger, "course_end_month_distribution", monthly_path, monthly_rows)
log_write(logger, "unified_temporal_block_candidates", unified_candidate_path, unified_candidate_rows)
log_write(logger, "unified_temporal_block_summary", unified_summary_path, unified_summary_rows)
log_write(logger, "unified_temporal_block_source_summary", unified_source_path, unified_source_rows)
log_write(logger, "courses_missing_end_time", missing_path, missing_rows)
log_write(logger, "course_schedule_overview", schedule_overview_path, schedule_overview_rows)
log_write(logger, "course_schedule_month_distribution", schedule_month_path, schedule_month_rows)
log_write(logger, "course_schedule_array_alignment_audit", alignment_path, alignment_rows)
log_write(logger, "course_schedule_runs", run_path, run_rows)
log_write(logger, "course_run_active_month_distribution", active_month_path, active_month_rows)
log_write(logger, "course_run_start_month_distribution", start_month_path, start_month_rows)
log_write(logger, "course_run_month_span_distribution", month_span_path, month_span_rows)
log_write(logger, "dominant_schedule_template_by_start_month", template_path, template_rows)
log_write(logger, "course_run_duration_overview", run_overview_path, run_overview_rows)
log_write(logger, "course_run_season_summary", run_season_path, run_season_rows)
log_write(logger, "enrollment_course_run_match_summary", run_match_path, run_match_rows)
log_write(logger, "course_enrollment_run_match_summary", course_run_match_path, course_run_match_rows)
log_write(logger, "missing_schedule_enrollment_profile", missing_schedule_profile_path, missing_schedule_profile_rows)
log_write(logger, "no_schedule_enrollment_overview", no_schedule_overview_path, no_schedule_overview_rows)
log_write(
    logger,
    "no_schedule_enrollment_year_month_distribution",
    no_schedule_year_month_path,
    no_schedule_year_month_rows,
)
log_write(
    logger,
    "no_schedule_enrollment_month_of_year_distribution",
    no_schedule_month_of_year_path,
    no_schedule_month_of_year_rows,
)
log_write(
    logger,
    "no_schedule_enrollment_day_of_month_distribution",
    no_schedule_day_of_month_path,
    no_schedule_day_of_month_rows,
)
log_write(logger, "no_schedule_monthly_cohorts", no_schedule_monthly_cohort_path, no_schedule_monthly_cohort_rows)
log_write(
    logger,
    "no_schedule_monthly_cohort_blocks",
    no_schedule_monthly_cohort_block_path,
    no_schedule_monthly_cohort_block_rows,
)
log_write(
    logger,
    "no_schedule_strict_month_lookup",
    no_schedule_strict_month_lookup_path,
    no_schedule_strict_month_lookup_rows,
)
log_write(
    logger,
    "no_schedule_strict_month_cohort_blocks",
    no_schedule_strict_month_cohort_block_path,
    no_schedule_strict_month_cohort_block_rows,
)
log_write(
    logger,
    "no_schedule_strict_month_block_summary",
    no_schedule_strict_month_block_summary_path,
    no_schedule_strict_month_block_summary_rows,
)
log_write(
    logger,
    "no_schedule_monthly_cohort_block_summary",
    no_schedule_monthly_cohort_block_summary_path,
    no_schedule_monthly_cohort_block_summary_rows,
)
log_write(logger, "missing_schedule_month_bucket_analysis", month_bucket_path, month_bucket_rows)
log_write(logger, "missing_schedule_month_bucket_summary", month_bucket_summary_path, month_bucket_summary_rows)
log_write(logger, "enrollment_anchored_pseudo_offering_assignments", enrollment_anchored_assignments_path, enrollment_anchored_assignments_rows)
log_write(logger, "enrollment_anchored_pseudo_offering_summary", enrollment_anchored_summary_path, enrollment_anchored_summary_rows)
log_write(logger, "enrollment_anchored_activity_overview", enrollment_anchored_activity_path, enrollment_anchored_activity_rows)
log_write(logger, "enrollment_anchored_duration_source_summary", enrollment_anchored_duration_path, enrollment_anchored_duration_rows)
log_write(logger, "course_name_time_match_audit", name_match_path, name_match_rows)
log_write(logger, "course_enrollment_time_summary", enrollment_time_path, enrollment_time_rows)
log_write(logger, "enrollment_time_overview", enrollment_overview_path, enrollment_overview_rows)
log_write(logger, "course_enrollment_month_distribution", enrollment_month_path, enrollment_month_rows)
# Recurring offering audit: schedule years are metadata/crawl years, so shift
# month/day/duration templates to each learner's enrollment year (and prior year).
offering_templates = course_schedule_runs.select("course_id", "run_start_time", "run_duration_days").dropDuplicates()
year_offsets = spark.createDataFrame([(0,), (-1,)], ["start_year_offset"])
shifted_offering_candidates = (enrollments.select("enrollment_id", "user_id", "course_id", "enroll_time").filter(F.col("enroll_time").isNotNull())
    .join(offering_templates, "course_id").crossJoin(F.broadcast(year_offsets))
    .withColumn("offering_start_date", F.add_months(F.to_date("run_start_time"), (F.year("enroll_time") + F.col("start_year_offset") - F.year("run_start_time")) * 12))
    .withColumn("offering_end_date", F.date_add("offering_start_date", F.col("run_duration_days")))
    .filter((F.to_date("enroll_time") >= F.col("offering_start_date")) & (F.to_date("enroll_time") <= F.col("offering_end_date")))
    .withColumn("offering_id", F.concat_ws("__", "course_id", F.date_format("offering_start_date", "yyyy-MM-dd"))))
offering_counts = shifted_offering_candidates.groupBy("enrollment_id").agg(F.countDistinct("offering_id").alias("matching_offering_count"))
shifted_offering_match_summary = (enrollments.select("enrollment_id", "course_id").join(offering_counts, "enrollment_id", "left")
    .withColumn("matching_offering_count", F.coalesce("matching_offering_count", F.lit(0)))
    .withColumn("offering_match_status", F.when(F.col("matching_offering_count") == 0, "unmatched").when(F.col("matching_offering_count") == 1, "matched_one_offering").otherwise("matched_multiple_offerings"))
    .groupBy("offering_match_status").agg(F.count("*").alias("enrollment_count"), F.countDistinct("course_id").alias("course_count")))
offering_choice_window = Window.partitionBy("enrollment_id").orderBy(F.desc("offering_start_date"), F.asc("offering_id"))
shifted_offering_assignments = (shifted_offering_candidates.withColumn("offering_choice_rank", F.row_number().over(offering_choice_window))
    .filter(F.col("offering_choice_rank") == 1).drop("offering_choice_rank"))
# Fallback for courses without a usable own template: learn one frequent
# month/day/duration template per opening month from observed schedules.
global_template_counts = (course_schedule_runs.withColumn("start_month", F.month("run_start_time")).withColumn("start_day", F.dayofmonth("run_start_time"))
    .groupBy("start_month", "start_day", "run_duration_days").count())
global_template_window = Window.partitionBy("start_month").orderBy(F.desc("count"), F.desc("run_duration_days"))
global_templates = global_template_counts.withColumn("rank", F.row_number().over(global_template_window)).filter("rank = 1").drop("rank")
unmatched_enrollments = (enrollments.select("enrollment_id", "user_id", "course_id", "enroll_time").join(offering_counts, "enrollment_id", "left")
    .filter(F.coalesce("matching_offering_count", F.lit(0)) == 0).drop("matching_offering_count"))
global_template_candidates = (unmatched_enrollments.crossJoin(F.broadcast(global_templates)).crossJoin(F.broadcast(year_offsets))
    .withColumn("offering_start_date", F.make_date(F.year("enroll_time") + F.col("start_year_offset"), F.col("start_month"), F.col("start_day")))
    .withColumn("offering_end_date", F.date_add("offering_start_date", F.col("run_duration_days")))
    .filter((F.to_date("enroll_time") >= F.col("offering_start_date")) & (F.to_date("enroll_time") <= F.col("offering_end_date")))
    .withColumn("offering_id", F.concat_ws("__global__", F.date_format("offering_start_date", "yyyy-MM-dd")))
    .withColumn("timeline_source", F.lit("global_template_fallback")))
global_choice = Window.partitionBy("enrollment_id").orderBy(F.desc("offering_start_date"), F.asc("offering_id"))
global_template_assignments = global_template_candidates.withColumn("rank", F.row_number().over(global_choice)).filter("rank = 1").drop("rank")
global_template_summary = (unmatched_enrollments.select("enrollment_id", "course_id").join(global_template_assignments.select("enrollment_id", "offering_id"), "enrollment_id", "left")
    .withColumn("global_template_status", F.when(F.col("offering_id").isNull(), "unmatched").otherwise("assigned_global_template"))
    .groupBy("global_template_status").agg(F.count("*").alias("enrollment_count"), F.countDistinct("course_id").alias("course_count")))
write_parquet(shifted_offering_candidates, f"{analysis_base}/shifted_offering_candidates/")
write_parquet(shifted_offering_match_summary, f"{analysis_base}/shifted_offering_match_summary/")
write_parquet(shifted_offering_assignments, f"{analysis_base}/shifted_offering_assignments/")
write_parquet(global_template_assignments, f"{analysis_base}/global_template_offering_assignments/")
write_parquet(global_template_summary, f"{analysis_base}/global_template_offering_match_summary/")
log_run_finished(logger, run_started_at)
flush_json_log(logger, spark)
