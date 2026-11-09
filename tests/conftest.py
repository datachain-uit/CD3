# -*- coding: utf-8 -*-
import sys
from pathlib import Path

import numpy as np
import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from f3_mantis.determinism import configure_determinism  # noqa: E402
from f3_mantis.encoder import load_frozen_mantis  # noqa: E402


@pytest.fixture(scope="session")
def backbone():
    """Real MantisV2 architecture with random weights (no download); truncated, guarded, frozen."""
    configure_determinism(42)
    torch.set_num_threads(2)
    return load_frozen_mantis(pretrained=False, device="cpu")


def make_tensor(n_rows=64, channels=12, seed=0, constant_tail=3):
    rng = np.random.default_rng(seed)
    base = rng.normal(size=(n_rows, 1, channels))
    steps = np.cumsum(np.abs(rng.normal(size=(n_rows, 4, channels))), axis=1)
    dynamic = (base + 0.5 * steps).astype(np.float32)
    if constant_tail:
        dynamic[:, :, -constant_tail:] = rng.normal(size=(n_rows, 1, constant_tail)).astype(np.float32)  # constant over phases
    return dynamic


@pytest.fixture
def tensor():
    return make_tensor()
