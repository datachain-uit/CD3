"""Build CQ labels with PM-approved operational threshold bands.

This release keeps the CQ v3 artifact as the feature/metric source, but changes
the final classification rule to the requested three operational bands:

* ``G < 0.10``         -> ``warning`` (cảnh báo)
* ``0.10 <= G < 0.30`` -> ``average`` (trung bình)
* ``G >= 0.30``        -> ``good`` (tốt)

The non-compensatory floor remains available as a diagnostic column.  It no
longer changes the class to ``needs_review``.  Rows for which the assessment
is not observable or a normalized CQ component is missing/invalid remain NULL
and are reported through an explicit exclusion reason; missing evidence is
not silently converted into the warning class.
"""

import runpy
import sys
import os
from pathlib import Path

# Databricks may execute this file from a notebook command whose working
# directory is not the project root.  Make sibling packages (common, features,
# views, ...) importable without relying on the caller's current directory.
_file_path = globals().get("__file__")
if _file_path:
    PROJECT_ROOT = Path(_file_path).resolve().parents[1]
else:
    # Workspace files executed with %run have no __file__; derive their
    # workspace location. A pasted cell can explicitly set PROJECT_ROOT first.
    _configured_root = globals().get("PROJECT_ROOT") or os.environ.get("PROJECT_ROOT")
    PROJECT_ROOT = Path(_configured_root) if _configured_root else None
    if PROJECT_ROOT is None or not (PROJECT_ROOT / "common").is_dir():
        try:
            _notebook = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
            _workspace_path = Path("/Workspace") / _notebook.lstrip("/")
            PROJECT_ROOT = next(parent for parent in _workspace_path.parents if (parent / "common").is_dir())
        except Exception as error:
            _candidates = list(Path("/Workspace/Users").glob("*/CQ/Feature_extraction"))
            if len(_candidates) == 1 and (_candidates[0] / "common").is_dir():
                PROJECT_ROOT = _candidates[0]
            else:
                raise RuntimeError(
                    "Cannot locate CQ/Feature_extraction. Set job environment variable PROJECT_ROOT to "
                    "the absolute workspace directory containing common/."
                ) from error
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pyspark.sql import SparkSession, Window, functions as F

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
OUTPUT_BASE = PROTOCOL["output_base"]


def _artifact_path(path_key: str, v1_relative_path: str) -> str:
    """Support the old workspace protocol while it is being migrated to V1."""
    try:
        return path_from_config(PROTOCOL, path_key)
    except KeyError:
        return f"{OUTPUT_BASE.rstrip('/')}/{v1_relative_path}"


SOURCE_PATH = _artifact_path("cq_label_components", "labels/cq_label_components_v1") + "/"
OUTPUT_PATH = _artifact_path("cq_label_release", "labels/cq_label_release_v1") + "/"
CANONICAL_OUTPUT_PATH = _artifact_path("cq_labels", "labels/cq_labels_v1") + "/"
# Ensure the component child invoked below uses exactly the same path even if
# Databricks has a stale common.protocol_config module cached in the kernel.
os.environ["CQ_COMPONENT_OUTPUT"] = SOURCE_PATH.rstrip("/")
AUDIT_BASE = f"{OUTPUT_BASE}/labels/cq_labels_v1_audit/"
LABEL_VERSION = "cq_vector_proximity_v1_zero_activity_policy"
G_WEIGHTS = {"COELO": 0.40, "AFELO": 0.20, "ACELO": 0.40}
G_WARNING = 0.10
G_GOOD = 0.30


spark = SparkSession.builder.appName("build_cq_labels").config(
    "spark.sql.session.timeZone", "UTC"
).getOrCreate()
logger = get_logger("build_cq_labels", f"{OUTPUT_BASE}/logs")
log_run_context(
    logger,
    spark,
    {
        "label_version": LABEL_VERSION,
        "source": SOURCE_PATH,
        "output": OUTPUT_PATH,
        "audit_output": AUDIT_BASE,
        "grain": "enrollment_id_user_id_course_id",
        "score_metric": "weighted_geometric_mean",
        "geometric_mean_weights": G_WEIGHTS,
        "expert_bands": {
            "warning": "G < 0.10",
            "average": "0.10 <= G < 0.30",
            "good": "G >= 0.30",
        },
        "floor_policy": "diagnostic_only__does_not_override_expert_band",
        "missing_data_policy": "NULL_with_exclusion_reason__not_warning",
        "population_policy": "all_enrollments_for_course_specific_timeline__active_only_for_proxy_timeline",
    },
)
started = start_run_timer()


