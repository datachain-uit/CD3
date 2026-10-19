"""The static-only probe must separate 'course identity transfers to VALIDATION but not to TEST' from 'no static signal'."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import probe_static_only as probe_mod  # noqa: E402
from LO.registries import STATIC_FEATURE_CONTRACT  # noqa: E402

FINGERPRINT = STATIC_FEATURE_CONTRACT["course_fingerprint_fields"]


FINGERPRINTS = np.random.default_rng(2026).normal(size=(64, len(FINGERPRINT)))   # one random vector per course


def frame(rows: int, seed: int, *, courses: np.ndarray, course_label_rate: dict[int, tuple[float, str]]) -> pd.DataFrame:
    """Each course has a fixed random fingerprint and its own minority rate/class; TEST may override them."""
    rng = np.random.default_rng(seed)
    course = rng.choice(courses, rows)
    label = np.array(["I/D"] * rows, dtype=object)
    for c in np.unique(course):
        idx = np.flatnonzero(course == c)
        rate, minority = course_label_rate[int(c)]
        chosen = rng.choice(idx, int(round(rate * len(idx))), replace=False)
        label[chosen] = minority
    values: dict[str, object] = {"enrollment_id": [f"e{seed}_{n}" for n in range(rows)], "offering_id": [f"o{c}" for c in course],
                                 "LO_performance_label_3": label,
                                 "gender": rng.integers(0, 2, rows).astype("float32"),
                                 "window_duration_seconds": rng.normal(2e6, 3e5, rows).astype("float32")}
    for k, name in enumerate(FINGERPRINT):
        values[name] = FINGERPRINTS[course, k].astype("float32")
    for phase in range(1, 5):
        values[f"phase_available_P{phase}"] = np.ones(rows, dtype="float32")
        for modality in ("video", "problem", "comment"):
            values[f"{modality}_observed_mask_P{phase}"] = np.ones(rows, dtype="float32")
        values[f"video_count_P{phase}"] = rng.normal(size=rows).astype("float32")
        values[f"missing__video_count_P{phase}"] = np.zeros(rows, dtype="float32")
    return pd.DataFrame(values)


def test_probe_detects_course_identity_that_transfers_to_validation_only(tmp_path) -> None:
    courses = np.arange(12)
    def rates(e_courses: int, g_courses: int) -> dict[int, tuple[float, str]]:
        return {c: ((0.6, "E") if c % 3 == e_courses else (0.6, "G") if c % 3 == g_courses else (0.02, "G")) for c in courses}
    train = frame(6000, 1, courses=courses, course_label_rate=rates(0, 1))        # course identity predicts E vs G
    validation = frame(1500, 2, courses=courses, course_label_rate=rates(0, 1))   # same courses, same mapping
    test = frame(1500, 3, courses=courses, course_label_rate=rates(1, 0))         # mapping flipped: identity misleads
    report = probe_mod.run(train, {"VALIDATION": validation, "TEST": test}, "LO")
    sets = report["feature_sets"]
    assert sets["ALL_STATIC"]["n_columns"] == 13 and sets["COURSE_FINGERPRINT"]["n_columns"] == 11
    assert sets["NON_COURSE"]["columns"] == ["gender", "window_duration_seconds"]
    fp = sets["COURSE_FINGERPRINT"]["class_weight_balanced"]
    assert fp["VALIDATION"]["balanced_accuracy"] > 0.55 > fp["TEST"]["balanced_accuracy"]
    assert fp["VALIDATION"]["macro_f1"] > fp["TEST"]["macro_f1"] + 0.1
    nc = sets["NON_COURSE"]["class_weight_balanced"]
    assert abs(nc["VALIDATION"]["balanced_accuracy"] - nc["TEST"]["balanced_accuracy"]) < 0.12
    ref = report["majority_reference"]["TEST"]
    assert abs(ref["macro_f1"] - (2 * ref["class_shares"]["I/D"] / (1 + ref["class_shares"]["I/D"])) / 3) < 1e-9
    for split in ("VALIDATION", "TEST"):
        scores = fp[split]
        assert scores["macro_f1"] <= scores["macro_f1_present_classes"] + 1e-12
        assert set(scores["per_class"]) == {"I/D", "G", "E"}
    table = probe_mod.summary_table(report)
    assert "COURSE_FINGERPRINT" in table and "| TEST |" in table


def test_cli_writes_report(tmp_path) -> None:
    courses = np.arange(6)
    rates = {c: (0.1, "G" if c % 2 else "E") for c in courses}
    paths = {}
    for name, seed, rows in (("train", 4, 1500), ("validation", 5, 400), ("test", 6, 400)):
        path = tmp_path / f"{name}.parquet"
        frame(rows, seed, courses=courses, course_label_rate=rates).to_parquet(path, index=False)
        paths[name] = str(path)
    out = tmp_path / "probe.json"
    assert probe_mod.main(["--task", "LO", "--train", paths["train"], "--validation", paths["validation"],
                           "--test", paths["test"], "--out", str(out), "--sample-rows", "1000"]) == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["feature_sets"]["ALL_STATIC"]["n_train"] == 1000
    assert "TRAIN" in report["majority_reference"] and report["inputs"]["sample_rows"] == 1000
