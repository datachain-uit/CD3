# -*- coding: utf-8 -*-
"""Release 0.3.1 (2026-11-26). SYNTHETIC data, never a source of reported numbers.

Author decision of 2026-11-26 on question Q-48, option (b) (registry decision 59): the negative control keeps the dtype of every
permuted state column, and the control alone is run again on the delivered runs. The bootstrap enumerates its clusters in an explicit
order, so that the tables of record are reproduced under any pandas version. Nothing else of the runner changed.
"""
import hashlib
import json
import sys

import numpy as np
import pandas as pd
import pytest

from metamodel import assemble as A
from metamodel import cli
from metamodel import contracts as C
from metamodel import experiment as E
from metamodel import features as F
from metamodel import metrics as M
from metamodel import schema as S
from metamodel import synthetic as SY
from metamodel import verify as V
from metamodel.experiment import MMConfig, run_experiment

KW = dict(seeds=(42, 43), models=("RNN", "PATCHTST"), noise=0.01)
TINY = dict(meta_release_id="TEST", feature_sets=("FS0", "FS3"), learners=("L3",), extra_learners=(), learner_seeds=(0, 1), n_trials=1,
            bootstrap_b=100, protocols=("E1-B",))
FULL = dict(training_subgroups=C.MANDATORY_SUBGROUPS, e1_scope=C.E1_SCOPE_PER_TASK, hypothesis_rows=C.HYP_ROWS_REGISTERED)
REASON = "tr_profile_note_reason"          # a text column of the state block, as the *_reason columns of the real profile


def _agg(subgroups=(("ALL", "ALL"),)):
    f = SY.make_synthetic(subgroups=subgroups, **KW)
    sl = A.assemble_seed_level(f["facts"], resources=f["resources"], state_profile=f["state_profile"], model_context=f["model_context"],
                               provenance={"meta_release_id": "TEST"})
    agg = A.aggregate_seeds(sl, planned_seeds=(42, 43))
    agg[REASON] = np.where(agg["phase_id"].astype(str).str.endswith("1"), "NO_PREVIOUS_PHASE", "OK")
    return agg


@pytest.fixture(scope="module")
def agg1():
    return _agg()


@pytest.fixture(scope="module")
def agg5():
    return _agg(C.MANDATORY_SUBGROUPS)


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------------------------
# bootstrap: explicit cluster order
# ---------------------------------------------------------------------------------------------


def test_clusters_are_enumerated_in_the_order_of_their_first_row():
    frame = pd.DataFrame({"task": ["LO", "CQ", "LO", "CQ", "CQ", None], "window_id": ["W2", "W1", "W2", "W3", "W1", "W1"],
                          "v": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]})
    clusters = M.clusters_by_first_appearance(frame, ["task", "window_id"])
    assert [c.tolist() for c in clusters] == [[0, 2], [1, 4], [3]]            # (LO, W2) first; the row with a missing key is in no cluster
    assert [c.tolist() for c in M.clusters_by_first_appearance(frame, [])] == [list(range(6))]
    # the bootstrap is a function of the row order alone: the same draws as a direct computation on the explicit order
    g = frame.dropna(subset=["task"])
    res = M.cluster_bootstrap_mean(g, "v", cluster_fields=("task", "window_id"), b=50, seed=7)
    rng = np.random.default_rng(7)
    vals = g["v"].to_numpy(dtype=float)
    draws = [np.mean(np.concatenate([vals[clusters[k]] for k in rng.integers(0, 3, size=3)])) for _ in range(50)]
    lo, hi = np.quantile(draws, [C.ALPHA_STAT / 2, 1 - C.ALPHA_STAT / 2])
    assert res["n_clusters"] == 3 and res["ci_low"] == pytest.approx(lo, abs=0) and res["ci_high"] == pytest.approx(hi, abs=0)


