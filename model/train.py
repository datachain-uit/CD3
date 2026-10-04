"""Train and evaluate one phase-prefix recurrent classifier."""
from __future__ import annotations

import copy
import random
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.amp import GradScaler, autocast
from torch.utils.data import DataLoader

from .architectures import HybridRecurrentClassifier
from .config import ModelConfig
from .data import FeatureLayout, PhaseDataset, transform_frame
from .metrics import classification_metrics


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _loader(dataset: PhaseDataset, config: ModelConfig, *, shuffle: bool) -> DataLoader:
    workers = max(config.num_workers, 0)
    return DataLoader(dataset, batch_size=config.batch_size, shuffle=shuffle,
                      num_workers=workers, pin_memory=torch.cuda.is_available(),
                      persistent_workers=workers > 0)


def _evaluate(model: nn.Module, loader: DataLoader, device: torch.device, labels: np.ndarray):
    model.eval()
    truth, predictions, probabilities = [], [], []
    loss_sum, n_rows = 0.0, 0
    criterion = nn.CrossEntropyLoss()
    amp_device = "cuda" if device.type == "cuda" else "cpu"
    with torch.no_grad():
        for dynamic, static, lengths, target in loader:
            dynamic, static, lengths, target = (dynamic.to(device), static.to(device),
                                                 lengths.to(device), target.to(device))
            with autocast(device_type=amp_device, enabled=device.type == "cuda"):
                logits = model(dynamic, static, lengths)
                loss = criterion(logits.float(), target)
            probabilities.append(torch.softmax(logits.float(), 1).cpu().numpy())
            predictions.append(logits.float().argmax(1).cpu().numpy())
            truth.append(target.cpu().numpy())
            loss_sum += float(loss) * len(target)
            n_rows += len(target)
    y_true, y_pred, y_prob = np.concatenate(truth), np.concatenate(predictions), np.concatenate(probabilities)
    metrics, matrix = classification_metrics(y_true, y_pred, y_prob, labels)
    metrics["loss"] = loss_sum / max(n_rows, 1)
    return metrics, matrix, y_true, y_pred, y_prob


def train_and_evaluate(*, config: ModelConfig, layout: FeatureLayout, classes: tuple[str, ...],
                       train_frame: pd.DataFrame, validation_frame: pd.DataFrame,
                       test_frame: pd.DataFrame, output_dir: str | Path) -> dict:
    """Fit on TRAIN, early-stop on validation, then evaluate one test prefix.

    Validation labels never enter feature fitting. The checkpoint selected by
    validation macro-F1 is evaluated once on test; no test-driven selection.
    """
    config.validate()
    seed_everything(config.seed)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    labels = np.arange(len(classes), dtype=np.int64)
    train_arrays = transform_frame(train_frame, layout, classes=classes, use_masks=config.use_masks)
    val_arrays = transform_frame(validation_frame, layout, classes=classes, use_masks=config.use_masks)
    test_arrays = transform_frame(test_frame, layout, classes=classes, use_masks=config.use_masks)
    train_ds, val_ds, test_ds = (PhaseDataset(*train_arrays), PhaseDataset(*val_arrays), PhaseDataset(*test_arrays))
    train_loader, val_loader, test_loader = (_loader(train_ds, config, shuffle=True),
                                               _loader(val_ds, config, shuffle=False),
                                               _loader(test_ds, config, shuffle=False))
    counts = np.bincount(train_arrays[3], minlength=len(classes))
    # Do not double-correct a synthetic balanced train set. The caller records
    # whether its training artifact is augmented in the manifest.
    class_weight = np.ones(len(classes), dtype="float32") if config.train_is_augmented else np.divide(
        counts.sum(), len(classes) * counts, out=np.zeros(len(classes), dtype="float32"), where=counts > 0,
    ).astype("float32")
    model = HybridRecurrentClassifier(train_arrays[0].shape[2], train_arrays[1].shape[1], len(classes),
                                      config.architecture, config.hidden_size, config.num_layers,
                                      config.dropout).to(device)
    criterion = nn.CrossEntropyLoss(weight=torch.tensor(class_weight, device=device))
    optimizer = torch.optim.AdamW(model.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay)
    scaler = GradScaler("cuda", enabled=device.type == "cuda")
    amp_device = "cuda" if device.type == "cuda" else "cpu"
    best_state, best_epoch, best_f1, stale = None, 0, -np.inf, 0
    epoch_rows = []
    started = time.perf_counter()
    for epoch in range(1, config.max_epochs + 1):
        model.train()
        loss_sum, n_rows = 0.0, 0
        for dynamic, static, lengths, target in train_loader:
            dynamic, static, lengths, target = (dynamic.to(device), static.to(device),
                                                 lengths.to(device), target.to(device))
            optimizer.zero_grad(set_to_none=True)
            with autocast(device_type=amp_device, enabled=device.type == "cuda"):
                logits = model(dynamic, static, lengths)
                loss = criterion(logits.float(), target)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            loss_sum += float(loss.detach()) * len(target)
            n_rows += len(target)
        val_metrics, _, _, _, _ = _evaluate(model, val_loader, device, labels)
        train_loss = loss_sum / max(n_rows, 1)
        epoch_rows.append({"epoch": epoch, "train_loss": train_loss, **{f"validation_{k}": v for k, v in val_metrics.items() if not isinstance(v, list)}})
        if val_metrics["f1_macro"] > best_f1 + 1e-6:
            best_f1, best_epoch, stale = val_metrics["f1_macro"], epoch, 0
            best_state = copy.deepcopy(model.state_dict())
        else:
            stale += 1
            if stale >= config.patience:
                break
    model.load_state_dict(best_state)
    test_started = time.perf_counter()
    val_metrics, val_matrix, val_true, val_pred, val_prob = _evaluate(model, val_loader, device, labels)
    test_metrics, test_matrix, test_true, test_pred, test_prob = _evaluate(model, test_loader, device, labels)
    test_seconds = time.perf_counter() - test_started
    total_seconds = time.perf_counter() - started
    checkpoint = {
        "model_state_dict": model.state_dict(), "classes": classes,
        "layout": layout.as_dict(), "config": config.as_dict(), "best_epoch": best_epoch,
    }
    temp = output / "model.pt.tmp"
    torch.save(checkpoint, temp)
    temp.replace(output / "model.pt")
    pd.DataFrame(epoch_rows).to_csv(output / "training_history.csv", index=False)
    for split, truth, pred, prob, matrix in (("validation", val_true, val_pred, val_prob, val_matrix),
                                             ("test", test_true, test_pred, test_prob, test_matrix)):
        pd.DataFrame({"y_true": truth, "y_pred": pred,
                      **{f"prob_class_{i}": prob[:, i] for i in range(prob.shape[1])}}).to_parquet(
                          output / f"{split}_predictions.parquet", index=False, compression="zstd")
        pd.DataFrame(matrix, index=classes, columns=classes).to_csv(output / f"{split}_confusion_matrix.csv")
    return {
        "task": config.task, "window_id": config.window_id, "phase_id": config.phase_id,
        "architecture": config.architecture, "input_mode": config.input_mode,
        "use_masks": config.use_masks, "best_epoch": best_epoch,
        "train_rows": len(train_ds), "validation_rows": len(val_ds), "test_rows": len(test_ds),
        "class_counts_train": counts.tolist(), "classes": list(classes),
        "validation": val_metrics, "test": test_metrics,
        "time_train_and_validation_s": total_seconds, "time_final_eval_s": test_seconds,
        "device": str(device),
    }
