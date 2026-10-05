"""Post-hoc uncertainty facts for immutable recurrent prediction artifacts.

This app never retrains or rewrites a model run.  It reads stored prediction
rows, verifies release identity/alignment, and writes L2 bootstrap facts.
"""
from __future__ import annotations

import json
from pathlib import Path

import modal

APP_NAME, VOLUME_NAME, MOUNT = "tempo-model-bootstrap-v1", "tempo-data-v1", "/data"
META_RELEASE = "imputation-v1"
REGIME = {"CQ": "CQ_RAW_EARLY", "LO": "LO_FULL_EARLY"}

app = modal.App(APP_NAME)
volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=False)
image = (modal.Image.debian_slim(python_version="3.12")
         .pip_install("numpy>=1.26", "pandas>=2.2", "pyarrow>=16", "scikit-learn>=1.5")
         .add_local_python_source("model")
         .add_local_python_source("release_core"))


def _latest(root: Path, spec: dict[str, str]) -> tuple[Path, dict]:
    candidates = sorted(root.glob("run_id=*/attempt_id=*/run_manifest.json"),
                        key=lambda path: path.stat().st_mtime, reverse=True)
    for path in candidates:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if manifest.get("run_status") != "SUCCESS":
            continue
        if all(manifest.get(field) == spec[field] for field in
               ("release_id", "split_registry_id", "split_version", "phase_version", "label_rule_version")):
            return path.parent, manifest
    raise FileNotFoundError(f"No successful locked model artifact under {root}")


def _model_root(task: str, window: str, pipeline_id: str, model_name: str, seed: int, spec: dict[str, str]) -> tuple[Path, dict]:
    root = (Path(MOUNT) / f"meta_release={META_RELEASE}" / "L1_runs" / f"task={task}" /
            f"feature_regime={REGIME[task]}" / f"window_id={window}" / f"pipeline_id={pipeline_id}" /
            f"model_name={model_name}" / f"seed={seed}")
    return _latest(root, spec)