def test_the_cluster_order_follows_the_rows_not_the_sorted_keys():
    a = pd.DataFrame({"rec_group_id": list("abcdef"), "task": ["LO", "LO", "CQ", "CQ", "LO", "CQ"], "regret": [0.5, 0.1, 0.9, 0.2, 0.3, 0.4]})
    b = a.assign(regret=[0.1, 0.4, 0.3, 0.6, 0.2, 0.1])
    r1 = M.paired_cluster_bootstrap(a, b, "regret", cluster_fields=("task",), b=200)
    rev = a.iloc[::-1].reset_index(drop=True)            # CQ first: another enumeration, the same clusters
    r2 = M.paired_cluster_bootstrap(rev, b, "regret", cluster_fields=("task",), b=200)
    assert r1["estimate"] == pytest.approx(r2["estimate"]) and r1["n_clusters"] == r2["n_clusters"] == 2
    assert [c.tolist() for c in M.clusters_by_first_appearance(a, ["task"])] == [[0, 1, 4], [2, 3, 5]]
    assert [c.tolist() for c in M.clusters_by_first_appearance(rev, ["task"])] == [[0, 2, 3], [1, 4, 5]]


# ---------------------------------------------------------------------------------------------
# negative control: the permutation keeps every dtype
# ---------------------------------------------------------------------------------------------


def test_the_permutation_moves_whole_situations_and_keeps_every_dtype(agg1):
    state = [c for c in F.select_columns(agg1.columns, "FS3", drop_task=False) if S.role_of(c)[1] == "X_STATE"]
    assert REASON in state and any(pd.api.types.is_numeric_dtype(agg1[c]) for c in state)
    other = [c for c in agg1.columns if c not in state]
    perm = E.permute_state_across_situations(agg1, state, seed=0)
    assert all(perm[c].dtype == agg1[c].dtype for c in state)
    pd.testing.assert_frame_equal(perm[other], agg1[other])                   # context, targets and keys untouched
    # every situation received the state of exactly one situation, and the assignment is a permutation of the situations
    first, got = agg1.groupby("rec_group_id")[state].first(), perm.groupby("rec_group_id")[state].first()
    assert (perm.groupby("rec_group_id")[state].nunique(dropna=False) <= 1).all().all()
    key = lambda fr: fr.astype(object).where(fr.notna(), "NA").apply(lambda r: "|".join(map(str, r.tolist())), axis=1)
    assert sorted(key(first)) == sorted(key(got)) and (key(first) != key(got)).any()
    # the assignment of metamodel <= 0.3.0: the mixed block is an object array and the numeric state columns lose their dtype
    legacy = E.permute_state_across_situations(agg1, state, seed=0, preserve_dtype=False)
    numeric = [c for c in state if pd.api.types.is_numeric_dtype(agg1[c])]
    assert all(legacy[c].dtype == object for c in numeric)
    for c in numeric:                                                         # the same values, another encoding
        assert np.allclose(pd.to_numeric(legacy[c]).to_numpy(dtype=float), perm[c].to_numpy(dtype=float), equal_nan=True)
    assert (legacy[REASON].astype(object) == perm[REASON].astype(object)).all()
    # without a text column in the block every column stays numeric, so the encoding of the state does not change: the fixture of the
    # releases up to 0.3.0 has no text column in the state block, which is why no test showed the defect
    num_only = E.permute_state_across_situations(agg1, numeric, seed=0, preserve_dtype=False)
    assert all(pd.api.types.is_numeric_dtype(num_only[c]) for c in numeric)
    for c in numeric:
        assert np.allclose(num_only[c].to_numpy(dtype=float), perm[c].to_numpy(dtype=float), equal_nan=True)


def test_the_control_of_a_run_keeps_the_feature_space_of_the_model(agg1, tmp_path):
    res = run_experiment(agg1, MMConfig(**TINY), tmp_path / "run")
    nc, reg = res["mm_negative_control"], res["mm_run_registry"]
    assert len(nc) == 1 and (nc["control_permutation"] == C.NEG_CONTROL_DTYPE_PRESERVED).all()
    assert (nc["control_state_columns_with_changed_dtype"] == 0).all()
    n_model = int(reg.loc[reg["strategy"] == "L3-FS3", "n_features"].iloc[0])
    assert abs(int(nc["control_n_features"].iloc[0]) - n_model) <= 2          # the same encoding; near-constant filtering may differ by a column


