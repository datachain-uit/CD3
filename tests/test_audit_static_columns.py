"""The static-column audit must expose exactly what fit_layout selects and flag offering attributes."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import audit_static_columns as audit_mod  # noqa: E402


def synthetic_frame(rows: int, seed: int, offering_shift: float = 0.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    offerings = rng.integers(0, 20, rows)
    offering_attr = (offerings * 1000.0 + 7.0).astype("float32")           # constant inside each offering
    duration = (offerings % 4 * 86400.0 + offering_shift).astype("float32")  # offering attribute that drives the label
    label = np.where(offerings % 4 == 0, "E", np.where(offerings % 4 == 1, "G", "I/D"))
    values: dict[str, object] = {
        "enrollment_id": [f"e{n}" for n in range(rows)],
        "offering_id": [f"o{n}" for n in offerings],
        "LO_performance_label_3": label,
        "static_row_noise": rng.normal(size=rows).astype("float32"),
        "static_offering_attr": offering_attr,
        "window_duration_seconds": duration,
        "static_constant": np.ones(rows, dtype="float32"),
        "split_rule_version": ["v3_1"] * rows,                                # identity/provenance since e17ae6e
        "label_threshold_set": ["CATALOG_NORMALIZED_PRIMARY_V3_1"] * rows,    # non-numeric -> never in the tensor
        "context__audit_only": rng.normal(size=rows).astype("float32"),       # context__ prefix -> excluded
    }
    for phase in range(1, 5):
        values[f"phase_available_P{phase}"] = np.ones(rows, dtype="float32")
        for modality in ("video", "problem", "comment"):
            values[f"{modality}_observed_mask_P{phase}"] = np.ones(rows, dtype="float32")
        for base in ("video_count", "problem_count"):
            values[f"{base}_P{phase}"] = rng.normal(size=rows).astype("float32")
            values[f"missing__{base}_P{phase}"] = np.zeros(rows, dtype="float32")
    return pd.DataFrame(values)


def test_audit_reports_the_selected_static_set_and_flags(tmp_path) -> None:
    train = synthetic_frame(2000, seed=1)
    evals = {"TEST": synthetic_frame(600, seed=2, offering_shift=5 * 86400.0)}
    allowlist = {"task": "LO", "allowed": ["static_row_noise"], "denied": ["window_duration_seconds"]}
    report = audit_mod.audit(train, "LO", evals, allowlist)
    summary = report["summary"]
    assert summary["layout_mode"].startswith("use_masks=True")
    assert summary["static_columns"] == ["static_constant", "static_offering_attr", "static_row_noise", "window_duration_seconds"]
    assert "label_threshold_set" in summary["non_numeric_columns_outside_tensor"]
    assert {"offering_id", "split_rule_version"} <= set(summary["identity_columns_present_in_frame"])
    by = {r["column"]: r for r in report["columns"]}
    assert "CONSTANT" in by["static_constant"]["flags"]
    assert "OFFERING_ATTRIBUTE" in by["static_offering_attr"]["flags"]
    assert by["static_offering_attr"]["icc_offering"] > 0.99
    assert "OFFERING_ATTRIBUTE" in by["window_duration_seconds"]["flags"]
    assert "LABEL_ASSOCIATED" in by["window_duration_seconds"]["flags"]
    assert by["window_duration_seconds"]["allowlist_status"] == "DENIED"
    assert "SHIFT_VS_TRAIN" in by["window_duration_seconds"]["flags"]
    assert by["static_row_noise"]["allowlist_status"] == "ALLOWED"
    assert "OFFERING_ATTRIBUTE" not in by["static_row_noise"]["flags"]
    assert by["static_row_noise"]["nmi_label"] < audit_mod.THRESHOLDS["nmi_label"]
    assert by["static_offering_attr"]["allowlist_status"] == "UNLISTED"
    assert summary["flag_counts"]["UNLISTED"] == 2 and summary["flag_counts"]["DENIED"] == 1
    table = audit_mod.markdown_table(report)
    assert "window_duration_seconds" in table and "DENIED" in table


def test_cli_strict_fails_on_unlisted_columns(tmp_path) -> None:
    train_path, out_path = tmp_path / "train.parquet", tmp_path / "audit.json"
    synthetic_frame(500, seed=3).to_parquet(train_path, index=False)
    assert audit_mod.main(["--task", "LO", "--train", str(train_path), "--out", str(out_path)]) == 0
    report = json.loads(out_path.read_text(encoding="utf-8"))
    assert report["summary"]["n_static_columns"] == 4
    assert audit_mod.main(["--task", "LO", "--train", str(train_path), "--out", str(out_path), "--strict"]) == 1
    allow = tmp_path / "allow.json"
    allow.write_text(json.dumps({"task": "LO", "allowed": ["static_constant", "static_offering_attr", "static_row_noise",
                                                              "window_duration_seconds"]}), encoding="utf-8")
    assert audit_mod.main(["--task", "LO", "--train", str(train_path), "--out", str(out_path), "--strict",
                           "--allowlist", str(allow)]) == 0


def test_registry_allowlist_matches_the_static_feature_contract() -> None:
    from LO.registries import STATIC_FEATURE_CONTRACT
    from model.data import IDENTITY_OR_PROVENANCE
    allow = audit_mod.registry_allowlist("LO")
    fields = STATIC_FEATURE_CONTRACT["fields"]
    assert len(fields) == 15 and len(allow["allowed"]) == 14 and allow["denied"] == ["split_rule_version"]
    assert fields["split_rule_version"]["disposition"] == "EXCLUDE" and "split_rule_version" in IDENTITY_OR_PROVENANCE
    assert set(STATIC_FEATURE_CONTRACT["course_fingerprint_fields"]) <= set(allow["allowed"])
    assert all(fields[n]["grain"] == "COURSE" for n in STATIC_FEATURE_CONTRACT["course_fingerprint_fields"])
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    import audit_prefix_validation_alignment as align_mod
    assert set(align_mod.STATIC_FIELD_CONTRACT) == set(fields)
