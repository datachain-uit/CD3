# -*- coding: utf-8 -*-
"""The package specification must equal the registry row (tempo_fix/registries.py, rev 2026-11-06)."""
import importlib
import os
import sys
from pathlib import Path

import pytest

from f3_mantis.spec import MANTIS_V2_SPEC, spec_digest

KEYS = ("model_name", "model_tier", "model_family", "variant_role", "is_pretrained", "finetune_mode", "pretrained_repo",
        "pretrained_revision", "library", "return_transf_layer", "output_token", "interp_len", "input_encoding",
        "model_revision", "hparam_config_id", "param_count_backbone_total", "param_count_backbone_used",
        "constant_series_rtol", "interp_constant_rows", "weight_loading")


def _registry():
    root = os.environ.get("TEMPO_FIX_PARENT")
    if not root:
        pytest.skip("set TEMPO_FIX_PARENT to the folder that contains tempo_fix/ to compare with the registry")
    sys.path.insert(0, str(Path(root)))
    return importlib.import_module("tempo_fix.registries")


def test_spec_digest_is_stable():
    assert spec_digest() == spec_digest(dict(MANTIS_V2_SPEC))


def test_spec_matches_registry_row():
    r = _registry()
    row = [m for m in r.MODEL_REGISTRY if m["model_name"] == "MANTIS_V2"][0]
    for key in KEYS:
        assert row[key] == MANTIS_V2_SPEC[key], key
    for key in ("n_components", "fit_rows", "sample_rows_max", "sample_seed", "fit_order"):
        assert row["channel_adapter"][key] == MANTIS_V2_SPEC["channel_adapter"][key], key
    for key in ("key", "reuse_rule", "dtype", "fallback"):
        assert row["embedding_cache"][key] == MANTIS_V2_SPEC["embedding_cache"][key], key
