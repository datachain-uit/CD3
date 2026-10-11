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
DEFAULT_REPORT_ID = "RNN_seed42_v3_1_clean_r2"

app = modal.App(APP_NAME)
volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=False)
image = (modal.Image.debian_slim(python_version="3.12")
         .pip_install("numpy>=1.26", "pandas>=2.2", "pyarrow>=16", "scikit-learn>=1.5")
         .add_local_python_source("imputation_core")
         .add_local_python_source("release_core"))


@app.function(image=image, volumes={MOUNT: volume}, cpu=1, memory=1024, timeout=10 * 60)
def rnn_status(model_name: str = "RNN", seed: int = 42) -> dict:
    """Read-only current-release inventory for the 17 × 3 LO model grid."""
    from imputation_core.meta_storage import release_inventory
    from release_core import resolve_release

    spec = resolve_release(TASK, "LO_V3_1")
    active_data_release_id = release_inventory(
        Path(MOUNT) / "input" / spec["input_dir"], task=TASK
    )["data_release_id"]
    base = Path(MOUNT) / f"meta_release={META_RELEASE}" / "L1_runs"
    pattern = (f"task=LO/feature_regime={REGIME}/window_id=*/pipeline_id=*/"
               f"model_name={model_name}/seed={seed}/run_id=*/attempt_id=*/run_manifest.json")
    latest: dict[tuple[str, str], tuple[float, dict]] = {}
    for path in base.glob(pattern):
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (manifest.get("release_id") != spec["release_id"] or
                manifest.get("split_registry_id") != spec["split_registry_id"] or
                manifest.get("split_version") != spec["split_version"] or
                manifest.get("phase_version") != spec["phase_version"] or
                manifest.get("data_release_id") != active_data_release_id):
            continue
        key = str(manifest.get("window_id")), str(manifest.get("pipeline_id"))
        candidate = (path.stat().st_mtime, manifest)
        if key not in latest or candidate[0] > latest[key][0]:
            latest[key] = candidate

    rows = []
    for window in ("W1", "W2", "W3"):
        for number in range(17):
            pipeline = f"V{number}"
            manifest = latest.get((window, pipeline), (0.0, {}))[1]
            rows.append({
                "window_id": window,
                "pipeline_id": pipeline,
                "run_status": manifest.get("run_status", "NOT_STARTED"),
                "progress_stage": manifest.get("progress_stage"),
                "attempt_id": manifest.get("attempt_id"),
                "best_epoch": manifest.get("best_epoch"),
            })
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["run_status"]] = counts.get(row["run_status"], 0) + 1
    return {
        "task": TASK,
        "release_id": spec["release_id"],
        "data_release_id": active_data_release_id,
        "model_name": model_name,
        "seed": seed,
        "expected_cells": 51,
        "status_counts": counts,
        "completed_cells": counts.get("SUCCESS", 0),
        "rows": rows,
    }


def _latest_successful_runs(base: Path, *, model_name: str, seed: int,
                            release_spec: dict[str, str], data_release_id: str) -> list[tuple[Path, dict]]:
    # Use monotonic attempt_id suffix, not volume mtime, to select a retry.
    selected: dict[tuple[str, str], tuple[int, float, Path, dict]] = {}
    pattern = (f"task=LO/feature_regime=LO_FULL_EARLY/window_id=*/pipeline_id=*/"
               f"model_name={model_name}/seed={seed}/run_id=*/attempt_id=*/run_manifest.json")
    for manifest_path in base.glob(pattern):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("run_status") != "SUCCESS":
            continue
        if (manifest.get("release_id") != release_spec["release_id"] or
                manifest.get("split_registry_id") != release_spec["split_registry_id"] or
                manifest.get("split_version") != release_spec["split_version"] or
                manifest.get("phase_version") != release_spec["phase_version"] or
                manifest.get("data_release_id") != data_release_id):
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


