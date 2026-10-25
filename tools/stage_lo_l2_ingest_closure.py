"""Build a compact, self-consistent LO external-facts ingest bundle.

The four VastAI families were downloaded at different times.  This utility
copies only the contract-declared, small files required by the L2 importer and
merges the per-family audit bundles.  The repaired RNN/W1/V0 cell replaces its
older runner-revision counterpart before ingest; no training artifact is
modified in place.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT_DEFAULT = ROOT / "LO/resuilt/lo_l2_ingest_closure_seed42_20261025"
RNN_LSTM = ROOT / "LO/resuilt/lo_nvml_historical_layout_seed42_20261023_complete/lo_nvml_historical_layout_seed42"
GRU = ROOT / "LO/resuilt/lo_gru_nvml_audited_seed42_20261025/lo_gru_historical_layout_seed42"
BILSTM = ROOT / "LO/resuilt/lo_bilstm_nvml_audited_seed42_20261025/lo_bilstm_historical_layout_seed42"
REPAIR = ROOT / "LO/resuilt/lo_cohort_audit_nvml_seed42/lo_rnn_w1_v0_runner_7886_repair_seed42"
REPAIR_AUDIT = ROOT / "LO/resuilt/lo_cohort_audit_nvml_seed42/audits_repair_7886_seed42/LO/RNN/seed=42"
AUDIT_ROOTS = {
    "RNN": RNN_LSTM / "audits/LO/RNN/seed=42",
    "LSTM": RNN_LSTM / "audits/LO/LSTM/seed=42",
    "GRU": GRU / "audits/LO/GRU/seed=42",
    "BILSTM": ROOT / "LO/resuilt/lo_bilstm_nvml_audited_seed42_20261025/audits_seed42/LO/BILSTM/seed=42",
}
RUN_ROOTS = {"RNN": RNN_LSTM, "LSTM": RNN_LSTM, "GRU": GRU, "BILSTM": BILSTM}
FACTS = ("canonical_s_leak", "sanity_components", "evaluation_slices", "metrics_per_class", "bootstrap_metrics_per_class", "checkpoint_selection")
SMALL_RUN_FILES = ("metadata_contract.json", "run_manifest.json", "metrics_overall.parquet", "train_history.parquet", "feature_layout.json")


def replace_w1_v0(full: pd.DataFrame, repair: pd.DataFrame, fact: str) -> pd.DataFrame:
    if fact == "canonical_s_leak":
        keys = ["window_id", "parent_pipeline", "eval_split", "phase_id"]
        selector = full["window_id"].eq("W1") & full["parent_pipeline"].eq("V0")
    elif fact == "checkpoint_selection":
        keys = ["window_id", "pipeline_id"]
        selector = full["window_id"].eq("W1") & full["pipeline_id"].eq("V0")
    else:
        keys = ["window_id", "pipeline_id", "eval_split", "phase_id"]
        if fact == "evaluation_slices":
            keys.append("slice")
        elif fact == "metrics_per_class":
            keys.append("class_index")
        elif fact == "bootstrap_metrics_per_class":
            keys.extend(("class_index", "metric_name"))
        selector = full["window_id"].eq("W1") & full["pipeline_id"].eq("V0")
    output = pd.concat((full.loc[~selector], repair), ignore_index=True)
    if output.duplicated(keys).any():
        raise ValueError(f"{fact}: duplicate keys after repair replacement")
    return output


def copy_run(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for name in SMALL_RUN_FILES:
        path = source / name
        if not path.is_file():
            raise FileNotFoundError(path)
        shutil.copy2(path, destination / name)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUT_DEFAULT)
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists():
        shutil.rmtree(out)
    artifacts, audits = out / "artifacts", out / "audits/LO"
    expected = {(family, f"W{window}", f"V{pipeline}")
                for family in RUN_ROOTS for window in range(1, 4) for pipeline in range(17)}
    copied: set[tuple[str, str, str]] = set()
    for family, root in RUN_ROOTS.items():
        for contract in root.glob(f"LO/*/*/{family}/seed=42/metadata_contract.json"):
            run = contract.parent
            manifest = json.loads(contract.read_text(encoding="utf-8"))
            identity = manifest["model_identity"]
            key = (family, str(identity["window_id"]), str(identity["pipeline_id"]))
            if key == ("RNN", "W1", "V0"):
                continue
            target = artifacts / "LO" / key[1] / key[2] / family / "seed=42"
            copy_run(run, target)
            copied.add(key)
    repair_run = REPAIR / "LO/W1/V0/RNN/seed=42"
    copy_run(repair_run, artifacts / "LO/W1/V0/RNN/seed=42")
    copied.add(("RNN", "W1", "V0"))
    if copied != expected:
        raise RuntimeError(f"Contract coverage mismatch: missing={sorted(expected-copied)[:3]}, extra={sorted(copied-expected)[:3]}")

    for family, source in AUDIT_ROOTS.items():
        destination = audits / family / "seed=42"
        destination.mkdir(parents=True, exist_ok=True)
        base_manifest = json.loads((source / "audit_manifest.json").read_text(encoding="utf-8"))
        output_rows = {}
        for fact in FACTS:
            frame = pd.read_parquet(source / f"{fact}.parquet")
            if family == "RNN":
                repair = pd.read_parquet(REPAIR_AUDIT / f"{fact}.parquet")
                frame = replace_w1_v0(frame, repair, fact)
            frame.to_parquet(destination / f"{fact}.parquet", index=False)
            output_rows[fact] = len(frame)
        base_manifest["runs"] = 51
        base_manifest["rows"] = output_rows
        base_manifest["closure_replacement"] = {
            "RNN_W1_V0": "runner_7886_repair" if family == "RNN" else None,
            "note": "RNN W1/V0 source facts replaced by the runner-7886 repair before L2 ingest." if family == "RNN" else None,
        }
        (destination / "audit_manifest.json").write_text(json.dumps(base_manifest, indent=2), encoding="utf-8")
    receipt = {"task": "LO", "release_id": "LO_V3_1", "seed": 42, "contracts": len(copied),
               "families": sorted(RUN_ROOTS), "rnn_w1_v0": "runner_7886_repair",
               "artifact_root": str(artifacts), "audit_root": str(out / "audits")}
    (out / "staging_receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
