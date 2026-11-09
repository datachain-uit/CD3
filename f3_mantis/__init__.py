# -*- coding: utf-8 -*-
"""Tier F3 of TEMPO-MDS (CD3): frozen MantisV2 encoder with a shared-phase linear probe, registered as EXPLORATORY.

Package of the writing side (2026-11-06, registry revision registries_rev_2026-11-06, decision 37) to be
integrated into github.com/datachain-uit/CD3 by the code team. See README_f3_mantis.md and the guide
Huong_dan_doi_code_F3_MantisV2_2026-11-06.docx.
"""
__version__ = "0.1.0"

from .adapter import ChannelPCAAdapter
from .encoder import (MantisPrefixEncoder, guarded_instance_norm, load_frozen_mantis, official_instance_norm,
                      resize_prefix)
from .probe import SharedPhaseLinearProbe, load_probe, predict_probe, save_probe, train_probe
from .spec import ARCHITECTURE, MANTIS_V2_SPEC, MODEL_NAME, spec_digest
from .store import CacheKey, EmbeddingStore, StackedFeatures, gather_rows, input_sha256

__all__ = ["ARCHITECTURE", "MANTIS_V2_SPEC", "MODEL_NAME", "spec_digest", "ChannelPCAAdapter", "MantisPrefixEncoder",
           "guarded_instance_norm", "official_instance_norm", "resize_prefix", "load_frozen_mantis",
           "SharedPhaseLinearProbe", "train_probe", "predict_probe", "save_probe", "load_probe",
           "CacheKey", "EmbeddingStore", "StackedFeatures", "gather_rows", "input_sha256"]
