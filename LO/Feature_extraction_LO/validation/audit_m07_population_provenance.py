"""Read-only M-07 population and present-day manifest identity audit on Databricks.

Configure with M07_* environment variables; all outputs are new files under a
new directory. The optional raw input must be an independent enrollment source.
This audit does not establish historical identity without a prior trusted hash.
"""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from pyspark.sql import SparkSession, functions as F


BASE = "/Volumes/workspace/default/preprocessed"
SOURCES = {
    "processed_enrollments": os.environ.get("M07_ENROLLMENTS_SOURCE", f"{BASE}/enrollments"),
    "CQ_labels": os.environ.get("M07_CQ_LABELS_SOURCE", f"{BASE}/labels/cq_labels_v1"),
    "LO_labels": os.environ.get("M07_LO_LABELS_SOURCE", f"{BASE}/labels/lo_labels_v3_1_scored_signal_excluded"),
    "CQ_manifest": os.environ.get("M07_CQ_MANIFEST_SOURCE", f"{BASE}/tasks/CQ/hybrid/split_registry_v2_2_overlap_audit_v1_r2/manifest"),
    "LO_manifest": os.environ.get("M07_LO_MANIFEST_SOURCE", f"{BASE}/tasks/LO/hybrid/split_registry_v3_1_scored_signal_excluded_overlap_audit_v1/manifest"),
}
raw_path = os.environ.get("M07_RAW_ENROLLMENT_SOURCE", "").strip()
if raw_path:
    SOURCES["raw_enrollments"] = raw_path
output = os.environ.get("M07_AUDIT_OUTPUT", "").strip()
if not output or not output.startswith("/Volumes/"):
    raise ValueError("Set M07_AUDIT_OUTPUT to a new absolute /Volumes/... directory.")
for name, source in SOURCES.items():
    if not source.startswith("/Volumes/"):
        raise ValueError(f"{name} must be an absolute /Volumes/... path: {source}")
    if not Path(source).exists():
        raise FileNotFoundError(f"{name} does not exist: {source}")
out = Path(output)
if out.exists():
    raise FileExistsError(f"Output already exists; choose a new path: {out}")
spark = SparkSession.builder.getOrCreate()


def file_inventory(source, hash_contents):
    root = Path(source)
    files = [root] if root.is_file() else sorted(p for p in root.rglob("*") if p.is_file() and not p.name.startswith(("_", ".")))
    if not files:
        raise ValueError(f"No data files found: {source}")
    result = []
    for path in files:
        before = path.stat()
        item = {"path": path.name if root.is_file() else path.relative_to(root).as_posix(), "bytes": before.st_size}
        if hash_contents:
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                    digest.update(chunk)
            item["sha256"] = digest.hexdigest()
            after = path.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise RuntimeError(f"File changed while hashing: {path}")
        result.append(item)
    return result


def read_population(name, path, fmt="parquet", id_column="enrollment_id"):
    if fmt == "parquet":
        frame = spark.read.parquet(path)
    elif fmt == "csv":
        frame = spark.read.option("header", "true").csv(path)
    else:
        raise ValueError(f"Unsupported format for {name}: {fmt}; use parquet or csv")
    if id_column not in frame.columns:
        raise ValueError(f"{name} missing {id_column}; available columns: {frame.columns}")
    return frame, frame.select(F.col(id_column).cast("string").alias("enrollment_id"))


def population_summary(name, ids):
    row = ids.agg(F.count(F.lit(1)).alias("rows"),
                  F.sum(F.when(F.col("enrollment_id").isNull(), 1).otherwise(0)).alias("null_id_rows"),
                  F.countDistinct("enrollment_id").alias("distinct_nonnull_ids")).first().asDict()
    row["null_id_rows"] = row["null_id_rows"] or 0
    row["duplicate_nonnull_id_rows"] = row["rows"] - row["null_id_rows"] - row["distinct_nonnull_ids"]
    row["source"] = name
    return row


def id_set(ids):
    return ids.where(F.col("enrollment_id").isNotNull()).dropDuplicates(["enrollment_id"])


