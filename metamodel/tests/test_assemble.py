# -*- coding: utf-8 -*-
import json

import numpy as np
import pandas as pd
import pytest

from metamodel import assemble as A
from metamodel import contracts as C
from metamodel.schema import build_column_dictionary, role_of


def test_pipeline_grid_matches_registry_order():
    assert C.PIPELINE_BY_ID["V1"]["imputer"] == "MEDIAN" and C.PIPELINE_BY_ID["V5"]["imputer"] == "MEAN"
    assert C.PIPELINE_BY_ID["V3"]["balancer"] == "SASMOTE" and C.PIPELINE_BY_ID["V4"]["balancer"] == "RADIUS_SMOTE"
    assert C.IMPUTER_ONLY_REF_REGISTRY == {"V0": "V0", "V1": "V0", "V2": "V1", "V3": "V1", "V4": "V1", "V5": "V0", "V6": "V5",
                                           "V7": "V5", "V8": "V5", "V9": "V0", "V10": "V9", "V11": "V9", "V12": "V9", "V13": "V0",
                                           "V14": "V13", "V15": "V13", "V16": "V13"}
    assert C.IMPUTER_ONLY_REF == {"V0": "V0", "V1": "V1", "V2": "V1", "V3": "V1", "V4": "V1", "V5": "V5", "V6": "V5", "V7": "V5",
                                  "V8": "V5", "V9": "V9", "V10": "V9", "V11": "V9", "V12": "V9", "V13": "V13", "V14": "V13",
                                  "V15": "V13", "V16": "V13"}
    assert [p["pipeline_id"] for p in C.PIPELINES if p["is_sensitivity"]] == ["V4", "V8", "V12", "V16"]


def test_seed_level_keys_and_identities(seed_level):
    df = seed_level
    assert df["meta_obs_id"].is_unique
    assert not df.duplicated(list(C.KEY_FIELDS)).any()
    # QA03 / QA04 / V0 identities
    assert df["qa_delta_identity_ok"].all()
    assert df["qa_decomposition_ok"].all()
    assert df["qa_v0_zero_delta_ok"].all()
    assert df["qa_metric_recompute_ok"].all()
    assert df["qa_run_level_invariant_ok"].all()
    assert df["qa_leak_probe_identity_ok"].all()   # 0.2.2: s_leak identical across pipelines/models of one situation
    assert df["s_leak_after"].groupby([df["window_id"], df["eval_split"], df["phase_id"]]).nunique().eq(1).all()
    assert df.groupby("run_group_id")["s_leak_after"].nunique().gt(1).any()   # and NOT constant within a run (QA24 excludes it)
    v0 = df[df["pipeline_id"] == "V0"]
    assert np.allclose(v0["acctempo_m3_delta"], 0.0) and np.allclose(v0["macro_f1_delta"], 0.0)
    # imputer-only pipelines: delta_bal = 0, delta_imp = delta
    v1 = df[df["pipeline_id"] == "V1"]
    assert np.allclose(v1["macro_f1_delta_bal"], 0.0) and np.allclose(v1["macro_f1_delta_imp"], v1["macro_f1_delta"])
    # balanced pipelines reference the registered imputer-only run
    v3 = df[df["pipeline_id"] == "V3"].iloc[0]
    assert v3["imputer_only_pipeline"] == "V1" and v3["run_id_imp_only"] != v3["run_id_before"]
    assert (df["row_status"] == "COMPLETE").all()


def test_calibration_composite_and_log_parts(seed_level):
    df = seed_level
    cal = C.acctempo(df["s_perf_after"], df["s_san_plus_v2_after"])
    assert np.allclose(df["acctempo_m3_cal_after"], cal, atol=1e-9)
    part = df["acctempo_m3_log_delta_perf_part"] + df["acctempo_m3_log_delta_san_part"]
    lg = lambda s: np.log(np.clip(s, C.EPS_FLOOR, 1))
    assert np.allclose(part, lg(df["acctempo_m3_after"]) - lg(df["acctempo_m3_before"]), atol=1e-9)


