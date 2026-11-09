# -*- coding: utf-8 -*-
"""On-disk cache of F3 embeddings (computed once, reused by every epoch, seed and balancer that shares them).

Layout under ``root`` (E = digest of the encoder fingerprint: backbone weights, encoding settings, precision,
microbatch, device; see ``MantisPrefixEncoder.fingerprint``)::

    task=<T>/window=<W>/imputer=<V>/adapter=<digest12>/encoder=<E12>/split=<S>/       level A (REAL_TRAIN, VALIDATION, TEST)
    task=<T>/window=<W>/imputer=<V>/adapter=<digest12>/encoder=<E12>/pipeline=<P>/seed=<s>/split=SYNTH_TRAIN/   level B
    task=<T>/window=<W>/imputer=<V>/adapter=<digest12>/encoder=<E12>/pipeline=<P>/seed=<s>/split=CELL_TRAIN/    fallback

Each leaf holds ``embeddings.npy`` (float16 memmap, rows x prefixes x D), ``row_ids.npy``, ``manifest.json``
(written last; its presence marks a complete entry) with the sha256 of the input tensor (rows sorted by id), of the
embedding file, the adapter digest, the encoder fingerprint, the specification digest, the backbone pin and the
encoder timing. Every entry, at every level, is reused only when the ids and the input sha256 of the rows asked for
equal those of the entry (``EmbeddingStore.ensure``); an entry built from other rows stops the run.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

import numpy as np

from .determinism import library_versions
from .spec import spec_digest

LEVEL_A_SPLITS = ("REAL_TRAIN", "VALIDATION", "TEST")
LEVEL_B_SPLIT = "SYNTH_TRAIN"
CELL_SPLIT = "CELL_TRAIN"     # fallback: every TRAIN row of one balanced cell when level-A reuse is not allowed


def _sha256_file(path: Path, chunk: int = 1 << 24) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def input_sha256(dynamic: np.ndarray, row_ids: Sequence) -> str:
    """sha256 of (ids, float32 values) with rows sorted by id: identical inputs give identical digests."""
    ids = np.asarray(row_ids)
    order = np.argsort(ids.astype(str), kind="stable")
    h = hashlib.sha256()
    h.update(json.dumps([str(v) for v in ids[order]]).encode("utf-8"))
    for start in range(0, len(order), 65536):
        idx = order[start:start + 65536]
        h.update(np.ascontiguousarray(dynamic[idx], dtype=np.float32).tobytes())
    return h.hexdigest()


@dataclass(frozen=True)
class CacheKey:
    task: str
    window: str
    imputer: str
    adapter_digest: str
    encoder_digest: str
    split: str
    pipeline: Optional[str] = None
    seed: Optional[int] = None

    def relative_dir(self) -> Path:
        base = (Path(f"task={self.task}") / f"window={self.window}" / f"imputer={self.imputer}"
                / f"adapter={self.adapter_digest[:12]}" / f"encoder={self.encoder_digest[:12]}")
        if self.split in LEVEL_A_SPLITS:
            if self.pipeline is not None or self.seed is not None:
                raise ValueError("level-A entries carry no pipeline or seed")
            return base / f"split={self.split}"
        if self.split in (LEVEL_B_SPLIT, CELL_SPLIT):
            if self.pipeline is None or self.seed is None:
                raise ValueError("level-B entries need the balanced pipeline and the master seed")
            return base / f"pipeline={self.pipeline}" / f"seed={int(self.seed)}" / f"split={self.split}"
        raise ValueError(f"unknown split {self.split}")


class EmbeddingStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def path(self, key: CacheKey) -> Path:
        return self.root / key.relative_dir()

    def exists(self, key: CacheKey) -> bool:
        return (self.path(key) / "manifest.json").is_file()

    def write(self, key: CacheKey, encoder, dynamic: np.ndarray, row_ids: Sequence,
              backbone_pin: Optional[dict] = None, extra: Optional[dict] = None, overwrite: bool = False,
              input_digest: Optional[str] = None) -> dict:
        leaf = self.path(key)
        if self.exists(key) and not overwrite:
            raise FileExistsError(f"cache entry exists: {leaf}")
        if key.adapter_digest != encoder.adapter.digest() or key.encoder_digest != encoder.fingerprint_digest:
            raise ValueError("the cache key does not describe this encoder (adapter digest or encoder fingerprint differ)")
        leaf.mkdir(parents=True, exist_ok=True)
        ids = np.asarray(row_ids)
        if len(ids) != dynamic.shape[0]:
            raise ValueError("row_ids and dynamic disagree on the number of rows")
        if len(np.unique(ids.astype(str))) != len(ids):
            raise ValueError("row ids must be unique within a cache entry")
        tmp = leaf / "embeddings.npy.partial"
        shape = (dynamic.shape[0], 4, encoder.embedding_dim)
        memmap = np.lib.format.open_memmap(tmp, mode="w+", dtype=np.float16, shape=shape)
        encoder.encode(dynamic, prefixes=(1, 2, 3, 4), out=memmap)
        memmap.flush()
        del memmap
        os.replace(tmp, leaf / "embeddings.npy")
        np.save(leaf / "row_ids.npy", ids.astype(str) if ids.dtype.kind in "OU" else ids)
        manifest = {
            "key": key.__dict__, "rows": int(shape[0]), "prefixes": [1, 2, 3, 4], "embedding_dim": int(shape[2]),
            "dtype": "float16", "input_sha256": input_digest or input_sha256(dynamic, ids),
            "embeddings_sha256": _sha256_file(leaf / "embeddings.npy"),
            "adapter_digest": encoder.adapter.digest(), "adapter_summary": encoder.adapter.summary(),
            "encoder_digest": encoder.fingerprint_digest, "encoder_fingerprint": encoder.fingerprint(),
            "spec_digest": spec_digest(encoder.spec), "model_revision": encoder.spec["model_revision"],
            "input_encoding": encoder.spec["input_encoding"], "backbone_pin": backbone_pin or {},
            "backbone_pretrained": bool(getattr(encoder.backbone, "f3_pretrained", True)),
            "precision": encoder.precision, "microbatch_sequences": encoder.microbatch_sequences,
            "timing": encoder.last_timing, "libraries": library_versions(),
            "created_at_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        }
        if extra:
            manifest["extra"] = extra
        (leaf / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
        return manifest

    def open(self, key: CacheKey, verify: bool = False):
        leaf = self.path(key)
        manifest = json.loads((leaf / "manifest.json").read_text(encoding="utf-8"))
        if verify and _sha256_file(leaf / "embeddings.npy") != manifest["embeddings_sha256"]:
            raise ValueError(f"embedding file changed since it was written: {leaf}")
        embeddings = np.load(leaf / "embeddings.npy", mmap_mode="r")
        row_ids = np.load(leaf / "row_ids.npy", allow_pickle=False)
        return embeddings, row_ids, manifest

    def reusable(self, key: CacheKey, dynamic: np.ndarray, row_ids: Sequence, input_digest: Optional[str] = None) -> bool:
        """True when the entry of ``key`` was built from exactly these rows and values (ids and input sha256 agree)."""
        if not self.exists(key):
            return False
        _, stored_ids, manifest = self.open(key)
        if manifest.get("adapter_digest") != key.adapter_digest or manifest.get("encoder_digest") != key.encoder_digest:
            return False
        if len(stored_ids) != len(row_ids):
            return False
        if set(map(str, stored_ids)) != set(map(str, row_ids)):
            return False
        return manifest["input_sha256"] == (input_digest or input_sha256(dynamic, row_ids))

    def ensure(self, key: CacheKey, encoder, dynamic: np.ndarray, row_ids: Sequence, *,
               backbone_pin: Optional[dict] = None, create: bool = True, strict: bool = True,
               input_digest: Optional[str] = None):
        """Open the entry of ``key`` built from exactly these rows, or write it.

        Returns ``(embeddings, positions of row_ids in the entry, reused, manifest)``. Returns None when the entry
        is missing and ``create`` is False, or when it holds other rows and ``strict`` is False. With
        ``strict=True`` an entry built from other rows (ids or values) stops the run: it means that a release view,
        an imputer or an S2 artefact changed after the entry was written.
        """
        digest = input_digest or input_sha256(dynamic, row_ids)
        if self.exists(key):
            if self.reusable(key, dynamic, row_ids, input_digest=digest):
                embeddings, stored_ids, manifest = self.open(key)
                return embeddings, gather_rows(embeddings, stored_ids, row_ids), True, manifest
            if strict:
                raise RuntimeError(f"cache entry {self.path(key)} exists but was built from other rows or values (ids or "
                                   "input sha256 differ); find out why the rows changed, then use a fresh cache root or "
                                   "move the stale entry away before running again")
            return None
        if not create:
            return None
        self.write(key, encoder, dynamic, row_ids, backbone_pin=backbone_pin, input_digest=digest)
        embeddings, stored_ids, manifest = self.open(key)
        return embeddings, gather_rows(embeddings, stored_ids, row_ids), False, manifest


def gather_rows(embeddings: np.ndarray, stored_ids: np.ndarray, wanted_ids: Sequence) -> np.ndarray:
    """Positions of ``wanted_ids`` in a cache entry (raises if an id is missing)."""
    index = {str(v): i for i, v in enumerate(stored_ids)}
    try:
        return np.fromiter((index[str(v)] for v in wanted_ids), dtype=np.int64, count=len(wanted_ids))
    except KeyError as missing:
        raise KeyError(f"row id {missing} not found in the cache entry") from None


class StackedFeatures:
    """Read-only view over several cache arrays in a fixed row order (real TRAIN rows then synthetic rows)."""

    def __init__(self, parts: Sequence[np.ndarray], positions: Sequence[np.ndarray]):
        if len(parts) != len(positions):
            raise ValueError("parts and positions must align")
        self.parts = list(parts)
        self.positions = [np.asarray(p, dtype=np.int64) for p in positions]
        self.offsets = np.cumsum([0] + [len(p) for p in self.positions])
        dims = {tuple(part.shape[1:]) for part in self.parts}
        if len(dims) != 1:
            raise ValueError("cache parts disagree on (prefixes, embedding_dim)")
        self.shape = (int(self.offsets[-1]),) + dims.pop()
        self.dtype = self.parts[0].dtype

    def __len__(self) -> int:
        return self.shape[0]

    def __getitem__(self, idx) -> np.ndarray:
        idx = np.asarray(idx, dtype=np.int64)
        out = np.empty((len(idx),) + self.shape[1:], dtype=self.dtype)
        which = np.searchsorted(self.offsets, idx, side="right") - 1
        for part_id in np.unique(which):
            mask = which == part_id
            local = idx[mask] - self.offsets[part_id]
            source_rows = self.positions[part_id][local]
            order = np.argsort(source_rows, kind="stable")
            values = self.parts[part_id][np.sort(source_rows)]
            restored = np.empty_like(values)
            restored[order] = values
            out[mask] = restored
        return out
