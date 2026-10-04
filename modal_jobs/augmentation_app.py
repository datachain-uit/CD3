"""TRAIN-only phase-safe augmentation on Modal."""
from __future__ import annotations

import json
import hashlib
import re
import time
from pathlib import Path
import modal

APP_NAME, VOLUME_NAME, MOUNT = "tempo-augmentation-v1", "tempo-data-v1", "/data"
app = modal.App(APP_NAME)
volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)
image = (modal.Image.debian_slim(python_version="3.12")
         .pip_install("numpy>=1.26", "pandas>=2.2", "pyarrow>=16", "scikit-learn>=1.5")
         .add_local_python_source("augmentation_core")
         .add_local_python_source("release_core"))

PARENT = {"V1": "median", "V5": "mean", "V9": "extra_trees", "V13": "mice"}
REGIME = {"CQ": "CQ_RAW_EARLY", "LO": "LO_FULL_EARLY"}


def _augmentation_quality_metrics(train, synthetic, batch, numeric_columns, label_column,
                                  available_mask_columns, missing_mask_columns, *, seed: int, phase_id: str) -> dict:
    """Compute bounded, reproducible post-balance DQ facts.

    Fidelity is evaluated within class on a deterministic maximum of 100k real
    and synthetic rows per class. This bounds memory/time on multi-million-row
    CQ training pools while retaining a declared, reproducible audit sample.
    """
    import numpy as np

    if len(synthetic) == 0:
        return {
            "quality_metric_version": "augmentation_dq_v1",
            "fidelity_sample_cap_per_class": 100000,
            "fidelity_n_classes": 0,
            "real_vs_synth_jsd_mean": None,
            "real_vs_synth_jsd_max": None,
            "real_vs_synth_wasserstein_norm_mean": None,
            "real_vs_synth_wasserstein_norm_max": None,
            "synth_out_of_domain_rate": 0.0,
            "synth_non_integer_count_rate": 0.0,
            "synth_invalid_mask_rate": 0.0,
            "synth_cross_phase_rate": 0.0,
            "synth_cross_phase_columns": 0,
            "synth_cross_phase_check": "no_synthetic_rows",
        }

    rng = np.random.default_rng(seed)
    cap = 100000
    real_labels = train[label_column].to_numpy()
    synth_labels = synthetic[label_column].to_numpy()
    real_values = train.loc[:, numeric_columns].to_numpy(dtype=np.float32, copy=False)
    synth_values = synthetic.loc[:, numeric_columns].to_numpy(dtype=np.float32, copy=False)
    jsd_values, wasserstein_values, domain_bad, domain_total = [], [], 0, 0

    def sample(indices: np.ndarray) -> np.ndarray:
        return indices if len(indices) <= cap else rng.choice(indices, size=cap, replace=False)

    for label in np.unique(synth_labels):
        real_index = sample(np.flatnonzero(real_labels == label))
        synth_index = sample(np.flatnonzero(synth_labels == label))
        if len(real_index) == 0 or len(synth_index) == 0:
            continue
        real_class, synth_class = real_values[real_index], synth_values[synth_index]
        lower, upper = real_class.min(axis=0), real_class.max(axis=0)
        outside = (synth_class < (lower - 1e-6)) | (synth_class > (upper + 1e-6))
        domain_bad += int(outside.sum())
        domain_total += int(outside.size)
        for feature_index in range(real_class.shape[1]):
            observed, generated = real_class[:, feature_index], synth_class[:, feature_index]
            if not (np.isfinite(observed).all() and np.isfinite(generated).all()):
                continue
            edges = np.unique(np.quantile(observed, np.linspace(0.0, 1.0, 21)))
            if len(edges) <= 1:
                jsd_values.append(0.0)
            else:
                real_hist = np.histogram(observed, bins=edges)[0].astype(float) + 1e-12
                synth_hist = np.histogram(generated, bins=edges)[0].astype(float) + 1e-12
                real_prob, synth_prob = real_hist / real_hist.sum(), synth_hist / synth_hist.sum()
                midpoint = (real_prob + synth_prob) / 2.0
                jsd_values.append(float(0.5 * np.sum(real_prob * np.log2(real_prob / midpoint)) +
                                        0.5 * np.sum(synth_prob * np.log2(synth_prob / midpoint))))
            quantiles = np.linspace(0.0, 1.0, 101)
            iqr = float(np.quantile(observed, 0.75) - np.quantile(observed, 0.25))
            if iqr <= 1e-12:
                iqr = float(np.std(observed))
            wasserstein_values.append(float(np.mean(np.abs(np.quantile(observed, quantiles) -
                                                            np.quantile(generated, quantiles))) /
                                              max(iqr, 1e-12)))

    count_like = [index for index, column in enumerate(numeric_columns)
                  if re.search(r"(?:^|_)(?:n|count|num|attempt|correct|incorrect|views?)(?:_|$)", column)]
    if count_like:
        count_values = synth_values[:, count_like]
        non_integer_rate = float((np.abs(count_values - np.rint(count_values)) > 1e-6).mean())
    else:
        non_integer_rate = 0.0

    invalid_mask, total_masks = 0, 0
    for column in available_mask_columns:
        expected = np.logical_and(train[column].to_numpy()[batch.parent_a], train[column].to_numpy()[batch.parent_b])
        actual = synthetic[column].to_numpy().astype(bool)
        invalid_mask += int((actual != expected).sum()); total_masks += len(actual)
    for column in missing_mask_columns:
        expected = np.logical_or(train[column].to_numpy()[batch.parent_a], train[column].to_numpy()[batch.parent_b])
        actual = synthetic[column].to_numpy().astype(bool)
        invalid_mask += int((actual != expected).sum()); total_masks += len(actual)

    # A real phase suffix above the requested Pk would mean synthetic data
    # crossed a future-information boundary.  This is computed from the
    # actual interpolated column set rather than reported as a constant.
    allowed_phase = int(phase_id[1:])
    cross_phase_columns = [column for column in numeric_columns
                           if (match := re.search(r"_P([1-4])$", column)) and int(match.group(1)) > allowed_phase]
    cross_phase_cells = len(synthetic) * len(cross_phase_columns)
    possible_cells = max(len(synthetic) * len(numeric_columns), 1)

    return {
        "quality_metric_version": "augmentation_dq_v1",
        "fidelity_sample_cap_per_class": cap,
        "fidelity_n_classes": int(len(np.unique(synth_labels))),
        "fidelity_n_numeric_features": int(len(numeric_columns)),
        "real_vs_synth_jsd_mean": float(np.mean(jsd_values)) if jsd_values else None,
        "real_vs_synth_jsd_max": float(np.max(jsd_values)) if jsd_values else None,
        "real_vs_synth_wasserstein_norm_mean": float(np.mean(wasserstein_values)) if wasserstein_values else None,
        "real_vs_synth_wasserstein_norm_max": float(np.max(wasserstein_values)) if wasserstein_values else None,
        "synth_out_of_domain_rate": float(domain_bad / domain_total) if domain_total else 0.0,
        "synth_non_integer_count_rate": non_integer_rate,
        "synth_invalid_mask_rate": float(invalid_mask / total_masks) if total_masks else 0.0,
        "synth_cross_phase_rate": float(cross_phase_cells / possible_cells),
        "synth_cross_phase_columns": int(len(cross_phase_columns)),
        "synth_cross_phase_check": "interpolated_feature_suffixes",
    }


