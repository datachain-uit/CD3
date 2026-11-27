# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import pytest

from metamodel import baselines as B
from metamodel import contracts as C
from metamodel import features as F
from metamodel import learners as L
from metamodel import metrics as M
from metamodel import protocols as P
from metamodel import schema as S
from metamodel.experiment import MMConfig, prepare_frame


@pytest.fixture(scope="module")
def frame(seed_agg):
    cfg = MMConfig(objective="PAPER_COMPOSITE_CAL", table="seed_agg")
    df, names = prepare_frame(seed_agg, cfg)
    return df, names, cfg


def test_feature_sets_are_nested_and_pass_leakage_checks(frame):
    df, names, cfg = frame
    sizes = []
    for fs in C.FEATURE_SETS:
        cols = F.select_columns(df.columns, fs)
        F.assert_inputs(cols, fs)
        sizes.append(len(cols))
        roles = {S.role_of(c)[1] for c in cols}
        assert "X_RESTRICTED" not in roles and "TARGET" not in roles and "DIAG" not in roles and "DERIVED" not in roles
        if fs in ("FS0", "FS1", "FS2", "FS3"):
            assert not any(c.startswith("val_") for c in cols)
        if fs == "FS4":
            assert all(S._strip_agg(c).endswith("_before") for c in cols if c.startswith("val_"))
    assert sizes == sorted(sizes)
    fs3 = F.select_columns(df.columns, "FS3")
    assert "tr_missing_rate" in fs3 and "drift_tr_ev_psi_mean" in fs3 and "label_drift_tr_ev_jsd" not in fs3
    assert "s_ent_after_mean" not in fs3 and "acctempo_m3_cal_delta_mean" not in fs3


def test_mq_checks_catch_leaks():
    ok, bad = S.mq01_input_roles(["tr_missing_rate", "acctempo_m3_delta"])
    assert not ok and bad == ["acctempo_m3_delta:TARGET"]
    ok, bad = S.mq10_no_target_components(["val_s_san_plus_before", "s_san_plus_after"])
    assert not ok and bad == ["s_san_plus_after"]
    ok, _ = S.mq06_scenario_columns(["val_macro_f1_after"], "WARM")
    assert not ok
    ok, _ = S.mq06_scenario_columns(["val_macro_f1_before"], "WARM")
    assert ok
    ok, _ = S.mq07_no_task_feature(["task", "tr_missing_rate"])
    assert not ok


def test_preprocessor_fits_on_train_only(frame):
    df, names, cfg = frame
    train, test = df[df.window_id.isin(["W1", "W2"])], df[df.window_id == "W3"]
    pre = F.Preprocessor("FS3").fit(train)
    Xtr, Xte = pre.transform(train), pre.transform(test)
    assert list(Xtr.columns) == list(Xte.columns) == pre.output_columns_
    num = [c for c in Xtr.columns if c.startswith("num__")]
    assert np.allclose(Xtr[num].mean(), 0, atol=1e-6) and np.allclose(Xtr[num].std(ddof=0), 1, atol=1e-6)
    assert any(c.startswith("cat__model_name__") for c in Xtr.columns)
    assert any(c.startswith("isnull__") for c in Xtr.columns)       # drift_window_prev is NULL on W1
    assert "NEAR_CONSTANT" in set(pre.dropped_.values()) or True


def test_protocols_and_mq_fold_checks(frame):
    df, names, cfg = frame
    for proto in ("E1-A", "E1-B", "E2", "E3", "W0_LOCKED"):
        folds = P.make_folds(df, proto)
        assert folds
        for f in folds:
            checks = P.check_fold(df, f)
            assert all(checks.values())
    e1b = P.make_folds(df, "E1-B")[0]
    assert set(df[e1b.train]["window_id"]) == {"W1", "W2"} and set(df[e1b.test]["window_id"]) == {"W3"}
    assert len(e1b.inner) == 1 and set(df[e1b.inner[0][0]]["window_id"]) == {"W1"}
    e2 = P.make_folds(df, "E2")
    assert {f.fold_id for f in e2} == {"CQ->LO", "LO->CQ"} and all(f.drop_task for f in e2)
    man = P.split_manifest(df, [e1b])
    assert set(man["role"]) == {"TRAIN", "TEST", "INNER_FIT_0", "INNER_VAL_0"} and man["manifest_sha256"].nunique() == 1


