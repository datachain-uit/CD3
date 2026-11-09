"""Exploratory Mantis cell (task CQ or LO), with real-parent adapter and compressed cache.

Generic copy of run_mantis_cq_grid_zstd_20261108.py: the task is a parameter (--task CQ|LO). CQ behaviour is unchanged.

Imputer-only parents must complete before their balanced children. This runner
does not claim the full F3/L2 audit contract; output is an exploratory cell.
"""
import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score

try:
    import resource
except ModuleNotFoundError:  # Windows preflight; execution is on Linux/VastAI.
    resource = None

from model.data import fit_layout, transform_frame
from model.energy import GpuPowerSampler
from f3_mantis.determinism import configure_determinism
from f3_mantis.encoder import load_frozen_mantis
from f3_mantis.spec import MANTIS_V2_SPEC
import f3_mantis.cell as cell
from mantis_zstd_dedup_store_20261107 import DedupZstdStore

PARENTS = {"V2": "V1", "V3": "V1", "V4": "V1", "V6": "V5", "V7": "V5", "V8": "V5",
           "V10": "V9", "V11": "V9", "V12": "V9", "V14": "V13", "V15": "V13", "V16": "V13"}
TASK_CLASSES = {"CQ": ("warning", "average", "good"), "LO": ("I/D", "G", "E")}
TASK_RELEASE = {"CQ": ("CQ_V2_2", "sha256:8db2b1d375c9cb7cd91cbccb7907fca51a8ab9bcd748c7bde43e879b1237d045"),
                "LO": ("LO_V3_1", "sha256:2edf8cc293044d29c360cb2db71b8d21e26e2187cf40c6d45266f342a826d35b")}
LABELS = {"CQ": "CQ_label_final", "LO": "LO_performance_label_3"}
CLASSES = TASK_CLASSES["CQ"]  # replaced in main() by the task classes
RELEASE = TASK_RELEASE["CQ"][1]


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def check_prefixes(eval_dir, layout, label_name):
    """Verify P4 values reused for each shorter test prefix, for all rows."""
    root = eval_dir / "test_P4.parquet"
    for prefix in (1, 2, 3):
        columns = ["enrollment_id", label_name, *layout.static_columns, *layout.mask_static_columns]
        for index in range(1, prefix + 1):
            phase = f"P{index}"
            columns += [f"{base}_{phase}" for base in layout.dynamic_bases]
            columns += [c for c in layout.mask_dynamic_columns if c.endswith(f"_{phase}")]
            columns += [f"{base}_{phase}" for base in layout.mask_phase_bases]
        columns = list(dict.fromkeys(columns))
        left = pd.read_parquet(eval_dir / f"test_P{prefix}.parquet", columns=columns)
        right = pd.read_parquet(root, columns=columns)
        # the LO test files of different phases are not row-aligned: compare after sorting by the unique enrollment id
        left = left.sort_values("enrollment_id", kind="stable").reset_index(drop=True)
        right = right.sort_values("enrollment_id", kind="stable").reset_index(drop=True)
        if not left.equals(right):
            mismatched = [name for name in columns if not left[name].equals(right[name])]
            raise ValueError(f"P{prefix}/P4 prefix mismatch: {mismatched}")
        del left, right


