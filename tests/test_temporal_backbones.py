"""Prefix safety and input-encoding contracts of the F2/F3 backbones.

The MOMENT test reproduces the patch-view mask arithmetic of momentfm revision
38f7310 inline, so it needs neither pretrained weights nor ``momentfm``.
"""
from __future__ import annotations

import torch
import numpy as np
import pandas as pd

from model.architectures import (
    ARCHITECTURE_METADATA,
    MAX_PHASES,
    SharedPhasePatchTSTClassifier,
    build_shared_phase_model,
    moment_phase_patch_inputs,
)


PATCH_LEN = 8  # MOMENT-1 config.patch_len


def patch_view(mask: torch.Tensor, patch_len: int = PATCH_LEN) -> torch.Tensor:
    """A patch is observed only if every position in it is observed."""
    return (mask.unfold(-1, patch_len, patch_len).sum(dim=-1) == patch_len).long()


def test_right_padding_inside_one_patch_is_fully_masked_and_mean_reduction_is_nan() -> None:
    """Protect against the broken v1 MOMENT prefix encoding."""
    for steps in range(1, MAX_PHASES + 1):
        mask = torch.zeros(2, PATCH_LEN)
        mask[:, :steps] = 1
        view = patch_view(mask)
        assert view.sum().item() == 0
        reduced = (view.unsqueeze(-1) * torch.randn(2, 1, 4)).sum(1) / view.unsqueeze(-1).sum(1)
        assert torch.isnan(reduced).all()


def test_phase_as_patch_inputs_expose_exactly_the_observed_phases() -> None:
    torch.manual_seed(0)
    dynamic = torch.randn(3, MAX_PHASES, 5)
    for steps in range(1, MAX_PHASES + 1):
        values, mask, statistics = moment_phase_patch_inputs(dynamic[:, :steps], PATCH_LEN)
        assert values.shape == (3, 5, MAX_PHASES * PATCH_LEN)
        assert mask.shape == (3, MAX_PHASES * PATCH_LEN)
        view = patch_view(mask)
        assert view.tolist()[0] == [1] * steps + [0] * (MAX_PHASES - steps)
        for phase in range(steps if steps > 1 else 0):   # at P1 every channel is constant -> zeros (guard)
            block = values[:, :, phase * PATCH_LEN:(phase + 1) * PATCH_LEN]
            assert torch.allclose(block, dynamic[:, phase, :].unsqueeze(-1).expand_as(block))
        assert torch.all(values[:, :, steps * PATCH_LEN:] == 0)
        assert torch.allclose(statistics[:, :5], dynamic[:, :steps].mean(1))
        expected_std = dynamic[:, :steps].std(1, unbiased=False) if steps > 1 else torch.zeros(3, 5)
        assert torch.allclose(statistics[:, 5:], expected_std)
        if steps == 1:  # every channel is constant at P1: the encoder input is exactly zero
            assert torch.all(values == 0)

    perturbed = dynamic.clone()
    perturbed[:, 2:] += 100
    v1, m1, s1 = moment_phase_patch_inputs(dynamic[:, :2], PATCH_LEN)
    v2, m2, s2 = moment_phase_patch_inputs(perturbed[:, :2], PATCH_LEN)
    assert torch.equal(v1, v2) and torch.equal(m1, m2) and torch.equal(s1, s2)


def revin_normalise(values: torch.Tensor, mask: torch.Tensor, eps: float = 1e-5) -> torch.Tensor:
    """momentfm 38f7310 RevIN._get_statistics/_normalize for affine=False (mean/std over masked positions)."""
    observed = torch.where(mask.unsqueeze(1).bool(), values, torch.nan)
    mean = torch.nanmean(observed, dim=-1, keepdim=True)
    std = (observed - mean).square().nanmean(dim=-1, keepdim=True).sqrt() + eps
    return (values - mean) / std


