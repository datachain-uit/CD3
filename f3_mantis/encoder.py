# -*- coding: utf-8 -*-
"""Frozen MantisV2 encoder for phase prefixes (tier F3).

Input contract (same common tensor as tiers F1 and F2): ``dynamic`` has shape (rows, steps <= 4, C) with the
numeric channels, the per-step mask bases, the missing__ indicators, phase_id and delta_t of ``model.data``.
For a prefix P1..Pk the encoder

1. takes the k observed steps only (nothing after the cutoff is read),
2. projects every step on the q principal components of the channel adapter (fitted on real TRAIN rows),
3. resizes every component series of length k to 512 points by linear interpolation (align_corners=False, the
   resizing recommended by the Mantis authors); a series whose k values are all equal (k = 1, or no change over the
   prefix) is replicated exactly instead, so that it stays exactly constant on every device,
4. encodes each component independently with the frozen MantisV2 truncated after transformer layer index 2,
   output token 'combined' (class token concatenated with the mean of the patch tokens, 512 values),
5. concatenates the q component embeddings (q x 512 values per row and prefix).

Constant-series guard. MantisV2 normalises every series by its own mean and ``std + 1e-5``. For a series that is
constant (every component at P1, any component without change later), float32 rounding of the mean leaves residues
of about 1e-8 * |x| that the division amplifies into pseudo-signal (measured on CPU: 0.0015 for x = 0.1 and 0.046
for x = 3.3). The guard replaces the normalised series by exact zeros when ``std <= rtol * (|mean| + rtol)`` with
rtol = 1e-6 (the rule of MOMENT revision v2_1) and leaves every other series bit-identical to the official
expression. The level of a constant series still reaches the encoder through the patch-statistics branch, which
reads the raw series. The guard needs exactly constant input: the CPU interpolation kernel keeps equal values exact,
but a kernel that computes w0 * x0 + w1 * x1 (CUDA) can leave a ripple of one ulp, which the guard of the series
branch removes while the first-difference branch (mean 0, threshold 1e-12) would amplify it. ``resize_prefix``
therefore replicates equal values instead of interpolating them.

Identity of an encoding. ``MantisPrefixEncoder.fingerprint()`` lists everything that changes the stored values
(sha256 of the truncated backbone weights, encoding settings of the registry row, precision, microbatch, device);
the cache keys every entry by its digest, so embeddings made with other weights or numerics are never mixed.
"""
from __future__ import annotations

import functools
import hashlib
import json
import time
from typing import Iterable, Optional, Sequence

import numpy as np
import torch
import torch.nn.functional as F
from torch import nn

from .adapter import ChannelPCAAdapter
from .determinism import math_sdpa
from .spec import MANTIS_V2_SPEC, N_PHASES


def official_instance_norm(x: torch.Tensor) -> torch.Tensor:
    """The expression of ``TokenGeneratorUnit.ts_scaler`` in mantis-tsfm 1.1.0 (kept for tests)."""
    return (x - torch.mean(x, axis=2, keepdim=True)) / (torch.std(x, axis=2, keepdim=True) + 1e-5)


def guarded_instance_norm(x: torch.Tensor, rtol: float = 1e-6) -> torch.Tensor:
    """Official instance normalisation with exact zeros for constant series (see module docstring)."""
    mean = torch.mean(x, axis=2, keepdim=True)
    std = torch.std(x, axis=2, keepdim=True)
    out = (x - mean) / (std + 1e-5)
    constant = std <= rtol * (mean.abs() + rtol)
    return out.masked_fill(constant, 0.0)


def resize_prefix(series: torch.Tensor, length: int = 512) -> torch.Tensor:
    """(N, k) -> (N, 1, length) by linear interpolation with align_corners=False."""
    if series.ndim != 2:
        raise ValueError("series must be (N, k)")
    if length % 32:
        raise ValueError("MantisV2 needs a length that is a multiple of 32")
    x = series.unsqueeze(1)
    if x.shape[-1] == 1:
        return x.expand(-1, -1, length).contiguous()
    out = F.interpolate(x, size=length, mode="linear", align_corners=False)
    constant = (series == series[:, :1]).all(dim=1)               # equal phase values: replicate, never interpolate
    if bool(constant.any()):
        out[constant] = x[constant, :, :1].expand(-1, -1, length)
    return out


def weights_sha256(module: nn.Module) -> str:
    """sha256 of the state dict (names, dtypes, shapes and bytes, keys sorted) of a backbone."""
    h = hashlib.sha256()
    for name, tensor in sorted(module.state_dict().items()):
        t = tensor.detach().to("cpu").contiguous()
        h.update(f"{name}|{t.dtype}|{tuple(t.shape)}|".encode("utf-8"))
        h.update(t.reshape(-1).view(torch.uint8).numpy().tobytes())
    return h.hexdigest()


