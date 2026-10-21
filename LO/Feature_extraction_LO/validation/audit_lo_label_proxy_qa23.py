"""QA23 audit for LO V3.1 catalog-normalised final-score label.

The active phase views are wide.  For each requested prediction phase this
audit exposes only P1..Pk feature variants, measures Spearman/NMI against the
persisted ``performance_score``, and verifies that every registered current-
grade/final-score proxy is excluded from LO model and imputer predictors.
"""
from __future__ import annotations

import argparse
import math
import re

from pyspark.sql import SparkSession, Window, functions as F


KEY_OR_CONTEXT = {
    "enrollment_id", "offering_id", "user_id", "course_id", "teacher_id", "school_id",
    "task", "window", "split", "split_id", "scenario", "temporal_block", "timeline_source",
    "label_availability_time", "label_availability_source", "label_rule_version",
    "label_threshold_set", "proxy_exclusion_reason", "decision", "proxy_reason",
}
LABEL_COLUMNS = {"LO_performance_label_3", "LO_performance_label_5"}
CURRENT_GRADE_BASES = {
    "performance_score", "video_weight", "assignment_weight", "exam_weight", "course_weight_total",
    "watched_videos", "video_counts", "watch_percent", "video_catalog_coverage",
    "problem_catalog_coverage", "problem_score_catalog_coverage", "assignment_problem_catalog_count",
    "assignment_best_correct_sum", "assignment_ratio_catalog", "exam_problem_catalog_count",
    "exam_best_correct_sum", "exam_ratio_catalog", "tempo_legacy_unclipped_score",
    "tempo_legacy_score_clipped",
}


def base_name(column: str) -> str:
    return re.sub(r"_P[1-4]$", "", column)


def visible_at_phase(column: str, phase_index: int) -> bool:
    match = re.search(r"_P([1-4])$", column)
    return match is None or int(match.group(1)) <= phase_index


def classify(column: str, data_type: str) -> tuple[str, int, str]:
    lower = column.lower()
    base = base_name(column)
    if column in KEY_OR_CONTEXT or lower.endswith("_time") or lower.endswith("_date"):
        return "KEY_OR_CONTEXT", 0, ""
    if column in LABEL_COLUMNS or lower.startswith("lo_performance_label"):
        return "LABEL", 1, "label_or_final_score"
    if base in CURRENT_GRADE_BASES:
        return "FEATURE", 1, "registered_current_grade_or_final_score_proxy"
    if lower.endswith("_observed_mask") or "_observed_mask_" in lower or lower.startswith("missing__") or lower.startswith("phase_available"):
        return "MASK", 0, ""
    if data_type in {"boolean", "tinyint", "smallint", "int", "bigint", "float", "double"} or data_type.startswith("decimal"):
        return "FEATURE", 0, ""
    return "NON_NUMERIC", 0, ""


