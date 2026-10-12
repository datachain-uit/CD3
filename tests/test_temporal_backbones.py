"""Prefix safety and input-encoding contracts of the F2/F3 backbones.

The MOMENT test reproduces the patch-view mask arithmetic of momentfm revision
38f7310 inline, so it needs neither pretrained weights nor ``momentfm``.
"""
from __future__ import annotations

import torch

from model.architectures import (
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
        for phase in range(steps):
            block = values[:, :, phase * PATCH_LEN:(phase + 1) * PATCH_LEN]
            assert torch.allclose(block, dynamic[:, phase, :].unsqueeze(-1).expand_as(block))
        assert torch.all(values[:, :, steps * PATCH_LEN:] == 0)
        assert torch.allclose(statistics[:, :5], dynamic[:, :steps].mean(1))
        expected_std = dynamic[:, :steps].std(1, unbiased=False) if steps > 1 else torch.zeros(3, 5)
        assert torch.allclose(statistics[:, 5:], expected_std)

    perturbed = dynamic.clone()
    perturbed[:, 2:] += 100
    v1, m1, s1 = moment_phase_patch_inputs(dynamic[:, :2], PATCH_LEN)
    v2, m2, s2 = moment_phase_patch_inputs(perturbed[:, :2], PATCH_LEN)
    assert torch.equal(v1, v2) and torch.equal(m1, m2) and torch.equal(s1, s2)


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