# ---------------------------------------------------------------------------------------------
# the control alone on a delivered run
# ---------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def delivered_030(agg5, tmp_path_factory):
    """A run directory as metamodel 0.3.0 delivered it: the control of the mixed-block assignment and the version string of 0.3.0."""
    out = tmp_path_factory.mktemp("delivered_030")
    pkg = sys.modules["metamodel"]
    kept_version, kept_control = pkg.__version__, E._negative_control
    pkg.__version__ = "0.3.0 (2026-11-21)"
    E._negative_control = lambda *a, **k: kept_control(*a, **{**k, "preserve_dtype": False})
    try:
        run_experiment(agg5, MMConfig(**{**TINY, "protocols": ("E1-A", "E1-B")}, **FULL), out)
    finally:
        pkg.__version__, E._negative_control = kept_version, kept_control
    return out


def test_the_control_alone_replays_a_delivery_of_0_3_0_and_adds_the_corrected_table(agg5, delivered_030, tmp_path):
    before = {p.name: _sha(p) for p in sorted(delivered_030.iterdir()) if p.is_file()}
    res = E.negative_control_only(agg5, delivered_030, tmp_path / "nc")
    t, s = res["table"], res["summary"]
    assert s["verdict"] == "PASS" and s["folds"] == s["folds_ok"] == 4 and s["delivered_control_permutation"] == C.NEG_CONTROL_LEGACY_BLOCK
    assert s["replay_max_abs_diff"] == 0.0 and s["replay_model_max_abs_diff"] == 0.0 and s["all_state_dtypes_kept"] is True
    assert (t["legacy_state_columns_with_changed_dtype"] > 0).all() and (t["control_state_columns_with_changed_dtype"] == 0).all()
    assert (t["legacy_control_n_features"] > t["control_n_features"]).all()   # the one-hot expansion of the numeric state
    assert (t["MQ08_pass"] == (t["mean_regret_permuted"] >= t["mean_regret_model"])).all()
    assert s["dtype_preserved_passes"] == int(t["MQ08_pass"].sum()) and s["delivered_passes"] == int(t["delivered_MQ08_pass"].sum())
    assert set(s["environment"]) >= {"python", "libraries", "thread_env", "cpu_count"} and "node" not in s["environment"]
    assert {p.name for p in (tmp_path / "nc").iterdir()} == {"mm_negative_control_r2.parquet", "mm_negative_control_r2.csv",
                                                             "negative_control_r2_summary.json"}
    assert before == {p.name: _sha(p) for p in sorted(delivered_030.iterdir()) if p.is_file()}     # the delivered run is never touched
    assert s["run_dir"] == delivered_030.name and str(delivered_030.parent) not in json.dumps(s)   # no machine path in the summary
    assert len(res["permutations"]) == 0 and "exploratory_permutations" not in s


def test_the_labelled_permutation_table_is_separate_and_symmetric_in_learner_seeds(agg5, delivered_030, tmp_path):
    res = E.negative_control_only(agg5, delivered_030, tmp_path / "nc", permutations=2)
    p, t, s = res["permutations"], res["table"], res["summary"]
    assert len(p) == 2 * len(t) and (p["analysis_label"] == C.NEG_CONTROL_EXPLORATORY_LABEL).all() and (p["n_learner_seeds"] == 2).all()
    assert sorted(p["permutation_seed"].unique()) == [0, 1]
    assert np.allclose(p["delta_control_minus_model"], p["mean_regret_permuted_ensemble"] - p["mean_regret_model"])
    per_fold = pd.DataFrame(s["exploratory_permutations"]["per_fold"])
    assert (per_fold["n"] == 2).all() and (per_fold["negative"] + per_fold["positive"] + per_fold["ties"] == 2).all()
    # the registered table is the one of the run without the option
    base = E.negative_control_only(agg5, delivered_030, tmp_path / "nc0", write=False)["table"]
    pd.testing.assert_frame_equal(t, base)
    assert (tmp_path / "nc" / "mm_negative_control_r2_permutations.parquet").exists()