def main():
    global CLASSES, RELEASE
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", default="CQ", choices=("CQ", "LO"))
    parser.add_argument("--window", required=True, choices=("W1", "W2", "W3"))
    parser.add_argument("--pipeline", required=True, choices=[f"V{i}" for i in range(0, 17)])
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--smoke-rows", type=int, default=0)
    args = parser.parse_args()
    CLASSES = TASK_CLASSES[args.task]
    RELEASE = TASK_RELEASE[args.task][1]
    release_name = TASK_RELEASE[args.task][0]
    if args.smoke_rows and args.pipeline in PARENTS:
        raise ValueError("Smoke subsets cannot safely reuse parent caches; run a full parent first")
    salt = os.environ.get("TEMPO_PREDICTION_SALT", "")
    if not salt:
        raise ValueError("Set TEMPO_PREDICTION_SALT for cohort-compatible hashed predictions")
    parent = PARENTS.get(args.pipeline, args.pipeline)
    balanced = args.pipeline != parent
    manifest_path = args.data_root / "download_manifest.json"
    release = json.loads(manifest_path.read_text(encoding="utf-8"))
    if release.get("release_id") != release_name or release.get("data_release_id") != RELEASE:
        raise ValueError(f"Unexpected {args.task} release identity")
    train_path = args.data_root / "train" / args.window / args.pipeline / ("balanced_train.parquet" if balanced else "train.parquet")
    eval_dir = args.data_root / "evaluation" / args.window / parent
    paths = {"train": train_path, "validation": eval_dir / "validation.parquet", "test": eval_dir / "test_P4.parquet"}
    for path in [*paths.values(), *(eval_dir / f"test_P{i}.parquet" for i in (1, 2, 3))]:
        if not path.is_file():
            raise FileNotFoundError(path)
    output = args.work_root / ("smoke" if args.smoke_rows else "runs") / args.window / args.pipeline
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite {output}")
    cache_root = args.work_root / ("smoke_cache" if args.smoke_rows else "cache")
    output.mkdir(parents=True)
    hashes = {key: sha(path) for key, path in paths.items()}
    hashes.update({f"test_P{i}": sha(eval_dir / f"test_P{i}.parquet") for i in (1, 2, 3)})
    frame = pd.read_parquet(train_path)
    if args.smoke_rows:
        frame = frame.head(args.smoke_rows).copy()
    if frame.enrollment_id.isna().any() or frame.enrollment_id.duplicated().any():
        raise ValueError("TRAIN IDs must be non-null and unique")
    layout = fit_layout(frame, task=args.task, phase_id="P4", use_masks=True)
    names = (list(layout.dynamic_bases) +
             [f"missing__{base}" for base in layout.dynamic_bases if f"missing__{base}_P1" in frame.columns] +
             list(layout.mask_phase_bases) + ["phase_fraction", "delta_t"])
    if balanced:
        if "synthetic_id" not in frame:
            raise ValueError("Balanced input is missing synthetic_id")
        synth = frame.synthetic_id.notna().to_numpy()
        if not synth.any() or not (~synth).any():
            raise ValueError("Balanced input must contain both real and synthetic TRAIN rows")
        if not frame.loc[synth, "synthetic_id"].astype(str).equals(frame.loc[synth, "enrollment_id"].astype(str)):
            raise ValueError("Synthetic IDs and enrollment IDs disagree")
    else:
        synth = np.zeros(len(frame), dtype=bool)

    def prepare(df):
        x, static, _, y = transform_frame(df, layout, classes=CLASSES, use_masks=True)
        if x.shape[-1] != len(names):
            raise ValueError("Channel layout mismatch")
        return {"dynamic": x, "static": static, "y": y,
                "row_ids": df.enrollment_id.astype(str).to_numpy(), "channel_names": names}

    train = prepare(frame)
    train["is_synthetic"] = synth
    del frame
    check_prefixes(eval_dir, layout, LABELS[args.task])
    eval_data, contexts = {}, {}
    for name in ("validation", "test"):
        frame = pd.read_parquet(paths[name])
        if args.smoke_rows:
            frame = frame.head(args.smoke_rows).copy()
        if frame.enrollment_id.isna().any() or frame.enrollment_id.duplicated().any():
            raise ValueError(f"{name} IDs must be non-null and unique")
        eval_data[name] = prepare(frame)
        keep = [c for c in ("enrollment_id", "offering_id", "timeline_source", "course_id",
                            "context__temporal_strict_P1", "context__temporal_strict_P2",
                            "context__temporal_strict_P3", "context__temporal_strict_P4") if c in frame.columns]
        contexts[name] = frame[keep].copy()
        del frame

    pin_path = args.work_root / "backbone_pin.json"
    if not pin_path.is_file():
        raise FileNotFoundError("Pinned backbone manifest required: " + str(pin_path))
    pin = json.loads(pin_path.read_text(encoding="utf-8"))
    configure_determinism(args.seed)
    backbone = load_frozen_mantis(device="cuda", snapshot_dir=pin["snapshot_dir"])
    cell.EmbeddingStore = DedupZstdStore
    original = cell.train_probe

    def logged(*pos, **kwargs):
        kwargs["log"] = lambda row: print(json.dumps({"event": "epoch_complete", "window": args.window,
                                                      "pipeline": args.pipeline, **row}), flush=True)
        return original(*pos, **kwargs)
    cell.train_probe = logged
    spec = json.loads(json.dumps(MANTIS_V2_SPEC))
    if args.smoke_rows:
        spec["training"]["max_epochs"] = 1
        spec["training"]["early_stopping_patience"] = 1
    torch.cuda.reset_peak_memory_stats()
    timer = time.monotonic()
    energy = GpuPowerSampler(interval_seconds=1).start()
    print(json.dumps({"event": "cell_started", "pipeline": args.pipeline, "window": args.window,
                      "parent": parent, "real": int((~synth).sum()), "synthetic": int(synth.sum())}), flush=True)
    result = cell.run_cell(task=args.task, window=args.window, pipeline=args.pipeline, imputer=parent,
                           seed=args.seed, num_classes=3, train=train, validation=eval_data["validation"],
                           test=eval_data["test"], backbone=backbone, store_root=str(cache_root),
                           out_dir=str(output / "result"), device="cuda", backbone_pin=pin, spec=spec,
                           microbatch_sequences=4096, precision="bf16")
    metrics = []
    pred_dir = output / "predictions"
    pred_dir.mkdir()
    for split in ("validation", "test"):
        probabilities, y, context = result[split + "_probabilities"], eval_data[split]["y"], contexts[split]
        ids = context.enrollment_id.astype(str).map(lambda value: hashlib.sha256(f"{salt}|{value}".encode()).hexdigest())
        for index in range(4):
            pred = probabilities[:, index].argmax(axis=1)
            common = {"task": args.task, "window_id": args.window, "pipeline_id": args.pipeline,
                      "model_name": "MANTIS_V2", "seed": args.seed, "eval_split": split.upper(), "phase_id": f"P{index+1}"}
            out = pd.DataFrame({**common, "enrollment_id_hash": ids, "y_true": [f"c{x}" for x in y],
                                "y_pred": [f"c{x}" for x in pred],
                                **{f"prob_c{i}": probabilities[:, index, i] for i in range(3)}})
            for col in context.columns:
                if col != "enrollment_id":
                    out[col.removeprefix("context__")] = context[col].to_numpy()
            out.to_parquet(pred_dir / f"{split}_P{index+1}.parquet", index=False)
            metrics.append({**common, "n_eval_samples": len(y), "accuracy": accuracy_score(y, pred),
                            "balanced_acc": balanced_accuracy_score(y, pred),
                            "macro_f1": f1_score(y, pred, labels=[0, 1, 2], average="macro", zero_division=0)})
    pd.DataFrame(metrics).to_parquet(output / "metrics_overall.parquet", index=False)
    metadata = {"task": args.task, "window": args.window, "pipeline": args.pipeline, "parent": parent,
                "seed": args.seed, "release_id": release["release_id"], "data_release_id": RELEASE,
                "input_sha256": hashes, "download_manifest_sha256": sha(manifest_path),
                "cache_format": "deduplicated_zstd_rows_v1", "test_prefix_full_parity": "PASS",
                "run_purpose": "EXPLORATORY_CACHE_VALIDATION", "cache_reuse": result["record"]["cache_reuse"],
                "cache_mode": result["record"]["cache_mode"], "epochs_trained": result["record"]["epochs_trained"],
                "elapsed_seconds": time.monotonic() - timer, "peak_cuda_allocated_bytes": torch.cuda.max_memory_allocated(),
                "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss if resource else None, "gpu_energy": energy.stop(),
                "limitations": "Exploratory cell; complete post-hoc sanity/bootstrap/L2 ingest not yet produced."}
    (output / "run_manifest.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    (output / "COMPLETE").write_text("complete\n", encoding="utf-8")
    print(json.dumps({"event": "cell_complete", **metadata}), flush=True)


if __name__ == "__main__":
    main()
