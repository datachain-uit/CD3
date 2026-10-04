"""Shared-checkpoint P1--P4 training utilities for the official protocol."""
from __future__ import annotations

import copy
import json
import random
import time
from dataclasses import asdict

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.amp import GradScaler, autocast
from torch.utils.data import DataLoader, Dataset

from .architectures import SharedPhaseHybridRecurrentClassifier
from .data import FeatureLayout, PHASES, transform_frame
from .metrics import calibration_metrics, classification_metrics


def seed_everything(seed: int) -> None:
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    # Determinism is part of the experiment identity.  It is intentionally
    # enabled even though a few CUDA kernels may be slower.
    torch.use_deterministic_algorithms(True, warn_only=True)
    if hasattr(torch.backends, "cudnn"):
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True


class SharedPhaseDataset(Dataset):
    def __init__(self, dynamic: np.ndarray, static: np.ndarray, labels: np.ndarray) -> None:
        # Some pandas/Arrow conversions expose read-only NumPy views. The
        # DataLoader must own writable arrays before PyTorch wraps them.
        self.dynamic = torch.from_numpy(np.array(dynamic, dtype=np.float32, copy=True))
        self.static = torch.from_numpy(np.array(static, dtype=np.float32, copy=True))
        self.labels = torch.from_numpy(np.array(labels, dtype=np.int64, copy=True))
    def __len__(self) -> int: return len(self.labels)
    def __getitem__(self, index: int): return self.dynamic[index], self.static[index], self.labels[index]


def _loader(dataset: Dataset, batch_size: int, shuffle: bool, workers: int, *, seed: int = 0) -> DataLoader:
    generator = torch.Generator()
    generator.manual_seed(seed)
    return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle, num_workers=max(workers, 0),
                      pin_memory=torch.cuda.is_available(), persistent_workers=workers > 0,
                      generator=generator)


def _evaluate_prefixes(model: nn.Module, dynamic: np.ndarray, static: np.ndarray, y: np.ndarray,
                       batch_size: int, workers: int, device: torch.device, class_ids: np.ndarray,
                       *, seed: int = 0) -> tuple[dict, dict]:
    dataset = SharedPhaseDataset(dynamic, static, y)
    loader = _loader(dataset, batch_size, False, workers, seed=seed)
    phases = PHASES[:dynamic.shape[1]]
    all_logits = [[] for _ in phases]
    truth = []
    criterion = nn.CrossEntropyLoss()
    model.eval()
    with torch.no_grad():
        for dx, sx, target in loader:
            dx, sx = dx.to(device), sx.to(device)
            logits = model(dx, sx).float()
            for i in range(len(phases)): all_logits[i].append(logits[:, i].cpu().numpy())
            truth.append(target.numpy())
    y_true = np.concatenate(truth)
    metrics, predictions = {}, {}
    for i, phase in enumerate(phases):
        logit = np.concatenate(all_logits[i]); prob = torch.softmax(torch.from_numpy(logit), 1).numpy(); pred = prob.argmax(1)
        record, matrix = classification_metrics(y_true, pred, prob, class_ids)
        record.update(calibration_metrics(y_true, prob, class_ids)); record["cross_entropy"] = float(criterion(torch.from_numpy(logit), torch.from_numpy(y_true)))
        metrics[phase] = record
        predictions[phase] = {"y_true": y_true, "y_pred": pred, "probabilities": prob, "confusion": matrix}
    return metrics, predictions