def _label(task: str) -> str:
    return "CQ_label_final" if task == "CQ" else "LO_performance_label_3"


def _pipeline(parent: str, method: str) -> str:
    table = {"V1": {"CDSMOTE": "V2", "SASMOTE": "V3", "RADIUS_SMOTE": "V4"},
             "V5": {"CDSMOTE": "V6", "SASMOTE": "V7", "RADIUS_SMOTE": "V8"},
             "V9": {"CDSMOTE": "V10", "SASMOTE": "V11", "RADIUS_SMOTE": "V12"},
             "V13": {"CDSMOTE": "V14", "SASMOTE": "V15", "RADIUS_SMOTE": "V16"}}
    return table[parent][method]


def _latest_successful_canonical_train(root: Path, *, spec: dict[str, str]) -> tuple[Path, dict] | None:
    """Resolve the immutable `run_id/attempt_id` layout used by newer runs."""
    candidates = sorted(
        root.glob("run_id=*/attempt_id=*/model_inputs/train.parquet"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for train_path in candidates:
        manifest_path = train_path.parent.parent / "run_manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (manifest.get("run_status") == "SUCCESS" and
                manifest.get("release_id") == spec["release_id"] and
                manifest.get("split_registry_id") == spec["split_registry_id"] and
                manifest.get("split_version") == spec["split_version"] and
                manifest.get("phase_version") == spec["phase_version"] and
                manifest.get("label_rule_version") == spec["label_rule_version"] and
                manifest.get("feature_dictionary_version")):
            return train_path, manifest
    return None


def _resolve_parent_train(task: str, window: str, parent_pipeline: str, *,
                          spec: dict[str, str]) -> tuple[Path | None, str, dict | None]:
    """Resolve one parent-imputation train file across canonical/migration layouts."""
    canonical_root = (Path(MOUNT) / "meta_release=imputation-v1/L1_runs" / f"task={task}" /
                      f"feature_regime={REGIME[task]}" / f"window_id={window}" /
                      f"pipeline_id={parent_pipeline}" / "model_name=IMPUTATION_ONLY" /
                      "seed=20260922")
    nested = _latest_successful_canonical_train(canonical_root, spec=spec)
    if nested is not None:
        return nested[0], "CANONICAL_IMMUTABLE_RELEASE_LOCKED", nested[1]
    # Migration/flat artifacts are intentionally excluded from a new model
    # release because they do not carry sufficient split/label provenance.
    return None, "MISSING_LOCKED_RELEASE", None


@app.function(image=image, volumes={MOUNT: volume}, cpu=8, memory=196608, timeout=60 * 60 * 24)
def run_augmentation(task: str, window: str, phase: str, parent_pipeline: str = "V1",
                     method: str = "CDSMOTE", seed: int = 42, release_id: str = "") -> dict:
    """Balance the full P1-P4 TRAIN sequence used by the TEMPO baselines.

    TEMPO fits one RNN/LSTM/GRU/BiLSTM on complete training sequences and
    evaluates it on the four unmodified test-prefix views with their timestep
    masks.  Balancing each prefix independently would be a different
    experiment, so this runner intentionally materializes only the P4/full
    sequence train artifact.
    """
    import numpy as np
    import pandas as pd
    from augmentation_core import CDSmote, RadiusSMOTE, SASmote, augmentable_model_columns, materialize_synthetic_rows
    from release_core import resolve_release

    if task not in REGIME or window not in {"W1", "W2", "W3"} or phase != "P4":
        raise ValueError("TEMPO full-sequence augmentation requires task=CQ|LO, window=W1..W3, phase=P4")
    if parent_pipeline not in PARENT or method not in {"CDSMOTE", "SASMOTE", "RADIUS_SMOTE"}:
        raise ValueError("parent_pipeline=V1|V5|V9|V13; method=CDSMOTE|SASMOTE|RADIUS_SMOTE")
    spec = resolve_release(task, release_id)
    balancer = {"CDSMOTE": CDSmote(random_state=seed), "SASMOTE": SASmote(random_state=seed),
                "RADIUS_SMOTE": RadiusSMOTE(random_state=seed)}[method]
    algorithm_config = {
        "algorithm": getattr(balancer, "algorithm", method),
        "sampling_strategy_id": balancer.sampling_strategy_id,
        "ir_target": balancer.ir_target,
        "max_expansion_per_class": balancer.max_expansion_per_class,
    }
    if method == "CDSMOTE":
        algorithm_config["parameters"] = {"n_clusters": balancer.n_clusters, "kmeans_n_init": 10}
    elif method == "RADIUS_SMOTE":
        algorithm_config["parameters"] = {"radius": balancer.radius, "radius_space": "scaled_numeric_model_input"}
    elif method == "SASMOTE":
        algorithm_config["parameters"] = {
            "visible_k": balancer.visible_k,
            "max_inspectors": balancer.max_inspectors,
            "inspector_trees": balancer.inspector_trees,
            "uncertainty_threshold": balancer.uncertainty_threshold,
            "candidate_batch_size": balancer.candidate_batch_size,
            "max_candidate_rounds": balancer.max_candidate_rounds,
        }
    # Inputs may have been uploaded by another container after this worker was
    # created.  Modal volumes require an explicit reload to see those commits.
    volume.reload()
    source, source_layout, parent_manifest = _resolve_parent_train(task, window, parent_pipeline, spec=spec)
    if source is None:
        raise FileNotFoundError(f"Missing TRAIN input for {task}/{window}/{parent_pipeline}")
    print(json.dumps({"event": "run_started", "task": task, "window_id": window,
                      "parent_pipeline": parent_pipeline, "method": method,
                      "source_layout": source_layout}, sort_keys=True), flush=True)
    started_wall, started_cpu = time.perf_counter(), time.process_time()
    run_context = {"task": task, "window_id": window, "phase_id": phase,
                   "parent_pipeline": parent_pipeline, "method": method, "seed": seed,
                   "source_train": str(source), "source_layout": source_layout,
                   "parent_imputation_run_id": parent_manifest.get("run_id"),
                   "parent_imputation_attempt_id": parent_manifest.get("attempt_id"),
                   "parent_imputation_manifest_sha256": hashlib.sha256(
                       json.dumps(parent_manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
                   ).hexdigest(),
                   "release_id": spec["release_id"], "split_registry_id": spec["split_registry_id"],
                   "split_version": parent_manifest.get("split_version"),
                   "phase_version": parent_manifest.get("phase_version"),
                   "feature_dictionary_version": parent_manifest.get("feature_dictionary_version"),
                   "label_rule_version": parent_manifest.get("label_rule_version"),
                   "label_threshold_set": parent_manifest.get("label_threshold_set"),
                   "algorithm_config": algorithm_config}
    run_id = hashlib.sha256(json.dumps(run_context, sort_keys=True).encode("utf-8")).hexdigest()
    attempt_id = f"{run_id[:16]}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"

    try:
        train = pd.read_parquet(source)
    except (OSError, ValueError, EOFError) as error:
        raise RuntimeError(
            f"Cannot read parent TRAIN Parquet for {task}/{window}/{parent_pipeline}: {source}. "
            "The parent imputation artifact is corrupted or incomplete; rerun that parent imputer "
            "before augmentation."
        ) from error
    read_finished = time.perf_counter()
    required_context = {
        "context__offering_id", "context__timeline_source", "context__course_id",
        "context__duration_days", "context__long_offering_flag", "context__label_threshold_set",
        "context__temporal_strict_P1", "context__temporal_strict_P2",
        "context__temporal_strict_P3", "context__temporal_strict_P4",
    }
    missing_context = sorted(required_context.difference(train.columns))
    if missing_context:
        raise ValueError(
            f"Parent imputation TRAIN lacks required audit context: {missing_context}. "
            "Re-materialize the locked views and rerun this parent imputer."
        )
    if "enrollment_id" not in train or train["enrollment_id"].isna().any() or train["enrollment_id"].duplicated().any():
        raise ValueError("Parent imputation TRAIN violates one-row-per-real-enrollment grain.")
    print(json.dumps({"event": "input_read_complete", "rows": len(train),
                      "columns": len(train.columns)}, sort_keys=True), flush=True)
    label = _label(task)
    if "categorical_columns" not in parent_manifest:
        raise ValueError(
            "Parent imputation manifest lacks categorical_columns. Rerun the locked parent imputer; "
            "augmentation must not guess which integer columns are nominal."
        )
    categorical_columns = tuple(parent_manifest["categorical_columns"])
    numeric = augmentable_model_columns(train, label_column=label, phase_id=phase,
                                        categorical_columns=categorical_columns)
    x = train[numeric].to_numpy(dtype=np.float32, copy=True)
    y = train[label].to_numpy()
    print(json.dumps({"event": "balance_started", "rows": len(train), "features": len(numeric)}, sort_keys=True), flush=True)
    batch = balancer.fit_resample(x, y)
    balance_finished = time.perf_counter()
    algorithm_audit = getattr(balancer, "audit", {})
    algorithm_config["sampling_plan"] = getattr(balancer, "plan", {})
    print(json.dumps({"event": "balance_complete", "synthetic_rows": len(batch.labels),
                      "algorithm_audit": algorithm_audit}, sort_keys=True), flush=True)
    available = [c for c in train if c.startswith(("phase_available_", "video_observed_mask_", "problem_observed_mask_", "comment_observed_mask_"))]
    missing = [c for c in train if c.startswith("missing__")]
    context = {"task": task, "window_id": window, "phase_id": phase, "parent_pipeline": parent_pipeline,
               "balance_pipeline": _pipeline(parent_pipeline, method), "seed": str(seed),
               "seed_augmentation": seed, "seed_sampler": seed,
               "release_id": spec["release_id"], "split_registry_id": spec["split_registry_id"],
               "split_version": parent_manifest["split_version"], "phase_version": parent_manifest["phase_version"],
               "feature_dictionary_version": parent_manifest["feature_dictionary_version"],
               "label_rule_version": parent_manifest["label_rule_version"],
               "label_threshold_set": parent_manifest.get("label_threshold_set"),
               "parent_imputation_run_id": parent_manifest.get("run_id"),
               "parent_imputation_attempt_id": parent_manifest.get("attempt_id"),
               "parent_imputation_manifest_sha256": hashlib.sha256(
                   json.dumps(parent_manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
               ).hexdigest()}
    synthetic, ledger = materialize_synthetic_rows(train, batch, numeric_columns=numeric, label_column=label,
        available_mask_columns=available, missing_mask_columns=missing, context=context)
    quality_metrics = _augmentation_quality_metrics(
        train, synthetic, batch, numeric, label, available, missing, seed=seed, phase_id=phase,
    )
    # P4 denotes the complete P1-P4 sequence.  Future masking is performed
    # only on the original test-prefix views at model evaluation time.
    balanced = pd.concat([train, synthetic], ignore_index=True)
    print(json.dumps({"event": "materialize_complete", "balanced_rows": len(balanced)}, sort_keys=True), flush=True)
    pipeline = _pipeline(parent_pipeline, method)
    root = (Path(MOUNT) / "meta_release=imputation-v1/L1_runs" / f"task={task}" /
            f"feature_regime={REGIME[task]}" / f"window_id={window}" / f"phase_id={phase}" /
            f"pipeline_id={pipeline}" / "model_name=BALANCED_TRAIN_ONLY" / f"seed={seed}" /
            f"run_id={run_id}" / f"attempt_id={attempt_id}")
    root.mkdir(parents=True, exist_ok=True)
    print(json.dumps({"event": "artifact_write_started", "output": str(root)}, sort_keys=True), flush=True)
    balanced.to_parquet(root / "balanced_train.parquet", index=False)
    ledger.to_parquet(root / "synthetic_ledger.parquet", index=False)
    write_finished = time.perf_counter()
    print(json.dumps({"event": "artifact_write_complete"}, sort_keys=True), flush=True)
    before = train[label].value_counts().to_dict(); after = balanced[label].value_counts().to_dict()
    peak_ram_mb = None
    try:
        import resource  # Linux worker: ru_maxrss is KiB.
        peak_ram_mb = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) / 1024.0
    except (ImportError, AttributeError):
        pass
    wall_seconds = time.perf_counter() - started_wall
    resource_usage = {
        "run_id": run_id, "attempt_id": attempt_id, "task": task, "feature_regime": REGIME[task],
        "window_id": window, "phase_id": phase, "pipeline_id": pipeline, "stage": "S2_BALANCED",
        "time_read_s": read_finished - started_wall,
        "time_balance_s": balance_finished - read_finished,
        "time_write_s": write_finished - balance_finished,
        "time_run_total_s": wall_seconds,
        "cpu_process_s": time.process_time() - started_cpu,
        "cpu_cores_allocated": 8,
        "cpu_core_seconds_allocated": wall_seconds * 8,
        "memory_allocated_mb": 196608,
        "peak_ram_mb": peak_ram_mb,
        "gpu_used": False, "gpu_count": 0, "peak_gpu_mem_mb": 0.0,
        "energy_gpu_run_kwh": None, "energy_it_run_kwh": None, "co2e_gpu_run_g": None,
        "co2e_it_run_g": None, "cost_usd_run": None,
        "energy_measurement_type": "TELEMETRY_UNAVAILABLE_CPU_MODAL",
        "cost_measurement_type": "TELEMETRY_UNAVAILABLE_MODAL_BILLING",
        "telemetry_missing_rate": 0.0 if peak_ram_mb is not None else 1.0,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    resource_root = (Path(MOUNT) / "meta_release=imputation-v1/L2_facts/resource_usage" /
                     f"task={task}" / f"feature_regime={REGIME[task]}" / f"window_id={window}" /
                     f"phase_id={phase}" / "stage=S2_BALANCED" / f"pipeline_id={pipeline}" /
                     f"run_id={run_id}" / f"attempt_id={attempt_id}")
    resource_root.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([resource_usage]).to_parquet(resource_root / "part-00000.parquet", index=False)
    quality_root = (Path(MOUNT) / "meta_release=imputation-v1/L2_facts/augmentation_quality" /
                    f"task={task}" / f"feature_regime={REGIME[task]}" / f"window_id={window}" /
                    f"phase_id={phase}" / f"pipeline_id={pipeline}" / f"run_id={run_id}" /
                    f"attempt_id={attempt_id}")
    quality_root.mkdir(parents=True, exist_ok=True)
    quality_record = {**context, "run_id": run_id, "attempt_id": attempt_id,
                      "pipeline_id": pipeline, "rows_original": len(train),
                      "rows_synthetic": len(synthetic), "rows_balanced": len(balanced),
                      "synthetic_ratio": len(synthetic) / len(balanced),
                      "expansion_ratio": len(balanced) / len(train), **quality_metrics}
    pd.DataFrame([quality_record]).to_parquet(quality_root / "part-00000.parquet", index=False)
    manifest = {**context, "run_id": run_id, "attempt_id": attempt_id, "run_status": "SUCCESS", "source_train": str(source), "rows_original": len(train),
                "rows_synthetic": len(synthetic), "rows_balanced": len(balanced), "class_counts_before": before,
                "class_counts_after": after, "validation_test_touched": False,
                "training_sequence": "P1_P2_P3_P4_FULL", "test_prefixes_untouched": "P1_P2_P3_P4"}
    if algorithm_audit:
        manifest["algorithm_audit"] = algorithm_audit
    manifest["algorithm_config"] = algorithm_config
    manifest["resource_usage_path"] = str(resource_root / "part-00000.parquet")
    manifest["augmentation_quality_path"] = str(quality_root / "part-00000.parquet")
    manifest["augmentation_quality"] = quality_record
    manifest["resource_summary"] = resource_usage
    (root / "run_manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"event": "commit_started"}, sort_keys=True), flush=True)
    volume.commit()
    print(json.dumps({"event": "run_complete", "run_id": run_id, "rows_balanced": len(balanced)}, sort_keys=True), flush=True)
    return manifest


@app.function(image=image, volumes={MOUNT: volume}, cpu=8, memory=196608, timeout=60 * 60 * 4)
def inspect_completed_augmentation(task: str, window: str,
                                   balance_pipelines: tuple[str, ...] = ("V2", "V6", "V10", "V14"),
                                   seed: int = 42, release_id: str = "") -> list[dict]:
    """Fully scan completed Parquet artifacts without creating model output.

    Iterating every row group validates page headers and decompression, which
    catches corruption that a footer-only Parquet metadata check would miss.
    """
    import pyarrow.parquet as pq
    from release_core import resolve_release

    if task not in REGIME or window not in {"W1", "W2", "W3"}:
        raise ValueError("task=CQ|LO and window=W1..W3 required")
    spec = resolve_release(task, release_id)
    volume.reload()
    results: list[dict] = []
    for pipeline in balance_pipelines:
        base_root = (Path(MOUNT) / "meta_release=imputation-v1/L1_runs" / f"task={task}" /
                     f"feature_regime={REGIME[task]}" / f"window_id={window}" / "phase_id=P4" /
                     f"pipeline_id={pipeline}" / "model_name=BALANCED_TRAIN_ONLY" / f"seed={seed}")
        # New immutable layout; legacy flat layout remains readable for
        # inspection only and must not be used to promote a new release.
        candidates = sorted(base_root.glob("run_id=*/attempt_id=*/run_manifest.json"),
                            key=lambda path: path.stat().st_mtime, reverse=True)
        candidates.append(base_root / "run_manifest.json")
        manifest_path = next((path for path in candidates if path.exists() and
                              (data := json.loads(path.read_text(encoding="utf-8"))).get("run_status") == "SUCCESS" and
                              all(data.get(field) == spec[field] for field in
                                  ("release_id", "split_registry_id", "split_version", "phase_version", "label_rule_version"))), None)
        if manifest_path is None:
            attempts = sorted(str(path.relative_to(base_root)) for path in base_root.glob("run_id=*/attempt_id=*"))
            record = {"window_id": window, "seed": seed, "pipeline_id": pipeline,
                      "status": "INCOMPLETE_OR_FAILED_ATTEMPT" if attempts else "MISSING_SUCCESS_MANIFEST",
                      "attempt_directories": attempts}
            results.append(record)
            print(json.dumps(record, sort_keys=True), flush=True)
            continue
        root = manifest_path.parent
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        report: dict = {"window_id": window, "seed": seed, "pipeline_id": pipeline,
                        "manifest_status": manifest.get("run_status"), "files": {}}
        for name in ("balanced_train.parquet", "synthetic_ledger.parquet"):
            path = root / name
            if not path.exists() or path.stat().st_size == 0:
                report["files"][name] = {"status": "MISSING_OR_EMPTY", "bytes": path.stat().st_size if path.exists() else 0}
                continue
            parquet = pq.ParquetFile(path)
            scanned_rows = 0
            # Full scan, in bounded batches: validates all Parquet pages while
            # avoiding an in-memory 9M-row table.
            for batch in parquet.iter_batches(batch_size=131_072):
                scanned_rows += batch.num_rows
            report["files"][name] = {
                "status": "VALID_FULL_SCAN",
                "bytes": path.stat().st_size,
                "metadata_rows": parquet.metadata.num_rows,
                "scanned_rows": scanned_rows,
                "columns": parquet.metadata.num_columns,
            }
        expected_balanced = manifest.get("rows_balanced")
        scanned_balanced = report["files"].get("balanced_train.parquet", {}).get("scanned_rows")
        report["rows_balanced_match_manifest"] = scanned_balanced == expected_balanced
        quality = manifest.get("augmentation_quality", {})
        required_quality = (
            "real_vs_synth_jsd_mean", "real_vs_synth_wasserstein_norm_mean",
            "synth_out_of_domain_rate", "synth_non_integer_count_rate",
            "synth_invalid_mask_rate", "synth_cross_phase_rate",
        )
        report["quality_metrics_present"] = all(key in quality for key in required_quality)
        report["qa_synthetic_mask_ok"] = quality.get("synth_invalid_mask_rate") == 0.0
        report["qa_synthetic_phase_ok"] = quality.get("synth_cross_phase_rate") == 0.0
        report["qa_quality_ok"] = (report["quality_metrics_present"] and
                                   report["qa_synthetic_mask_ok"] and
                                   report["qa_synthetic_phase_ok"])
        results.append(report)
        print(json.dumps(report, sort_keys=True), flush=True)
    return results


@app.function(image=image, volumes={MOUNT: volume}, cpu=8, memory=196608, timeout=60 * 60 * 12)
def inspect_parent_imputations(task: str = "ALL", release_id: str = "") -> list[dict]:
    """Full page-level integrity scan of every available parent TRAIN artifact."""
    import pyarrow.parquet as pq
    from release_core import resolve_release

    tasks = tuple(REGIME) if task == "ALL" else (task,)
    if any(item not in REGIME for item in tasks):
        raise ValueError("task must be ALL, CQ, or LO")
    volume.reload()
    results: list[dict] = []
    for item in tasks:
        spec = resolve_release(item, release_id if task != "ALL" else "")
        for window in ("W1", "W2", "W3"):
            for pipeline in PARENT:
                path, layout, parent_manifest = _resolve_parent_train(item, window, pipeline, spec=spec)
                record: dict = {"task": item, "window_id": window, "pipeline_id": pipeline,
                                "parent_variant": PARENT[pipeline], "source_layout": layout}
                if path is None:
                    record["status"] = "MISSING"
                    results.append(record)
                    print(json.dumps(record, sort_keys=True), flush=True)
                    continue
                record.update({"path": str(path), "bytes": path.stat().st_size})
                try:
                    parquet = pq.ParquetFile(path)
                    scanned_rows = 0
                    for batch in parquet.iter_batches(batch_size=131_072):
                        scanned_rows += batch.num_rows
                    record.update({"status": "VALID_FULL_SCAN", "metadata_rows": parquet.metadata.num_rows,
                                   "scanned_rows": scanned_rows, "columns": parquet.metadata.num_columns})
                except Exception as error:  # Return all failures in one audit rather than aborting the scan.
                    record.update({"status": "CORRUPTED", "error_type": type(error).__name__, "error": str(error)})
                results.append(record)
                print(json.dumps(record, sort_keys=True), flush=True)
    return results


@app.function(image=image, volumes={MOUNT: volume}, timeout=60 * 10)
def inspect_augmentation_status(task: str, window: str,
                                balance_pipelines: tuple[str, ...], seed: int = 42,
                                release_id: str = "") -> list[dict]:
    """Read-only manifest status; deliberately avoids expensive Parquet scans."""
    from release_core import resolve_release
    if task not in REGIME or window not in {"W1", "W2", "W3"}:
        raise ValueError("task=CQ|LO and window=W1..W3 required")
    spec = resolve_release(task, release_id)
    volume.reload()
    records: list[dict] = []
    for pipeline in balance_pipelines:
        base = (Path(MOUNT) / "meta_release=imputation-v1/L1_runs" / f"task={task}" /
                f"feature_regime={REGIME[task]}" / f"window_id={window}" / "phase_id=P4" /
                f"pipeline_id={pipeline}" / "model_name=BALANCED_TRAIN_ONLY" / f"seed={seed}")
        manifests = [path for path in sorted(base.glob("run_id=*/attempt_id=*/run_manifest.json"),
                           key=lambda path: path.stat().st_mtime, reverse=True)
                     if all(json.loads(path.read_text(encoding="utf-8")).get(field) == spec[field] for field in
                            ("release_id", "split_registry_id", "split_version", "phase_version", "label_rule_version"))]
        attempts = sorted(str(path.relative_to(base)) for path in base.glob("run_id=*/attempt_id=*"))
        if not manifests:
            record = {"window_id": window, "pipeline_id": pipeline, "seed": seed,
                      "status": "INCOMPLETE_ATTEMPT" if attempts else "NOT_STARTED",
                      "attempt_count": len(attempts)}
        else:
            data = json.loads(manifests[0].read_text(encoding="utf-8"))
            record = {"window_id": window, "pipeline_id": pipeline, "seed": seed,
                      "status": data.get("run_status", "UNKNOWN"), "attempt_count": len(attempts),
                      "rows_balanced": data.get("rows_balanced"),
                      "attempt_id": data.get("attempt_id")}
        records.append(record)
        print(json.dumps(record, sort_keys=True), flush=True)
    return records


@app.local_entrypoint()
def cli(mode: str = "augment", task: str = "CQ", window: str = "W1", phase: str = "P4",
        parent_pipeline: str = "V1", method: str = "CDSMOTE", seed: int = 42,
        balance_pipelines: str = "V2,V6,V10,V14", release_id: str = ""):
    if mode == "inspect":
        pipelines = tuple(item.strip() for item in balance_pipelines.split(",") if item.strip())
        result = inspect_completed_augmentation.remote(task, window, pipelines, seed, release_id)
    elif mode == "inspect_all_windows":
        if task not in REGIME:
            raise ValueError("inspect_all_windows requires task=CQ or LO")
        pipelines = tuple(item.strip() for item in balance_pipelines.split(",") if item.strip())
        result = []
        for scoped_window in ("W1", "W2", "W3"):
            result.extend(inspect_completed_augmentation.remote(task, scoped_window, pipelines, seed, release_id))
    elif mode == "status":
        pipelines = tuple(item.strip() for item in balance_pipelines.split(",") if item.strip())
        result = inspect_augmentation_status.remote(task, window, pipelines, seed, release_id)
    elif mode == "status_all_windows":
        pipelines = tuple(item.strip() for item in balance_pipelines.split(",") if item.strip())
        result = []
        for scoped_window in ("W1", "W2", "W3"):
            result.extend(inspect_augmentation_status.remote(task, scoped_window, pipelines, seed, release_id))
    elif mode == "inspect_parents":
        result = inspect_parent_imputations.remote(task, release_id)
    elif mode == "augment":
        result = run_augmentation.remote(task, window, phase, parent_pipeline, method, seed, release_id)
    else:
        raise ValueError("mode must be augment, inspect, inspect_all_windows, status, status_all_windows, or inspect_parents")
    print(json.dumps(result, indent=2, default=str))
