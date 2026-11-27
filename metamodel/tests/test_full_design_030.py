# -*- coding: utf-8 -*-
"""Release 0.3.0 (2026-11-21): the full-design run. SYNTHETIC data, never a source of reported numbers.

Author decisions of 2026-11-21 (registry decisions 52, 53, 54): Q-41 (a) one model per task and fold, verdict rows on the clusters of the
two tasks together; Q-42 (a) baselines and inner selection on the matched slice; Q-43 (b) one Holm family over every test row.
"""
import json

import numpy as np
import pandas as pd
import pytest

from metamodel import assemble as A
from metamodel import cli
from metamodel import contracts as C
from metamodel import experiment as E
from metamodel import metrics as M
from metamodel import synthetic as SY
from metamodel.experiment import MMConfig, run_experiment

KW = dict(seeds=(42, 43), models=("RNN", "PATCHTST"), noise=0.01)
RUN = dict(meta_release_id="TEST", feature_sets=("FS0", "FS3"), learners=("L1", "L3"), extra_learners=(), learner_seeds=(0,), n_trials=2,
           bootstrap_b=200)
FAST = dict(meta_release_id="TEST", feature_sets=("FS3",), learners=("L3",), extra_learners=(), learner_seeds=(0,), n_trials=1, bootstrap_b=100,
            negative_control=False, protocols=("E1-B",))
FULL = dict(training_subgroups=C.MANDATORY_SUBGROUPS, e1_scope=C.E1_SCOPE_PER_TASK, hypothesis_rows=C.HYP_ROWS_REGISTERED)
LEGACY_DIGEST = "5df1e71e7eb16432319eb9069108a85ff6e128b9625fb9c669d703ef9864673b"      # MMConfig().sha256() of metamodel 0.2.6
NEW_TABLES = ("mm_metrics_joint", "mm_metrics_secondary", "mm_recommendations_secondary", "mm_fold_composition")
N_MAIN = 2 * 4          # models x phases: situations of one task and one test window on the main report slice
BASELINES = ["B0", "B1", "B2", "B3", "B4", "B5", "B6", "B7"]


def _agg(f):
    sl = A.assemble_seed_level(f["facts"], resources=f["resources"], state_profile=f["state_profile"], model_context=f["model_context"],
                               provenance={"meta_release_id": "TEST"})
    return A.aggregate_seeds(sl, planned_seeds=(42, 43))


@pytest.fixture(scope="module")
def agg1():
    return _agg(SY.make_synthetic(**KW))


@pytest.fixture(scope="module")
def agg5():
    return _agg(SY.make_synthetic(subgroups=C.MANDATORY_SUBGROUPS, **KW))


@pytest.fixture(scope="module")
def full(agg5, tmp_path_factory):
    out = tmp_path_factory.mktemp("full")
    return run_experiment(agg5, MMConfig(protocols=("E1-A", "E1-B", "E2"), **RUN, **FULL), out), out


@pytest.fixture(scope="module")
def all_only(agg5, tmp_path_factory):
    """the robustness variant of Table 42 with the registered folds: training on the (ALL, ALL) rows, one model per task"""
    cfg = MMConfig(protocols=("E1-A", "E1-B", "E2"), **RUN, e1_scope=C.E1_SCOPE_PER_TASK, hypothesis_rows=C.HYP_ROWS_REGISTERED)
    return run_experiment(agg5, cfg, tmp_path_factory.mktemp("all_only"))


def _same(a, b, cols, check_dtype=True):
    pd.testing.assert_frame_equal(a[cols].reset_index(drop=True), b[cols].reset_index(drop=True), check_exact=True, check_dtype=check_dtype)


