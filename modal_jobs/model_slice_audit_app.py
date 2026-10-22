"""Post-hoc STRICT/OVERLAP metrics for locked recurrent prediction artifacts.

The job never retrains or changes L1 predictions.  It selects only successful
manifests matching the active release and writes compact L2 slice facts.
"""
from __future__ import annotations

import json
from pathlib import Path

import modal


APP_NAME, VOLUME_NAME, MOUNT = "tempo-model-slice-audit-v1", "tempo-data-v1", "/data"
META_RELEASE = "imputation-v1"
REGIME = {"CQ": "CQ_RAW_EARLY", "LO": "LO_FULL_EARLY"}

app = modal.App(APP_NAME)
volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=False)
image = (modal.Image.debian_slim(python_version="3.12")
         .pip_install("numpy>=1.26", "pandas>=2.2", "pyarrow>=16", "scikit-learn>=1.5")
         .add_local_python_source("imputation_core")
         .add_local_python_source("release_core"))


def _selected_runs(base: Path, *, task: str, model_name: str, seed: int,
                   spec: dict[str, str], accepted_identities: dict[str, str]) -> list[tuple[Path, dict]]:
    selected: dict[tuple[str, str], tuple[int, float, Path, dict]] = {}
    pattern = (f"task={task}/feature_regime={REGIME[task]}/window_id=*/pipeline_id=*/"
               f"model_name={model_name}/seed={seed}/run_id=*/attempt_id=*/run_manifest.json")
    for path in base.glob(pattern):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if manifest.get("run_status") != "SUCCESS":
            continue
        if any(manifest.get(field) != expected for field, expected in (
            ("release_id", spec["release_id"]),
            ("split_registry_id", spec["split_registry_id"]),
            ("split_version", spec["split_version"]),
            ("phase_version", spec["phase_version"]),
        )):
            continue
        identity = str(manifest.get("data_release_id") or "")
        if identity not in accepted_identities:
            raise ValueError(
                f"{task} manifest matches the active release contract but has unknown "
                f"data_release_id={identity or '<absent>'}"
            )
        manifest = {**manifest, "data_release_identity_class": accepted_identities[identity]}
        pipeline, window = str(manifest.get("pipeline_id")), str(manifest.get("window_id"))
        if pipeline not in {f"V{i}" for i in range(17)} or window not in {"W1", "W2", "W3"}:
            continue
        suffix = str(manifest.get("attempt_id", "")).rsplit("-", 1)[-1]
        candidate = (int(suffix) if suffix.isdigit() else 0, path.stat().st_mtime, path.parent, manifest)
        key = pipeline, window
        if key not in selected or candidate[:2] > selected[key][:2]:
            selected[key] = candidate
    return [(path, manifest) for _, _, path, manifest in selected.values()]