def require_columns(dataframe, columns):
    missing = sorted(set(columns).difference(dataframe.columns))
    if missing:
        raise ValueError("CQ v3 artifact is missing columns: " + ", ".join(missing))


def valid_component(column_name):
    value = F.col(column_name).cast("double")
    return (
        value.isNotNull()
        & (~F.isnan(value))
        & (value >= F.lit(0.0))
        & (value <= F.lit(1.0))
    )


def weighted_geometric_mean(coelo, afelo, acelo, valid):
    return F.when(
        valid,
        F.pow(F.col(coelo).cast("double"), F.lit(G_WEIGHTS["COELO"]))
        * F.pow(F.col(afelo).cast("double"), F.lit(G_WEIGHTS["AFELO"]))
        * F.pow(F.col(acelo).cast("double"), F.lit(G_WEIGHTS["ACELO"])),
    )


def expert_band(score_column, valid_expression):
    score = F.col(score_column)
    return (
        F.when(~valid_expression, F.lit(None).cast("string"))
        .when(score < F.lit(G_WARNING), F.lit("warning"))
        .when(score < F.lit(G_GOOD), F.lit("average"))
        .otherwise(F.lit("good"))
    )


# Components are an implementation detail of the single canonical builder.
# This must run before its output is read; users invoke only build_cq_labels.
# On Databricks Serverless a Volume write can be invisible to a subsequent
# Spark read inside the same notebook command, even though the child write
# has committed.  ``run_module`` returns the child's globals, so consume its
# in-memory artifact in this parent run.  The child still persists the
# components artifact for audit/re-execution; a fresh process can use it.
_component_module = runpy.run_module("labels.cq_component_builder", run_name="__main__")
source = _component_module.get("artifact")
if source is None:
    source = spark.read.parquet(SOURCE_PATH)
if "label_availability_source" not in source.columns:
    source = source.withColumn("label_availability_source", F.col("offering_source"))
require_columns(
    source,
    (
        "enrollment_id",
        "user_id",
        "course_id",
        "assessment_observable",
        "COELO_personal",
        "AFELO_personal",
        "ACELO_personal",
        "assessment_proxy_available",
        "COELO_proxy_personal",
        "AFELO_personal",
        "ACELO_proxy_personal",
        "cq_label",
        "cq_proxy_label",
        "label_valid",
        "proxy_label_valid",
        "label_rule_version",
        "cq_population_group",
        "cq_active_event_any",
    ),
)

primary_components_present = (
    F.col("COELO_personal").isNotNull()
    & F.col("AFELO_personal").isNotNull()
    & F.col("ACELO_personal").isNotNull()
)
primary_components_valid = (
    valid_component("COELO_personal")
    & valid_component("AFELO_personal")
    & valid_component("ACELO_personal")
)
primary_valid = (
    (F.coalesce(F.col("assessment_observable"), F.lit(0)) == 1)
    & primary_components_valid
)

proxy_components_present = (
    F.col("COELO_proxy_personal").isNotNull()
    & F.col("AFELO_personal").isNotNull()
    & F.col("ACELO_proxy_personal").isNotNull()
)
proxy_components_valid = (
    valid_component("COELO_proxy_personal")
    & valid_component("AFELO_personal")
    & valid_component("ACELO_proxy_personal")
)
proxy_valid = (
    (F.coalesce(F.col("assessment_proxy_available"), F.lit(0)) == 1)
    & proxy_components_valid
)

