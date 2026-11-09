# -*- coding: utf-8 -*-
"""Shared-phase linear probe of tier F3 on cached MantisV2 features.

The training rule mirrors ``model.shared_phase.train_shared_checkpoint`` of CD3: one head per cell for P1..P4,
loss = mean over the four phases of the cross-entropy, AdamW (lr 1e-3, weight decay 1e-5), batch 2048, at most
50 epochs, patience 5, checkpoint selected on VALIDATION by the mean macro-F1 over P1..P4 with the mean
cross-entropy as tie-break, class weighting NONE. Only the head is trained; the backbone never runs here.
"""
from __future__ import annotations

import copy
import time
from typing import Optional, Sequence

import numpy as np
import torch
from torch import nn

from .determinism import configure_determinism
from .metrics import cross_entropy_from_logits, macro_f1
from .spec import MANTIS_V2_SPEC, N_PHASES

_STAT_BLOCK = 16384


def _streaming_mean_std(features, n_rows: int, block: int = _STAT_BLOCK, floor: float = 1e-6):
    """Per-dimension mean and population std over rows x prefixes, float64 accumulation."""
    first = np.asarray(features[np.arange(min(1, n_rows))], dtype=np.float64)
    dim = first.shape[-1]
    total = np.zeros(dim, dtype=np.float64)
    total_sq = np.zeros(dim, dtype=np.float64)
    count = 0
    for start in range(0, n_rows, block):
        idx = np.arange(start, min(start + block, n_rows))
        x = np.asarray(features[idx], dtype=np.float64).reshape(-1, dim)
        total += x.sum(axis=0)
        total_sq += np.square(x).sum(axis=0)
        count += x.shape[0]
    mean = total / count
    var = np.clip(total_sq / count - np.square(mean), 0.0, None)
    std = np.sqrt(var)
    std = np.where(std > floor, std, 1.0)
    return mean.astype(np.float32), std.astype(np.float32)


class SharedPhaseLinearProbe(nn.Module):
    """Linear head on [standardised embedding of prefix k ; standardised static block ; one-hot of k]."""

    def __init__(self, embedding_dim: int, static_dim: int, num_classes: int, dropout: float = 0.3,
                 n_phases: int = N_PHASES):
        super().__init__()
        self.embedding_dim, self.static_dim, self.n_phases = int(embedding_dim), int(static_dim), int(n_phases)
        self.register_buffer("emb_mean", torch.zeros(self.embedding_dim))
        self.register_buffer("emb_scale", torch.ones(self.embedding_dim))
        self.register_buffer("static_mean", torch.zeros(self.static_dim))
        self.register_buffer("static_scale", torch.ones(self.static_dim))
        self.register_buffer("phase_eye", torch.eye(self.n_phases))
        self.head = nn.Sequential(nn.Dropout(dropout),
                                  nn.Linear(self.embedding_dim + self.static_dim + self.n_phases, num_classes))

    def set_standardisation(self, emb_mean, emb_scale, static_mean, static_scale) -> None:
        for name, value in (("emb_mean", emb_mean), ("emb_scale", emb_scale),
                            ("static_mean", static_mean), ("static_scale", static_scale)):
            getattr(self, name).copy_(torch.as_tensor(value, dtype=torch.float32))

    def forward(self, z: torch.Tensor, static: torch.Tensor, phase_index: Optional[Sequence[int]] = None) -> torch.Tensor:
        """z: (B, P, D) cached features of P prefixes; static: (B, S); phase_index: phases of the P slots (0-based)."""
        batch, n_slots, _ = z.shape
        if phase_index is None:
            phase_index = list(range(n_slots))
        if len(phase_index) != n_slots:
            raise ValueError("phase_index must list one phase per cached slot")
        zt = (z.float() - self.emb_mean) / self.emb_scale
        st = ((static.float() - self.static_mean) / self.static_scale).unsqueeze(1).expand(-1, n_slots, -1)
        onehot = self.phase_eye[torch.as_tensor(list(phase_index), device=z.device)].unsqueeze(0).expand(batch, -1, -1)
        return self.head(torch.cat((zt, st, onehot), dim=2))


