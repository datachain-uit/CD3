# -*- coding: utf-8 -*-
import numpy as np
import pytest
import torch

from f3_mantis.adapter import ChannelPCAAdapter
from f3_mantis.encoder import (MantisPrefixEncoder, guarded_instance_norm, load_frozen_mantis, official_instance_norm,
                               resize_prefix)
from f3_mantis.spec import MANTIS_V2_SPEC


def test_official_scaler_leaks_pseudo_signal_for_constant_series():
    """Reproduces the numerical problem the guard fixes (float32 mean of a constant series is not exact)."""
    x = torch.full((2, 1, 512), 3.3)
    assert float(official_instance_norm(x).abs().max()) > 1e-3
    assert float(guarded_instance_norm(x).abs().max()) == 0.0


def test_guard_is_bitwise_identical_to_official_for_varying_series():
    torch.manual_seed(0)
    x = torch.randn(64, 1, 512) * torch.logspace(-3, 3, 64).view(-1, 1, 1)
    assert torch.equal(guarded_instance_norm(x), official_instance_norm(x))


def test_backbone_uses_guard_and_is_truncated(backbone):
    assert backbone.tokgen_unit.ts_scaler.func is guarded_instance_norm
    assert len(backbone.transf_unit.transformer.layers) == MANTIS_V2_SPEC["return_transf_layer"] + 1
    assert backbone.f3_param_count_used == MANTIS_V2_SPEC["param_count_backbone_used"]
    assert backbone.hidden_dim == MANTIS_V2_SPEC["embedding_dim_per_series"]
    assert not any(p.requires_grad for p in backbone.parameters())


def test_resize_prefix_contract():
    one = resize_prefix(torch.tensor([[2.5]]), 512)
    assert one.shape == (1, 1, 512) and bool((one == 2.5).all())
    flat = resize_prefix(torch.tensor([[0.1, 0.1, 0.1]]), 512)
    assert bool((flat == torch.tensor(0.1)).all())          # equal phase values stay exactly constant
    ramp = resize_prefix(torch.tensor([[0.0, 1.0]]), 512)
    assert float(ramp[0, 0, 0]) == 0.0 and float(ramp[0, 0, -1]) == 1.0
    with pytest.raises(ValueError):
        resize_prefix(torch.tensor([[0.0, 1.0]]), 500)


def _encoder(backbone, tensor, q=4):
    adapter = ChannelPCAAdapter(n_components=q).fit(tensor)
    return MantisPrefixEncoder(backbone, adapter, device="cpu", microbatch_sequences=64)


def test_prefix_safety_future_steps_never_read(backbone, tensor):
    enc = _encoder(backbone, tensor)
    full = enc.encode(tensor)
    perturbed = tensor.copy()
    perturbed[:, 2:, :] += 100.0                     # change P3 and P4 only
    again = enc.encode(perturbed)
    assert np.array_equal(full[:, 0], again[:, 0]) and np.array_equal(full[:, 1], again[:, 1])
    assert not np.array_equal(full[:, 2], again[:, 2])


def test_truncated_and_full_inputs_give_identical_prefix_embeddings(backbone, tensor):
    enc = _encoder(backbone, tensor)
    full = enc.encode(tensor)
    for k in (1, 2, 3, 4):
        truncated = enc.encode(np.ascontiguousarray(tensor[:, :k]), prefixes=(k,))
        assert np.array_equal(truncated[:, 0], full[:, k - 1]), k


def test_encoding_is_deterministic_and_finite(backbone, tensor):
    enc = _encoder(backbone, tensor)
    a, b = enc.encode(tensor), enc.encode(tensor)
    assert a.dtype == np.float16 and a.shape == (tensor.shape[0], 4, enc.embedding_dim)
    assert np.array_equal(a, b) and np.isfinite(a.astype(np.float32)).all()


