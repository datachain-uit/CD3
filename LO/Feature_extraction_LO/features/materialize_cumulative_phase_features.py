"""Pivot long P1--P4 feature rows into leakage-safe cumulative wide snapshots.

It emits one complete wide row per enrollment: dynamic features are retained
as ``<feature>_P1`` through ``<feature>_P4`` while static context occurs once.
Test-prefix masking is deliberately performed only after the window split.
Run this after the long feature builder and before the task split materializer;
the long source is not modified.
"""
import os
import sys
from pathlib import Path

PROJECT_ROOT = os.environ.get("PROJECT_ROOT")
if not PROJECT_ROOT or not (Path(PROJECT_ROOT) / "common").is_dir():
    candidates = list(Path("/Workspace/Users").glob("*/LO/Feature_extraction_LO"))
    if len(candidates) != 1:
        raise RuntimeError("Set PROJECT_ROOT to the LO/Feature_extraction_LO workspace path.")
    PROJECT_ROOT = str(candidates[0])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from pyspark.sql import SparkSession, functions as F
from common.pipeline_logging import flush_json_log, get_logger, log_dataframe, log_event, log_run_context, log_run_finished, log_write, start_run_timer, write_parquet
from common.protocol_config import load_protocol_config, path_from_config

P = load_protocol_config()
BASE = P["output_base"].rstrip("/")
SCENARIO = os.environ.get("CUMULATIVE_SCENARIO", "hybrid")
SOURCE = os.environ.get("CUMULATIVE_FEATURE_SOURCE", f"{BASE}/features/scenarios/{SCENARIO}/merged_phase_features/").rstrip("/")
OUTPUT = os.environ.get("CUMULATIVE_FEATURE_OUTPUT", f"{BASE}/features/scenarios/{SCENARIO}/cumulative_phase_features_v1/").rstrip("/")
PHASES = ("P1", "P2", "P3", "P4")
KEYS = ("scenario", "enrollment_id", "user_id", "course_id", "temporal_block", "timeline_source")
STATIC = (
    "window_end_exclusive", "window_duration_seconds", "gender", "year_of_birth", "age_at_enroll",
    "resource_count", "video_counts", "ex_counts", "teacher_count", "teacher_bio_coverage",
    "teacher_avg_bio_length_chars", "teacher_org_count", "school_count", "school_bio_coverage",
    "school_avg_bio_length_chars", "school_motto_coverage", "school_avg_motto_length_chars",
)

spark = SparkSession.builder.appName("materialize_cumulative_phase_features_v1").getOrCreate()
logger = get_logger("materialize_cumulative_phase_features_v1", path_from_config(P, "logs"))
started = start_run_timer()
log_run_context(logger, spark, {"source": SOURCE, "output": OUTPUT, "scenario": SCENARIO, "phases": PHASES})

source = spark.read.parquet(SOURCE)
required = (*KEYS, "phase", "cutoff_time")
missing = [name for name in required if name not in source.columns]
if missing:
    raise ValueError(f"Long feature source is missing required columns: {missing}")
source = source.filter(F.col("phase").isin(*PHASES))
types = {field.name: field.dataType for field in source.schema.fields}
static = tuple(name for name in STATIC if name in types)
excluded = set(KEYS) | set(static) | {"phase", "cutoff_time"}
phase_features = tuple(name for name in source.columns if name not in excluded)

aggregates = [F.max(F.col(name)).alias(name) for name in static]
for name in phase_features:
    for phase in PHASES:
        aggregates.append(F.max(F.when(F.col("phase") == phase, F.col(name))).alias(f"{name}_{phase}"))
for phase in PHASES:
    aggregates.append(F.max(F.when(F.col("phase") == phase, F.col("cutoff_time"))).alias(f"_cutoff_{phase}"))
wide_all = source.groupBy(*KEYS).agg(*aggregates)

columns = [F.col(name) for name in (*KEYS, *static)]
columns += [F.col(f"_cutoff_{phase}").alias(f"cutoff_time_{phase}") for phase in PHASES]
columns += [F.lit(1).alias(f"phase_available_{phase}") for phase in PHASES]
columns += [F.col(f"{name}_{phase}") for name in phase_features for phase in PHASES]
wide = wide_all.select(*columns)
write_parquet(wide, OUTPUT)
rows = log_dataframe(logger, "cumulative_phase_features_v1", wide, ("enrollment_id",))
log_write(logger, "cumulative_phase_features_v1", OUTPUT, rows)
log_event(logger, "cumulative_phase_features_materialized", source=SOURCE, output=OUTPUT)
log_run_finished(logger, started)
flush_json_log(logger, spark)
