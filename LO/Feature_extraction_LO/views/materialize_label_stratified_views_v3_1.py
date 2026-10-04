"""Materialize LO V3.1 views from the locked V3.1 split registry.

The V3.1 label contract excludes courses with no scored signal and must be
paired with the corresponding V3.1 scored-signal-excluded split manifest.
"""
from hashlib import sha256
import os
import sys
from pathlib import Path

PROJECT_ROOT = os.environ.get("PROJECT_ROOT") or str(Path(__file__).resolve().parents[1])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from pyspark.sql import SparkSession, Window, functions as F

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
BASE = P["output_base"]
# The frozen V1 source is the scenarios release.  An explicit environment
# override remains available for a later immutable release.
FEATURE_BASE = os.environ.get("VIEW_FEATURE_BASE", f"{BASE.rstrip('/')}/features/scenarios").rstrip("/")
TASK_BASE = os.environ.get("VIEW_TASK_BASE", path_from_config(P, "task_feature_base")).rstrip("/")
LABEL_SOURCE = path_from_config(P, "lo_labels") + "/"
# A materialized V3.1 view must never silently inherit a V2.2 manifest. The
# explicit override is retained only for the identically named V3.1 release.
EXPECTED_SPLIT_RULE_VERSION = "offering_temporal_label_balanced_v3_1_scored_signal_excluded"
EXPECTED_MANIFEST_RELEASE = "split_registry_v3_1_scored_signal_excluded_overlap_audit_v1"
EXTERNAL_MANIFEST_SOURCE = os.environ.get(
    "VIEW_SPLIT_MANIFEST_SOURCE",
    f"{TASK_BASE}/LO/hybrid/{EXPECTED_MANIFEST_RELEASE}/manifest",
).rstrip("/")
if EXPECTED_MANIFEST_RELEASE not in EXTERNAL_MANIFEST_SOURCE:
    raise ValueError(
        "LO V3.1 requires the scored-signal-excluded V3.1 manifest; "
        f"got {EXTERNAL_MANIFEST_SOURCE!r}."
    )
VIEW_RELEASE = "v3_1_scored_signal_excluded"
OUT = f"{TASK_BASE}/LO/hybrid/phase_views_{VIEW_RELEASE}/"
MANIFEST_OUT = f"{TASK_BASE}/LO/hybrid/split_manifest_{VIEW_RELEASE}/"
TEST_PREFIX_OUT = f"{TASK_BASE}/LO/hybrid/test_prefix_views_{VIEW_RELEASE}/"
print(
    "[materialize_lo] "
    f"release={VIEW_RELEASE}; manifest_input={EXTERNAL_MANIFEST_SOURCE or 'built_in_v1'}; "
    f"manifest_output={MANIFEST_OUT}; phase_views_output={OUT}; "
    f"test_prefix_output={TEST_PREFIX_OUT}"
)
WINDOWS = (
    ("W1", ("A",), "B", "C"),
    ("W2", ("A", "B", "C"), "D", "E"),
    ("W3", ("A", "B", "C", "D", "E"), "F", "G"),
)
BLOCK_CUTOFFS = (
    ("A", 0.60), ("B", 0.60 + 1 / 15), ("C", 0.60 + 2 / 15),
    ("D", 0.60 + 3 / 15), ("E", 0.60 + 4 / 15),
    ("F", 0.60 + 5 / 15), ("G", 1.0),
)


spark = (SparkSession.builder
    .appName("materialize_lo_label_stratified_v3_1")
    .config("spark.sql.session.timeZone", "UTC")
    .getOrCreate())
logger = get_logger("materialize_lo_label_stratified_v3_1", path_from_config(P, "logs"))
started = start_run_timer()
log_run_context(logger, spark, {
    "label_source": LABEL_SOURCE,
    "output": OUT,
    "manifest_output": MANIFEST_OUT,
    "test_prefix_output": TEST_PREFIX_OUT,
    "view_release": VIEW_RELEASE,
    "external_manifest_source": EXTERNAL_MANIFEST_SOURCE or None,
    "split": "method_5__A_chronological_60__B_to_G_greedy_label_count_stratified",
    "label_filter": "all eligible LO operational-label rows; no downsampling",
})

