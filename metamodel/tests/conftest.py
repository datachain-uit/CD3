# -*- coding: utf-8 -*-
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]      # ".../Data and Code"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from metamodel import assemble as A          # noqa: E402
from metamodel import contracts as C         # noqa: E402
from metamodel import synthetic as SY        # noqa: E402


@pytest.fixture(scope="session")
def synthetic_small():
    """Small SYNTHETIC fixture: 2 tasks x 3 windows x 2 seeds x 3 models x 17 pipelines x 4 phases x 2 splits."""
    return SY.make_synthetic(seeds=(42, 43), models=("RNN", "LSTM", "PATCHTST"), noise=0.01)


@pytest.fixture(scope="session")
def seed_level(synthetic_small):
    f = synthetic_small
    return A.assemble_seed_level(f["facts"], resources=f["resources"], state_profile=f["state_profile"],
                                 model_context=f["model_context"], provenance={"meta_release_id": "TEST"},
                                 energy_measured_types=C.ENERGY_MEASURED_TYPES_WITH_ESTIMATE)


@pytest.fixture(scope="session")
def seed_agg(seed_level):
    return A.aggregate_seeds(seed_level, planned_seeds=(42, 43), energy_measured_types=C.ENERGY_MEASURED_TYPES_WITH_ESTIMATE)