def compare(left_name, left, right_name, right):
    return {"left": left_name, "right": right_name,
            "left_only_distinct_ids": left.join(right, "enrollment_id", "left_anti").count(),
            "right_only_distinct_ids": right.join(left, "enrollment_id", "left_anti").count(),
            "intersection_distinct_ids": left.join(right, "enrollment_id", "inner").count()}


frames, ids, stats = {}, {}, []
for name in ("processed_enrollments", "CQ_labels", "LO_labels"):
    frames[name], ids[name] = read_population(name, SOURCES[name])
    stats.append(population_summary(name, ids[name]))
if raw_path:
    frames["raw_enrollments"], ids["raw_enrollments"] = read_population(
        "raw_enrollments", raw_path, os.environ.get("M07_RAW_ENROLLMENT_FORMAT", "parquet").lower(),
        os.environ.get("M07_RAW_ENROLLMENT_ID_COLUMN", "enrollment_id"))
    stats.append(population_summary("raw_enrollments", ids["raw_enrollments"]))

sets = {name: id_set(frame) for name, frame in ids.items()}
comparisons = [compare("processed_enrollments", sets["processed_enrollments"], name, sets[name])
               for name in ("CQ_labels", "LO_labels")]
if raw_path:
    comparisons.append(compare("raw_enrollments", sets["raw_enrollments"], "processed_enrollments", sets["processed_enrollments"]))

status_rows = []
for task, reason, label in (("CQ", "cq_exclusion_reason", "CQ_label_final"),
                            ("LO", "proxy_exclusion_reason", "LO_performance_label_3")):
    frame = frames[f"{task}_labels"]
    missing = [c for c in (reason, label) if c not in frame.columns]
    if missing:
        raise ValueError(f"{task} label fields missing: {missing}")
    grouped = frame.groupBy(F.coalesce(F.col(reason).cast("string"), F.lit("<NULL>")).alias("exclusion_reason"),
                            F.coalesce(F.col(label).cast("string"), F.lit("<NULL>")).alias("label")).count()
    status_rows += [{"task": task, **row.asDict()} for row in grouped.collect()]

inventories = {}
for name, path in SOURCES.items():
    print(f"[M07] inventory {name}: {path}", flush=True)
    inventories[name] = file_inventory(path, name.endswith("_manifest"))
    if name.endswith("_manifest"):
        # Detect addition/removal while hashing as well as changes to individual files.
        again = file_inventory(path, False)
        if [(x["path"], x["bytes"]) for x in inventories[name]] != [(x["path"], x["bytes"]) for x in again]:
            raise RuntimeError(f"Manifest file listing changed while hashing: {path}")

identity = {}
for name in ("CQ_manifest", "LO_manifest"):
    payload = json.dumps(inventories[name], sort_keys=True, separators=(",", ":")).encode("utf-8")
    identity[name] = {"canonical_inventory_sha256": hashlib.sha256(payload).hexdigest(),
                      "file_count": len(inventories[name]), "historical_match": "NOT_VERIFIED_NO_PRIOR_REFERENCE"}

out.mkdir(parents=True, exist_ok=False)
result = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "sources": SOURCES,
          "population_summary": stats, "comparisons": comparisons, "label_status": status_rows,
          "manifest_identity": identity,
          "raw_population_status": "PROVIDED_UNVERIFIED_INDEPENDENCE" if raw_path else "NOT_PROVIDED",
          "limitations": ["Processed enrollments are not necessarily the independent raw population.",
                          "ID comparison casts IDs to strings; inspect types and leading-zero conventions.",
                          "A present-day hash does not establish historical provenance without a prior trusted hash.",
                          "Non-manifest source files are inventoried by name and size, not content-hashed."],
          "id_types": {name: str(frame.schema[os.environ.get("M07_RAW_ENROLLMENT_ID_COLUMN", "enrollment_id") if name == "raw_enrollments" else "enrollment_id"].dataType) for name, frame in frames.items()}}
for name, data in inventories.items():
    (out / f"{name}_files.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
(out / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
(out / "_SUCCESS").write_text("completed\n", encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
print(f"[M07] COMPLETE: {out}", flush=True)
