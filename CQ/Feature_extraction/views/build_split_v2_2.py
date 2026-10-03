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
from math import ceil, log2, sqrt

import pandas as pd
from pyspark.sql import SparkSession, Window, functions as F, types as T

PROJECT_ROOT = os.environ.get("PROJECT_ROOT") or str(Path(__file__).resolve().parents[1])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from common.pipeline_logging import (flush_json_log, get_logger, log_dataframe,
    log_event, log_run_context, log_run_finished, log_write, start_run_timer,
    write_parquet)
from common.protocol_config import load_protocol_config, path_from_config

SCRIPT_TASK = "CQ"
TASK = os.environ.get("SPLIT_V2_TASK", SCRIPT_TASK).upper()
if TASK != SCRIPT_TASK:
    raise ValueError(
        f"This is the CQ builder, but SPLIT_V2_TASK={TASK!r}. "
        "Run LO/Feature_extraction_LO/views/build_split_v2_2.py for LO."
    )
LABEL_COLUMN = os.environ.get("SPLIT_V2_LABEL_COLUMN", "CQ_label_final")
LABEL_VALUES = tuple(os.environ.get("SPLIT_V2_LABEL_VALUES", "warning,average,good").split(","))
RELEASE_KEY = os.environ.get("SPLIT_V2_RELEASE", "v2_2")
if RELEASE_KEY not in {"v2_2", "v2_3"}:
    raise ValueError("SPLIT_V2_RELEASE must be v2_2 or v2_3")
RELEASE_LABEL = RELEASE_KEY.replace("_", ".")
SPLIT_VERSION = f"offering_temporal_label_balanced_{RELEASE_KEY}"
SEED = int(os.environ.get("SPLIT_V2_SEED", "42"))
PAIRING_STRATEGY = os.environ.get("SPLIT_V2_PAIRING", "rarest_first" if TASK == "LO" else "balanced").lower()
if PAIRING_STRATEGY not in {"balanced", "rarest_first"}:
    raise ValueError("SPLIT_V2_PAIRING must be balanced or rarest_first")

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
# This revision changes audit semantics, not A--G assignment.  Never overwrite
# the immutable reference registry; promote this output only after review.
OUT = os.environ.get("SPLIT_V2_OUTPUT", f"{TASK_BASE}/{TASK}/hybrid/split_registry_{RELEASE_KEY}_overlap_audit_v1").rstrip("/")
SHARED_BOUNDARIES_SOURCE = os.environ.get("SPLIT_V2_SHARED_BOUNDARIES_SOURCE", "").rstrip("/")
if TASK == "CQ" and SHARED_BOUNDARIES_SOURCE:
    raise ValueError("CQ is the V2.2 calendar anchor; do not set SPLIT_V2_SHARED_BOUNDARIES_SOURCE for CQ.")
if TASK == "LO" and not SHARED_BOUNDARIES_SOURCE:
    raise ValueError("LO V2.2 requires SPLIT_V2_SHARED_BOUNDARIES_SOURCE from the CQ V2.2 registry.")
if TASK == "LO" and PAIRING_STRATEGY != "rarest_first":
    raise ValueError("LO V2.2 requires SPLIT_V2_PAIRING=rarest_first.")

# V2.2 is the QA22 baseline in tempo_fix: label-end order plus non-empty
# validation/test.  V2.3 is the explicit successor that adds a registered
# two-tier size gate; both retain the same temporal split semantics.
QA_SIZE_POLICY = os.environ.get(
    "SPLIT_V2_QA_SIZE_POLICY", "reference_nonempty" if RELEASE_KEY == "v2_2" else "two_tier"
)
if QA_SIZE_POLICY not in {"reference_nonempty", "two_tier"}:
    raise ValueError("SPLIT_V2_QA_SIZE_POLICY must be reference_nonempty or two_tier")
