# -*- coding: utf-8 -*-
"""Request 2026-11-13 items 1.1 and 1.2: the audit copies the reference s_leak into canonical_s_leak (refit kept as a diagnostic) and records the probe thread mode."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from metrics_core.evaluation import probe_environment, probe_mode_record, s_leak_from_probe  # noqa: E402
import vastai_audit_shared as audit  # noqa: E402

KEYS = ["window_id", "eval_split", "phase_id"]


def _canonical(offset=0.0, auc_values=None):
    rows = []
    aucs = auc_values or [0.62, 0.71, 0.55, 0.9, 0.5, 0.47]
    i = 0
    for w in ("W1", "W2"):
        for split in ("TEST", "VALIDATION"):
            for phase in ("P1", "P2"):
                auc = aucs[i % len(aucs)] + offset
                i += 1
                rows.append({"task": "CQ", "window_id": w, "parent_pipeline": "V0", "eval_split": split, "phase_id": phase,
                             "s_leak_probe_auc": auc, "s_leak": s_leak_from_probe(auc), "probe_mode": "deterministic_single_thread", "probe_threads": 1})
    return pd.DataFrame(rows)


def test_copy_reference_equals_reference_and_keeps_refit_as_diagnostic():
    reference = _canonical().loc[:, KEYS + ["s_leak"]].drop_duplicates()
    refit = _canonical(offset=2e-5)  # the single-thread fit lands slightly off the table
    out, report = audit.apply_reference_s_leak(refit, reference)
    merged = out.merge(reference.rename(columns={"s_leak": "ref"}), on=KEYS)
    assert (merged["s_leak"] - merged["ref"]).abs().max() == 0.0
    assert report["mode"] == "COPY_REFERENCE" and report["max_abs_diff"] == 0.0
    assert report["refit_max_abs_diff"] > 1e-6 and (out["s_leak_refit_abs_diff"] > 0).any()
    assert (out["s_leak_source"] == "REFERENCE_TABLE_COPY").all()
    # auc follows the copied s_leak where s_leak < 1 (auc = 1 - s_leak / 2)
    below = out["s_leak"] < 1.0
    assert np.allclose(out.loc[below, "s_leak_probe_auc"], 1.0 - out.loc[below, "s_leak"] / 2.0)
    # where the reference is 1 the refit auc is kept (not recoverable)
    assert (out.loc[~below, "s_leak_probe_auc"] == out.loc[~below, "s_leak_probe_auc_refit"]).all()
    # the copied canonical table passes the 1e-9 identity check (check 38)
    audit.assert_s_leak_matches_reference(out, reference, 1e-9)


def test_copy_reference_stops_on_missing_or_ambiguous_reference():
    reference = _canonical().loc[:, KEYS + ["s_leak"]].drop_duplicates()
    with pytest.raises(RuntimeError, match="lacks cells"):
        audit.apply_reference_s_leak(_canonical(), reference.iloc[:-1])
    ambiguous = pd.concat([reference, reference.iloc[[0]].assign(s_leak=0.123)], ignore_index=True)
    with pytest.raises(RuntimeError, match="several values"):
        audit.apply_reference_s_leak(_canonical(), ambiguous)


def test_probe_mode_is_recorded():
    det = probe_mode_record(True)
    assert det == {"probe_mode": "deterministic_single_thread", "probe_threads": 1}
    multi = probe_mode_record(False)
    assert multi["probe_mode"] == "default_multithread" and (multi["probe_threads"] is None or multi["probe_threads"] >= 1)
    env = probe_environment()
    assert "threadpools" in env and set(env) >= {"python", "numpy", "scipy", "scikit_learn", "platform"}
