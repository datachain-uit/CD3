# -*- coding: utf-8 -*-
"""Release 0.2.6 (2026-11-20, second pass): five-subgroup input (author decision Q-40 (b)).

The registered design (Meta-Dataset-Report §2.5, §3.3, §10.3 Table 42) has five mandatory subgroups per situation; the releases built
until 20/11 hold the (ALL, ALL) slice only. These tests fix what `assemble` guarantees on a five-subgroup input and what it reports,
and that `run`, which is unchanged and evaluates one subgroup, gives the same result on a five-subgroup release as on an ALL-only one.
SYNTHETIC fixture only."""
import json

import numpy as np
import pandas as pd
import pytest

from metamodel import assemble as A
from metamodel import cli
from metamodel import contracts as C
from metamodel import synthetic as SY
from metamodel.experiment import MMConfig, run_experiment

KW = dict(seeds=(42, 43), models=("RNN", "PATCHTST"), noise=0.01)
PARENT = list(A.SUBGROUP_PARENT_KEYS)


@pytest.fixture(scope="module")
def base():
    return SY.make_synthetic(**KW)


@pytest.fixture(scope="module")
def five():
    return SY.make_synthetic(subgroups=C.MANDATORY_SUBGROUPS, **KW)


def _assemble(f, **kw):
    args = dict(resources=f["resources"], state_profile=f["state_profile"], model_context=f["model_context"],
                provenance={"meta_release_id": "TEST"})
    args.update(kw)
    return A.assemble_seed_level(f["facts"], **args)


@pytest.fixture(scope="module")
def sl_base(base):
    return _assemble(base)


@pytest.fixture(scope="module")
def sl_five(five):
    return _assemble(five)


def _sub(df, axis, value):
    return df[(df.subgroup_axis == axis) & (df.subgroup_value == value)]


def test_fixture_adds_subgroups_without_touching_the_all_slice(base, five):
    fa, st = five["facts"], five["state_profile"]
    pd.testing.assert_frame_equal(fa[fa.subgroup_axis == "ALL"].reset_index(drop=True), base["facts"])
    pd.testing.assert_frame_equal(st[st.subgroup_axis == "ALL"].reset_index(drop=True), base["state_profile"])
    assert len(fa) == 5 * len(base["facts"]) and len(st) == 5 * len(base["state_profile"])
    assert set(zip(fa.subgroup_axis, fa.subgroup_value)) == set(C.MANDATORY_SUBGROUPS)
    keys = [k for k in PARENT if k in fa.columns]
    n = fa.set_index(keys + ["subgroup_axis", "subgroup_value"])["n_eval_samples"].unstack(["subgroup_axis", "subgroup_value"])
    for axis in C.SUBGROUP_PARTITION_AXES:                       # SEEN and UNSEEN partition the slice
        assert (n[(axis, "SEEN")] + n[(axis, "UNSEEN")] == n[("ALL", "ALL")]).all()