MIN_EVAL_ARM_SHARE = float(os.environ.get(
    "SPLIT_V2_MIN_EVAL_ARM_SHARE", "0.0" if QA_SIZE_POLICY == "reference_nonempty" else "0.025"
))
MIN_EVAL_ARM_ROWS = int(os.environ.get("SPLIT_V2_MIN_EVAL_ARM_ROWS", "1" if QA_SIZE_POLICY == "reference_nonempty" else "50000"))
MIN_EVAL_TOTAL_SHARE = float(os.environ.get("SPLIT_V2_MIN_EVAL_TOTAL_SHARE", "0.0" if QA_SIZE_POLICY == "reference_nonempty" else "0.05"))
if QA_SIZE_POLICY == "two_tier" and not (0.0 < MIN_EVAL_ARM_SHARE <= MIN_EVAL_TOTAL_SHARE <= 1.0):
    raise ValueError("Require 0 < SPLIT_V2_MIN_EVAL_ARM_SHARE <= SPLIT_V2_MIN_EVAL_TOTAL_SHARE <= 1.")
if QA_SIZE_POLICY == "two_tier" and MIN_EVAL_ARM_ROWS < 1:
    raise ValueError("SPLIT_V2_MIN_EVAL_ARM_ROWS must be positive.")

spark = (SparkSession.builder.appName(f"build_cq_split_{RELEASE_KEY}")
    .config("spark.sql.session.timeZone", "UTC").getOrCreate())