def load_frozen_mantis(spec: dict = MANTIS_V2_SPEC, device: str = "cpu", pretrained: bool = True,
                       snapshot_dir: Optional[str] = None, local_files_only: bool = False) -> nn.Module:
    """Build MantisV2 truncated after ``return_transf_layer`` with the constant-series guard, frozen and in eval mode.

    ``pretrained=False`` keeps the random initialisation (tests and installation checks only, never a run:
    ``run_cell`` refuses such a backbone unless ``allow_random_backbone=True``).
    ``snapshot_dir`` loads a local snapshot made with ``f3_mantis.cli pin`` (preferred on the grid machines).
    The weights are loaded with ``strict=True``: every key of the checkpoint must match the network (the state dict
    of MantisV2 holds 4,188,690 values, the safetensors total of the pinned revision), otherwise the load fails
    instead of leaving random weights in place.
    """
    from mantis.architecture import MantisV2

    net = MantisV2(device=device, return_transf_layer=int(spec["return_transf_layer"]),
                   output_token=str(spec["output_token"]))
    if pretrained:
        try:
            if snapshot_dir:
                net = net.from_pretrained(snapshot_dir, local_files_only=True, strict=True)
            else:
                net = net.from_pretrained(str(spec["pretrained_repo"]), revision=str(spec["pretrained_revision"]),
                                          local_files_only=local_files_only, strict=True)
        except RuntimeError as error:
            raise RuntimeError("the MantisV2 checkpoint does not match the network key by key (strict load); report the "
                               f"missing/unexpected keys to the writing side, never load with strict=False: {error}") from error
    net.remove_transf_layers()
    net.tokgen_unit.ts_scaler = functools.partial(guarded_instance_norm, rtol=float(spec["constant_series_rtol"]))
    net.eval()
    for parameter in net.parameters():
        parameter.requires_grad_(False)
    n_used = sum(p.numel() for p in net.parameters())
    if pretrained and n_used != int(spec["param_count_backbone_used"]):
        raise RuntimeError(f"truncated MantisV2 has {n_used} parameters, registry says {spec['param_count_backbone_used']}")
    net.f3_param_count_used = n_used
    net.f3_pretrained = bool(pretrained)
    net.f3_weights_sha256 = weights_sha256(net)
    return net


