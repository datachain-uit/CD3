# -*- coding: utf-8 -*-
"""End-to-end smoke test on the SYNTHETIC fixture: assemble -> freeze -> run E1-A/E1-B with a tiny grid."""
import dataclasses
import json
from pathlib import Path

import numpy as np
import pandas as pd

from metamodel import cli
from metamodel.experiment import MMConfig, run_experiment


def test_run_experiment_small_grid(seed_agg, tmp_path):
    cfg = MMConfig(meta_release_id="TEST", objective="PAPER_COMPOSITE_CAL", protocols=("E1-A", "E1-B"),
                   feature_sets=("FS0", "FS3", "FS4"), learners=("L1", "L3"), extra_learners=("L6",), learner_seeds=(0, 1),
                   n_trials=2, bootstrap_b=100, include_b7=True,
                   energy_measured_types=("MEASURED", "NVML_COUNTER", "NVML_POWER_SAMPLING_ESTIMATE"))
    res = run_experiment(seed_agg, cfg, tmp_path / "mm")
    m = res["mm_metrics"]
    assert len(m) and {"B0", "B1", "B3", "L3-FS3", "L1-FS0", "L6-FS3"} <= set(m["strategy"])
    assert (m.loc[m.strategy == "B0", "mean_regret"] == 0).all()
    e1b = m[(m.protocol == "E1-B")]
    assert e1b.loc[e1b.strategy == "L3-FS3", "mean_regret"].iloc[0] <= e1b.loc[e1b.strategy == "B1", "mean_regret"].iloc[0]
    assert "gap_closure_vs_B3" in e1b.columns
    assert (tmp_path / "mm" / "mm_config_sha256.txt").exists() and (tmp_path / "mm" / "mm_metrics.csv").exists()
    reg = res["mm_run_registry"]
    assert (reg["config_sha256"] == cfg.sha256()).all()
    assert len(res["mm_predictions"]) and len(res["mm_feature_importance"]) and len(res["mm_split_manifest"])
    nc = res["mm_negative_control"]
    assert len(nc) == 2 and "MQ08_pass" in nc.columns
    hyp = res["mm_hypotheses"]
    assert {"H1", "H3", "H4", "H6", "H7", "H8"} <= set(hyp["hypothesis"])      # H2 needs FS2, H5 needs E2 (omitted here)
    h8 = hyp[hyp.hypothesis == "H8"]
    assert len(h8) >= 2 and h8["comparison"].str.contains("phase_index").any() and h8["comparison"].str.contains("tr_missing_rate").any()
    # release 0.2.4 (author decision 2026-11-13, Q-34 (a)): the phase row is the test and needs >= 10 clusters; the state row is descriptive
    assert cfg.h8_min_clusters == 10 and dataclasses.replace(cfg, h8_min_clusters=11).sha256() != cfg.sha256()
    desc = h8[h8["comparison"].str.contains("tr_missing_rate")]
    if "estimate" in desc.columns and desc["estimate"].notna().any():
        assert (desc["status"] == "DESCRIPTIVE").all() and not desc["supported"].astype(bool).any() and desc["comparison"].str.contains("descriptive").all()
        assert desc["p_holm"].isna().all()                      # outside the Holm family
    ph = h8[h8["comparison"].str.contains("phase_index") & h8["n_clusters"].notna()]
    assert not ph.loc[ph["n_clusters"] < 10, "supported"].astype(bool).any()
    assert "B7" in set(m["strategy"]) and "tempo_dq_quadrant" not in m.columns
    assert hyp.loc[hyp["supported"].notna(), "supported"].isin([True, False]).all()


def test_cli_roundtrip(tmp_path):
    syn = tmp_path / "syn"
    assert cli.main(["synthetic", "--out", str(syn), "--n-seeds", "2", "--models", "RNN", "LSTM"]) == 0
    out = tmp_path / "l3"
    assert cli.main(["assemble", "--facts", str(syn / "synthetic_facts.parquet"), "--resources", str(syn / "synthetic_resources.parquet"),
                     "--state", str(syn / "synthetic_state_profile.parquet"), "--model-context", str(syn / "synthetic_model_context.parquet"),
                     "--out", str(out), "--accept-energy-estimates"]) == 0
    man = json.loads((out / "meta_release_manifest.json").read_text())
    assert man["synthetic"] is True and man["n_rows_seed_level"] == 2 * 3 * 2 * 2 * 17 * 4 * 2
    assert (out / "meta_column_dictionary.csv").exists()
    mm = tmp_path / "mm"
    assert cli.main(["run", "--meta", str(out / "meta_dataset_seed_agg.parquet"), "--out", str(mm), "--protocols", "E1-B",
                     "--learners", "L3", "--extra-learners", "--n-trials", "1", "--learner-seeds", "1", "--accept-energy-estimates"]) == 0
    reg = pd.read_csv(mm / "mm_run_registry.csv")
    assert "SYNTHETIC" in str(json.loads((mm / "mm_config.json").read_text())["notes"])
