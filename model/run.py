"""CLI for one leakage-safe CQ/LO recurrent-model experiment.

Example (after the augmentation runner writes its L1 train input)::

  python -m model.run --task CQ --window W1 --phase P2 --architecture gru \
    --train <balanced_train.parquet> --validation <imputed_validation.parquet> \
    --test <imputed_test_P2.parquet> --output-dir outputs/CQ/W1/P2/V2/gru
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import ModelConfig
from .data import fit_layout, label_column, read_parquet
from .train import train_and_evaluate


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--task", choices=("CQ", "LO"), required=True)
    value.add_argument("--window", choices=("W1", "W2", "W3"), required=True)
    value.add_argument("--phase", choices=("P1", "P2", "P3", "P4"), required=True)
    value.add_argument("--architecture", choices=("rnn", "lstm", "gru", "bilstm"), required=True)
    value.add_argument("--train", type=Path, required=True, help="imputed or balanced TRAIN parquet")
    value.add_argument("--validation", type=Path, required=True, help="imputed validation parquet")
    value.add_argument("--test", type=Path, required=True, help="matching imputed test_Pk parquet")
    value.add_argument("--output-dir", type=Path, required=True)
    value.add_argument("--input-mode", choices=("imputed", "v0_mask"), default="imputed")
    value.add_argument("--use-masks", action="store_true")
    value.add_argument("--train-is-augmented", action="store_true")
    value.add_argument("--hidden-size", type=int, default=128)
    value.add_argument("--batch-size", type=int, default=2048)
    value.add_argument("--max-epochs", type=int, default=30)
    value.add_argument("--patience", type=int, default=5)
    value.add_argument("--learning-rate", type=float, default=1e-3)
    value.add_argument("--seed", type=int, default=20260922)
    return value


def main() -> None:
    args = parser().parse_args()
    use_masks = args.use_masks or args.input_mode == "v0_mask"
    config = ModelConfig(task=args.task, window_id=args.window, phase_id=args.phase,
                         architecture=args.architecture, input_mode=args.input_mode,
                         use_masks=use_masks, train_is_augmented=args.train_is_augmented, hidden_size=args.hidden_size,
                         batch_size=args.batch_size, max_epochs=args.max_epochs,
                         patience=args.patience, learning_rate=args.learning_rate,
                         seed=args.seed)
    train, validation, test = read_parquet(args.train), read_parquet(args.validation), read_parquet(args.test)
    label = label_column(args.task)
    classes = tuple(sorted(train[label].astype("string").dropna().unique().tolist()))
    if len(classes) != 3:
        raise ValueError(f"expected three TRAIN labels, got {classes}")
    layout = fit_layout(train, task=args.task, phase_id=args.phase, use_masks=use_masks)
    result = train_and_evaluate(config=config, layout=layout, classes=classes,
                                train_frame=train, validation_frame=validation,
                                test_frame=test, output_dir=args.output_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "run_manifest.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
