# -*- coding: utf-8 -*-
"""C2 (request 2026-11-09): the leak probe used by the audits is deterministic and the audit checks s_leak against the reference table."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from metrics_core.evaluation import PROBE_CONFIG, fit_missingness_probe, probe_environment, score_missingness_probe_auc  # noqa: E402
import vastai_audit_shared as audit  # noqa: E402


def _data(n=6000, d=14, seed=0):
    rng = np.random.default_rng(seed)
    x = (rng.random((n, d)) < 0.3).astype(float)
    y = (x[:, 0] + x[:, 1] + rng.normal(0, 0.8, n) > 0.9).astype(int) + (x[:, 2] > 0).astype(int)
    return x, y


def test_deterministic_fit_is_bitwise_repeatable_under_any_ambient_thread_count():
    from threadpoolctl import threadpool_limits
    x, y = _data()
    ref = fit_missingness_probe(x, y, seed=42, deterministic=True)
    for threads in (1, 2, 4):
        with threadpool_limits(limits=threads):
            other = fit_missingness_probe(x, y, seed=42, deterministic=True)
        assert np.array_equal(ref[1].coef_, other[1].coef_) and np.array_equal(ref[1].intercept_, other[1].intercept_)
        assert np.array_equal(ref[0].mean_, other[0].mean_)
    x2, y2 = _data(seed=1)
    assert score_missingness_probe_auc(ref, x2, y2) == score_missingness_probe_auc(other, x2, y2)


def test_probe_parameters_are_the_registered_ones():
    x, y = _data()
    _, model = fit_missingness_probe(x, y, seed=42, deterministic=True)
    assert (model.C, model.max_iter, model.tol, model.solver) == (1.0, 500, 1e-4, "lbfgs")
    assert (PROBE_CONFIG["C"], PROBE_CONFIG["max_iter"], PROBE_CONFIG["tol"], PROBE_CONFIG["solver"]) == (1.0, 500, 1e-4, "lbfgs")
    # the default (non-audit) mode keeps the same estimator parameters
    _, model2 = fit_missingness_probe(x, y, seed=42)
    assert (model2.C, model2.max_iter, model2.tol, model2.solver) == (1.0, 500, 1e-4, "lbfgs")


def test_environment_record_names_the_libraries():
    env = probe_environment()
    assert {"python", "numpy", "scipy", "scikit_learn", "threadpools"} <= set(env)


def _canonical(values):
    rows = [{"window_id": w, "eval_split": s, "phase_id": p, "s_leak": v} for (w, s, p), v in values.items()]
    return pd.DataFrame(rows)


def test_reference_assertion_accepts_equal_values_and_rejects_differences():
    ref_values = {("W1", "TEST", "P1"): 0.406528, ("W1", "TEST", "P2"): 0.381529}
    ref = _canonical(ref_values)
    report = audit.assert_s_leak_matches_reference(_canonical(ref_values).assign(parent_pipeline="V0"), ref, 1e-9)
    assert report["checked_cells"] == 2 and report["max_abs_diff"] == 0.0
    shifted = _canonical({k: v + 1e-6 for k, v in ref_values.items()})
    with pytest.raises(RuntimeError, match="not reproducible"):
        audit.assert_s_leak_matches_reference(shifted, ref, 1e-9)
    assert audit.assert_s_leak_matches_reference(shifted, ref, 1e-5)["max_abs_diff"] > 0          # a looser tolerance is explicit
    with pytest.raises(RuntimeError, match="lacks cells"):
        audit.assert_s_leak_matches_reference(_canonical({("W2", "TEST", "P1"): 0.1}), ref, 1e-9)
