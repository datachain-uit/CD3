# -*- coding: utf-8 -*-
"""Release 0.2.5 (2026-11-20): the cost basis follows the run configuration; estimates fill an empty run-energy column;
an energy basis on the seed-aggregated table needs every planned seed. SYNTHETIC fixture only."""
import numpy as np
import pandas as pd
import pytest

from metamodel import assemble as A
from metamodel import contracts as C
from metamodel import experiment as E

STRICT = C.ENERGY_MEASURED_TYPES_STRICT
WITH_EST = C.ENERGY_MEASURED_TYPES_WITH_ESTIMATE


def _assemble(f, resources, types=STRICT):
    return A.assemble_seed_level(f["facts"], resources=resources, state_profile=f["state_profile"], model_context=f["model_context"],
                                 provenance={"meta_release_id": "TEST"}, energy_measured_types=types)


def test_estimate_fills_an_empty_run_energy_column(synthetic_small):
    """LO static-v2 resource layout: an entirely empty energy_gpu_run_kwh next to the filled NVML estimate (releases full42 and 20261119)."""
    f = synthetic_small
    res = f["resources"].copy()
    res["energy_gpu_run_kwh"] = np.nan
    sl = _assemble(f, res)
    test = sl[sl["eval_split"] == "TEST"]
    assert test[test.task == "CQ"]["energy_gpu_run_kwh_after"].notna().all()          # 0.2.4 left these empty
    assert test[test.task == "LO"]["energy_gpu_run_kwh_after"].isna().all()           # the fixture has no LO energy at all
    ref = _assemble(f, f["resources"])
    pd.testing.assert_series_equal(sl["energy_gpu_run_kwh_after"], ref["energy_gpu_run_kwh_after"])
    # a filled run value wins over the estimate, row by row
    res2 = f["resources"].copy()
    res2["energy_gpu_run_kwh"] = np.nan
    pick = res2.index[(res2.task == "CQ") & (res2.pipeline_id == "V3")]
    res2.loc[pick, "energy_gpu_run_kwh"] = 123.0
    sl2 = _assemble(f, res2)
    v3 = sl2[(sl2.task == "CQ") & (sl2.pipeline_id == "V3")]
    other = sl2[(sl2.task == "CQ") & (sl2.pipeline_id == "V4")]
    assert (v3["energy_gpu_run_kwh_after"] == 123.0).all() and (other["energy_gpu_run_kwh_after"] != 123.0).all()


def test_seed_agg_records_seeds_with_energy(seed_agg):
    agg = seed_agg
    assert {A.ENERGY_N_SEEDS_COL, A.ENERGY_TYPES_COL} <= set(agg.columns)
    assert (agg[agg.task == "CQ"][A.ENERGY_N_SEEDS_COL] == 2).all() and (agg[agg.task == "LO"][A.ENERGY_N_SEEDS_COL] == 0).all()
    assert set(agg[agg.task == "CQ"][A.ENERGY_TYPES_COL]) == {"NVML_POWER_SAMPLING_ESTIMATE"} and set(agg[agg.task == "LO"][A.ENERGY_TYPES_COL]) == {""}
    assert set(agg[agg.task == "CQ"]["cost_basis_agg"]) == {"ENERGY"} and set(agg[agg.task == "LO"]["cost_basis_agg"]) == {"TIME"}


def test_seed_agg_energy_basis_needs_every_planned_seed(synthetic_small):
    """CQ F1 of seed 43 in the real grid has no energy value: the aggregated group must fall back to TIME, not average the other seeds."""
    f = synthetic_small
    res = f["resources"].copy()
    hole = (res.task == "CQ") & (res.model_name == "RNN") & (res.seed == 43)
    res.loc[hole, "energy_gpu_estimated_kwh"] = np.nan
    res.loc[hole, "energy_measurement_type"] = "UNAVAILABLE"
    sl = _assemble(f, res, WITH_EST)
    agg = A.aggregate_seeds(sl, planned_seeds=(42, 43), energy_measured_types=WITH_EST)
    cq = agg[agg.task == "CQ"]
    assert set(cq[cq.model_name == "RNN"]["cost_basis_agg"]) == {"TIME"}
    assert (cq[cq.model_name == "RNN"][A.ENERGY_N_SEEDS_COL] == 1).all()
    assert cq[cq.model_name == "RNN"]["energy_gpu_run_kwh_ratio_mean"].notna().all()          # the mean exists but rests on one seed
    assert set(cq[cq.model_name == "LSTM"]["cost_basis_agg"]) == {"ENERGY"}
    assert np.allclose(cq[cq.model_name == "RNN"]["cost_ratio_used_agg"], cq[cq.model_name == "RNN"]["time_run_total_s_ratio_mean"])


