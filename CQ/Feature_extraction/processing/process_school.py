from pyspark.sql import SparkSession, functions as F
from common.pipeline_logging import flush_json_log, get_logger, log_dataframe, log_run_context, log_write, write_parquet
from common.protocol_config import load_protocol_config

PROTOCOL = load_protocol_config()
RAW_BASE = PROTOCOL["raw_base"]
OUTPUT_BASE = PROTOCOL["output_base"]
RELATION_BASE = f"{RAW_BASE}/3"


spark = (
    SparkSession.builder.appName("process_school")
    .config("spark.driver.memory", "10g")
    .config("spark.executor.memory", "10g")
    .config("spark.sql.session.timeZone", "UTC")
    .getOrCreate()
)
logger = get_logger("process_school", f"{OUTPUT_BASE}/logs")
log_run_context(logger, spark, {"raw_base": RAW_BASE, "relation_base": RELATION_BASE, "output_base": OUTPUT_BASE})

school = spark.read.json(f"{RAW_BASE}/3/school.json")
log_dataframe(logger, "school_raw", school, ("id",))

# Exclude name/name_en/sign: they primarily identify a particular institution.
school_profiles = (
    school.select(
        F.col("id").alias("school_id"),
        F.col("about").alias("about"),
        F.col("motto").alias("motto"),
    )
    .filter(F.col("school_id").isNotNull())
    .withColumn("has_bio", F.col("about").isNotNull() & (F.length(F.trim("about")) > 0))
    .withColumn("bio_length_chars", F.when(F.col("has_bio"), F.length("about")).otherwise(F.lit(0)))
    .withColumn("has_motto", F.col("motto").isNotNull() & (F.length(F.trim("motto")) > 0))
    .withColumn("motto_length_chars", F.when(F.col("has_motto"), F.length("motto")).otherwise(F.lit(0)))
    .drop("about", "motto")
    .dropDuplicates(["school_id"])
)
# Used only as an in-memory lookup to enrich the course-school relation.
log_dataframe(logger, "school_profiles_in_memory", school_profiles, ("school_id",))

# Tab-separated relation rows: course_id<TAB>school_id, e.g. C_375629<TAB>S_1.
course_school = (
    spark.read.option("sep", "\t")
    .option("header", False)
    .csv(f"{RELATION_BASE}/course-school.txt")
    .toDF("course_id", "school_id")
    .filter(F.col("course_id").isNotNull() & F.col("school_id").isNotNull())
    .dropDuplicates(["course_id", "school_id"])
)

active_courses = spark.read.parquet(f"{OUTPUT_BASE}/course_summary/").select("course_id")
course_school_clean = (
    course_school.join(active_courses, "course_id", "inner")
    .join(school_profiles, "school_id", "inner")
)
course_school_summary = course_school_clean.groupBy("course_id").agg(
    F.countDistinct("school_id").alias("school_count"),
    F.avg(F.col("has_bio").cast("double")).alias("school_bio_coverage"),
    F.avg("bio_length_chars").alias("school_avg_bio_length_chars"),
    F.avg(F.col("has_motto").cast("double")).alias("school_motto_coverage"),
    F.avg("motto_length_chars").alias("school_avg_motto_length_chars"),
)

clean_rows = log_dataframe(logger, "course_school_clean", course_school_clean, ("course_id", "school_id"))
summary_rows = log_dataframe(logger, "course_school_summary", course_school_summary, ("course_id",))
clean_path = f"{OUTPUT_BASE}/course_school_clean/"
summary_path = f"{OUTPUT_BASE}/course_school_summary/"
write_parquet(course_school_clean, clean_path)
write_parquet(course_school_summary, summary_path)
log_write(logger, "course_school_clean", clean_path, clean_rows)
log_write(logger, "course_school_summary", summary_path, summary_rows)
flush_json_log(logger, spark)
