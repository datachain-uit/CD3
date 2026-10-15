"""Read every Parquet input required by one portable VastAI task/window."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


PARENTS = {"V2": "V1", "V3": "V1", "V4": "V1", "V6": "V5", "V7": "V5", "V8": "V5",
           "V10": "V9", "V11": "V9", "V12": "V9", "V14": "V13", "V15": "V13", "V16": "V13"}
PHASES = ("P1", "P2", "P3", "P4")


def parse() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--window", choices=("W1", "W2", "W3"), required=True)
    return parser.parse_args()


def inspect(path: Path) -> dict:
    started = time.perf_counter()
    try:
        table = pq.read_table(path)  # Full page decode; detects truncated/corrupt streams.
        if table.num_rows == 0:
            raise ValueError("zero rows")
        record = {"path": str(path), "ok": True, "rows": table.num_rows,
                  "columns": table.num_columns, "seconds": round(time.perf_counter() - started, 3)}
        del table
        pa.default_memory_pool().release_unused()
        return record
    except Exception as exc:  # Audit must report every bad file before failing.
        return {"path": str(path), "ok": False, "error": f"{type(exc).__name__}: {exc}",
                "seconds": round(time.perf_counter() - started, 3)}


def main() -> None:
    args = parse()
    paths: list[Path] = []
    for index in range(17):
        pipeline = f"V{index}"
        parent = PARENTS.get(pipeline, pipeline)
        train_file = "train.parquet" if pipeline == parent else "balanced_train.parquet"
        paths.append(args.data_root / "train" / args.window / pipeline / train_file)
    for parent in ("V0", "V1", "V5", "V9", "V13"):
        base = args.data_root / "evaluation" / args.window / parent
        paths.append(base / "validation.parquet")
        paths.extend(base / f"test_{phase}.parquet" for phase in PHASES)

    records = [inspect(path) for path in paths]
    failures = [record for record in records if not record["ok"]]
    report = {"window": args.window, "expected_files": len(paths), "passed_files": len(paths) - len(failures),
              "failed_files": len(failures), "records": records}
    out = args.data_root / f"input_integrity_audit_{args.window}.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in report if key != "records"}, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