def test_constant_channels_normalise_to_exactly_zero_under_momentfm_revin() -> None:
    """RevIN divides by std + 1e-5; without the guard, float32 rounding of a constant channel's mean is
    amplified into O(1e-2) pseudo-signal (O(1) for unscaled magnitudes).  Values whose 2..4-fold sum is not
    exactly representable (e.g. 2.3, 7.1) trigger the rounding, so they are used here on purpose."""
    torch.manual_seed(1)
    batch, channels = 64, 6
    for steps in range(1, MAX_PHASES + 1):
        dynamic = 7.1 * torch.rand(batch, steps, channels) + 2.3
        dynamic[:, :, :3] = dynamic[:, :1, :3]            # channels 0-2 constant over the prefix
        values, mask, statistics = moment_phase_patch_inputs(dynamic, PATCH_LEN)
        normalised = revin_normalise(values, mask)[:, :, :steps * PATCH_LEN]
        assert torch.all(normalised[:, :3] == 0), f"k={steps}: constant channels leak rounding noise"
        assert torch.all(statistics[:, channels:channels + 3] == 0)          # std reported as exactly 0
        assert torch.allclose(statistics[:, :3], dynamic[:, 0, :3])          # level kept for the head
        if steps > 1:                                                       # varying channels untouched
            assert torch.allclose(values[:, 3:, :steps * PATCH_LEN],
                                  dynamic[:, :, 3:].transpose(1, 2).repeat_interleave(PATCH_LEN, dim=2))
            assert torch.all(normalised[:, 3:].abs().amax(dim=-1) > 0.5)
    # the unguarded arithmetic is what the guard protects against
    raw = (7.1 * torch.rand(batch, 1, channels) + 2.3).transpose(1, 2).repeat_interleave(PATCH_LEN, dim=2)
    leaked = revin_normalise(raw, torch.ones(batch, PATCH_LEN)).abs().amax(dim=-1)
    assert (leaked > 0).float().mean() > 0.3 and leaked.max() > 1e-3


def test_task_contracts_follow_the_implemented_model_revision() -> None:
    import runpy
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    for task in ("CQ", "LO"):
        for folder in ("patchtst", "moment_small"):
            contract = runpy.run_path(str(root / task / "model" / folder / "config.py"))["MODEL_CONTRACT"]
            metadata = ARCHITECTURE_METADATA[contract["architecture"]]
            assert contract["model_revision"] == metadata["model_revision"], (task, folder)
            for key in ("input_encoding", "revin_statistics_fusion", "channel_mixing", "channel_aggregation", "attention_backend", "constant_channel_guard"):
                if key in metadata:
                    assert contract[key] == metadata[key], (task, folder, key)


def test_patchtst_prefix_logits_do_not_depend_on_future_phases() -> None:
    torch.manual_seed(0)
    model = SharedPhasePatchTSTClassifier(7, 3, 3).eval()
    dynamic, static = torch.randn(4, MAX_PHASES, 7), torch.randn(4, 3)
    with torch.no_grad():
        full = model(dynamic, static)
        assert full.shape == (4, MAX_PHASES, 3)
        for steps in range(1, MAX_PHASES + 1):
            assert torch.allclose(model(dynamic[:, :steps], static)[:, -1], full[:, steps - 1], atol=1e-6)
        perturbed = dynamic.clone()
        perturbed[:, 2:] += 100
        assert torch.allclose(model(perturbed, static)[:, :2], full[:, :2], atol=1e-6)


def test_patchtst_temporal_encoder_is_channel_independent() -> None:
    torch.manual_seed(3)
    channels, hidden = 5, 16
    model = SharedPhasePatchTSTClassifier(channels, 2, 3, hidden_size=hidden, attention_heads=4).eval()
    assert model.patch_projection.in_features == 2 * model.patch_len
    assert model.head[1].in_features == channels * hidden + 2

    dynamic = torch.randn(2, 3, channels)
    changed = dynamic.clone()
    changed[:, :, 0] += 100
    with torch.no_grad():
        encoded = model._encode_prefix(dynamic).reshape(2, channels, hidden)
        encoded_changed = model._encode_prefix(changed).reshape(2, channels, hidden)
    # The shared encoder sees each channel as a separate batch item. Changing
    # channel 0 cannot alter temporal encodings of channels 1..C-1.
    assert torch.allclose(encoded[:, 1:], encoded_changed[:, 1:], atol=1e-6)