labels = (spark.read.parquet(LABEL_SOURCE)
    .filter(F.col("proxy_exclusion_reason").isNull() & F.col("LO_performance_label_3").isNotNull())
    .select("enrollment_id", "LO_performance_label_3", "LO_performance_label_5",
            "performance_score", "label_availability_time", "label_availability_source",
            "label_rule_version", "label_threshold_set", "decision", "proxy_reason"))
features = spark.read.parquet(os.environ.get(
    "VIEW_FEATURE_SOURCE", f"{FEATURE_BASE}/hybrid/cumulative_phase_features_v1/"
).rstrip("/") + "/")
windows = (spark.read.parquet(f"{FEATURE_BASE}/hybrid/enrollment_windows/")
    .select("enrollment_id", F.col("offering_id").cast("string").alias("_source_offering_id"),
            F.col("window_end_date").alias("_offering_end_date"))
    .dropDuplicates(["enrollment_id"]))
base = features.join(labels, "enrollment_id", "inner").join(windows, "enrollment_id", "left")
if "offering_id" in features.columns:
    base = base.withColumn("offering_id", F.coalesce(
        F.col("offering_id").cast("string"), F.col("_source_offering_id")))
else:
    base = base.withColumn("offering_id", F.col("_source_offering_id"))
base = base.drop("_source_offering_id")
if base.filter(F.col("offering_id").isNull() | F.col("_offering_end_date").isNull()).limit(1).count():
    raise ValueError("Each eligible enrollment must have offering_id and window_end_date.")

unit_columns = ["offering_id", "timeline_source"]
offerings = (base
    .groupBy(*unit_columns)
    .agg(F.min("_offering_end_date").alias("offering_end_date"),
         F.countDistinct("enrollment_id").alias("offering_enrollment_count"),
         F.sum(F.when(F.col("LO_performance_label_3") == "G", 1).otherwise(0)).alias("g_count"),
         F.sum(F.when(F.col("LO_performance_label_3") == "E", 1).otherwise(0)).alias("e_count")))

# A is fixed first: the historical 60% is never touched by label balancing.
chronological = (Window.orderBy("offering_end_date", "timeline_source", "offering_id")
    .rowsBetween(Window.unboundedPreceding, Window.currentRow))
all_offerings = Window.partitionBy()
offerings = (offerings
    .withColumn("cumulative_enrollment_count", F.sum("offering_enrollment_count").over(chronological))
    .withColumn("total_enrollment_count", F.sum("offering_enrollment_count").over(all_offerings)))
a_offerings = offerings.filter(F.col("cumulative_enrollment_count") <= F.col("total_enrollment_count") * F.lit(0.60))
later_offerings = offerings.filter(F.col("cumulative_enrollment_count") > F.col("total_enrollment_count") * F.lit(0.60))


def allocate_later_offerings(rows):
    """Greedily allocate whole offerings to B--G by actual class counts."""
    blocks = ("B", "C", "D", "E", "F", "G")
    metrics = ("offering_enrollment_count", "g_count", "e_count")
    totals = {metric: sum(int(row[metric]) for row in rows) for metric in metrics}
    targets = {metric: totals[metric] / len(blocks) for metric in metrics}
    state = {block: {metric: 0 for metric in metrics} for block in blocks}

    def stable_key(row):
        raw = f"{row['offering_id']}|{row['timeline_source']}".encode("utf-8")
        return sha256(raw).hexdigest()

    # Offerings carrying scarce labels are placed first.  A class count, not
    # merely a has-class flag, determines the balancing decision.
    def rarity_priority(row):
        return sum(int(row[m]) / max(totals[m], 1) for m in metrics[1:])

    assigned = []
    for row in sorted(rows, key=lambda r: (-rarity_priority(r), -int(r["offering_enrollment_count"]), stable_key(r))):
        def score(block):
            value = 0.0
            # Compare the global allocation after placing this offering in a
            # candidate block.  Scoring only that one block starves later
            # blocks because their current deficits are ignored.
            for candidate in blocks:
                for metric in metrics:
                    projected = state[candidate][metric] + (
                        int(row[metric]) if candidate == block else 0)
                    deviation = (projected - targets[metric]) / max(targets[metric], 1.0)
                    weight = 1.0 if metric == "offering_enrollment_count" else 2.0
                    value += weight * deviation * deviation
            return value

        block = min(blocks, key=lambda candidate: (score(candidate), candidate))
        for metric in metrics:
            state[block][metric] += int(row[metric])
        assigned.append((row["offering_id"], row["timeline_source"], block))
    if {row[2] for row in assigned} != set(blocks):
        raise RuntimeError("Label allocator did not populate every B--G block.")
    return assigned


