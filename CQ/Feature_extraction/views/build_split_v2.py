"""Spark-native chronological, label-balanced Split V2.1 builder for CQ.

V2 fixes the V1 leakage risk: A is an early whole-offering block; the
remaining chronology is split into three consecutive slices, and only the
two blocks *within each slice* are label-balanced.  Validation/test offerings
are retained: overlap is measured and reported, never purged.

Outputs are intentionally separate from V1 and the superseded strict-purge
V2 artifacts. A view materializer must explicitly opt in to this manifest.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from hashlib import sha256
from math import log2, sqrt

import pandas as pd
from pyspark.sql import SparkSession, Window, functions as F, types as T

PROJECT_ROOT = os.environ.get("PROJECT_ROOT") or str(Path(__file__).resolve().parents[1])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from common.pipeline_logging import (flush_json_log, get_logger, log_dataframe,
    log_event, log_run_context, log_run_finished, log_write, start_run_timer,
    write_parquet)
from common.protocol_config import load_protocol_config, path_from_config

TASK = os.environ.get("SPLIT_V2_TASK", "CQ").upper()
LABEL_COLUMN = os.environ.get("SPLIT_V2_LABEL_COLUMN", "CQ_label_final")
LABEL_VALUES = tuple(os.environ.get("SPLIT_V2_LABEL_VALUES", "warning,average,good").split(","))
SPLIT_VERSION = "offering_temporal_label_balanced_v2_1"
SEED = int(os.environ.get("SPLIT_V2_SEED", "42"))

P = load_protocol_config()
BASE = P["output_base"].rstrip("/")
ANALYSIS_BASE = path_from_config(P, "analysis_base")
TASK_BASE = path_from_config(P, "task_feature_base")
_default_label_key = "cq_labels" if TASK == "CQ" else "lo_labels"
LABEL_SOURCE = os.environ.get("SPLIT_V2_LABEL_SOURCE", path_from_config(P, _default_label_key)).rstrip("/")
WINDOWS_SOURCE = os.environ.get(
    "SPLIT_V2_WINDOWS_SOURCE", f"{BASE}/features/scenarios/hybrid/enrollment_windows"
).rstrip("/")
# Registry is immutable input to materialization.  Do not share the
# ``split_manifest_v2_1`` directory produced by the view materializer.
OUT = os.environ.get("SPLIT_V2_OUTPUT", f"{TASK_BASE}/{TASK}/hybrid/split_registry_v2_1").rstrip("/")

spark = (SparkSession.builder.appName("build_cq_split_v2_1")
    .config("spark.sql.session.timeZone", "UTC").getOrCreate())
logger = get_logger(f"build_{TASK.lower()}_split_v2_1", path_from_config(P, "logs"))
started = start_run_timer()
log_run_context(logger, spark, {
    "split_version": SPLIT_VERSION, "seed": SEED, "output": OUT,
    "assignment_rule": "A_60pct_chronological__three_future_temporal_slices__pairwise_label_balance",
    "qa22": "label_end_order__nonempty_evaluation__overlap_report_only",
})


def _schedule_assignments():
    """Return the canonical schedule assignment for each enrollment.

    The three sources match the hybrid feature builder's precedence exactly.
    They provide real offering start/end dates needed by QA22; never replace
    start dates with first enrollment timestamps.
    """
    timeline = (spark.read.parquet(f"{ANALYSIS_BASE}/shifted_offering_assignments/")
        .select("enrollment_id", F.col("offering_id").cast("string").alias("schedule_offering_id"),
                "offering_start_date", "offering_end_date")
        .withColumn("timeline_source", F.lit("course_specific_timeline")))
    anchored = (spark.read.parquet(f"{ANALYSIS_BASE}/enrollment_anchored_pseudo_offering_assignments/")
        .select("enrollment_id", F.col("pseudo_offering_id").cast("string").alias("schedule_offering_id"),
                F.col("pseudo_start_date").alias("offering_start_date"),
                F.col("pseudo_end_date").alias("offering_end_date"))
        .withColumn("timeline_source", F.lit("enrollment_anchored_proxy")))
    global_fallback = (spark.read.parquet(f"{ANALYSIS_BASE}/global_template_offering_assignments/")
        .select("enrollment_id", F.col("offering_id").cast("string").alias("schedule_offering_id"),
                "offering_start_date", "offering_end_date")
        .withColumn("timeline_source", F.lit("global_template_fallback"))
        .join(anchored.select("enrollment_id"), "enrollment_id", "left_anti"))
    # ``enrollment_windows`` already carries the canonical timeline_source.
    # Keep this source under a private name solely for a consistency audit so
    # that the later enrollment_id join cannot create ambiguous columns.
    return (timeline.unionByName(anchored).unionByName(global_fallback)
        .dropDuplicates(["enrollment_id"])
        .withColumnRenamed("timeline_source", "_schedule_timeline_source"))


labels = spark.read.parquet(LABEL_SOURCE)
if TASK == "CQ":
    labels = labels.filter(F.col("cq_exclusion_reason").isNull() & F.col(LABEL_COLUMN).isNotNull())
else:
    labels = labels.filter(F.col("proxy_exclusion_reason").isNull() & F.col(LABEL_COLUMN).isNotNull())
labels = labels.select("enrollment_id", LABEL_COLUMN)
windows = (spark.read.parquet(WINDOWS_SOURCE)
    .select("enrollment_id", F.col("offering_id").cast("string").alias("window_offering_id"),
            F.to_timestamp("enroll_time").alias("enroll_time"), "timeline_source")
    .dropDuplicates(["enrollment_id"]))
base = (labels.join(windows, "enrollment_id", "inner")
    .join(_schedule_assignments(), "enrollment_id", "inner")
    .withColumn("offering_id", F.coalesce("window_offering_id", "schedule_offering_id"))
    .drop("window_offering_id", "schedule_offering_id", "_schedule_timeline_source"))
if base.filter(F.col("offering_id").isNull() | F.col("offering_start_date").isNull() |
               F.col("offering_end_date").isNull() | F.col("enroll_time").isNull()).limit(1).count():
    raise ValueError("Split V2 requires offering_id, official offering_start/end_date, and enroll_time for every row.")

unit_cols = ["offering_id", "timeline_source"]
offerings = base.groupBy(*unit_cols).agg(
    F.min("offering_start_date").alias("offering_start_date"),
    F.min("offering_end_date").alias("offering_end_date"),
    F.countDistinct("enrollment_id").alias("n"),
    *[F.sum(F.when(F.col(LABEL_COLUMN) == value, 1).otherwise(0)).alias(f"n_{value}") for value in LABEL_VALUES],
)
chronological = Window.orderBy("offering_end_date", "timeline_source", "offering_id").rowsBetween(Window.unboundedPreceding, Window.currentRow)
total_n = offerings.agg(F.sum("n").alias("n")).first()["n"]
if not total_n:
    raise ValueError("Split V2 has no eligible offerings.")
offerings = offerings.withColumn("cum_n", F.sum("n").over(chronological))
early = offerings.filter(F.col("cum_n") <= F.lit(float(total_n) * 0.60)).withColumn("rolling_block", F.lit("A"))
later = offerings.filter(F.col("cum_n") > F.lit(float(total_n) * 0.60))
later_order = Window.orderBy("offering_end_date", "timeline_source", "offering_id").rowsBetween(Window.unboundedPreceding, Window.currentRow)
later_total = later.agg(F.sum("n").alias("n")).first()["n"]
if not later_total:
    raise ValueError("Split V2 has no future offerings after chronological A block.")
later = (later.withColumn("later_cum_n", F.sum("n").over(later_order))
    .withColumn("temporal_slice", F.least(F.lit(3), F.ceil(F.col("later_cum_n") / F.lit(float(later_total) / 3.0)).cast("int"))))

schema = T.StructType([
    T.StructField("offering_id", T.StringType(), False),
    T.StructField("timeline_source", T.StringType(), False),
    T.StructField("rolling_block", T.StringType(), False),
])

def allocate_pair(pdf: pd.DataFrame) -> pd.DataFrame:
    """Deterministic greedy two-way allocation within one chronological slice."""
    pdf = pdf.copy()
    pair = {1: ("B", "C"), 2: ("D", "E"), 3: ("F", "G")}[int(pdf["temporal_slice"].iloc[0])]
    metrics = ["n", *[f"n_{label}" for label in LABEL_VALUES]]
    totals = {m: float(pdf[m].sum()) for m in metrics}
    state = {block: {m: 0.0 for m in metrics} for block in pair}

    def key(row):
        raw = f"{SEED}|{row['offering_id']}|{row['timeline_source']}".encode("utf-8")
        return sha256(raw).hexdigest()
    # Dict access is intentional: LO has a legitimate ``I/D`` label, whose
    # derived column ``n_I/D`` is not a valid Python namedtuple attribute.
    ordered = sorted(pdf.to_dict("records"), key=lambda r: (-float(r["n"]), key(r)))
    assignments = []
    for row in ordered:
        def score(block):
            total = 0.0
            for candidate in pair:
                for metric in metrics:
                    observed = state[candidate][metric] + (float(row[metric]) if candidate == block else 0.0)
                    target = totals[metric] / 2.0
                    weight = 2.0 if metric != "n" else 1.0
                    total += weight * ((observed - target) / max(target, 1.0)) ** 2
            return total
        selected = min(pair, key=lambda b: (score(b), b))
        for metric in metrics:
            state[selected][metric] += float(row[metric])
        assignments.append((row["offering_id"], row["timeline_source"], selected))
    return pd.DataFrame(assignments, columns=["offering_id", "timeline_source", "rolling_block"])

later_allocated = later.groupBy("temporal_slice").applyInPandas(allocate_pair, schema=schema)
offerings = early.select(*unit_cols, "offering_start_date", "offering_end_date", "n", *[f"n_{v}" for v in LABEL_VALUES], "rolling_block").unionByName(
    later.join(later_allocated, unit_cols, "inner").select(*unit_cols, "offering_start_date", "offering_end_date", "n", *[f"n_{v}" for v in LABEL_VALUES], "rolling_block"))

windows_spec = (("W1", ("A",), "B", "C"), ("W2", ("A", "B", "C"), "D", "E"), ("W3", ("A", "B", "C", "D", "E"), "F", "G"))
manifest = None
for window_id, train_blocks, validation_block, test_block in windows_spec:
    frame = (offerings.filter(F.col("rolling_block").isin(*train_blocks, validation_block, test_block))
        .withColumn("window_id", F.lit(window_id))
        .withColumn("split", F.when(F.col("rolling_block").isin(*train_blocks), "train")
            .when(F.col("rolling_block") == validation_block, "validation").otherwise("test")))
    manifest = frame if manifest is None else manifest.unionByName(frame)

# Split V2.1 primary protocol: no purge.  Label-end ordering is the
# acceptance condition; P1 overlap is reported and later used for STRICT vs
# OVERLAP prediction subgroups.
manifest_final = manifest
split_counts = manifest_final.groupBy("window_id", "split").agg(F.sum("n").alias("enrollment_count"))
split_window_totals = split_counts.groupBy("window_id").agg(F.sum("enrollment_count").alias("window_enrollment_count"))
split_counts = split_counts.join(split_window_totals, "window_id", "inner").withColumn(
    "split_enrollment_share", F.try_divide("enrollment_count", "window_enrollment_count"))
train_bounds = (manifest_final.filter(F.col("split") == "train").groupBy("window_id")
    .agg(F.to_timestamp(F.min("offering_start_date")).alias("train_start_utc"),
         F.to_timestamp(F.max("offering_end_date")).alias("tau_w")))
evaluation_bounds = (manifest_final.filter(F.col("split") != "train").groupBy("window_id")
    .agg(F.to_timestamp(F.min("offering_end_date")).alias("min_evaluation_end_utc")))
test_bounds = (manifest_final.filter(F.col("split") == "test").groupBy("window_id")
    .agg(F.to_timestamp(F.min("offering_start_date")).alias("window_test_start_utc"),
         F.to_timestamp(F.max("offering_end_date")).alias("window_test_end_utc")))
eval_sizes = manifest_final.groupBy("window_id").agg(
    F.sum(F.when(F.col("split") == "validation", F.col("n")).otherwise(0)).alias("n_enrollments_validation"),
    F.sum(F.when(F.col("split") == "test", F.col("n")).otherwise(0)).alias("n_enrollments_test"))
min_eval_enrollments = int(float(total_n) * float(os.environ.get("SPLIT_V2_MIN_EVAL_SHARE", "0.05")))

qa_rows = base.join(manifest_final.select(*unit_cols, "window_id", "split"), unit_cols, "inner")
qa_rows = qa_rows.join(train_bounds.select("window_id", "tau_w"), "window_id", "inner")
for phase, ratio in (("P1", 0.25), ("P2", 0.50), ("P3", 0.75), ("P4", 0.90)):
    qa_rows = qa_rows.withColumn(
        f"cutoff_time_{phase}", F.timestamp_seconds(
            F.unix_timestamp("enroll_time") +
            (F.unix_timestamp("offering_end_date") - F.unix_timestamp("enroll_time")) * F.lit(ratio)))
    qa_rows = qa_rows.withColumn(f"temporal_strict_{phase}",
        (F.col(f"cutoff_time_{phase}") >= F.col("tau_w")).cast("int"))
evaluation_overlap = (qa_rows.filter(F.col("split") != "train").groupBy("window_id").agg(
    F.countDistinct("enrollment_id").alias("evaluation_enrollment_count"),
    F.sum(F.when(F.col("cutoff_time_P1") < F.col("tau_w"), 1).otherwise(0)).alias("ev_train_overlap_enrollment_count"))
    .withColumn("ev_train_overlap_share", F.try_divide("ev_train_overlap_enrollment_count", "evaluation_enrollment_count")))
qa22 = (train_bounds.join(evaluation_bounds, "window_id", "inner").join(test_bounds, "window_id", "inner")
    .join(eval_sizes, "window_id", "inner").join(evaluation_overlap, "window_id", "inner")
    .withColumn("end_order_ok", F.col("tau_w") <= F.col("min_evaluation_end_utc"))
    .withColumn("eval_size_ok", (F.col("n_enrollments_validation") >= F.lit(min_eval_enrollments)) &
                (F.col("n_enrollments_test") >= F.lit(min_eval_enrollments)))
    .withColumn("qa22_ok", F.col("end_order_ok") & F.col("eval_size_ok"))
    .withColumn("days_train_end_to_test_start", F.datediff("window_test_start_utc", "tau_w"))
    .withColumn("embargo_gap_days", F.lit(0).cast("int"))
    .withColumn("train_history_span_days", F.datediff("tau_w", "train_start_utc"))
    .withColumn("min_eval_enrollments", F.lit(min_eval_enrollments)))
if qa22.filter(~F.col("qa22_ok")).limit(1).count():
    raise RuntimeError("QA22 V2.1 failed: require label-end order and non-empty/adequate validation and test in every window.")

split_registry = (qa22.withColumn("n_purged", F.lit(0).cast("long"))
    .withColumn("purged_enrollment_count", F.lit(0).cast("long"))
    .withColumn("purged_enrollment_share", F.lit(0.0))
    .withColumn("purge_gt_half_eval", F.lit(False))
    .withColumn("purge_mode", F.lit("NONE"))
    .withColumn("scenario", F.lit("hybrid"))
    .withColumn("split_version", F.lit("v2.1"))
    .withColumn("task", F.lit(TASK)))

split_label_distribution = (base.join(manifest_final.select(*unit_cols, "window_id", "split"), unit_cols, "inner")
    .groupBy("window_id", "split", F.col(LABEL_COLUMN).alias("label"))
    .agg(F.countDistinct("enrollment_id").alias("label_enrollment_count"))
    .join(split_counts, ["window_id", "split"], "inner")
    .withColumn("label_ratio", F.try_divide("label_enrollment_count", "enrollment_count"))
    .withColumn("task", F.lit(TASK)).withColumn("scenario", F.lit("hybrid")).withColumn("split_version", F.lit("v2.1")))

def _jsd(previous, current):
    midpoint = [(p + q) / 2.0 for p, q in zip(previous, current)]
    kl = lambda values, mean: sum(v * log2(v / m) for v, m in zip(values, mean) if v > 0 and m > 0)
    return sqrt(0.5 * kl(previous, midpoint) + 0.5 * kl(current, midpoint))

test_rows = split_label_distribution.filter(F.col("split") == "test").select("window_id", "label", "label_ratio").collect()
by_window = {}
for row in test_rows:
    by_window.setdefault(row["window_id"], {})[row["label"]] = float(row["label_ratio"])
drift_rows, previous = [], None
for window_id in ("W1", "W2", "W3"):
    current = [by_window.get(window_id, {}).get(label, 0.0) for label in LABEL_VALUES]
    drift_rows.append((window_id, None if previous is None else float(_jsd(previous, current))))
    previous = current
label_drift = spark.createDataFrame(drift_rows, "window_id string, label_drift_window_prev_jsd double")
split_registry = split_registry.join(label_drift, "window_id", "left")

# Temporal profile and duration audit are required before a boundary is locked.
monthly_active = (offerings.withColumn("month", F.explode(F.sequence(
    F.date_trunc("month", "offering_start_date"), F.date_trunc("month", "offering_end_date"), F.expr("INTERVAL 1 MONTH"))))
    .groupBy("month").agg(F.count("*").alias("active_offering_count"), F.sum("n").alias("active_enrollment_mass")))
monthly_starts = offerings.groupBy(F.date_trunc("month", "offering_start_date").alias("month")).agg(F.count("*").alias("offering_starts"))
monthly_ends = offerings.groupBy(F.date_trunc("month", "offering_end_date").alias("month")).agg(F.count("*").alias("offering_ends"))
temporal_profile = monthly_active.join(monthly_starts, "month", "full").join(monthly_ends, "month", "full").fillna(0)
last_end = offerings.agg(F.max("offering_end_date").alias("last_end")).first()["last_end"]
duration_summary = (offerings.withColumn("duration_days", F.datediff("offering_end_date", "offering_start_date"))
    .groupBy("timeline_source").agg(F.count("*").alias("offering_count"), F.sum("n").alias("enrollment_count"),
        F.expr("percentile_approx(duration_days, 0.5)").alias("duration_days_p50"),
        F.expr("percentile_approx(duration_days, 0.9)").alias("duration_days_p90"),
        F.avg(F.when(F.col("offering_end_date") == F.lit(last_end), 1.0).otherwise(0.0)).alias("end_at_dataset_last_date_share")))
block_audit = offerings.groupBy("rolling_block").agg(F.count("*").alias("offering_count"), F.sum("n").alias("enrollment_count"), *[F.sum(f"n_{v}").alias(f"{v}_count") for v in LABEL_VALUES])
write_parquet(manifest_final.withColumn("split_rule_version", F.lit(SPLIT_VERSION)).withColumn("seed", F.lit(SEED)), f"{OUT}/manifest/")
write_parquet(qa22, f"{OUT}/qa22_v2_1/")
write_parquet(block_audit, f"{OUT}/block_label_audit/")
write_parquet(split_registry, f"{OUT}/split_registry/")
write_parquet(split_counts.withColumn("task", F.lit(TASK)).withColumn("scenario", F.lit("hybrid")).withColumn("split_version", F.lit("v2.1")), f"{OUT}/split_actual_ratios/")
write_parquet(split_label_distribution, f"{OUT}/split_label_distribution/")
write_parquet(qa_rows.select("enrollment_id", "window_id", "split", "tau_w", *[f"cutoff_time_P{i}" for i in range(1, 5)], *[f"temporal_strict_P{i}" for i in range(1, 5)]), f"{OUT}/temporal_strict_context/")
write_parquet(temporal_profile, f"{OUT}/temporal_profile_monthly/")
write_parquet(duration_summary, f"{OUT}/duration_summary/")
log_write(logger, "split_manifest_v2_1", f"{OUT}/manifest/", log_dataframe(logger, "split_v2_1_manifest", manifest_final, ("window_id", "split")))
log_event(logger, "qa22_complete", purge_mode="NONE", qa22_rule="label_end_order_and_eval_size")
log_run_finished(logger, started)
flush_json_log(logger, spark)
