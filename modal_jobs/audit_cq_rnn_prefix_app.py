"""Read-only CQ RNN prefix and course-cohort audit; writes only compact audit facts."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path

import modal

app = modal.App("tempo-cq-rnn-prefix-audit")
volume = modal.Volume.from_name("tempo-data-v1", create_if_missing=False)
secret = modal.Secret.from_name("tempo-prediction-salt", required_keys=["TEMPO_PREDICTION_SALT"])
image = (modal.Image.debian_slim(python_version="3.12")
         .pip_install("numpy>=1.26", "pandas>=2.2", "pyarrow>=16", "scikit-learn>=1.5")
         .add_local_python_source("imputation_core", "release_core")
         .add_local_file("LO/registries.py", "/root/LO/registries.py")
         .add_local_file("tools/audit_prefix_validation_alignment.py", "/root/prefix_audit.py")
         .add_local_file("modal_jobs/export_cq_rnn_facts.py", "/root/cq_export.py"))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@app.function(image=image, volumes={"/data": volume}, secrets=[secret], cpu=4, memory=16384, timeout=10800)
def audit():
    import numpy as np
    import pandas as pd
    from sklearn.metrics import balanced_accuracy_score, f1_score
    from imputation_core.meta_storage import release_inventory
    from release_core import resolve_release

    helper = _load("prefix_audit", "/root/prefix_audit.py")
    exporter = _load("cq_export", "/root/cq_export.py")
    spec = resolve_release("CQ", "CQ_V2_2")
    input_root = Path("/data/input") / spec["input_dir"]
    release_id = release_inventory(input_root, task="CQ")["data_release_id"]
    base = Path("/data/meta_release=imputation-v1")
    runs = exporter._latest_successful_runs(base / "L1_runs", model_name="RNN", seed=42,
                                           release_spec=spec, data_release_id=release_id)
    if len(runs) != 51 or len({(m["window_id"], m["pipeline_id"]) for _, m in runs}) != 51:
        raise RuntimeError(f"Expected 51 unique release-matched RNN runs, found {len(runs)}")
    # Audit the exact selected layouts, not older attempts also on the volume.
    layouts = [(root, manifest, json.loads((root / "feature_layout.json").read_text())) for root, manifest in runs]
    signatures = {}
    columns = set()
    for _, _, layout in layouts:
        static = sorted(layout.get("static_columns", []))
        masks = sorted(layout.get("mask_static_columns", []))
        signature = hashlib.sha256(json.dumps({"static_columns": static, "mask_static_columns": masks}, sort_keys=True).encode()).hexdigest()
        signatures[signature] = signatures.get(signature, 0) + 1
        columns.update(static)
    prefix_root = input_root / "test_prefix_views_v2_2"
    phase_root = input_root / "phase_views_v2_2"
    prefix = pd.DataFrame(helper._prefix_schema_audit(prefix_root))
    parity = helper._static_prefix_parity(prefix_root, sorted(columns))
    cohort, context = helper._course_cohort_audit(phase_root, prefix_root, "CQ_label_final")
    salt = os.environ["TEMPO_PREDICTION_SALT"]
    context = context.copy()
    context["enrollment_id_hash"] = context["enrollment_id"].astype("string").map(
        lambda value: hashlib.sha256(f"{salt}|{value}".encode()).hexdigest())
    if context["enrollment_id_hash"].duplicated().any():
        raise ValueError("Duplicate context enrollment hashes")
    context = context.set_index("enrollment_id_hash")
    context["temporal_slice"] = np.where(pd.to_numeric(context["temporal_strict_P1"], errors="coerce").fillna(0).eq(1), "STRICT", "OVERLAP")
    label_map = {"warning": "c0", "average": "c1", "good": "c2"}
    summaries, slices, per_class, inventory = [], [], [], []
    for root, m, layout in layouts:
        inventory.append({"window_id": m["window_id"], "pipeline_id": m["pipeline_id"], "run_id": m["run_id"], "attempt_id": m["attempt_id"], "data_release_id": m["data_release_id"]})
        if m["window_id"] != "W1":
            continue
        for split in ("VALIDATION", "TEST"):
            for phase in ("P1", "P2", "P3", "P4"):
                path = root / "predictions" / f"eval_split={split}" / f"phase_id={phase}" / "part-00000.parquet"
                df = pd.read_parquet(path, columns=["enrollment_id_hash", "y_true", "y_pred"])
                if df["enrollment_id_hash"].duplicated().any():
                    raise ValueError(f"Duplicate prediction enrollment: {path}")
                base_row = {"window_id": "W1", "pipeline_id": m["pipeline_id"], "model_name": "RNN", "eval_split": split, "phase_id": phase, "run_id": m["run_id"], "attempt_id": m["attempt_id"]}
                def scores(frame):
                    y, pred = frame["y_true"].astype(str), frame["y_pred"].astype(str)
                    return {"n_rows": len(frame), "macro_f1": f1_score(y, pred, labels=["c0", "c1", "c2"], average="macro", zero_division=0), "balanced_accuracy": balanced_accuracy_score(y, pred)}
                summaries.append({**base_row, **scores(df)})
                if phase == "P1":
                    for token, label in (("c0", "warning"), ("c1", "average"), ("c2", "good")):
                        n = int(df["y_true"].eq(token).sum())
                        per_class.append({**base_row, "class_label": label, "support": n, "recall": float((df["y_true"].eq(token) & df["y_pred"].eq(token)).sum() / n) if n else None})
                if split == "TEST" and phase == "P1":
                    aligned = context.reindex(df["enrollment_id_hash"])
                    expected = aligned["CQ_label_final"].map(label_map)
                    if len(df) != len(context) or expected.isna().any() or not np.array_equal(df["y_true"].astype(str).to_numpy(), expected.to_numpy()):
                        raise ValueError(f"Prediction/context enrollment or label mismatch: {path}")
                    for axis in ("course_cohort", "temporal_slice"):
                        groups = aligned[axis].to_numpy()
                        for group in sorted(set(groups)):
                            slices.append({**base_row, "axis": axis, "slice": group, "row_alignment": "salted_enrollment_hash_and_label_match", **scores(df.loc[groups == group])})
    out = base / "L2_facts" / "report_exports" / "task=CQ" / "report_id=RNN_prefix_audit_20261017"
    if out.exists():
        raise FileExistsError(f"Immutable audit output already exists: {out}")
    out.mkdir(parents=True)
    for name, frame in {"run_inventory": pd.DataFrame(inventory), "test_prefix_mask_audit": prefix, "test_prefix_static_parity_audit": parity, "w1_p1_course_cohort_label_support": cohort, "w1_prediction_summary": pd.DataFrame(summaries), "w1_p1_per_class_predictions": pd.DataFrame(per_class), "w1_p1_slice_metrics": pd.DataFrame(slices)}.items():
        frame.to_csv(out / f"{name}.csv", index=False)
    summary = {"task": "CQ", "model": "RNN", "seed": 42, "data_release_id": release_id, "layout_count": len(layouts), "layout_signatures": signatures, "static_columns": sorted(columns), "test_prefix_mask_sample_ok": bool(prefix["future_mask_ok_sample"].all()), "test_static_parity_ok": bool(parity["values_identical"].all()), "w1_prediction_cells": len(summaries), "w1_p1_slice_cells": len(slices), "output": str(out)}
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    volume.commit()
    return summary


@app.local_entrypoint()
def cli():
    print(json.dumps(audit.remote(), indent=2))
