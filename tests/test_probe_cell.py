# -*- coding: utf-8 -*-
import numpy as np
import pytest
import torch

from f3_mantis.cell import run_cell
from f3_mantis.metrics import cross_entropy_from_logits, macro_f1
from f3_mantis.probe import SharedPhaseLinearProbe, train_probe
import copy

from f3_mantis.spec import MANTIS_V2_SPEC

from conftest import make_tensor

SMALL_BATCH = copy.deepcopy(MANTIS_V2_SPEC)
SMALL_BATCH["training"]["batch_size"] = 32      # 400 toy rows: the registered 2048 would give one step per epoch


CHANNELS = [f"ch{i}" for i in range(10)]


def _split(n, seed, channels=10, static_dim=3, synthetic=0):
    rng = np.random.default_rng(seed)
    y = rng.integers(0, 3, size=n)
    dyn = make_tensor(n, channels, seed=seed)
    dyn += (y[:, None, None] * np.linspace(0.5, 2.0, 4)[None, :, None]).astype(np.float32)
    split = {"dynamic": dyn, "static": rng.normal(size=(n, static_dim)).astype(np.float32), "y": y,
             "row_ids": np.array([f"s{seed}_{i}" for i in range(n)]), "channel_names": CHANNELS[:channels]}
    if synthetic:
        split["is_synthetic"] = np.r_[np.zeros(n - synthetic, bool), np.ones(synthetic, bool)]
    return split


def _balanced(train, synth, real_keep=None, scale=1.0):
    keep = len(train["y"]) if real_keep is None else real_keep
    out = {k: np.concatenate([train[k][:keep], synth[k]]) for k in ("dynamic", "static", "y")}
    out["dynamic"] = (out["dynamic"] * scale).astype(np.float32)
    out["row_ids"] = np.concatenate([train["row_ids"][:keep], np.array([f"syn_{i}" for i in range(len(synth["y"]))])])
    out["is_synthetic"] = np.r_[np.zeros(keep, bool), np.ones(len(synth["y"]), bool)]
    out["channel_names"] = train["channel_names"]
    return out


def _common(tmp_path, backbone, **extra):
    common = dict(task="CQ", window="W1", num_classes=3, backbone=backbone, store_root=str(tmp_path / "cache"),
                  device="cpu", allow_random_backbone=True)
    common.update(extra)
    return common


def test_metrics_reference_values():
    y = np.array([0, 0, 1, 2]); p = np.array([0, 1, 1, 1])
    assert macro_f1(y, p, 3) == pytest.approx((2 / 3 + 0.5 + 0.0) / 3)   # class 2 never predicted -> 0
    logits = np.log(np.array([[0.7, 0.2, 0.1], [0.1, 0.8, 0.1]]))
    assert cross_entropy_from_logits(logits, np.array([0, 1])) == pytest.approx(-(np.log(0.7) + np.log(0.8)) / 2)


def test_probe_forward_shapes_and_phase_one_hot():
    model = SharedPhaseLinearProbe(embedding_dim=6, static_dim=2, num_classes=3)
    z, s = torch.randn(5, 4, 6), torch.randn(5, 2)
    assert model(z, s).shape == (5, 4, 3)
    assert model(z[:, 2:3], s, phase_index=[2]).shape == (5, 1, 3)
    model.eval()
    assert torch.allclose(model(z, s)[:, 2], model(z[:, 2:3], s, phase_index=[2])[:, 0], atol=1e-6)


def test_train_probe_selection_rule_and_determinism():
    rng = np.random.default_rng(0)
    def feats(n):
        y = rng.integers(0, 3, n)
        z = rng.normal(size=(n, 4, 8)).astype(np.float16)
        z[:, :, 0] += (2.0 * y[:, None]).astype(np.float16)
        return z, rng.normal(size=(n, 2)).astype(np.float32), y
    ztr, str_, ytr = feats(400); zva, sva, yva = feats(200)
    a = train_probe(ztr, str_, ytr, zva, sva, yva, num_classes=3, seed=42, spec=SMALL_BATCH)
    b = train_probe(ztr, str_, ytr, zva, sva, yva, num_classes=3, seed=42, spec=SMALL_BATCH)
    for (ka, va), (kb, vb) in zip(a["model"].state_dict().items(), b["model"].state_dict().items()):
        assert ka == kb and torch.equal(va, vb)
    hist = a["history"]
    best = max(hist, key=lambda h: (h["validation_macro_f1_mean_p1_p4"], -h["validation_cross_entropy_mean_p1_p4"]))
    assert a["best_epoch"] == best["epoch"]
    patience = MANTIS_V2_SPEC["training"]["early_stopping_patience"]
    assert len(hist) <= MANTIS_V2_SPEC["training"]["max_epochs"]
    if a["early_stopped"]:
        assert len(hist) - a["best_epoch"] == patience
    assert a["selection_key"]["validation_macro_f1_mean_p1_p4"] > 0.6