logger = get_logger(f"build_{TASK.lower()}_split_{RELEASE_KEY}", path_from_config(P, "logs"))
started = start_run_timer()
log_run_context(logger, spark, {
    "split_version": SPLIT_VERSION, "seed": SEED, "output": OUT,
    "assignment_rule": "A_60pct_or_shared_calendar__three_future_temporal_slices__pairwise_label_balance",
    "pairing_strategy": PAIRING_STRATEGY,
    "shared_boundaries_source": SHARED_BOUNDARIES_SOURCE or None,
    "qa22": f"label_end_order__{QA_SIZE_POLICY}__overlap_report_only",
    "overlap_contract": "offering_start_and_p1_cutoff_are_separate_metrics",
    "release": RELEASE_LABEL,
    "min_eval_arm_share": MIN_EVAL_ARM_SHARE,
    "min_eval_arm_rows": MIN_EVAL_ARM_ROWS,
    "min_eval_total_share": MIN_EVAL_TOTAL_SHARE,
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
shared_boundaries = None
if SHARED_BOUNDARIES_SOURCE:
    shared = spark.read.parquet(SHARED_BOUNDARIES_SOURCE).limit(2).collect()
    if len(shared) != 1:
        raise ValueError("SPLIT_V2_SHARED_BOUNDARIES_SOURCE must contain exactly one boundary row.")
    shared_boundaries = shared[0].asDict(recursive=True)
    for name in ("a_boundary", "slice_1_boundary", "slice_2_boundary"):
        if shared_boundaries.get(name) is None:
            raise ValueError(f"Shared boundary artifact is missing {name}.")

if shared_boundaries:
    early = offerings.filter(F.col("offering_end_date") <= F.lit(shared_boundaries["a_boundary"])).withColumn("rolling_block", F.lit("A"))
    later = offerings.filter(F.col("offering_end_date") > F.lit(shared_boundaries["a_boundary"]))
else:
    early = offerings.filter(F.col("cum_n") <= F.lit(float(total_n) * 0.60)).withColumn("rolling_block", F.lit("A"))
    later = offerings.filter(F.col("cum_n") > F.lit(float(total_n) * 0.60))
later_order = Window.orderBy("offering_end_date", "timeline_source", "offering_id").rowsBetween(Window.unboundedPreceding, Window.currentRow)
later_total = later.agg(F.sum("n").alias("n")).first()["n"]
if not later_total:
    raise ValueError("Split V2 has no future offerings after chronological A block.")
if shared_boundaries:
    later = later.withColumn(
        "temporal_slice",
        F.when(F.col("offering_end_date") <= F.lit(shared_boundaries["slice_1_boundary"]), F.lit(1))
         .when(F.col("offering_end_date") <= F.lit(shared_boundaries["slice_2_boundary"]), F.lit(2))
         .otherwise(F.lit(3)),
    )
else:
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
                    if PAIRING_STRATEGY == "rarest_first" and metric != "n":
                        # Let the rarest class in a slice dominate the pairing
                        # objective while retaining offering-size balance.
                        weight *= float(totals["n"]) / max(float(totals[metric]), 1.0)
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
offerings = offerings.withColumn("duration_days", F.datediff("offering_end_date", "offering_start_date")).withColumn(
    "long_offering_flag", (F.col("duration_days") > F.lit(270)).cast("int"))

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
min_eval_arm_enrollments = max(ceil(float(total_n) * MIN_EVAL_ARM_SHARE), MIN_EVAL_ARM_ROWS)
min_eval_total_enrollments = ceil(float(total_n) * MIN_EVAL_TOTAL_SHARE)

qa_rows = base.join(manifest_final.select(*unit_cols, "window_id", "split"), unit_cols, "inner")
qa_rows = qa_rows.join(train_bounds.select("window_id", "tau_w"), "window_id", "inner")
for phase, ratio in (("P1", 0.25), ("P2", 0.50), ("P3", 0.75), ("P4", 0.90)):
    qa_rows = qa_rows.withColumn(
        f"cutoff_time_{phase}", F.timestamp_seconds(
            F.unix_timestamp("enroll_time") +
            (F.unix_timestamp("offering_end_date") - F.unix_timestamp("enroll_time")) * F.lit(ratio)))
    qa_rows = qa_rows.withColumn(f"temporal_strict_{phase}",
        (F.col(f"cutoff_time_{phase}") >= F.col("tau_w")).cast("int"))
overlap_by_split = (qa_rows.filter(F.col("split") != "train")
    .groupBy("window_id", "split")
    .agg(F.countDistinct("enrollment_id").alias("evaluation_enrollment_count"),
         F.sum(F.when(F.col("cutoff_time_P1") < F.col("tau_w"), 1).otherwise(0)).alias("p1_cutoff_overlap_enrollment_count"),
         F.sum(F.when(F.col("offering_start_date") < F.to_date(F.col("tau_w")), 1).otherwise(0)).alias("offering_start_overlap_enrollment_count"))
    .withColumn("p1_cutoff_overlap_share", F.try_divide("p1_cutoff_overlap_enrollment_count", "evaluation_enrollment_count"))
    .withColumn("offering_start_overlap_share", F.try_divide("offering_start_overlap_enrollment_count", "evaluation_enrollment_count"))
    .withColumn("p1_cutoff_overlap_definition", F.lit("cutoff_time_P1_lt_tau_w"))
    .withColumn("offering_start_overlap_definition", F.lit("offering_start_date_lt_date(tau_w)"))
    .withColumn("overlap_metric_version", F.lit("overlap_contract_v1")))
# These two overlap measures answer different questions and must never be
# substituted for one another.  P1 cutoff overlap is the complement of P1
# strictness; offering-start overlap is the independent cohort-level measure.
test_overlap = (overlap_by_split.filter(F.col("split") == "test")
    .select("window_id",
            F.col("evaluation_enrollment_count").alias("test_enrollment_count"),
            F.col("p1_cutoff_overlap_enrollment_count").alias("test_p1_cutoff_overlap_enrollment_count"),
            F.col("p1_cutoff_overlap_share").alias("test_p1_cutoff_overlap_share"),
            F.col("offering_start_overlap_enrollment_count").alias("test_offering_start_overlap_enrollment_count"),
            F.col("offering_start_overlap_share").alias("test_offering_start_overlap_share")))
validation_overlap = (overlap_by_split.filter(F.col("split") == "validation")
    .select("window_id",
            F.col("evaluation_enrollment_count").alias("validation_enrollment_count"),
            F.col("p1_cutoff_overlap_enrollment_count").alias("validation_p1_cutoff_overlap_enrollment_count"),
            F.col("p1_cutoff_overlap_share").alias("validation_p1_cutoff_overlap_share"),
            F.col("offering_start_overlap_enrollment_count").alias("validation_offering_start_overlap_enrollment_count"),
            F.col("offering_start_overlap_share").alias("validation_offering_start_overlap_share")))
qa22 = (train_bounds.join(evaluation_bounds, "window_id", "inner").join(test_bounds, "window_id", "inner")
    .join(eval_sizes, "window_id", "inner").join(test_overlap, "window_id", "inner")
    .join(validation_overlap, "window_id", "inner")
    # Backward-compatible contract field: cohort overlap, not P1-cutoff overlap.
    .withColumn("ev_train_overlap_share", F.col("test_offering_start_overlap_share"))
    .withColumn("end_order_ok", F.col("tau_w") <= F.col("min_evaluation_end_utc"))
    .withColumn("n_enrollments_evaluation",
                F.col("n_enrollments_validation") + F.col("n_enrollments_test"))
    .withColumn("eval_arm_size_ok", (F.col("n_enrollments_validation") >= F.lit(min_eval_arm_enrollments)) &
                (F.col("n_enrollments_test") >= F.lit(min_eval_arm_enrollments)))
    .withColumn("eval_total_size_ok", F.lit(True) if QA_SIZE_POLICY == "reference_nonempty" else F.col("n_enrollments_evaluation") >= F.lit(min_eval_total_enrollments))
    .withColumn("eval_size_ok", F.col("eval_arm_size_ok") & F.col("eval_total_size_ok"))
    .withColumn("qa22_ok", F.col("end_order_ok") & F.col("eval_size_ok"))
    .withColumn("days_train_end_to_test_start", F.datediff("window_test_start_utc", "tau_w"))
    .withColumn("embargo_gap_days", F.lit(0).cast("int"))
    .withColumn("train_history_span_days", F.datediff("tau_w", "train_start_utc"))
    .withColumn("min_eval_arm_enrollments", F.lit(min_eval_arm_enrollments))
    .withColumn("min_eval_total_enrollments", F.lit(min_eval_total_enrollments)))
qa22_failure_rows = (qa22.filter(~F.col("qa22_ok"))
    .select("window_id", "tau_w", "min_evaluation_end_utc", "window_test_start_utc",
            "n_enrollments_validation", "n_enrollments_test", "n_enrollments_evaluation",
            "min_eval_arm_enrollments", "min_eval_total_enrollments",
            "end_order_ok", "eval_arm_size_ok", "eval_total_size_ok", "eval_size_ok", "qa22_ok")
    .orderBy("window_id"))
if qa22_failure_rows.limit(1).count():
    # Keep the failed registry audit observable in driver logs.  This prevents
    # operators from changing a threshold blindly when the actual issue is
    # temporal ordering (or vice versa).
    failures = [row.asDict(recursive=True) for row in qa22_failure_rows.collect()]
    raise RuntimeError(
        f"QA22 {RELEASE_LABEL} failed: require label-end order and adequate validation "
        f"and test in every window. failures={failures}"
    )

split_registry = (qa22.withColumn("n_purged", F.lit(0).cast("long"))
    .withColumn("purged_enrollment_count", F.lit(0).cast("long"))
    .withColumn("purged_enrollment_share", F.lit(0.0))
    .withColumn("purge_gt_half_eval", F.lit(False))
    .withColumn("purge_mode", F.lit("NONE"))
    .withColumn("scenario", F.lit("hybrid"))
    .withColumn("split_version", F.lit(RELEASE_LABEL))
    .withColumn("task", F.lit(TASK))
    .withColumn("pairing_strategy", F.lit(PAIRING_STRATEGY))
    .withColumn("calendar_anchor_task", F.lit("CQ" if not SHARED_BOUNDARIES_SOURCE else "CQ"))
    .withColumn("registry_revision", F.lit("overlap_audit_v1"))
    .withColumn("overlap_metric_version", F.lit("overlap_contract_v1"))
    .withColumn("ev_train_overlap_definition", F.lit("test_offering_start_date_lt_date(tau_w)")))

split_label_distribution = (base.join(manifest_final.select(*unit_cols, "window_id", "split"), unit_cols, "inner")
    .groupBy("window_id", "split", F.col(LABEL_COLUMN).alias("label"))
    .agg(F.countDistinct("enrollment_id").alias("label_enrollment_count"))
    .join(split_counts, ["window_id", "split"], "inner")
    .withColumn("label_ratio", F.try_divide("label_enrollment_count", "enrollment_count"))
    .withColumn("task", F.lit(TASK)).withColumn("scenario", F.lit("hybrid")).withColumn("split_version", F.lit(RELEASE_LABEL)))

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
        F.max("duration_days").alias("duration_days_max"),
        F.sum(F.when(F.col("long_offering_flag") == 1, 1).otherwise(0)).alias("n_long_offerings"),
        F.sum(F.when(F.col("long_offering_flag") == 1, F.col("n")).otherwise(0)).alias("long_offering_enrollment_count"),
        F.avg(F.when(F.col("offering_end_date") == F.lit(last_end), 1.0).otherwise(0.0)).alias("end_at_dataset_last_date_share")))
