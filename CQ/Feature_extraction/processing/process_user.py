from pyspark.sql import SparkSession, functions as F
from common.pipeline_logging import flush_json_log, get_logger, log_dataframe, log_run_context, log_write, write_parquet
from common.protocol_config import load_protocol_config

PROTOCOL = load_protocol_config()
RAW_BASE = PROTOCOL["raw_base"]
OUTPUT_BASE = PROTOCOL["output_base"]


spark = (
    SparkSession.builder.appName("process_user")
    .config("spark.driver.memory", "10g")
    .config("spark.executor.memory", "10g")
    .config("spark.sql.session.timeZone", "UTC")
    .getOrCreate()
)
logger = get_logger("process_user", f"{OUTPUT_BASE}/logs")
log_run_context(logger, spark, {"raw_base": RAW_BASE, "output_base": OUTPUT_BASE})

user = spark.read.json(f"{RAW_BASE}/3/user.json")
log_dataframe(logger, "user_raw", user, ("id",))

# One row per learner-course enrollment. This is the common input for all event processors.
enrollments = (
    user.withColumn("zipped", F.explode(F.arrays_zip("course_order", "enroll_time")))
    .select(
        F.col("id").alias("user_id"),
        F.col("gender").alias("gender"),
        F.col("year_of_birth").alias("year_of_birth"),
        F.concat(F.lit("C_"), F.col("zipped.course_order")).alias("course_id"),
        F.to_timestamp(F.col("zipped.enroll_time")).alias("enroll_time"),
    )
    .filter(F.col("user_id").isNotNull() & F.col("course_id").isNotNull() & F.col("enroll_time").isNotNull())
    .withColumn(
        "enrollment_id",
        F.concat("user_id", F.lit("::"), "course_id", F.lit("::"), F.col("enroll_time").cast("string")),
    )
    .dropDuplicates(["enrollment_id"])
)

enrollment_rows = log_dataframe(logger, "enrollments_clean", enrollments, ("enrollment_id", "user_id", "course_id"))
enrollment_path = f"{OUTPUT_BASE}/enrollments/"
write_parquet(enrollments, enrollment_path)
log_write(logger, "enrollments", enrollment_path, enrollment_rows)
flush_json_log(logger, spark)
