"""Audit categorical/discrete columns in a frozen CQ or LO phase-view release."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUTS = {
    "CQ": ROOT / "resuilt" / "CQ_view_v1" / "phase_views_v1",
    "LO": ROOT / "resuilt" / "LO" / "hybrid" / "phase_views_v1",
}
CANDIDATES = (
    "gender", "video_observed_mask", "problem_observed_mask", "comment_observed_mask",
    "most_common_hour", "most_common_day", "temporal_block", "phase", "scenario",
    "timeline_source", "window", "split", "split_id", "label_availability_source",
    "label_rule_version", "CQ_label_final", "LO_performance_label_3",
    "LO_performance_label_5", "decision", "teacher_count", "school_count",
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", choices=("CQ", "LO"), required=True)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    source = (args.input or DEFAULT_INPUTS[args.task]).resolve()
    output = (args.output or ROOT / "artifacts" / "dq_baseline_v1" / args.task / "categorical_audit.json").resolve()
    files = sorted(source.rglob("*.parquet"))
    if not files:
        raise FileNotFoundError(source)
    schema = pq.ParquetFile(files[0]).schema_arrow
    candidates = [name for name in CANDIDATES if name in schema.names]
    counts = {name: Counter() for name in candidates}
    nulls = Counter()
    total = 0
    for file in files:
        parquet = pq.ParquetFile(file)
        for batch in parquet.iter_batches(batch_size=262_144, columns=candidates):
            total += batch.num_rows
            for name, values in batch.to_pydict().items():
                nulls[name] += sum(value is None for value in values)
                counts[name].update(value for value in values if value is not None)
    result = {"task": args.task, "rows": total, "columns": {}}
    for name in candidates:
        counter = counts[name]
        values = sorted(counter.items(), key=lambda pair: str(pair[0]))
        result["columns"][name] = {
            "dtype": str(schema.field(name).type),
            "null_count": nulls[name],
            "null_rate": nulls[name] / total,
            "distinct_count": len(counter),
            "values": values if len(values) <= 64 else values[:64],
            "values_truncated": len(values) > 64,
        }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