def _batches(n_rows: int, batch_size: int, generator: Optional[torch.Generator]):
    order = torch.randperm(n_rows, generator=generator).numpy() if generator is not None else np.arange(n_rows)
    for start in range(0, n_rows, batch_size):
        yield np.sort(order[start:start + batch_size])


@torch.no_grad()
def predict_logits(model: SharedPhaseLinearProbe, features, static: np.ndarray, batch_size: int = 8192,
                   phase_index: Optional[Sequence[int]] = None, device: str = "cpu") -> np.ndarray:
    model.eval()
    n_rows = len(features)
    outputs = []
    for start in range(0, n_rows, batch_size):
        idx = np.arange(start, min(start + batch_size, n_rows))
        z = torch.from_numpy(np.asarray(features[idx], dtype=np.float32)).to(device)
        s = torch.from_numpy(np.asarray(static[idx], dtype=np.float32)).to(device)
        outputs.append(model(z, s, phase_index).float().cpu().numpy())
    return np.concatenate(outputs, axis=0)


def predict_probe(model: SharedPhaseLinearProbe, features, static: np.ndarray, batch_size: int = 8192,
                  phase_index: Optional[Sequence[int]] = None, device: str = "cpu") -> np.ndarray:
    """Class probabilities (rows, prefixes, classes) in float32."""
    logits = predict_logits(model, features, static, batch_size, phase_index, device)
    logits = logits - logits.max(axis=-1, keepdims=True)
    probs = np.exp(logits)
    return (probs / probs.sum(axis=-1, keepdims=True)).astype(np.float32)


def evaluate_phases(model, features, static, y, num_classes: int, device: str = "cpu", batch_size: int = 8192) -> dict:
    logits = predict_logits(model, features, static, batch_size, None, device)
    metrics = {}
    for p in range(logits.shape[1]):
        pred = logits[:, p].argmax(axis=1)
        metrics[f"P{p + 1}"] = {"f1_macro": macro_f1(y, pred, num_classes),
                                "cross_entropy": cross_entropy_from_logits(logits[:, p], y)}
    return metrics


