"""Recompute CQ COELO/AFELO/ACELO from events available up to each phase cutoff (F0 CQ_PARTIAL_TRIAD input).

Runs the unchanged production component builder (labels/cq_component_builder.py) with ONE change in its
source text: events are kept only if availability_time is before enroll + q * (offering_end_exclusive - enroll),
with q = 0.25, 0.5, 0.75, 0.9 for P1-P4 (the cutoff rule observed in phase_views_v2_2) and q = 1.0 as the
self-check. All outputs go to a new scratch directory; production label, audit and log paths are replaced.

Validation built in: level FINAL (q = 1.0) must reproduce the production component artifact exactly
(max absolute difference of COELO/AFELO/ACELO and row-count parity are written to final_check.json).
If FINAL does not match, do not use P1-P4 outputs.

Environment:
  PROJECT_ROOT          absolute path of the directory containing common/ (CQ/Feature_extraction)
  F0_OUTPUT             NEW absolute /Volumes/... directory (must not exist)
  F0_COMMENT_EVENTS     optional absolute path of the comment events to read instead of the protocol-config path
                        (use when the config points to a missing comment_v1 directory; recorded in the manifest)
  TEMPO_OUTPUT_BASE     absolute /Volumes/... base of the preprocessed tables (e.g. /Volumes/workspace/default/preprocessed)
  TEMPO_RAW_BASE        absolute /Volumes/... base that holds course_limit.csv
  F0_REUSE_COMPONENTS   optional "1": if <F0_OUTPUT>/<level>/components already exists (builder finished, only the f0_components write failed), skip the builder
  F0_ACELO_RULE         with_comment (default, reproduces labels/cq_personal_v3) or video_problem_only (current repo builder)
  F0_APPEND             optional "1": reuse an existing F0_OUTPUT to add levels; a level directory that already exists is never overwritten
  F0_LEVELS             optional, comma list from FINAL,P1,P2,P3,P4 (default: all, FINAL first)
  F0_PRODUCTION_ARTIFACT optional path of the production component artifact for the FINAL check
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

LEVELS = {"FINAL": 1.0, "P1": 0.25, "P2": 0.5, "P3": 0.75, "P4": 0.9}
OUT = os.environ.get("F0_OUTPUT", "")
APPEND = os.environ.get("F0_APPEND") == "1"
if not OUT.startswith("/Volumes/") or (Path(OUT).exists() and not APPEND):
    raise ValueError("Set F0_OUTPUT to a new absolute /Volumes/... directory (or an existing one with F0_APPEND=1 to add levels)")
requested = [x.strip() for x in os.environ.get("F0_LEVELS", "FINAL,P1,P2,P3,P4").split(",") if x.strip()]
if not requested or any(x not in LEVELS for x in requested):
    raise ValueError(f"F0_LEVELS must be a subset of {list(LEVELS)}")
root = os.environ.get("PROJECT_ROOT")
if not root or not (Path(root) / "labels" / "cq_component_builder.py").is_file():
    raise ValueError("PROJECT_ROOT must contain labels/cq_component_builder.py")
builder = (Path(root) / "labels" / "cq_component_builder.py").read_text(encoding="utf-8")
# The tracked config uses relative storage roots; the deployment must supply absolute ones.
for key in ("TEMPO_OUTPUT_BASE", "TEMPO_RAW_BASE"):
    value = os.environ.get(key, "")
    if not value.startswith("/Volumes/") or not Path(value).is_dir():
        raise ValueError(f"Set {key} to an existing absolute /Volumes/... directory (got {value!r})")
OUTPUT_BASE_ENV, RAW_BASE_ENV = os.environ["TEMPO_OUTPUT_BASE"].rstrip("/"), os.environ["TEMPO_RAW_BASE"].rstrip("/")
missing = [x for x in (f"{RAW_BASE_ENV}/course_limit.csv", f"{OUTPUT_BASE_ENV}/enrollments", f"{OUTPUT_BASE_ENV}/video_events_clean",
                       f"{OUTPUT_BASE_ENV}/problem_events_clean", f"{OUTPUT_BASE_ENV}/course_problem_catalog",
                       f"{OUTPUT_BASE_ENV}/course_summary", f"{OUTPUT_BASE_ENV}/course_score_structure_summary",
                       f"{OUTPUT_BASE_ENV}/split_analysis/shifted_offering_assignments") if not Path(x).exists()]
if missing:
    raise ValueError("Missing builder inputs under the configured bases: " + ", ".join(missing))


import re
CUTOFF_EXPR = ('(F.unix_timestamp("label_enroll_time") + F.lit(F0_Q) * '
               '(F.unix_timestamp("offering_end_exclusive") - F.unix_timestamp("label_enroll_time"))).cast("timestamp")')
# Each pattern must match exactly once in the builder; otherwise print the candidate lines and stop.
PATCHES = [
    ("event window end", re.compile(r'&\s*\(F\.col\("availability_time"\)\s*<\s*F\.col\("offering_end_exclusive"\)\)'),
     lambda m: m.group(0) + ' & ((F.col("availability_time") < ' + CUTOFF_EXPR + ') if F0_Q < 1.0 else F.lit(True))', "availability_time"),
    ("audit path", re.compile(r'^audit_path\s*=.*$', re.M), lambda m: 'audit_path = F0_AUDIT_PATH', "audit_path"),
    ("logger", re.compile(r'^logger\s*=\s*get_logger\(.*$', re.M), lambda m: 'logger = get_logger("build_cq_partial", F0_LOG_PATH)', "get_logger"),
]

# Production rule (verified: 0 mismatches on 3,180,020 rows of labels/cq_personal_v3): ACELO includes the configured
# comment weight, i.e. ACELO = (wv*video_watch_ratio + wp*problem_score_ratio + wc*comment_progress_ratio) / (wv+wp+wc).
# The current repo builder drops comments from ACELO; F0_ACELO_RULE=video_problem_only keeps that newer rule instead.
ACELO_RULE = os.environ.get("F0_ACELO_RULE", "with_comment")
if ACELO_RULE not in ("with_comment", "video_problem_only"):
    raise ValueError("F0_ACELO_RULE must be with_comment or video_problem_only")
ACELO_PATCHES = [
    ('.withColumn("observed_configured_comment_weight", F.lit(0.0))',
     '.withColumn("observed_configured_comment_weight", F.col("configured_comment_weight"))'),
    ('.withColumn("effective_comment_weight", F.lit(0.0))',
     '.withColumn("effective_comment_weight", F.when(F.col("observed_configured_weight_total") > 0, F.col("observed_configured_comment_weight")).otherwise(F.lit(0.0)))'),
    ('F.col("effective_video_weight") + F.col("effective_problem_weight"),\n    )',
     'F.col("effective_video_weight") + F.col("effective_problem_weight") + F.col("effective_comment_weight"),\n    )'),
    ('+ F.col("effective_problem_weight") * F.col("problem_score_ratio"),\n            F.col("effective_weight_total"),',
     '+ F.col("effective_problem_weight") * F.col("problem_score_ratio")\n            + F.col("effective_comment_weight") * F.coalesce(F.col("comment_progress_ratio"), F.lit(0.0)),\n            F.col("effective_weight_total"),'),
]
if ACELO_RULE == "with_comment":
    for old_text, _ in ACELO_PATCHES:
        if builder.count(old_text) != 1:
            raise RuntimeError(f"ACELO patch anchor matched {builder.count(old_text)} times (need 1): {old_text[:80]!r}")
    for old_text, new_text in ACELO_PATCHES:
        builder = builder.replace(old_text, new_text, 1)

COMMENT_PATH = os.environ.get("F0_COMMENT_EVENTS", "")
if COMMENT_PATH:
    if not COMMENT_PATH.startswith("/Volumes/") or not Path(COMMENT_PATH).exists():
        raise ValueError(f"F0_COMMENT_EVENTS does not exist: {COMMENT_PATH}")
    PATCHES.append(("comment source", re.compile(r'path_from_config\(PROTOCOL,\s*"comment_events_clean"\)'),
                    lambda m: 'F0_COMMENT_PATH', "comment_events_clean"))
for name, pattern, _, keyword in PATCHES:
    found = pattern.findall(builder)
    if len(found) != 1:
        candidates = [f"{i + 1}: {line.strip()[:160]}" for i, line in enumerate(builder.splitlines()) if keyword in line][:12]
        raise RuntimeError(f"Builder patch point {name!r} matched {len(found)} times (need 1). Candidate lines: " + " || ".join(candidates))

sys.path.insert(0, root)
import importlib
import common.protocol_config as _protocol_config
_protocol_config.load_protocol_config.cache_clear()          # a previous failed run in this kernel may have cached relative bases
_resolved = _protocol_config.load_protocol_config()
if not str(_resolved["output_base"]).startswith("/Volumes/") or not str(_resolved["raw_base"]).startswith("/Volumes/"):
    raise RuntimeError(f"Protocol bases are still relative after cache reset: output_base={_resolved['output_base']!r}, raw_base={_resolved['raw_base']!r}. "
                       "Restart Python (dbutils.library.restartPython()) and rerun.")
print("Resolved bases:", _resolved["output_base"], _resolved["raw_base"])

from pyspark.sql import SparkSession, functions as F

spark = SparkSession.builder.getOrCreate()
spark.conf.set("spark.sql.session.timeZone", "UTC")
os.makedirs(OUT, exist_ok=True)
manifest = {"started_utc": datetime.now(timezone.utc).isoformat(), "levels": {}, "builder_sha": None, "comment_events_path": COMMENT_PATH or "protocol_config_default", "acelo_rule": ACELO_RULE}
import hashlib
manifest["builder_sha"] = hashlib.sha256(builder.encode("utf-8")).hexdigest()

for level in requested:
    q = LEVELS[level]
    level_dir = f"{OUT}/{level}"
    patched = builder
    for _, pattern, repl, _ in PATCHES:
        patched = pattern.sub(repl, patched, count=1)
    os.environ["CQ_COMPONENT_OUTPUT"] = f"{level_dir}/components"
    namespace = {"__name__": "__f0_builder__", "PROJECT_ROOT": root, "F0_Q": q, "F0_AUDIT_PATH": f"{level_dir}/_builder_audit/", "F0_COMMENT_PATH": COMMENT_PATH, "F0_LOG_PATH": f"{level_dir}/_logs"}
    # The builder resolves PROJECT_ROOT from the environment when __file__ is absent.
    os.environ["PROJECT_ROOT"] = root
    sys.path.insert(0, root)
    reuse = os.environ.get("F0_REUSE_COMPONENTS") == "1" and Path(f"{level_dir}/components").is_dir() and not Path(f"{level_dir}/f0_components").exists()
    if reuse:
        print(f"Reusing existing builder output for {level}: {level_dir}/components")
    else:
        exec(compile(patched, f"cq_component_builder_{level}", "exec"), namespace)
    artifact = spark.read.parquet(f"{level_dir}/components/")
    keep = ["enrollment_id", "course_id", "cq_population_group", "label_valid", "COELO_personal", "AFELO_personal",
            "ACELO_personal", "video_event_count", "problem_count", "comment_count", "has_video_catalog", "has_problem_catalog",
            "effective_video_weight", "effective_problem_weight", "primary_label_source"]
    present = [c for c in keep if c in artifact.columns]
    artifact.select(*present).write.mode("error").parquet(f"{level_dir}/f0_components")
    manifest["levels"][level] = {"q": q, "rows": artifact.count(), "columns": present}

if "FINAL" in requested:
    prod_path = os.environ.get("F0_PRODUCTION_ARTIFACT")
    if not prod_path:
        from common.protocol_config import load_protocol_config, path_from_config
        protocol = load_protocol_config()
        try:
            prod_path = path_from_config(protocol, "cq_label_components")
        except KeyError:
            prod_path = f"{protocol['output_base'].rstrip('/')}/labels/cq_label_components_v1"
    prod = spark.read.parquet(prod_path.rstrip("/") + "/").select(
        "enrollment_id", F.col("COELO_personal").alias("p_c"), F.col("AFELO_personal").alias("p_a"), F.col("ACELO_personal").alias("p_l"))
    mine = spark.read.parquet(f"{OUT}/FINAL/f0_components").select(
        "enrollment_id", F.col("COELO_personal").alias("m_c"), F.col("AFELO_personal").alias("m_a"), F.col("ACELO_personal").alias("m_l"))
    joined = prod.join(mine, "enrollment_id", "full_outer")
    check = joined.agg(
        F.count("*").alias("rows_union"),
        F.sum(F.when(F.col("p_c").isNull() & F.col("p_a").isNull() & F.col("p_l").isNull(), 1).otherwise(0)).alias("only_in_rebuild"),
        F.sum(F.when(F.col("m_c").isNull() & F.col("m_a").isNull() & F.col("m_l").isNull(), 1).otherwise(0)).alias("only_in_production"),
        F.max(F.abs(F.col("p_c") - F.col("m_c"))).alias("max_abs_diff_coelo"),
        F.max(F.abs(F.col("p_a") - F.col("m_a"))).alias("max_abs_diff_afelo"),
        F.max(F.abs(F.col("p_l") - F.col("m_l"))).alias("max_abs_diff_acelo"),
    ).first().asDict()
    manifest["final_check"] = check
    manifest["final_check_pass"] = bool(
        check["only_in_rebuild"] == 0 and check["only_in_production"] == 0
        and all((check[k] or 0.0) <= 1e-9 for k in ("max_abs_diff_coelo", "max_abs_diff_afelo", "max_abs_diff_acelo")))
manifest["finished_utc"] = datetime.now(timezone.utc).isoformat()
Path(f"{OUT}/f0_manifest_{'_'.join(requested)}.json").write_text(json.dumps(manifest, indent=2, default=str) + "\n", encoding="utf-8")
print(json.dumps(manifest, indent=2, default=str))
