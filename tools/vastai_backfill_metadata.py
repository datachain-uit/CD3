"""Backfill immutable metadata sidecars without changing completed model manifests."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from vastai_metadata_contract import build_contract, write_contract


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", choices=("CQ", "LO"), required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--runs-root", type=Path, required=True)
    parser.add_argument("--models", nargs="+", default=["LSTM", "GRU"])
    parser.add_argument("--runner-path", type=Path, default=Path(__file__).with_name("vastai_train_shared.py"))
    args = parser.parse_args()
    records, failures, written = [], [], 0
    for manifest_path in sorted(args.runs_root.glob(f"{args.task}/W*/V*/**/seed=*/run_manifest.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("model_name") not in args.models:
            continue
        try:
            contract = build_contract(task=args.task, data_root=args.data_root, run_dir=manifest_path.parent,
                                      manifest=manifest, runner_path=args.runner_path)
            created = write_contract(contract, manifest_path.parent / "metadata_contract.json")
            written += int(created)
            records.append({"run": str(manifest_path.parent), "ok": True, "created": created})
        except Exception as error:  # report all invalid cells in one pass
            failures.append({"run": str(manifest_path.parent), "error": str(error)})
    report = {"task": args.task, "models": args.models, "runs_seen": len(records) + len(failures),
              "sidecars_created": written, "failures": failures, "passed": len(records)}
    (args.runs_root / args.task / "vastai_metadata_backfill_audit.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "failures"}, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