def test_validation_copies_and_cost(seed_level):
    df = seed_level
    test = df[df["eval_split"] == "TEST"]
    val = df[df["eval_split"] == "VALIDATION"]
    assert test["val_macro_f1_before"].notna().all() and val["val_macro_f1_before"].isna().all()
    assert test["val_s_san_plus_before"].notna().all()
    # cost: time for every run, energy only for CQ in the fixture; ratios use the V0 run of the same situation
    assert test["time_run_total_s_after"].notna().all()
    assert test[test.task == "LO"]["energy_gpu_run_kwh_after"].isna().all()
    assert test[test.task == "CQ"]["energy_gpu_run_kwh_after"].notna().all()
    v0 = test[test.pipeline_id == "V0"]
    assert np.allclose(v0["time_run_total_s_ratio"], 1.0)
    nulls = json.loads(test[test.task == "LO"].iloc[0]["null_reason_map"])
    assert nulls.get("energy_gpu_run_kwh_after") == "TELEMETRY_UNAVAILABLE"
    assert (test["cost_shared_across_phases"] == 1).all()


def test_recommendation_block(seed_level):
    df = seed_level[seed_level["eval_split"] == "TEST"]
    g = df.groupby("rec_group_id")
    assert (g.size() == 17).all()
    assert (g["within_eps_best"].sum() >= 1).all()
    assert (g["is_best"].sum() >= 1).all()
    best = g["acctempo_m3_cal_delta"].transform("max")
    assert np.allclose(df["regret"], best - df["acctempo_m3_cal_delta"])
    # cost basis: CQ groups have accepted energy estimates -> ENERGY; LO -> TIME
    assert set(df[df.task == "CQ"]["cost_basis"]) == {"ENERGY"} and set(df[df.task == "LO"]["cost_basis"]) == {"TIME"}
    # utility with lambda = 0 equals the objective delta
    assert np.allclose(df["utility_l0"], df["acctempo_m3_cal_delta"])
    assert (g["recommended_utility_l2"].sum() >= 1).all()
    assert df["relevance_grade"].isin([0, 1, 2, 3]).all()


def test_strict_cost_policy_treats_estimates_as_time(synthetic_small):
    f = synthetic_small
    sl = A.assemble_seed_level(f["facts"], resources=f["resources"], energy_measured_types=C.ENERGY_MEASURED_TYPES_STRICT)
    assert set(sl["cost_basis"]) == {"TIME"}


def test_seed_agg_statistics(seed_agg, seed_level):
    agg = seed_agg
    keys = [k for k in C.KEY_FIELDS if k != "seed"]
    assert not agg.duplicated(keys).any()
    assert (agg["n_seeds_success"] == 2).all() and (agg["row_status_agg"] == "COMPLETE").all()
    one = agg.iloc[0]
    rows = seed_level[(seed_level[keys] == one[keys]).all(axis=1)]
    assert np.isclose(one["acctempo_m3_cal_delta_mean"], rows["acctempo_m3_cal_delta"].mean())
    assert np.isclose(one["macro_f1_after_p90"], rows["macro_f1_after"].quantile(0.9))
    assert "regret_agg" in agg.columns and "rank_delta_agg" in agg.columns
    # X_STATE columns carried unchanged
    assert "tr_missing_rate" in agg.columns and agg["tr_missing_rate"].notna().all()


def test_column_dictionary_roles(seed_level):
    cd = build_column_dictionary(seed_level)
    roles = dict(zip(cd.column_name, cd.role))
    assert roles["acctempo_m3_delta"] == "TARGET" and roles["val_acctempo_m3_before"] == "X_VAL"
    assert roles["s_ent_after"] == "DIAG" and roles["s_san_plus_v2_delta"] == "DIAG"
    assert roles["tr_missing_rate"] == "X_STATE" and roles["drift_tr_ev_psi_mean"] == "X_STATE"
    assert roles["label_drift_tr_ev_jsd"] == "X_RESTRICTED" and roles["ev_imbalance_ratio"] == "X_RESTRICTED"
    assert roles["regret"] == "DERIVED" and roles["time_train_s_after"] == "COST" and roles["a_imp_mice"] == "X_CONTEXT"
    assert roles["meta_obs_id"] == "KEY" and roles["run_id_before"] == "PROV" and roles["row_status"] == "QA"
    unassigned = cd[cd.role == "UNASSIGNED"]["column_name"].tolist()
    # only the synthetic flag and helper columns may be unassigned
    assert set(unassigned) <= {"synthetic", "gpu"}, unassigned   # reference columns carry the PROV role since v0.2.0