def normalised_mutual_information(frame) -> float:
    binned = frame.withColumn("x_bin", F.ntile(20).over(Window.orderBy("x"))).withColumn(
        "y_bin", F.ntile(20).over(Window.orderBy("y"))
    )
    cells = [(row["x_bin"], row["y_bin"], row["n"])
             for row in binned.groupBy("x_bin", "y_bin").count().withColumnRenamed("count", "n").collect()]
    total = sum(n for _, _, n in cells)
    if total == 0:
        return float("nan")
    px, py = {}, {}
    for x_bin, y_bin, n in cells:
        px[x_bin] = px.get(x_bin, 0) + n
        py[y_bin] = py.get(y_bin, 0) + n
    mi = sum((n / total) * math.log((n * total) / (px[x_bin] * py[y_bin]))
             for x_bin, y_bin, n in cells if n)
    hx = -sum((n / total) * math.log(n / total) for n in px.values() if n)
    hy = -sum((n / total) * math.log(n / total) for n in py.values() if n)
    return mi / math.sqrt(hx * hy) if hx > 0 and hy > 0 else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description="QA23 LO final-score/current-grade proxy audit")
    parser.add_argument("--input", required=True, help="Wide materialized LO phase-view root")
    parser.add_argument("--output", required=True, help="Output root for one requested phase")
    parser.add_argument("--phase", default="P4")
    parser.add_argument("--split", default="train")
    parser.add_argument("--rho-threshold", type=float, default=0.50)
    args = parser.parse_args()
    match = re.fullmatch(r"P([1-4])", args.phase.upper())
    if not match:
        raise ValueError("--phase must be P1, P2, P3, or P4")
    phase_index = int(match.group(1))

    spark = SparkSession.builder.appName("audit_lo_label_proxy_qa23").getOrCreate()
    source = spark.read.parquet(args.input)
    if "split" not in source.columns or "performance_score" not in source.columns:
        raise ValueError("QA23 LO requires split and performance_score in materialized views")
    audit_source = source.filter(
        (F.lower(F.col("split")) == F.lit(args.split.lower())) & F.col("performance_score").isNotNull()
    )
    rows = []
    for field in source.schema.fields:
        role, is_proxy, rule = classify(field.name, field.dataType.simpleString())
        rows.append((field.name, field.dataType.simpleString(), role, is_proxy, rule,
                     int(visible_at_phase(field.name, phase_index))))
    dictionary = spark.createDataFrame(rows, "column_name string, data_type string, role string, is_label_proxy int, proxy_rule string, visible_at_phase int")

    audit_frames = []
    for feature in dictionary.filter((F.col("role") == "FEATURE") & (F.col("visible_at_phase") == 1)).collect():
        column = feature["column_name"]
        paired = audit_source.select(F.col(column).cast("double").alias("x"), F.col("performance_score").cast("double").alias("y")).where(
            F.col("x").isNotNull() & F.col("y").isNotNull()
        )
        ranked = paired.select(F.percent_rank().over(Window.orderBy("x")).alias("rx"), F.percent_rank().over(Window.orderBy("y")).alias("ry"))
        audit_frames.append(ranked.agg(F.count("rx").alias("n_obs"), F.corr("rx", "ry").alias("spearman_rho"))
                            .withColumn("column_name", F.lit(column))
                            .withColumn("is_label_proxy", F.lit(feature["is_label_proxy"]))
                            .withColumn("proxy_rule", F.lit(feature["proxy_rule"]))
                            .withColumn("nmi", F.lit(normalised_mutual_information(paired))))
    if not audit_frames:
        raise ValueError("No visible numeric LO features were found for QA23")
    audit = audit_frames[0]
    for frame in audit_frames[1:]:
        audit = audit.unionByName(frame)
    audit = audit.withColumn("spearman_abs", F.abs("spearman_rho")).withColumn(
        "needs_review", (F.col("spearman_abs") >= F.lit(args.rho_threshold)) & (F.col("is_label_proxy") == 0)
    ).withColumn("rho_threshold", F.lit(args.rho_threshold)).withColumn("phase_id", F.lit(args.phase.upper()))

    predictors = dictionary.filter(
        (F.col("role") == "FEATURE") & (F.col("visible_at_phase") == 1) & (F.col("is_label_proxy") == 0)
    ).select("column_name").withColumn("phase_id", F.lit(args.phase.upper()))
    proxy_in_predictors = predictors.join(
        dictionary.filter(F.col("is_label_proxy") == 1).select("column_name"), "column_name", "inner"
    )
    summary = audit.agg(
        F.count("*").alias("audited_feature_count"),
        F.sum(F.when(F.col("needs_review"), 1).otherwise(0)).alias("unreviewed_high_rho_nonproxy_count"),
        F.sum(F.when(F.col("is_label_proxy") == 1, 1).otherwise(0)).alias("registered_proxy_feature_count"),
    ).crossJoin(proxy_in_predictors.agg(F.count("*").alias("proxy_in_model_or_imputer_predictors"))).withColumn(
        "qa23_ok", (F.col("proxy_in_model_or_imputer_predictors") == 0)
    ).withColumn("phase_id", F.lit(args.phase.upper())).withColumn(
        "label_contract", F.lit("catalog_normalized_activity_derived_final_score")
    )

    dictionary.withColumn("phase_id", F.lit(args.phase.upper())).write.mode("overwrite").parquet(f"{args.output}/feature_dictionary")
    audit.write.mode("overwrite").parquet(f"{args.output}/label_proxy_audit")
    predictors.write.mode("overwrite").parquet(f"{args.output}/model_imputer_predictors")
    summary.write.mode("overwrite").parquet(f"{args.output}/qa23_summary")


if __name__ == "__main__":
    main()
