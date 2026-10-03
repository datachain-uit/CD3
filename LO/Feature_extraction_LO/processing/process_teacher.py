from pyspark.sql import SparkSession, functions as F
from common.pipeline_logging import flush_json_log, get_logger, log_dataframe, log_run_context, log_write, write_parquet
from common.protocol_config import load_protocol_config

PROTOCOL = load_protocol_config()
RAW_BASE = PROTOCOL["raw_base"]
OUTPUT_BASE = PROTOCOL["output_base"]
RELATION_BASE = f"{RAW_BASE}/3"


spark = (
    SparkSession.builder.appName("process_teacher")
    .config("spark.driver.memory", "10g")
    .config("spark.executor.memory", "10g")
    .config("spark.sql.session.timeZone", "UTC")
    .getOrCreate()
)
logger = get_logger("process_teacher", f"{OUTPUT_BASE}/logs")
log_run_context(logger, spark, {"raw_base": RAW_BASE, "relation_base": RELATION_BASE, "output_base": OUTPUT_BASE})

teacher = spark.read.json(f"{RAW_BASE}/3/teacher.json")
log_dataframe(logger, "teacher_raw", teacher, ("id",))

# Exclude name/name_en: they are identifiers rather than generalizable model features.
teacher_profiles = (
    teacher.select(
        F.col("id").alias("teacher_id"),
        F.trim(F.col("job_title")).alias("job_title"),
        F.trim(F.col("org_name")).alias("org_name"),
        F.col("about").alias("about"),
    )
    .filter(F.col("teacher_id").isNotNull())
    .withColumn("has_bio", F.col("about").isNotNull() & (F.length(F.trim("about")) > 0))
    .withColumn("bio_length_chars", F.when(F.col("has_bio"), F.length("about")).otherwise(F.lit(0)))
    .drop("about")
    .dropDuplicates(["teacher_id"])
)
# Used only as an in-memory lookup to enrich the course-teacher relation.
log_dataframe(logger, "teacher_profiles_in_memory", teacher_profiles, ("teacher_id",))

# Tab-separated relation rows: course_id<TAB>teacher_id, e.g. C_375629<TAB>T_1.
course_teacher = (
    spark.read.option("sep", "\t")
    .option("header", False)
    .csv(f"{RELATION_BASE}/course-teacher.txt")
    .toDF("course_id", "teacher_id")
    .filter(F.col("course_id").isNotNull() & F.col("teacher_id").isNotNull())
    .dropDuplicates(["course_id", "teacher_id"])
)

active_courses = spark.read.parquet(f"{OUTPUT_BASE}/course_summary/").select("course_id")
course_teacher_clean = (
    course_teacher.join(active_courses, "course_id", "inner")
    .join(teacher_profiles, "teacher_id", "inner")
)
course_teacher_summary = course_teacher_clean.groupBy("course_id").agg(
    F.countDistinct("teacher_id").alias("teacher_count"),
    F.avg(F.col("has_bio").cast("double")).alias("teacher_bio_coverage"),
    F.avg("bio_length_chars").alias("teacher_avg_bio_length_chars"),
    F.countDistinct("org_name").alias("teacher_org_count"),
)

clean_rows = log_dataframe(logger, "course_teacher_clean", course_teacher_clean, ("course_id", "teacher_id"))
summary_rows = log_dataframe(logger, "course_teacher_summary", course_teacher_summary, ("course_id",))
clean_path = f"{OUTPUT_BASE}/course_teacher_clean/"
summary_path = f"{OUTPUT_BASE}/course_teacher_summary/"
write_parquet(course_teacher_clean, clean_path)
write_parquet(course_teacher_summary, summary_path)
log_write(logger, "course_teacher_clean", clean_path, clean_rows)
log_write(logger, "course_teacher_summary", summary_path, summary_rows)
flush_json_log(logger, spark)