expert = (
    source.withColumn(
        "G_expert_weighted_geometric_mean",
        weighted_geometric_mean(
            "COELO_personal", "AFELO_personal", "ACELO_personal", primary_valid
        ),
    )
    .withColumn(
        "G_proxy_expert_weighted_geometric_mean",
        weighted_geometric_mean(
            "COELO_proxy_personal",
            "AFELO_personal",
            "ACELO_proxy_personal",
            proxy_valid,
        ),
    )
    .withColumn(
        "cq_label_expert_v4",
        expert_band("G_expert_weighted_geometric_mean", primary_valid),
    )
    .withColumn(
        "cq_proxy_label_expert_v4",
        expert_band("G_proxy_expert_weighted_geometric_mean", proxy_valid),
    )
    .withColumn("cq_label_expert_v4_valid", primary_valid.cast("int"))
    .withColumn("cq_proxy_label_expert_v4_valid", proxy_valid.cast("int"))
    .withColumn(
        "cq_label_expert_v4_exclusion_reason",
        F.when(
            (F.coalesce(F.col("assessment_observable"), F.lit(0)) != 1),
            F.lit("assessment_activity_not_fully_observable"),
        )
        .when(~primary_components_present, F.lit("missing_cq_component"))
        .when(~primary_components_valid, F.lit("cq_component_out_of_range")),
    )
    .withColumn(
        "cq_proxy_label_expert_v4_exclusion_reason",
        F.when(
            (F.coalesce(F.col("assessment_proxy_available"), F.lit(0)) != 1),
            F.lit("assessment_proxy_not_available"),
        )
        .when(~proxy_components_present, F.lit("missing_cq_proxy_component"))
        .when(~proxy_components_valid, F.lit("cq_proxy_component_out_of_range")),
    )
    .withColumn(
        "floor_fail_but_expert_labeled",
        (
            primary_valid
            & (F.coalesce(F.col("floor_pass"), F.lit(0)) != 1)
        ).cast("int"),
    )
    .withColumn(
        "proxy_floor_fail_but_expert_labeled",
        (
            proxy_valid
            & (F.coalesce(F.col("proxy_floor_pass"), F.lit(0)) != 1)
        ).cast("int"),
    )
    # Keep the old strict result for audit, but make the canonical fields in
    # this v4 artifact use the expert bands so downstream joins do not silently
    # continue training on the obsolete ``needs_review`` policy.
    .withColumn("cq_label_v3_strict", F.col("cq_label"))
    .withColumn("cq_proxy_label_v3_strict", F.col("cq_proxy_label"))
    .withColumn("label_valid_v3_strict", F.col("label_valid"))
    .withColumn("proxy_label_valid_v3_strict", F.col("proxy_label_valid"))
    .withColumn("label_rule_version_v3_strict", F.col("label_rule_version"))
    .withColumn("label_exclusion_reason_v3_strict", F.col("label_exclusion_reason"))
    .withColumn("cq_label", F.col("cq_label_expert_v4"))
    .withColumn("cq_proxy_label", F.col("cq_proxy_label_expert_v4"))
    .withColumn("label_valid", F.col("cq_label_expert_v4_valid"))
    .withColumn("proxy_label_valid", F.col("cq_proxy_label_expert_v4_valid"))
    .withColumn("label_rule_version", F.lit(LABEL_VERSION))
    .withColumn(
        "label_exclusion_reason",
        F.col("cq_label_expert_v4_exclusion_reason"),
    )
    .withColumn("expert_label_rule_version", F.lit(LABEL_VERSION))
)

label_distribution = (
    expert.groupBy(
        F.coalesce(F.col("cq_label_expert_v4"), F.lit("NULL")).alias("label"),
        F.coalesce(F.col("primary_label_source"), F.lit("unknown")).alias("label_source"),
    )
    .agg(
        F.count("enrollment_id").alias("enrollment_count"),
        F.countDistinct("user_id").alias("user_count"),
        F.countDistinct("course_id").alias("course_count"),
        F.avg("G_expert_weighted_geometric_mean").alias("G_mean"),
        F.avg("COELO_personal").alias("COELO_mean"),
        F.avg("AFELO_personal").alias("AFELO_mean"),
        F.avg("ACELO_personal").alias("ACELO_mean"),
    )
    .orderBy("label_source", "label")
)

population_summary = (
    expert.groupBy("cq_population_group")
    .agg(
        F.count("enrollment_id").alias("enrollment_count"),
        F.countDistinct("user_id").alias("user_count"),
        F.countDistinct("course_id").alias("course_count"),
        F.sum("cq_active_event_any").alias("active_event_enrollment_count"),
        F.sum(F.when(F.col("cq_active_event_any") == 0, 1).otherwise(0)).alias("zero_activity_enrollment_count"),
        F.sum("cq_label_expert_v4_valid").alias("labeled_enrollment_count"),
        F.sum(F.when(F.col("cq_label_expert_v4") == "warning", 1).otherwise(0)).alias("warning_count"),
    )
    .withColumn("label_version", F.lit(LABEL_VERSION))
    .orderBy("cq_population_group")
)

