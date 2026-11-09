"""Turn completed DQ baseline CSV files into an actionable release gate."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", choices=("CQ", "LO"), required=True)
    parser.add_argument("--baseline", type=Path)
    args = parser.parse_args()
    root = (args.baseline or ROOT / "artifacts" / "dq_baseline_v1" / args.task).resolve()
    with (root / "key_quality.csv").open(encoding="utf-8") as handle:
        key_rows = list(csv.DictReader(handle))
    with (root / "feature_quality.csv").open(encoding="utf-8") as handle:
        feature_rows = list(csv.DictReader(handle))
    with (root / "scope_counts.csv").open(encoding="utf-8") as handle:
        scope_rows = list(csv.DictReader(handle))

    blocking = []
    warnings = []
    for row in key_rows:
        if row["key"] in {"enrollment_id", "offering_id"} and float(row["null_rate"]) > 0:
            blocking.append(f"Required split key {row['key']} has nulls.")
        elif row["key"] in {"user_id", "course_id"} and float(row["null_rate"]) >= 0.999999:
            warnings.append(f"{row['key']} is null 100%; exclude it from model input and recover it upstream only if subgroup analysis needs it.")
    sparse = [row["feature"] for row in feature_rows if float(row["null_rate"]) >= 0.99]
    if sparse:
        warnings.append(f"{len(sparse)} features have >=99% null. These are mostly activity/comment-dependent fields; do not blindly impute them. Retain observed masks and evaluate an explicit comment-feature ablation.")
    exclusions = []
    age = next((row for row in feature_rows if row["feature"] == "age_at_enroll"), None)
    if age and (float(age["negative_rate_observed"] or 0) > 0 or float(age["min"] or 0) < 0 or float(age["max"] or 0) > 120):
        exclusions.append("age_at_enroll")
        warnings.append(
            "age_at_enroll has invalid observed values (negative or >120); exclude it from V1 model inputs and do not impute it until year_of_birth is repaired upstream."
        )
    labels_by_scope = {}
    for row in scope_rows:
        labels_by_scope.setdefault((row["window"], row["split_id"], row["phase"]), 0)
        labels_by_scope[(row["window"], row["split_id"], row["phase"])] += int(row["row_count"])
    if any(count == 0 for count in labels_by_scope.values()):
        blocking.append("At least one window/split/phase scope is empty.")
    result = {
        "task": args.task,
        "gate": "BLOCK" if blocking else "PASS_WITH_WARNINGS" if warnings else "PASS",
        "blocking_issues": blocking,
        "warnings": warnings,
        "recommended_feature_exclusions_v1": exclusions,
        "sparse_feature_count_ge_99pct_null": len(sparse),
        "required_next_actions": [
            "Freeze this release inventory before preprocessing.",
            "Exclude labels, label provenance, enrollment_id and offering_id. Handle user_id/course_id only through the explicit train-vocabulary categorical-ID contract.",
            "Fit scaler/encoder/imputer only on TRAIN_POOLED_P1_P4 for each window.",
            "Keep observed-missing, future-unavailable and structural absence separate through masks.",
        ],
    }
    (root / "quality_review.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