def test_the_default_plan_is_the_plan_of_0_2_x(agg1, tmp_path):
    cfg = MMConfig()
    assert cfg.sha256() == LEGACY_DIGEST and cfg.is_legacy_design() and cfg.to_dict()["config_version"] == "mm_config_v0.2"
    assert not set(MMConfig.V03_FIELDS) & set(cfg.to_dict())
    new = MMConfig(**FULL)
    d = new.to_dict()
    assert d["config_version"] == "mm_config_v0.3" and d["e1_scope"] == "PER_TASK" and d["hypothesis_rows"] == "REGISTERED"
    assert d["training_subgroups"] == [list(s) for s in C.MANDATORY_SUBGROUPS] and d["baseline_scope"] == "MATCHED_SLICE"
    assert new.sha256() != LEGACY_DIGEST and not new.is_legacy_design()
    with pytest.raises(ValueError):
        MMConfig(e1_scope=C.E1_SCOPE_PER_TASK).validate()               # per-task folds need the joint verdict rows
    with pytest.raises(ValueError):
        MMConfig(baseline_scope="SOMETHING").validate()
    res = run_experiment(agg1, MMConfig(**FAST), tmp_path / "legacy")
    assert all(len(res[t]) == 0 for t in NEW_TABLES) and "analysis_role" not in res["mm_hypotheses"].columns
    assert not any((tmp_path / "legacy" / f"{t}.csv").exists() for t in NEW_TABLES)
    assert "e1_scope" not in res["mm_run_registry"].columns
    assert json.loads((tmp_path / "legacy" / "mm_config.json").read_text())["config_version"] == "mm_config_v0.2"


def test_the_full_design_needs_a_five_subgroup_release(agg1):
    with pytest.raises(KeyError, match="five-subgroup release"):
        run_experiment(agg1, MMConfig(**FAST, **FULL), "unused", write=False)


def test_a_per_task_fold_equals_the_run_on_the_table_of_that_task(agg1):
    """One model per task and fold (decision 52 (a)): the fold of a task must be the run of 0.2.x on the rows of that task alone."""
    cfg = dict(RUN, protocols=("E1-A", "E1-B"))
    a = run_experiment(agg1, MMConfig(**cfg, e1_scope=C.E1_SCOPE_PER_TASK, hypothesis_rows=C.HYP_ROWS_REGISTERED), "unused", write=False)
    num = ["n_groups", "mean_regret", "median_regret", "harm_rate", "top1_hit_rate", "mean_gain_over_v0", "mean_regret_ci_low", "mean_regret_ci_high"]
    for t in ("CQ", "LO"):
        b = run_experiment(agg1[agg1.task == t], MMConfig(**cfg), "unused", write=False)
        ma = a["mm_metrics"][a["mm_metrics"].fold_id.str.startswith(t + ":")].sort_values(["protocol", "strategy"])
        mb = b["mm_metrics"].sort_values(["protocol", "strategy"])
        assert list(ma.fold_id.str.split(":", n=1).str[1]) == list(mb.fold_id) and len(ma) == 2 * (8 + 4)
        _same(ma, mb, ["protocol", "strategy"] + num)
        pa = a["mm_predictions"][a["mm_predictions"].fold_id.str.startswith(t + ":")].sort_values(["protocol", "strategy", "meta_obs_id"])
        pb = b["mm_predictions"].sort_values(["protocol", "strategy", "meta_obs_id"])
        _same(pa, pb, ["protocol", "strategy", "meta_obs_id", "y", "score"])
        # the hypothesis rows of one task equal the table of the single-task run
        ha = a["mm_hypotheses"][(a["mm_hypotheses"].analysis_role == C.ROLE_PER_TASK) & (a["mm_hypotheses"].task_scope == t)]
        hb = b["mm_hypotheses"][b["mm_hypotheses"].fold_id == "W1W2->W3"]
        _same(ha, hb, ["hypothesis", "comparison", "estimate", "ci_low", "ci_high", "n_clusters", "supported"], check_dtype=False)