def test_duplicate_keys_rejected(synthetic_small):
    facts = pd.concat([synthetic_small["facts"], synthetic_small["facts"].head(5)], ignore_index=True)
    with pytest.raises(ValueError):
        A.assemble_seed_level(facts)


def test_missing_baseline_status(synthetic_small):
    facts = synthetic_small["facts"]
    facts = facts[~((facts.pipeline_id == "V0") & (facts.window_id == "W2"))]
    sl = A.assemble_seed_level(facts)
    w2 = sl[sl.window_id == "W2"]
    assert (w2["row_status"] == "MISSING_BASELINE").all() and w2["macro_f1_delta"].isna().all()
    assert (sl[sl.window_id != "W2"]["row_status"] == "COMPLETE").all()


def test_release_0_2_2_reference_key_conventions_and_loud_joins():
    """Request 2026-11-09 point 2.3 (CD3 M-14 RUN_LOG): an S0 profile written with cohort = 'ALL' or without cohort/subgroup
    columns joins on the FIXED/ALL/ALL convention of the facts; a profile that matches nothing raises instead of leaving every
    X_STATE column NULL; an F0 table without a cohort column joins; an F0 table that matches nothing raises."""
    from metamodel import synthetic as SY
    data = SY.make_synthetic(tasks=("CQ",), windows=("W1",), seeds=(42,), models=("RNN",))
    facts, state = data["facts"], data["state_profile"]
    # a deterministic F0 table at the grain of the contract (one row per task x window x phase x split, ALL slice)
    f0 = (facts[facts["pipeline_id"] == "V0"]
          .groupby(["task", "window_id", "phase_id", "cohort", "eval_split", "subgroup_axis", "subgroup_value"], as_index=False)
          [["f1_macro", "balanced_accuracy", "mcc", "cohen_kappa", "gmean_recall", "s_perf"]].mean())
    f0[["f1_macro", "balanced_accuracy"]] -= 0.1
    # S0 written with cohort = 'ALL' (team convention of 2026-11-08) and without subgroup columns
    sp_all = state.copy()
    sp_all["cohort"] = "ALL"
    sp_all = sp_all.drop(columns=["subgroup_axis", "subgroup_value"])
    df = A.assemble_seed_level(facts, state_profile=sp_all, f0_reference=f0.drop(columns=["cohort"]))
    assert df.attrs["join_stats"]["state_profile"]["rows_matched"] == len(df)
    assert df.attrs["join_stats"]["f0_reference"]["rows_matched"] == len(df)
    assert df["tr_missing_rate"].notna().all() and df["macro_f1_ref"].notna().all()
    assert (df["cohort"] == C.COHORT_FIXED).all()
    # a profile whose keys match nothing must not pass silently
    sp_bad = state.copy()
    sp_bad["feature_regime"] = "OTHER_REGIME"
    with pytest.raises(ValueError, match="joined 0 of"):
        A.assemble_seed_level(facts, state_profile=sp_bad)
    f0_bad = f0.copy()
    f0_bad["cohort"] = "SOMETHING_ELSE"
    with pytest.raises(ValueError, match="f0_reference for task"):
        A.assemble_seed_level(facts, f0_reference=f0_bad)
    # QA24 as registered: s_eff run-level; s_leak varies within a run and is identical across pipelines
    full = A.assemble_seed_level(facts, state_profile=state, f0_reference=f0)
    assert full["qa_run_level_invariant_ok"].all() and full["qa_leak_probe_identity_ok"].all()
    broken = facts.copy()
    one = (broken["pipeline_id"] == "V3") & (broken["phase_id"] == "P2") & (broken["eval_split"] == "TEST")
    broken.loc[one, "s_leak"] += 0.02
    flagged = A.assemble_seed_level(broken)
    assert not flagged["qa_leak_probe_identity_ok"].all() and flagged["qa_run_level_invariant_ok"].all()
    # tolerance boundary (0.2.4, 2026-11-13): every export copies the registered reference, so only float noise (5e-11) passes
    # and a spread of 2e-4 is flagged
    assert A.TOL_LEAK_IDENTITY == 1e-9   # 0.2.4: reference-copy contract ratified on 2026-11-13 (Q-31 (a)); 0.2.2-0.2.3 used 1e-4
    near = facts.copy()
    near.loc[one, "s_leak"] += 5e-11   # the F1 exports equal the reference to 4.8e-11
    assert A.assemble_seed_level(near)["qa_leak_probe_identity_ok"].all()
    far = facts.copy()
    far.loc[one, "s_leak"] += 2e-4
    assert not A.assemble_seed_level(far)["qa_leak_probe_identity_ok"].all()