class MantisPrefixEncoder:
    """Encode phase prefixes of the common tensor into cached F3 features."""

    def __init__(self, backbone: nn.Module, adapter: ChannelPCAAdapter, spec: dict = MANTIS_V2_SPEC,
                 device: str = "cpu", microbatch_sequences: Optional[int] = None, precision: Optional[str] = None):
        self.backbone = backbone
        self.adapter = adapter
        self.spec = spec
        self.device = torch.device(device)
        self.interp_len = int(spec["interp_len"])
        self.q = int(adapter.n_components)
        self.d_series = int(getattr(backbone, "hidden_dim", spec["embedding_dim_per_series"]))
        self.microbatch_sequences = int(microbatch_sequences or spec["microbatch_sequences"])
        self.rows_per_batch = max(1, self.microbatch_sequences // self.q)
        if precision is None:
            precision = "bf16" if self.device.type == "cuda" else "fp32"
        if precision not in {"bf16", "fp32"}:
            raise ValueError("precision must be bf16 or fp32")
        self.precision = precision
        self.weights_sha256 = getattr(backbone, "f3_weights_sha256", None) or weights_sha256(backbone)
        self.last_timing: dict = {}

    def fingerprint(self) -> dict:
        """Everything that changes the stored embedding values; its digest is part of every cache key."""
        device_name = None
        if self.device.type == "cuda" and torch.cuda.is_available():
            device_name = torch.cuda.get_device_name(self.device)
        return {"weights_sha256": self.weights_sha256, "pretrained": bool(getattr(self.backbone, "f3_pretrained", True)),
                "model_revision": self.spec["model_revision"], "input_encoding": self.spec["input_encoding"],
                "return_transf_layer": int(self.spec["return_transf_layer"]), "output_token": str(self.spec["output_token"]),
                "interp_len": self.interp_len, "interp_mode": self.spec.get("interp_mode", "linear"),
                "constant_series_rtol": float(self.spec["constant_series_rtol"]), "precision": self.precision,
                "microbatch_sequences": self.microbatch_sequences, "device_type": self.device.type,
                "device_name": device_name}

    @property
    def fingerprint_digest(self) -> str:
        payload = json.dumps(self.fingerprint(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @property
    def embedding_dim(self) -> int:
        return self.q * self.d_series

    def series_for_prefix(self, x_prefix: torch.Tensor) -> torch.Tensor:
        """(rows, k, C) float32 -> (rows * q, 1, interp_len) resized component series."""
        rows, k, _ = x_prefix.shape
        projected = self.adapter.transform_torch(x_prefix)                  # (rows, k, q)
        series = projected.transpose(1, 2).reshape(rows * self.q, k)        # component-major per row
        return resize_prefix(series, self.interp_len)

    @torch.no_grad()
    def encode_batch(self, x_prefix: torch.Tensor) -> torch.Tensor:
        """(rows, k, C) on device -> (rows, q * 512) float32."""
        rows = x_prefix.shape[0]
        series = self.series_for_prefix(x_prefix.to(self.device, dtype=torch.float32))
        with math_sdpa():
            if self.precision == "bf16":
                with torch.autocast(device_type=self.device.type, dtype=torch.bfloat16):
                    z = self.backbone(series)
            else:
                z = self.backbone(series)
        z = z.float().reshape(rows, self.q * self.d_series)
        if not torch.isfinite(z).all():
            raise RuntimeError("MantisV2 returned a non-finite embedding")
        return z

    @torch.no_grad()
    def encode(self, dynamic: np.ndarray, prefixes: Sequence[int] = (1, 2, 3, 4),
               out: Optional[np.ndarray] = None, progress: Optional[callable] = None) -> np.ndarray:
        """Encode ``dynamic`` (rows, steps, C) for every prefix in ``prefixes``.

        Returns (or fills ``out``) an array (rows, len(prefixes), q * 512) in float16. The embedding of prefix k
        reads ``dynamic[:, :k]`` only, so a k-step tensor and a 4-step tensor give identical results for prefix k
        (same rows in the same order).
        """
        if dynamic.ndim != 3:
            raise ValueError("dynamic must be (rows, steps, channels)")
        n_rows, n_steps, _ = dynamic.shape
        prefixes = tuple(int(k) for k in prefixes)
        if not prefixes or min(prefixes) < 1 or max(prefixes) > min(n_steps, N_PHASES):
            raise ValueError(f"prefixes {prefixes} not available in a tensor with {n_steps} steps")
        shape = (n_rows, len(prefixes), self.embedding_dim)
        if out is None:
            out = np.empty(shape, dtype=np.float16)
        elif tuple(out.shape) != shape:
            raise ValueError(f"output buffer has shape {out.shape}, expected {shape}")
        started = time.perf_counter()
        n_sequences, max_abs = 0, 0.0
        for p_idx, k in enumerate(prefixes):
            for start in range(0, n_rows, self.rows_per_batch):
                end = min(start + self.rows_per_batch, n_rows)
                block = np.ascontiguousarray(dynamic[start:end, :k, :], dtype=np.float32)
                z = self.encode_batch(torch.from_numpy(block))
                max_abs = max(max_abs, float(z.abs().max()))
                z16 = z.to(torch.float16)
                if not torch.isfinite(z16).all():
                    raise RuntimeError(f"an embedding value ({max_abs:.1f}) exceeds the float16 range of the registered cache; "
                                       "stop and report it to the writing side (the cache dtype is a registered constant)")
                out[start:end, p_idx, :] = z16.cpu().numpy()
                n_sequences += (end - start) * self.q
                if progress is not None:
                    progress(k, end, n_rows)
        if self.device.type == "cuda":
            torch.cuda.synchronize()
        seconds = time.perf_counter() - started
        self.last_timing = {"rows": n_rows, "prefixes": list(prefixes), "sequences": n_sequences,
                            "seconds": round(seconds, 3),
                            "sequences_per_second": round(n_sequences / seconds, 1) if seconds > 0 else None,
                            "max_abs_embedding": round(max_abs, 4)}
        return out


def count_sequences(n_rows: int, n_components: int, n_prefixes: int = N_PHASES) -> int:
    """Number of univariate series sent through the backbone for one pass over ``n_rows`` rows."""
    return int(n_rows) * int(n_components) * int(n_prefixes)


def cache_bytes(n_rows: int, n_components: int = 8, d_series: int = 512, n_prefixes: int = N_PHASES,
                bytes_per_value: int = 2) -> int:
    """Size of one cache array (rows x prefixes x q x 512 values)."""
    return int(n_rows) * int(n_prefixes) * int(n_components) * int(d_series) * int(bytes_per_value)


def iter_row_blocks(n_rows: int, block: int) -> Iterable[slice]:
    for start in range(0, n_rows, block):
        yield slice(start, min(start + block, n_rows))