# Fixed-width score bins make the expert thresholds and the actual score
# density directly comparable.  This is intentionally based on the canonical
# primary score, not the proxy score.
score_bin_distribution = (
    expert.filter(F.col("cq_label_expert_v4").isNotNull())
    .withColumn(
        "score_bin",
        F.when(F.col("G_expert_weighted_geometric_mean") < F.lit(0.20), F.lit("0.0–<0.2"))
        .when(F.col("G_expert_weighted_geometric_mean") < F.lit(0.40), F.lit("0.2–<0.4"))
        .when(F.col("G_expert_weighted_geometric_mean") < F.lit(0.60), F.lit("0.4–<0.6"))
        .when(F.col("G_expert_weighted_geometric_mean") < F.lit(0.80), F.lit("0.6–<0.8"))
        .otherwise(F.lit("0.8–1.0")),
    )
    .withColumn(
        "bin_order",
        F.when(F.col("G_expert_weighted_geometric_mean") < F.lit(0.20), F.lit(1))
        .when(F.col("G_expert_weighted_geometric_mean") < F.lit(0.40), F.lit(2))
        .when(F.col("G_expert_weighted_geometric_mean") < F.lit(0.60), F.lit(3))
        .when(F.col("G_expert_weighted_geometric_mean") < F.lit(0.80), F.lit(4))
        .otherwise(F.lit(5)),
    )
    .groupBy("bin_order", "score_bin")
    .agg(
        F.count("enrollment_id").alias("enrollment_count"),
        F.countDistinct("user_id").alias("user_count"),
        F.countDistinct("course_id").alias("course_count"),
        F.avg("G_expert_weighted_geometric_mean").alias("G_mean"),
        F.min("G_expert_weighted_geometric_mean").alias("G_min"),
        F.max("G_expert_weighted_geometric_mean").alias("G_max"),
    )
    .withColumn(
        "enrollment_ratio",
        F.try_divide(F.col("enrollment_count"), F.sum("enrollment_count").over(Window.partitionBy()))
    )
    .withColumn("label_version", F.lit(LABEL_VERSION))
    .orderBy("bin_order")
)

# Reporting distribution for the same PM-approved bands that define
# CQ_label_final. It uses the valid primary CQ population.
three_threshold_distribution = (
    expert.filter(F.col("cq_label_expert_v4").isNotNull())
    .withColumn(
        "threshold_band",
        F.when(F.col("G_expert_weighted_geometric_mean") < F.lit(0.10), F.lit("warning_<0.1"))
        .when(F.col("G_expert_weighted_geometric_mean") < F.lit(0.30), F.lit("average_0.1_to_lt_0.3"))
        .otherwise(F.lit("good_ge_0.3")),
    )
    .withColumn(
        "band_order",
        F.when(F.col("G_expert_weighted_geometric_mean") < F.lit(0.10), F.lit(1))
        .when(F.col("G_expert_weighted_geometric_mean") < F.lit(0.30), F.lit(2))
        .otherwise(F.lit(3)),
    )
    .groupBy("band_order", "threshold_band")
    .agg(
        F.count("enrollment_id").alias("enrollment_count"),
        F.countDistinct("user_id").alias("user_count"),
        F.countDistinct("course_id").alias("course_count"),
        F.avg("G_expert_weighted_geometric_mean").alias("G_mean"),
        F.min("G_expert_weighted_geometric_mean").alias("G_min"),
        F.max("G_expert_weighted_geometric_mean").alias("G_max"),
    )
    .withColumn(
        "enrollment_ratio",
        F.try_divide(F.col("enrollment_count"), F.sum("enrollment_count").over(Window.partitionBy()))
    )
    .withColumn("label_version", F.lit(LABEL_VERSION))
    .orderBy("band_order")
)

proxy_label_distribution = (
    expert.groupBy(
        F.coalesce(F.col("cq_proxy_label_expert_v4"), F.lit("NULL")).alias("label"),
        F.coalesce(F.col("assessment_weight_source"), F.lit("unknown")).alias("weight_source"),
    )
    .agg(
        F.count("enrollment_id").alias("enrollment_count"),
        F.countDistinct("user_id").alias("user_count"),
        F.countDistinct("course_id").alias("course_count"),
        F.avg("G_proxy_expert_weighted_geometric_mean").alias("G_mean"),
    )
    .orderBy("weight_source", "label")
)