duration_summary = duration_summary.withColumn("long_offering_enrollment_share", F.try_divide("long_offering_enrollment_count", "enrollment_count"))
block_audit = offerings.groupBy("rolling_block").agg(F.count("*").alias("offering_count"), F.sum("n").alias("enrollment_count"), F.sum("long_offering_flag").alias("n_long_offerings"), F.sum(F.when(F.col("long_offering_flag") == 1, F.col("n")).otherwise(0)).alias("long_offering_enrollment_count"), *[F.sum(f"n_{v}").alias(f"{v}_count") for v in LABEL_VALUES])

calendar_boundaries = (offerings.agg(
    F.max(F.when(F.col("rolling_block") == "A", F.col("offering_end_date"))).alias("a_boundary"),
    F.max(F.when(F.col("rolling_block").isin("B", "C"), F.col("offering_end_date"))).alias("slice_1_boundary"),
    F.max(F.when(F.col("rolling_block").isin("D", "E"), F.col("offering_end_date"))).alias("slice_2_boundary"),
    F.max("offering_end_date").alias("slice_3_boundary"),
).withColumn("calendar_anchor_task", F.lit("CQ")).withColumn("split_version", F.lit(RELEASE_LABEL)))

strict_share = None
for phase in ("P1", "P2", "P3", "P4"):
    frame = (qa_rows.filter(F.col("split") != "train").groupBy("window_id", "split")
        .agg(F.avg(F.col(f"temporal_strict_{phase}")).alias("temporal_strict_share"), F.countDistinct("enrollment_id").alias("evaluation_enrollment_count"))
        .withColumn("phase_id", F.lit(phase))
        .withColumn("p_cutoff_overlap_share", F.lit(1.0) - F.col("temporal_strict_share"))
        .withColumn("p_cutoff_overlap_definition", F.lit("cutoff_time_phase_lt_tau_w")))
    strict_share = frame if strict_share is None else strict_share.unionByName(frame)