def test_p1_embedding_depends_on_level_not_on_float_noise(backbone):
    """At P1 every component is constant; equal levels must give bitwise equal embeddings, any level must be finite."""
    adapter = ChannelPCAAdapter(n_components=2, standardize=False)
    adapter.mean_, adapter.scale_ = np.zeros(2), np.ones(2)
    adapter.components_, adapter.n_channels_ = np.eye(2), 2
    adapter.explained_variance_ = adapter.explained_variance_ratio_ = np.ones(2)
    enc = MantisPrefixEncoder(backbone, adapter, device="cpu")
    x = np.array([[[3.3, 3.3]], [[3.3, 3.3]], [[-7.0, 0.0]]], dtype=np.float32)    # (rows, 1 step, 2 channels)
    z = enc.encode(x, prefixes=(1,))
    d = enc.d_series
    assert np.array_equal(z[0, 0, :d], z[0, 0, d:]) and np.array_equal(z[0], z[1])
    assert not np.array_equal(z[2, 0, :d], z[2, 0, d:])


def test_resize_replicates_equal_values_even_if_the_kernel_ripples(monkeypatch):
    """A kernel computing w0*x0 + w1*x1 (CUDA) can leave one-ulp ripples; equal phase values must stay exact."""
    import f3_mantis.encoder as encoder_module
    real = encoder_module.F.interpolate

    def rippling(x, **kwargs):
        out = real(x, **kwargs)
        ripple = torch.zeros(out.shape[-1], dtype=out.dtype)
        ripple[1::2] = 1e-6
        return out + ripple

    monkeypatch.setattr(encoder_module.F, "interpolate", rippling)
    series = torch.tensor([[0.1, 0.1, 0.1], [0.0, 1.0, 2.0], [3.3, 3.3, 3.3]])
    r = resize_prefix(series, 512)
    assert bool((r[0] == series[0, 0]).all()) and bool((r[2] == series[2, 0]).all())
    expected_ramp = rippling(series[1:2].unsqueeze(1), size=512, mode="linear", align_corners=False)
    assert torch.equal(r[1:2], expected_ramp)                   # a varying series is still interpolated
    flat = r[[0, 2]]
    diff = torch.nn.functional.pad(torch.diff(flat, dim=2), (0, 1))
    assert float(guarded_instance_norm(flat).abs().max()) == 0.0 and float(guarded_instance_norm(diff).abs().max()) == 0.0


def test_fingerprint_tracks_weights_precision_and_microbatch(backbone, tensor):
    adapter = ChannelPCAAdapter(n_components=4).fit(tensor)
    a = MantisPrefixEncoder(backbone, adapter, device="cpu", microbatch_sequences=64)
    assert a.fingerprint_digest == MantisPrefixEncoder(backbone, adapter, device="cpu", microbatch_sequences=64).fingerprint_digest
    assert a.fingerprint()["weights_sha256"] == backbone.f3_weights_sha256
    assert MantisPrefixEncoder(backbone, adapter, device="cpu", microbatch_sequences=128).fingerprint_digest != a.fingerprint_digest
    assert MantisPrefixEncoder(backbone, adapter, device="cpu", microbatch_sequences=64, precision="bf16").fingerprint_digest != a.fingerprint_digest
    torch.manual_seed(7)
    other = load_frozen_mantis(pretrained=False)
    assert MantisPrefixEncoder(other, adapter, device="cpu", microbatch_sequences=64).fingerprint_digest != a.fingerprint_digest


def test_strict_loading_of_snapshots(tmp_path):
    """A snapshot whose keys match loads exactly; a snapshot with other keys fails instead of leaving random weights."""
    from mantis.architecture import MantisV2
    from safetensors.torch import save_file

    torch.manual_seed(11)
    reference = MantisV2(device="cpu")                         # full six-layer network, as an upstream checkpoint
    good = tmp_path / "good"
    reference.save_pretrained(good)
    net = load_frozen_mantis(device="cpu", snapshot_dir=str(good))
    ref_state = reference.state_dict()
    assert net.f3_pretrained and net.f3_param_count_used == MANTIS_V2_SPEC["param_count_backbone_used"]
    assert all(torch.equal(value, ref_state[name]) for name, value in net.state_dict().items())
    assert len(net.transf_unit.transformer.layers) == 3 and net.output_token == "combined"
    bad = tmp_path / "bad"
    bad.mkdir()
    save_file({"module." + k: v.contiguous() for k, v in ref_state.items()}, str(bad / "model.safetensors"))
    with pytest.raises(RuntimeError, match="strict load"):
        load_frozen_mantis(device="cpu", snapshot_dir=str(bad))