def test_assemble_pairs_and_joins_inside_the_subgroup(sl_base, sl_five):
    df = sl_five
    assert len(df) == 5 * len(sl_base) and df["meta_obs_id"].is_unique and df["rec_group_id"].nunique() == 5 * sl_base["rec_group_id"].nunique()
    assert (df.groupby("rec_group_id")["pipeline_id"].nunique() == 17).all()
    assert (df.groupby("rec_group_id")[["subgroup_axis", "subgroup_value"]].nunique() == 1).all().all()     # a group never mixes subgroups
    for c in [c for c in df.columns if c.startswith("qa_")]:
        assert df[c].all(), c
    assert (df["row_status"] == "COMPLETE").all()
    v0 = df[df.pipeline_id == "V0"]
    assert np.allclose(v0["acctempo_m3_cal_delta"], 0.0) and np.allclose(v0["macro_f1_delta"], 0.0)
    # the V0 reference of a subgroup row is the V0 row of the SAME subgroup, not of ALL
    ls = _sub(df, "LEARNER", "SEEN")
    ref = ls[ls.pipeline_id == "V0"].set_index([k for k in C.SITUATION_FIELDS])["macro_f1_after"]
    got = ls.set_index([k for k in C.SITUATION_FIELDS])["macro_f1_before"]
    assert np.allclose(got.to_numpy(), ref.reindex(got.index).to_numpy())
    al = _sub(df, "ALL", "ALL").set_index(PARENT)["macro_f1_before"]
    assert not np.allclose(ls.set_index(PARENT)["macro_f1_before"].reindex(al.index).to_numpy(), al.to_numpy())
    # validation copies come from the VALIDATION row of the same subgroup
    test = ls[(ls.eval_split == "TEST")].set_index([k for k in C.KEY_FIELDS if k != "eval_split"])
    val = ls[(ls.eval_split == "VALIDATION")].set_index([k for k in C.KEY_FIELDS if k != "eval_split"])
    assert np.allclose(test["val_macro_f1_after"].to_numpy(), val["macro_f1_after"].reindex(test.index).to_numpy())
    # state profile: every subgroup covered, and the evaluation-slice columns differ between subgroups
    js = df.attrs["join_stats"]["state_profile"]
    assert set(js["by_subgroup"]) == {f"{a}/{v}" for a, v in C.MANDATORY_SUBGROUPS}
    assert all(v["rows_matched"] == v["rows_total"] for v in js["by_subgroup"].values()) and js["rows_matched"] == len(df)
    k2 = [k for k in PARENT]
    assert (ls.set_index(k2)["ev_n_enrollments"] < _sub(df, "ALL", "ALL").set_index(k2)["ev_n_enrollments"].reindex(ls.set_index(k2).index)).all()
    assert np.allclose(ls.set_index(k2)["tr_missing_rate"], _sub(df, "ALL", "ALL").set_index(k2)["tr_missing_rate"].reindex(ls.set_index(k2).index))


def test_all_slice_of_a_five_subgroup_release_equals_the_all_only_release(sl_base, sl_five):
    rep = A.compare_main_slice(sl_five, sl_base)
    assert rep["ok"] and rep["rows_candidate_all_slice"] == len(sl_base) and rep["max_abs_diff"] == 0.0 and rep["columns_compared"] > 300
    agg5 = A.aggregate_seeds(sl_five, planned_seeds=(42, 43))
    agg1 = A.aggregate_seeds(sl_base, planned_seeds=(42, 43))
    rep = A.compare_main_slice(agg5, agg1)
    assert rep["ok"] and rep["id_column"] == "meta_obs_id_agg" and rep["rows_reference_all_slice"] == len(agg1) and len(agg5) == 5 * len(agg1)
    # 0.2.6: the slice size survives the aggregation
    assert {"n_eval_samples"} <= set(agg5.columns) and (agg5["n_eval_samples"] > 0).all()
    # a changed value on the ALL slice is found
    broken = sl_five.copy()
    hit = broken.index[(broken.subgroup_axis == "ALL") & (broken.pipeline_id == "V3")][:4]
    broken.loc[hit, "macro_f1_after"] += 1e-6
    rep = A.compare_main_slice(broken, sl_base)
    assert not rep["ok"] and rep["columns_differing"]["macro_f1_after"]["max_abs_diff"] == pytest.approx(1e-6, rel=1e-3)
    # and a missing ALL row
    rep = A.compare_main_slice(sl_five.drop(index=hit), sl_base)
    assert not rep["ok"] and rep["rows_only_in_reference"] == 4


