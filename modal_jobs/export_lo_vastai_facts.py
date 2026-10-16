"""Export CQ/LO F1 seed-42 VastAI facts already ingested into the L2 Volume.

This exporter is deliberately read-only for L1 model artifacts.  It consumes
only the compact ``execution_backend=vastai_portable_runner`` L2 partitions
created by :mod:`ingest_lo_vastai_facts_app` and creates a conventional report
bundle under ``L2_facts/report_exports``.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import modal


VOLUME_NAME, MOUNT = "tempo-data-v1", "/data"
META_RELEASE, SEED = "imputation-v1", 42
TASK = os.environ.get("VASTAI_TASK", "LO").strip().upper()
TASK_SPECS = {
    "CQ": {"regime": "CQ_RAW_EARLY", "release": "CQ_V2_2", "ingest": "vastai_f1_seed42_clean_20261016_r1"},
    "LO": {"regime": "LO_FULL_EARLY", "release": "LO_V3_1", "ingest": "vastai_f2_seed42_clean_20261015_r2"},
}
if TASK not in TASK_SPECS:
    raise ValueError("VASTAI_TASK must be CQ or LO")
REGIME = TASK_SPECS[TASK]["regime"]
APP_NAME = f"tempo-export-{TASK.lower()}-vastai-facts-v1"
BACKEND = "vastai_portable_runner"
INGEST_ID = os.environ.get("VASTAI_INGEST_ID", TASK_SPECS[TASK]["ingest"])
DEFAULT_REPORT_ID = os.environ.get(
    "VASTAI_REPORT_ID",
    f"F1_seed42_{'v2_2' if TASK == 'CQ' else 'v3_1'}_vastai_ingested_r1",
)
FAMILIES = ("RNN", "LSTM", "GRU", "BILSTM")
EXPECTED = {
    "metrics_overall": 1632,
    "sanity_components": 1632,
    "metrics_per_class": 4896,
    "bootstrap_metrics_per_class": 14688,
    "evaluation_slices": 4896,
    "checkpoint_selection": 204,
    "canonical_s_leak": 120,
    "resource_usage": 204,
}

app = modal.App(APP_NAME)
volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=False)
image = modal.Image.debian_slim(python_version="3.12").pip_install(
    "numpy>=1.26", "pandas>=2.2", "pyarrow>=16"
)


def _read_compact(facts: Path, fact_name: str):
    import pandas as pd

    root = (facts / fact_name / "task=LO" / f"feature_regime={REGIME}" /
            f"execution_backend={BACKEND}" / f"ingest_id={INGEST_ID}")
    paths = sorted(root.rglob("*.parquet")) if root.is_dir() else []
    if not paths:
        raise FileNotFoundError(f"No imported {fact_name} partitions under {root}")
    frame = pd.concat([pd.read_parquet(path) for path in paths], ignore_index=True)
    expected = EXPECTED[fact_name]
    if len(frame) != expected:
        raise RuntimeError(f"{fact_name}: expected {expected} rows, found {len(frame)}")
    return frame


def _write_idempotent(frame, path: Path) -> None:
    import pandas as pd

    if path.exists():
        current = pd.read_parquet(path)
        if current.equals(frame):
            return
        raise FileExistsError(f"Refusing to replace non-identical report fact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)


def _summary(frame, fields: tuple[str, ...]):
    """Mean over P1-P4 per pipeline x window x family.

    The family dimension is kept on purpose: the registered reading rule forbids pooling recurrent families,
    and a per-cell composite averaged over phases is not the composite of averaged components (the report
    tables state this).  The output carries ``averaging_rule`` so that no consumer mistakes it for a cell fact.
    """
    selected = [field for field in fields if field in frame.columns]
    out = frame.groupby(["pipeline_id", "window_id", "model_name"], as_index=False)[selected].mean()
    out["averaging_rule"] = "mean_of_per_cell_values_over_P1_P4"
    return out


@app.function(image=image, volumes={MOUNT: volume}, cpu=2, memory=4096, timeout=30 * 60)
def export_lo_vastai_facts(report_id: str = DEFAULT_REPORT_ID) -> dict:
    """Create a verified report export from immutable external CQ/LO L2 facts."""
    import numpy as np
    import pandas as pd

    facts = Path(MOUNT) / f"meta_release={META_RELEASE}" / "L2_facts"
    loaded = {name: _read_compact(facts, name) for name in EXPECTED}
    metrics = loaded["metrics_overall"]
    sanity = loaded["sanity_components"].copy()
    canonical = loaded["canonical_s_leak"]

    key = ["window_id", "parent_pipeline", "eval_split", "phase_id"]
    canonical_check = canonical.groupby(key, dropna=False).size()
    if len(canonical_check) != 120 or canonical_check.max() != 1:
        raise RuntimeError("Canonical S_leak must contain exactly one row per parent/split/phase key")
    sanity = sanity.merge(
        canonical[key + ["s_leak", "s_leak_probe_auc", "probe_fit_rows", "s_leak_probe_n_eval",
                         "probe_fit_scope", "probe_score_scope"]],
        on=key, how="left", suffixes=("_run", "_canonical"), validate="many_to_one",
    )
    if sanity["s_leak_canonical"].isna().any():
        raise RuntimeError("Imported sanity row has no canonical parent S_leak")
    sanity["s_leak"] = sanity.pop("s_leak_canonical")
    # Audit rows retain their own probe metadata, so pandas suffixes both
    # source columns.  The canonical parent-real-row probe is authoritative.
    sanity["s_leak_probe_fit_rows"] = sanity.pop("probe_fit_rows_canonical")
    sanity["s_leak_probe_n_eval"] = sanity.pop("s_leak_probe_n_eval_canonical")
    sanity["s_leak_probe_fit_once"] = True
    sanity["s_leak_definition_version"] = "parent_imputation_real_rows_canonical_v1"
    components = ["s_nan", "s_maj_jsd", "s_ent", "s_drift", "s_eff", "s_leak"]
    components_v2 = ["s_nan", "s_maj_jsd", "s_cal", "s_drift", "s_eff", "s_leak"]
    sanity["s_san_plus"] = np.prod(np.clip(sanity[components].to_numpy(float), 1e-3, 1.0), axis=1) ** (1 / 6)
    sanity["s_san_plus_v2"] = np.prod(np.clip(sanity[components_v2].to_numpy(float), 1e-3, 1.0), axis=1) ** (1 / 6)
    sanity["acctempo_m3"] = sanity["s_perf"].clip(lower=1e-3) ** 0.6 * sanity["s_san_plus"] ** 0.4

    test = metrics[metrics["eval_split"] == "TEST"].reset_index(drop=True)
    validation = metrics[metrics["eval_split"] == "VALIDATION"].reset_index(drop=True)
    sanity_test = sanity[sanity["eval_split"] == "TEST"].reset_index(drop=True)
    sanity_validation = sanity[sanity["eval_split"] == "VALIDATION"].reset_index(drop=True)
    expected_split_rows = 51 * 4
    if any(len(frame) != expected_split_rows for frame in (test, validation, sanity_test, sanity_validation)):
        raise RuntimeError("Expected 204 TEST and 204 VALIDATION metric/sanity facts")

    output = facts / "report_exports" / "task=LO" / f"report_id={report_id}"
    payloads = {
        "metrics_test_long.parquet": test,
        "metrics_validation_long.parquet": validation,
        "sanity_test_long.parquet": sanity_test,
        "sanity_validation_long.parquet": sanity_validation,
        "metrics_per_class_long.parquet": loaded["metrics_per_class"],
        "bootstrap_metrics_per_class_long.parquet": loaded["bootstrap_metrics_per_class"],
        "strict_overlap_metrics_long.parquet": loaded["evaluation_slices"],
        "checkpoint_selection_long.parquet": loaded["checkpoint_selection"],
        "canonical_s_leak_long.parquet": canonical,
        "resource_long.parquet": loaded["resource_usage"],
        "test_summary_p1_p4_mean.parquet": _summary(test, ("f1_macro", "balanced_accuracy", "accuracy", "acctempo_m3")),
        "sanity_summary_p1_p4_mean.parquet": _summary(sanity_test, tuple(components + ["s_san_plus", "s_cal", "s_san_plus_v2", "s_perf", "acctempo_m3"])),
        "validation_sanity_summary_p1_p4_mean.parquet": _summary(sanity_validation, tuple(components + ["s_san_plus", "s_cal", "s_san_plus_v2", "s_perf", "acctempo_m3"])),
    }
    for name, frame in payloads.items():
        _write_idempotent(frame.reset_index(drop=True), output / name)
    metadata = {
        "task": TASK, "report_id": report_id, "release_id": TASK_SPECS[TASK]["release"], "seed": SEED,
        "ingest_id": INGEST_ID,
        "execution_backend": BACKEND, "exporter_revision": "external_vastai_l2_r2_family_summaries",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "expected_rows": EXPECTED,
        "actual_rows": {name: len(frame) for name, frame in loaded.items()},
        "paths": {name: str(output / name) for name in payloads},
    }
    manifest = output / "export_manifest.json"
    if manifest.exists() and json.loads(manifest.read_text(encoding="utf-8")) != metadata:
        # Timestamp is intentionally volatile; retain an immutable export once
        # its fact payloads have already passed idempotence checks.
        metadata["generated_at_utc"] = json.loads(manifest.read_text(encoding="utf-8")).get("generated_at_utc")
    manifest.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    volume.commit()
    return metadata


@app.local_entrypoint()
def cli(report_id: str = DEFAULT_REPORT_ID) -> None:
    print(json.dumps(export_lo_vastai_facts.remote(report_id), indent=2))
