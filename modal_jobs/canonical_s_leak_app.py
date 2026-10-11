"""Canonical real-row S_leak facts, shared by all models with one parent imputer.

This job neither reads model predictions nor trains a recurrent network.  It
fits the registered mask/availability probe once for each immutable parent
imputation run and scores the parent VALIDATION/TEST prefixes.
"""
from __future__ import annotations

import json
from pathlib import Path

import modal


APP_NAME, VOLUME_NAME, MOUNT = "tempo-canonical-s-leak-v1", "tempo-data-v1", "/data"
META_RELEASE = "imputation-v1"
REGIME = {"CQ": "CQ_RAW_EARLY", "LO": "LO_FULL_EARLY"}
PARENT_PIPELINES = {"V0", "V1", "V5", "V9", "V13"}
CLASSES = {"CQ": ("warning", "average", "good"), "LO": ("I/D", "G", "E")}

app = modal.App(APP_NAME)
volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=False)
image = (modal.Image.debian_slim(python_version="3.12")
         .pip_install("numpy>=1.26", "pandas>=2.2", "pyarrow>=16", "scikit-learn>=1.5")
         .add_local_python_source("metrics_core")
         .add_local_python_source("imputation_core")
         .add_local_python_source("release_core"))


def _selected_models(base: Path, *, task: str, seed: int, spec: dict[str, str], data_release_id: str):
    selected: dict[tuple[str, str], tuple[int, float, Path, dict]] = {}
    pattern = (f"task={task}/feature_regime={REGIME[task]}/window_id=*/pipeline_id=*/"
               f"model_name=RNN/seed={seed}/run_id=*/attempt_id=*/run_manifest.json")
    for path in base.glob(pattern):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if manifest.get("run_status") != "SUCCESS":
            continue
        if any(manifest.get(field) != spec[field] for field in
               ("release_id", "split_registry_id", "split_version", "phase_version")):
            continue
        if manifest.get("data_release_id") != data_release_id:
            continue
        pipeline, window = str(manifest.get("pipeline_id")), str(manifest.get("window_id"))
        if pipeline not in {f"V{i}" for i in range(17)} or window not in {"W1", "W2", "W3"}:
            continue
        suffix = str(manifest.get("attempt_id", "")).rsplit("-", 1)[-1]
        candidate = (int(suffix) if suffix.isdigit() else 0, path.stat().st_mtime, path.parent, manifest)
        key = pipeline, window
        if key not in selected or candidate[:2] > selected[key][:2]:
            selected[key] = candidate
    if len(selected) != 51:
        raise RuntimeError(f"Expected 51 current {task} model runs, found {len(selected)}")
    return [(path, manifest) for _, _, path, manifest in selected.values()]


def _class_ids(values, *, task: str):
    import pandas as pd
    return pd.Series(values, dtype="string").map(
        {name: index for index, name in enumerate(CLASSES[task])}
    ).to_numpy(dtype="int64")


def _phase_mask_matrix(frame, phase: str, dynamic_bases: list[str]):
    import numpy as np
    import pandas as pd
    columns = [f"missing__{base}_{phase}" for base in dynamic_bases if f"missing__{base}_{phase}" in frame]
    columns += [column for column in frame if column.startswith("missing__") and "_P" not in column]
    columns += [column for column in (f"phase_available_{phase}", f"video_observed_mask_{phase}",
                                      f"problem_observed_mask_{phase}", f"comment_observed_mask_{phase}")
                if column in frame]
    values = frame.loc[:, columns].apply(pd.to_numeric, errors="coerce").fillna(0).to_numpy(dtype="float32")
    modality = [column for column in (f"video_observed_mask_{phase}", f"problem_observed_mask_{phase}",
                                      f"comment_observed_mask_{phase}") if column in frame]
    zero_event = (frame.loc[:, modality].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1).eq(0)
                  .to_numpy(dtype="float32") if modality else np.zeros(len(frame), dtype="float32"))
    return np.column_stack((values, zero_event))


