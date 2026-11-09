# -*- coding: utf-8 -*-
"""Determinism helpers shared by the encoder and the probe (same rules as COMMON_HPARAMS of the registry)."""
from __future__ import annotations

import contextlib
import os
import random

import numpy as np
import torch


def configure_determinism(seed: int, strict: bool = True) -> None:
    """Seed every generator and switch to deterministic kernels.

    ``CUBLAS_WORKSPACE_CONFIG`` only takes effect when it is set before the first CUDA call, so runners must call
    this function (or set the variable in the environment) before anything touches the GPU.
    """
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    random.seed(seed)
    np.random.seed(seed % (2 ** 32))
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    if strict:
        torch.use_deterministic_algorithms(True)


@contextlib.contextmanager
def math_sdpa():
    """Scope scaled-dot-product attention to the MATH backend (deterministic, no batch-size limit of fused kernels)."""
    try:
        from torch.nn.attention import SDPBackend, sdpa_kernel
    except ImportError:  # torch < 2.3
        if torch.cuda.is_available():
            with torch.backends.cuda.sdp_kernel(enable_flash=False, enable_math=True, enable_mem_efficient=False):
                yield
        else:
            yield
        return
    with sdpa_kernel(SDPBackend.MATH):
        yield


def library_versions() -> dict:
    """Versions recorded in every manifest."""
    versions = {"torch": torch.__version__, "numpy": np.__version__,
                "cuda": torch.version.cuda, "cudnn": torch.backends.cudnn.version() if torch.backends.cudnn.is_available() else None}
    try:
        import importlib.metadata as md
        versions["mantis-tsfm"] = md.version("mantis-tsfm")
    except Exception:  # pragma: no cover - package metadata missing
        versions["mantis-tsfm"] = None
    if torch.cuda.is_available():
        versions["gpu"] = torch.cuda.get_device_name(0)
        versions["cuda_capability"] = ".".join(map(str, torch.cuda.get_device_capability(0)))
    versions["cublas_workspace_config"] = os.environ.get("CUBLAS_WORKSPACE_CONFIG")
    return versions
