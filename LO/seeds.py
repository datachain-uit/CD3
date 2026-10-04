"""Shared deterministic seeds and canonical hashing for LO registries.

This small module intentionally has no project-path or runtime dependency so
``LO.registries`` can be imported by a report/export job as well as run as a
stand-alone registry writer.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


SEED_PREPROCESS = 20260922


def sha256_of(value: Any) -> str:
    """Return a stable content hash for a JSON-serialisable registry value."""
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), default=str).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"
