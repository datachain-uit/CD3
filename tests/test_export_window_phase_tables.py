"""Window x phase tables keep the registered grain and never pool families."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import export_window_phase_tables as wp  # noqa: E402


def long_frame(seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for family in ("LSTM", "GRU"):
        for split in ("TEST", "VALIDATION"):
            for window in ("W1", "W2", "W3"):
                for phase in ("P1", "P2", "P3", "P4"):
                    for index in range(17):
                        rows.append({"model_name": family, "eval_split": split, "window_id": window, "phase_id": phase,
                                     "pipeline_id": f"V{index}", "acctempo_m3": float(rng.uniform(0.6, 0.75)),
                                     "f1_macro": float(rng.uniform(0.7, 0.73)), "balanced_acc": float(rng.uniform(0.68, 0.72))})
    return pd.DataFrame(rows)


def test_tables_have_one_cell_per_window_phase_and_group_summary_is_labelled(tmp_path) -> None:
    long = long_frame()
    sanity = long[["model_name", "eval_split", "window_id", "phase_id", "pipeline_id"]].copy()
    sanity["s_ent"] = 0.1
    metrics_path, sanity_path = tmp_path / "m.parquet", tmp_path / "s.parquet"
    long.to_parquet(metrics_path, index=False); sanity.to_parquet(sanity_path, index=False)
    merged = wp.load_long(metrics_path, sanity_path)
    assert "s_ent" in merged.columns and len(merged) == len(long)
    receipt = wp.export(merged, tmp_path / "out", ["acctempo_m3", "f1_macro", "s_ent", "s_perf"])
    assert receipt["missing_metrics"] == ["s_perf"] and receipt["metrics"] == ["acctempo_m3", "f1_macro", "s_ent"]
    table = pd.read_csv(tmp_path / "out" / "LSTM_TEST_acctempo_m3_window_phase.csv", index_col=0)
    assert list(table.index) == [f"V{i}" for i in range(17)] and table.shape == (17, 12)
    assert list(table.columns)[:4] == ["W1/P1", "W1/P2", "W1/P3", "W1/P4"]
    cell = long[(long.model_name == "LSTM") & (long.eval_split == "TEST") & (long.window_id == "W2") & (long.phase_id == "P3") & (long.pipeline_id == "V5")]
    assert abs(table.loc["V5", "W2/P3"] - float(cell["acctempo_m3"].iloc[0])) < 1e-12
    group = pd.read_csv(tmp_path / "out" / "GROUP_TEST_acctempo_m3_imputer_vs_balanced.csv")
    assert set(group["group"]) == {"imputer_only", "balanced"} and set(group["model_name"]) == {"LSTM", "GRU"}
    assert set(group.loc[group.group == "imputer_only", "n_pipelines"]) == {5} and set(group.loc[group.group == "balanced", "n_pipelines"]) == {12}
    assert group["averaging_rule"].str.contains("one family, one window, one phase").all()
    trend = pd.read_csv(tmp_path / "out" / "TREND_TEST_acctempo_m3_P4_minus_P1.csv")
    assert len(trend) == 2 * 3 * 17 and np.allclose(trend["P4_minus_P1"], trend["P4"] - trend["P1"])


def test_duplicate_cells_are_refused(tmp_path) -> None:
    long = long_frame()
    dup = pd.concat([long, long.iloc[[0]]], ignore_index=True)
    path = tmp_path / "dup.parquet"; dup.to_parquet(path, index=False)
    try:
        wp.load_long(path, None)
    except ValueError as error:
        assert "duplicate" in str(error)
    else:
        raise AssertionError("duplicate rows must be refused")


def test_cli(tmp_path) -> None:
    path = tmp_path / "m.parquet"; long_frame(1).to_parquet(path, index=False)
    assert wp.main(["--metrics", str(path), "--out", str(tmp_path / "o"), "--metric", "f1_macro"]) == 0
    receipt = json.loads((tmp_path / "o" / "receipt.json").read_text(encoding="utf-8"))
    assert receipt["metrics"] == ["f1_macro"] and receipt["n_rows"] == 2 * 2 * 12 * 17


def test_mixed_seed_is_refused(tmp_path) -> None:
    import pytest
    data = long_frame()
    data['task'] = 'CQ'
    data['seed'] = 42
    data.loc[0, 'seed'] = 43
    path = tmp_path / 'mixed.parquet'
    data.to_parquet(path, index=False)
    with pytest.raises(ValueError, match='mixed seed'):
        wp.load_long(path, None)