def test_the_main_slice_keeps_the_baselines_of_the_all_only_analysis(full, all_only):
    """Decision 53 (a): on the main report slice the baselines are exactly those of the ALL-only analysis; only the learners gain rows."""
    res, _ = full
    m5, m1 = res["mm_metrics"], all_only["mm_metrics"]
    key = ["protocol", "fold_id", "strategy"]
    cols = key + ["n_groups", "mean_regret", "harm_rate", "top1_hit_rate", "mean_regret_ci_low", "mean_regret_ci_high"]
    _same(m5[m5.strategy.isin(BASELINES)].sort_values(key), m1[m1.strategy.isin(BASELINES)].sort_values(key), cols)
    assert set(m5.fold_id) == {"CQ:W1->W2", "LO:W1->W2", "CQ:W1W2->W3", "LO:W1W2->W3", "CQ->LO", "LO->CQ"}
    assert (m5[m5.protocol != "E2"].n_groups == N_MAIN).all() and (m5[m5.protocol == "E2"].n_groups == N_MAIN).all()
    comp = res["mm_fold_composition"]
    assert len(all_only["mm_fold_composition"].report_slice.unique()) == 1
    for (protocol, fold_id), g in comp.groupby(["protocol", "fold_id"]):
        assert len(g) == 5 and g.is_main_slice.sum() == 1
        main = g[g.is_main_slice].iloc[0]
        windows = 1 if protocol == "E1-A" else 2
        assert main.n_train_groups == N_MAIN * windows and (g.n_train_groups == main.n_train_groups).all()      # five times the training groups
        assert (g.n_test_groups == N_MAIN).all()
        assert (g.loc[~g.is_main_slice, "n_inner_val_groups"] == 0).all() and main.n_inner_val_groups > 0      # inner selection on the main slice
        assert (g.n_inner_fit_groups > 0).all()
    # the split manifest says the same: no secondary row is an inner validation row
    man = res["mm_split_manifest"]
    ids_main = set(res["mm_predictions"].meta_obs_id)
    val_ids = set(man[man.role.str.startswith("INNER_VAL")].meta_obs_id)
    assert val_ids and len(man[man.role == "TRAIN"]) == 5 * len(all_only["mm_split_manifest"][all_only["mm_split_manifest"].role == "TRAIN"])
    assert len(man[man.role.str.startswith("INNER_VAL")]) == len(all_only["mm_split_manifest"][all_only["mm_split_manifest"].role.str.startswith("INNER_VAL")])
    assert ids_main and len(res["mm_predictions"]) == len(all_only["mm_predictions"])
    # the learners are not those of the ALL-only analysis: they were fitted on five times the rows
    l5 = m5[m5.strategy == "L3-FS3"].sort_values(key).mean_regret.to_numpy()
    l1 = m1[m1.strategy == "L3-FS3"].sort_values(key).mean_regret.to_numpy()
    assert l5.shape == l1.shape and not np.array_equal(l5, l1)
    reg = res["mm_run_registry"]
    assert set(reg.e1_scope) == {"PER_TASK"} and set(reg.training_subgroups) == {"ALL/ALL|LEARNER/SEEN|LEARNER/UNSEEN|COURSE/SEEN|COURSE/UNSEEN"}


