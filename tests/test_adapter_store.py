# -*- coding: utf-8 -*-
import numpy as np
import pytest

from f3_mantis.adapter import ChannelPCAAdapter
from f3_mantis.encoder import MantisPrefixEncoder
from f3_mantis.store import CacheKey, EmbeddingStore, StackedFeatures, gather_rows, input_sha256

from conftest import make_tensor


def test_pca_is_deterministic_ordered_and_signed():
    x = make_tensor(200, 10, seed=3)
    a = ChannelPCAAdapter(n_components=4).fit(x)
    b = ChannelPCAAdapter(n_components=4).fit(x.copy())
    assert a.digest() == b.digest()
    assert np.all(np.diff(a.explained_variance_) <= 1e-12)
    for j in range(4):
        i = int(np.argmax(np.abs(a.components_[:, j])))
        assert a.components_[i, j] > 0
    proj = a.transform(x)
    assert proj.shape == (200, 4, 4) and proj.dtype == np.float32


def test_pca_ignores_synthetic_rows():
    x = make_tensor(100, 8, seed=4)
    synth = make_tensor(40, 8, seed=5) * 10.0
    both = np.concatenate([x, synth])
    mask = np.r_[np.ones(100, bool), np.zeros(40, bool)]
    assert ChannelPCAAdapter(3).fit(x).digest() == ChannelPCAAdapter(3).fit(both, real_mask=mask).digest()


def test_pca_sample_uses_registered_seed():
    x = make_tensor(300, 6, seed=6)
    a = ChannelPCAAdapter(3, sample_rows_max=100).fit(x)
    b = ChannelPCAAdapter(3, sample_rows_max=100).fit(x)
    c = ChannelPCAAdapter(3, sample_rows_max=100, sample_seed=1).fit(x)
    assert a.digest() == b.digest() != c.digest() and a.n_rows_fit_ == 100


def test_adapter_save_load_roundtrip(tmp_path):
    a = ChannelPCAAdapter(3).fit(make_tensor(50, 6, seed=7))
    a.save(tmp_path / "adapter")
    assert ChannelPCAAdapter.load(tmp_path / "adapter").digest() == a.digest()


def test_store_write_open_reuse(tmp_path, backbone):
    x = make_tensor(40, 6, seed=8)
    adapter = ChannelPCAAdapter(3).fit(x)
    enc = MantisPrefixEncoder(backbone, adapter, device="cpu", microbatch_sequences=48)
    store = EmbeddingStore(tmp_path)
    ids = np.array([f"e{i}" for i in range(40)])
    key = CacheKey("CQ", "W1", "V1", adapter.digest(), enc.fingerprint_digest, "REAL_TRAIN")
    manifest = store.write(key, enc, x, ids)
    assert manifest["encoder_digest"] == enc.fingerprint_digest and f"encoder={enc.fingerprint_digest[:12]}" in str(store.path(key))
    assert manifest["rows"] == 40 and manifest["embedding_dim"] == 3 * 512
    emb, stored, _ = store.open(key, verify=True)
    assert np.array_equal(np.asarray(emb), enc.encode(x))
    perm = np.random.default_rng(0).permutation(40)
    assert store.reusable(key, x[perm], ids[perm])                     # same rows in another order
    changed = x.copy(); changed[0, 0, 0] += 1e-3
    assert not store.reusable(key, changed, ids)                       # different values -> no reuse
    with pytest.raises(FileExistsError):
        store.write(key, enc, x, ids)
    pos = gather_rows(emb, stored, ids[perm])
    assert np.array_equal(np.asarray(emb)[pos], np.asarray(emb)[perm])


def test_stacked_features_preserve_order():
    a = np.arange(5 * 4 * 2, dtype=np.float16).reshape(5, 4, 2)
    b = -np.arange(3 * 4 * 2, dtype=np.float16).reshape(3, 4, 2)
    view = StackedFeatures([a, b], [np.array([4, 0, 2]), np.array([2, 1])])
    assert len(view) == 5
    got = view[np.array([4, 0, 3, 1])]
    assert np.array_equal(got[0], b[1]) and np.array_equal(got[1], a[4]) and np.array_equal(got[2], b[2])
    assert np.array_equal(got[3], a[0])


def test_input_sha256_is_order_free():
    x = make_tensor(10, 4, seed=9)
    ids = np.arange(10)
    perm = np.random.default_rng(1).permutation(10)
    assert input_sha256(x, ids) == input_sha256(x[perm], ids[perm])


def test_pca_fit_is_independent_of_row_order_given_ids():
    x = make_tensor(400, 6, seed=6)
    ids = np.array([f"e{i:04d}" for i in range(400)])
    perm = np.random.default_rng(5).permutation(400)
    for sample in (1_000_000, 150):                     # without and with the row sample
        a = ChannelPCAAdapter(3, sample_rows_max=sample).fit(x, row_ids=ids)
        b = ChannelPCAAdapter(3, sample_rows_max=sample).fit(x[perm], row_ids=ids[perm])
        assert a.digest() == b.digest() and a.fit_order_ == "row_id", sample


def test_channel_names_are_checked():
    x = make_tensor(50, 4, seed=7)
    names = ["a", "b", "c", "d"]
    adapter = ChannelPCAAdapter(2).fit(x, channel_names=names)
    adapter.check_channel_names(names)
    with pytest.raises(ValueError, match="position 1"):
        adapter.check_channel_names(["a", "c", "b", "d"])
    with pytest.raises(ValueError, match="without channel names"):
        ChannelPCAAdapter(2).fit(x).check_channel_names(names)


def test_store_keys_entries_by_encoder_and_refuses_stale_rows(tmp_path, backbone):
    x = make_tensor(30, 6, seed=10)
    ids = np.array([f"e{i}" for i in range(30)])
    adapter = ChannelPCAAdapter(3).fit(x)
    enc = MantisPrefixEncoder(backbone, adapter, device="cpu", microbatch_sequences=48)
    other = MantisPrefixEncoder(backbone, adapter, device="cpu", microbatch_sequences=96)
    store = EmbeddingStore(tmp_path)
    key = CacheKey("CQ", "W1", "V1", adapter.digest(), enc.fingerprint_digest, "VALIDATION")
    key_other = CacheKey("CQ", "W1", "V1", adapter.digest(), other.fingerprint_digest, "VALIDATION")
    assert store.path(key) != store.path(key_other)
    with pytest.raises(ValueError, match="does not describe this encoder"):
        store.write(key_other, enc, x, ids)
    _, _, reused, _ = store.ensure(key, enc, x, ids)
    assert reused is False and store.ensure(key, enc, x, ids)[2] is True
    changed = x.copy(); changed[3, 1, 2] += 0.5
    with pytest.raises(RuntimeError, match="other rows or values"):
        store.ensure(key, enc, changed, ids)
    assert store.ensure(key, enc, changed, ids, strict=False) is None
    with pytest.raises(RuntimeError, match="other rows or values"):
        store.ensure(key, enc, x[:20], ids[:20])            # fewer rows than the entry: never gathered silently
