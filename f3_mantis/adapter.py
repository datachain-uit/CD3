# -*- coding: utf-8 -*-
"""Channel adapter of tier F3: PCA across channels, fitted on the real TRAIN rows of a cell.

MantisV2 encodes every channel as an independent univariate series, so the backbone cost grows linearly with the
channel count (CQ: 274 dynamic channels). The Mantis authors recommend a PCA projection across channels before the
encoder when the channel count is large (``mantis.adapters.MultichannelProjector(base_projector='pca')``). This
module implements the same projection deterministically: every phase step of a row is one C-dimensional vector,
the vectors of the selected TRAIN rows are standardised channel by channel, and the leading eigenvectors of their
covariance define the components. The projection acts on each phase step separately, so a prefix P1..Pk is mapped
from its own steps only (prefix safety is preserved).

Only real TRAIN rows enter the fit (synthetic rows of a balancer are excluded), so the adapter depends on the
window and the imputer of the cell but not on the balancer or on the master seed. The sample of rows is drawn with
the registered preprocessing seed (20260922), as for the MICE fit sample. When row ids are given (``run_cell`` always
gives them), the rows are sorted by id before the sample is drawn and before the float64 sums are accumulated, so the
fit depends on the set of (id, values) and not on the order of the frame. The sha256 of the rows used for the fit can
be stored with the adapter (``fit_rows_sha256_``) so that a later cell can verify that it was fitted on its own rows.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Sequence

import numpy as np
import torch

_CHUNK_ROWS = 65536


@dataclass
class ChannelPCAAdapter:
    n_components: int = 8
    standardize: bool = True
    sample_rows_max: int = 1_000_000
    sample_seed: int = 20260922
    zero_variance_scale: float = 1.0
    # fitted state
    mean_: Optional[np.ndarray] = field(default=None, repr=False)
    scale_: Optional[np.ndarray] = field(default=None, repr=False)
    components_: Optional[np.ndarray] = field(default=None, repr=False)   # (C, q) loadings
    explained_variance_: Optional[np.ndarray] = field(default=None, repr=False)
    explained_variance_ratio_: Optional[np.ndarray] = field(default=None, repr=False)
    n_channels_: int = 0
    n_rows_fit_: int = 0
    n_vectors_fit_: int = 0
    channel_names_: Optional[tuple] = None
    fit_order_: str = "position"
    fit_rows_sha256_: Optional[str] = None

    # ------------------------------------------------------------------ fit
    def fit(self, dynamic: np.ndarray, real_mask: Optional[np.ndarray] = None,
            channel_names: Optional[Sequence[str]] = None, row_ids: Optional[Sequence] = None,
            rows_digest: Optional[str] = None) -> "ChannelPCAAdapter":
        """Fit on ``dynamic`` of shape (n_rows, n_steps, n_channels); ``real_mask`` marks real (non-synthetic) rows.

        ``row_ids`` (one per row of ``dynamic``) makes the fit independent of the row order; ``rows_digest`` is the
        sha256 of the real rows (``store.input_sha256``), kept as metadata for later verification.
        """
        if dynamic.ndim != 3:
            raise ValueError("dynamic must be (rows, steps, channels)")
        n_rows, n_steps, n_channels = dynamic.shape
        if self.n_components < 1 or self.n_components > n_channels:
            raise ValueError(f"n_components must be in [1, {n_channels}]")
        if channel_names is not None and len(channel_names) != n_channels:
            raise ValueError("channel_names must list one name per channel of the tensor")
        rows = np.arange(n_rows) if real_mask is None else np.flatnonzero(np.asarray(real_mask, dtype=bool))
        if rows.size == 0:
            raise ValueError("no real TRAIN row to fit the channel adapter")
        if row_ids is not None:
            ids = np.asarray(row_ids)
            if len(ids) != n_rows:
                raise ValueError("row_ids must give one id per row of the tensor")
            rows = rows[np.argsort(ids[rows].astype(str), kind="stable")]       # canonical order: by row id
            self.fit_order_ = "row_id"
        else:
            self.fit_order_ = "position"
        if rows.size > self.sample_rows_max:
            rng = np.random.default_rng(self.sample_seed)
            rows = rows[np.sort(rng.choice(rows.size, size=self.sample_rows_max, replace=False))]
        # pass 1: mean of every channel over all selected (row, step) vectors, float64
        total = np.zeros(n_channels, dtype=np.float64)
        count = 0
        for block in self._row_blocks(rows):
            x = np.asarray(dynamic[block], dtype=np.float64).reshape(-1, n_channels)
            if not np.isfinite(x).all():
                raise ValueError("non-finite value in the TRAIN tensor given to the channel adapter")
            total += x.sum(axis=0)
            count += x.shape[0]
        mean = total / count
        # pass 2: centred second moments (covariance of raw channels), float64
        second = np.zeros((n_channels, n_channels), dtype=np.float64)
        for block in self._row_blocks(rows):
            x = np.asarray(dynamic[block], dtype=np.float64).reshape(-1, n_channels) - mean
            second += x.T @ x
        cov = second / max(count - 1, 1)
        std = np.sqrt(np.clip(np.diag(cov), 0.0, None))
        if self.standardize:
            scale = np.where(std > 1e-12, std, self.zero_variance_scale)
        else:
            scale = np.ones(n_channels, dtype=np.float64)
        corr = cov / np.outer(scale, scale)
        corr = 0.5 * (corr + corr.T)
        eigval, eigvec = np.linalg.eigh(corr)            # ascending
        order = np.argsort(-eigval, kind="stable")[: self.n_components]
        eigval, eigvec = eigval[order], eigvec[:, order]
        # sign rule: the largest absolute loading of each component is positive (ties -> lowest index)
        for j in range(eigvec.shape[1]):
            i = int(np.argmax(np.abs(eigvec[:, j])))
            if eigvec[i, j] < 0:
                eigvec[:, j] = -eigvec[:, j]
        total_var = float(np.clip(np.trace(corr), 1e-300, None))
        self.mean_, self.scale_, self.components_ = mean, scale, eigvec
        self.explained_variance_ = np.clip(eigval, 0.0, None)
        self.explained_variance_ratio_ = self.explained_variance_ / total_var
        self.n_channels_, self.n_rows_fit_, self.n_vectors_fit_ = n_channels, int(rows.size), int(count)
        self.channel_names_ = tuple(str(c) for c in channel_names) if channel_names is not None else None
        self.fit_rows_sha256_ = rows_digest
        return self

    @staticmethod
    def _row_blocks(rows: np.ndarray):
        for start in range(0, rows.size, _CHUNK_ROWS):
            yield rows[start:start + _CHUNK_ROWS]

    # ------------------------------------------------------------ transform
    def _check(self, n_channels: int) -> None:
        if self.components_ is None:
            raise RuntimeError("channel adapter is not fitted")
        if n_channels != self.n_channels_:
            raise ValueError(f"channel count {n_channels} differs from the fitted layout ({self.n_channels_})")

    def check_channel_names(self, channel_names: Sequence[str]) -> None:
        """Refuse a tensor whose channel order differs from the one the adapter was fitted on."""
        names = tuple(str(c) for c in channel_names)
        if len(names) != self.n_channels_:
            raise ValueError(f"{len(names)} channel names for an adapter fitted on {self.n_channels_} channels")
        if self.channel_names_ is None:
            raise ValueError("the channel adapter was fitted without channel names; refit it with the names of the layout")
        if names != self.channel_names_:
            first = next(i for i, (a, b) in enumerate(zip(names, self.channel_names_)) if a != b)
            raise ValueError(f"channel layout differs from the fitted adapter at position {first}: "
                             f"{names[first]!r} vs {self.channel_names_[first]!r}")

    def transform_torch(self, x: torch.Tensor) -> torch.Tensor:
        """Project (rows, steps, C) -> (rows, steps, q) in float64 on the tensor's device, return float32."""
        self._check(x.shape[-1])
        dev = x.device
        mean = torch.as_tensor(self.mean_, dtype=torch.float64, device=dev)
        scale = torch.as_tensor(self.scale_, dtype=torch.float64, device=dev)
        comp = torch.as_tensor(self.components_, dtype=torch.float64, device=dev)
        z = (x.to(torch.float64) - mean) / scale
        return (z @ comp).to(torch.float32)

    def transform(self, dynamic: np.ndarray) -> np.ndarray:
        self._check(dynamic.shape[-1])
        z = (np.asarray(dynamic, dtype=np.float64) - self.mean_) / self.scale_
        return (z @ self.components_).astype(np.float32)

    # ------------------------------------------------------------ identity
    def digest(self) -> str:
        if self.components_ is None:
            raise RuntimeError("channel adapter is not fitted")
        h = hashlib.sha256()
        h.update(json.dumps({"q": self.n_components, "standardize": self.standardize,
                             "sample_rows_max": self.sample_rows_max, "sample_seed": self.sample_seed,
                             "n_channels": self.n_channels_}, sort_keys=True).encode())
        for arr in (self.mean_, self.scale_, self.components_):
            h.update(np.ascontiguousarray(arr, dtype=np.float64).tobytes())
        return h.hexdigest()

    def summary(self) -> dict:
        return {"n_components": self.n_components, "standardize": self.standardize, "n_channels": self.n_channels_,
                "n_rows_fit": self.n_rows_fit_, "n_vectors_fit": self.n_vectors_fit_, "fit_order": self.fit_order_,
                "fit_rows_sha256": self.fit_rows_sha256_,
                "explained_variance_ratio": [round(float(v), 6) for v in self.explained_variance_ratio_],
                "explained_variance_ratio_total": round(float(self.explained_variance_ratio_.sum()), 6),
                "digest": self.digest()}

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(path.with_suffix(".npz"), mean=self.mean_, scale=self.scale_, components=self.components_,
                 explained_variance=self.explained_variance_, explained_variance_ratio=self.explained_variance_ratio_)
        meta = self.summary()
        meta.update({"sample_rows_max": self.sample_rows_max, "sample_seed": self.sample_seed,
                     "zero_variance_scale": self.zero_variance_scale,
                     "channel_names": list(self.channel_names_) if self.channel_names_ else None})
        path.with_suffix(".json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        return path.with_suffix(".npz")

    @classmethod
    def load(cls, path: str | Path) -> "ChannelPCAAdapter":
        path = Path(path)
        meta = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        arrays = np.load(path.with_suffix(".npz"))
        adapter = cls(n_components=meta["n_components"], standardize=meta["standardize"],
                      sample_rows_max=meta["sample_rows_max"], sample_seed=meta["sample_seed"],
                      zero_variance_scale=meta["zero_variance_scale"])
        adapter.mean_, adapter.scale_ = arrays["mean"], arrays["scale"]
        adapter.components_ = arrays["components"]
        adapter.explained_variance_ = arrays["explained_variance"]
        adapter.explained_variance_ratio_ = arrays["explained_variance_ratio"]
        adapter.n_channels_, adapter.n_rows_fit_ = meta["n_channels"], meta["n_rows_fit"]
        adapter.n_vectors_fit_ = meta["n_vectors_fit"]
        adapter.channel_names_ = tuple(meta["channel_names"]) if meta.get("channel_names") else None
        adapter.fit_order_ = meta.get("fit_order", "position")
        adapter.fit_rows_sha256_ = meta.get("fit_rows_sha256")
        if adapter.digest() != meta["digest"]:
            raise ValueError("channel adapter digest mismatch after loading")
        return adapter