def test_joint_units_and_registered_hypothesis_rows(full):
    res, out = full
    j, rec, hyp = res["mm_metrics_joint"], res["mm_recommendations"], res["mm_hypotheses"]
    assert (out / "mm_metrics_joint.csv").exists() and json.loads((out / "mm_config.json").read_text())["config_version"] == "mm_config_v0.3"
    units = set(map(tuple, j[["protocol", "fold_id", "task_scope"]].drop_duplicates().to_numpy()))
    assert units == {(p, f, s) for p, f in (("E1-A", "W1->W2"), ("E1-B", "W1W2->W3")) for s in ("CQ", "LO", "CQ+LO")} | {("E1-A+E1-B", "W1->W2+W1W2->W3", "CQ+LO")}
    for strategy in ("B3", "L3-FS3"):
        row = j[(j.protocol == "E1-B") & (j.task_scope == "CQ+LO") & (j.strategy == strategy)].iloc[0]
        groups = rec[(rec.protocol == "E1-B") & (rec.strategy == strategy)]
        assert row.n_groups == len(groups) == 2 * N_MAIN and abs(row.mean_regret - groups.regret.mean()) < 1e-15
        pooled = j[(j.protocol == "E1-A+E1-B") & (j.strategy == strategy)].iloc[0]
        both = rec[rec.protocol.isin(["E1-A", "E1-B"]) & (rec.strategy == strategy)]
        assert pooled.n_groups == len(both) == 4 * N_MAIN and abs(pooled.mean_regret - both.regret.mean()) < 1e-15
        assert pooled.mean_regret_n_clusters == 4 * N_MAIN and row.mean_regret_n_clusters == 2 * N_MAIN
    # registered rows and their units
    assert list(hyp.analysis_role.drop_duplicates()) == [C.ROLE_PRIMARY, C.ROLE_PER_TASK, C.ROLE_REPLICATION, C.ROLE_POOLED_2FOLD, C.ROLE_TRANSFER]
    h1 = hyp[hyp.hypothesis == "H1"].set_index(["analysis_role", "task_scope"])
    assert h1.loc[(C.ROLE_PRIMARY, "CQ+LO"), "n_clusters"] == 2 * N_MAIN and h1.loc[(C.ROLE_PRIMARY, "CQ+LO"), "protocol"] == "E1-B"
    assert h1.loc[(C.ROLE_PER_TASK, "CQ"), "n_clusters"] == N_MAIN == h1.loc[(C.ROLE_PER_TASK, "LO"), "n_clusters"]
    assert h1.loc[(C.ROLE_REPLICATION, "CQ+LO"), "n_clusters"] == 2 * N_MAIN and h1.loc[(C.ROLE_REPLICATION, "CQ+LO"), "protocol"] == "E1-A"
    assert h1.loc[(C.ROLE_POOLED_2FOLD, "CQ+LO"), "n_clusters"] == 4 * N_MAIN
    a = rec[(rec.protocol == "E1-B") & (rec.strategy == "L3-FS3")].set_index("rec_group_id").regret
    b = rec[(rec.protocol == "E1-B") & (rec.strategy == "B3")].set_index("rec_group_id").regret
    assert abs(h1.loc[(C.ROLE_PRIMARY, "CQ+LO"), "estimate"] - (a - b.loc[a.index]).mean()) < 1e-15
    assert set(hyp[hyp.analysis_role == C.ROLE_TRANSFER].hypothesis) == {"H5"}
    for role in (C.ROLE_PRIMARY, C.ROLE_PER_TASK, C.ROLE_REPLICATION, C.ROLE_POOLED_2FOLD):
        assert {"H1", "H3", "H7", "H8"} <= set(hyp[hyp.analysis_role == role].hypothesis)      # H2 and H4 need FS2 and FS4, not in this small grid
    # decision 54 (b): one Holm family over every test row of the table
    status = hyp["status"] if "status" in hyp.columns else pd.Series([None] * len(hyp), index=hyp.index)
    tests = hyp[hyp.p_boot.notna() & (status != "DESCRIPTIVE")]
    adj = M.holm({str(i): p for i, p in tests.p_boot.items()})
    assert len(tests) > len(hyp[(hyp.analysis_role == C.ROLE_PRIMARY) & hyp.p_boot.notna()])
    assert np.allclose([adj[str(i)]["p_holm"] for i in tests.index], tests.p_holm.to_numpy(), rtol=0, atol=0)
    assert hyp.loc[~hyp.index.isin(tests.index), "p_holm"].isna().all() and (tests.p_holm >= tests.p_boot - 1e-15).all()
    primary = tests[tests.analysis_role == C.ROLE_PRIMARY]
    alone = M.holm({str(i): p for i, p in primary.p_boot.items()})
    assert all(primary.loc[i, "p_holm"] >= alone[str(i)]["p_holm"] - 1e-15 for i in primary.index)      # the added rows can only raise them


def test_secondary_slices_are_reports_not_tests(full):
    res, _ = full
    sec, srec, hyp = res["mm_metrics_secondary"], res["mm_recommendations_secondary"], res["mm_hypotheses"]
    slices = {f"{a}/{v}" for a, v in C.SECONDARY_SUBGROUPS}
    assert set(sec.report_slice) == slices == set(srec.report_slice) and "report_slice" not in hyp.columns
    assert set(res["mm_metrics_joint"].report_slice) == {"ALL/ALL"}
    unit = sec[(sec.protocol == "E1-B") & (sec.task_scope == "CQ+LO")]
    assert set(unit.strategy) >= set(BASELINES) | {"L1-FS0", "L3-FS3"} and (unit.n_groups == 2 * N_MAIN).all()
    learner = unit[unit.strategy == "L3-FS3"]
    assert learner.regret_minus_B3.notna().all() and (learner.status == "DESCRIPTIVE").all() and unit[unit.strategy == "B3"].regret_minus_B3.isna().all()
    assert not set(srec.rec_group_id) & set(res["mm_recommendations"].rec_group_id)
    # the baselines of a secondary slice come from the training rows of that slice (matched slice), with the k of B5 chosen on the main slice
    one = srec[(srec.report_slice == "COURSE/UNSEEN") & (srec.strategy == "B5") & (srec.fold_id == "CQ:W1W2->W3")]
    assert len(one) == N_MAIN