def test_run_time_cost_basis_follows_the_run_configuration(synthetic_small):
    """A release assembled with the strict types (every stored basis = TIME) analysed with estimates accepted must switch to ENERGY
    where every candidate and every planned seed has a value. Until 0.2.4 the stored column was read and nothing changed."""
    f = synthetic_small
    sl = _assemble(f, f["resources"], STRICT)
    agg = A.aggregate_seeds(sl, planned_seeds=(42, 43), energy_measured_types=STRICT)
    assert set(agg["cost_basis_agg"]) == {"TIME"}
    strict, n_s = E.prepare_frame(agg, E.MMConfig(energy_measured_types=STRICT))
    est, n_e = E.prepare_frame(agg, E.MMConfig(energy_measured_types=WITH_EST))
    assert n_s["cost_ratio"] == n_e["cost_ratio"] == "cost_ratio_run" and n_e["cost_basis_rule"] == "ALL_PLANNED_SEEDS"
    assert set(strict["cost_basis_run"]) == {"TIME"}
    assert np.allclose(strict["cost_ratio_run"], strict["cost_ratio_used_agg"])                 # strict run == stored labels
    assert set(est[est.task == "CQ"]["cost_basis_run"]) == {"ENERGY"} and set(est[est.task == "LO"]["cost_basis_run"]) == {"TIME"}
    cq = est[est.task == "CQ"]
    assert np.allclose(cq["cost_ratio_run"], cq["energy_gpu_run_kwh_ratio_mean"])
    assert not np.allclose(cq["cost_ratio_run"], cq["time_run_total_s_ratio_mean"])
    tab = E.cost_basis_table(est, n_e, "digest")
    assert set(tab[tab.task == "CQ"]["cost_basis"]) == {"ENERGY"} and tab["n_groups"].sum() == est["rec_group_id"].nunique()


def test_legacy_seed_agg_refuses_a_silent_energy_flag(seed_agg):
    legacy = seed_agg.drop(columns=[A.ENERGY_N_SEEDS_COL, A.ENERGY_TYPES_COL])
    df, names = E.prepare_frame(legacy, E.MMConfig(energy_measured_types=STRICT))
    assert names["cost_basis_rule"] == "LEGACY_FIRST_SEED_TYPE" and set(df["cost_basis_run"]) == {"TIME"}
    with pytest.raises(ValueError, match="metamodel < 0.2.5"):
        E.prepare_frame(legacy, E.MMConfig(energy_measured_types=WITH_EST))


def test_registry_records_the_package_version_and_cost_basis(synthetic_small, tmp_path):
    f = synthetic_small
    sl = _assemble(f, f["resources"], STRICT)
    agg = A.aggregate_seeds(sl, planned_seeds=(42, 43), energy_measured_types=STRICT)
    cfg = E.MMConfig(protocols=("E1-B",), learners=("L1",), extra_learners=(), feature_sets=("FS3",), n_trials=1, learner_seeds=(0,),
                     negative_control=False, energy_measured_types=WITH_EST, bootstrap_b=50)
    r = E.run_experiment(agg, cfg, tmp_path / "mm")
    reg = r["mm_run_registry"]
    assert reg["metamodel_version"].str.startswith("0.3.1").all() and set(reg["cost_basis_rule"]) == {"ALL_PLANNED_SEEDS"}
    cb = r["mm_cost_basis"]
    assert set(cb[cb.task == "CQ"]["cost_basis"]) == {"ENERGY"} and (tmp_path / "mm" / "mm_cost_basis.csv").exists()
    rec = r["mm_recommendations"]
    assert rec["log2_cost_ratio_recommended"].notna().any()


def test_l2_random_fallback_draws_valid_max_features():
    """Without Optuna the ExtraTrees search fell over on max_features = '0.5' (a numpy string)."""
    from metamodel import learners as L
    rng = np.random.default_rng(0)
    seen = {repr(L.sample_params("L2", rng, as_rng=True)["max_features"]) for _ in range(60)}
    assert seen == {"0.3", "0.5", "'sqrt'"}
