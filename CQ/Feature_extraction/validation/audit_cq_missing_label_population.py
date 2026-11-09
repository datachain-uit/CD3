"""Reconstruct CQ population selection and reconcile it with the label artifact.

Read-only sources; writes only aggregates to a new M07_CQ_AUDIT_OUTPUT path.
This reconstructs using sources currently available, not necessarily historical
inputs. Review cross-source offering overlaps and unexpected mismatch groups.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from pyspark.sql import SparkSession, functions as F

BASE = "/Volumes/workspace/default/preprocessed"
paths = {
    "enrollments": os.environ.get("M07_CQ_ENROLLMENTS", f"{BASE}/enrollments"),
    "labels": os.environ.get("M07_CQ_LABELS", f"{BASE}/labels/cq_labels_v1"),
    "timeline": os.environ.get("M07_CQ_TIMELINE", f"{BASE}/split_analysis/shifted_offering_assignments"),
    "anchored": os.environ.get("M07_CQ_ANCHORED", f"{BASE}/split_analysis/enrollment_anchored_pseudo_offering_assignments"),
    "global": os.environ.get("M07_CQ_GLOBAL", f"{BASE}/split_analysis/global_template_offering_assignments"),
    "video": os.environ.get("M07_CQ_VIDEO", f"{BASE}/video_events_clean"),
    "problem": os.environ.get("M07_CQ_PROBLEM", f"{BASE}/problem_events_clean"),
    "comment": os.environ.get("M07_CQ_COMMENT", f"{BASE}/comment_v1/comment_events_clean"),
}
outpath = os.environ.get("M07_CQ_AUDIT_OUTPUT", "")
if not outpath.startswith("/Volumes/") or Path(outpath).exists():
    raise ValueError("Set M07_CQ_AUDIT_OUTPUT to a new absolute /Volumes/... directory")
for name, path in paths.items():
    if not path.startswith("/Volumes/") or not Path(path).exists():
        raise ValueError(f"Missing or invalid {name} source: {path}")
spark = SparkSession.builder.getOrCreate()
# Match the label builder, including date-to-timestamp conversion.
spark.conf.set("spark.sql.session.timeZone", "UTC")
frames = {name: spark.read.parquet(path) for name, path in paths.items()}


def require(name, columns):
    missing = sorted(set(columns).difference(frames[name].columns))
    if missing:
        raise ValueError(f"{name} missing columns {missing}; actual: {frames[name].columns}")


require("enrollments", ["enrollment_id", "enroll_time"])
require("labels", ["enrollment_id"])
require("timeline", ["enrollment_id", "offering_id", "offering_end_date"])
require("anchored", ["enrollment_id", "pseudo_offering_id", "pseudo_end_date"])
require("global", ["enrollment_id", "offering_id", "offering_end_date"])
for name in ("video", "problem", "comment"):
    require(name, ["enrollment_id"])
require("video", ["event_time"])
require("comment", ["event_time"])
if not {"availability_time", "submit_time"}.intersection(frames["problem"].columns):
    raise ValueError("problem source requires availability_time or submit_time")

enroll = frames["enrollments"].select("enrollment_id", F.to_timestamp("enroll_time").alias("enroll_time"))
label_ids = frames["labels"].select("enrollment_id").distinct().withColumn("has_label", F.lit(True))
e_counts = enroll.agg(F.count("*").alias("rows"), F.countDistinct("enrollment_id").alias("ids"),
                      F.sum(F.when(F.col("enrollment_id").isNull(), 1).otherwise(0)).alias("nulls")).first()
if e_counts["nulls"] or e_counts["rows"] != e_counts["ids"]:
    raise ValueError(f"Enrollment source must have one non-null row per ID; got {e_counts}")
timeline = frames["timeline"].select("enrollment_id", "offering_id", "offering_end_date").withColumn("source", F.lit("timeline"))
anchored = (frames["anchored"].select("enrollment_id", F.col("pseudo_offering_id").alias("offering_id"),
                                      F.col("pseudo_end_date").alias("offering_end_date"))
            .withColumn("source", F.lit("anchored"))
            .join(timeline.select("enrollment_id"), "enrollment_id", "left_anti"))
# The builder excludes anchored IDs here, but does not anti-join timeline IDs.
global_off = (frames["global"].select("enrollment_id", "offering_id", "offering_end_date")
              .withColumn("source", F.lit("global"))
              .join(anchored.select("enrollment_id"), "enrollment_id", "left_anti"))
offerings = timeline.unionByName(anchored).unionByName(global_off)
spine = (enroll.join(offerings, "enrollment_id", "inner")
         .withColumn("offering_end_exclusive", F.to_timestamp(F.date_add("offering_end_date", 1))))


def event_ids(name):
    events = frames[name]
    if name == "problem":
        t = (F.coalesce(F.to_timestamp("availability_time"), F.to_timestamp("submit_time"))
             if {"availability_time", "submit_time"}.issubset(events.columns)
             else F.to_timestamp("availability_time" if "availability_time" in events.columns else "submit_time"))
    else:
        t = F.col("event_time")
    events = events.select("enrollment_id", t.alias("availability_time"))
    return (events.join(spine.select("enrollment_id", "enroll_time", "offering_end_exclusive"), "enrollment_id", "inner")
            .where((F.col("availability_time") >= F.col("enroll_time")) &
                   (F.col("availability_time") < F.col("offering_end_exclusive")))
            .select("enrollment_id").distinct())


active = event_ids("video").unionByName(event_ids("problem")).unionByName(event_ids("comment")).distinct()
off_flags = offerings.groupBy("enrollment_id").agg(
    F.count("*").alias("offering_rows"),
    F.max(F.when(F.col("source") == "timeline", 1).otherwise(0)).alias("has_timeline"),
    F.max(F.when(F.col("source") != "timeline", 1).otherwise(0)).alias("has_proxy"))
base = (enroll.select("enrollment_id").join(off_flags, "enrollment_id", "left")
        .join(active.withColumn("has_activity", F.lit(True)), "enrollment_id", "left")
        .join(label_ids, "enrollment_id", "left")
        .fillna({"has_label": False, "has_activity": False, "has_timeline": 0, "has_proxy": 0, "offering_rows": 0})
        .withColumn("expected_selected", (F.col("has_timeline") == 1) | ((F.col("has_proxy") == 1) & F.col("has_activity")))
        .withColumn("category", F.when(F.col("has_label") & F.col("expected_selected"), "LABEL_PRESENT_EXPECTED_SELECTED")
                    .when(F.col("has_label"), "LABEL_PRESENT_UNEXPECTED_BY_RECONSTRUCTION")
                    .when(F.col("offering_rows") == 0, "NO_OFFERING")
                    .when(~F.col("expected_selected"), "PROXY_WITHOUT_IN_WINDOW_ACTIVITY")
                    .otherwise("EXPECTED_SELECTED_BUT_LABEL_MISSING")))
counts = [x.asDict() for x in base.groupBy("category").count().orderBy("category").collect()]
checks = base.agg(F.count("*").alias("enrollments"),
                  F.sum(F.when(~F.col("has_label"), 1).otherwise(0)).alias("missing_labels"),
                  F.sum(F.when(F.col("offering_rows") > 1, 1).otherwise(0)).alias("multiple_offering_rows_ids"),
                  F.sum(F.when((F.col("has_timeline") == 1) & (F.col("has_proxy") == 1), 1).otherwise(0)).alias("timeline_proxy_overlap_ids")).first().asDict()
checks["label_ids_outside_enrollments"] = label_ids.join(enroll.select("enrollment_id"), "enrollment_id", "left_anti").count()
summary = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "sources": paths, "checks": checks,
           "categories": counts, "expected_previous_missing_labels": 8614884,
           "matches_previous_missing_count": checks["missing_labels"] == 8614884,
           "limitations": ["Reconstruction from current sources; not proof these were the exact historical inputs.",
                           "Comment source must match the configuration used for the historical label build.",
                           "Activity is any valid event in any reconstructed offering for the enrollment, as in the builder.",
                           "Expected-selected but missing labels and label-present unexpected groups require investigation."]}
out = Path(outpath)
out.mkdir(parents=True, exist_ok=False)
(out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
(out / "_SUCCESS").write_text("completed\n", encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
print(f"[M07_CQ] COMPLETE: {out}", flush=True)