def test_run_cell_imputer_then_balanced_reuses_level_a(tmp_path, backbone):
    common = _common(tmp_path, backbone)
    val, test = _split(80, 2), _split(80, 3)
    train_v1 = _split(160, 1)
    r1 = run_cell(pipeline="V1", imputer="V1", seed=42, train=train_v1, validation=val, test=test,
                  out_dir=str(tmp_path / "V1"), **common)
    assert r1["record"]["cache_mode"] == "LEVEL_A" and r1["test_probabilities"].shape == (80, 4, 3)
    assert r1["record"]["adapter_fit_rows_match"] and r1["record"]["adapter"]["fit_order"] == "row_id"
    train_v2 = _balanced(train_v1, _split(40, 9))
    r2 = run_cell(pipeline="V2", imputer="V1", seed=42, train=train_v2, validation=val, test=test,
                  out_dir=str(tmp_path / "V2"), **common)
    rec = r2["record"]
    assert rec["cache_mode"] == "LEVEL_A_PLUS_B"
    assert rec["cache_reuse"] == {"REAL_TRAIN": True, "VALIDATION": True, "TEST": True, "SYNTH_TRAIN": False}
    assert rec["adapter"]["digest"] == r1["record"]["adapter"]["digest"] and rec["encoder_digest"] == r1["record"]["encoder_digest"]
    assert np.isfinite(r2["test_probabilities"]).all()
    np.testing.assert_allclose(r2["test_probabilities"].sum(axis=-1), 1.0, rtol=1e-5)
    again = run_cell(pipeline="V2", imputer="V1", seed=42, train=train_v2, validation=val, test=test,
                     out_dir=str(tmp_path / "V2_again"), **common)
    assert again["record"]["cache_reuse"]["SYNTH_TRAIN"] is True
    assert np.array_equal(again["test_probabilities"], r2["test_probabilities"])


def test_run_cell_balanced_without_adapter_is_refused(tmp_path, backbone):
    train = _split(60, 1, synthetic=10)
    with pytest.raises(RuntimeError, match="imputer-only"):
        run_cell(task="LO", window="W2", pipeline="V6", imputer="V5", seed=43, num_classes=3, train=train,
                 validation=_split(30, 2), test=_split(30, 3), backbone=backbone,
                 store_root=str(tmp_path / "cache"), out_dir=str(tmp_path / "o"), allow_random_backbone=True)


def test_run_cell_refuses_a_random_backbone_by_default(tmp_path, backbone):
    with pytest.raises(RuntimeError, match="random weights"):
        run_cell(task="CQ", window="W1", pipeline="V1", imputer="V1", seed=42, num_classes=3, train=_split(60, 1),
                 validation=_split(30, 2), test=_split(30, 3), backbone=backbone,
                 store_root=str(tmp_path / "cache"), out_dir=str(tmp_path / "o"))


def test_regenerated_synthetic_rows_stop_the_run(tmp_path, backbone):
    """Level B is verified like level A: same synthetic ids with new values or fewer rows are never reused."""
    common = _common(tmp_path, backbone)
    val, test, train = _split(60, 2), _split(60, 3), _split(120, 1)
    run_cell(pipeline="V1", imputer="V1", seed=42, train=train, validation=val, test=test, out_dir=str(tmp_path / "a"), **common)
    synth = _split(30, 9)
    run_cell(pipeline="V2", imputer="V1", seed=42, train=_balanced(train, synth), validation=val, test=test,
             out_dir=str(tmp_path / "b"), **common)
    regenerated = dict(synth, dynamic=(synth["dynamic"] * 5.0 + 3.0).astype(np.float32), y=(synth["y"] + 1) % 3)
    with pytest.raises(RuntimeError, match="other rows or values"):
        run_cell(pipeline="V2", imputer="V1", seed=42, train=_balanced(train, regenerated), validation=val, test=test,
                 out_dir=str(tmp_path / "c"), **common)
    fewer = {k: (v[:20] if isinstance(v, np.ndarray) else v) for k, v in synth.items()}
    with pytest.raises(RuntimeError, match="other rows or values"):
        run_cell(pipeline="V2", imputer="V1", seed=42, train=_balanced(train, fewer), validation=val, test=test,
                 out_dir=str(tmp_path / "d"), **common)


