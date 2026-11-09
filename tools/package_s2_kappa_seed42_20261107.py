"""Generate versioned M-06 seed-42 summaries using the agreed kappa definition."""
import hashlib
import json
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "LO/resuilt/m06_s2_kappa_seed42_20261107"
SOURCES = {
    "CQ": ROOT / "CQ/resuilt/cq_s2_rehash_20261107/delivery",
    "LO": ROOT / "LO/resuilt/lo_s2_sampling_seed42_20261106",
}
if DEST.exists():
    raise FileExistsError(DEST)
for task, source in SOURCES.items():
    name = f"s2_sampling_summary_{task.lower()}_seed42"
    df = pd.read_csv(source / f"{name}.csv")
    before = "n_train_before" if task == "CQ" else "n_before"
    groups = ["window_id", "pipeline_id", "balancer"]
    if len(df) != 108 or df.duplicated(groups + ["class_code"]).any() or len(df.groupby(groups)) != 36:
        raise ValueError(f"{task}: unexpected row grain")
    for col in [before, "n_target", "n_generated", "n_after"]:
        df[col] = pd.to_numeric(df[col], errors="raise").astype("int64")
    if (df[before] <= 0).any() or (df["n_after"] <= 0).any():
        raise ValueError(f"{task}: empty or missing class needs separate semantics")
    if not (df["n_after"] == df[before] + df["n_generated"]).all():
        raise ValueError(f"{task}: inconsistent generated counts")
    majority_before = df.groupby(groups)[before].transform("max")
    majority_after = df.groupby(groups)["n_after"].transform("max")
    if not (majority_before == majority_after).all():
        raise ValueError(f"{task}: majority support changed")
    expected_target = [min(max(n, math.ceil(m / 10)), 10 * n) for n, m in zip(df[before], majority_before)]
    if not (df["n_target"] == expected_target).all() or not (df["n_after"] == df["n_target"]).all():
        raise ValueError(f"{task}: counts differ from registered IR10_K10 target")
    df["kappa_reached"] = majority_after / df["n_after"]
    df["kappa_status"] = "DEFINED_MAJORITY_AFTER_OVER_CLASS_AFTER"
    df["ir_target"] = 10
    df["ir_target_met"] = majority_after <= 10 * df["n_after"]
    df["expansion_cap"] = 10
    df["expansion_cap_reached"] = (df["n_after"] == 10 * df[before]) & (df[before] < majority_before)
    df["expansion_cap_bound"] = [math.ceil(m / 10) > 10 * n for n, m in zip(df[before], majority_before)]
    fallback = df[df["fallback_count"].notna()]
    if len(fallback) != 24 or not ((fallback["fallback_count"] / fallback["n_generated"] - fallback["fallback_rate"]).abs() < 1e-8).all():
        raise ValueError(f"{task}: Radius fallback count/rate mismatch")
    out = DEST / task
    out.mkdir(parents=True)
    df.to_csv(out / f"{name}.csv", index=False)
    df.to_parquet(out / f"{name}.parquet", index=False)
    shutil.copy2(source / "ledger_inventory.json", out / "ledger_inventory.json")
    note = ("All 36 manifest and ledger hashes were matched to the earlier CQ inventory." if task == "CQ" else
            "All 36 manifest/ledger hashes were recomputed but lack an independent historical reference. "
            "Radius rows match window, parent pipeline, class, seed and generated counts; the Radius audit "
            "does not include parent run ID, so exact parent identity is not independently verified.")
    definition = {"name": "kappa_reached", "definition": "max_class_n_after / n_after_class",
                  "target_criterion": "max_class_n_after <= 10 * n_after_class",
                  "cap_bound_criterion": "ceil(max_class_n_before / 10) > 10 * n_before_class",
                  "zero_support": "undefined; fail closed in this export",
                  "not_cohens_kappa": True, "approved_in_conversation": "2026-11-07"}
    (out / "METRIC_DEF_kappa_reached.json").write_text(json.dumps(definition, indent=2) + "\n", encoding="utf-8")
    summary = {"task": task, "generated_at_utc": datetime.now(timezone.utc).isoformat(), "rows": len(df),
               "runs": 36, "radius_fallback_rows": len(fallback), "kappa_defined_rows": int(df.kappa_reached.notna().sum()),
               "ir_target_not_met_rows": int((~df.ir_target_met).sum()), "expansion_cap_bound_rows": int(df.expansion_cap_bound.sum()),
               "target_rule_and_generated_counts": "PASS", "fallback_count_rate": "PASS", "provenance": note}
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "README.md").write_text(
        "# M-06 S2 seed 42 — kappa definition\n\n"
        "kappa_reached = maximum post-augmentation class support divided by post-augmentation support for "
        "this class. This is an imbalance ratio, not Cohen's kappa; smaller is more balanced. "
        "ir_target_met is true when the ratio is <= 10. expansion_cap_reached means the class reached "
        "10 times its original support; expansion_cap_bound means that cap prevents the uncapped target. "
        "Both are distinct from ir_target_met. Majority rows have kappa 1. Empty classes are undefined.\n\n"
        "fallback_count counts generated rows using nearest-neighbour fallback, not distance candidates; "
        "fallback_rate = fallback_count / n_generated; > 0.50 is a warning. Existing S2 artifacts remain unchanged.\n\n"
        + note + "\n", encoding="utf-8")
    lines = []
    for p in sorted(out.iterdir()):
        if p.is_file() and p.name != "sha256sums.txt":
            lines.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}")
    (out / "sha256sums.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