@app.function(image=image, volumes={MOUNT: volume}, cpu=8, memory=65536, timeout=60 * 60 * 6)
def materialize_canonical_s_leak(task: str = "CQ", seed: int = 42, release_id: str = "") -> dict:
    import numpy as np
    import pandas as pd
    from imputation_core.meta_storage import release_inventory
    from metrics_core.evaluation import fit_missingness_probe, score_missingness_probe_auc, s_leak_from_probe
    from release_core import resolve_release

    if task not in REGIME:
        raise ValueError("task must be CQ or LO")
    spec = resolve_release(task, release_id)
    volume.reload()
    base = Path(MOUNT) / f"meta_release={META_RELEASE}"
    data_release_id = release_inventory(Path(MOUNT) / "input" / spec["input_dir"], task=task)["data_release_id"]
    models = _selected_models(base / "L1_runs", task=task, seed=seed, spec=spec, data_release_id=data_release_id)

    # Every model declares its immutable parent.  The representative with the
    # lexically lowest pipeline supplies an identical feature layout only;
    # values and labels always come from the parent imputation artifacts.
    parents: dict[tuple[str, str], tuple[Path, dict]] = {}
    for model_root, manifest in models:
        parent_id = str(manifest.get("parent_imputation_run_id"))
        key = str(manifest["window_id"]), parent_id
        candidate = (model_root, manifest)
        if key not in parents or str(manifest["pipeline_id"]) < str(parents[key][1]["pipeline_id"]):
            parents[key] = candidate
    if len(parents) != 15:
        raise RuntimeError(f"Expected 15 window/parent-imputer cells, found {len(parents)}")

    records = []
    for (window, parent_id), (model_root, manifest) in sorted(parents.items()):
        input_root = Path(manifest["input_root"])
        layout = json.loads((model_root / "feature_layout.json").read_text(encoding="utf-8"))
        bases = list(layout["dynamic_bases"])
        train = pd.read_parquet(input_root / "model_inputs" / "train.parquet")
        label_column = "CQ_label_final" if task == "CQ" else "LO_performance_label_3"
        train_y = _class_ids(train[label_column], task=task)
        pooled_x = [_phase_mask_matrix(train, phase, bases) for phase in ("P1", "P2", "P3", "P4")]
        pooled_y = [train_y] * 4
        probe = fit_missingness_probe(np.concatenate(pooled_x), np.concatenate(pooled_y), seed=seed)
        fit_rows = int(sum(len(values) for values in pooled_y))
        for eval_split in ("VALIDATION", "TEST"):
            for phase in ("P1", "P2", "P3", "P4"):
                file_name = "validation.parquet" if eval_split == "VALIDATION" else f"test_{phase}.parquet"
                frame = pd.read_parquet(input_root / "model_inputs" / file_name)
                eval_y = _class_ids(frame[label_column], task=task)
                auc = score_missingness_probe_auc(probe, _phase_mask_matrix(frame, phase, bases), eval_y)
                records.append({
                    "task": task, "feature_regime": REGIME[task], "release_id": spec["release_id"],
                    "data_release_id": data_release_id, "window_id": window,
                    "parent_imputation_run_id": parent_id, "eval_split": eval_split, "phase_id": phase,
                    "probe_seed": seed, "probe_fit_rows": fit_rows,
                    "s_leak_probe_n_eval": int(len(eval_y)),
                    "probe_fit_scope": "PARENT_IMPUTATION_REAL_TRAIN_POOLED_P1_P4",
                    "probe_score_scope": "PARENT_IMPUTATION_REAL_EVAL_PREFIX",
                    "s_leak_probe_auc": auc, "s_leak": s_leak_from_probe(auc),
                })

    output = (base / "L2_facts" / "canonical_s_leak" / f"task={task}" / f"feature_regime={REGIME[task]}" /
              f"release_id={spec['release_id']}" /
              f"data_release_id={data_release_id.replace(':', '_')}" / f"seed={seed}")
    output.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(records).to_parquet(output / "part-00000.parquet", index=False)
    volume.commit()
    return {"task": task, "release_id": spec["release_id"], "data_release_id": data_release_id,
            "parent_cells": len(parents), "records": len(records), "path": str(output / "part-00000.parquet")}


