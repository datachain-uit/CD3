"""Portable VastAI runner for the locked shared-checkpoint temporal protocol.

This intentionally does not import Modal.  It consumes the compact tree made
by ``download_*_vastai_inputs.ps1`` and trains one F1 recurrent architecture
with the same prefix-safe ``model.shared_phase`` implementation as S3.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import torch

SCRIPT_PATH = Path(__file__).resolve()
# Locally this runner lives in ``tools/`` beside ``model/`` at project root;
# the portable upload places both directly in ``/workspace/CD3/code``.
PROJECT_ROOT = next(
    (candidate for candidate in (SCRIPT_PATH.parent, SCRIPT_PATH.parents[1])
     if (candidate / "model").is_dir()),
    None,
)
if PROJECT_ROOT is None:
    raise RuntimeError("Cannot locate sibling model/ package for VastAI runner.")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from model.data import fit_layout
from model.shared_phase import evaluate_test_prefix, train_shared_checkpoint
from vastai_metadata_contract import build_contract, write_contract

try:  # ``resource`` is available in the Linux VastAI container, not Windows.
    import resource
except ModuleNotFoundError:  # pragma: no cover - local CLI/help convenience.
    resource = None


PARENTS = {"V2": "V1", "V3": "V1", "V4": "V1", "V6": "V5", "V7": "V5", "V8": "V5",
           "V10": "V9", "V11": "V9", "V12": "V9", "V14": "V13", "V15": "V13", "V16": "V13"}
CLASSES = {"CQ": ("warning", "average", "good"), "LO": ("I/D", "G", "E")}


def role_seed(master: int, role: str, *, task: str, window: str, pipeline: str, model: str) -> int:
    value = f"{master}|{role}|{task}|{window}|{pipeline}|{model}".encode("utf-8")
    return int(hashlib.sha256(value).hexdigest()[:8], 16) % (2**31 - 1)


def prediction_frame(prediction: dict, source: pd.DataFrame, *, salt: str, common: dict) -> pd.DataFrame:
    ids = source["enrollment_id"].astype("string")
    frame = pd.DataFrame({
        **common,
        "enrollment_id_hash": ids.map(lambda value: hashlib.sha256(f"{salt}|{value}".encode()).hexdigest()),
        "y_true": [f"c{x}" for x in prediction["y_true"]],
        "y_pred": [f"c{x}" for x in prediction["y_pred"]],
    })
    for index in range(prediction["probabilities"].shape[1]):
        frame[f"prob_c{index}"] = prediction["probabilities"][:, index]
    for column in ("offering_id", "timeline_source", "course_id", "context__temporal_strict_P1",
                   "context__temporal_strict_P2", "context__temporal_strict_P3", "context__temporal_strict_P4"):
        if column in source:
            frame[column.removeprefix("context__")] = source[column].to_numpy()
    return frame


def parse() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", choices=("CQ", "LO"), required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--window", choices=("W1", "W2", "W3"), required=True)
    parser.add_argument("--pipeline-id", choices=tuple(f"V{i}" for i in range(17)), required=True)
    parser.add_argument("--model-name", choices=("RNN", "LSTM", "GRU", "BILSTM", "PATCHTST", "MOMENT_SMALL"), required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--batch-size", type=int, default=2048)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--max-epochs", type=int, default=50,
                        help="Epoch cap; use 1 only for environment smoke tests.")
    parser.add_argument("--patience", type=int, default=5,
                        help="Validation early-stopping patience; capped to max_epochs.")
    parser.add_argument("--prediction-salt", default=os.environ.get("TEMPO_PREDICTION_SALT", ""))
    return parser.parse_args()


def main() -> None:
    args = parse()
    if not args.prediction_salt:
        raise ValueError("Set TEMPO_PREDICTION_SALT once for all VastAI comparison runs, or pass --prediction-salt.")
    architecture = args.model_name.lower()
    moment_snapshot = None
    moment_cache_dir = None
    if architecture.startswith("moment_"):
        from model.architectures import prepare_moment_snapshot
        moment_cache_dir = os.environ.get("MOMENT_CACHE_DIR", "/workspace/.cache/moment")
        moment_snapshot = prepare_moment_snapshot(architecture, cache_dir=moment_cache_dir)
    parent = PARENTS.get(args.pipeline_id, args.pipeline_id)
    train_name = "train.parquet" if args.pipeline_id == parent else "balanced_train.parquet"
    train_path = args.data_root / "train" / args.window / args.pipeline_id / train_name
    evaluation = args.data_root / "evaluation" / args.window / parent
    validation_path = evaluation / "validation.parquet"
    test_paths = {phase: evaluation / f"test_{phase}.parquet" for phase in ("P1", "P2", "P3", "P4")}
    missing = [str(path) for path in (train_path, validation_path, *test_paths.values()) if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing downloaded VastAI inputs: {missing}")

    started = time.perf_counter()
    train, validation = pd.read_parquet(train_path), pd.read_parquet(validation_path)
    tests = {phase: pd.read_parquet(path) for phase, path in test_paths.items()}
    classes = CLASSES[args.task]
    label = "CQ_label_final" if args.task == "CQ" else "LO_performance_label_3"
    unseen = set(train[label].astype(str).unique()).difference(classes)
    if unseen:
        raise ValueError(f"Unexpected labels in TRAIN: {sorted(unseen)}")
    layout = fit_layout(train, task=args.task, phase_id="P4", use_masks=True)
    model_seed = role_seed(args.seed, "model", task=args.task, window=args.window,
                           pipeline=args.pipeline_id, model=args.model_name)
    loader_seed = role_seed(args.seed, "dataloader", task=args.task, window=args.window,
                            pipeline=args.pipeline_id, model=args.model_name)
    trained, runtime = train_shared_checkpoint(
        layout=layout, classes=classes, train_frame=train, validation_frame=validation,
        architecture=architecture, seed=model_seed, dataloader_seed=loader_seed,
        batch_size=args.batch_size, workers=args.workers, max_epochs=args.max_epochs,
        patience=min(args.patience, args.max_epochs),
        hidden_size=128, num_layers=1, dropout=0.3, learning_rate=1e-3, weight_decay=1e-5,
        moment_cache_dir=moment_cache_dir, moment_snapshot=(moment_snapshot or {}).get("snapshot"),
    )
    output = args.output_root / args.task / args.window / args.pipeline_id / args.model_name / f"seed={args.seed}"
    output.mkdir(parents=True, exist_ok=True)
    torch.save(trained["checkpoint"], output / "model.pt")
    pd.DataFrame(trained["history"]).to_parquet(output / "train_history.parquet", index=False)
    (output / "feature_layout.json").write_text(json.dumps(layout.as_dict(), indent=2), encoding="utf-8")

    metrics = []
    prediction_root = output / "predictions"
    prediction_root.mkdir(parents=True, exist_ok=True)
    for phase, prediction in trained["validation_predictions"].items():
        common = {"task": args.task, "window_id": args.window, "pipeline_id": args.pipeline_id,
                  "model_name": args.model_name, "seed": args.seed, "eval_split": "VALIDATION", "phase_id": phase}
        prediction_frame(prediction, validation, salt=args.prediction_salt, common=common).to_parquet(
            prediction_root / f"validation_{phase}.parquet", index=False
        )
        metrics.append({**common, **trained["validation_metrics"][phase]})
    for phase, frame in tests.items():
        metric, prediction = evaluate_test_prefix(runtime["model"], frame, layout, classes, phase,
                                                  args.batch_size, args.workers, runtime["device"])
        common = {"task": args.task, "window_id": args.window, "pipeline_id": args.pipeline_id,
                  "model_name": args.model_name, "seed": args.seed, "eval_split": "TEST", "phase_id": phase}
        prediction_frame(prediction, frame, salt=args.prediction_salt, common=common).to_parquet(
            prediction_root / f"test_{phase}.parquet", index=False
        )
        metrics.append({**common, **metric})
    pd.DataFrame(metrics).to_parquet(output / "metrics_overall.parquet", index=False)
    manifest = {
        "runner": "tools/vastai_train_shared.py", "protocol": "shared_checkpoint_prefix_safe_v2_4",
        "task": args.task, "window_id": args.window, "pipeline_id": args.pipeline_id,
        "parent_pipeline": parent, "model_name": args.model_name, "architecture": architecture,
        "seed": args.seed, "seed_model": model_seed, "seed_dataloader": loader_seed,
        "batch_size": args.batch_size, "max_epochs": args.max_epochs,
        "early_stopping_patience": min(args.patience, args.max_epochs),
        "precision_policy": "cuda_bfloat16_logits_loss_float32", "best_epoch": trained["best_epoch"],
        "pretrained_backbone": moment_snapshot,
        "train_rows": len(train), "validation_rows": len(validation),
        "test_rows": {phase: len(frame) for phase, frame in tests.items()},
        "input_paths": {"train": str(train_path), "validation": str(validation_path),
                        **{phase: str(path) for phase, path in test_paths.items()}},
        "elapsed_seconds": time.perf_counter() - started,
        "peak_ram_mb": (resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
                        if resource is not None else None),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (output / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    # A separate, deterministic sidecar preserves complete release lineage without
    # making the execution manifest depend on a local download layout.
    write_contract(build_contract(task=args.task, data_root=args.data_root, run_dir=output,
                                  manifest=manifest, runner_path=SCRIPT_PATH),
                   output / "metadata_contract.json")
    print(json.dumps(manifest, indent=2), flush=True)


if __name__ == "__main__":
    main()