def train_shared_checkpoint(*, layout: FeatureLayout, classes: tuple[str, ...], train_frame: pd.DataFrame,
                            validation_frame: pd.DataFrame, architecture: str, seed: int,
                            hidden_size: int = 128, num_layers: int = 1, dropout: float = .3,
                            batch_size: int = 2048, max_epochs: int = 50, patience: int = 5,
                            learning_rate: float = 1e-3, weight_decay: float = 1e-5, workers: int = 4) -> tuple[dict, dict]:
    """Fit a single checkpoint using average CE over P1--P4 real train rows."""
    seed_everything(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    class_ids = np.arange(len(classes), dtype=np.int64)
    train_dynamic, train_static, _, train_y = transform_frame(train_frame, layout, classes=classes, use_masks=True)
    val_dynamic, val_static, _, val_y = transform_frame(validation_frame, layout, classes=classes, use_masks=True)
    train_loader = _loader(SharedPhaseDataset(train_dynamic, train_static, train_y), batch_size, True, workers, seed=seed)
    model = SharedPhaseHybridRecurrentClassifier(train_dynamic.shape[2], train_static.shape[1], len(classes), architecture,
                                                  hidden_size, num_layers, dropout).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=weight_decay)
    scaler = GradScaler("cuda", enabled=device.type == "cuda"); amp_device = "cuda" if device.type == "cuda" else "cpu"
    criterion = nn.CrossEntropyLoss(); best_state = None; best_key = (-np.inf, -np.inf); best_epoch = 0; stale = 0; history = []
    for epoch in range(1, max_epochs + 1):
        epoch_started = time.perf_counter()
        model.train(); total = 0.; rows = 0
        for dx, sx, target in train_loader:
            dx, sx, target = dx.to(device), sx.to(device), target.to(device); optimizer.zero_grad(set_to_none=True)
            # L4 supports bfloat16. Cross-entropy is explicitly computed on
            # logits.float() below, so checkpoint selection remains fp32.
            with autocast(device_type=amp_device, dtype=torch.bfloat16,
                          enabled=device.type == "cuda"):
                logits = model(dx, sx); loss = sum(criterion(logits[:, i].float(), target) for i in range(4)) / 4
            scaler.scale(loss).backward(); scaler.step(optimizer); scaler.update(); total += float(loss.detach()) * len(target); rows += len(target)
        val_metrics, _ = _evaluate_prefixes(model, val_dynamic, val_static, val_y, batch_size, workers, device, class_ids, seed=seed)
        mean_f1 = float(np.mean([val_metrics[p]["f1_macro"] for p in PHASES])); mean_ce = float(np.mean([val_metrics[p]["cross_entropy"] for p in PHASES]))
        history.append({"epoch": epoch, "train_cross_entropy_mean_p1_p4": total / max(rows, 1), "validation_macro_f1_mean_p1_p4": mean_f1, "validation_cross_entropy_mean_p1_p4": mean_ce})
        key = (mean_f1, -mean_ce)
        if key > best_key:
            best_key, best_epoch, stale, best_state = key, epoch, 0, copy.deepcopy(model.state_dict())
        else:
            stale += 1
        print(json.dumps({
            "event": "epoch_complete", "epoch": epoch, "epoch_seconds": round(time.perf_counter() - epoch_started, 3),
            "train_cross_entropy_mean_p1_p4": history[-1]["train_cross_entropy_mean_p1_p4"],
            "validation_macro_f1_mean_p1_p4": mean_f1,
            "validation_cross_entropy_mean_p1_p4": mean_ce,
            "best_epoch": best_epoch, "best_validation_macro_f1_mean_p1_p4": best_key[0],
            "early_stopping_stale_epochs": stale, "early_stopping_patience": patience,
        }, sort_keys=True), flush=True)
        if stale >= patience:
            print(json.dumps({"event": "early_stopping", "epoch": epoch, "best_epoch": best_epoch,
                              "patience": patience}, sort_keys=True), flush=True)
            break
    model.load_state_dict(best_state)
    val_metrics, val_predictions = _evaluate_prefixes(model, val_dynamic, val_static, val_y, batch_size, workers, device, class_ids, seed=seed)
    checkpoint = {"model_state_dict": model.state_dict(), "classes": list(classes), "layout": layout.as_dict(),
                  "architecture": architecture, "best_epoch": best_epoch, "selection_objective": "mean_validation_macro_f1_p1_p4"}
    return {"checkpoint": checkpoint, "history": history, "validation_metrics": val_metrics,
             "validation_predictions": val_predictions, "best_epoch": best_epoch, "device": str(device),
             "train_rows": len(train_y), "validation_rows": len(val_y)}, {"model": model, "device": device}


def evaluate_test_prefix(model: nn.Module, frame: pd.DataFrame, full_layout: FeatureLayout,
                         classes: tuple[str, ...], phase_id: str, batch_size: int = 2048,
                         workers: int = 4, device: torch.device | None = None) -> tuple[dict, dict]:
    """Evaluate only P1..Pk columns; structural future cells are never read."""
    if phase_id not in PHASES:
        raise ValueError("phase_id must be P1-P4")
    layout = FeatureLayout(full_layout.task, phase_id, full_layout.dynamic_bases,
                           full_layout.static_columns, full_layout.mask_dynamic_columns,
                           full_layout.mask_static_columns)
    dynamic, static, _, y = transform_frame(frame, layout, classes=classes, use_masks=True)
    if device is None: device = next(model.parameters()).device
    metrics, predictions = _evaluate_prefixes(model, dynamic, static, y, batch_size, workers, device,
                                               np.arange(len(classes), dtype=np.int64), seed=0)
    return metrics[phase_id], predictions[phase_id]