@app.function(image=image, volumes={MOUNT: volume}, cpu=2, memory=4096, timeout=20 * 60)
def backfill_canonical_s_leak_n_eval(task: str = "CQ", seed: int = 42, release_id: str = "") -> dict:
    """Attach immutable evaluation cardinalities without refitting the probe.

    ``n_eval`` is a property of each frozen evaluation cohort, not of the
    probe.  Backfilling it from manifest-declared metrics preserves the
    already-accepted canonical AUC values while avoiding an unnecessary
    reread/refit of 15 pooled parent TRAIN cohorts.
    """
    import pandas as pd
    from imputation_core.meta_storage import release_inventory
    from release_core import resolve_release

    if task not in REGIME:
        raise ValueError("task must be CQ or LO")
    spec = resolve_release(task, release_id)
    volume.reload()
    base = Path(MOUNT) / f"meta_release={META_RELEASE}"
    data_release_id = release_inventory(Path(MOUNT) / "input" / spec["input_dir"], task=task)["data_release_id"]
    models = _selected_models(base / "L1_runs", task=task, seed=seed, spec=spec, data_release_id=data_release_id)
    representatives: dict[tuple[str, str], dict] = {}
    for _, manifest in models:
        key = str(manifest["window_id"]), str(manifest["parent_imputation_run_id"])
        if key not in representatives or str(manifest["pipeline_id"]) < str(representatives[key]["pipeline_id"]):
            representatives[key] = manifest
    if len(representatives) != 15:
        raise RuntimeError(f"Expected 15 window/parent-imputer cells, found {len(representatives)}")

    counts = []
    for (window, parent_id), manifest in representatives.items():
        metrics_paths = [Path(path) for path in manifest.get("metrics_paths", [])]
        if len(metrics_paths) != 4:
            raise RuntimeError(f"Expected four metrics paths for {window}/{parent_id}")
        metrics = pd.concat([pd.read_parquet(path) for path in metrics_paths], ignore_index=True)
        for row in metrics.itertuples(index=False):
            if row.eval_split not in {"VALIDATION", "TEST"}:
                continue
            counts.append({"window_id": window, "parent_imputation_run_id": parent_id,
                           "eval_split": row.eval_split, "phase_id": row.phase_id,
                           "s_leak_probe_n_eval": int(row.n_rows)})
    cohort_sizes = pd.DataFrame(counts)
    expected = 15 * 2 * 4
    if len(cohort_sizes) != expected:
        raise RuntimeError(f"Expected {expected} immutable evaluation-size rows, got {len(cohort_sizes)}")

    output = (base / "L2_facts" / "canonical_s_leak" / f"task={task}" / f"feature_regime={REGIME[task]}" /
              f"release_id={spec['release_id']}" /
              f"data_release_id={data_release_id.replace(':', '_')}" / f"seed={seed}")
    target = output / "part-00000.parquet"
    canonical = pd.read_parquet(target)
    if len(canonical) != expected:
        raise RuntimeError(f"Incomplete canonical S_leak facts: expected {expected}, got {len(canonical)}")
    canonical = canonical.drop(columns=["s_leak_probe_n_eval"], errors="ignore").merge(
        cohort_sizes, on=["window_id", "parent_imputation_run_id", "eval_split", "phase_id"],
        how="left", validate="one_to_one",
    )
    if canonical["s_leak_probe_n_eval"].isna().any():
        raise RuntimeError("Could not resolve a canonical S_leak evaluation cohort size")
    canonical.to_parquet(target, index=False)
    volume.commit()
    return {"task": task, "release_id": spec["release_id"], "data_release_id": data_release_id,
            "records": len(canonical), "path": str(target), "operation": "n_eval_backfill"}


@app.local_entrypoint()
def cli(task: str = "CQ", seed: int = 42, release_id: str = "", mode: str = "materialize") -> None:
    if mode == "materialize":
        result = materialize_canonical_s_leak.remote(task, seed, release_id)
    elif mode == "backfill_n_eval":
        result = backfill_canonical_s_leak_n_eval.remote(task, seed, release_id)
    else:
        raise ValueError("mode must be materialize or backfill_n_eval")
    print(json.dumps(result, indent=2))
