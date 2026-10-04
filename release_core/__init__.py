"""Immutable release specifications shared by every execution stage."""

from .contracts import RELEASE_SPECS, default_release_id, resolve_release, validate_release_manifest

__all__ = ["RELEASE_SPECS", "default_release_id", "resolve_release", "validate_release_manifest"]
