"""Full component and label audit for CQ V1."""
import os, sys
from pathlib import Path
PROJECT_ROOT = os.environ.get("PROJECT_ROOT") or str(Path(__file__).resolve().parents[1])
if PROJECT_ROOT not in sys.path: sys.path.insert(0, PROJECT_ROOT)
from pyspark.sql import SparkSession, Window, functions as F
from common.protocol_config import load_protocol_config, path_from_config

P = load_protocol_config(); BASE = P["output_base"]
spark = SparkSession.builder.appName("audit_cq_labels_v1").config("spark.sql.session.timeZone", "UTC").getOrCreate()
source = spark.read.parquet(path_from_config(P, "cq_labels") + "/").filter(F.col("CQ_label_final").isNotNull())
long = source.selectExpr(
    "CQ_label_final as label",
    "stack(5, 'COELO_final', COELO_final, 'AFELO_final', AFELO_final, 'ACELO_final', ACELO_final, 'CQ_distance_euclidean_final', CQ_distance_euclidean_final, 'CQ_proximity_final', CQ_proximity_final) as (metric, value)"
).filter(F.col("value").isNotNull())

def summarize(frame, groups):
    return frame.groupBy(*groups).agg(
        F.count("value").alias("sample_count"), F.avg("value").alias("mean"), F.stddev("value").alias("stddev"),
        F.min("value").alias("min"), F.expr("percentile_approx(value, 0.25, 10000)").alias("p25"),
        F.expr("percentile_approx(value, 0.50, 10000)").alias("p50"), F.expr("percentile_approx(value, 0.75, 10000)").alias("p75"),
        F.max("value").alias("max"), F.sum(F.when(F.col("value") == 0, 1).otherwise(0)).alias("zero_count")
    ).withColumn("zero_ratio", F.col("zero_count") / F.col("sample_count"))

overall = summarize(long, ["metric"])
by_label = summarize(long, ["metric", "label"])
labels = source.groupBy("CQ_label_final").agg(F.count("*").alias("enrollment_count")).withColumn("enrollment_ratio", F.col("enrollment_count") / F.sum("enrollment_count").over(Window.partitionBy()))
out = f"{BASE}/labels/cq_labels_v1_audit_full/"
for name, df in (("component_summary", overall), ("component_by_label", by_label), ("label_distribution", labels)):
    df.write.mode("overwrite").parquet(f"{out}{name}/")