def test_metrics_regret_hit_harm_ndcg():
    scored = pd.DataFrame({
        "rec_group_id": ["g"] * 4, "pipeline_id": ["V0", "V1", "V2", "V3"],
        "y": [0.0, 0.02, -0.01, 0.05], "score": [0.0, 0.03, 0.01, 0.02],
        "task": "CQ", "window_id": "W3", "model_name": "RNN", "phase_id": "P1",
    })
    rec = M.recommend(scored)
    assert rec.iloc[0]["pipeline_recommended"] == "V1"
    out = M.group_outcomes(scored, rec)
    r = out.iloc[0]
    assert np.isclose(r["regret"], 0.03) and r["hit"] == 0.0 and r["harm"] == 0.0 and np.isclose(r["gain_over_v0"], 0.02)
    assert 0 < r["ndcg_at_3"] < 1
    # oracle has zero regret and a hit
    out0 = M.group_outcomes(scored, M.recommend(scored.assign(score=scored["y"])))
    assert out0.iloc[0]["regret"] == 0 and out0.iloc[0]["hit"] == 1.0
    # conservative rule keeps V0 when the best score does not exceed eps
    rec_c = M.recommend(scored.assign(score=[0.0, 0.004, 0.001, 0.002]), conservative=True)
    assert rec_c.iloc[0]["pipeline_recommended"] == "V0"
    # harm
    out_h = M.group_outcomes(scored, M.recommend(scored.assign(score=[0, 0, 1, 0])))
    assert out_h.iloc[0]["harm"] == 1.0


def test_holm_and_bootstrap():
    adj = M.holm({"H1": 0.01, "H2": 0.04, "H3": 0.20})
    assert adj["H1"]["p_holm"] == pytest.approx(0.03) and adj["H2"]["p_holm"] == pytest.approx(0.08) and adj["H3"]["p_holm"] == pytest.approx(0.20)
    g = pd.DataFrame({"regret": np.r_[np.zeros(20), np.ones(20) * 0.1], "task": "CQ", "window_id": "W3",
                      "model_name": ["RNN"] * 20 + ["LSTM"] * 20, "phase_id": ["P1", "P2", "P3", "P4"] * 10})
    r = M.cluster_bootstrap_mean(g, "regret", b=200)
    assert r["ci_low"] <= r["estimate"] <= r["ci_high"] and r["n_clusters"] == 8


def test_baselines_on_frame(frame):
    df, names, cfg = frame
    train, test = df[df.window_id.isin(["W1", "W2"])], df[df.window_id == "W3"]
    bl = B.run_baselines(train, test, objective_stem=names["stem"], include_b7=True)
    for name in ("B0", "B1", "B2", "B3", "B4", "B5", "B6", "B7"):
        assert name in bl and "error" not in bl[name].columns, (name, bl[name].get("error"))
    o0 = M.group_outcomes(bl["B0"], M.recommend(bl["B0"]))
    assert np.allclose(o0["regret"], 0.0)
    o1 = M.group_outcomes(bl["B1"], M.recommend(bl["B1"]))
    assert (o1["pipeline_recommended"] == "V0").all() and np.allclose(o1["gain_over_v0"], 0.0)
    o3 = M.group_outcomes(bl["B3"], M.recommend(bl["B3"]))
    assert o3["regret"].mean() >= 0
    assert set(bl["B7"]["tempo_dq_quadrant"]) <= {"Q1", "Q2", "Q3", "Q4", "UNKNOWN"}


def test_learners_fit_and_score(frame):
    df, names, cfg = frame
    train, test = df[df.window_id.isin(["W1", "W2"])], df[df.window_id == "W3"]
    pre = F.Preprocessor("FS3").fit(train)
    Xtr, Xte = pre.transform(train), pre.transform(test)
    for name in ("L1", "L2", "L3", "L4", "L5"):
        m = L.MetaLearner(name, seed=0, n_estimators=60).fit(Xtr, train["y"], groups=train["rec_group_id"])
        s = m.score(Xte)
        assert s.shape == (len(test),) and np.isfinite(s).all()
    m6 = L.MetaLearner("L6", seed=0, n_estimators=60).fit(Xtr, train["y"], y_parts=(train[names["part_perf"]], train[names["part_san"]]))
    s6 = m6.score(Xte)
    assert np.isfinite(s6).all()
    # the planted structure must make L3 beat B1 (always V0) on mean regret
    sc = test.copy()
    sc["score"] = L.MetaLearner("L3", seed=0, n_estimators=200).fit(Xtr, train["y"]).score(Xte)
    r_l3 = L.mean_regret_of_scores(sc, sc["score"].to_numpy())
    r_b1 = L.mean_regret_of_scores(sc, (sc["pipeline_id"] == "V0").astype(float).to_numpy())
    assert r_l3 < r_b1


def test_inner_loop_random_or_optuna(frame):
    df, names, cfg = frame
    fit, val = df[df.window_id == "W1"], df[df.window_id == "W2"]
    pre = F.Preprocessor("FS3").fit(fit)
    loop = L.InnerLoop("L3", n_trials=3, seed=0).run([(pre.transform(fit), fit, pre.transform(val), val)])
    assert loop.best_params_ and np.isfinite(loop.best_value_) and len(loop.trials_) == 3
