"""Audit temporal coverage of the accepted activity-derived LO label.

This audit deliberately does not claim to measure independently observed
final-grade coverage. It measures whether the activity-derived label is
eligible and how its I/D, G and E support changes across A, T1, T2 and T3.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from datetime import datetime, timezone

from pyspark.sql import SparkSession, Window, functions as F

PROJECT_ROOT = os.environ.get("PROJECT_ROOT") or str(Path(__file__).resolve().parents[1])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

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
BASE = P["output_base"].rstrip("/")
ANALYSIS_BASE = path_from_config(P, "analysis_base").rstrip("/")
TASK_BASE = path_from_config(P, "task_feature_base").rstrip("/")
LABEL_SOURCE = os.environ.get("LO_PROXY_LABEL_SOURCE", path_from_config(P, "lo_labels")).rstrip("/")
WINDOWS_SOURCE = os.environ.get(
    "LO_PROXY_WINDOWS_SOURCE", f"{BASE}/features/scenarios/hybrid/enrollment_windows"
).rstrip("/")
MANIFEST_SOURCE = os.environ.get("LO_PROXY_MANIFEST_SOURCE", "").rstrip("/")
if not MANIFEST_SOURCE:
    raise ValueError("Set LO_PROXY_MANIFEST_SOURCE to the frozen release manifest path.")
OUT = os.environ.get(
    "LO_PROXY_AUDIT_OUTPUT", f"{TASK_BASE}/LO/hybrid/label_coverage_audit_proxy_v1"
).rstrip("/")
SEED = int(os.environ.get("LO_PROXY_AUDIT_SEED", "42"))

AUDIT_RELEASE = os.environ.get("LO_PROXY_AUDIT_RELEASE", "v3_1_scored_signal_excluded")
spark = (SparkSession.builder.appName(f"audit_lo_final_score_label_coverage_{AUDIT_RELEASE}")
    .config("spark.sql.session.timeZone", "UTC").getOrCreate())
logger = get_logger(f"audit_lo_final_score_label_coverage_{AUDIT_RELEASE}", path_from_config(P, "logs"))
started = start_run_timer()
log_run_context(logger, spark, {
    "label_contract": "LO_activity_derived_final_score__not_independently_observed_final_grade",
    "label_source": LABEL_SOURCE,
    "manifest_source": MANIFEST_SOURCE,
    "output": OUT,
    "seed": SEED,
})


def schedule_assignments():
    """Canonical hybrid offering/timeline assignment, matching the split builder."""
    course = (spark.read.parquet(f"{ANALYSIS_BASE}/shifted_offering_assignments/")
        .select("enrollment_id", F.col("offering_id").cast("string").alias("schedule_offering_id"),
                "offering_start_date", "offering_end_date")
        .withColumn("schedule_timeline_source", F.lit("course_specific_timeline")))
    anchored = (spark.read.parquet(f"{ANALYSIS_BASE}/enrollment_anchored_pseudo_offering_assignments/")
        .select("enrollment_id", F.col("pseudo_offering_id").cast("string").alias("schedule_offering_id"),
                F.col("pseudo_start_date").alias("offering_start_date"),
                F.col("pseudo_end_date").alias("offering_end_date"))
        .withColumn("schedule_timeline_source", F.lit("enrollment_anchored_proxy")))
    fallback = (spark.read.parquet(f"{ANALYSIS_BASE}/global_template_offering_assignments/")
        .select("enrollment_id", F.col("offering_id").cast("string").alias("schedule_offering_id"),
                "offering_start_date", "offering_end_date")
        .withColumn("schedule_timeline_source", F.lit("global_template_fallback"))
        .join(anchored.select("enrollment_id"), "enrollment_id", "left_anti"))
    return course.unionByName(anchored).unionByName(fallback).dropDuplicates(["enrollment_id"])


labels_raw = spark.read.parquet(LABEL_SOURCE)
required = {"enrollment_id", "proxy_exclusion_reason", "LO_performance_label_3", "performance_score"}
missing = sorted(required.difference(labels_raw.columns))
if missing:
    raise ValueError(f"LO proxy-label source is missing required columns: {missing}")

def optional(name: str, dtype: str = "string"):
    return F.col(name) if name in labels_raw.columns else F.lit(None).cast(dtype).alias(name)

labels = labels_raw.select(
    "enrollment_id", "proxy_exclusion_reason", "LO_performance_label_3", "performance_score",
    optional("label_availability_source"), optional("label_schedule_assignment_status"),
    optional("label_rule_version"), optional("label_threshold_set"), optional("decision"), optional("proxy_reason"),
)
windows = (spark.read.parquet(WINDOWS_SOURCE)
    .select("enrollment_id", F.col("offering_id").cast("string").alias("window_offering_id"),
            F.col("timeline_source").alias("window_timeline_source"))
    .dropDuplicates(["enrollment_id"]))
schedules = schedule_assignments()

unit_cols = ["offering_id", "timeline_source"]
manifest = spark.read.parquet(MANIFEST_SOURCE)
required_manifest = set(unit_cols + ["rolling_block"])
missing_manifest = sorted(required_manifest.difference(manifest.columns))
if missing_manifest:
    raise ValueError(f"Split manifest is missing required columns: {missing_manifest}")
block_lookup = manifest.select(*unit_cols, "rolling_block").dropDuplicates(unit_cols + ["rolling_block"])
if block_lookup.groupBy(*unit_cols).count().filter(F.col("count") != 1).limit(1).count():
    raise ValueError("Each offering/timeline unit must map to exactly one rolling block.")

base = (labels.join(windows, "enrollment_id", "left")
    .join(schedules, "enrollment_id", "left")
    .withColumn("offering_id", F.coalesce("window_offering_id", "schedule_offering_id"))
    .withColumn("timeline_source", F.coalesce("window_timeline_source", "schedule_timeline_source"))
    .drop("window_offering_id", "window_timeline_source", "schedule_offering_id", "schedule_timeline_source")
    .join(block_lookup, unit_cols, "left")
    .withColumn("temporal_slice",
        F.when(F.col("rolling_block") == "A", "A")
         .when(F.col("rolling_block").isin("B", "C"), "T1")
         .when(F.col("rolling_block").isin("D", "E"), "T2")
         .when(F.col("rolling_block").isin("F", "G"), "T3")
         .otherwise("UNASSIGNED"))
    .withColumn("proxy_eligible_flag", (
        F.col("proxy_exclusion_reason").isNull() & F.col("LO_performance_label_3").isNotNull()
    ).cast("int"))
    .withColumn("performance_score_observed_flag", F.col("performance_score").isNotNull().cast("int"))
    .withColumn("e_flag", (F.col("LO_performance_label_3") == "E").cast("int"))
    .withColumn("g_flag", (F.col("LO_performance_label_3") == "G").cast("int"))
    .withColumn("id_flag", (F.col("LO_performance_label_3") == "I/D").cast("int")))

coverage = (base.groupBy("temporal_slice", "rolling_block", "timeline_source", "label_availability_source",
                         "label_schedule_assignment_status")
    .agg(F.countDistinct("enrollment_id").alias("n_enrollments_total"),
         F.sum("proxy_eligible_flag").alias("n_proxy_eligible"),
         F.sum("performance_score_observed_flag").alias("n_performance_score_observed"),
         F.sum("e_flag").alias("n_E"), F.sum("g_flag").alias("n_G"), F.sum("id_flag").alias("n_I_D"),
         F.countDistinct(F.when(F.col("offering_id").isNotNull(), F.struct("offering_id", "timeline_source"))).alias("n_offerings"))
    .withColumn("proxy_eligible_share", F.try_divide("n_proxy_eligible", "n_enrollments_total"))
    .withColumn("performance_score_observed_share", F.try_divide("n_performance_score_observed", "n_enrollments_total"))
    .withColumn("E_share_all", F.try_divide("n_E", "n_enrollments_total"))
    .withColumn("G_share_all", F.try_divide("n_G", "n_enrollments_total"))
    .withColumn("E_share_eligible", F.try_divide("n_E", "n_proxy_eligible"))
    .withColumn("G_share_eligible", F.try_divide("n_G", "n_proxy_eligible")))

exclusions = (base.groupBy("temporal_slice", "rolling_block", "timeline_source",
                           F.coalesce(F.col("proxy_exclusion_reason"), F.lit("ELIGIBLE")).alias("proxy_status"))
    .agg(F.countDistinct("enrollment_id").alias("n_enrollments")))
exclusion_totals = exclusions.groupBy("temporal_slice", "rolling_block", "timeline_source").agg(
    F.sum("n_enrollments").alias("slice_timeline_enrollment_count"))
exclusions = exclusions.join(exclusion_totals, ["temporal_slice", "rolling_block", "timeline_source"], "inner").withColumn(
    "share_within_slice_timeline", F.try_divide("n_enrollments", "slice_timeline_enrollment_count"))

offering_rare = (base.filter(F.col("temporal_slice") != "UNASSIGNED")
    .groupBy("temporal_slice", "rolling_block", "timeline_source", "offering_id")
    .agg(F.countDistinct("enrollment_id").alias("n_enrollments"), F.sum("proxy_eligible_flag").alias("n_proxy_eligible"),
         F.sum("e_flag").alias("n_E"), F.sum("g_flag").alias("n_G"))
    .withColumn("rare_count", F.col("n_E") + F.col("n_G"))
    .withColumn("has_E", (F.col("n_E") > 0).cast("int"))
    .withColumn("has_G", (F.col("n_G") > 0).cast("int")))

rare_summary = (offering_rare.groupBy("temporal_slice", "timeline_source")
    .agg(F.count("offering_id").alias("n_offerings"), F.sum("n_enrollments").alias("n_enrollments"),
         F.sum("n_E").alias("n_E"), F.sum("n_G").alias("n_G"), F.sum("has_E").alias("n_offerings_with_E"),
         F.sum("has_G").alias("n_offerings_with_G"), F.max("n_E").alias("max_E_in_one_offering"),
         F.max("n_G").alias("max_G_in_one_offering"), F.max("rare_count").alias("max_EG_in_one_offering"))
    .withColumn("top_E_offering_share", F.try_divide("max_E_in_one_offering", "n_E"))
    .withColumn("top_G_offering_share", F.try_divide("max_G_in_one_offering", "n_G")))

assignment_qa = (base.groupBy("temporal_slice")
    .agg(F.countDistinct("enrollment_id").alias("n_enrollments"),
         F.countDistinct(F.when(F.col("offering_id").isNotNull(), F.struct("offering_id", "timeline_source"))).alias("n_offering_units")))

audit_manifest = spark.createDataFrame([{
    "audit_id": f"lo_final_score_label_coverage_{AUDIT_RELEASE}",
    "audit_release": AUDIT_RELEASE,
    "generated_at_utc": datetime.now(timezone.utc),
    "label_contract": "LO_activity_derived_final_score__not_independently_observed_final_grade",
    "label_source": LABEL_SOURCE,
    "parent_manifest_source": MANIFEST_SOURCE,
    "seed": SEED,
    "slice_definition": "A=A; T1=B_C; T2=D_E; T3=F_G; UNASSIGNED=not_in_parent_manifest",
}])

for name, frame, keys in (
    ("slice_timeline_summary", coverage, ("temporal_slice", "timeline_source")),
    ("slice_exclusion_reason_summary", exclusions, ("temporal_slice", "timeline_source", "proxy_status")),
    ("offering_rare_label_summary", offering_rare, ("temporal_slice", "timeline_source", "offering_id")),
    ("rare_label_concentration", rare_summary, ("temporal_slice", "timeline_source")),
    ("assignment_coverage_qa", assignment_qa, ("temporal_slice",)),
    ("audit_manifest", audit_manifest, ("audit_id",)),
):
    path = f"{OUT}/{name}/"
    write_parquet(frame, path)
    log_write(logger, name, path, log_dataframe(logger, name, frame, keys))

log_event(
    logger,
    "lo_final_score_label_coverage_audit_complete",
    label_contract="activity_derived_final_score__not_independently_observed_final_grade",
)
log_run_finished(logger, started)
flush_json_log(logger, spark)