def test_subgroup_report_passes_and_names_each_violation(five, sl_five):
    rep = A.subgroup_report(sl_five)
    assert rep["ok"] and rep["violations"] == [] and set(rep["rows_by_subgroup"]) == set(rep["required"])
    assert all(v["n_eval_samples"]["cells_not_adding_up"] == 0 for v in rep["partition"].values())
    assert all(v["s_leak_after"]["max_abs_diff_to_all"] == 0.0 and v["s_eff_after"]["max_abs_diff_to_all"] == 0.0 for v in rep["inherited_components"].values())
    # (a) a mandatory subgroup is missing
    facts = five["facts"]
    part = {**five, "facts": facts[~((facts.subgroup_axis == "COURSE") & (facts.subgroup_value == "UNSEEN"))]}
    rep = A.subgroup_report(_assemble(part))
    assert not rep["ok"] and any("required subgroups without rows" in v and "COURSE/UNSEEN" in v for v in rep["violations"])
    assert any("COURSE" in v and "without n_eval_samples" in v for v in rep["violations"])   # SEEN has no partner left
    # (b) SEEN + UNSEEN != ALL
    f2 = facts.copy()
    hit = (f2.subgroup_axis == "LEARNER") & (f2.subgroup_value == "SEEN") & (f2.window_id == "W2") & (f2.pipeline_id == "V4")
    f2.loc[hit, "n_eval_samples"] += 3
    rep = A.subgroup_report(_assemble({**five, "facts": f2}))
    assert not rep["ok"] and rep["partition"]["LEARNER"]["n_eval_samples"]["cells_not_adding_up"] == int(hit.sum())
    assert rep["partition"]["COURSE"]["n_eval_samples"]["cells_not_adding_up"] == 0 and any("QA06" in v for v in rep["violations"])
    # (c) s_eff is a run-level quantity: a subgroup row may not carry its own value
    f3 = facts.copy()
    f3.loc[(f3.subgroup_axis == "COURSE") & (f3.subgroup_value == "SEEN"), "s_eff"] += 0.01
    sl3 = _assemble({**five, "facts": f3})
    rep = A.subgroup_report(sl3)
    assert not rep["ok"] and any("COURSE/SEEN: s_eff_after differs" in v for v in rep["violations"]) and not sl3["qa_run_level_invariant_ok"].all()
    # (d) s_leak re-scored on the subgroup: identical across pipelines inside the subgroup (check 38 passes) but not inherited
    f4 = facts.copy()
    f4.loc[(f4.subgroup_axis == "LEARNER") & (f4.subgroup_value == "UNSEEN"), "s_leak"] -= 0.02
    sl4 = _assemble({**five, "facts": f4})
    rep = A.subgroup_report(sl4)
    assert sl4["qa_leak_probe_identity_ok"].all() and not rep["ok"] and any("LEARNER/UNSEEN: s_leak_after differs" in v for v in rep["violations"])
    # (e) a state profile written for the ALL slice only (the profile v4 of the releases so far)
    st = five["state_profile"]
    sl5 = _assemble({**five, "state_profile": st[st.subgroup_axis == "ALL"]})
    rep = A.subgroup_report(sl5)
    assert not rep["ok"] and set(rep["state_profile_rows_unmatched"]) == {"COURSE/SEEN", "COURSE/UNSEEN", "LEARNER/SEEN", "LEARNER/UNSEEN"}
    assert _sub(sl5, "LEARNER", "SEEN")["tr_missing_rate"].isna().all() and _sub(sl5, "ALL", "ALL")["tr_missing_rate"].notna().all()
    # (f) rows of one run left out on one subgroup (QA01)
    f6 = facts[~((facts.subgroup_axis == "COURSE") & (facts.subgroup_value == "SEEN") & (facts.model_name == "RNN") & (facts.window_id == "W3")
                 & (facts.seed == 43) & (facts.pipeline_id == "V7"))]
    rep = A.subgroup_report(_assemble({**five, "facts": f6}))
    assert not rep["ok"] and rep["grid"]["COURSE/SEEN"]["all_rows_without_this_subgroup"] == 2 * 4 * 2 and any("QA01" in v for v in rep["violations"])   # tasks x phases x splits


