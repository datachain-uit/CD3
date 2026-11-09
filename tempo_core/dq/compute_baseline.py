"""Compute a reproducible, streaming data-quality baseline for CQ or LO.

The released views contain the label already.  This command does not join
labels or fit preprocessing; it only measures the frozen input release.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUTS = {
    "CQ": ROOT / "resuilt" / "CQ" / "views" / "hybrid" / "phase_views_v1",
    "LO": ROOT / "resuilt" / "LO" / "hybrid" / "phase_views_v1",
}
LABELS = {"CQ": "CQ_label_final", "LO": "LO_performance_label_3"}
KEYS = ("enrollment_id", "user_id", "course_id", "offering_id")
SCOPE_COLUMNS = ("window", "split_id", "phase")
MASK_COLUMNS = ("video_observed_mask", "problem_observed_mask", "comment_observed_mask")
EXCLUDED_NUMERIC = {
    "enrollment_id", "user_id", "course_id", "offering_id", "year_of_birth",
    "cutoff_time", "window_end_exclusive", "label_availability_time",
    # CQ target definition/provenance, retained in views for auditing only.
    "COELO_final", "AFELO_final", "ACELO_final", "CQ_distance_euclidean_final",
    "CQ_proximity_final", "TRIAD_distance_final",
    # LO target definition/provenance, likewise never a model feature.
    "performance_score",
}


class HyperLogLog:
    """Small streaming cardinality estimator; avoids retaining all release IDs."""

    def __init__(self, precision: int = 14) -> None:
        self.precision = precision
        self.registers = np.zeros(1 << precision, dtype=np.uint8)

    def add(self, value: Any) -> None:
        raw = hashlib.blake2b(str(value).encode("utf-8"), digest_size=8).digest()
        hashed = int.from_bytes(raw, "big")
        index = hashed >> (64 - self.precision)
        remainder = (hashed << self.precision) & ((1 << 64) - 1)
        rank = 64 - remainder.bit_length() + 1 if remainder else 64 - self.precision + 1
        self.registers[index] = max(self.registers[index], rank)

    def estimate(self) -> int:
        m = len(self.registers)
        alpha = 0.7213 / (1 + 1.079 / m)
        harmonic = float(np.exp2(-self.registers.astype(np.float64)).sum())
        raw = alpha * m * m / harmonic
        zeros = int((self.registers == 0).sum())
        if raw <= 2.5 * m and zeros:
            raw = m * math.log(m / zeros)
        return round(raw)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", choices=("CQ", "LO"), required=True)
    parser.add_argument("--input", type=Path, help="Override the phase_views_v1 directory.")
    parser.add_argument("--output", type=Path, help="Output directory (default: artifacts/dq_baseline_v1/<TASK>).")
    parser.add_argument("--batch-size", type=int, default=131_072)
    parser.add_argument("--max-batches", type=int, help="Development smoke-test limit; do not use for a release baseline.")
    parser.add_argument("--hash-files", action="store_true", help="Add SHA-256 for every Parquet file.")
    return parser.parse_args()


def parquet_files(path: Path) -> list[Path]:
    files = sorted(path.rglob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"No Parquet files found below {path}")
    return files


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scope_key(row: dict[str, Any], label: str | None = None) -> tuple[str, ...]:
    values = tuple(str(row.get(column) if row.get(column) is not None else "<NULL>") for column in SCOPE_COLUMNS)
    return values + ((str(label),) if label is not None else ())


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def numeric_columns(schema: pa.Schema) -> list[str]:
    result = []
    for field in schema:
        if field.name in EXCLUDED_NUMERIC:
            continue
        if pa.types.is_integer(field.type) or pa.types.is_floating(field.type) or pa.types.is_decimal(field.type):
            result.append(field.name)
    return result


def main() -> None:
    args = parse_args()
    input_path = (args.input or DEFAULT_INPUTS[args.task]).resolve()
    output = (args.output or ROOT / "artifacts" / "dq_baseline_v1" / args.task).resolve()
    output.mkdir(parents=True, exist_ok=True)
    files = parquet_files(input_path)
    label_column = LABELS[args.task]
    first = pq.ParquetFile(files[0])
    schema = first.schema_arrow
    columns = set(schema.names)
    required = set(SCOPE_COLUMNS) | {label_column, "enrollment_id", "offering_id"}
    missing = sorted(required - columns)
    if missing:
        raise ValueError(f"Input release misses required columns: {missing}")

    numeric = numeric_columns(schema)
    selected = list(dict.fromkeys([*SCOPE_COLUMNS, label_column, *KEYS, *MASK_COLUMNS, *numeric]))
    selected = [name for name in selected if name in columns]
    feature_stats = {
        name: {"rows": 0, "null": 0, "nonfinite": 0, "zero": 0, "negative": 0, "sum": 0.0, "sum_sq": 0.0, "min": math.inf, "max": -math.inf}
        for name in numeric
    }
    scopes: Counter[tuple[str, ...]] = Counter()
    scope_enrollments: dict[tuple[str, ...], HyperLogLog] = defaultdict(HyperLogLog)
    scope_offerings: dict[tuple[str, ...], HyperLogLog] = defaultdict(HyperLogLog)
    mask_counts: Counter[tuple[str, ...]] = Counter()
    mask_denominators: Counter[tuple[str, ...]] = Counter()
    key_nulls: Counter[str] = Counter()
    total_rows = 0
    row_cardinality = HyperLogLog()

    batches_read = 0
    stop = False
    for file in files:
        reader = pq.ParquetFile(file)
        for batch in reader.iter_batches(batch_size=args.batch_size, columns=selected):
            table = pa.Table.from_batches([batch])
            total_rows += table.num_rows
            # Include every declared key.  Restricting this projection to the
            # split keys falsely reported user_id/course_id as all-null even
            # when they were present in the released view.
            records = table.select([name for name in [*SCOPE_COLUMNS, label_column, *KEYS, *MASK_COLUMNS] if name in table.column_names]).to_pylist()
            for row in records:
                base = scope_key(row)
                label = row.get(label_column)
                scopes[scope_key(row, label)] += 1
                scope_enrollments[base].add(row.get("enrollment_id"))
                scope_offerings[base].add(row.get("offering_id"))
                row_key = (row.get("enrollment_id"), *base)
                row_cardinality.add(row_key)
                for key in KEYS:
                    if row.get(key) is None:
                        key_nulls[key] += 1
                for mask in MASK_COLUMNS:
                    if mask not in row:
                        continue
                    mask_denominators[(mask, *base)] += 1
                    if row[mask] is True or row[mask] == 1:
                        mask_counts[(mask, *base)] += 1
            for name in numeric:
                values = table[name].to_numpy(zero_copy_only=False)
                values = np.asarray(values, dtype=np.float64)
                state = feature_stats[name]
                state["rows"] += len(values)
                valid = np.isfinite(values)
                state["null"] += int(np.isnan(values).sum())
                state["nonfinite"] += int((~valid).sum())
                if valid.any():
                    x = values[valid]
                    state["zero"] += int((x == 0).sum())
                    state["negative"] += int((x < 0).sum())
                    state["sum"] += float(x.sum())
                    state["sum_sq"] += float(np.dot(x, x))
                    state["min"] = min(state["min"], float(x.min()))
                    state["max"] = max(state["max"], float(x.max()))
            batches_read += 1
            if args.max_batches and batches_read >= args.max_batches:
                stop = True
                break
        if stop:
            break

    scope_rows = []
    for (window, split_id, phase, label), count in sorted(scopes.items()):
        base = (window, split_id, phase)
        scope_rows.append({"task": args.task, "window": window, "split_id": split_id, "phase": phase, "label": label, "row_count": count,
                           "unique_enrollment_count_est": scope_enrollments[base].estimate(), "unique_offering_count_est": scope_offerings[base].estimate(),
                           "label_rate_within_scope": round(count / sum(v for k, v in scopes.items() if k[:3] == base), 8)})
    write_csv(output / "scope_counts.csv", scope_rows, list(scope_rows[0]) if scope_rows else [])

    feature_rows = []
    for name, state in feature_stats.items():
        observed = state["rows"] - state["nonfinite"]
        mean = state["sum"] / observed if observed else None
        variance = max(0.0, state["sum_sq"] / observed - mean * mean) if observed and mean is not None else None
        feature_rows.append({"feature": name, "dtype": str(schema.field(name).type), "row_count": state["rows"],
                             "null_rate": round(state["null"] / state["rows"], 8), "nonfinite_rate": round(state["nonfinite"] / state["rows"], 8),
                             "zero_rate_observed": round(state["zero"] / observed, 8) if observed else None,
                             "negative_rate_observed": round(state["negative"] / observed, 8) if observed else None,
                             "min": state["min"] if observed else None, "max": state["max"] if observed else None,
                             "mean": mean, "std": math.sqrt(variance) if variance is not None else None})
    write_csv(output / "feature_quality.csv", feature_rows, list(feature_rows[0]) if feature_rows else [])

    mask_rows = [{"mask": mask, "window": window, "split_id": split_id, "phase": phase, "observed_count": mask_counts[(mask, window, split_id, phase)],
                  "row_count": den, "observed_rate": round(mask_counts[(mask, window, split_id, phase)] / den, 8)}
                 for (mask, window, split_id, phase), den in sorted(mask_denominators.items())]
    write_csv(output / "mask_quality.csv", mask_rows, list(mask_rows[0]) if mask_rows else [])
    key_rows = [{"key": key, "null_count": key_nulls[key], "null_rate": round(key_nulls[key] / total_rows, 8)} for key in KEYS]
    duplicate_estimate = max(0, total_rows - row_cardinality.estimate())
    key_rows.append({"key": "duplicate_enrollment_window_split_phase_est", "null_count": duplicate_estimate, "null_rate": round(duplicate_estimate / total_rows, 8)})
    write_csv(output / "key_quality.csv", key_rows, list(key_rows[0]))

    file_info = []
    for file in files:
        info = {"path": str(file), "bytes": file.stat().st_size, "rows": pq.ParquetFile(file).metadata.num_rows}
        if args.hash_files:
            info["sha256"] = sha256(file)
        file_info.append(info)
    inventory = {"task": args.task, "created_at_utc": datetime.now(timezone.utc).isoformat(), "input_path": str(input_path),
                 "file_count": len(files), "total_file_bytes": sum(item["bytes"] for item in file_info), "parquet_row_count": total_rows,
                 "schema": [{"name": field.name, "type": str(field.type), "nullable": field.nullable} for field in schema], "files": file_info}
    (output / "release_inventory.json").write_text(json.dumps(inventory, indent=2, ensure_ascii=False), encoding="utf-8")
    failures = []
    # HLL is an estimate, so it informs a manual duplicate investigation rather
    # than failing a release by itself.
    if any(row["label"] == "None" for row in scope_rows):
        failures.append("Null labels detected")
    if any(row["row_count"] == 0 for row in scope_rows):
        failures.append("Empty label scope detected")
    summary = {"task": args.task, "input_path": str(input_path), "output_path": str(output), "rows": total_rows,
               "is_complete_release_scan": not bool(args.max_batches),
               "features_numeric": len(numeric), "scope_rows": len(scope_rows), "duplicate_row_estimate": duplicate_estimate,
               "checks": {"status": "PASS" if not failures else "FAIL", "failures": failures},
               "next_gate": "Proceed to train-pooled P1-P4 preprocessing only when this baseline is accepted."}
    (output / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