strict_share = strict_share.withColumn("task", F.lit(TASK)).withColumn("scenario", F.lit("hybrid")).withColumn("split_version", F.lit(RELEASE_LABEL))
write_parquet(manifest_final.withColumn("split_rule_version", F.lit(SPLIT_VERSION)).withColumn("seed", F.lit(SEED)), f"{OUT}/manifest/")
write_parquet(qa22, f"{OUT}/qa22_{RELEASE_KEY}/")
write_parquet(block_audit, f"{OUT}/block_label_audit/")
write_parquet(split_registry, f"{OUT}/split_registry/")
write_parquet(split_counts.withColumn("task", F.lit(TASK)).withColumn("scenario", F.lit("hybrid")).withColumn("split_version", F.lit(RELEASE_LABEL)), f"{OUT}/split_actual_ratios/")
write_parquet(split_label_distribution, f"{OUT}/split_label_distribution/")
write_parquet(qa_rows.select(
    "enrollment_id", "offering_id", "timeline_source", "offering_start_date", "offering_end_date",
    "enroll_time", "window_id", "split", "tau_w",
    *[f"cutoff_time_P{i}" for i in range(1, 5)],
    *[f"temporal_strict_P{i}" for i in range(1, 5)],
    (F.col("cutoff_time_P1") < F.col("tau_w")).cast("int").alias("p1_cutoff_overlap_flag"),
    (F.col("offering_start_date") < F.to_date(F.col("tau_w"))).cast("int").alias("offering_start_overlap_flag"),
    F.lit("overlap_contract_v1").alias("overlap_metric_version")), f"{OUT}/temporal_strict_context/")
write_parquet(strict_share, f"{OUT}/temporal_strict_share/")
write_parquet(overlap_by_split.withColumn("task", F.lit(TASK)).withColumn("scenario", F.lit("hybrid")).withColumn("split_version", F.lit(RELEASE_LABEL)), f"{OUT}/temporal_overlap_audit_v1/")
write_parquet(temporal_profile, f"{OUT}/temporal_profile_monthly/")
write_parquet(duration_summary, f"{OUT}/duration_summary/")
write_parquet(calendar_boundaries, f"{OUT}/calendar_boundaries/")
log_write(logger, f"split_manifest_{RELEASE_KEY}", f"{OUT}/manifest/", log_dataframe(logger, f"split_{RELEASE_KEY}_manifest", manifest_final, ("window_id", "split")))
log_event(logger, "qa22_complete", purge_mode="NONE", qa22_rule="label_end_order_and_eval_size")
log_run_finished(logger, started)
flush_json_log(logger, spark)