def test_class_supports_are_checked_where_present(five):
    """c{k}_support of SEEN and UNSEEN must add up to ALL; an export without supports on the ALL rows (older F1 exports) is reported, not failed."""
    f = five["facts"].copy()
    n = f["n_eval_samples"].to_numpy()
    f["c0_support"], f["c1_support"] = np.floor(n * 0.9).astype(int), np.floor(n * 0.07).astype(int)
    f["c2_support"] = n - f["c0_support"] - f["c1_support"]
    # make the supports of SEEN + UNSEEN add up exactly: UNSEEN = ALL - SEEN on each axis
    keys = [k for k in PARENT if k in f.columns]
    idx = f.set_index(keys + ["subgroup_axis", "subgroup_value"]).index
    for c in ("c0_support", "c1_support", "c2_support"):
        v = pd.Series(f[c].to_numpy(), index=idx)
        w = v.unstack(["subgroup_axis", "subgroup_value"])
        for axis in C.SUBGROUP_PARTITION_AXES:
            w[(axis, "UNSEEN")] = w[("ALL", "ALL")] - w[(axis, "SEEN")]
        f[c] = w.stack(["subgroup_axis", "subgroup_value"], future_stack=True).reindex(idx).to_numpy()
    rep = A.subgroup_report(_assemble({**five, "facts": f}))
    assert rep["ok"] and rep["partition"]["COURSE"]["c1_support"]["cells_not_adding_up"] == 0 and rep["partition"]["COURSE"]["c1_support"]["cells_checked"] > 0
    g = f.copy()
    g.loc[g.subgroup_axis == "ALL", ["c0_support", "c1_support", "c2_support"]] = np.nan          # supports absent on the ALL rows
    rep = A.subgroup_report(_assemble({**five, "facts": g}))
    assert rep["ok"] and rep["partition"]["LEARNER"]["c0_support"]["cells_checked"] == 0 and rep["partition"]["LEARNER"]["c0_support"]["cells_without_a_count"] > 0
    h = f.copy()
    hit = (h.subgroup_axis == "COURSE") & (h.subgroup_value == "UNSEEN") & (h.window_id == "W1") & (h.pipeline_id == "V0")
    h.loc[hit, "c2_support"] += 2
    rep = A.subgroup_report(_assemble({**five, "facts": h}))
    assert not rep["ok"] and rep["partition"]["COURSE"]["c2_support"]["cells_not_adding_up"] == int(hit.sum()) and rep["partition"]["COURSE"]["n_eval_samples"]["cells_not_adding_up"] == 0


def test_undefined_slice_is_infeasible_and_leaves_the_rest_complete():
    f = SY.make_synthetic(subgroups=C.MANDATORY_SUBGROUPS, undefined_slices=(("LO", "W2", "COURSE", "UNSEEN"),), **KW)
    sl = _assemble(f)
    bad = (sl.task == "LO") & (sl.window_id == "W2") & (sl.subgroup_axis == "COURSE") & (sl.subgroup_value == "UNSEEN")
    assert bad.sum() == 2 * 2 * 17 * 4 * 2 and (sl.loc[bad, "row_status"] == "INFEASIBLE").all() and (sl.loc[~bad, "row_status"] == "COMPLETE").all()
    reasons = json.loads(sl.loc[bad, "null_reason_map"].iloc[0])
    assert reasons["acctempo_m3_cal_after"] == "CLASS_ABSENT" and reasons["acctempo_m3_cal_delta"] == "CLASS_ABSENT"
    assert sl.loc[bad, "n_eval_samples"].notna().all() and sl.loc[bad, "acctempo_m3_cal_delta"].isna().all()
    rep = A.subgroup_report(sl)                               # an undefined slice is reported, it is not a violation of the contract
    assert rep["ok"] and rep["row_status_by_subgroup"]["COURSE/UNSEEN"] == {"COMPLETE": int((~bad & (sl.subgroup_axis == "COURSE") & (sl.subgroup_value == "UNSEEN")).sum()),
                                                                             "INFEASIBLE": int(bad.sum())}
    agg = A.aggregate_seeds(sl, planned_seeds=(42, 43))
    gone = (agg.task == "LO") & (agg.window_id == "W2") & (agg.subgroup_axis == "COURSE") & (agg.subgroup_value == "UNSEEN")
    assert gone.sum() == 0 and agg["acctempo_m3_cal_delta_mean"].notna().all() and (agg["row_status_agg"] == "COMPLETE").all()
    # until 0.2.5 these rows were COMPLETE with a NaN target: a V0 row that exists but has no value now marks its group
    g = SY.make_synthetic(**KW)["facts"]
    hole = (g.pipeline_id == "V0") & (g.window_id == "W3") & (g.task == "CQ")
    g.loc[hole, ["s_perf", "acctempo_m3", "acctempo_m4", "f1_macro"]] = np.nan
    sl2 = A.assemble_seed_level(g)
    w3 = sl2[(sl2.window_id == "W3") & (sl2.task == "CQ")]
    assert set(w3.loc[w3.pipeline_id == "V0", "row_status"]) == {"INFEASIBLE"} and set(w3.loc[w3.pipeline_id != "V0", "row_status"]) == {"MISSING_BASELINE"}
    assert (sl2[~((sl2.window_id == "W3") & (sl2.task == "CQ"))]["row_status"] == "COMPLETE").all()


