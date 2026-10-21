"""Scan all CQ TEST prefix rows for future values and profile static fields."""
from __future__ import annotations

import json
from pathlib import Path
import pyarrow.compute as pc
import pyarrow.parquet as pq

ROOT = Path("CQ/resuilt/_checked_feature_v2")
OUT = Path("CQ/resuilt/cq_full_prefix_static_audit_20261017")
PHASES = ("P1", "P2", "P3", "P4")
STATIC = ("ex_counts", "gender", "primary_risk_set", "resource_count",
          "school_avg_bio_length_chars", "school_avg_motto_length_chars", "school_count",
          "split_rule_version", "teacher_avg_bio_length_chars", "teacher_count",
          "teacher_org_count", "timeline_source", "window_duration_seconds")


def main():
    mask = []
    profiles = []
    for phase_i, phase in enumerate(PHASES):
        files = sorted((ROOT / "test_prefix_views_v2_2" / phase).rglob("*.parquet"))
        if not files:
            raise FileNotFoundError(phase)
        total_rows = total_nonnull = total_cells = 0
        for path in files:
            pf = pq.ParquetFile(path)
            future = [name for name in pf.schema_arrow.names if not name.startswith("phase_available_")
                      and any(name.endswith("_" + p) for p in PHASES[phase_i + 1:])]
            total_rows += pf.metadata.num_rows
            total_cells += pf.metadata.num_rows * len(future)
            for batch in pf.iter_batches(batch_size=8192, columns=future) if future else ():
                total_nonnull += sum(len(col) - col.null_count for col in batch.columns)
        mask.append({"phase": phase, "files": len(files), "rows": total_rows,
                     "future_cells": total_cells, "non_null_future_cells": total_nonnull,
                     "pass": total_nonnull == 0})
        print(json.dumps(mask[-1]), flush=True)

    roots = {"TRAIN_VALIDATION": ROOT / "phase_views_v2_2" / "phase_views_v2_2",
             **{f"TEST_{phase}": ROOT / "test_prefix_views_v2_2" / phase for phase in PHASES}}
    for group, root in roots.items():
        accum = {c: {"rows": 0, "nulls": 0, "values": set(), "truncated": False} for c in STATIC}
        for path in sorted(root.rglob("*.parquet")):
            pf = pq.ParquetFile(path)
            available = [c for c in STATIC if c in pf.schema_arrow.names]
            for batch in pf.iter_batches(batch_size=65536, columns=available):
                for name, arr in zip(available, batch.columns):
                    item = accum[name]
                    item["rows"] += len(arr)
                    item["nulls"] += arr.null_count
                    if not item["truncated"]:
                        for value in pc.unique(arr).to_pylist():
                            if value is not None:
                                item["values"].add(str(value))
                            if len(item["values"]) > 20:
                                item["truncated"] = True
                                break
        for name, item in accum.items():
            profiles.append({"dataset": group, "column": name, "rows": item["rows"],
                             "nulls": item["nulls"], "distinct_up_to_21": len(item["values"]),
                             "unique_values_truncated": item["truncated"],
                             "values_if_small": sorted(item["values"]) if not item["truncated"] else None})
        print(f"profile complete: {group}", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "full_scan.json").write_text(json.dumps({"mask": mask, "static_profiles": profiles}, indent=2), encoding="utf-8")
    print(f"saved: {OUT / 'full_scan.json'}", flush=True)


if __name__ == "__main__":
    main()
