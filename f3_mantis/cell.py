# -*- coding: utf-8 -*-
"""One F3 cell end to end on arrays produced by the team's loader (``model.data.transform_frame``).

The runner of the team owns data loading, S2 artefact resolution, prediction files, metrics and L2 ingestion.
This function covers the F3-specific part between the tensors and the class probabilities:

    adapter (real TRAIN rows) -> level-A cache (REAL_TRAIN, VALIDATION, TEST) -> level-B cache (synthetic rows)
    -> TRAIN features in the order of the TRAIN frame -> shared-phase probe -> probabilities P1..P4.

Inputs per split: ``dynamic`` (rows, 4, C) float32, ``static`` (rows, S) float32, ``y`` (rows,) int class ids,
``row_ids`` (enrollment_id for real rows, synthetic_id for synthetic rows); for TRAIN also ``is_synthetic`` and
``channel_names`` (the C dynamic channel names in tensor order, required); VALIDATION and TEST may carry
``channel_names`` too, which are then checked against TRAIN.

Identity rules (independent review of 2026-11-06):
  * the backbone must carry the pinned weights (``allow_random_backbone=True`` only in tests);
  * the adapter of (task, window, imputer) is fitted once by the imputer-only cell on its real TRAIN rows, stored
    with the sha256 of these rows, and refused by a later imputer-only cell whose real TRAIN rows differ;
  * every cache entry (level A, level B, CELL_TRAIN) is keyed by the adapter digest and the encoder fingerprint and
    is reused only when ids and input sha256 match; an entry built from other rows stops the run.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import numpy as np

from .adapter import ChannelPCAAdapter
from .encoder import MantisPrefixEncoder
from .probe import predict_probe, save_probe, train_probe
from .spec import MANTIS_V2_SPEC, spec_digest
from .store import CacheKey, EmbeddingStore, StackedFeatures, input_sha256


def _take(array: np.ndarray, idx: np.ndarray) -> np.ndarray:
    """``array[idx]`` without a copy when ``idx`` selects every row in order (imputer-only TRAIN)."""
    idx = np.asarray(idx, dtype=np.int64)
    if idx.size == len(array) and (idx.size == 0 or (idx[0] == 0 and bool(np.all(np.diff(idx) == 1)))):
        return array
    return array[idx]


def adapter_path_for(root: str | Path, task: str, window: str, imputer: str) -> Path:
    """Location of the channel adapter of (task, window, imputer) under a cache or adapter root."""
    return Path(root) / f"task={task}" / f"window={window}" / f"imputer={imputer}" / "channel_adapter"


def run_cell(*, task: str, window: str, pipeline: str, imputer: str, seed: int, num_classes: int,
             train: dict, validation: dict, test: dict, backbone, store_root: str, out_dir: str,
             device: str = "cpu", backbone_pin: Optional[dict] = None, adapter_dir: Optional[str] = None,
             spec: dict = MANTIS_V2_SPEC, microbatch_sequences: Optional[int] = None, precision: Optional[str] = None,
             allow_random_backbone: bool = False) -> dict:
    """Run one F3 cell. ``adapter_dir`` is a root: the adapter always lives under task=/window=/imputer=."""
    if not getattr(backbone, "f3_pretrained", False) and not allow_random_backbone:
        raise RuntimeError("the backbone has random weights (load_frozen_mantis(pretrained=False)); an F3 cell needs the "
                           "pinned MantisV2 weights. allow_random_backbone=True is for tests only, with a cache root of "
                           "their own")
    channel_names = train.get("channel_names")
    if channel_names is None:
        raise ValueError("train['channel_names'] is required: the names of the dynamic channels in tensor order")
    channel_names = tuple(str(c) for c in channel_names)
    for split_name, split in (("validation", validation), ("test", test)):
        names = split.get("channel_names")
        if names is not None and tuple(str(c) for c in names) != channel_names:
            raise ValueError(f"the {split_name} tensor has another channel layout than the TRAIN tensor")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    store = EmbeddingStore(store_root)
    is_synth = np.asarray(train.get("is_synthetic", np.zeros(len(train["y"]), dtype=bool)), dtype=bool)
    real_idx, synth_idx = np.flatnonzero(~is_synth), np.flatnonzero(is_synth)
    balanced = pipeline != imputer
    if not balanced and synth_idx.size:
        raise ValueError("an imputer-only pipeline must not carry synthetic TRAIN rows")
    row_ids = np.asarray(train["row_ids"])
    real_dynamic, real_ids = _take(train["dynamic"], real_idx), row_ids[real_idx]
    real_digest = input_sha256(real_dynamic, real_ids)

    # 1. channel adapter: real TRAIN rows of the imputer-only cell, shared by every balancer and seed of this
    #    (task, window, imputer); stored with the sha256 of the rows it was fitted on
    adapter_path = adapter_path_for(adapter_dir or store_root, task, window, imputer)
    if adapter_path.with_suffix(".npz").exists():
        adapter = ChannelPCAAdapter.load(adapter_path)
        if not balanced and adapter.fit_rows_sha256_ != real_digest:
            raise RuntimeError(f"the channel adapter {adapter_path} was fitted on other real TRAIN rows than this "
                               f"imputer-only cell ({adapter.fit_rows_sha256_} vs {real_digest}); the TRAIN rows of an "
                               "imputer-only pipeline must not depend on the seed or change after the fit")
    elif balanced:
        raise RuntimeError(f"no channel adapter for {task}/{window}/{imputer}: run the imputer-only pipeline {imputer} "
                           "of this window first (it fits the adapter on the real TRAIN rows)")
    else:
        cfg = spec["channel_adapter"]
        adapter = ChannelPCAAdapter(n_components=int(cfg["n_components"]), standardize=bool(cfg["standardize"]),
                                    sample_rows_max=int(cfg["sample_rows_max"]), sample_seed=int(cfg["sample_seed"]))
        adapter.fit(train["dynamic"], real_mask=~is_synth, channel_names=channel_names, row_ids=row_ids,
                    rows_digest=real_digest)
        adapter.save(adapter_path)
    adapter.check_channel_names(channel_names)
    digest = adapter.digest()
    encoder = MantisPrefixEncoder(backbone, adapter, spec=spec, device=device, microbatch_sequences=microbatch_sequences,
                                  precision=precision)
    pinned_weights = (backbone_pin or {}).get("weights_sha256_truncated")
    if pinned_weights and pinned_weights != encoder.weights_sha256:
        raise RuntimeError("the backbone weights differ from backbone_pin.json (weights_sha256_truncated)")
    encoder_digest = encoder.fingerprint_digest

    def key(split: str, with_cell: bool = False) -> CacheKey:
        return CacheKey(task, window, imputer, digest, encoder_digest, split,
                        pipeline=pipeline if with_cell else None, seed=seed if with_cell else None)

    # 2. level A (encoded once per imputer and encoder): VALIDATION and TEST never depend on the balancer, and the
    #    TRAIN rows of an imputer-only pipeline never depend on the seed, so an entry built from other rows stops
    #    the run. Only the imputer-only cell creates REAL_TRAIN; a balanced cell reuses it when ids and values agree.
    va_emb, va_pos, va_reused, _ = store.ensure(key("VALIDATION"), encoder, validation["dynamic"], validation["row_ids"],
                                                backbone_pin=backbone_pin)
    te_emb, te_pos, te_reused, _ = store.ensure(key("TEST"), encoder, test["dynamic"], test["row_ids"],
                                                backbone_pin=backbone_pin)
    real_part = store.ensure(key("REAL_TRAIN"), encoder, real_dynamic, real_ids, backbone_pin=backbone_pin,
                             create=not balanced, strict=not balanced, input_digest=real_digest)
    order = np.concatenate([real_idx, synth_idx])
    cache_reuse = {"VALIDATION": va_reused, "TEST": te_reused}

    # 3. TRAIN features in a fixed order (real rows, then synthetic rows)
    if real_part is not None:
        tr_emb, tr_pos, tr_reused, tr_manifest = real_part
        cache_reuse["REAL_TRAIN"] = tr_reused
        parts, positions = [tr_emb], [tr_pos]
        if synth_idx.size:   # level B: synthetic rows of this balanced pipeline and master seed, verified like level A
            sy_emb, sy_pos, sy_reused, _ = store.ensure(key("SYNTH_TRAIN", with_cell=True), encoder,
                                                        _take(train["dynamic"], synth_idx), row_ids[synth_idx],
                                                        backbone_pin=backbone_pin)
            parts.append(sy_emb)
            positions.append(sy_pos)
            cache_reuse["SYNTH_TRAIN"] = sy_reused
        cache_mode = "LEVEL_A_PLUS_B" if synth_idx.size else "LEVEL_A"
    else:                    # real rows of this balanced cell differ from the imputer-only TRAIN: encode the cell
        ce_emb, ce_pos, ce_reused, tr_manifest = store.ensure(key("CELL_TRAIN", with_cell=True), encoder,
                                                              train["dynamic"][order], row_ids[order],
                                                              backbone_pin=backbone_pin)
        parts, positions = [ce_emb], [ce_pos]
        cache_reuse["CELL_TRAIN"] = ce_reused
        cache_mode = "CELL_TRAIN_FALLBACK"
    train_features = StackedFeatures(parts, positions)
    train_static = np.asarray(train["static"])[order]
    train_y = np.asarray(train["y"])[order]
    val_features = StackedFeatures([va_emb], [va_pos])
    test_features = StackedFeatures([te_emb], [te_pos])

    # 4. probe
    result = train_probe(train_features, train_static, train_y, val_features, validation["static"], validation["y"],
                         num_classes=num_classes, seed=seed, spec=spec, device=device)
    save_probe(result, out / "probe_head.pt", digest, extra={"task": task, "window": window, "pipeline": pipeline,
                                                              "seed": seed, "encoder_digest": encoder_digest})
    val_probs = predict_probe(result["model"], val_features, validation["static"], device=device)
    test_probs = predict_probe(result["model"], test_features, test["static"], device=device)
    np.save(out / "validation_probabilities.npy", val_probs)
    np.save(out / "test_probabilities.npy", test_probs)
    record = {"task": task, "window": window, "pipeline": pipeline, "imputer": imputer, "seed": seed,
              "model_name": spec["model_name"], "model_tier": spec["model_tier"], "variant_role": spec["variant_role"],
              "model_revision": spec["model_revision"], "hparam_config_id": spec["hparam_config_id"],
              "input_encoding": spec["input_encoding"], "spec_digest": spec_digest(spec),
              "adapter": adapter.summary(), "adapter_fit_rows_match": adapter.fit_rows_sha256_ == real_digest,
              "real_train_input_sha256": real_digest,
              "encoder_digest": encoder_digest, "encoder_fingerprint": encoder.fingerprint(),
              "backbone_pin": backbone_pin or {}, "backbone_pretrained": bool(getattr(backbone, "f3_pretrained", False)),
              "cache_mode": cache_mode, "cache_reuse": cache_reuse,
              "train_rows_real": int(real_idx.size), "train_rows_synthetic": int(synth_idx.size),
              "best_epoch": result["best_epoch"], "epochs_trained": result["epochs_trained"],
              "early_stopped": result["early_stopped"], "selection_key": result["selection_key"],
              "param_count_trainable": result["trainable_parameters"],
              "param_count_total": int(getattr(backbone, "f3_param_count_used", 0)) + result["trainable_parameters"],
              "encoder_timing_train": tr_manifest.get("timing"), "history": result["history"]}
    (out / "f3_cell_record.json").write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
    return {"record": record, "validation_probabilities": val_probs, "test_probabilities": test_probs,
            "train_order": order, "model": result["model"]}
