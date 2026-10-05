"""Post-hoc MDS sanity facts for a frozen recurrent-model run; no retraining."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import modal

APP_NAME, VOLUME_NAME, MOUNT = "tempo-model-sanity-v1", "tempo-data-v1", "/data"
META_RELEASE = "imputation-v1"
REGIME = {"CQ": "CQ_RAW_EARLY", "LO": "LO_FULL_EARLY"}
CLASSES = {"CQ": ("warning", "average", "good"), "LO": ("I/D", "G", "E")}

app = modal.App(APP_NAME)
volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=False)
image = (modal.Image.debian_slim(python_version="3.12")
         .pip_install("numpy>=1.26", "pandas>=2.2", "pyarrow>=16", "scikit-learn>=1.5")
         .add_local_python_source("metrics_core")
         .add_local_python_source("release_core"))


def _latest_attempt(root: Path, *, spec: dict[str, str]) -> tuple[Path, dict]:
    pattern = "attempt_id=*/run_manifest.json" if root.name.startswith("run_id=") else "run_id=*/attempt_id=*/run_manifest.json"
    paths = sorted(root.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in paths:
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("run_status") == "SUCCESS":
            if any(value.get(field) != spec[field] for field in
                   ("release_id", "split_registry_id", "split_version", "phase_version", "label_rule_version", "label_threshold_set")):
                continue
            return path.parent, value
    raise FileNotFoundError(f"No successful run under {root}")


def _label(task: str) -> str: return "CQ_label_final" if task == "CQ" else "LO_performance_label_3"


def _class_ids(values, task: str):
    mapping = {name: index for index, name in enumerate(CLASSES[task])}
    return values.astype("string").map(mapping).to_numpy(dtype="int64")


def _phase_mask_matrix(frame, phase: str, dynamic_bases: list[str]):
    """Only mask/availability signals the model receives, with no values."""
    import numpy as np
    import pandas as pd
    columns = [f"missing__{base}_{phase}" for base in dynamic_bases if f"missing__{base}_{phase}" in frame]
    columns += [c for c in frame if c.startswith("missing__") and "_P" not in c]
    columns += [c for c in (f"phase_available_{phase}", f"video_observed_mask_{phase}",
                             f"problem_observed_mask_{phase}", f"comment_observed_mask_{phase}") if c in frame]
    values = frame.loc[:, columns].apply(pd.to_numeric, errors="coerce").fillna(0).to_numpy(dtype="float32")
    # Required by the MDS probe contract; it is derived exclusively from
    # availability indicators, never from feature values.
    modality = [c for c in (f"video_observed_mask_{phase}", f"problem_observed_mask_{phase}", f"comment_observed_mask_{phase}") if c in frame]
    zero_event = (frame.loc[:, modality].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1).eq(0).to_numpy(dtype="float32")
                  if modality else np.zeros(len(frame), dtype="float32"))
    return np.column_stack((values, zero_event)), columns + ["zero_event_flag"]


def _effective_information_rate(frame, phase: str, dynamic_bases: list[str]) -> tuple[float, float, float]:
    import numpy as np
    missing = [f"missing__{base}_{phase}" for base in dynamic_bases if f"missing__{base}_{phase}" in frame]
    missing += [c for c in frame if c.startswith("missing__") and "_P" not in c]
    observed = 1.0 - frame.loc[:, missing].apply(lambda x: x.astype(float)).to_numpy().mean() if missing else 1.0
    available = [c for c in (f"phase_available_{phase}", f"video_observed_mask_{phase}",
                              f"problem_observed_mask_{phase}", f"comment_observed_mask_{phase}") if c in frame]
    availability = frame.loc[:, available].apply(lambda x: x.astype(float)).to_numpy().mean() if available else 1.0
    # The input-mask vector comprises observed/not-missing and availability
    # channels; s_eff is its mean as specified in the MDS document.
    return float((observed * len(missing) + availability * len(available)) / max(len(missing) + len(available), 1)), float(observed), float(availability)


def _train_tensor_s_eff(train, dynamic_bases: list[str]) -> tuple[float, float, float]:
    """Locked run-level S_eff: mean mask channels over actual TRAIN P1--P4."""
    import numpy as np
    rows = [_effective_information_rate(train, phase, dynamic_bases) for phase in ("P1", "P2", "P3", "P4")]
    return tuple(float(np.mean([row[i] for row in rows])) for i in range(3))


@app.function(image=image, volumes={MOUNT: volume}, cpu=8, memory=65536, timeout=60 * 60 * 6)
def materialize_model_sanity(task: str = "CQ", window: str = "W1", pipeline_id: str = "V0",
                              model_name: str = "RNN", seed: int = 42, run_id: str = "",
                              probe_rows_per_phase: int = 0, split_version: str = "",
                              phase_version: str = "", release_id: str = "") -> dict:
    """Materialize S_san+ components from stored artifacts; checkpoint untouched."""
    import numpy as np
    import pandas as pd
    from metrics_core.evaluation import (COMPOSITE_EPS, classification_metrics, fit_missingness_probe,
                                         score_missingness_probe_auc, s_leak_from_probe)
    from release_core import resolve_release

    if task not in REGIME or window not in {"W1", "W2", "W3"}: raise ValueError("task=CQ|LO, window=W1..W3")
    spec = resolve_release(task, release_id)
    if split_version and split_version != spec["split_version"]:
        raise ValueError(f"split_version is controlled by {spec['release_id']}")
    if phase_version and phase_version != spec["phase_version"]:
        raise ValueError(f"phase_version is controlled by {spec['release_id']}")
    volume.reload()
    model_base = (Path(MOUNT) / f"meta_release={META_RELEASE}" / "L1_runs" / f"task={task}" /
                  f"feature_regime={REGIME[task]}" / f"window_id={window}" / f"pipeline_id={pipeline_id}" /
                  f"model_name={model_name}" / f"seed={seed}")
    if run_id:
        model_base = model_base / f"run_id={run_id}"
    model_root, manifest = _latest_attempt(model_base, spec=spec)
    input_root = Path(manifest["input_root"])
    layout = json.loads((model_root / "feature_layout.json").read_text(encoding="utf-8"))
    bases = layout["dynamic_bases"]
    # S_eff and S_leak describe the natural TRAIN cohort, never synthetic
    # rows added solely for optimisation.  ``train_input_path`` may refer to a
    # balanced TRAIN artifact for V2--V16, so deliberately use its immutable
    # parent imputation input here.
    natural_train_path = input_root / "model_inputs/train.parquet"
    if not natural_train_path.exists():
        raise FileNotFoundError(f"Missing immutable parent TRAIN for sanity: {natural_train_path}")
    train = pd.read_parquet(natural_train_path)
    train_y = _class_ids(train[_label(task)], task)
    # S_eff is deliberately computed once from the immutable natural TRAIN
    # cohort, not recomputed from an evaluation prefix or synthetic rows.
    train_s_eff, train_observed_rate, train_availability_rate = _train_tensor_s_eff(train, bases)
    # The protocol specifies one standardized multinomial probe fit on the
    # pooled TRAIN P1--P4 mask tensor.  Fit it once and reuse it for every
    # validation/test prefix; refitting by slice is redundant and much slower.
    pooled_x, pooled_y, probe_columns = [], [], None
    for train_phase in ("P1", "P2", "P3", "P4"):
        sampled = train if probe_rows_per_phase <= 0 else train.sample(
            min(len(train), probe_rows_per_phase), random_state=seed + int(train_phase[1:]))
        x, feature_names = _phase_mask_matrix(sampled, train_phase, bases)
        if probe_columns is None:
            probe_columns = feature_names
        elif len(feature_names) != len(probe_columns):
            raise ValueError("missingness probe feature width differs across TRAIN phases")
        pooled_x.append(x); pooled_y.append(train_y[sampled.index])
    pooled_x = np.concatenate(pooled_x)
    pooled_y = np.concatenate(pooled_y)
    probe = fit_missingness_probe(pooled_x, pooled_y, seed=seed)
    probe_fit_rows = int(len(pooled_y))
    del pooled_x, pooled_y
    started = time.perf_counter(); records = []
    for split in ("VALIDATION", "TEST"):
        for phase in ("P1", "P2", "P3", "P4"):
            frame = pd.read_parquet(input_root / "model_inputs" / ("validation.parquet" if split == "VALIDATION" else f"test_{phase}.parquet"))
            prediction = pd.read_parquet(model_root / "predictions" / f"eval_split={split}" / f"phase_id={phase}" / "part-00000.parquet")
            y_true = prediction["y_true"].str.removeprefix("c").astype(int).to_numpy()
            probabilities = prediction[["prob_c0", "prob_c1", "prob_c2"]].to_numpy(dtype="float64")
            # Prediction and source input originate from the same immutable split.
            if len(frame) != len(prediction): raise ValueError(f"row mismatch {split}/{phase}")
            eval_x, _ = _phase_mask_matrix(frame, phase, bases)
            auc = score_missingness_probe_auc(probe, eval_x, y_true)
            values = classification_metrics(y_true, probabilities, train_class_counts=np.bincount(train_y, minlength=3), s_eff=train_s_eff, s_leak=s_leak_from_probe(auc))
            s_cal = float(max(0.0, 1.0 - values["ece"]))
            v2_parts = np.clip([values["s_nan"], values["s_maj_jsd"], s_cal, values["s_drift"],
                                values["s_eff"], values["s_leak"]], COMPOSITE_EPS, 1.0)
            s_san_plus_v2 = float(np.prod(v2_parts) ** (1 / len(v2_parts)))
            record = {"task": task, "feature_regime": REGIME[task], "window_id": window, "phase_id": phase,
                      "eval_split": split, "stage": "S3_MODEL", "pipeline_id": pipeline_id, "model_name": model_name,
                      "run_id": manifest["run_id"], "attempt_id": manifest["attempt_id"], "seed": seed,
                      "s_san_formula_version": "acctempo_m3_v1_jsd_base2_six_components",
                      "s_eff_definition_version": "model_input_mask_mean_v1", "s_leak_probe_rows_per_phase": probe_rows_per_phase,
                      "s_eff_train_source": "parent_imputation_train_unaugmented",
                      "s_leak_probe_fit_rows": probe_fit_rows, "s_leak_probe_fit_once": True,
                      "s_leak_probe_auc": auc,
                      "s_eff_observed_rate": train_observed_rate, "s_eff_availability_rate": train_availability_rate,
                      "prediction_nan_inf_count": values["prediction_nan_inf_count"],
                      "probability_sum_max_abs_error": values["probability_sum_max_abs_error"],
                      "s_cal": s_cal, "s_san_plus_v2": s_san_plus_v2,
                      **{key: values[key] for key in ("s_nan", "s_maj_jsd", "s_ent", "s_drift", "s_eff", "s_leak", "s_san_plus", "s_perf", "acctempo_m3")}}
            root = (Path(MOUNT) / f"meta_release={META_RELEASE}" / "L2_facts" / "sanity_components" / f"task={task}" /
                    f"feature_regime={REGIME[task]}" / f"window_id={window}" / f"phase_id={phase}" / "stage=S3_MODEL" /
                    f"pipeline_id={pipeline_id}" / f"model_name={model_name}" / f"run_id={manifest['run_id']}" / f"attempt_id={manifest['attempt_id']}")
            root.mkdir(parents=True, exist_ok=True)
            pd.DataFrame([record]).to_parquet(root / f"eval_split={split}.parquet", index=False); records.append(record)
    volume.commit()
    return {"run_id": manifest["run_id"], "attempt_id": manifest["attempt_id"], "records": len(records),
            "seconds": time.perf_counter() - started, "formula": "acctempo_m3_v1_jsd_base2_six_components"}


@app.local_entrypoint()
def cli(task: str = "CQ", window: str = "W1", pipeline_id: str = "V0", model_name: str = "RNN",
        seed: int = 42, run_id: str = "", probe_rows_per_phase: int = 0,
        split_version: str = "", phase_version: str = "", release_id: str = "") -> None:
    print(json.dumps(materialize_model_sanity.remote(task, window, pipeline_id, model_name, seed, run_id,
                                                     probe_rows_per_phase, split_version, phase_version, release_id), indent=2))
