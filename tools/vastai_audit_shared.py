"""Post-hoc, Modal-free audit facts for VastAI shared-checkpoint runs.

The runner consumes the compact immutable input tree and predictions written by
``vastai_train_shared.py``.  It never reloads a checkpoint or retrains a
model.  Its output is deliberately compact: all tables are Parquet facts that
can be copied back to the workstation or an L2 store without moving the
multi-gigabyte model inputs.

``canonical_s_leak`` is fit once per (window, real parent imputer) and then
joined to every derived/augmented pipeline.  This prevents augmentation from
changing the leakage diagnostic merely by adding synthetic TRAIN rows.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

# The upload scripts place this file beside ``model/`` and ``metrics_core/``
# under ``/workspace/CD3/code``.  The same lookup also supports direct local
# execution from the repository's ``tools/`` directory.
PROJECT_ROOT = next(
    (candidate for candidate in (Path(__file__).resolve().parent, Path(__file__).resolve().parents[1])
     if (candidate / "model").is_dir() and (candidate / "metrics_core").is_dir()),
    None,
)
if PROJECT_ROOT is None:
    raise RuntimeError("Cannot locate sibling model/ and metrics_core/ packages.")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vastai_metadata_contract import PARENT_PIPELINES, load_download_manifest


CLASSES = {"CQ": ("warning", "average", "good"), "LO": ("I/D", "G", "E")}
REGIMES = {"CQ": "CQ_RAW_EARLY", "LO": "LO_FULL_EARLY"}
PHASES = ("P1", "P2", "P3", "P4")
SPLITS = ("VALIDATION", "TEST")


def _parse() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", choices=tuple(CLASSES), required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True,
                        help="Root containing TASK/W{1..3}/V{0..16}/MODEL/seed=N")
    parser.add_argument("--audit-root", type=Path, required=True)
    parser.add_argument("--model-name", default="RNN")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--bootstrap-repetitions", type=int, default=2000)
    parser.add_argument("--allow-partial", action="store_true",
                        help="For smoke tests only; official exports require all 51 cells.")
    return parser.parse_args()


def _label(task: str) -> str:
    return "CQ_label_final" if task == "CQ" else "LO_performance_label_3"


def _class_ids(values: pd.Series, task: str) -> np.ndarray:
    # Prediction artifacts encode targets as c0/c1/c2 to keep their schema
    # task-neutral, whereas input releases retain their human-readable labels.
    # Both are the same locked class order declared in ``CLASSES``.
    mapping = {name: index for index, name in enumerate(CLASSES[task])}
    mapping.update({f"c{index}": index for index in range(len(CLASSES[task]))})
    mapped = values.astype("string").map(mapping)
    if mapped.isna().any():
        raise ValueError(f"Unknown {task} labels: {sorted(values[mapped.isna()].astype(str).unique())}")
    return mapped.to_numpy(dtype="int64")


def _read_layout(run_dir: Path) -> dict:
    return json.loads((run_dir / "feature_layout.json").read_text(encoding="utf-8"))


def _mask_matrix(frame: pd.DataFrame, phase: str, bases: list[str]) -> np.ndarray:
    columns = [f"missing__{base}_{phase}" for base in bases if f"missing__{base}_{phase}" in frame]
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


def _s_eff(frame: pd.DataFrame, bases: list[str]) -> tuple[float, float, float]:
    values = []
    for phase in PHASES:
        missing = [f"missing__{base}_{phase}" for base in bases if f"missing__{base}_{phase}" in frame]
        missing += [column for column in frame if column.startswith("missing__") and "_P" not in column]
        observed = 1.0 - frame.loc[:, missing].apply(pd.to_numeric, errors="coerce").fillna(1).to_numpy().mean() if missing else 1.0
        available = [column for column in (f"phase_available_{phase}", f"video_observed_mask_{phase}",
                                             f"problem_observed_mask_{phase}", f"comment_observed_mask_{phase}") if column in frame]
        availability = frame.loc[:, available].apply(pd.to_numeric, errors="coerce").fillna(0).to_numpy().mean() if available else 1.0
        effective = (observed * len(missing) + availability * len(available)) / max(len(missing) + len(available), 1)
        values.append((effective, observed, availability))
    return tuple(float(np.mean([row[index] for row in values])) for index in range(3))


def _run_dir(root: Path, task: str, window: str, pipeline: str, model: str, seed: int) -> Path:
    return root / task / window / pipeline / model / f"seed={seed}"


def _selected_runs(args: argparse.Namespace, release: dict) -> dict[tuple[str, str], Path]:
    selected: dict[tuple[str, str], Path] = {}
    for window in ("W1", "W2", "W3"):
        for index in range(17):
            pipeline = f"V{index}"
            path = _run_dir(args.run_root, args.task, window, pipeline, args.model_name, args.seed)
            manifest_path = path / "run_manifest.json"
            contract_path = path / "metadata_contract.json"
            if not manifest_path.is_file() or not contract_path.is_file():
                continue
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            if manifest.get("task") != args.task or manifest.get("window_id") != window or manifest.get("pipeline_id") != pipeline:
                raise ValueError(f"Run identity mismatch: {path}")
            if contract.get("release", {}).get("release_id") != release["release_id"]:
                raise ValueError(f"Release mismatch in {contract_path}")
            selected[(window, pipeline)] = path
    if not args.allow_partial and len(selected) != 51:
        missing = [f"{window}/{pipeline}" for window in ("W1", "W2", "W3") for pipeline in (f"V{i}" for i in range(17))
                   if (window, pipeline) not in selected]
        raise RuntimeError(f"Expected 51 immutable runs, found {len(selected)}; missing={missing}")
    if not selected:
        raise RuntimeError("No valid VastAI runs found")
    return selected


def _prediction(run_dir: Path, split: str, phase: str) -> pd.DataFrame:
    prefix = "validation" if split == "VALIDATION" else "test"
    path = run_dir / "predictions" / f"{prefix}_{phase}.parquet"
    frame = pd.read_parquet(path)
    required = {"y_true", "y_pred", "prob_c0", "prob_c1", "prob_c2"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Prediction lacks {sorted(missing)}: {path}")
    return frame


def _canonical_s_leak(args: argparse.Namespace, selected: dict[tuple[str, str], Path]) -> pd.DataFrame:
    from metrics_core.evaluation import fit_missingness_probe, score_missingness_probe_auc, s_leak_from_probe

    records: list[dict] = []
    parent_pipelines = sorted(set(PARENT_PIPELINES.get(pipeline, pipeline) for _, pipeline in selected))
    for window in ("W1", "W2", "W3"):
        for parent in parent_pipelines:
            representative = next((path for (item_window, pipeline), path in selected.items()
                                   if item_window == window and PARENT_PIPELINES.get(pipeline, pipeline) == parent), None)
            if representative is None:
                continue
            layout = _read_layout(representative)
            bases = list(layout["dynamic_bases"])
            train = pd.read_parquet(args.data_root / "train" / window / parent / "train.parquet")
            train_y = _class_ids(train[_label(args.task)], args.task)
            x = np.concatenate([_mask_matrix(train, phase, bases) for phase in PHASES])
            y = np.concatenate([train_y] * len(PHASES))
            probe = fit_missingness_probe(x, y, seed=args.seed)
            for split in SPLITS:
                for phase in PHASES:
                    input_path = (args.data_root / "evaluation" / window / parent /
                                  ("validation.parquet" if split == "VALIDATION" else f"test_{phase}.parquet"))
                    frame = pd.read_parquet(input_path)
                    labels = _class_ids(frame[_label(args.task)], args.task)
                    auc = score_missingness_probe_auc(probe, _mask_matrix(frame, phase, bases), labels)
                    records.append({
                        "task": args.task, "feature_regime": REGIMES[args.task], "window_id": window,
                        "parent_pipeline": parent, "eval_split": split, "phase_id": phase,
                        "probe_seed": args.seed, "probe_fit_rows": int(len(y)), "s_leak_probe_n_eval": int(len(labels)),
                        "probe_fit_scope": "PARENT_IMPUTATION_REAL_TRAIN_POOLED_P1_P4",
                        "probe_score_scope": "PARENT_IMPUTATION_REAL_EVAL_PREFIX",
                        "s_leak_probe_auc": auc, "s_leak": s_leak_from_probe(auc),
                    })
    expected = len({window for window, _ in selected}) * len(parent_pipelines) * len(SPLITS) * len(PHASES)
    if len(records) != expected:
        raise RuntimeError(f"Canonical S_leak incomplete: expected {expected}, got {len(records)}")
    return pd.DataFrame(records)


def _slice_rows(frame: pd.DataFrame, *, task: str, window: str, pipeline: str, model: str,
                seed: int, split: str, phase: str) -> list[dict]:
    from metrics_core.evaluation import classification_metrics

    strict_col = f"temporal_strict_{phase}"
    if strict_col not in frame:
        raise ValueError(f"Prediction lacks {strict_col}; cannot produce STRICT/OVERLAP facts")
    rows = []
    for name, subset in (("ALL", frame),
                         ("STRICT", frame[pd.to_numeric(frame[strict_col], errors="coerce").fillna(0).astype(int) == 1]),
                         ("OVERLAP", frame[pd.to_numeric(frame[strict_col], errors="coerce").fillna(0).astype(int) == 0])):
        if subset.empty:
            continue
        probabilities = subset[["prob_c0", "prob_c1", "prob_c2"]].to_numpy(dtype=float)
        values = classification_metrics(_class_ids(subset["y_true"], task), probabilities)
        rows.append({"task": task, "feature_regime": REGIMES[task], "window_id": window, "pipeline_id": pipeline,
                     "model_name": model, "seed": seed, "eval_split": split, "phase_id": phase,
                     "slice": name, **values})
    return rows


def _run_facts(args: argparse.Namespace, selected: dict[tuple[str, str], Path], canonical: pd.DataFrame):
    from metrics_core.evaluation import COMPOSITE_EPS, classification_metrics
    from model.metrics import per_class_metric_records, stratified_bootstrap_per_class_ci

    sanity: list[dict] = []; slices: list[dict] = []; per_class: list[dict] = []; bootstrap: list[dict] = []; selection: list[dict] = []
    for (window, pipeline), run_dir in sorted(selected.items()):
        manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
        parent = PARENT_PIPELINES.get(pipeline, pipeline)
        layout = _read_layout(run_dir); bases = list(layout["dynamic_bases"])
        train = pd.read_parquet(args.data_root / "train" / window / parent / "train.parquet")
        train_y = _class_ids(train[_label(args.task)], args.task)
        train_counts = np.bincount(train_y, minlength=3)
        s_eff, observed_rate, availability_rate = _s_eff(train, bases)
        history = pd.read_parquet(run_dir / "train_history.parquet")
        score_col = "validation_macro_f1_mean_p1_p4"
        if score_col not in history:
            raise ValueError(f"Training history lacks {score_col}: {run_dir}")
        ordered = sorted(((float(row[score_col]), int(row["epoch"])) for _, row in history.iterrows()), reverse=True)
        best_score, best_epoch = ordered[0]; second = ordered[1][0] if len(ordered) > 1 else best_score
        margin = best_score - second
        selection.append({"task": args.task, "window_id": window, "pipeline_id": pipeline,
                          "model_name": args.model_name, "seed": args.seed, "best_epoch": int(manifest.get("best_epoch", best_epoch)),
                          "best_score": best_score, "selection_margin": margin, "checkpoint_count_evaluated": int(len(history)),
                          "n_checkpoints_within_margin": int((history[score_col].astype(float) >= best_score - margin - 1e-12).sum()),
                          "within_margin_rule": f"{score_col}>=best_score-selection_margin"})
        for split in SPLITS:
            for phase in PHASES:
                prediction = _prediction(run_dir, split, phase)
                y_true = _class_ids(prediction["y_true"], args.task)
                probabilities = prediction[["prob_c0", "prob_c1", "prob_c2"]].to_numpy(dtype=float)
                canonical_row = canonical[(canonical.window_id == window) & (canonical.parent_pipeline == parent) &
                                          (canonical.eval_split == split) & (canonical.phase_id == phase)]
                if len(canonical_row) != 1:
                    raise RuntimeError(f"Missing canonical S_leak for {window}/{parent}/{split}/{phase}")
                leak = canonical_row.iloc[0]
                values = classification_metrics(y_true, probabilities, train_class_counts=train_counts, s_eff=s_eff, s_leak=leak.s_leak)
                s_cal = max(0.0, 1.0 - float(values["ece"]))
                values["s_cal"] = s_cal
                values["s_san_plus_v2"] = float(np.prod(np.clip([
                    values["s_nan"], values["s_maj_jsd"], s_cal, values["s_drift"], values["s_eff"], values["s_leak"]
                ], COMPOSITE_EPS, 1.0)) ** (1 / 6))
                values["acctempo_m3"] = float((max(values["s_perf"], COMPOSITE_EPS) ** .6) *
                                               (max(values["s_san_plus"], COMPOSITE_EPS) ** .4))
                common = {"task": args.task, "feature_regime": REGIMES[args.task], "window_id": window,
                          "pipeline_id": pipeline, "parent_pipeline": parent, "model_name": args.model_name,
                          "seed": args.seed, "eval_split": split, "phase_id": phase,
                          "s_eff_definition_version": "model_input_mask_mean_v1",
                          "s_eff_train_source": "parent_imputation_train_unaugmented",
                          "s_eff_observed_rate": observed_rate, "s_eff_availability_rate": availability_rate,
                          "s_leak_probe_fit_once": True, **leak.to_dict()}
                sanity.append({**common, **values})
                predicted = probabilities.argmax(axis=1)
                for row in per_class_metric_records(y_true, predicted, np.arange(3), CLASSES[args.task], probabilities):
                    per_class.append({**common, **row})
                for row in stratified_bootstrap_per_class_ci(y_true, predicted, np.arange(3), CLASSES[args.task],
                                                              repetitions=args.bootstrap_repetitions, seed=args.seed):
                    bootstrap.append({**common, **row})
                slices.extend(_slice_rows(prediction, task=args.task, window=window, pipeline=pipeline,
                                          model=args.model_name, seed=args.seed, split=split, phase=phase))
    return (pd.DataFrame(sanity), pd.DataFrame(slices), pd.DataFrame(per_class),
            pd.DataFrame(bootstrap), pd.DataFrame(selection))


def main() -> None:
    args = _parse()
    download, _, download_hash = load_download_manifest(args.data_root, task=args.task)
    selected = _selected_runs(args, download)
    root = args.audit_root / args.task / args.model_name / f"seed={args.seed}"
    root.mkdir(parents=True, exist_ok=True)
    canonical = _canonical_s_leak(args, selected)
    sanity, slices, per_class, bootstrap, selection = _run_facts(args, selected, canonical)
    outputs = {
        "canonical_s_leak": canonical, "sanity_components": sanity, "evaluation_slices": slices,
        "metrics_per_class": per_class, "bootstrap_metrics_per_class": bootstrap,
        "checkpoint_selection": selection,
    }
    for name, frame in outputs.items():
        frame.to_parquet(root / f"{name}.parquet", index=False)
    metadata = {
        "audit_schema_version": "vastai_posthoc_audit_v1", "task": args.task,
        "model_name": args.model_name, "seed": args.seed, "release_id": download["release_id"],
        "data_release_id": download["data_release_id"], "input_download_manifest_sha256": download_hash,
        "runs": len(selected), "bootstrap_repetitions": args.bootstrap_repetitions,
        "rows": {name: int(len(frame)) for name, frame in outputs.items()},
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (root / "audit_manifest.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({**metadata, "output": str(root)}, indent=2), flush=True)


if __name__ == "__main__":
    main()