floor_cross_tab = (
    expert.groupBy(
        F.coalesce(F.col("floor_pass"), F.lit(-1)).alias("floor_pass"),
        F.coalesce(F.col("cq_label_expert_v4"), F.lit("NULL")).alias("label"),
    )
    .agg(F.count("enrollment_id").alias("enrollment_count"))
    .orderBy("floor_pass", "label")
)

exclusion_summary = (
    expert.groupBy(
        F.coalesce(
            F.col("cq_label_expert_v4_exclusion_reason"), F.lit("labeled")
        ).alias("exclusion_reason")
    )
    .agg(F.count("enrollment_id").alias("enrollment_count"))
    .orderBy("exclusion_reason")
)

global_summary = expert.agg(
    F.count("enrollment_id").alias("enrollment_count"),
    F.countDistinct("user_id").alias("user_count"),
    F.countDistinct("course_id").alias("course_count"),
    F.sum("cq_label_expert_v4_valid").alias("primary_valid_count"),
    F.sum("cq_proxy_label_expert_v4_valid").alias("proxy_valid_count"),
    F.sum("floor_fail_but_expert_labeled").alias("primary_floor_fail_but_labeled_count"),
    F.sum("proxy_floor_fail_but_expert_labeled").alias("proxy_floor_fail_but_labeled_count"),
    F.sum(F.when(F.col("cq_label_expert_v4") == "warning", 1).otherwise(0)).alias("warning_count"),
    F.sum(F.when(F.col("cq_label_expert_v4") == "average", 1).otherwise(0)).alias("average_count"),
    F.sum(F.when(F.col("cq_label_expert_v4") == "good", 1).otherwise(0)).alias("good_count"),
).withColumn("label_version", F.lit(LABEL_VERSION))

metric_distribution = None
for column_name, metric_name in (
    ("G_expert_weighted_geometric_mean", "G_expert"),
    ("G_proxy_expert_weighted_geometric_mean", "G_proxy_expert"),
):
    summary = expert.agg(
        F.count(column_name).alias("sample_count"),
        F.avg(column_name).alias("mean"),
        F.stddev(column_name).alias("stddev"),
        F.min(column_name).alias("min"),
        F.expr(f"percentile_approx({column_name}, 0.25, 10000)").alias("p25"),
        F.expr(f"percentile_approx({column_name}, 0.50, 10000)").alias("p50"),
        F.expr(f"percentile_approx({column_name}, 0.75, 10000)").alias("p75"),
        F.max(column_name).alias("max"),
    ).withColumn("metric", F.lit(metric_name)).withColumn("label_version", F.lit(LABEL_VERSION))
    metric_distribution = summary if metric_distribution is None else metric_distribution.unionByName(summary)

artifact_path = OUTPUT_PATH
write_parquet(expert, artifact_path)
artifact_rows = log_dataframe(logger, "cq_personal_v4_expert_labels", expert, ("enrollment_id",))
log_write(logger, "cq_personal_v4_expert_labels", artifact_path, artifact_rows)

