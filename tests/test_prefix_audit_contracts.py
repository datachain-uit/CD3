"""Regression tests for the audit's class convention, full scan and hash join."""
import hashlib
import pandas as pd
import pytest

from tools.audit_prefix_validation_alignment import _macro_scores, _prefix_schema_audit, _w1_p1_slice_metrics


def test_fixed_class_macro_differs_when_class_absent():
    result = _macro_scores(pd.Series(["c0", "c1"]), pd.Series(["c0", "c1"]))
    assert result["macro_f1"] == pytest.approx(2 / 3)
    assert result["macro_f1_present_classes"] == pytest.approx(1)


def test_full_scan_includes_second_file(tmp_path):
    for phase in ("P1", "P2", "P3", "P4"):
        directory = tmp_path / phase
        directory.mkdir()
        pd.DataFrame({"feature_P2": [None], "feature_P3": [None], "feature_P4": [None]}).to_parquet(directory / "a.parquet")
        pd.DataFrame({"feature_P2": [1.0 if phase == "P1" else None], "feature_P3": [None], "feature_P4": [None]}).to_parquet(directory / "b.parquet")
    result = _prefix_schema_audit(tmp_path, full_scan=True)
    assert result[0]["sample_rows_checked"] == 2
    assert result[0]["future_phase_non_null_cells_sample"] == 1


def test_prediction_slices_join_by_hash_not_order(tmp_path, monkeypatch):
    monkeypatch.setenv("TEMPO_PREDICTION_SALT", "test-only")
    digest = lambda value: hashlib.sha256(f"test-only|{value}".encode()).hexdigest()
    context = pd.DataFrame({"enrollment_id": ["a", "b"], "CQ_label_final": ["warning", "good"],
                            "temporal_strict_P1": [1, 0], "course_cohort": ["SEEN_COURSE", "UNSEEN_COURSE"]})
    root = tmp_path / "W1" / "predictions"
    root.mkdir(parents=True)
    pd.DataFrame({"enrollment_id_hash": [digest("b"), digest("a")], "window_id": ["W1"] * 2,
                  "pipeline_id": ["V0"] * 2, "model_name": ["RNN"] * 2,
                  "eval_split": ["TEST"] * 2, "phase_id": ["P1"] * 2,
                  "y_true": ["c2", "c0"], "y_pred": ["c2", "c0"]}).to_parquet(root / "test_P1.parquet")
    result = _w1_p1_slice_metrics(tmp_path, context, "CQ_label_final", {"c0": "warning", "c1": "average", "c2": "good"})
    assert set(result["row_alignment"]) == {"salted_enrollment_hash_and_label_match"}
    assert len(result) == 4
