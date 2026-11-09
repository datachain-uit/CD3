# -*- coding: utf-8 -*-
"""Contract tests of tools/mantis_zstd_dedup_store_20261107.DedupZstdStore (request 2026-11-09, D2; check 37 (h)).

The compressed store replaces EmbeddingStore for the Mantis grids, so it must keep the identity contract of the registered store:
every entry records input_sha256, adapter_digest, encoder_digest, encoder_fingerprint and backbone_pin; the round trip is lossless;
hashes are checked on open; ensure()/reusable() behave as before.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from f3_mantis.adapter import ChannelPCAAdapter  # noqa: E402
from f3_mantis.encoder import MantisPrefixEncoder  # noqa: E402
from f3_mantis.store import CacheKey, EmbeddingStore, gather_rows, input_sha256  # noqa: E402
from mantis_zstd_dedup_store_20261107 import DedupZstdStore  # noqa: E402

from conftest import make_tensor  # noqa: E402

PIN = {"repo": "paris-noah/MantisV2", "revision": "test", "weights_sha256_truncated": "0" * 16}


def _setup(backbone, rows=40, channels=6, seed=8):
    x = make_tensor(rows, channels, seed=seed)
    adapter = ChannelPCAAdapter(3).fit(x)
    enc = MantisPrefixEncoder(backbone, adapter, device="cpu", microbatch_sequences=48)
    ids = np.array([f"e{i}" for i in range(rows)])
    key = CacheKey("CQ", "W1", "V1", adapter.digest(), enc.fingerprint_digest, "REAL_TRAIN")
    return x, ids, adapter, enc, key


def test_round_trip_is_lossless_and_equals_the_registered_store(tmp_path, backbone):
    x, ids, _, enc, key = _setup(backbone)
    DedupZstdStore(tmp_path / "z").write(key, enc, x, ids, backbone_pin=PIN)
    EmbeddingStore(tmp_path / "r").write(key, enc, x, ids, backbone_pin=PIN)
    zrows, zids, _ = DedupZstdStore(tmp_path / "z").open(key, verify=True)
    rrows, rids, _ = EmbeddingStore(tmp_path / "r").open(key, verify=True)
    assert np.array_equal(zids, rids)
    assert zrows.shape == np.asarray(rrows).shape and zrows.dtype == np.asarray(rrows).dtype
    assert np.array_equal(zrows[np.arange(len(zrows))], np.asarray(rrows))      # byte-exact float16 content
    assert np.array_equal(zrows[np.arange(len(zrows))], enc.encode(x))


def test_manifest_records_the_full_identity(tmp_path, backbone):
    x, ids, adapter, enc, key = _setup(backbone)
    manifest = DedupZstdStore(tmp_path).write(key, enc, x, ids, backbone_pin=PIN)
    assert manifest["input_sha256"] == input_sha256(x, ids)
    assert manifest["adapter_digest"] == adapter.digest() == key.adapter_digest
    assert manifest["encoder_digest"] == enc.fingerprint_digest == key.encoder_digest
    assert manifest["encoder_fingerprint"] == enc.fingerprint()
    assert manifest["backbone_pin"] == PIN
    assert manifest["format"] == "deduplicated_zstd_rows_v1" and manifest["rows"] == 40 and manifest["embedding_dim"] == 3 * 512
    for field in ("frames_sha256", "index_sha256", "row_ids_sha256"):
        assert len(manifest[field]) == 64
    on_disk = json.loads((DedupZstdStore(tmp_path).path(key) / "manifest.json").read_text(encoding="utf-8"))
    assert on_disk["input_sha256"] == manifest["input_sha256"] and on_disk["key"]["encoder_digest"] == key.encoder_digest


def test_identical_rows_are_stored_once_and_indexing_keeps_the_requested_order(tmp_path, backbone):
    base = make_tensor(10, 6, seed=3)
    x = np.concatenate([base, base, base[:4]])                    # 24 rows, only 10 distinct
    ids = np.array([f"r{i}" for i in range(len(x))])
    adapter = ChannelPCAAdapter(3).fit(base)
    enc = MantisPrefixEncoder(backbone, adapter, device="cpu", microbatch_sequences=48)
    key = CacheKey("CQ", "W1", "V1", adapter.digest(), enc.fingerprint_digest, "REAL_TRAIN")
    manifest = DedupZstdStore(tmp_path).write(key, enc, x, ids, backbone_pin=PIN)
    assert manifest["unique_rows"] <= 10 < manifest["rows"] == 24
    rows, _, _ = DedupZstdStore(tmp_path).open(key)
    wanted = np.array([23, 0, 0, 11, 5, 23])
    full = enc.encode(x)
    assert np.array_equal(rows[wanted], full[wanted])              # order and repeats of the request are kept
    with pytest.raises(IndexError):
        rows[np.array([24])]


def test_open_verifies_hashes_and_refuses_overwrite(tmp_path, backbone):
    x, ids, _, enc, key = _setup(backbone)
    store = DedupZstdStore(tmp_path)
    store.write(key, enc, x, ids, backbone_pin=PIN)
    with pytest.raises(FileExistsError):
        store.write(key, enc, x, ids, backbone_pin=PIN)           # never overwrite a partial or complete entry
    frames = store.path(key) / "frames.bin"
    raw = bytearray(frames.read_bytes()); raw[len(raw) // 2] ^= 0xFF; frames.write_bytes(bytes(raw))
    with pytest.raises(ValueError, match="Hash mismatch"):
        store.open(key, verify=True)
    store.open(key, verify=False)                                  # the opt-out stays available (as before)


def test_key_must_describe_the_encoder(tmp_path, backbone):
    x, ids, adapter, enc, _ = _setup(backbone)
    other = MantisPrefixEncoder(backbone, adapter, device="cpu", microbatch_sequences=96)
    wrong = CacheKey("CQ", "W1", "V1", adapter.digest(), other.fingerprint_digest, "VALIDATION")
    with pytest.raises(ValueError, match="Encoder identity mismatch"):
        DedupZstdStore(tmp_path).write(wrong, enc, x, ids)
    with pytest.raises(ValueError, match="Invalid row IDs"):
        DedupZstdStore(tmp_path).write(CacheKey("CQ", "W1", "V1", adapter.digest(), enc.fingerprint_digest, "TEST"), enc, x, np.array(["a"] * len(x)))


def test_ensure_and_reusable_are_unchanged(tmp_path, backbone):
    x, ids, _, enc, key = _setup(backbone)
    store = DedupZstdStore(tmp_path)
    emb, pos, reused, manifest = store.ensure(key, enc, x, ids, backbone_pin=PIN)
    assert reused is False and manifest["backbone_pin"] == PIN
    assert np.array_equal(emb[pos], enc.encode(x))
    perm = np.random.default_rng(0).permutation(len(x))
    assert store.reusable(key, x[perm], ids[perm])                  # same rows in another order
    emb2, pos2, reused2, _ = store.ensure(key, enc, x[perm], ids[perm])
    assert reused2 is True and np.array_equal(emb2[pos2], enc.encode(x)[perm])
    changed = x.copy(); changed[0, 0, 0] += 1e-3
    assert not store.reusable(key, changed, ids)                    # different values -> no reuse
    with pytest.raises(RuntimeError, match="built from other rows"):
        store.ensure(key, enc, changed, ids)
    assert store.ensure(key, enc, changed, ids, strict=False) is None
    assert store.ensure(CacheKey("CQ", "W1", "V1", key.adapter_digest, key.encoder_digest, "VALIDATION"), enc, x, ids, create=False) is None
    with pytest.raises(RuntimeError, match="built from other rows"):
        store.ensure(key, enc, x[:20], ids[:20])                    # fewer rows than the entry: never gathered silently