def test_release_0_2_3_alias_per_source_key_fill_and_b5_numeric_state(synthetic_small, tmp_path):
    """Release 0.2.3 (2026-11-13), three defects reported by the code team on the release of 2026-11-12:
    (1) an export writing ``f1_macro`` concatenated with one writing ``macro_f1`` left macro_f1 empty for the former;
    (2) a constant ``--key`` was filled only when the column was absent, not for NaN rows after concatenation;
    (3) B5 took string X_STATE columns (``*_prev_reason``) into its numeric state matrix."""
    from metamodel import baselines as B
    from metamodel import cli as CLI
    facts = synthetic_small["facts"]
    assert ("macro_f1" in facts.columns) != ("f1_macro" in facts.columns)       # the fixture uses one of the two names
    r4_like = facts[facts["model_name"] == "RNN"].rename(columns={"macro_f1": "f1_macro"}).drop(columns=["feature_regime"])
    f2_like = facts[facts["model_name"] == "PATCHTST"].rename(columns={"f1_macro": "macro_f1"})
    # (1a) already-concatenated frame: both columns present, complementary -> one registered column, alias dropped
    cat = pd.concat([r4_like, f2_like], ignore_index=True)
    assert cat["macro_f1"].isna().sum() == len(r4_like)
    norm = A.normalise_fact_columns(cat)
    assert "f1_macro" not in norm.columns and norm["macro_f1"].notna().all()
    # (1b) the CLI renames per source before concatenating
    p1, p2 = tmp_path / "r4.parquet", tmp_path / "f2.parquet"
    r4_like.to_parquet(p1, index=False), f2_like.to_parquet(p2, index=False)
    read = CLI._read_many([str(p1), str(p2)], normalise=True)
    assert "f1_macro" not in read.columns and read["macro_f1"].notna().all()
    # both filled and disagreeing: registered column kept, alias left, warning raised
    bad = f2_like.assign(f1_macro=f2_like["macro_f1"] + 0.5)
    with pytest.warns(UserWarning, match="disagree"):
        kept = A.normalise_fact_columns(bad)
    assert "f1_macro" in kept.columns and np.allclose(kept["macro_f1"], f2_like["macro_f1"])
    # (2) constant key fills the NaN rows of the export that omits the column, and only those
    regime = str(f2_like["feature_regime"].iloc[0])
    filled = A.fill_key_defaults(norm, {"feature_regime": regime})
    assert filled["feature_regime"].notna().all() and (filled["feature_regime"] == regime).all()
    with pytest.raises(KeyError, match="feature_regime"):
        A.fill_key_defaults(norm.assign(cohort=C.COHORT_FIXED), {})
    # (3) B5 ignores non-numeric X_STATE columns
    sl = A.assemble_seed_level(facts, resources=synthetic_small["resources"], state_profile=synthetic_small["state_profile"],
                               model_context=synthetic_small["model_context"], provenance={"meta_release_id": "TEST"},
                               energy_measured_types=C.ENERGY_MEASURED_TYPES_WITH_ESTIMATE)
    state_num = [c for c in sl.columns if role_of(c)[1] == "X_STATE" and pd.api.types.is_numeric_dtype(sl[c])]
    assert state_num
    probe = sl[sl["eval_split"] == sl["eval_split"].iloc[0]].copy()
    probe["y"] = np.arange(len(probe), dtype=float)
    str_col = "drift_phase_prev_psi_mean_reason"                   # a string X_STATE column of the S0 profile (v3/v4)
    assert role_of(str_col)[1] == "X_STATE"
    probe[str_col] = "NO_PREVIOUS_PHASE"
    knn = B.KNNMeta(k=3).fit(probe, "y", "rec_group_id")
    assert str_col not in knn.pre_.numeric_ and all(pd.api.types.is_numeric_dtype(probe[c]) for c in knn.pre_.numeric_)
    assert knn.score(probe, "rec_group_id")["score"].notna().any()
