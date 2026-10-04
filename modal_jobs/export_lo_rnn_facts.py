"""CPU-only exporter for immutable LO recurrent-model L2 facts.

The job is read-only with respect to model inputs and checkpoints.  It selects
one successful immutable run for every pipeline/window, verifies that the
complete 17 x 3 x 4 TEST fact set exists, and writes compact tables for the
LO report.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import modal


APP_NAME, VOLUME_NAME, MOUNT = "tempo-lo-report-export-v1", "tempo-data-v1", "/data"
META_RELEASE, TASK, REGIME = "imputation-v1", "LO", "LO_FULL_EARLY"
SPLIT_VERSION, PHASE_VERSION = "v3_1", "wide_prefix_v3_1"

app = modal.App(APP_NAME)
volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=False)
image = modal.Image.debian_slim(python_version="3.12").pip_install("pandas>=2.2", "pyarrow>=16")


def _latest_successful_runs(base: Path, *, model_name: str, seed: int) -> list[tuple[Path, dict]]:
    # Use monotonic attempt_id suffix, not volume mtime, to select a retry.
    selected: dict[tuple[str, str], tuple[int, float, Path, dict]] = {}
    pattern = (f"task=LO/feature_regime=LO_FULL_EARLY/window_id=*/pipeline_id=*/"
               f"model_name={model_name}/seed={seed}/run_id=*/attempt_id=*/run_manifest.json")
    for manifest_path in base.glob(pattern):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("run_status") != "SUCCESS":
            continue
        if manifest.get("split_version") != SPLIT_VERSION or manifest.get("phase_version") != PHASE_VERSION:
            continue
        window, pipeline = manifest.get("window_id"), manifest.get("pipeline_id")
        if window not in {"W1", "W2", "W3"} or pipeline not in {f"V{i}" for i in range(17)}:
            continue
        key = pipeline, window
        suffix = str(manifest.get("attempt_id", "")).rsplit("-", 1)[-1]
        attempt_number = int(suffix) if suffix.isdigit() else 0
        candidate = (attempt_number, manifest_path.stat().st_mtime, manifest_path.parent, manifest)
        if key not in selected or candidate[:2] > selected[key][:2]:
            selected[key] = candidate
    return [(path, manifest) for _, _, path, manifest in selected.values()]


def _read_all(folder: Path):
    import pandas as pd

    files = sorted(folder.rglob("*.parquet")) if folder.exists() else []
    return pd.concat([pd.read_parquet(file) for file in files], ignore_index=True) if files else pd.DataFrame()


@app.function(image=image, volumes={MOUNT: volume}, cpu=2, memory=4096, timeout=60 * 60)
def export_lo_rnn_facts(model_name: str = "RNN", seed: int = 42) -> dict:
    import pandas as pd

    base = Path(MOUNT) / f"meta_release={META_RELEASE}"
    runs = _latest_successful_runs(base / "L1_runs", model_name=model_name, seed=seed)
    if len(runs) != 51:
        raise RuntimeError(f"Expected 51 successful LO RNN V3.1 cells, found {len(runs)}")

    metrics_frames, sanity_frames, resource_frames, run_rows = [], [], [], []
    facts = base / "L2_facts"
    for model_root, manifest in runs:
        pipeline, window = manifest["pipeline_id"], manifest["window_id"]
        run_id, attempt_id = manifest["run_id"], manifest["attempt_id"]
        common = {"pipeline_id": pipeline, "window_id": window, "run_id": run_id, "attempt_id": attempt_id}
        run_rows.append({**common, "best_epoch": manifest.get("best_epoch"), "train_rows": manifest.get("train_rows"),
                         "validation_rows": manifest.get("validation_rows"), "split_version": manifest.get("split_version"),
                         "phase_version": manifest.get("phase_version")})
        metrics = _read_all(facts / "metrics_overall" / "task=LO" / f"feature_regime={REGIME}" / f"window_id={window}")
        if not metrics.empty:
            metrics = metrics[(metrics.get("pipeline_id") == pipeline) & (metrics.get("model_name") == model_name) &
                              (metrics.get("run_id") == run_id) & (metrics.get("attempt_id") == attempt_id)]
            if "eval_split" in metrics:
                metrics = metrics[metrics["eval_split"] == "TEST"]
            metrics_frames.append(metrics)
        sanity = _read_all(facts / "sanity_components" / "task=LO" / f"feature_regime={REGIME}" / f"window_id={window}")
        if not sanity.empty:
            sanity = sanity[(sanity.get("pipeline_id") == pipeline) & (sanity.get("model_name") == model_name) &
                            (sanity.get("run_id") == run_id) & (sanity.get("attempt_id") == attempt_id)]
            if "eval_split" in sanity:
                sanity = sanity[sanity["eval_split"] == "TEST"]
            sanity_frames.append(sanity)
        resource = _read_all(facts / "resource_usage" / "task=LO" / f"feature_regime={REGIME}" / f"window_id={window}")
        if not resource.empty:
            resource = resource[(resource.get("pipeline_id") == pipeline) & (resource.get("model_name") == model_name) &
                                (resource.get("run_id") == run_id) & (resource.get("attempt_id") == attempt_id)]
            resource_frames.append(resource)

    metrics = pd.concat(metrics_frames, ignore_index=True) if metrics_frames else pd.DataFrame()
    sanity = pd.concat(sanity_frames, ignore_index=True) if sanity_frames else pd.DataFrame()
    resource = pd.concat(resource_frames, ignore_index=True) if resource_frames else pd.DataFrame()
    runs_df = pd.DataFrame(run_rows)
    required = {"metrics_test": 51 * 4, "sanity_test": 51 * 4, "resource": 51}
    actual = {"metrics_test": len(metrics), "sanity_test": len(sanity), "resource": len(resource)}
    if actual != required:
        raise RuntimeError(f"Incomplete L2 facts: expected={required}, actual={actual}")

    metric_fields = [field for field in ("f1_macro", "balanced_accuracy", "mcc", "roc_auc_macro_ovr",
                                         "pr_auc_macro", "multiclass_nll", "multiclass_brier", "top_label_ece_15")
                     if field in metrics.columns]
    test_summary = metrics.groupby(["pipeline_id", "window_id"], as_index=False)[metric_fields].mean()
    sanity_fields = [field for field in ("s_nan", "s_maj_jsd", "s_ent", "s_drift", "s_eff", "s_leak",
                                         "s_san_plus", "s_cal", "s_san_plus_v2", "s_perf", "acctempo_m3")
                     if field in sanity.columns]
    sanity_summary = sanity.groupby(["pipeline_id", "window_id"], as_index=False)[sanity_fields].mean()

    export = facts / "report_exports" / "task=LO" / f"report_id={model_name}_seed{seed}_v3_1"
    export.mkdir(parents=True, exist_ok=True)
    metrics.to_parquet(export / "metrics_test_long.parquet", index=False)
    sanity.to_parquet(export / "sanity_test_long.parquet", index=False)
    resource.to_parquet(export / "resource_long.parquet", index=False)
    runs_df.to_parquet(export / "run_inventory.parquet", index=False)
    test_summary.to_parquet(export / "test_summary_p1_p4_mean.parquet", index=False)
    sanity_summary.to_parquet(export / "sanity_summary_p1_p4_mean.parquet", index=False)
    names = ("metrics_test_long.parquet", "sanity_test_long.parquet", "resource_long.parquet",
             "run_inventory.parquet", "test_summary_p1_p4_mean.parquet", "sanity_summary_p1_p4_mean.parquet")
    metadata = {"task": TASK, "model_name": model_name, "seed": seed, "split_version": SPLIT_VERSION,
                "phase_version": PHASE_VERSION, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "expected_rows": required, "actual_rows": actual,
                "paths": {name: str(export / name) for name in names}}
    (export / "export_manifest.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    volume.commit()
    return metadata


@app.local_entrypoint()
def cli(model_name: str = "RNN", seed: int = 42) -> None:
    print(json.dumps(export_lo_rnn_facts.remote(model_name, seed), indent=2))