def _read_manifest_paths(paths: list[str]):
    """Read only files explicitly claimed by a selected immutable manifest.

    Never scan a window-wide L2 directory: it may contain valid historical
    releases and therefore is not an admissible provenance selector.
    """
    import pandas as pd

    selected = [Path(path) for path in paths]
    missing = [str(path) for path in selected if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Manifest-declared L2 facts are missing: {missing}")
    return pd.concat([pd.read_parquet(path) for path in selected], ignore_index=True)


def _l2_fact_path(facts: Path, *, fact_name: str, window: str, phase: str,
                  pipeline: str, model_name: str, run_id: str, attempt_id: str) -> str:
    return str(
        facts / fact_name / "task=LO" / f"feature_regime={REGIME}" /
        f"window_id={window}" / f"phase_id={phase}" / "stage=S3_MODEL" /
        f"pipeline_id={pipeline}" / f"model_name={model_name}" /
        f"run_id={run_id}" / f"attempt_id={attempt_id}" / "part-00000.parquet"
    )


def _overlay_canonical_s_leak(sanity, runs_df, *, facts: Path, release_id: str,
                               data_release_id: str, seed: int):
    """Overlay the one real-parent leakage probe shared by augmented variants."""
    import numpy as np
    import pandas as pd

    root = (facts / "canonical_s_leak" / "task=LO" / f"feature_regime={REGIME}" /
            f"release_id={release_id}" /
            f"data_release_id={data_release_id.replace(':', '_')}" / f"seed={seed}")
    paths = sorted(root.glob("part-*.parquet"))
    if not paths:
        raise FileNotFoundError(f"Missing canonical S_leak facts under {root}")
    canonical = pd.concat([pd.read_parquet(path) for path in paths], ignore_index=True)
    expected = 15 * 2 * 4
    if len(canonical) != expected:
        raise RuntimeError(f"Incomplete canonical S_leak facts: expected {expected}, got {len(canonical)}")
    parents = runs_df[["pipeline_id", "window_id", "run_id", "parent_imputation_run_id"]]
    result = sanity.merge(parents, on=["pipeline_id", "window_id", "run_id"], how="left", validate="many_to_one")
    result = result.merge(
        canonical[["window_id", "parent_imputation_run_id", "eval_split", "phase_id",
                   "s_leak_probe_auc", "s_leak", "probe_fit_rows", "s_leak_probe_n_eval",
                   "probe_fit_scope", "probe_score_scope"]],
        on=["window_id", "parent_imputation_run_id", "eval_split", "phase_id"], how="left",
        suffixes=("_old", "_canonical"), validate="many_to_one",
    )
    if result["s_leak_canonical"].isna().any():
        raise RuntimeError("A selected LO sanity fact has no canonical parent S_leak")
    result["s_leak"] = result.pop("s_leak_canonical")
    result["s_leak_probe_auc"] = result.pop("s_leak_probe_auc_canonical")
    result["s_leak_probe_fit_rows"] = result.pop("probe_fit_rows")
    result["s_leak_probe_n_eval"] = result.pop("s_leak_probe_n_eval")
    result["s_leak_probe_fit_once"] = True
    result["s_leak_definition_version"] = "parent_imputation_real_rows_canonical_v1"
    parts = result[["s_nan", "s_maj_jsd", "s_ent", "s_drift", "s_eff", "s_leak"]].to_numpy(dtype=float)
    result["s_san_plus"] = np.prod(np.clip(parts, 1e-3, 1.0), axis=1) ** (1 / 6)
    parts_v2 = result[["s_nan", "s_maj_jsd", "s_cal", "s_drift", "s_eff", "s_leak"]].to_numpy(dtype=float)
    result["s_san_plus_v2"] = np.prod(np.clip(parts_v2, 1e-3, 1.0), axis=1) ** (1 / 6)
    result["acctempo_m3"] = (result["s_perf"].clip(lower=1e-3) ** 0.6) * (result["s_san_plus"] ** 0.4)
    return result.drop(columns=["s_leak_old", "parent_imputation_run_id"], errors="ignore")


@app.function(image=image, volumes={MOUNT: volume}, cpu=2, memory=4096, timeout=60 * 60)
def export_lo_rnn_facts(model_name: str = "RNN", seed: int = 42, report_id: str = "") -> dict:
    import pandas as pd
    from imputation_core.meta_storage import release_inventory
    from release_core import resolve_release

    base = Path(MOUNT) / f"meta_release={META_RELEASE}"
    spec = resolve_release(TASK, "LO_V3_1")
    active_data_release_id = release_inventory(
        Path(MOUNT) / "input" / spec["input_dir"], task=TASK
    )["data_release_id"]
    runs = _latest_successful_runs(
        base / "L1_runs", model_name=model_name, seed=seed,
        release_spec=spec, data_release_id=active_data_release_id,
    )
    if len(runs) != 51:
        raise RuntimeError(f"Expected 51 successful LO RNN V3.1 cells, found {len(runs)}")

    (metrics_test_frames, metrics_validation_frames, sanity_test_frames, sanity_validation_frames,
     resource_frames, selection_frames, per_class_frames, bootstrap_frames, calibration_frames,
     slice_frames, run_rows) = ([], [], [], [], [], [], [], [], [], [], [])
    facts = base / "L2_facts"
    for model_root, manifest in runs:
        pipeline, window = manifest["pipeline_id"], manifest["window_id"]
        run_id, attempt_id = manifest["run_id"], manifest["attempt_id"]
        common = {"pipeline_id": pipeline, "window_id": window, "run_id": run_id, "attempt_id": attempt_id}
        manifest_mtime_utc = datetime.fromtimestamp(
            model_root.joinpath("run_manifest.json").stat().st_mtime, timezone.utc
        ).isoformat()
        run_rows.append({
            **common,
            "created_at_utc": manifest.get("created_at_utc") or manifest_mtime_utc,
            "created_at_source": "manifest" if manifest.get("created_at_utc") else "manifest_mtime_fallback",
            "manifest_mtime_utc": manifest_mtime_utc,
            "model_revision": manifest.get("model_revision"),
            "config_version": manifest.get("config_version"),
            "data_release_id": manifest.get("data_release_id"),
            "input_root": manifest.get("input_root"),
            "train_input_path": manifest.get("train_input_path"),
            "parent_imputation_run_id": manifest.get("parent_imputation_run_id"),
            "parent_augmentation_run_id": manifest.get("parent_augmentation_run_id"),
            "best_epoch": manifest.get("best_epoch"),
            "train_rows": manifest.get("train_rows"),
            "validation_rows": manifest.get("validation_rows"),
            "test_rows": json.dumps(manifest.get("test_rows", {}), sort_keys=True),
            "master_seed": manifest.get("master_seed"),
            "seed_model": manifest.get("seed_model"),
            "seed_dataloader": manifest.get("seed_dataloader"),
            "seed_augmentation": manifest.get("seed_augmentation"),
            "seed_preprocess": manifest.get("seed_preprocess"),
            "split_version": manifest.get("split_version"),
            "phase_version": manifest.get("phase_version"),
        })
        metrics = _read_manifest_paths(list(manifest.get("metrics_paths", [])))
        metrics = metrics[(metrics.get("pipeline_id") == pipeline) & (metrics.get("model_name") == model_name) &
                          (metrics.get("run_id") == run_id) & (metrics.get("attempt_id") == attempt_id)]
        metrics_test_frames.append(metrics[metrics.get("eval_split") == "TEST"])
        metrics_validation_frames.append(metrics[metrics.get("eval_split") == "VALIDATION"])
        sanity_paths = [
            str(facts / "sanity_components" / "task=LO" / f"feature_regime={REGIME}" /
                f"window_id={window}" / f"phase_id={phase}" / "stage=S3_MODEL" /
                f"pipeline_id={pipeline}" / f"model_name={model_name}" / f"run_id={run_id}" /
                f"attempt_id={attempt_id}" / f"eval_split={eval_split}.parquet")
            for eval_split in ("TEST", "VALIDATION")
            for phase in ("P1", "P2", "P3", "P4")
        ]
        sanity_all = _read_manifest_paths(sanity_paths)
        sanity_all = sanity_all[(sanity_all.get("pipeline_id") == pipeline) & (sanity_all.get("model_name") == model_name) &
                                (sanity_all.get("run_id") == run_id) & (sanity_all.get("attempt_id") == attempt_id)]
        sanity_test_frames.append(sanity_all[sanity_all.get("eval_split") == "TEST"])
        sanity_validation_frames.append(sanity_all[sanity_all.get("eval_split") == "VALIDATION"])
        slice_path = (facts / "evaluation_slices" / "task=LO" / f"feature_regime={REGIME}" /
                      f"window_id={window}" / "stage=S3_MODEL" / f"pipeline_id={pipeline}" /
                      f"model_name={model_name}" / f"run_id={run_id}" /
                      f"attempt_id={attempt_id}" / "part-00000.parquet")
        slices = _read_manifest_paths([str(slice_path)])
        slice_frames.append(slices[(slices.get("pipeline_id") == pipeline) &
                                   (slices.get("model_name") == model_name) &
                                   (slices.get("run_id") == run_id) &
                                   (slices.get("attempt_id") == attempt_id)])
        resource = _read_manifest_paths([str(manifest.get("resource_path", ""))])
        resource = resource[(resource.get("pipeline_id") == pipeline) & (resource.get("model_name") == model_name) &
                            (resource.get("run_id") == run_id) & (resource.get("attempt_id") == attempt_id)]
        resource_frames.append(resource)
        selection = _read_manifest_paths([str(manifest.get("selection_audit_path", ""))]).copy()
        history = pd.read_parquet(model_root / "train_history.parquet")
        if history.empty:
            raise RuntimeError(f"Empty train history for {pipeline}/{window}/{run_id}")
        best_score = float(selection.iloc[0]["best_score"])
        margin = selection.iloc[0].get("selection_margin")
        margin = 0.0 if pd.isna(margin) else float(margin)
        selection["checkpoint_count_evaluated"] = int(len(history))
        selection["n_checkpoints_within_margin"] = int(
            (history["validation_macro_f1_mean_p1_p4"].astype(float) >= best_score - margin - 1e-12).sum()
        )
        selection["within_margin_rule"] = "validation_macro_f1_mean_p1_p4>=best_score-selection_margin"
        selection_frames.append(selection)
        for phase in ("P1", "P2", "P3", "P4"):
            for fact_name, target in (("metrics_per_class", per_class_frames),
                                      ("bootstrap_metrics_per_class", bootstrap_frames),
                                      ("calibration", calibration_frames)):
                target.append(_read_manifest_paths([_l2_fact_path(
                    facts, fact_name=fact_name, window=window, phase=phase, pipeline=pipeline,
                    model_name=model_name, run_id=run_id, attempt_id=attempt_id,
                )]))

    metrics = pd.concat(metrics_test_frames, ignore_index=True) if metrics_test_frames else pd.DataFrame()
    validation = pd.concat(metrics_validation_frames, ignore_index=True) if metrics_validation_frames else pd.DataFrame()
    sanity = pd.concat(sanity_test_frames, ignore_index=True) if sanity_test_frames else pd.DataFrame()
    sanity_validation = pd.concat(sanity_validation_frames, ignore_index=True) if sanity_validation_frames else pd.DataFrame()
    resource = pd.concat(resource_frames, ignore_index=True) if resource_frames else pd.DataFrame()
    selection = pd.concat(selection_frames, ignore_index=True) if selection_frames else pd.DataFrame()
    per_class = pd.concat(per_class_frames, ignore_index=True) if per_class_frames else pd.DataFrame()
    bootstrap = pd.concat(bootstrap_frames, ignore_index=True) if bootstrap_frames else pd.DataFrame()
    calibration = pd.concat(calibration_frames, ignore_index=True) if calibration_frames else pd.DataFrame()
    slices = pd.concat(slice_frames, ignore_index=True) if slice_frames else pd.DataFrame()
    runs_df = pd.DataFrame(run_rows)
    sanity = _overlay_canonical_s_leak(sanity, runs_df, facts=facts, release_id=spec["release_id"],
                                       data_release_id=active_data_release_id, seed=seed)
    sanity_validation = _overlay_canonical_s_leak(sanity_validation, runs_df, facts=facts, release_id=spec["release_id"],
                                                  data_release_id=active_data_release_id, seed=seed)
    required = {"metrics_test": 51 * 4, "metrics_validation": 51 * 4,
                "sanity_test": 51 * 4, "sanity_validation": 51 * 4, "resource": 51,
                "checkpoint_selection": 51, "metrics_per_class": 51 * 2 * 4 * 3,
                "bootstrap_metrics_per_class": 51 * 2 * 4 * 3 * 3, "calibration": 51 * 2 * 4,
                "evaluation_slices": 51 * 2 * 4 * 3 * 3}
    actual = {"metrics_test": len(metrics), "metrics_validation": len(validation),
              "sanity_test": len(sanity), "sanity_validation": len(sanity_validation),
              "resource": len(resource), "checkpoint_selection": len(selection),
              "metrics_per_class": len(per_class), "bootstrap_metrics_per_class": len(bootstrap),
              "calibration": len(calibration), "evaluation_slices": len(slices)}
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
    validation_sanity_summary = sanity_validation.groupby(
        ["pipeline_id", "window_id"], as_index=False
    )[sanity_fields].mean()

    selected_report_id = report_id or (
        DEFAULT_REPORT_ID if model_name == "RNN" and seed == 42 else f"{model_name}_seed{seed}_v3_1_clean"
    )
    export = facts / "report_exports" / "task=LO" / f"report_id={selected_report_id}"
    export.mkdir(parents=True, exist_ok=True)
    metrics.to_parquet(export / "metrics_test_long.parquet", index=False)
    validation.to_parquet(export / "metrics_validation_long.parquet", index=False)
    sanity.to_parquet(export / "sanity_test_long.parquet", index=False)
    sanity_validation.to_parquet(export / "sanity_validation_long.parquet", index=False)
    resource.to_parquet(export / "resource_long.parquet", index=False)
    selection.to_parquet(export / "checkpoint_selection_long.parquet", index=False)
    per_class.to_parquet(export / "metrics_per_class_long.parquet", index=False)
    bootstrap.to_parquet(export / "bootstrap_metrics_per_class_long.parquet", index=False)
    calibration.to_parquet(export / "calibration_long.parquet", index=False)
    slices.to_parquet(export / "strict_overlap_metrics_long.parquet", index=False)
    runs_df.to_parquet(export / "run_inventory.parquet", index=False)
    test_summary.to_parquet(export / "test_summary_p1_p4_mean.parquet", index=False)
    sanity_summary.to_parquet(export / "sanity_summary_p1_p4_mean.parquet", index=False)
    validation_sanity_summary.to_parquet(export / "validation_sanity_summary_p1_p4_mean.parquet", index=False)
    names = ("metrics_test_long.parquet", "metrics_validation_long.parquet",
             "sanity_test_long.parquet", "sanity_validation_long.parquet", "resource_long.parquet",
             "checkpoint_selection_long.parquet", "metrics_per_class_long.parquet",
             "bootstrap_metrics_per_class_long.parquet", "calibration_long.parquet",
             "strict_overlap_metrics_long.parquet", "run_inventory.parquet",
             "test_summary_p1_p4_mean.parquet", "sanity_summary_p1_p4_mean.parquet",
             "validation_sanity_summary_p1_p4_mean.parquet")
    metadata = {"task": TASK, "report_id": selected_report_id, "exporter_revision": "clean_provenance_r2",
                "release_id": spec["release_id"], "data_release_id": active_data_release_id,
                "model_name": model_name, "seed": seed, "split_version": SPLIT_VERSION,
                "phase_version": PHASE_VERSION, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "expected_rows": required, "actual_rows": actual,
                "paths": {name: str(export / name) for name in names}}
    (export / "export_manifest.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    volume.commit()
    return metadata


@app.local_entrypoint()
def cli(model_name: str = "RNN", seed: int = 42, mode: str = "export", report_id: str = "") -> None:
    if mode == "export":
        result = export_lo_rnn_facts.remote(model_name, seed, report_id)
    elif mode == "status":
        result = rnn_status.remote(model_name, seed)
    else:
        raise ValueError("mode must be export or status")
    print(json.dumps(result, indent=2))