def test_run_is_unchanged_and_gives_the_same_result_on_a_five_subgroup_release(sl_base, sl_five, tmp_path):
    """`run` evaluates one subgroup (MMConfig.subgroup = ALL/ALL, the robustness variant of Table 42). On a five-subgroup release whose
    ALL rows keep their order it must reproduce the run on the ALL-only release exactly."""
    cfg = MMConfig(meta_release_id="TEST", protocols=("E1-B",), feature_sets=("FS0", "FS3"), learners=("L1", "L3"), extra_learners=(),
                   learner_seeds=(0,), n_trials=2, bootstrap_b=100, negative_control=False)
    assert cfg.subgroup == C.MAIN_REPORT_SUBGROUP == ("ALL", "ALL")
    agg1 = A.aggregate_seeds(sl_base, planned_seeds=(42, 43))
    agg5 = A.aggregate_seeds(sl_five, planned_seeds=(42, 43))
    r1 = run_experiment(agg1, cfg, tmp_path / "all_only")
    r5 = run_experiment(agg5, cfg, tmp_path / "five")
    for name in ("mm_metrics", "mm_hypotheses", "mm_recommendations", "mm_predictions"):
        a, b = r1[name], r5[name]
        drop = [c for c in a.columns if c in ("mm_run_id", "created_utc", "elapsed_s", "duration_s")]
        pd.testing.assert_frame_equal(a.drop(columns=drop).reset_index(drop=True), b.drop(columns=drop).reset_index(drop=True), check_exact=True)
    assert r1["mm_metrics"]["n_groups"].max() == r5["mm_metrics"]["n_groups"].max() == 2 * 2 * 4    # tasks x models x phases on W3, ALL only


def test_cli_require_subgroups_and_compare_all_with(tmp_path):
    syn1, syn5 = tmp_path / "syn1", tmp_path / "syn5"
    assert cli.main(["synthetic", "--out", str(syn1), "--n-seeds", "2", "--models", "RNN", "LSTM"]) == 0
    assert cli.main(["synthetic", "--out", str(syn5), "--n-seeds", "2", "--models", "RNN", "LSTM", "--five-subgroups"]) == 0

    def assemble(src, out, *extra, state=None):
        return cli.main(["assemble", "--facts", str(src / "synthetic_facts.parquet"), "--resources", str(src / "synthetic_resources.parquet"),
                         "--state", str(state or (src / "synthetic_state_profile.parquet")), "--model-context", str(src / "synthetic_model_context.parquet"),
                         "--planned-seeds", "42", "43", "--out", str(out), *extra])

    ref = tmp_path / "rel_all_only"
    assert assemble(syn1, ref) == 0
    assert "subgroup_report" not in json.loads((ref / "meta_release_manifest.json").read_text())
    assert assemble(syn1, tmp_path / "x", "--require-subgroups") == 2          # an ALL-only input is not a five-subgroup release
    out = tmp_path / "rel_five"
    assert assemble(syn5, out, "--require-subgroups", "--compare-all-with", str(ref)) == 0
    man = json.loads((out / "meta_release_manifest.json").read_text())
    assert man["builder_version"].startswith("metamodel 0.3.1") and man["subgroup_report"]["ok"] and len(man["rows_by_subgroup"]) == 5
    assert man["n_rows_seed_level"] == 5 * 2 * 3 * 2 * 2 * 17 * 4 * 2
    cmp_ = man["all_slice_against_reference"]
    assert cmp_["meta_dataset_seed_level"]["ok"] and cmp_["meta_dataset_seed_agg"]["ok"] and cmp_["meta_dataset_seed_level"]["max_abs_diff"] == 0.0
    # the state profile of the releases so far (ALL rows only) fails the acceptance, and the tables are still written for inspection
    st = pd.read_parquet(syn5 / "synthetic_state_profile.parquet")
    st[st.subgroup_axis == "ALL"].to_parquet(tmp_path / "state_all_only.parquet", index=False)
    bad = tmp_path / "rel_five_state_all_only"
    assert assemble(syn5, bad, "--require-subgroups", state=tmp_path / "state_all_only.parquet") == 2
    man = json.loads((bad / "meta_release_manifest.json").read_text())
    assert not man["subgroup_report"]["ok"] and (bad / "meta_dataset_seed_agg.parquet").exists()
