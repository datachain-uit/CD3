# -*- coding: utf-8 -*-
"""Registered specification of tier F3 (MANTIS_V2, exploratory) for TEMPO-MDS / CD3.

The values below mirror ``tempo_fix/registries.py`` (MODEL_REGISTRY row ``MANTIS_V2``, revision
registries_rev_2026-11-06, decision 37). Change them in the registry first, never here alone: the
test ``tests/test_spec.py`` and the registry test compare the two.

Sources read on 2026-11-06 (writing side):
  * Hugging Face API ``paris-noah/MantisV2``: sha 8f6ca35cb54ab14b120618943c6fca5ddf5a76a6,
    lastModified 2026-08-21T09:56:46Z, licence apache-2.0, safetensors total 4,188,690.
  * PyPI ``mantis-tsfm`` 1.1.0 (wheel sha256 accdaf2e44d263b23913fc914e00d5d0d37d41d70590ba34d70883f21b40a55f),
    ``mantis/architecture/version2.py``: MantisV2 has 4,188,672 parameters; with ``return_transf_layer=2``
    the truncated network has 2,214,144; ``output_token='combined'`` gives a 512-dimensional embedding.
  * Feofanov et al., ICML 2026 (PMLR 306:30692-30719) and arXiv:2602.17868 (MantisV2): frozen-encoder use,
    third layer (index 2) best, class token concatenated with the mean token, inputs resized to 512,
    channels encoded independently.
"""
from __future__ import annotations

import hashlib
import json
from typing import Dict

MODEL_NAME = "MANTIS_V2"
ARCHITECTURE = "mantis_v2"
N_PHASES = 4

MANTIS_V2_SPEC: Dict[str, object] = {
    "model_name": MODEL_NAME,
    "architecture": ARCHITECTURE,
    "model_tier": "F3_TS_FOUNDATION",
    "model_family": "MANTIS",
    "variant_role": "EXPLORATORY",
    "is_pretrained": 1,
    "finetune_mode": "LINEAR_PROBE",
    "encoder_frozen": 1,
    "pretrained_repo": "paris-noah/MantisV2",
    "pretrained_revision": "8f6ca35cb54ab14b120618943c6fca5ddf5a76a6",
    "pretrained_revision_note": "read from the Hugging Face API on 2026-11-06 (lastModified 2026-08-21T09:56:46Z); "
                                "the pilot re-reads it and records the resolved snapshot and file sha256 in the manifest",
    "pretraining_data": "synthetic only (CauKer, 2 million series); no real-data overlap possible with MOOCCubeX",
    "library": "mantis-tsfm==1.1.0",
    "library_wheel_sha256": "accdaf2e44d263b23913fc914e00d5d0d37d41d70590ba34d70883f21b40a55f",
    "licence": "Apache-2.0 (PyPI package; model-card metadata at the pinned revision)",
    "architecture_class": "mantis.architecture.MantisV2",
    "param_count_backbone_total": 4188672,
    "param_count_backbone_used": 2214144,
    "return_transf_layer": 2,
    "output_token": "combined",
    "embedding_dim_per_series": 512,
    "num_patches": 32,
    "interp_len": 512,
    "interp_mode": "linear",
    "interp_align_corners": False,
    "interp_constant_rows": "a component whose k values are all equal is replicated exactly instead of interpolated (keeps the "
                            "constant-series guard exact on kernels that compute w0 x0 + w1 x1, such as CUDA)",
    "input_encoding": "PCA8_PER_PHASE_THEN_LINEAR_RESIZE_512_v1",
    "channel_adapter": {
        "method": "PCA_ACROSS_CHANNELS",
        "n_components": 8,
        "standardize": True,
        "fit_rows": "REAL_TRAIN_ROWS_ONLY",
        "fit_vectors": "every phase step of the selected rows (P1..P4 pooled)",
        "sample_rows_max": 1_000_000,
        "sample_seed": 20260922,
        "solver": "eigh of the float64 covariance of standardised channels",
        "sign_rule": "largest absolute loading of every component is positive (ties: lowest channel index)",
        "zero_variance_channel_scale": 1.0,
        "fit_order": "rows sorted by row id before sampling and accumulation (independent of the frame order); "
                     "sha256 of the fitted rows stored with the adapter and checked by later imputer-only cells",
    },
    "constant_series_guard": "instance normalisation returns exact zeros when std <= 1e-6 * (|mean| + 1e-6) "
                             "over the resized series (rule of MOMENT revision v2_1); otherwise the official expression",
    "constant_series_rtol": 1e-6,
    "head_inputs": ["standardised MantisV2 embeddings (8 x 512 = 4096)", "standardised static block",
                    "phase one-hot (4)"],
    "head": "Dropout(0.3) + Linear(4096 + static_dim + 4 -> n_classes)",
    "feature_standardisation": "per-dimension mean and std over TRAIN rows x four prefixes (float64 accumulation)",
    "embedding_cache": {
        "level_A": "per (task, window, imputer pipeline, adapter digest): REAL TRAIN, VALIDATION, TEST",
        "level_B": "per (task, window, balanced pipeline, master seed): SYNTHETIC TRAIN rows only",
        "fallback": "CELL_TRAIN when the real rows of a balanced cell differ from the imputer-only TRAIN (ids or input sha256)",
        "dtype": "float16",
        "key": "adapter digest + encoder fingerprint (sha256 of the truncated backbone weights, encoding settings, "
               "precision, microbatch, device)",
        "reuse_rule": "every entry (level A, level B, CELL_TRAIN) is reused only when ids and the sha256 of its input "
                      "tensor match; an existing entry built from other rows stops the run",
    },
    "weight_loading": "strict key-by-key load of the pinned snapshot (state dict 4,188,690 values); run_cell refuses a "
                      "random-weight backbone",
    "microbatch_sequences": 4096,
    "attention_backend": "MATH (scoped torch.nn.attention.sdpa_kernel)",
    "backbone_precision": "bf16 autocast on CUDA, fp32 on CPU; embeddings stored as float16",
    "training": {
        "loss_name": "cross_entropy", "class_weighting": "NONE", "optimizer": "AdamW", "lr": 1e-3,
        "weight_decay": 1e-5, "batch_size": 2048, "max_epochs": 50, "early_stopping_patience": 5,
        "dropout": 0.3, "selection_metric": "MEAN_PHASE_MACRO_F1", "selection_tiebreak": "MEAN_PHASE_CROSS_ENTROPY_MIN",
        "training_sequence": "P1_P2_P3_P4 (one head per cell, checkpoint shared by the four phases)",
        "head_precision": "fp32",
    },
    "scope": {
        "release": "full release (phase 2); outside the phase-1 submission (decision 36)",
        "core_pipelines": ["V0", "V1", "V5", "V9", "V13", "V2", "V6", "V10", "V14", "V3", "V7", "V11", "V15"],
        "sensitivity_pipelines": ["V4", "V8", "V12", "V16"],
        "windows": ["W1", "W2", "W3"],
        "tables": "separate export labelled EXPLORATORY; never pooled into the primary tables or hypothesis tests",
    },
    "hparam_config_id": "HP_MANTISV2_FROZEN_LINEAR_PROBE_v1_pca8",
    "model_revision": "mantisv2_frozen_linear_probe_v1_pca8_interp512",
    "max_seq_len": 4,
    "patch_len": 16,
    "patch_stride": 16,
}


def spec_digest(spec: Dict[str, object] = MANTIS_V2_SPEC) -> str:
    """sha256 of the canonical JSON of the specification (recorded in every manifest)."""
    payload = json.dumps(spec, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
