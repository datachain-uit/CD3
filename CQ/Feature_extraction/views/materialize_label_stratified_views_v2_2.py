"""CQ Method-5 views: chronological A, label-balanced B--G offerings.

A is the earliest 60% of enrollments at whole-offering boundaries.  Only the
remaining offerings are allocated to B--G by their actual Warning, Average
and Good counts.  B--G are therefore label-stratified, not time intervals.
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
if not str(BASE).startswith("/"):
    raise ValueError(
        "Set TEMPO_OUTPUT_BASE to the absolute Databricks storage root, for example "
        "'/Volumes/workspace/default/preprocessed'."
    )
# The frozen feature release used by the current CQ V1 view is the existing
# scenarios release.  Do not inherit a stale workspace protocol value such as
# ``features/v1`` here; an explicit VIEW_FEATURE_BASE can override it later.
FEATURE_BASE = os.environ.get("VIEW_FEATURE_BASE", f"{BASE.rstrip('/')}/features/scenarios").rstrip("/")
TASK_BASE = os.environ.get("VIEW_TASK_BASE", path_from_config(P, "task_feature_base")).rstrip("/")

# V1 config publishes ``cq_labels``.  Some workspaces still carry a pre-V1
# protocol file, but the V1 label rebuild is now canonical; therefore the
# fallback must point to cq_labels_v1 rather than the removed V3 release.
# VIEW_LABEL_SOURCE always takes precedence for an explicit experiment input.
try:
    _default_label_source = path_from_config(P, "cq_labels")
except KeyError:
    _default_label_source = f"{BASE.rstrip('/')}/labels/cq_labels_v1"
LABEL_SOURCE = os.environ.get("VIEW_LABEL_SOURCE", _default_label_source).rstrip("/") + "/"
FEATURE_SOURCE = os.environ.get(
    "VIEW_FEATURE_SOURCE", f"{FEATURE_BASE}/hybrid/cumulative_phase_features_v1/"
).rstrip("/") + "/"
WINDOWS_SOURCE = os.environ.get(
    "VIEW_WINDOWS_SOURCE", f"{FEATURE_BASE}/hybrid/enrollment_windows/"
).rstrip("/") + "/"
# Optional immutable Split V2 manifest.  Leaving this unset preserves the
# original V1 experiment exactly; set it to ``.../split_manifest_v2/manifest``
# only after the V2 QA22 artifact has passed review.
EXTERNAL_MANIFEST_SOURCE = os.environ.get("VIEW_SPLIT_MANIFEST_SOURCE", "").rstrip("/")
VIEW_RELEASE = os.environ.get("VIEW_RELEASE")
if not VIEW_RELEASE:
    if EXTERNAL_MANIFEST_SOURCE:
        raise ValueError(
            "Set VIEW_RELEASE explicitly for an external split manifest "
            "(for example, v2_1). Refusing to write an ambiguous release."
        )
    VIEW_RELEASE = "v1"
if VIEW_RELEASE not in {"v1", "v2", "v2_1", "v2_2", "v2_3"}:
    raise ValueError("VIEW_RELEASE must be v1, v2, v2_1, v2_2, or v2_3")
OUT = f"{TASK_BASE}/CQ/hybrid/phase_views_{VIEW_RELEASE}/"
MANIFEST_OUT = f"{TASK_BASE}/CQ/hybrid/split_manifest_{VIEW_RELEASE}/"
TEST_PREFIX_OUT = f"{TASK_BASE}/CQ/hybrid/test_prefix_views_{VIEW_RELEASE}/"
STRICT_CONTEXT_SOURCE = os.environ.get(
    "VIEW_TEMPORAL_STRICT_CONTEXT_SOURCE",
    f"{EXTERNAL_MANIFEST_SOURCE.rsplit('/', 1)[0]}/temporal_strict_context" if EXTERNAL_MANIFEST_SOURCE else "",
).rstrip("/")
print(
    "[materialize_cq] "
    f"release={VIEW_RELEASE}; manifest_input={EXTERNAL_MANIFEST_SOURCE or 'built_in_v1'}; "
    f"strict_context_input={STRICT_CONTEXT_SOURCE or 'not-required'}; "
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
    .appName("materialize_cq_label_stratified_v1")
    .config("spark.sql.session.timeZone", "UTC")
    .getOrCreate())
logger = get_logger("materialize_cq_label_stratified_v1", path_from_config(P, "logs"))
started = start_run_timer()
log_run_context(logger, spark, {
    "label_source": LABEL_SOURCE,
    "feature_source": FEATURE_SOURCE,
    "windows_source": WINDOWS_SOURCE,
    "output": OUT,
    "manifest_output": MANIFEST_OUT,
    "test_prefix_output": TEST_PREFIX_OUT,
    "view_release": VIEW_RELEASE,
    "external_manifest_source": EXTERNAL_MANIFEST_SOURCE or None,
    "split": "method_5__A_chronological_60__B_to_G_greedy_label_count_stratified",
    "label_filter": "canonical eligible CQ V3 rows only; no downsampling",
})


def require_one_row_per_enrollment(frame, source_name):
    """Remove byte-for-byte duplicate rows; reject conflicting source rows.

    Every downstream split, imputation, balancing and model run has
    ``enrollment_id`` as its analytical unit.  Silently choosing one of two
    non-identical source rows would corrupt that contract, so only complete
    duplicate records are collapsed here.  Any remaining repeated key stops
    materialization and must be repaired at its upstream producer.
    """
    rows_before = frame.count()
    deduplicated = frame.dropDuplicates()
    rows_after_exact_deduplication = deduplicated.count()
    repeated = (deduplicated.groupBy("enrollment_id").count()
        .filter(F.col("count") > 1))
    if repeated.limit(1).count():
        examples = [row["enrollment_id"] for row in repeated.limit(10).collect()]
        raise ValueError(
            f"{source_name} has non-identical repeated enrollment_id values; "
            f"examples={examples}. Repair the upstream source instead of selecting arbitrarily."
        )
    print(
        f"[materialize_cq] grain_ok source={source_name}; "
        f"rows_before={rows_before}; rows_after_exact_deduplication={rows_after_exact_deduplication}; "
        f"exact_duplicates_collapsed={rows_before - rows_after_exact_deduplication}"
    )
    return deduplicated


labels = (spark.read.parquet(LABEL_SOURCE)
    .filter(F.col("cq_exclusion_reason").isNull() & F.col("CQ_label_final").isNotNull())
    .select("enrollment_id", "CQ_label_final", "label_availability_time",
            "label_availability_source", "label_rule_version",
            # Label provenance is retained for auditing/explainability only.
            # The Python preprocessing contract excludes these from X.
            "COELO_final", "AFELO_final", "ACELO_final", "CQ_label_vector",
            "CQ_distance_euclidean_final", "CQ_proximity_final",
            "TRIAD_distance_final", "observed_dimension_mask"))
labels = require_one_row_per_enrollment(labels, "labels")
features = require_one_row_per_enrollment(spark.read.parquet(FEATURE_SOURCE), "features")
windows = require_one_row_per_enrollment((spark.read.parquet(WINDOWS_SOURCE)
    .select("enrollment_id", F.col("offering_id").cast("string").alias("_source_offering_id"),
            F.col("window_end_date").alias("_offering_end_date"))), "enrollment_windows")
base = features.join(labels, "enrollment_id", "inner").join(windows, "enrollment_id", "left")
if "offering_id" in features.columns:
    base = base.withColumn("offering_id", F.coalesce(
        F.col("offering_id").cast("string"), F.col("_source_offering_id")))
else:
    base = base.withColumn("offering_id", F.col("_source_offering_id"))
base = base.drop("_source_offering_id")
base = require_one_row_per_enrollment(base, "joined_base")
if base.filter(F.col("offering_id").isNull() | F.col("_offering_end_date").isNull()).limit(1).count():
    raise ValueError("Each eligible enrollment must have offering_id and window_end_date.")

unit_columns = ["offering_id", "timeline_source"]
offerings = (base
    .groupBy(*unit_columns)
    .agg(F.min("_offering_end_date").alias("offering_end_date"),
         F.countDistinct("enrollment_id").alias("offering_enrollment_count"),
         F.sum(F.when(F.col("CQ_label_final") == "average", 1).otherwise(0)).alias("average_count"),
         F.sum(F.when(F.col("CQ_label_final") == "good", 1).otherwise(0)).alias("good_count")))

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
    metrics = ("offering_enrollment_count", "average_count", "good_count")
    totals = {metric: sum(int(row[metric]) for row in rows) for metric in metrics}
    targets = {metric: totals[metric] / len(blocks) for metric in metrics}
    state = {block: {metric: 0 for metric in metrics} for block in blocks}

    def stable_key(row):
        raw = f"{row['offering_id']}|{row['timeline_source']}".encode("utf-8")
        return sha256(raw).hexdigest()

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
    *unit_columns, "offering_enrollment_count", "average_count", "good_count").collect())
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
    manifest = external.withColumnRenamed("window_id", "window")
    if VIEW_RELEASE in {"v2_2", "v2_3"}:
        required_v22 = {"duration_days", "long_offering_flag"}
        missing_v22 = required_v22.difference(manifest.columns)
        if missing_v22:
            raise ValueError(f"V2.2 manifest is missing audit columns: {sorted(missing_v22)}")
        manifest_join_columns.extend(["duration_days", "long_offering_flag"])
    split_rule_version = {
        "v2_1": "offering_temporal_label_balanced_v2_1",
        "v2_2": "offering_temporal_label_balanced_v2_2",
        "v2_3": "offering_temporal_label_balanced_v2_3",
    }.get(VIEW_RELEASE, "offering_temporal_label_balanced_v2")

view = (base.join(manifest.select(*manifest_join_columns), unit_columns, "inner")
    .withColumn("task", F.lit("CQ"))
    .withColumn("split_id", F.col("split"))
    .withColumn("split_rule_version", F.lit(split_rule_version))
    # Locked CQ threshold-set identity; retained downstream exclusively as
    # non-predictive audit context.
    .withColumn("label_threshold_set", F.lit("CQ_VECTOR_PROXIMITY_PRIMARY_V1"))
    .withColumn("primary_risk_set", F.lit(1))
    .withColumn("label_available_by_cutoff_P1", (F.col("label_availability_time") <= F.col("cutoff_time_P1")).cast("int"))
    .withColumn("label_available_by_cutoff_P2", (F.col("label_availability_time") <= F.col("cutoff_time_P2")).cast("int"))
    .withColumn("label_available_by_cutoff_P3", (F.col("label_availability_time") <= F.col("cutoff_time_P3")).cast("int"))
    .withColumn("label_available_by_cutoff_P4", (F.col("label_availability_time") <= F.col("cutoff_time_P4")).cast("int"))
    .drop("_offering_end_date"))

if VIEW_RELEASE in {"v2_2", "v2_3"}:
    if not STRICT_CONTEXT_SOURCE:
        raise ValueError("V2.2+ materialization requires VIEW_TEMPORAL_STRICT_CONTEXT_SOURCE.")
    strict = spark.read.parquet(STRICT_CONTEXT_SOURCE)
    strict_columns = {"enrollment_id", "window_id", "split", *[f"temporal_strict_P{i}" for i in range(1, 5)]}
    missing_strict = strict_columns.difference(strict.columns)
    if missing_strict:
        raise ValueError(f"Temporal-strict context is missing columns: {sorted(missing_strict)}")
    strict = strict.select(
        "enrollment_id", F.col("window_id").alias("window"), "split",
        *[f"temporal_strict_P{i}" for i in range(1, 5)],
    )
    if strict.groupBy("enrollment_id", "window", "split").count().filter(F.col("count") > 1).limit(1).count():
        raise ValueError("Temporal-strict context has duplicate enrollment/window/split keys.")
    unmatched = view.join(strict.select("enrollment_id", "window", "split"), ["enrollment_id", "window", "split"], "left_anti")
    if unmatched.limit(1).count():
        raise ValueError("Some materialized CQ rows lack temporal-strict context.")
    view = view.join(strict, ["enrollment_id", "window", "split"], "inner")

split_counts = view.groupBy("window", "split", "CQ_label_final").agg(
    F.countDistinct("enrollment_id").alias("enrollment_count"))
split_totals = split_counts.groupBy("window", "split").agg(
    F.sum("enrollment_count").alias("split_enrollment_count"))
phase_audit = split_counts.join(split_totals, ["window", "split"], "inner").withColumn(
    "label_ratio", F.col("enrollment_count") / F.col("split_enrollment_count"))
block_audit = (offerings.groupBy("rolling_block")
    .agg(F.countDistinct(F.struct("offering_id", "timeline_source")).alias("offering_count"),
         F.sum("offering_enrollment_count").alias("enrollment_count"),
         F.sum("average_count").alias("average_count"), F.sum("good_count").alias("good_count"))
    .withColumn("warning_count", F.col("enrollment_count") - F.col("average_count") - F.col("good_count"))
    .withColumn("average_ratio", F.col("average_count") / F.col("enrollment_count"))
    .withColumn("good_ratio", F.col("good_count") / F.col("enrollment_count"))
    .withColumn("warning_ratio", F.col("warning_count") / F.col("enrollment_count")))

phase_audit_path = OUT.rstrip("/") + "_audit/"
block_audit_path = MANIFEST_OUT.rstrip("/") + "_block_audit/"
write_parquet(manifest, MANIFEST_OUT)
# Train and validation contain the complete P1--P4 wide sequence.  Full test
# rows are intentionally not released here, so a consumer cannot accidentally
# use future phases while evaluating early prefixes.
train_validation = view.filter(F.col("split") != "test")
write_parquet(train_validation, OUT)
write_parquet(phase_audit, phase_audit_path)
write_parquet(block_audit, block_audit_path)
print(
    "[materialize_cq] primary outputs written: "
    f"{MANIFEST_OUT}, {OUT}, {phase_audit_path}, {block_audit_path}"
)
schema = {field.name: field.dataType for field in view.schema.fields}
for phase_index, prediction_phase in enumerate(("P1", "P2", "P3", "P4"), start=1):
    prefix_columns = []
    for name in view.columns:
        if name.startswith("phase_available_P"):
            phase_number = int(name[-1])
            prefix_columns.append(F.lit(int(phase_number <= phase_index)).alias(name))
        elif name.endswith(("_P1", "_P2", "_P3", "_P4")) and int(name[-1]) > phase_index:
            prefix_columns.append(F.lit(None).cast(schema[name]).alias(name))
        else:
            prefix_columns.append(F.col(name))
    test_prefix = (view.filter(F.col("split") == "test")
        .select(*prefix_columns)
        .withColumn("prediction_phase", F.lit(prediction_phase)))
    write_parquet(test_prefix, f"{TEST_PREFIX_OUT}{prediction_phase}/")
    prefix_rows = log_dataframe(logger, f"cq_test_prefix_{prediction_phase}_v1", test_prefix,
                                ("window", "enrollment_id"))
    log_write(logger, f"cq_test_prefix_{prediction_phase}_v1", f"{TEST_PREFIX_OUT}{prediction_phase}/", prefix_rows)
print(f"[materialize_cq] all test-prefix outputs written under {TEST_PREFIX_OUT}")
for name, frame, keys, path in (
    ("cq_split_manifest_v1", manifest, ("window", "offering_id"), MANIFEST_OUT),
    ("cq_train_validation_views_v1", train_validation, ("window", "split", "enrollment_id"), OUT),
    ("cq_split_audit_v1", phase_audit, ("window", "split", "CQ_label_final"), phase_audit_path),
    ("cq_block_audit_v1", block_audit, ("rolling_block",), block_audit_path),
):
    rows = log_dataframe(logger, name, frame, keys)
    log_write(logger, name, path, rows)
log_event(logger, f"cq_phase_views_{VIEW_RELEASE}_materialized")
log_run_finished(logger, started)
flush_json_log(logger, spark)
