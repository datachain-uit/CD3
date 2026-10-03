"""Build and audit the CQ feature dictionary required by QA23.

Run this after materializing phase views and before fitting an imputer.  The
audit uses only TRAIN/P4 and the continuous CQ proximity that produced the
final W/A/G label; neither the label nor a label-proxy is allowed to become an
imputer predictor in ``CQ_RAW_EARLY``.
"""
from __future__ import annotations

import argparse
import math
import re

from pyspark.sql import SparkSession, Window, functions as F


REGIMES = ("CQ_RAW_EARLY", "CQ_REDUCED_DIRECT", "CQ_EARLY_COMPONENT")
KEY_OR_CONTEXT = {
    "enrollment_id", "offering_id", "user_id", "course_id", "teacher_id", "school_id",
    "task", "window", "split", "split_id", "scenario", "temporal_block", "phase",
    "timeline_source", "label_availability_time", "label_availability_source",
    "label_rule_version", "cq_exclusion_reason", "proxy_exclusion_reason",
}
LABEL_PATTERNS = (
    r"^cq_label_", r"^(?:coelo|afelo|acelo)_final$",
    r"^triad_distance_final$", r"^cq_(?:distance|proximity|score_g)(?:_final)?$",
)
PROXY_PATTERNS = (
    (r"(?:catalog_)?coverage$|_coverage$", "coverage_of_catalog"),
    (r"score_fraction|correct_ratio|watch_ratio", "ratio_of_activity_or_score"),
    (r"video_ratio|problem_ratio", "triad_component_ratio"),
    (r"scaled_watch|watch_count_scaled|scaled_attempts", "triad_scaled_input"),
    (r"^(?:coelo|afelo|acelo|triad_distance)_", "partial_triad_component"),
)
EARLY_COMPONENT = re.compile(r"(?:coelo|afelo|acelo|triad_distance)_partial|(?:coelo|afelo|acelo)_p[1-4]", re.I)


def classify(name: str, data_type: str) -> tuple[str, int, str, str]:
    """Return role, is_label_proxy, proxy_rule and allowed regimes."""
    lower = name.lower()
    if lower in KEY_OR_CONTEXT or lower.endswith("_time") or lower.endswith("_date"):
        return "KEY_OR_CONTEXT", 0, "", ""
    if lower.endswith("_observed_mask") or "_observed_mask_" in lower or lower.startswith("missing__") or lower.startswith("phase_available"):
        return "MASK", 0, "", "|".join(REGIMES)
    if any(re.search(pattern, lower) for pattern in LABEL_PATTERNS):
        return "LABEL", 1, "label_or_triad_component", ""
    for pattern, reason in PROXY_PATTERNS:
        if re.search(pattern, lower):
            regime = "CQ_EARLY_COMPONENT" if EARLY_COMPONENT.search(lower) else "CQ_REDUCED_DIRECT"
            return "FEATURE", 1, reason, regime
    if data_type in {"boolean", "tinyint", "smallint", "int", "bigint", "float", "double"} or data_type.startswith("decimal"):
        return "FEATURE", 0, "", "CQ_RAW_EARLY"
    return "NON_NUMERIC", 0, "", ""