def test_a_changed_table_or_another_configuration_is_refused(agg5, delivered_030, tmp_path):
    digest = (delivered_030 / "mm_config_sha256.txt").read_text().split()[0]
    assert cli.main(["negative-control", "--meta", str(tmp_path / "x.parquet"), "--run-dir", str(delivered_030), "--out", str(delivered_030)]) == 2
    agg5.to_parquet(tmp_path / "agg.parquet", index=False)
    args = ["negative-control", "--meta", str(tmp_path / "agg.parquet"), "--run-dir", str(delivered_030)]
    assert cli.main(args + ["--out", str(tmp_path / "a"), "--expect-digest", "0" * 64]) == 2 and not (tmp_path / "a").exists()
    assert cli.main(args + ["--out", str(tmp_path / "b"), "--expect-digest", digest]) == 0
    assert json.loads((tmp_path / "b" / "negative_control_r2_summary.json").read_text())["config_sha256"] == digest
    # another table than the one the run read: the replays no longer equal the delivered values and no fold is comparable
    other = agg5.copy()
    ycols = [c for c in other.columns if c.startswith("acctempo_m3_cal") and pd.api.types.is_numeric_dtype(other[c])]
    rng = np.random.default_rng(1)
    for c in ycols:
        other[c] = other[c] + rng.normal(0, 0.05, len(other))
    res = E.negative_control_only(other, delivered_030, tmp_path / "c", write=False)
    assert res["summary"]["verdict"] == "FAIL" and res["summary"]["folds_ok"] < res["summary"]["folds"]
    assert res["table"]["status"].astype(str).str.startswith("NOT_COMPARABLE").any()


# ---------------------------------------------------------------------------------------------
# bootstrap rows from the stored outcomes of a run
# ---------------------------------------------------------------------------------------------


def test_the_bootstrap_rows_of_a_run_are_reproduced_from_its_stored_outcomes(agg5, delivered_030, tmp_path):
    res = V.verify_bootstrap(delivered_030)
    t = res["table"]
    assert res["verdict"] == "PASS" and res["max_abs_diff"] == 0.0 and res["rows_without_stored_counterpart"] == 0
    assert res["run_dir"] == delivered_030.name
    assert {"H1", "H3"} <= set(t["hypothesis"]) and {C.ROLE_PRIMARY, C.ROLE_PER_TASK, C.ROLE_REPLICATION, C.ROLE_POOLED_2FOLD} <= set(t["analysis_role"])
    assert cli.main(["verify-bootstrap", "--run-dir", str(delivered_030), "--out", str(tmp_path / "rows.csv")]) == 0
    assert json.loads((tmp_path / "rows.json").read_text())["verdict"] == "PASS"
    # a stored limit that the outcomes do not give is reported
    broken = tmp_path / "broken"
    broken.mkdir()
    for p in delivered_030.iterdir():
        if p.is_file() and p.suffix in (".json", ".txt", ".parquet"):
            (broken / p.name).write_bytes(p.read_bytes())
    hyp = pd.read_parquet(broken / "mm_hypotheses.parquet")
    row = hyp.index[(hyp["analysis_role"] == C.ROLE_PRIMARY) & (hyp["hypothesis"] == "H1")][0]
    hyp.loc[row, "ci_low"] = float(hyp.loc[row, "ci_low"]) + 1e-6
    hyp.to_parquet(broken / "mm_hypotheses.parquet", index=False)
    assert V.verify_bootstrap(broken)["verdict"] == "FAIL" and cli.main(["verify-bootstrap", "--run-dir", str(broken)]) == 1


def test_the_environment_record_names_versions_and_threads_only(tmp_path, capsys):
    assert cli.main(["env", "--out", str(tmp_path / "env.json")]) == 0
    rec = json.loads((tmp_path / "env.json").read_text())
    assert set(rec) == {"python", "python_implementation", "platform", "machine", "cpu_count", "learner_threads_n_jobs_minus_one", "libraries",
                        "thread_env", "metamodel_version", "env_id"}
    assert rec["metamodel_version"].startswith("0.3.1") and {"pandas", "numpy", "lightgbm"} <= set(rec["libraries"])
    assert "LOKY_MAX_CPU_COUNT" in rec["thread_env"]            # the variable that sets the threads of the learners built with n_jobs=-1
