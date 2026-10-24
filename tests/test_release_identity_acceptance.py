"""Exporters accept ledgered legacy identities and fail closed for unknown ones."""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = {
    "release_id": "CQ_V2_2",
    "split_registry_id": "split_registry_v2_2_overlap_audit_v1_r2",
    "split_version": "v2_2",
    "phase_version": "wide_prefix_v2_2",
}
ACCEPTED = {"sha256:current": "CURRENT", "sha256:legacy": "LEGACY_WITH_LINEAGE"}


def _import_with_modal_stub(name: str):
    """Import an app module without requiring the Modal SDK at test time."""
    stub = types.ModuleType("modal")

    class Image:
        @staticmethod
        def debian_slim(**_):
            return Image()

        def __getattr__(self, _name):
            return lambda *_, **__: self

    class App:
        def __init__(self, *_, **__):
            pass

        def function(self, **_):
            return lambda fn: fn

        def local_entrypoint(self):
            return lambda fn: fn

    class Volume:
        @staticmethod
        def from_name(*_, **__):
            return object()

    stub.Image, stub.App, stub.Volume = Image, App, Volume
    saved = sys.modules.get("modal")
    sys.modules["modal"] = stub
    try:
        spec = importlib.util.spec_from_file_location(name, ROOT / "modal_jobs" / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
    finally:
        if saved is None:
            sys.modules.pop("modal", None)
        else:
            sys.modules["modal"] = saved
    return module


@pytest.fixture(scope="module")
def exporter():
    return _import_with_modal_stub("export_cq_rnn_facts")


def test_other_release_is_skipped_without_identity_check(exporter) -> None:
    manifest = {**SPEC, "release_id": "CQ_V1", "data_release_id": "sha256:anything"}
    assert exporter._identity_class(manifest, release_spec=SPEC, accepted_identities=ACCEPTED) is None


@pytest.mark.parametrize("identity,label", list(ACCEPTED.items()))
def test_known_identities_are_classified_not_dropped(exporter, identity: str, label: str) -> None:
    manifest = {**SPEC, "data_release_id": identity}
    assert exporter._identity_class(manifest, release_spec=SPEC, accepted_identities=ACCEPTED) == label


@pytest.mark.parametrize("identity", ["sha256:unknown", "", None])
def test_unknown_or_absent_active_identity_fails_closed(exporter, identity: str | None) -> None:
    manifest = {**SPEC, "data_release_id": identity}
    with pytest.raises(ValueError, match="unknown"):
        exporter._identity_class(manifest, release_spec=SPEC, accepted_identities=ACCEPTED)