def test_undefined_slices_drop_out_and_the_variants_run(agg5):
    f = SY.make_synthetic(subgroups=C.MANDATORY_SUBGROUPS, undefined_slices=(("LO", "W3", "COURSE", "UNSEEN"),), **KW)
    res = run_experiment(_agg(f), MMConfig(**FAST, **FULL), "unused", write=False)
    sec = res["mm_metrics_secondary"]
    gone = sec[(sec.report_slice == "COURSE/UNSEEN") & (sec.protocol == "E1-B")]
    assert set(gone.task_scope) == {"CQ"}                          # no LO unit and therefore no joint unit for the undefined slice
    assert set(sec[(sec.report_slice == "COURSE/SEEN") & (sec.protocol == "E1-B")].task_scope) == {"CQ", "LO", "CQ+LO"}
    assert len(res["mm_metrics"]) and (res["mm_metrics"].n_groups == N_MAIN).all()
    # all-rows variant of decision 53: baselines without a subgroup key, inner validation on every group
    matched = run_experiment(agg5, MMConfig(**FAST, **FULL), "unused", write=False)
    allrows = run_experiment(agg5, MMConfig(**FAST, **FULL, baseline_scope=C.BASELINE_SCOPE_ALL_ROWS), "unused", write=False)
    n_val = lambda r: int(r["mm_split_manifest"].role.str.startswith("INNER_VAL").sum())
    assert n_val(allrows) == 5 * n_val(matched)
    key = ["fold_id", "strategy"]
    free = ["B0", "B1", "B6", "B7"]                                 # these do not read the training rows
    _same(matched["mm_metrics"][matched["mm_metrics"].strategy.isin(free)].sort_values(key),
          allrows["mm_metrics"][allrows["mm_metrics"].strategy.isin(free)].sort_values(key), key + ["n_groups", "mean_regret", "harm_rate"])
    assert set(allrows["mm_run_registry"].baseline_scope) == {"ALL_ROWS"}
    # task-pooled variant of Appendix E.4 with the registered rows: the tasks are subsets of the pooled fold
    pooled = run_experiment(agg5, MMConfig(**FAST, training_subgroups=C.MANDATORY_SUBGROUPS, hypothesis_rows=C.HYP_ROWS_REGISTERED), "unused", write=False)
    assert set(pooled["mm_metrics"].fold_id) == {"W1W2->W3"} and (pooled["mm_metrics"].n_groups == 2 * N_MAIN).all()
    hp = pooled["mm_hypotheses"]
    assert set(hp.analysis_role) == {C.ROLE_PRIMARY, C.ROLE_PER_TASK} and set(hp[hp.analysis_role == C.ROLE_PER_TASK].task_scope) == {"CQ", "LO"}
    # sensitivity: flagged secondary rows never enter a fit
    flagged = agg5.copy()
    flagged[C.SMALL_SUBGROUP_FLAG] = ((flagged.task == "LO") & (flagged.subgroup_axis == "COURSE") & (flagged.subgroup_value == "UNSEEN")).to_numpy()
    drop = run_experiment(flagged, MMConfig(**FAST, **FULL, small_subgroup_policy=C.SMALL_SUBGROUP_DROP), "unused", write=False)
    comp = drop["mm_fold_composition"].set_index(["fold_id", "report_slice"])
    assert comp.loc[("LO:W1W2->W3", "COURSE/UNSEEN"), "n_train_rows"] == 0 and comp.loc[("LO:W1W2->W3", "COURSE/UNSEEN"), "n_test_groups"] == N_MAIN
    assert comp.loc[("CQ:W1W2->W3", "COURSE/UNSEEN"), "n_train_rows"] > 0 and comp.loc[("LO:W1W2->W3", "ALL/ALL"), "n_train_rows"] > 0
    with pytest.raises(KeyError):
        run_experiment(agg5.drop(columns=[C.SMALL_SUBGROUP_FLAG], errors="ignore"), MMConfig(**FAST, **FULL, small_subgroup_policy=C.SMALL_SUBGROUP_DROP),
                       "unused", write=False)