allocation_rows = allocate_later_offerings(later_offerings.select(
    *unit_columns, "offering_enrollment_count", "g_count", "e_count").collect())
later_assignments = spark.createDataFrame(allocation_rows, [*unit_columns, "rolling_block"])
offerings = (a_offerings.withColumn("rolling_block", F.lit("A"))
    .unionByName(later_offerings.join(later_assignments, unit_columns, "inner")))

manifests = []
for window_name, train_blocks, validation_block, test_block in WINDOWS:
    assigned = (offerings.filter(F.col("rolling_block").isin(*train_blocks, validation_block, test_block))
        .withColumn("split", F.when(F.col("rolling_block").isin(*train_blocks), F.lit("train"))
            .when(F.col("rolling_block") == validation_block, F.lit("validation"))
            .otherwise(F.lit("test"))))
    manifests.append(assigned.withColumn("window", F.lit(window_name)))
manifest = manifests[0]
for frame in manifests[1:]:
    manifest = manifest.unionByName(frame, allowMissingColumns=True)

split_rule_version = "offering_label_stratified_v1"
manifest_join_columns = [*unit_columns, "window", "split"]
if EXTERNAL_MANIFEST_SOURCE:
    external = spark.read.parquet(EXTERNAL_MANIFEST_SOURCE)
    required_manifest_columns = set(unit_columns + ["window_id", "split"])
    missing_manifest_columns = required_manifest_columns.difference(external.columns)
    if missing_manifest_columns:
        raise ValueError(f"Split manifest is missing required columns: {sorted(missing_manifest_columns)}")
    if external.groupBy(*unit_columns, "window_id").count().filter(F.col("count") > 1).limit(1).count():
        raise ValueError("Split manifest must have exactly one assignment per offering/timeline/window.")
    if "split_rule_version" not in external.columns:
        raise ValueError("LO V3.1 manifest must declare split_rule_version.")
    if (external.filter(F.col("split_rule_version") != F.lit(EXPECTED_SPLIT_RULE_VERSION))
            .limit(1).count()):
        raise ValueError(
            "LO V3.1 manifest split_rule_version does not match "
            f"{EXPECTED_SPLIT_RULE_VERSION!r}."
        )
    manifest = external.withColumnRenamed("window_id", "window")
    if VIEW_RELEASE in {"v2_2", "v2_2_sourcefaithful", "v2_3", "v3_catalog_normalized", "v3_1_scored_signal_excluded"}:
        required_v22 = {"duration_days", "long_offering_flag"}
        missing_v22 = required_v22.difference(manifest.columns)
        if missing_v22:
            raise ValueError(f"V2.2 manifest is missing audit columns: {sorted(missing_v22)}")
        manifest_join_columns.extend(["duration_days", "long_offering_flag"])
    split_rule_version = {
        "v2_1": "offering_temporal_label_balanced_v2_1",
        "v2_2": "offering_temporal_label_balanced_v2_2",
        "v2_2_sourcefaithful": "offering_temporal_label_balanced_v2_2_sourcefaithful",
        "v3_catalog_normalized": "offering_temporal_label_balanced_v3_catalog_normalized",
        "v3_1_scored_signal_excluded": "offering_temporal_label_balanced_v3_1_scored_signal_excluded",
        "v2_3": "offering_temporal_label_balanced_v2_3",
    }.get(VIEW_RELEASE, "offering_temporal_label_balanced_v2")

view = (base.join(manifest.select(*manifest_join_columns), unit_columns, "inner")
    .withColumn("task", F.lit("LO_operational"))
    .withColumn("split_id", F.col("split"))
    .withColumn("split_rule_version", F.lit(split_rule_version))
    .withColumn("label_available_by_cutoff_P1", (F.col("label_availability_time") <= F.col("cutoff_time_P1")).cast("int"))
    .withColumn("label_available_by_cutoff_P2", (F.col("label_availability_time") <= F.col("cutoff_time_P2")).cast("int"))
    .withColumn("label_available_by_cutoff_P3", (F.col("label_availability_time") <= F.col("cutoff_time_P3")).cast("int"))
    .withColumn("label_available_by_cutoff_P4", (F.col("label_availability_time") <= F.col("cutoff_time_P4")).cast("int"))
    .withColumn("primary_risk_set_P1", (F.col("cutoff_time_P1") < F.col("label_availability_time")).cast("int"))
    .withColumn("primary_risk_set_P2", (F.col("cutoff_time_P2") < F.col("label_availability_time")).cast("int"))
    .withColumn("primary_risk_set_P3", (F.col("cutoff_time_P3") < F.col("label_availability_time")).cast("int"))
    .withColumn("primary_risk_set_P4", (F.col("cutoff_time_P4") < F.col("label_availability_time")).cast("int"))
    .drop("_offering_end_date"))