def test_cell_train_fallback_is_verified(tmp_path, backbone):
    common = _common(tmp_path, backbone)
    val, test, train = _split(60, 2), _split(60, 3), _split(120, 1)
    run_cell(pipeline="V1", imputer="V1", seed=42, train=train, validation=val, test=test, out_dir=str(tmp_path / "a"), **common)
    synth = _split(30, 9)
    r = run_cell(pipeline="V3", imputer="V1", seed=42, train=_balanced(train, synth, real_keep=100), validation=val,
                 test=test, out_dir=str(tmp_path / "b"), **common)
    assert r["record"]["cache_mode"] == "CELL_TRAIN_FALLBACK" and r["record"]["cache_reuse"]["CELL_TRAIN"] is False
    with pytest.raises(RuntimeError, match="other rows or values"):
        run_cell(pipeline="V3", imputer="V1", seed=42, train=_balanced(train, synth, real_keep=100, scale=3.0),
                 validation=val, test=test, out_dir=str(tmp_path / "c"), **common)


def test_other_backbone_weights_never_reuse_the_cache(tmp_path, backbone):
    from f3_mantis.encoder import load_frozen_mantis

    torch.manual_seed(3)
    other = load_frozen_mantis(pretrained=False)
    val, test, train = _split(60, 2), _split(60, 3), _split(120, 1)
    a = run_cell(pipeline="V1", imputer="V1", seed=42, train=train, validation=val, test=test,
                 out_dir=str(tmp_path / "a"), **_common(tmp_path, backbone))
    b = run_cell(pipeline="V1", imputer="V1", seed=42, train=train, validation=val, test=test,
                 out_dir=str(tmp_path / "b"), **_common(tmp_path, other))
    assert a["record"]["encoder_digest"] != b["record"]["encoder_digest"]
    assert b["record"]["cache_reuse"] == {"VALIDATION": False, "TEST": False, "REAL_TRAIN": False}
    assert not np.array_equal(a["test_probabilities"], b["test_probabilities"])
    pin = {"weights_sha256_truncated": backbone.f3_weights_sha256}
    with pytest.raises(RuntimeError, match="backbone_pin"):
        run_cell(pipeline="V1", imputer="V1", seed=42, train=train, validation=val, test=test,
                 out_dir=str(tmp_path / "c"), backbone_pin=pin, **_common(tmp_path, other))


def test_adapter_root_is_keyed_and_verified(tmp_path, backbone):
    common = _common(tmp_path, backbone, adapter_dir=str(tmp_path / "adapters"))
    del common["window"]
    w1 = run_cell(window="W1", pipeline="V1", imputer="V1", seed=42, train=_split(120, 1), validation=_split(60, 2),
                  test=_split(60, 3), out_dir=str(tmp_path / "a"), **common)
    other = _split(120, 21)
    other["dynamic"] = (other["dynamic"] * 4.0 - 2.0).astype(np.float32)
    w2 = run_cell(window="W2", pipeline="V5", imputer="V5", seed=42, train=other, validation=_split(60, 22),
                  test=_split(60, 23), out_dir=str(tmp_path / "b"), **common)
    assert w1["record"]["adapter"]["digest"] != w2["record"]["adapter"]["digest"]
    assert (tmp_path / "adapters" / "task=CQ" / "window=W2" / "imputer=V5" / "channel_adapter.npz").exists()
    changed = _split(120, 1)
    changed["dynamic"] = (changed["dynamic"] + 0.25).astype(np.float32)        # the imputer output changed after the fit
    with pytest.raises(RuntimeError, match="fitted on other real TRAIN rows"):
        run_cell(window="W1", pipeline="V1", imputer="V1", seed=43, train=changed, validation=_split(60, 2),
                 test=_split(60, 3), out_dir=str(tmp_path / "c"), **common)


def test_channel_layout_is_checked(tmp_path, backbone):
    common = _common(tmp_path, backbone)
    val, test, train = _split(60, 2), _split(60, 3), _split(120, 1)
    with pytest.raises(ValueError, match="channel_names"):
        run_cell(pipeline="V1", imputer="V1", seed=42, train={k: v for k, v in train.items() if k != "channel_names"},
                 validation=val, test=test, out_dir=str(tmp_path / "a"), **common)
    run_cell(pipeline="V1", imputer="V1", seed=42, train=train, validation=val, test=test, out_dir=str(tmp_path / "b"), **common)
    permuted = _balanced(train, _split(30, 9))
    permuted["channel_names"] = list(reversed(train["channel_names"]))
    with pytest.raises(ValueError, match="channel layout"):
        run_cell(pipeline="V2", imputer="V1", seed=42, train=permuted, validation=dict(val, channel_names=None), test=test,
                 out_dir=str(tmp_path / "c"), **common)