def _slice_metrics(frame, *, task: str, window: str, phase: str, split: str,
                   pipeline: str, model_name: str, run_id: str, attempt_id: str,
                   slice_name: str) -> list[dict]:
    import numpy as np
    from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, matthews_corrcoef, precision_recall_fscore_support

    truth = frame["y_true"].astype(str).str.removeprefix("c").astype(int).to_numpy()
    pred = frame["y_pred"].astype(str).str.removeprefix("c").astype(int).to_numpy()
    precision, recall, f1, support = precision_recall_fscore_support(
        truth, pred, labels=np.arange(3), zero_division=0,
    )
    n = int(len(frame))
    small = bool(n < 30 or int(support.min()) < 5)
    common = {
        "task": task, "feature_regime": REGIME[task], "window_id": window, "phase_id": phase,
        "eval_split": split, "pipeline_id": pipeline, "model_name": model_name,
        "run_id": run_id, "attempt_id": attempt_id, "slice": slice_name,
        "n_eval_samples": n, "small_subgroup_flag": small,
        "macro_f1": float(f1_score(truth, pred, labels=np.arange(3), average="macro", zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(truth, pred)),
        "accuracy": float(accuracy_score(truth, pred)),
        "mcc": float(matthews_corrcoef(truth, pred)) if len(np.unique(truth)) > 1 else None,
    }
    return [{**common, "class_index": int(cls), "precision": float(precision[cls]),
             "recall": float(recall[cls]), "f1": float(f1[cls]), "support": int(support[cls])}
            for cls in range(3)]


@app.function(image=image, volumes={MOUNT: volume}, cpu=4, memory=16384, timeout=60 * 60 * 3)
def materialize_slice_audit(task: str = "CQ", model_name: str = "RNN", seed: int = 42,
                            release_id: str = "") -> dict:
    import pandas as pd
    from imputation_core.meta_storage import release_identity_aliases
    from release_core import resolve_release

    if task not in REGIME:
        raise ValueError("task must be CQ or LO")
    spec = resolve_release(task, release_id)
    volume.reload()
    release, accepted_identities = release_identity_aliases(
        Path(MOUNT) / "input" / spec["input_dir"], task=task
    )
    active_id = release["data_release_id"]
    base = Path(MOUNT) / f"meta_release={META_RELEASE}"
    runs = _selected_runs(base / "L1_runs", task=task, model_name=model_name, seed=seed,
                          spec=spec, accepted_identities=accepted_identities)
    if len(runs) != 51:
        raise RuntimeError(f"Expected 51 current {task} runs, found {len(runs)}")
    fact_root = base / "L2_facts" / "evaluation_slices"
    records, outputs = [], []
    for model_root, manifest in runs:
        pipeline, window = manifest["pipeline_id"], manifest["window_id"]
        run_id, attempt_id = manifest["run_id"], manifest["attempt_id"]
        for split in ("VALIDATION", "TEST"):
            for phase in ("P1", "P2", "P3", "P4"):
                path = model_root / "predictions" / f"eval_split={split}" / f"phase_id={phase}" / "part-00000.parquet"
                frame = pd.read_parquet(path)
                strict_column = f"temporal_strict_{phase}"
                required = {"y_true", "y_pred", strict_column}
                missing = required.difference(frame.columns)
                if missing:
                    raise ValueError(f"Prediction artifact lacks STRICT context {sorted(missing)}: {path}")
                for name, subset in (
                    ("ALL", frame),
                    ("STRICT", frame[pd.to_numeric(frame[strict_column], errors="coerce").fillna(0).astype(int) == 1]),
                    ("OVERLAP", frame[pd.to_numeric(frame[strict_column], errors="coerce").fillna(0).astype(int) == 0]),
                ):
                    if subset.empty:
                        continue
                    records.extend(_slice_metrics(subset, task=task, window=window, phase=phase, split=split,
                                                  pipeline=pipeline, model_name=model_name, run_id=run_id,
                                                  attempt_id=attempt_id, slice_name=name))
        root = (fact_root / f"task={task}" / f"feature_regime={REGIME[task]}" / f"window_id={window}" /
                "stage=S3_MODEL" / f"pipeline_id={pipeline}" / f"model_name={model_name}" /
                f"run_id={run_id}" / f"attempt_id={attempt_id}")
        root.mkdir(parents=True, exist_ok=True)
        own = [record for record in records if record["run_id"] == run_id and record["attempt_id"] == attempt_id]
        pd.DataFrame(own).to_parquet(root / "part-00000.parquet", index=False)
        outputs.append(str(root / "part-00000.parquet"))
    volume.commit()
    return {"task": task, "release_id": spec["release_id"], "data_release_id": active_id,
            "runs": len(runs), "records": len(records), "paths": outputs}


@app.function(image=image, volumes={MOUNT: volume}, cpu=1, memory=2048, timeout=20 * 60)
def inspect_slice_audit(task: str = "CQ", model_name: str = "RNN", seed: int = 42,
                        release_id: str = "") -> dict:
    """Verify all current run manifests have complete ALL/STRICT/OVERLAP facts."""
    import pandas as pd
    from imputation_core.meta_storage import release_identity_aliases
    from release_core import resolve_release

    spec = resolve_release(task, release_id)
    volume.reload()
    release, accepted_identities = release_identity_aliases(
        Path(MOUNT) / "input" / spec["input_dir"], task=task
    )
    active_id = release["data_release_id"]
    base = Path(MOUNT) / f"meta_release={META_RELEASE}"
    runs = _selected_runs(base / "L1_runs", task=task, model_name=model_name, seed=seed,
                          spec=spec, accepted_identities=accepted_identities)
    root = base / "L2_facts" / "evaluation_slices"
    frames, missing = [], []
    for _, manifest in runs:
        path = (root / f"task={task}" / f"feature_regime={REGIME[task]}" /
                f"window_id={manifest['window_id']}" / "stage=S3_MODEL" /
                f"pipeline_id={manifest['pipeline_id']}" / f"model_name={model_name}" /
                f"run_id={manifest['run_id']}" / f"attempt_id={manifest['attempt_id']}" / "part-00000.parquet")
        if not path.is_file():
            missing.append(str(path))
        else:
            frames.append(pd.read_parquet(path))
    facts = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    expected_cells = len(runs) * 2 * 4 * 3
    actual_cells = (facts[["run_id", "eval_split", "phase_id", "slice"]].drop_duplicates().shape[0]
                    if not facts.empty else 0)
    expected_records = expected_cells * 3
    return {
        "task": task, "release_id": spec["release_id"], "data_release_id": active_id,
        "expected_runs": 51, "actual_runs": len(runs), "files_found": len(frames), "missing_files": missing,
        "expected_cells": expected_cells, "actual_cells": actual_cells,
        "expected_records": expected_records, "actual_records": int(len(facts)),
        "complete": len(runs) == 51 and not missing and actual_cells == expected_cells and len(facts) == expected_records,
    }


@app.local_entrypoint()
def cli(task: str = "CQ", model_name: str = "RNN", seed: int = 42, release_id: str = "",
        mode: str = "materialize") -> None:
    if mode == "materialize":
        result = materialize_slice_audit.remote(task, model_name, seed, release_id)
    elif mode == "status":
        result = inspect_slice_audit.remote(task, model_name, seed, release_id)
    else:
        raise ValueError("mode must be materialize or status")
    print(json.dumps(result, indent=2))