split_counts = view.groupBy("window", "split", "LO_performance_label_3").agg(
    F.countDistinct("enrollment_id").alias("enrollment_count"))
split_totals = split_counts.groupBy("window", "split").agg(
    F.sum("enrollment_count").alias("split_enrollment_count"))
phase_audit = split_counts.join(split_totals, ["window", "split"], "inner").withColumn(
    "label_ratio", F.col("enrollment_count") / F.col("split_enrollment_count"))
block_audit = (offerings.groupBy("rolling_block")
    .agg(F.countDistinct(F.struct("offering_id", "timeline_source")).alias("offering_count"),
         F.sum("offering_enrollment_count").alias("enrollment_count"),
         F.sum("g_count").alias("g_count"), F.sum("e_count").alias("e_count"))
    .withColumn("id_count", F.col("enrollment_count") - F.col("g_count") - F.col("e_count"))
    .withColumn("g_ratio", F.col("g_count") / F.col("enrollment_count"))
    .withColumn("e_ratio", F.col("e_count") / F.col("enrollment_count"))
    .withColumn("id_ratio", F.col("id_count") / F.col("enrollment_count")))

phase_audit_path = OUT.rstrip("/") + "_audit/"
block_audit_path = MANIFEST_OUT.rstrip("/") + "_block_audit/"
write_parquet(manifest, MANIFEST_OUT)
train_validation = view.filter(F.col("split") != "test")
write_parquet(train_validation, OUT)
write_parquet(phase_audit, phase_audit_path)
write_parquet(block_audit, block_audit_path)
print(
    "[materialize_lo] primary outputs written: "
    f"{MANIFEST_OUT}, {OUT}, {phase_audit_path}, {block_audit_path}"
)
schema = {field.name: field.dataType for field in view.schema.fields}
for phase_index, prediction_phase in enumerate(("P1", "P2", "P3", "P4"), start=1):
    prefix_columns = []
    for name in view.columns:
        if name.startswith("phase_available_P"):
            prefix_columns.append(F.lit(int(int(name[-1]) <= phase_index)).alias(name))
        elif name.endswith(("_P1", "_P2", "_P3", "_P4")) and int(name[-1]) > phase_index:
            prefix_columns.append(F.lit(None).cast(schema[name]).alias(name))
        else:
            prefix_columns.append(F.col(name))
    test_prefix = (view.filter(F.col("split") == "test")
        .select(*prefix_columns)
        .withColumn("prediction_phase", F.lit(prediction_phase)))
    write_parquet(test_prefix, f"{TEST_PREFIX_OUT}{prediction_phase}/")
    prefix_rows = log_dataframe(logger, f"lo_test_prefix_{prediction_phase}_v1", test_prefix,
                                ("window", "enrollment_id"))
    log_write(logger, f"lo_test_prefix_{prediction_phase}_v1", f"{TEST_PREFIX_OUT}{prediction_phase}/", prefix_rows)
print(f"[materialize_lo] all test-prefix outputs written under {TEST_PREFIX_OUT}")
for name, frame, keys, path in (
    ("lo_split_manifest_v1", manifest, ("window", "offering_id"), MANIFEST_OUT),
    ("lo_train_validation_views_v1", train_validation, ("window", "split", "enrollment_id"), OUT),
    ("lo_split_audit_v1", phase_audit, ("window", "split", "LO_performance_label_3"), phase_audit_path),
    ("lo_block_audit_v1", block_audit, ("rolling_block",), block_audit_path),
):
    rows = log_dataframe(logger, name, frame, keys)
    log_write(logger, name, path, rows)
log_event(logger, "lo_phase_views_v3_1_materialized")
log_run_finished(logger, started)
flush_json_log(logger, spark)