def _predictions(root: Path, split: str, phase: str):
    import pandas as pd
    path = root / "predictions" / f"eval_split={split}" / f"phase_id={phase}" / "part-00000.parquet"
    frame = pd.read_parquet(path)
    required = {"enrollment_id_hash", "y_true", "y_pred", "offering_id"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Prediction artifact lacks bootstrap columns {sorted(missing)}: {path}")
    return frame.sort_values("enrollment_id_hash", kind="stable").reset_index(drop=True)


def _cluster_per_class_ci(frame, *, repetitions: int, seed: int) -> list[dict]:
    """Offering-resampled F1 sensitivity only when a true class spans <=2 offerings."""
    import numpy as np
    from sklearn.metrics import f1_score

    truth = frame["y_true"].str.removeprefix("c").astype(int).to_numpy()
    pred = frame["y_pred"].str.removeprefix("c").astype(int).to_numpy()
    groups = frame["offering_id"].astype("string").to_numpy()
    rng = np.random.default_rng(seed)
    rows: list[dict] = []
    # Materialize offering-to-row membership once.  Re-scanning the full
    # prediction frame for every sampled offering makes the bootstrap
    # needlessly quadratic in the number of offerings.
    all_groups, group_codes = np.unique(groups, return_inverse=True)
    order = np.argsort(group_codes, kind="stable")
    bounds = np.searchsorted(group_codes[order], np.arange(len(all_groups) + 1))
    members = [order[bounds[code]:bounds[code + 1]] for code in range(len(all_groups))]
    for class_id in range(3):
        class_groups = np.unique(groups[truth == class_id])
        if len(class_groups) == 0 or len(class_groups) > 2:
            continue
        values = np.empty(repetitions, dtype=float)
        for draw in range(repetitions):
            sampled = rng.integers(0, len(all_groups), size=len(all_groups))
            indices = np.concatenate([members[code] for code in sampled])
            values[draw] = f1_score(truth[indices], pred[indices], labels=[class_id], average="macro", zero_division=0)
        rows.append({"class_index": class_id, "metric_name": "f1", "estimate": float(f1_score(truth, pred, labels=[class_id], average="macro", zero_division=0)),
                     "ci_lower": float(np.quantile(values, .025)), "ci_upper": float(np.quantile(values, .975)),
                     "bootstrap_method": "offering_cluster_bootstrap_v1", "bootstrap_repetitions": repetitions,
                     "bootstrap_seed": seed, "ci_level": .95, "n_offerings_with_class": int(len(class_groups))})
    return rows


@app.function(image=image, volumes={MOUNT: volume}, cpu=4, memory=16384, timeout=60 * 60 * 8)
def materialize_model_uncertainty(task: str = "LO", window: str = "W1", pipeline_id: str = "V0",
                                  reference_pipeline_id: str = "V0", model_name: str = "RNN", seed: int = 42,
                                  repetitions: int = 2000, release_id: str = "") -> dict:
    import numpy as np
    import pandas as pd
    from model.paired_bootstrap import paired_bootstrap_macro_f1_delta
    from release_core import resolve_release

    if task not in REGIME or window not in {"W1", "W2", "W3"} or repetitions < 100:
        raise ValueError("task=CQ|LO, window=W1..W3, repetitions>=100 required")
    spec = resolve_release(task, release_id)
    volume.reload()
    candidate_root, candidate_manifest = _model_root(task, window, pipeline_id, model_name, seed, spec)
    reference_root, reference_manifest = _model_root(task, window, reference_pipeline_id, model_name, seed, spec)
    paired_rows, cluster_rows = [], []
    for split in ("VALIDATION", "TEST"):
        for phase in ("P1", "P2", "P3", "P4"):
            candidate = _predictions(candidate_root, split, phase)
            reference = _predictions(reference_root, split, phase)
            if not candidate["enrollment_id_hash"].equals(reference["enrollment_id_hash"]) or not candidate["y_true"].equals(reference["y_true"]):
                raise ValueError(f"Paired bootstrap requires exact aligned rows: {split}/{phase}")
            y_true = candidate["y_true"].str.removeprefix("c").astype(int).to_numpy()
            candidate_pred = candidate["y_pred"].str.removeprefix("c").astype(int).to_numpy()
            reference_pred = reference["y_pred"].str.removeprefix("c").astype(int).to_numpy()
            paired = paired_bootstrap_macro_f1_delta(y_true, reference_pred, candidate_pred, np.arange(3),
                                                      repetitions=repetitions, seed=seed)
            paired_rows.append({"task": task, "feature_regime": REGIME[task], "window_id": window, "phase_id": phase,
                                "eval_split": split, "pipeline_id": pipeline_id, "reference_pipeline_id": reference_pipeline_id,
                                "model_name": model_name, "run_id": candidate_manifest["run_id"],
                                "reference_run_id": reference_manifest["run_id"], "attempt_id": candidate_manifest["attempt_id"], **paired})
            for record in _cluster_per_class_ci(candidate, repetitions=repetitions, seed=seed):
                cluster_rows.append({"task": task, "feature_regime": REGIME[task], "window_id": window, "phase_id": phase,
                                     "eval_split": split, "pipeline_id": pipeline_id, "model_name": model_name,
                                     "run_id": candidate_manifest["run_id"], "attempt_id": candidate_manifest["attempt_id"], **record})
    base = Path(MOUNT) / f"meta_release={META_RELEASE}" / "L2_facts"
    paired_root = (base / "paired_bootstrap" / f"task={task}" / f"window_id={window}" /
                   f"pipeline_id={pipeline_id}" / f"reference_pipeline_id={reference_pipeline_id}" /
                   f"model_name={model_name}" / f"run_id={candidate_manifest['run_id']}" / f"attempt_id={candidate_manifest['attempt_id']}")
    paired_root.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(paired_rows).to_parquet(paired_root / "part-00000.parquet", index=False)
    cluster_root = (base / "offering_cluster_bootstrap" / f"task={task}" / f"window_id={window}" /
                    f"pipeline_id={pipeline_id}" / f"model_name={model_name}" /
                    f"run_id={candidate_manifest['run_id']}" / f"attempt_id={candidate_manifest['attempt_id']}")
    cluster_root.mkdir(parents=True, exist_ok=True)
    if cluster_rows:
        pd.DataFrame(cluster_rows).to_parquet(cluster_root / "part-00000.parquet", index=False)
    else:
        (cluster_root / "no_eligible_cells.json").write_text(
            json.dumps({"reason": "no_class_with_n_offerings_lte_2", "task": task, "window_id": window}),
            encoding="utf-8",
        )
    volume.commit()
    return {"paired_records": len(paired_rows), "cluster_records": len(cluster_rows),
            "paired_path": str(paired_root / "part-00000.parquet"), "cluster_path": str(cluster_root / "part-00000.parquet")}


@app.local_entrypoint()
def cli(task: str = "LO", window: str = "W1", pipeline_id: str = "V0", reference_pipeline_id: str = "V0",
        model_name: str = "RNN", seed: int = 42, repetitions: int = 2000, release_id: str = "") -> None:
    print(json.dumps(materialize_model_uncertainty.remote(task, window, pipeline_id, reference_pipeline_id,
                                                          model_name, seed, repetitions, release_id), indent=2))