# Publish the canonical CQ vector.  The class is derived from proximity to
# the ideal vector [1, 1, 1], not from the legacy geometric-mean diagnostic.
canonical = (
    expert.withColumn("COELO_final", F.col("COELO_personal"))
    .withColumn("AFELO_final", F.col("AFELO_personal"))
    .withColumn("ACELO_final", F.col("ACELO_personal"))
    .withColumn(
        "TRIAD_distance_final",
        F.sqrt(
            F.pow(F.col("COELO_personal") - F.lit(1.0), F.lit(2.0))
            + F.pow(F.col("AFELO_personal") - F.lit(1.0), F.lit(2.0))
            + F.pow(F.col("ACELO_personal") - F.lit(1.0), F.lit(2.0))
        ) / F.sqrt(F.lit(3.0)),
    )
    .withColumn(
        "CQ_label_vector",
        F.array(F.col("COELO_personal").cast("double"), F.col("AFELO_personal").cast("double"), F.col("ACELO_personal").cast("double")),
    )
    .withColumn(
        "CQ_distance_euclidean_final",
        F.when(
            F.col("cq_label_expert_v4_valid") == 1,
            F.sqrt(
                F.pow(F.col("COELO_personal") - F.lit(1.0), F.lit(2.0))
                + F.pow(F.col("AFELO_personal") - F.lit(1.0), F.lit(2.0))
                + F.pow(F.col("ACELO_personal") - F.lit(1.0), F.lit(2.0))
            ),
        ),
    )
    .withColumn(
        "CQ_proximity_final",
        F.when(F.col("CQ_distance_euclidean_final").isNotNull(), F.lit(1.0) - F.col("CQ_distance_euclidean_final") / F.sqrt(F.lit(3.0))),
    )
    .withColumn(
        "CQ_label_final",
        F.when(F.col("CQ_proximity_final").isNull(), F.lit(None).cast("string"))
        .when(F.col("CQ_proximity_final") < F.lit(0.10), F.lit("warning"))
        .when(F.col("CQ_proximity_final") < F.lit(0.30), F.lit("average"))
        .otherwise(F.lit("good")),
    )
    .withColumn(
        "observed_dimension_mask",
        F.array(
            F.coalesce(F.col("video_event_present"), F.lit(0)).cast("int"),
            F.coalesce(F.col("problem_event_present"), F.lit(0)).cast("int"),
            F.coalesce(F.col("comment_event_present"), F.lit(0)).cast("int"),
        ),
    )
    .withColumn("cq_exclusion_reason", F.col("cq_label_expert_v4_exclusion_reason"))
    .select(
        "enrollment_id", "user_id", "course_id",
        "cq_population_group", "cq_active_event_any",
        "COELO_final", "AFELO_final", "ACELO_final", "CQ_label_vector",
        "CQ_distance_euclidean_final", "CQ_proximity_final", "TRIAD_distance_final",
        "CQ_label_final", "observed_dimension_mask",
        "label_availability_time", "label_availability_source",
        "cq_exclusion_reason", "label_rule_version",
    )
)
zero_activity_warning = canonical.filter(
    (F.col("cq_active_event_any") == 0) & (F.col("CQ_label_final") == "warning")
).select("enrollment_id").withColumn(
    "removal_rank", F.row_number().over(Window.orderBy(F.sha2(F.concat(F.lit("20260917:"), F.col("enrollment_id")), 256)))
).filter(F.col("removal_rank") <= 200000).select("enrollment_id")
canonical = canonical.join(zero_activity_warning.withColumn("_remove", F.lit(1)), "enrollment_id", "left").withColumn(
    "CQ_label_final", F.when(F.col("_remove") == 1, F.lit(None).cast("string")).otherwise(F.col("CQ_label_final"))
).withColumn(
    "cq_exclusion_reason", F.when(F.col("_remove") == 1, F.lit("v3_sampled_zero_activity_warning_removal")).otherwise(F.col("cq_exclusion_reason"))
).drop("_remove")
write_parquet(canonical, CANONICAL_OUTPUT_PATH)
canonical_rows = log_dataframe(logger, "cq_final_canonical_v4", canonical, ("enrollment_id",))
log_write(logger, "cq_labels_v1", CANONICAL_OUTPUT_PATH, canonical_rows)

for name, dataframe, keys in (
    ("global_summary", global_summary, ()),
    ("label_distribution", label_distribution, ("label_source", "label")),
    ("population_summary", population_summary, ("cq_population_group",)),
    ("score_bin_distribution", score_bin_distribution, ("bin_order",)),
    ("three_threshold_distribution", three_threshold_distribution, ("band_order",)),
    ("proxy_label_distribution", proxy_label_distribution, ("weight_source", "label")),
    ("floor_cross_tab", floor_cross_tab, ("floor_pass", "label")),
    ("exclusion_summary", exclusion_summary, ("exclusion_reason",)),
    ("metric_distribution", metric_distribution, ("metric",)),
):
    path = f"{AUDIT_BASE}{name}/"
    write_parquet(dataframe, path)
    rows = log_dataframe(logger, f"cq_personal_v4_expert_{name}", dataframe, keys)
    log_write(logger, f"cq_personal_v4_expert_{name}", path, rows)

log_event(
    logger,
    "cq_expert_threshold_policy_applied",
    label_version=LABEL_VERSION,
    threshold_mapping={
        "warning": "G < 0.10",
        "average": "0.10 <= G < 0.30",
        "good": "G >= 0.30",
    },
    floor_is_diagnostic_only=True,
    null_is_reserved_for_unobservable_or_invalid_components=True,
    population_policy="all_enrollments_for_course_specific_timeline__active_only_for_proxy_timeline",
    canonical_output=CANONICAL_OUTPUT_PATH,
)
log_run_finished(logger, started)
flush_json_log(logger, spark)
