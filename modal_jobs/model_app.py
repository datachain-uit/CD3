"""Official V1.6 shared-checkpoint recurrent-model runner.

The runner resolves an immutable, explicitly V2.2-compatible parent run.  It
never selects an arbitrary "latest" input, and only the TRAIN sequence may be
replaced by a balanced artifact.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import modal

APP_NAME, VOLUME_NAME, MOUNT = "tempo-model-v1", "tempo-data-v1", "/data"
SEED_IMPUTATION, META_RELEASE = 20260922, "imputation-v1"
REGIME = {"CQ": "CQ_RAW_EARLY", "LO": "LO_FULL_EARLY"}
CLASSES = {"CQ": ("warning", "average", "good"), "LO": ("I/D", "G", "E")}
PARENT_PIPELINE = {"V2": "V1", "V3": "V1", "V4": "V1", "V6": "V5", "V7": "V5", "V8": "V5",
                   "V10": "V9", "V11": "V9", "V12": "V9", "V14": "V13", "V15": "V13", "V16": "V13"}
ARCHITECTURES = {"RNN": "rnn", "LSTM": "lstm", "GRU": "gru", "BILSTM": "bilstm"}
# LO V3.1 is the current catalog-normalised, source-faithful label release.
# The arguments remain overridable for a later immutable LO release; no model
# run can silently fall back to a prior split.

app = modal.App(APP_NAME)
volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)
prediction_secret = modal.Secret.from_name(
    "tempo-prediction-salt", required_keys=["TEMPO_PREDICTION_SALT"]
)
image = (modal.Image.debian_slim(python_version="3.12")
         .pip_install("numpy>=1.26", "pandas>=2.2", "pyarrow>=16", "scikit-learn>=1.5", "torch>=2.4", "nvidia-ml-py>=12")
         .add_local_python_source("model")
         .add_local_python_source("release_core"))


def _canonical_json(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _role_seed(master_seed: int, role: str, *, task: str, window: str,
               pipeline_id: str, model_name: str) -> int:
    """Derive stable independent RNG streams without changing split membership."""
    payload = f"{master_seed}|{role}|{task}|{window}|{pipeline_id}|{model_name}".encode("utf-8")
    return int(hashlib.sha256(payload).hexdigest()[:8], 16) % (2**31 - 1)


def _label(task: str) -> str:
    return "CQ_label_final" if task == "CQ" else "LO_performance_label_3"


def _require_release(manifest: dict, *, source: Path, spec: dict[str, str]) -> None:
    """Reject old split/phase releases instead of silently training on them."""
    mismatch = {
        "split_version": manifest.get("split_version"),
        "phase_version": manifest.get("phase_version"),
        "feature_dictionary_version": manifest.get("feature_dictionary_version"),
        "label_rule_version": manifest.get("label_rule_version"),
    }
    if mismatch["split_version"] != spec["split_version"] or mismatch["phase_version"] != spec["phase_version"]:
        raise ValueError(
            f"Model input is not release_id={spec['release_id']} ({spec['split_version']}/{spec['phase_version']}): {source}; "
            f"split={mismatch['split_version']!r}, phase={mismatch['phase_version']!r}."
        )
    if manifest.get("release_id") != spec["release_id"] or manifest.get("split_registry_id") != spec["split_registry_id"]:
        raise ValueError(f"Model input release identity/registry mismatch at {source}")
    if not mismatch["feature_dictionary_version"] or not mismatch["label_rule_version"]:
        raise ValueError(f"Model input lacks feature/label provenance: {source}")
    if mismatch["label_rule_version"] != spec["label_rule_version"]:
        raise ValueError(f"Model input label-rule mismatch at {source}: {mismatch['label_rule_version']!r}")


def _latest_imputer_root(task: str, window: str, pipeline_id: str, *, spec: dict[str, str]) -> tuple[Path, dict]:
    root = (Path(MOUNT) / f"meta_release={META_RELEASE}" / "L1_runs" / f"task={task}" /
            f"feature_regime={REGIME[task]}" / f"window_id={window}" / f"pipeline_id={pipeline_id}" /
            "model_name=IMPUTATION_ONLY" / f"seed={SEED_IMPUTATION}")
    candidates = sorted(root.glob("run_id=*/attempt_id=*/run_manifest.json"),
                        key=lambda path: path.stat().st_mtime, reverse=True)
    for path in candidates:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if manifest.get("run_status") == "SUCCESS" and (path.parent / "model_inputs/train.parquet").exists():
            try:
                _require_release(manifest, source=path, spec=spec)
            except ValueError:
                # An old run may have been retried later than the valid run.
                # It is an ineligible candidate, not a reason to stop the scan.
                continue
            return path.parent, manifest
    raise FileNotFoundError(
        f"No successful immutable {pipeline_id} input matching release_id={spec['release_id']} under {root}"
    )


def _latest_balanced_train(task: str, window: str, pipeline_id: str, parent_manifest: dict,
                           *, spec: dict[str, str], augmentation_seed: int) -> tuple[Path, dict]:
    root = (Path(MOUNT) / f"meta_release={META_RELEASE}" / "L1_runs" / f"task={task}" /
            f"feature_regime={REGIME[task]}" / f"window_id={window}" / "phase_id=P4" /
            f"pipeline_id={pipeline_id}" / "model_name=BALANCED_TRAIN_ONLY" / f"seed={augmentation_seed}")
    paths = sorted(root.glob("run_id=*/attempt_id=*/run_manifest.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in paths:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        train = path.parent / "balanced_train.parquet"
        if manifest.get("run_status") != "SUCCESS" or not train.exists():
            continue
        if manifest.get("parent_pipeline") != PARENT_PIPELINE[pipeline_id]:
            continue
        if int(manifest.get("seed", -1)) != augmentation_seed:
            continue
        if manifest.get("validation_test_touched") is not False:
            raise ValueError(f"Balanced run illegally touched validation/test: {path}")
        for field in ("release_id", "split_registry_id", "split_version", "phase_version", "label_rule_version"):
            expected = spec[field]
            if manifest.get(field) != expected:
                raise ValueError(
                    f"Balanced TRAIN release mismatch at {path}: {field}="
                    f"{manifest.get(field)!r}, expected {expected!r}"
                )
        if manifest.get("parent_imputation_run_id") != parent_manifest.get("run_id"):
            raise ValueError(f"Balanced TRAIN has a different parent imputation run: {path}")
        if manifest.get("parent_imputation_attempt_id") != parent_manifest.get("attempt_id"):
            raise ValueError(f"Balanced TRAIN has a different parent imputation attempt: {path}")
        expected_parent_hash = hashlib.sha256(
            json.dumps(parent_manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        if manifest.get("parent_imputation_manifest_sha256") != expected_parent_hash:
            raise ValueError(f"Balanced TRAIN parent-manifest hash mismatch: {path}")
        return train, manifest
    raise FileNotFoundError(
        f"No successful seed={augmentation_seed} balanced TRAIN for {task}/{window}/{pipeline_id} under {root}"
    )


def _resolve_model_inputs(task: str, window: str, pipeline_id: str, *, spec: dict[str, str],
                          augmentation_seed: int) -> tuple[Path, Path, dict, dict | None]:
    """Return train, immutable parent root, parent manifest, augmentation manifest."""
    parent = PARENT_PIPELINE.get(pipeline_id, pipeline_id)
    parent_root, parent_manifest = _latest_imputer_root(task, window, parent, spec=spec)
    if pipeline_id == parent:
        return parent_root / "model_inputs/train.parquet", parent_root, parent_manifest, None
    train, augmentation_manifest = _latest_balanced_train(
        task, window, pipeline_id, parent_manifest, spec=spec, augmentation_seed=augmentation_seed
    )
    return train, parent_root, parent_manifest, augmentation_manifest


def _write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, default=str), encoding="utf-8")
    temporary.replace(path)


def _prediction_frame(prediction: dict, source, *, task: str, window: str, phase: str,
                      run_id: str, attempt_id: str, split: str, salt: str,
                      pipeline_id: str, model_name: str, seed_index: int):
    import pandas as pd
    ids = source["enrollment_id"].astype("string") if "enrollment_id" in source else pd.Series(range(len(source)), dtype="string")
    anonymous = ids.map(lambda v: hashlib.sha256(f"{salt}|{v}".encode()).hexdigest())
    frame = pd.DataFrame({"enrollment_id_hash": anonymous, "task": task,
                          "feature_regime": REGIME[task], "window_id": window, "seed_index": seed_index,
                          "model_family": "F1_RECURRENT", "model_name": model_name,
                          "model_revision": "recurrent_shared_phase_v2_4_prefixsafe_epoch50", "pipeline_id": pipeline_id,
                          "phase_id": phase, "cohort_type": "FIXED", "eval_split": split,
                          "run_id": run_id, "attempt_id": attempt_id,
                          "y_true": [f"c{x}" for x in prediction["y_true"]],
                          "y_pred": [f"c{x}" for x in prediction["y_pred"]],
                          "observed_length": int(phase[1:]), "sample_type": "real",
                          "inference_latency_ms": None})
    # Keep the non-personal cohort keys needed for offering/timeline audits.
    # Raw enrollment IDs never leave the source frame.
    for column in ("offering_id", "timeline_source", "course_id"):
        context_column = f"context__{column}"
        if context_column in source:
            frame[column] = source[context_column].astype("string").to_numpy()
            continue
        if column in source:
            frame[column] = source[column].astype("string").to_numpy()
    for column in ("context__duration_days", "context__long_offering_flag",
                   "context__label_threshold_set", "context__temporal_strict_P1",
                   "context__temporal_strict_P2", "context__temporal_strict_P3",
                   "context__temporal_strict_P4"):
        if column in source:
            frame[column.removeprefix("context__")] = source[column].to_numpy()
    for index in range(prediction["probabilities"].shape[1]):
        frame[f"prob_c{index}"] = prediction["probabilities"][:, index]
    return frame


PREDICTION_CONTEXT = {
    "context__offering_id", "context__timeline_source", "context__course_id", "context__duration_days",
    "context__long_offering_flag", "context__label_threshold_set",
    "context__temporal_strict_P1", "context__temporal_strict_P2",
    "context__temporal_strict_P3", "context__temporal_strict_P4",
}


def _require_prediction_context(frame, *, source: str) -> None:
    """Reject model inputs that cannot support the registered audit slices."""
    missing = sorted(PREDICTION_CONTEXT.difference(frame.columns))
    if missing:
        raise ValueError(
            f"Model input lacks required non-predictive audit context at {source}: {missing}. "
            "Re-materialize views and rerun the parent imputation."
        )


@app.function(image=image, volumes={MOUNT: volume}, secrets=[prediction_secret], gpu="L4", cpu=8, memory=65536,
              timeout=60 * 60 * 18)
def train_recurrent(task: str = "CQ", window: str = "W1", pipeline_id: str = "V0",
                    model_name: str = "RNN", seed: int = 42, split_version: str = "",
                    phase_version: str = "", augmentation_seed: int = 42,
                    release_id: str = "") -> dict:
    """Train one V1.6 recurrent checkpoint and test it at P1, P2, P3 and P4.

    No training, scaler fitting, selection, or preprocessing is done on any
    test prefix. ``phase_id=P4`` is intentionally not a separate model: it is
    the full temporal training sequence for the shared-checkpoint protocol.
    """
    import resource
    import numpy as np
    import pandas as pd
    import torch
    from model.data import fit_layout
    from model.energy import GpuEnergyMeter
    from model.metrics import per_class_metric_records, stratified_bootstrap_per_class_ci
    from model.shared_phase import evaluate_test_prefix, train_shared_checkpoint
    from release_core import resolve_release

    if task not in REGIME or window not in {"W1", "W2", "W3"} or pipeline_id not in {f"V{i}" for i in range(17)}:
        raise ValueError("task=CQ|LO, window=W1..W3, pipeline_id=V0..V16 required")
    if model_name not in ARCHITECTURES:
        raise ValueError(f"model_name must be one of {sorted(ARCHITECTURES)}")
    spec = resolve_release(task, release_id)
    if split_version and split_version != spec["split_version"]:
        raise ValueError(f"split_version is controlled by {spec['release_id']}; expected {spec['split_version']!r}")
    if phase_version and phase_version != spec["phase_version"]:
        raise ValueError(f"phase_version is controlled by {spec['release_id']}; expected {spec['phase_version']!r}")
    volume.reload()
    started = time.perf_counter(); cpu_started = time.process_time()
    if augmentation_seed < 0:
        raise ValueError("augmentation_seed must be non-negative")
    prediction_salt = os.environ.get("TEMPO_PREDICTION_SALT")
    if not prediction_salt:
        raise RuntimeError("TEMPO_PREDICTION_SALT must be supplied by the tempo-prediction-salt Modal secret")
    train_path, input_root, input_manifest, augmentation_manifest = _resolve_model_inputs(
        task, window, pipeline_id, spec=spec, augmentation_seed=augmentation_seed)
    seed_model = _role_seed(seed, "model", task=task, window=window, pipeline_id=pipeline_id, model_name=model_name)
    seed_dataloader = _role_seed(seed, "dataloader", task=task, window=window, pipeline_id=pipeline_id, model_name=model_name)
    seed_bundle = {"master_seed": seed, "seed_model": seed_model,
                   "seed_sampler": augmentation_seed if augmentation_manifest is not None else None,
                   "seed_augmentation": augmentation_seed if augmentation_manifest is not None else None,
                   "seed_dataloader": seed_dataloader, "seed_preprocess": SEED_IMPUTATION}
    config = {"config_version": "recurrent_shared_phase_v2_4_prefixsafe_epoch50", "task": task, "feature_regime": REGIME[task],
              "window_id": window, "pipeline_id": pipeline_id,
              "pipeline_name": "RAW_CONSTANT_FILL_WITH_MASKS" if pipeline_id == "V0" else "IMPUTE_AND_BALANCE",
              "model_name": model_name, "model_revision": "recurrent_shared_phase_v2_4_prefixsafe_epoch50", "seed": seed,
              "augmentation_seed": augmentation_seed,
              "prediction_id_salt_sha256": hashlib.sha256(prediction_salt.encode("utf-8")).hexdigest(),
              **seed_bundle,
              "gpu_type": "L4", "precision_policy": "bf16_amp", "logits_loss_dtype": "float32",
              "training_sequence": "P1_P2_P3_P4", "checkpoint_count": 1,
              "validation_selection": "mean_macro_f1(P1,P2,P3,P4); tie=min_mean_cross_entropy",
              "small_support_contract": {"threshold": 400, "bootstrap_ci": "stratified_95pct",
                                         "bootstrap_repetitions": 2000,
                                         "applies_to": "LO_W2_W3_per_class"},
              "paired_bootstrap_contract": {"repetitions": 2000, "unit": "paired_prediction_rows",
                                             "applies_to": "LO_W2_W3_pipeline_comparison"},
              "long_offering_policy": "retain_flagged_no_pseudo_run_v1",
              "test_refit_forbidden": True, "hidden_size": 128, "num_layers": 1, "dropout": .3,
              "batch_size": 2048, "max_epochs": 50, "patience": 5, "learning_rate": .001,
              "weight_decay": .00001, "data_release_id": input_manifest.get("data_release_id"),
              "release_id": spec["release_id"], "split_registry_id": spec["split_registry_id"],
              "split_version": input_manifest.get("split_version"), "phase_version": input_manifest.get("phase_version"),
              "expected_split_version": spec["split_version"], "expected_phase_version": spec["phase_version"],
              "feature_dictionary_version": input_manifest.get("feature_dictionary_version"),
              "label_rule_version": input_manifest.get("label_rule_version"),
              "label_threshold_set": input_manifest.get("label_threshold_set", "PRIMARY"),
              "input_channels": ["X", "M_missing", "M_available", "delta_t", "phase_id", "observed_length"],
              "parent_imputation_run_id": input_manifest.get("run_id"),
              "parent_augmentation_run_id": None if augmentation_manifest is None else augmentation_manifest.get("run_id")}
    run_id = hashlib.sha256(_canonical_json(config).encode()).hexdigest()
    run_base = (Path(MOUNT) / f"meta_release={META_RELEASE}" / "L1_runs" / f"task={task}" /
            f"feature_regime={REGIME[task]}" / f"window_id={window}" / f"pipeline_id={pipeline_id}" /
            f"model_name={model_name}" / f"seed={seed}" / f"run_id={run_id}")
    # Same logical config => same run_id. Retries are separate, monotonically
    # numbered attempts and never overwrite a prior attempt's provenance.
    prior_attempts = sorted(run_base.glob("attempt_id=*")) if run_base.exists() else []
    attempt_id = f"{run_id}-{len(prior_attempts) + 1:04d}"
    root = run_base / f"attempt_id={attempt_id}"
    root.mkdir(parents=True, exist_ok=True)
    print(json.dumps({"event": "run_started", "run_id": run_id, "attempt_id": attempt_id,
                      "task": task, "window_id": window, "pipeline_id": pipeline_id, "model_name": model_name}), flush=True)
    train = pd.read_parquet(train_path)
    validation = pd.read_parquet(input_root / "model_inputs/validation.parquet")
    tests = {phase: pd.read_parquet(input_root / f"model_inputs/test_{phase}.parquet") for phase in ("P1", "P2", "P3", "P4")}
    for source_name, frame in (("train", train), ("validation", validation), *tests.items()):
        _require_prediction_context(frame, source=source_name)
    read_s = time.perf_counter() - started
    layout = fit_layout(train, task=task, phase_id="P4", use_masks=True)
    label = _label(task); classes = CLASSES[task]
    unseen = set(train[label].astype(str).unique()) - set(classes)
    if unseen: raise ValueError(f"unexpected {task} class labels: {sorted(unseen)}")
    # Keep the meter open through both checkpoint selection and all frozen
    # prefix inference; resource cost is a run-level quantity.
    energy_meter = GpuEnergyMeter(); energy_meter.__enter__()
    trained, runtime = train_shared_checkpoint(layout=layout, classes=classes, train_frame=train,
        validation_frame=validation, architecture=ARCHITECTURES[model_name], seed=seed_model,
        dataloader_seed=seed_dataloader, hidden_size=128, num_layers=1,
        dropout=.3, batch_size=2048, max_epochs=50, patience=5, learning_rate=.001,
        weight_decay=.00001, workers=4)
    train_s = time.perf_counter() - started - read_s
    checkpoint_root = root / "checkpoint"; checkpoint_root.mkdir(parents=True, exist_ok=True)
    torch.save(trained["checkpoint"], checkpoint_root / "model.pt")
    pd.DataFrame(trained["history"]).to_parquet(root / "train_history.parquet", index=False)
    _write_json(root / "feature_layout.json", layout.as_dict())
    result_metrics = []
    confusion_records = []
    calibration_records = []
    per_class_records = []
    bootstrap_records = []
    salt = prediction_salt
    # Validation predictions are preserved for selection audit; test remains
    # purely post-selection and is written once for every prefix.
    for phase, prediction in trained["validation_predictions"].items():
        path = root / "predictions" / "eval_split=VALIDATION" / f"phase_id={phase}"; path.mkdir(parents=True, exist_ok=True)
        prediction_frame = _prediction_frame(prediction, validation, task=task, window=window, phase=phase, run_id=run_id,
                                             attempt_id=attempt_id, split="VALIDATION", salt=salt,
                                             pipeline_id=pipeline_id, model_name=model_name, seed_index=seed)
        prediction_frame.to_parquet(path / "part-00000.parquet", index=False)
        probability_root = root / "probability_matrices" / "eval_split=VALIDATION" / f"phase_id={phase}"
        probability_root.mkdir(parents=True, exist_ok=True)
        prediction_frame.loc[:, ["enrollment_id_hash", "prob_c0", "prob_c1", "prob_c2"]].to_parquet(probability_root / "part-00000.parquet", index=False)
        confusion_root = root / "confusion_matrices" / "eval_split=VALIDATION" / f"phase_id={phase}"
        confusion_root.mkdir(parents=True, exist_ok=True)
        confusion = pd.DataFrame(prediction["confusion"], index=["c0", "c1", "c2"], columns=["c0", "c1", "c2"])
        confusion.index.name = "y_true"; confusion.reset_index().to_parquet(confusion_root / "part-00000.parquet", index=False)
        metric = {"task": task, "feature_regime": REGIME[task], "window_id": window, "phase_id": phase,
                  "eval_split": "VALIDATION", "pipeline_id": pipeline_id, "model_name": model_name, "run_id": run_id,
                  "attempt_id": attempt_id, **trained["validation_metrics"][phase]}
        result_metrics.append(metric)
        for record in per_class_metric_records(prediction["y_true"], prediction["y_pred"], np.arange(len(classes)), classes,
                                               probabilities=prediction["probabilities"]):
            per_class_records.append({"task": task, "feature_regime": REGIME[task], "window_id": window, "phase_id": phase,
                                      "eval_split": "VALIDATION", "pipeline_id": pipeline_id, "model_name": model_name, "run_id": run_id,
                                      "attempt_id": attempt_id, **record})
        if task == "LO" and window in {"W2", "W3"}:
            for record in stratified_bootstrap_per_class_ci(prediction["y_true"], prediction["y_pred"], np.arange(len(classes)), classes,
                                                             repetitions=2000, seed=seed):
                bootstrap_records.append({"task": task, "feature_regime": REGIME[task], "window_id": window, "phase_id": phase,
                                          "eval_split": "VALIDATION", "pipeline_id": pipeline_id, "model_name": model_name, "run_id": run_id,
                                          "attempt_id": attempt_id, **record})
        calibration_records.append({key: metric[key] for key in ("task", "feature_regime", "window_id", "phase_id", "eval_split", "pipeline_id", "model_name", "run_id", "attempt_id", "multiclass_nll", "multiclass_brier", "top_label_ece_15", "calibration_bins")})
        for true_index, true_code in enumerate(("c0", "c1", "c2")):
            for pred_index, pred_code in enumerate(("c0", "c1", "c2")):
                confusion_records.append({"task": task, "feature_regime": REGIME[task], "window_id": window, "phase_id": phase,
                                          "eval_split": "VALIDATION", "pipeline_id": pipeline_id, "model_name": model_name, "run_id": run_id,
                                          "attempt_id": attempt_id, "y_true": true_code, "y_pred": pred_code,
                                          "count": int(prediction["confusion"][true_index, pred_index])})
    inference_started = time.perf_counter()
    for phase, frame in tests.items():
        metrics, prediction = evaluate_test_prefix(runtime["model"], frame, layout, classes, phase, 2048, 4, runtime["device"])
        path = root / "predictions" / "eval_split=TEST" / f"phase_id={phase}"; path.mkdir(parents=True, exist_ok=True)
        prediction_frame = _prediction_frame(prediction, frame, task=task, window=window, phase=phase, run_id=run_id,
                                             attempt_id=attempt_id, split="TEST", salt=salt,
                                             pipeline_id=pipeline_id, model_name=model_name, seed_index=seed)
        prediction_frame.to_parquet(path / "part-00000.parquet", index=False)
        probability_root = root / "probability_matrices" / "eval_split=TEST" / f"phase_id={phase}"
        probability_root.mkdir(parents=True, exist_ok=True)
        prediction_frame.loc[:, ["enrollment_id_hash", "prob_c0", "prob_c1", "prob_c2"]].to_parquet(probability_root / "part-00000.parquet", index=False)
        confusion_root = root / "confusion_matrices" / "eval_split=TEST" / f"phase_id={phase}"
        confusion_root.mkdir(parents=True, exist_ok=True)
        confusion = pd.DataFrame(prediction["confusion"], index=["c0", "c1", "c2"], columns=["c0", "c1", "c2"])
        confusion.index.name = "y_true"; confusion.reset_index().to_parquet(confusion_root / "part-00000.parquet", index=False)
        result_metrics.append({"task": task, "feature_regime": REGIME[task], "window_id": window, "phase_id": phase,
                               "eval_split": "TEST", "pipeline_id": pipeline_id, "model_name": model_name, "run_id": run_id,
                               "attempt_id": attempt_id, **metrics})
        metric = result_metrics[-1]
        for record in per_class_metric_records(prediction["y_true"], prediction["y_pred"], np.arange(len(classes)), classes,
                                               probabilities=prediction["probabilities"]):
            per_class_records.append({"task": task, "feature_regime": REGIME[task], "window_id": window, "phase_id": phase,
                                      "eval_split": "TEST", "pipeline_id": pipeline_id, "model_name": model_name, "run_id": run_id,
                                      "attempt_id": attempt_id, **record})
        if task == "LO" and window in {"W2", "W3"}:
            for record in stratified_bootstrap_per_class_ci(prediction["y_true"], prediction["y_pred"], np.arange(len(classes)), classes,
                                                             repetitions=2000, seed=seed):
                bootstrap_records.append({"task": task, "feature_regime": REGIME[task], "window_id": window, "phase_id": phase,
                                          "eval_split": "TEST", "pipeline_id": pipeline_id, "model_name": model_name, "run_id": run_id,
                                          "attempt_id": attempt_id, **record})
        calibration_records.append({key: metric[key] for key in ("task", "feature_regime", "window_id", "phase_id", "eval_split", "pipeline_id", "model_name", "run_id", "attempt_id", "multiclass_nll", "multiclass_brier", "top_label_ece_15", "calibration_bins")})
        for true_index, true_code in enumerate(("c0", "c1", "c2")):
            for pred_index, pred_code in enumerate(("c0", "c1", "c2")):
                confusion_records.append({"task": task, "feature_regime": REGIME[task], "window_id": window, "phase_id": phase,
                                          "eval_split": "TEST", "pipeline_id": pipeline_id, "model_name": model_name, "run_id": run_id,
                                          "attempt_id": attempt_id, "y_true": true_code, "y_pred": pred_code,
                                          "count": int(prediction["confusion"][true_index, pred_index])})
    inference_s = time.perf_counter() - inference_started
    metric_paths = []
    for phase in ("P1", "P2", "P3", "P4"):
        metrics_root = (Path(MOUNT) / f"meta_release={META_RELEASE}" / "L2_facts" / "metrics_overall" / f"task={task}" /
                        f"feature_regime={REGIME[task]}" / f"window_id={window}" / f"phase_id={phase}" /
                        "stage=S3_MODEL" / f"pipeline_id={pipeline_id}" / f"model_name={model_name}" /
                        f"run_id={run_id}" / f"attempt_id={attempt_id}")
        metrics_root.mkdir(parents=True, exist_ok=True)
        pd.DataFrame([record for record in result_metrics if record["phase_id"] == phase]).to_parquet(metrics_root / "part-00000.parquet", index=False)
        metric_paths.append(str(metrics_root / "part-00000.parquet"))
    fact_base = Path(MOUNT) / f"meta_release={META_RELEASE}" / "L2_facts"
    for fact_name, records in (("confusion_matrix", confusion_records), ("calibration", calibration_records),
                               ("metrics_per_class", per_class_records), ("bootstrap_metrics_per_class", bootstrap_records)):
        if not records:
            continue
        for phase in ("P1", "P2", "P3", "P4"):
            phase_records = [record for record in records if record["phase_id"] == phase]
            if not phase_records:
                continue
            fact_root = (fact_base / fact_name / f"task={task}" / f"feature_regime={REGIME[task]}" /
                         f"window_id={window}" / f"phase_id={phase}" / "stage=S3_MODEL" /
                         f"pipeline_id={pipeline_id}" / f"model_name={model_name}" / f"run_id={run_id}" / f"attempt_id={attempt_id}")
            fact_root.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(phase_records).to_parquet(fact_root / "part-00000.parquet", index=False)
    selection_scores = sorted((float(row["validation_macro_f1_mean_p1_p4"]), int(row["epoch"])) for row in trained["history"])
    best_score = selection_scores[-1][0]
    second_best_score = selection_scores[-2][0] if len(selection_scores) > 1 else None
    selection_margin = best_score - second_best_score if second_best_score is not None else None
    selection_record = {"task": task, "feature_regime": REGIME[task], "window_id": window,
                        "phase_id": "P1_P2_P3_P4", "stage": "S3_MODEL", "pipeline_id": pipeline_id,
                        "model_name": model_name, "run_id": run_id, "attempt_id": attempt_id,
                        "selection_metric": "mean_validation_macro_f1_p1_p4", "best_epoch": trained["best_epoch"],
                        "best_score": best_score, "second_best_score": second_best_score,
                        "selection_margin": selection_margin, "tie_breaker": "min_mean_cross_entropy"}
    selection_root = (fact_base / "checkpoint_selection" / f"task={task}" / f"feature_regime={REGIME[task]}" /
                      f"window_id={window}" / "phase_id=P1_P2_P3_P4" / "stage=S3_MODEL" /
                      f"pipeline_id={pipeline_id}" / f"model_name={model_name}" / f"run_id={run_id}" / f"attempt_id={attempt_id}")
    selection_root.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([selection_record]).to_parquet(selection_root / "part-00000.parquet", index=False)
    total_s = time.perf_counter() - started
    energy_meter.__exit__(None, None, None)
    energy = energy_meter.result()
    cpu_process_s = time.process_time() - cpu_started
    # Linux ru_maxrss is KiB.  This is process peak RSS (the relevant host-RAM
    # signal for sizing the next Modal request), not merely PyTorch tensors.
    peak_ram_mb = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0)
    resource = {"task": task, "feature_regime": REGIME[task], "window_id": window, "phase_id": "P1_P2_P3_P4",
                "stage": "S3_MODEL", "pipeline_id": pipeline_id, "model_name": model_name, "run_id": run_id, "attempt_id": attempt_id,
                "time_read_s": read_s, "time_train_selection_s": train_s, "time_test_inference_s": inference_s,
                "time_run_total_s": total_s, "cpu_process_s": cpu_process_s,
                "cpu_cores_allocated": 8, "cpu_cores_mean_used": float(cpu_process_s / max(total_s, 1e-9)),
                "memory_allocated_mb": 65536, "peak_ram_mb": peak_ram_mb, "gpu_used": True,
                "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
                "peak_gpu_memory_mb": float(torch.cuda.max_memory_allocated() / 1024**2) if torch.cuda.is_available() else 0.0,
                "cost_usd_run": None, "cost_measurement_type": "TELEMETRY_UNAVAILABLE_MODAL_BILLING",
                "energy_it_run_kwh": None, "co2e_gpu_run_g": None, "co2e_it_run_g": None,
                **energy}
    resource_root = (Path(MOUNT) / f"meta_release={META_RELEASE}" / "L2_facts" / "resource_usage" / f"task={task}" /
                     f"feature_regime={REGIME[task]}" / f"window_id={window}" / "stage=S3_MODEL" /
                     f"pipeline_id={pipeline_id}" / f"model_name={model_name}" / f"run_id={run_id}" / f"attempt_id={attempt_id}")
    resource_root.mkdir(parents=True, exist_ok=True); pd.DataFrame([resource]).to_parquet(resource_root / "part-00000.parquet", index=False)
    pd.DataFrame([{"run_id": run_id, "attempt_id": attempt_id, "task": task, "window_id": window,
                   "pipeline_id": pipeline_id, "model_name": model_name, "time_read_s": read_s,
                   "time_train_selection_s": train_s, "time_test_inference_s": inference_s,
                   "time_run_total_s": total_s}]).to_parquet(root / "timing.parquet", index=False)
    manifest = {**config, "run_id": run_id, "attempt_id": attempt_id, "run_status": "SUCCESS",
                "input_root": str(input_root), "classes": list(classes), "class_code_order": ["c0", "c1", "c2"],
                "train_input_path": str(train_path),
                "best_epoch": trained["best_epoch"], "train_rows": trained["train_rows"], "validation_rows": trained["validation_rows"],
                "test_rows": {p: len(f) for p, f in tests.items()}, "feature_layout": layout.as_dict(),
                "cost_shared_across_phases": True,
                "metrics_paths": metric_paths, "resource_path": str(resource_root / "part-00000.parquet"),
                "selection_audit_path": str(selection_root / "part-00000.parquet"),
                "small_support_fact_written": bool(per_class_records),
                "bootstrap_small_support_fact_written": bool(bootstrap_records)}
    _write_json(root / "run_manifest.json", manifest)
    registry = Path(MOUNT) / f"meta_release={META_RELEASE}" / "L0_registry" / "run_registry"; registry.mkdir(parents=True, exist_ok=True)
    _write_json(registry / f"run_id={run_id}.json", manifest)
    model_registry = Path(MOUNT) / f"meta_release={META_RELEASE}" / "L0_registry" / "model_registry" / f"model_name={model_name}"
    model_registry.mkdir(parents=True, exist_ok=True)
    _write_json(model_registry / "model_revision=recurrent_shared_phase_v2_4_prefixsafe_epoch50.json", {
        "model_family": "F1_RECURRENT", "model_name": model_name, "model_revision": "recurrent_shared_phase_v2_4_prefixsafe_epoch50",
        "pipeline_id": pipeline_id, "input_mode": "v0_mask" if pipeline_id == "V0" else "imputed_or_balanced",
        "temporal_contract": config["training_sequence"],
        "selection_objective": config["validation_selection"], "config": config,
    })
    environments = Path(MOUNT) / f"meta_release={META_RELEASE}" / "L0_registry" / "environments"; environments.mkdir(parents=True, exist_ok=True)
    _write_json(environments / f"attempt_id={attempt_id}.json", {
        "attempt_id": attempt_id, "python": os.sys.version, "torch": torch.__version__,
        "cuda_available": bool(torch.cuda.is_available()), "gpu_name": resource["gpu_name"],
    })
    (root / "SUCCESS").touch()
    volume.commit()
    print(json.dumps({"event": "run_finished", "run_id": run_id, "best_epoch": trained["best_epoch"], "seconds": total_s}), flush=True)
    return manifest


@app.local_entrypoint()
def cli(task: str = "CQ", window: str = "W1", pipeline_id: str = "V0",
        model_name: str = "RNN", seed: int = 42, split_version: str = "", phase_version: str = "",
        augmentation_seed: int = 42, release_id: str = "") -> None:
    print(json.dumps(train_recurrent.remote(
        task, window, pipeline_id, model_name, seed, split_version, phase_version, augmentation_seed, release_id
    ), indent=2, default=str))