def test_patchtst_smoke_training_reduces_shared_prefix_loss() -> None:
    torch.manual_seed(4)
    model = SharedPhasePatchTSTClassifier(4, 2, 3, hidden_size=16, attention_heads=4, dropout=0.0)
    dynamic, static = torch.randn(12, 4, 4), torch.randn(12, 2)
    target = torch.arange(12) % 3
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-2)
    criterion = torch.nn.CrossEntropyLoss()

    def loss_value() -> torch.Tensor:
        logits = model(dynamic, static)
        return sum(criterion(logits[:, phase], target) for phase in range(4)) / 4

    initial = float(loss_value().detach())
    for _ in range(40):
        optimizer.zero_grad(set_to_none=True)
        loss_value().backward()
        optimizer.step()
    assert float(loss_value().detach()) < initial


def test_factory_preserves_shared_phase_shape_for_task_trained_backbones() -> None:
    dynamic, static = torch.randn(2, 4, 7), torch.randn(2, 3)
    for architecture in ("rnn", "lstm", "gru", "bilstm", "patchtst"):
        model = build_shared_phase_model(7, 3, 3, architecture, hidden_size=16, num_layers=1)
        assert model(dynamic, static).shape == (2, 4, 3)


def test_patchtst_gradient_accumulation_preserves_registered_update() -> None:
    from model.data import fit_layout
    from model.shared_phase import train_shared_checkpoint
    rng = np.random.default_rng(7)
    def frame(rows: int) -> pd.DataFrame:
        values: dict[str, object] = {"enrollment_id": [f"e{n}" for n in range(rows)],
                                     "CQ_label_final": rng.choice(["warning", "average", "good"], rows),
                                     "static_a": rng.normal(size=rows).astype("float32")}
        for phase in range(1, 5):
            values[f"phase_available_P{phase}"] = np.ones(rows, dtype="float32")
            for modality in ("video", "problem", "comment"):
                values[f"{modality}_observed_mask_P{phase}"] = np.ones(rows, dtype="float32")
            for base in ("video_count", "problem_count"):
                values[f"{base}_P{phase}"] = rng.normal(size=rows).astype("float32")
                values[f"missing__{base}_P{phase}"] = np.zeros(rows, dtype="float32")
        return pd.DataFrame(values)
    train, validation = frame(64), frame(16)
    layout = fit_layout(train, task="CQ", phase_id="P4", use_masks=True)
    full, _ = train_shared_checkpoint(layout=layout, classes=("warning", "average", "good"),
        train_frame=train, validation_frame=validation, architecture="patchtst", seed=7,
        dataloader_seed=11, hidden_size=16, dropout=0.0, batch_size=64, max_epochs=1,
        patience=1, workers=0, accumulation_steps=1)
    accumulated, _ = train_shared_checkpoint(layout=layout, classes=("warning", "average", "good"),
        train_frame=train, validation_frame=validation, architecture="patchtst", seed=7,
        dataloader_seed=11, hidden_size=16, dropout=0.0, batch_size=64, max_epochs=1,
        patience=1, workers=0, accumulation_steps=4)
    assert accumulated["micro_batch_size"] == 16
    assert accumulated["history"][0]["train_seconds"] > 0
    for name, tensor in full["checkpoint"]["model_state_dict"].items():
        other = accumulated["checkpoint"]["model_state_dict"][name]
        if name.endswith("self_attn.in_proj_bias"):
            continue  # zero-gradient key-bias is AdamW rounding-sensitive
        assert torch.allclose(tensor, other, atol=5e-5, rtol=1e-4), name


def test_split_rule_version_is_never_a_static_predictor() -> None:
    """Release bookkeeping must not become a feature in a future mixed release."""
    from model.data import fit_layout

    frame = pd.DataFrame({
        "enrollment_id": ["e1", "e2", "e3"],
        "CQ_label_final": ["warning", "average", "good"],
        "split_rule_version": [1.0, 2.0, 1.0],
        "static_allowed": [0.1, 0.2, 0.3],
        **{f"phase_available_P{phase}": np.ones(3, dtype="float32") for phase in range(1, 5)},
        **{f"video_count_P{phase}": np.arange(3, dtype="float32") for phase in range(1, 5)},
    })
    layout = fit_layout(frame, task="CQ", phase_id="P4", use_masks=False)
    assert "static_allowed" in layout.static_columns
    assert "split_rule_version" not in layout.static_columns