def train_probe(train_features, train_static: np.ndarray, train_y: np.ndarray,
                val_features, val_static: np.ndarray, val_y: np.ndarray, *, num_classes: int, seed: int,
                dataloader_seed: Optional[int] = None, spec: dict = MANTIS_V2_SPEC, device: str = "cpu",
                strict_determinism: bool = True, log=None) -> dict:
    """Train the shared-phase head; returns the selected model, history and selection record."""
    hp = spec["training"]
    configure_determinism(seed, strict=strict_determinism)
    dev = torch.device(device)
    n_train = len(train_features)
    if n_train != len(train_y) or n_train != len(train_static):
        raise ValueError("TRAIN features, static block and labels disagree on the number of rows")
    if tuple(train_features.shape[1:2]) != (N_PHASES,) or tuple(val_features.shape[1:2]) != (N_PHASES,):
        raise ValueError("cached features must hold the four prefixes P1..P4")
    emb_mean, emb_scale = _streaming_mean_std(train_features, n_train)
    static_arr = np.asarray(train_static, dtype=np.float64)
    static_mean = static_arr.mean(axis=0).astype(np.float32)
    static_std = static_arr.std(axis=0)
    static_scale = np.where(static_std > 1e-6, static_std, 1.0).astype(np.float32)
    model = SharedPhaseLinearProbe(train_features.shape[-1], train_static.shape[1], num_classes,
                                   dropout=float(hp["dropout"])).to(dev)
    model.set_standardisation(emb_mean, emb_scale, static_mean, static_scale)
    optimizer = torch.optim.AdamW(model.head.parameters(), lr=float(hp["lr"]), weight_decay=float(hp["weight_decay"]))
    criterion = nn.CrossEntropyLoss()
    generator = torch.Generator().manual_seed(int(seed if dataloader_seed is None else dataloader_seed))
    y_train = torch.as_tensor(np.asarray(train_y, dtype=np.int64))
    best_key, best_state, best_epoch, stale, history = (-np.inf, -np.inf), None, 0, 0, []
    for epoch in range(1, int(hp["max_epochs"]) + 1):
        started = time.perf_counter()
        model.train()
        total, rows = 0.0, 0
        for idx in _batches(n_train, int(hp["batch_size"]), generator):
            z = torch.from_numpy(np.asarray(train_features[idx], dtype=np.float32)).to(dev)
            s = torch.from_numpy(np.asarray(train_static[idx], dtype=np.float32)).to(dev)
            target = y_train[idx].to(dev)
            logits = model(z, s)
            loss = sum(criterion(logits[:, i], target) for i in range(logits.size(1))) / logits.size(1)
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()
            total += float(loss.detach()) * len(idx)
            rows += len(idx)
        train_seconds = time.perf_counter() - started
        val_metrics = evaluate_phases(model, val_features, val_static, val_y, num_classes, device)
        mean_f1 = float(np.mean([val_metrics[f"P{p}"]["f1_macro"] for p in range(1, N_PHASES + 1)]))
        mean_ce = float(np.mean([val_metrics[f"P{p}"]["cross_entropy"] for p in range(1, N_PHASES + 1)]))
        history.append({"epoch": epoch, "train_cross_entropy_mean_p1_p4": total / max(rows, 1),
                        "validation_macro_f1_mean_p1_p4": mean_f1, "validation_cross_entropy_mean_p1_p4": mean_ce,
                        "train_seconds": round(train_seconds, 3),
                        "epoch_seconds": round(time.perf_counter() - started, 3)})
        if log:
            log(history[-1])
        key = (mean_f1, -mean_ce)
        if key > best_key:
            best_key, best_epoch, stale = key, epoch, 0
            best_state = copy.deepcopy(model.state_dict())
        else:
            stale += 1
            if stale >= int(hp["early_stopping_patience"]):
                break
    model.load_state_dict(best_state)
    val_metrics = evaluate_phases(model, val_features, val_static, val_y, num_classes, device)
    return {"model": model, "history": history, "best_epoch": best_epoch,
            "selection_key": {"validation_macro_f1_mean_p1_p4": best_key[0],
                              "validation_cross_entropy_mean_p1_p4": -best_key[1]},
            "validation_metrics": val_metrics, "train_rows": n_train, "validation_rows": len(val_y),
            "trainable_parameters": int(sum(p.numel() for p in model.head.parameters())),
            "epochs_trained": len(history), "early_stopped": len(history) < int(hp["max_epochs"])}


def save_probe(result: dict, path, adapter_digest: str, extra: Optional[dict] = None) -> None:
    """Checkpoint = head state (with standardisation buffers) + identity; the backbone is never checkpointed."""
    model = result["model"]
    torch.save({"state_dict": model.state_dict(), "embedding_dim": model.embedding_dim, "static_dim": model.static_dim,
                "num_classes": model.head[1].out_features, "best_epoch": result["best_epoch"],
                "selection_key": result["selection_key"], "adapter_digest": adapter_digest,
                "model_revision": MANTIS_V2_SPEC["model_revision"], "extra": extra or {}}, path)


def load_probe(path, device: str = "cpu", dropout: float = 0.3) -> SharedPhaseLinearProbe:
    payload = torch.load(path, map_location=device, weights_only=False)
    model = SharedPhaseLinearProbe(payload["embedding_dim"], payload["static_dim"], payload["num_classes"], dropout)
    model.load_state_dict(payload["state_dict"])
    return model.to(device).eval()