def test_cli_design_full(tmp_path, capsys):
    syn, rel, mm = tmp_path / "syn", tmp_path / "rel", tmp_path / "mm"
    assert cli.main(["synthetic", "--out", str(syn), "--n-seeds", "2", "--models", "RNN", "PATCHTST", "--five-subgroups"]) == 0
    assert cli.main(["assemble", "--facts", str(syn / "synthetic_facts.parquet"), "--resources", str(syn / "synthetic_resources.parquet"),
                     "--state", str(syn / "synthetic_state_profile.parquet"), "--model-context", str(syn / "synthetic_model_context.parquet"),
                     "--out", str(rel), "--require-subgroups"]) == 0
    capsys.readouterr()
    assert cli.main(["run", "--meta", str(rel / "meta_dataset_seed_agg.parquet"), "--out", str(mm), "--design", "full", "--protocols", "E1-A", "E1-B",
                     "--learners", "L3", "--extra-learners", "--n-trials", "1", "--learner-seeds", "1", "--progress"]) == 0
    printed = capsys.readouterr().out
    assert "cell 1/6 L3-FS0 start" in printed and "mm_metrics_joint" in printed
    E.PROGRESS = False
    cfg = json.loads((mm / "mm_config.json").read_text())
    assert cfg["config_version"] == "mm_config_v0.3" and cfg["e1_scope"] == "PER_TASK" and cfg["hypothesis_rows"] == "REGISTERED" and len(cfg["training_subgroups"]) == 5
    hyp = pd.read_csv(mm / "mm_hypotheses.csv")
    assert {C.ROLE_PRIMARY, C.ROLE_PER_TASK, C.ROLE_REPLICATION, C.ROLE_POOLED_2FOLD} <= set(hyp.analysis_role)
    assert all((mm / f"{t}.csv").exists() for t in NEW_TABLES)
    # the presets can be overridden one option at a time: the robustness variant of Table 42 with the registered folds
    mm2 = tmp_path / "mm_all_only"
    assert cli.main(["run", "--meta", str(rel / "meta_dataset_seed_agg.parquet"), "--out", str(mm2), "--design", "full", "--training-subgroups", "all-only",
                     "--protocols", "E1-B", "--learners", "L3", "--extra-learners", "--n-trials", "1", "--learner-seeds", "1"]) == 0
    cfg2 = json.loads((mm2 / "mm_config.json").read_text())
    assert cfg2["training_subgroups"] == [["ALL", "ALL"]] and cfg2["e1_scope"] == "PER_TASK" and not (mm2 / "mm_metrics_secondary.csv").exists()
    # the plan can be frozen and enforced: --digest-only reads no table, --expect-digest refuses any other configuration
    common = ["--design", "full", "--release-id", "FIVE_r1", "--protocols", "E1-A", "E1-B", "E2", "E3", "--learners", "L1", "L2", "L3", "L4", "--extra-learners", "L5", "L6",
              "--n-trials", "50", "--learner-seeds", "5"]
    capsys.readouterr()
    assert cli.main(["run", "--meta", "NOT_READ", "--out", "NOT_WRITTEN", "--digest-only"] + common) == 0
    frozen = json.loads(capsys.readouterr().out)
    expect = MMConfig(meta_release_id="FIVE_r1", protocols=("E1-A", "E1-B", "E2", "E3"), **FULL)
    assert frozen["mm_config_sha256"] == expect.sha256() and frozen["mm_config"] == expect.to_dict() and not (tmp_path / "NOT_WRITTEN").exists()
    assert cli.main(["run", "--meta", "NOT_READ", "--out", "X", "--digest-only", "--conservative"] + common) == 0
    assert json.loads(capsys.readouterr().out)["mm_config_sha256"] != frozen["mm_config_sha256"]
    mm3, mm4 = tmp_path / "mm_refused", tmp_path / "mm_accepted"
    small = ["run", "--meta", str(rel / "meta_dataset_seed_agg.parquet"), "--design", "full", "--training-subgroups", "all-only", "--protocols", "E1-B", "--learners", "L3",
             "--extra-learners", "--n-trials", "1", "--learner-seeds", "1"]
    assert cli.main(small + ["--out", str(mm3), "--expect-digest", frozen["mm_config_sha256"]]) == 3
    assert not mm3.exists() and "nothing was run" in capsys.readouterr().err
    assert cli.main(small + ["--out", str(mm4), "--expect-digest", (mm2 / "mm_config_sha256.txt").read_text().strip()]) == 0      # the plan of the run above
    assert (mm4 / "mm_config_sha256.txt").read_text() == (mm2 / "mm_config_sha256.txt").read_text()
