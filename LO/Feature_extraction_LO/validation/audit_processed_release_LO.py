"""Create a lockable inventory, checksum manifest and unified exclusion log.

Run this after all clean/temporal/feature/label stages and before model
training.  It never rewrites source tables; it writes a new release-audit
artifact under the configured output base.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = os.environ.get("PROJECT_ROOT")
if not PROJECT_ROOT or not (Path(PROJECT_ROOT) / "common").is_dir():
    _candidates = list(Path("/Workspace/Users").glob("*/LO/Feature_extraction_LO"))
    if len(_candidates) != 1 or not (_candidates[0] / "common").is_dir():
        raise RuntimeError("Set PROJECT_ROOT to the absolute LO/Feature_extraction_LO workspace path.")
    PROJECT_ROOT = str(_candidates[0])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from pyspark.sql import SparkSession, functions as F

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
RAW_BASE = PROTOCOL["raw_base"]
AUDIT_BASE = path_from_config(PROTOCOL, "release_audit")
CONTRACT_BASE = path_from_config(PROTOCOL, "contract_base")

spark = SparkSession.builder.appName("audit_processed_release").config(
    "spark.sql.session.timeZone", "UTC"
).getOrCreate()
logger = get_logger("audit_processed_release", path_from_config(PROTOCOL, "logs"))
log_run_context(logger, spark, {"audit_base": AUDIT_BASE, "protocol_version": PROTOCOL["version"]})
started = start_run_timer()


def safe_read(path):
    try:
        return spark.read.parquet(path), None
    except Exception as error:  # one missing optional table must remain visible
        return None, f"{type(error).__name__}: {str(error)[:240]}"


def recursive_volume_size(path):
    """Return byte size/file count using DBUtils; retain an explicit reason on failure."""
    try:
        from pyspark.dbutils import DBUtils

        dbutils = DBUtils(spark)
        stack = [path]
        byte_size = 0
        file_count = 0
        while stack:
            current = stack.pop()
            for item in dbutils.fs.ls(current):
                if item.path.endswith("/"):
                    stack.append(item.path)
                else:
                    byte_size += int(item.size)
                    file_count += 1
        return byte_size, file_count, None
    except Exception as error:
        return None, None, f"{type(error).__name__}: {str(error)[:240]}"


def content_manifest_sha256(path):
    """Hash sorted file hashes, avoiding driver reads of large source data."""
    try:
        files = spark.read.format("binaryFile").load(path).select(
            "path", F.sha2("content", 256).alias("file_sha256")
        )
        summary = files.agg(
            F.count("*").alias("file_count"),
            F.sha2(
                F.concat_ws(
                    "||",
                    F.sort_array(F.collect_list(F.concat_ws(":", "path", "file_sha256"))),
                ),
                256,
            ).alias("manifest_sha256"),
        ).first()
        return summary["manifest_sha256"], int(summary["file_count"]), None
    except Exception as error:
        return None, None, f"{type(error).__name__}: {str(error)[:240]}"


def profile_table(source_id, path, primary_keys, foreign_keys=()):
    dataframe, read_error = safe_read(path)
    byte_size, volume_file_count, size_error = recursive_volume_size(path)
    content_hash, hash_file_count, hash_error = content_manifest_sha256(path)
    if dataframe is None:
        return {
            "source_id": source_id,
            "path_or_uri": path,
            "format": "parquet",
            "primary_keys": list(primary_keys),
            "foreign_keys": list(foreign_keys),
            "status": "missing_or_unreadable",
            "read_error": read_error,
            "row_count": None,
            "byte_size": byte_size,
            "sha256": content_hash,
            "schema_hash": None,
            "checksum_error": hash_error or size_error,
        }
    schema = [{"name": field.name, "type": field.dataType.simpleString()} for field in dataframe.schema.fields]
    row_count = dataframe.count()
    key_count = None
    if primary_keys and all(key in dataframe.columns for key in primary_keys):
        key_count = dataframe.select(
            F.concat_ws("::", *[F.coalesce(F.col(key).cast("string"), F.lit("<NULL>")) for key in primary_keys]).alias("key")
        ).distinct().count()
    return {
        "source_id": source_id,
        "path_or_uri": path,
        "format": "parquet",
        "primary_keys": list(primary_keys),
        "foreign_keys": list(foreign_keys),
        "status": "profiled",
        "row_count": row_count,
        "distinct_primary_key_count": key_count,
        "byte_size": byte_size,
        "volume_file_count": volume_file_count,
        "sha256": content_hash,
        "hash_file_count": hash_file_count,
        "schema_hash": hashlib.sha256(json.dumps(schema, sort_keys=True).encode("utf-8")).hexdigest(),
        "schema": schema,
        "checksum_error": hash_error or size_error,
    }


table_specs = (
    ("enrollments", f"{OUTPUT_BASE}/enrollments/", ("enrollment_id",), ("user_id", "course_id")),
    ("course_resources_clean", f"{OUTPUT_BASE}/course_resources_clean/", ("course_id", "resource_id"), ("course_id",)),
    ("course_problem_catalog", f"{OUTPUT_BASE}/course_problem_catalog/", ("course_id", "problem_id"), ("course_id",)),
    ("video_events_clean", f"{OUTPUT_BASE}/video_events_clean/", ("enrollment_id", "resource_id", "event_time"), ("enrollment_id",)),
    ("problem_events_clean", f"{OUTPUT_BASE}/problem_events_clean/", ("enrollment_id", "problem_id", "event_time"), ("enrollment_id",)),
    ("comment_events_clean", path_from_config(PROTOCOL, "comment_events_clean") + "/", ("enrollment_id", "comment_id"), ("enrollment_id",)),
    ("cq_labels_v1", path_from_config(PROTOCOL, "cq_labels") + "/", ("enrollment_id",), ("enrollment_id",)),
    ("lo_labels_v1", path_from_config(PROTOCOL, "lo_labels") + "/", ("enrollment_id",), ("enrollment_id",)),
)
processed_inventory = [profile_table(*spec) for spec in table_specs]

# These paths are immutable raw inputs for the release.  Binary-file hashing
# applies the same deterministic manifest hash without loading content to the driver.
raw_specs = (
    ("raw_user", f"{RAW_BASE}/3/user.json"),
    ("raw_course", f"{RAW_BASE}/course.csv"),
    ("raw_course_limit", f"{RAW_BASE}/course_limit.csv"),
    ("raw_user_problem", f"{RAW_BASE}/3/user-problem.json"),
    ("raw_user_video", f"{RAW_BASE}/3/user-video.json"),
    ("raw_comment", f"{RAW_BASE}/3/comment.json"),
    ("raw_course_comment", f"{RAW_BASE}/3/course-comment.txt"),
    ("raw_score_structure", f"{RAW_BASE}/course_ScoreStruct.csv"),
)
raw_inventory = []
for source_id, path in raw_specs:
    byte_size, file_count, size_error = recursive_volume_size(path)
    checksum, hash_file_count, hash_error = content_manifest_sha256(path)
    raw_inventory.append({
        "source_id": source_id,
        "path_or_uri": path,
        "byte_size": byte_size,
        "volume_file_count": file_count,
        "sha256": checksum,
        "hash_file_count": hash_file_count,
        "checksum_error": hash_error or size_error,
    })


def optional_exclusion(path, source_name):
    dataframe, error = safe_read(path)
    if dataframe is None:
        return None, error
    columns = dataframe.columns
    return dataframe.select(
        F.lit(source_name).alias("exclusion_source"),
        F.col("scenario") if "scenario" in columns else F.lit(None).cast("string").alias("scenario"),
        F.col("enrollment_id") if "enrollment_id" in columns else F.lit(None).cast("string").alias("enrollment_id"),
        F.col("course_id") if "course_id" in columns else F.lit(None).cast("string").alias("course_id"),
        F.col("exclusion_reason") if "exclusion_reason" in columns else F.lit("source_specific_exclusion").alias("exclusion_reason"),
    ), None


exclusion_specs = (
    ("feature_scenarios", f"{path_from_config(PROTOCOL, 'feature_base')}/exclusion_log/"),
    ("course_score_structure", f"{OUTPUT_BASE}/course_score_structure_exclusion_log/"),
    ("comments_unmapped", path_from_config(PROTOCOL, "comment_unmapped") + "/"),
    ("comment_events", f"{OUTPUT_BASE}/comment_v2/comment_events_exclusion_log/"),
    ("video_events", f"{OUTPUT_BASE}/video_events_exclusion_log/"),
    ("problem_events", f"{OUTPUT_BASE}/problem_events_exclusion_log/"),
)
exclusion_frames = []
exclusion_errors = []
for source_name, path in exclusion_specs:
    frame, error = optional_exclusion(path, source_name)
    if frame is not None:
        exclusion_frames.append(frame)
    elif error:
        exclusion_errors.append({"source": source_name, "path": path, "error": error})

if exclusion_frames:
    unified_exclusion_log = exclusion_frames[0]
    for frame in exclusion_frames[1:]:
        unified_exclusion_log = unified_exclusion_log.unionByName(frame)
else:
    unified_exclusion_log = spark.createDataFrame(
        [], "exclusion_source string, scenario string, enrollment_id string, course_id string, exclusion_reason string"
    )
exclusion_path = f"{AUDIT_BASE}/exclusion_log/"
write_parquet(unified_exclusion_log, exclusion_path)
exclusion_rows = log_dataframe(logger, "unified_exclusion_log", unified_exclusion_log, ("exclusion_source", "exclusion_reason"))
log_write(logger, "unified_exclusion_log", exclusion_path, exclusion_rows)

release_id = f"{PROTOCOL['version']}__{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
manifest = {
    "data_release_id": release_id,
    "parent_release_id": None,
    "created_at_utc": datetime.now(timezone.utc).isoformat(),
    "schema_version": "scenario_phase_schema_v3",
    "feature_dictionary_version": "scenario_phase_features_v5_contract_audited",
    "cq_label_version": PROTOCOL["labels"]["cq_canonical_version"],
    "lo_label_version": PROTOCOL["labels"]["lo_version"],
    "phase_version": "phase_cutoff_calendar_proxy_v3_cumulative_prefix",
    "split_version": PROTOCOL["split_status"],
    "exclusion_log": exclusion_path,
    "raw_sources": raw_inventory,
    "processed_sources": processed_inventory,
    "exclusion_source_errors": exclusion_errors,
    "release_status": "locked" if all(item.get("sha256") for item in raw_inventory + processed_inventory) else "checksum_incomplete",
}

from pyspark.dbutils import DBUtils
dbutils = DBUtils(spark)
dbutils.fs.put(f"{AUDIT_BASE}/data_inventory.yaml", json.dumps(manifest, ensure_ascii=False, indent=2), True)
dbutils.fs.put(f"{AUDIT_BASE}/data_release_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2), True)
log_event(logger, "release_audit_written", release_id=release_id, release_status=manifest["release_status"])
log_run_finished(logger, started)
flush_json_log(logger, spark)