def normalised_mutual_information(frame) -> float:
    """NMI over 20 rank bins, matching the QA23 review signal.

    The grouped contingency table has at most 400 rows, so collecting this
    aggregate is safe even when the TRAIN/P4 source itself is large.
    """
    binned = frame.withColumn("x_bin", F.ntile(20).over(Window.orderBy("x"))).withColumn(
        "y_bin", F.ntile(20).over(Window.orderBy("y"))
    )
    cells = [(row["x_bin"], row["y_bin"], row["n"]) for row in binned.groupBy("x_bin", "y_bin").count().withColumnRenamed("count", "n").collect()]
    total = sum(n for _, _, n in cells)
    if total == 0:
        return float("nan")
    px, py = {}, {}
    for x_bin, y_bin, n in cells:
        px[x_bin] = px.get(x_bin, 0) + n
        py[y_bin] = py.get(y_bin, 0) + n
    mi = sum(
        (n / total) * math.log((n * total) / (px[x_bin] * py[y_bin]))
        for x_bin, y_bin, n in cells if n
    )
    hx = -sum((n / total) * math.log(n / total) for n in px.values() if n)
    hy = -sum((n / total) * math.log(n / total) for n in py.values() if n)
    return mi / math.sqrt(hx * hy) if hx > 0 and hy > 0 else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description="QA23 CQ label-proxy audit")
    parser.add_argument("--input", required=True, help="Materialized phase-view parquet root")
    parser.add_argument("--output", required=True, help="Output root for dictionary and audit tables")
    parser.add_argument("--label-score", default="CQ_proximity_final")
    parser.add_argument("--phase", default="P4")
    parser.add_argument("--split", default="train")
    parser.add_argument("--rho-threshold", type=float, default=0.50)
    parser.add_argument(
        "--reviewed-column", action="append", default=[],
        help="Column reviewed by an owner despite exceeding the rho threshold; repeat per column.",
    )
    args = parser.parse_args()

    spark = SparkSession.builder.appName("audit_cq_label_proxy_qa23").getOrCreate()
    source = spark.read.parquet(args.input)
    if args.label_score not in source.columns:
        raise ValueError(f"Missing label score column: {args.label_score}")
    if "phase" not in source.columns or "split" not in source.columns:
        raise ValueError("QA23 needs phase and split columns in the materialized view")

    dictionary_rows = []
    for field in source.schema.fields:
        role, is_proxy, rule, regimes = classify(field.name, field.dataType.simpleString())
        dictionary_rows.append((field.name, field.dataType.simpleString(), role, is_proxy, rule, regimes))
    dictionary = spark.createDataFrame(
        dictionary_rows,
        "column_name string, data_type string, role string, is_label_proxy int, proxy_rule string, regimes_included string",
    ).withColumn("feature_dictionary_version", F.lit("feature_dictionary_v1"))

    audit_source = source.filter(
        (F.col("phase") == F.lit(args.phase))
        & (F.lower(F.col("split")) == F.lit(args.split.lower()))
        & F.col(args.label_score).isNotNull()
    )
    feature_rows = dictionary.filter(F.col("role") == "FEATURE").collect()
    audit_frames = []
    for feature in feature_rows:
        column = feature["column_name"]
        # Pearson-free Spearman is calculated with Spark's rank primitive.
        # corr(rank(x), rank(y)) is Spearman rho, and leaves null values out.
        paired = audit_source.select(
            F.col(column).cast("double").alias("x"), F.col(args.label_score).cast("double").alias("y")
        ).where(F.col("x").isNotNull() & F.col("y").isNotNull())
        ranked = paired.select(
            F.percent_rank().over(Window.orderBy("x")).alias("rx"),
            F.percent_rank().over(Window.orderBy("y")).alias("ry"),
        )
        nmi = normalised_mutual_information(paired)
        audit_frames.append(
            ranked.agg(F.count("rx").alias("n_obs"), F.corr("rx", "ry").alias("spearman_rho"))
            .withColumn("column_name", F.lit(column))
            .withColumn("is_label_proxy", F.lit(feature["is_label_proxy"]))
            .withColumn("proxy_rule", F.lit(feature["proxy_rule"]))
            .withColumn("nmi", F.lit(nmi))
        )
    if not audit_frames:
        raise ValueError("No numeric CQ features were found for QA23")
    audit = audit_frames[0]
    for frame in audit_frames[1:]:
        audit = audit.unionByName(frame)
    reviewed = set(args.reviewed_column)
    audit = audit.withColumn("spearman_abs", F.abs("spearman_rho")).withColumn(
        "needs_review",
        (F.col("spearman_abs") >= F.lit(args.rho_threshold)) & (F.col("is_label_proxy") == 0),
    ).withColumn(
        "proxy_review_note",
        F.when(F.col("column_name").isin(sorted(reviewed)), F.lit("reviewed_by_owner")),
    ).withColumn("rho_threshold", F.lit(args.rho_threshold))

    predictors = dictionary.filter(
        (F.col("regimes_included").contains("CQ_RAW_EARLY")) & (F.col("is_label_proxy") == 0)
    ).select("column_name")
    proxy_predictors = predictors.join(
        dictionary.filter(F.col("is_label_proxy") == 1).select("column_name"), "column_name", "inner"
    )
    summary = audit.agg(
        F.count("*").alias("audited_feature_count"),
        F.sum(F.when(F.col("needs_review") & F.col("proxy_review_note").isNull(), 1).otherwise(0)).alias("unreviewed_proxy_count"),
    ).crossJoin(proxy_predictors.agg(F.count("*").alias("proxy_in_imputer_predictors"))).withColumn(
        "qa23_ok",
        (F.col("unreviewed_proxy_count") == 0) & (F.col("proxy_in_imputer_predictors") == 0),
    )

    dictionary.write.mode("overwrite").parquet(f"{args.output}/feature_dictionary_v1")
    audit.write.mode("overwrite").parquet(f"{args.output}/label_proxy_audit")
    predictors.write.mode("overwrite").parquet(f"{args.output}/imputer_predictors_cq_raw_early")
    summary.write.mode("overwrite").parquet(f"{args.output}/qa23_summary")


if __name__ == "__main__":
    main()
