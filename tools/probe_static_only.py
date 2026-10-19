#!/usr/bin/env python3
"""Static-only probe: how much label information do the static inputs alone carry, split by split?

Diagnostic (2) of the LO W1 VALIDATION-vs-TEST question (review 2026-10-17, POST_MATERIALIZE_CHECKS[15]).
A multinomial logistic regression is fit on TRAIN using only the static columns that ``model.data.fit_layout``
would feed to the model (no dynamic P1-P4 features), then scored on VALIDATION and TEST.  Three feature sets are
probed: ALL_STATIC (what the model sees in its static branch), COURSE_FINGERPRINT (the COURSE-grain fields of
LO.registries.STATIC_FEATURE_CONTRACT) and NON_COURSE (the rest).  Each is fit twice, unweighted and with
class_weight="balanced", because a 0.3% minority is never predicted by an unweighted probe.

The probe can indicate whether static features carry predictive signal across splits, but does not establish
the cause of a validation-test gap or rule out other explanations.  It is read-only.

Usage::

    python tools/probe_static_only.py --task LO --train <W1 train.parquet> --validation <W1 validation.parquet> \
        --test <W1 TEST P1 prefix view or evaluation parquet> --out probe_static_only_W1.json [--sample-rows 400000]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from model.data import fit_layout, label_column  # noqa: E402

CLASSES = {"CQ": ("warning", "average", "good"), "LO": ("I/D", "G", "E")}


def course_fingerprint_fields(task: str) -> list[str]:
    if task == "CQ":
        from CQ.registries import STATIC_FEATURE_CONTRACT
    elif task == "LO":
        from LO.registries import STATIC_FEATURE_CONTRACT
    else:
        raise ValueError(f"Unsupported task: {task}")
    return list(STATIC_FEATURE_CONTRACT["course_fingerprint_fields"])


def static_columns_for(train: pd.DataFrame, task: str, layout_path: Path | None) -> list[str]:
    if layout_path is not None:
        layout = json.loads(layout_path.read_text(encoding="utf-8"))
        return [c for c in layout["static_columns"] if c in train.columns]
    try:
        return list(fit_layout(train, task=task, phase_id="P4", use_masks=True).static_columns)
    except ValueError:
        return list(fit_layout(train, task=task, phase_id="P4", use_masks=False).static_columns)


def _matrix(frame: pd.DataFrame, columns: list[str]) -> np.ndarray:
    values = frame.loc[:, columns].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    return np.where(np.isfinite(values), values, np.nan)


def _scores(y_true: np.ndarray, y_pred: np.ndarray, proba: np.ndarray, classes: tuple[str, ...]) -> dict[str, Any]:
    from sklearn.metrics import balanced_accuracy_score, f1_score, log_loss, precision_recall_fscore_support
    labels = list(range(len(classes)))
    precision, recall, f1, support = precision_recall_fscore_support(y_true, y_pred, labels=labels, zero_division=0)
    present = sorted(set(y_true.tolist()).union(y_pred.tolist()))
    return {
        "n_rows": int(len(y_true)),
        "macro_f1": float(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)),
        "macro_f1_present_classes": float(f1_score(y_true, y_pred, labels=present, average="macro", zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "log_loss": float(log_loss(y_true, proba, labels=labels)),
        "per_class": {classes[k]: {"support": int(support[k]), "predicted": int((y_pred == k).sum()),
                                   "precision": float(precision[k]), "recall": float(recall[k]), "f1": float(f1[k])}
                      for k in labels},
    }


def majority_reference(y_true: np.ndarray, classes: tuple[str, ...]) -> dict[str, Any]:
    counts = np.bincount(y_true, minlength=len(classes)).astype(float)
    share = counts / counts.sum()
    majority = int(share.argmax())
    f1_majority = 2 * share[majority] / (1 + share[majority])
    return {"class_shares": {classes[k]: float(share[k]) for k in range(len(classes))},
            "macro_f1": float(f1_majority / len(classes)), "balanced_accuracy": float(1 / len(classes)),
            "log_loss_prior": float(-(share[share > 0] * np.log(share[share > 0])).sum())}


def probe(train: pd.DataFrame, evals: dict[str, pd.DataFrame], task: str, columns: list[str], *, seed: int = 42,
          max_iter: int = 500) -> dict[str, Any]:
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    classes = CLASSES[task]
    label = label_column(task)
    mapping = {name: index for index, name in enumerate(classes)}
    y_train = train[label].astype(str).map(mapping)
    if y_train.isna().any():
        raise ValueError(f"TRAIN labels outside {classes}: {sorted(set(train[label].astype(str)) - set(classes))}")
    x_train = _matrix(train, columns)
    out: dict[str, Any] = {"columns": columns, "n_columns": len(columns), "n_train": int(len(train))}
    for weighting in ("none", "balanced"):
        model = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                              LogisticRegression(C=1.0, max_iter=max_iter, random_state=seed,
                                                 class_weight=None if weighting == "none" else "balanced"))
        model.fit(x_train, y_train.to_numpy())
        results = {}
        for split_name, frame in evals.items():
            y_true = frame[label].astype(str).map(mapping)
            if y_true.isna().any():
                raise ValueError(f"{split_name} labels outside {classes}")
            proba = model.predict_proba(_matrix(frame, columns))
            full = np.zeros((len(frame), len(classes)))
            full[:, model.classes_] = proba
            y_pred = full.argmax(axis=1)
            results[split_name] = _scores(y_true.to_numpy(), y_pred, np.clip(full, 1e-12, 1), classes)
        out[f"class_weight_{weighting}"] = results
    return out


def run(train: pd.DataFrame, evals: dict[str, pd.DataFrame], task: str, layout_path: Path | None = None,
        seed: int = 42) -> dict[str, Any]:
    classes = CLASSES[task]
    label = label_column(task)
    all_static = static_columns_for(train, task, layout_path)
    fingerprint = [c for c in course_fingerprint_fields(task) if c in all_static]
    non_course = [c for c in all_static if c not in fingerprint]
    feature_sets = {"ALL_STATIC": all_static, "COURSE_FINGERPRINT": fingerprint, "NON_COURSE": non_course}
    report: dict[str, Any] = {
        "task": task, "label": label, "seed": seed, "probe": "multinomial_logistic_regression_C1_median_impute_standardise",
        "majority_reference": {name: majority_reference(frame[label].astype(str).map({c: i for i, c in enumerate(classes)}).to_numpy(),
                                                       classes) for name, frame in {"TRAIN": train, **evals}.items()},
        "feature_sets": {},
    }
    for name, columns in feature_sets.items():
        report["feature_sets"][name] = probe(train, evals, task, columns, seed=seed) if columns else {"columns": [], "skipped": "empty set"}
    return report


def summary_table(report: dict[str, Any]) -> str:
    lines = ["| feature set | weighting | split | macro-F1 (K=3) | macro-F1 (present) | balanced acc. | log-loss | minority recall |",
             "|---|---|---|---|---|---|---|---|"]
    classes = CLASSES[report["task"]]
    for name, block in report["feature_sets"].items():
        if "skipped" in block:
            continue
        for weighting in ("none", "balanced"):
            for split, scores in block[f"class_weight_{weighting}"].items():
                minority = ", ".join(f"{c}={scores['per_class'][c]['recall']:.2f}" for c in classes[1:])
                lines.append(f"| {name} | {weighting} | {split} | {scores['macro_f1']:.4f} | {scores['macro_f1_present_classes']:.4f} | "
                             f"{scores['balanced_accuracy']:.4f} | {scores['log_loss']:.4f} | {minority} |")
    return "\n".join(lines)


def _read(path: str, sample_rows: int | None, seed: int) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    if sample_rows and len(frame) > sample_rows:
        frame = frame.sample(n=sample_rows, random_state=seed)
    return frame


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--task", required=True, choices=("CQ", "LO"))
    parser.add_argument("--train", required=True)
    parser.add_argument("--validation", required=True)
    parser.add_argument("--test", required=True, help="TEST frame with the label (P1 prefix view or evaluation parquet)")
    parser.add_argument("--layout", type=Path, default=None, help="feature_layout.json of a completed run (optional)")
    parser.add_argument("--sample-rows", type=int, default=None, help="random TRAIN sample (evaluation splits are never sampled)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default="probe_static_only.json")
    args = parser.parse_args(argv)
    train = _read(args.train, args.sample_rows, args.seed)
    evals = {"VALIDATION": pd.read_parquet(args.validation), "TEST": pd.read_parquet(args.test)}
    report = run(train, evals, args.task, args.layout, args.seed)
    report["inputs"] = {"train": args.train, "validation": args.validation, "test": args.test,
                        "layout": str(args.layout) if args.layout else None, "sample_rows": args.sample_rows}
    Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(summary_table(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
