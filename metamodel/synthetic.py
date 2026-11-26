# -*- coding: utf-8 -*-
"""SYNTHETIC fixture for tests and dry runs. **Never a source of reported numbers.**

The generator produces long facts in the R4 export grain, per-run resources, a state profile (Z_D / Z_DQ / Z_T) and a
model-context table with planted, documented structure: the effect of imputation grows with the missing rate, the
effect of balancing grows with the imbalance ratio, both are attenuated at later phases, and every realised metric is
built from these effects plus noise. Every frame carries ``synthetic = True``.
"""
from __future__ import annotations

from typing import Dict, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from . import contracts as C

SYNTHETIC_FLAG = "synthetic"


def make_synthetic(*, tasks: Sequence[str] = ("CQ", "LO"), windows: Sequence[str] = C.WINDOWS, seeds: Sequence[int] = C.MASTER_SEEDS,
                   models: Sequence[str] = ("RNN", "LSTM", "GRU", "BILSTM", "PATCHTST"), phases: Sequence[str] = C.PHASES,
                   splits: Sequence[str] = C.EVAL_SPLITS, noise: float = 0.01, rng_seed: int = 20261024,
                   missing_energy_for: Sequence[str] = ("LO",),
                   subgroups: Sequence[Tuple[str, str]] = (("ALL", "ALL"),),
                   undefined_slices: Sequence[Tuple[str, str, str, str]] = ()) -> Dict[str, pd.DataFrame]:
    """``subgroups`` (0.2.6): subgroup slices to generate besides (ALL, ALL), e.g. ``contracts.MANDATORY_SUBGROUPS``. The ALL rows are
    the same with or without them (separate random stream). ``undefined_slices``: (task, window_id, subgroup_axis, subgroup_value)
    whose slice holds a single class, so that every metric of the slice is NaN (n_eval_samples kept)."""
    rng = np.random.default_rng(rng_seed)
    # state slices: one row per (task, window, phase, split)
    state_rows = []
    for t in tasks:
        for w in windows:
            for p in phases:
                for sp in splits:
                    pi, q = C.PHASE_INDEX[p]
                    miss = float(np.clip(0.35 - 0.06 * pi + 0.1 * (t == "LO") + rng.normal(0, 0.03), 0.02, 0.9))
                    ir = float(np.clip(20 + 15 * (t == "LO") + 4 * C.WINDOW_INDEX[w] + rng.normal(0, 3), 2, 200))
                    state_rows.append({
                        "task": t, "feature_regime": "PRIMARY", "window_id": w, "phase_id": p, "cohort": C.COHORT_FIXED,
                        "eval_split": sp, "subgroup_axis": "ALL", "subgroup_value": "ALL",
                        # Z_D
                        "tr_n_enrollments": int(1_500_000 + 400_000 * (C.WINDOW_INDEX[w] - 1) + rng.integers(-5000, 5000)),
                        "ev_n_enrollments": int(175_000 + rng.integers(-2000, 2000)), "tr_n_features_total": 300, "tr_imbalance_ratio": ir,
                        "tr_minority_ratio": 1.0 / ir, "tr_class_entropy_norm": float(np.clip(0.3 - ir / 1000, 0.01, 1)),
                        "ev_mean_observed_fraction": q,
                        # Z_DQ
                        "tr_missing_rate": miss, "ev_missing_rate": float(np.clip(miss + rng.normal(0, 0.02), 0, 1)),
                        "tr_unavailable_rate": float(1 - q), "tr_sparsity_cell": float(np.clip(0.6 + rng.normal(0, 0.05), 0, 1)),
                        "tr_zero_activity_ratio": float(np.clip(0.2 + rng.normal(0, 0.03), 0, 1)),
                        "tr_missing_label_mi_max": float(abs(rng.normal(0.05, 0.02))),
                        # Z_T
                        "drift_tr_ev_psi_mean": float(abs(rng.normal(0.05 + 0.03 * (C.WINDOW_INDEX[w] - 1), 0.02))),
                        "ev_behavior_growth_rate": float(abs(rng.normal(1.0, 0.2))), "ev_train_overlap_share": float(np.clip(rng.uniform(0.6, 1.0), 0, 1)),
                        "drift_window_prev_psi_mean": np.nan if w == "W1" else float(abs(rng.normal(0.08, 0.03))),
                        "tr_missing_rate_delta_prev": np.nan if p == "P1" else float(rng.normal(-0.05, 0.01)),
                        "label_drift_tr_ev_jsd": float(abs(rng.normal(0.1, 0.03))),      # X_RESTRICTED (must never enter inputs)
                        "ev_imbalance_ratio": float(ir * rng.uniform(0.8, 1.2)),         # X_RESTRICTED
                        SYNTHETIC_FLAG: True,
                    })
    state = pd.DataFrame(state_rows)
    # model context
    mc = pd.DataFrame([{"model_name": m, "param_count_total": {"RNN": 60_000, "LSTM": 200_000, "GRU": 150_000, "BILSTM": 400_000, "PATCHTST": 900_000}.get(m, 1e5),
                        "lr": 1e-3, "batch_size": 2048, "max_epochs": 50, "patch_len": 2 if m == "PATCHTST" else np.nan, SYNTHETIC_FLAG: True} for m in models])
    mc["log10_param_count"] = np.log10(mc["param_count_total"])
    # facts
    fact_rows, res_rows = [], []
    for t in tasks:
        for w in windows:
            for s in seeds:
                for m in models:
                    model_eff = {"RNN": 0.0, "LSTM": 0.01, "GRU": 0.008, "BILSTM": 0.005, "PATCHTST": -0.005}.get(m, 0.0)
                    for pipe in C.PIPELINES:
                        pid = pipe["pipeline_id"]
                        base_time = 250 + 60 * (pipe["has_imputation"]) + 40 * pipe["has_balancing"] + {"EXTRATREES": 90, "MICE": 160}.get(pipe["imputer"], 0)
                        time_s = float(base_time * rng.uniform(0.9, 1.1))
                        energy = np.nan if t in missing_energy_for else float(time_s * 1.2e-5 * rng.uniform(0.95, 1.05))
                        res_rows.append({"task": t, "feature_regime": "PRIMARY", "window_id": w, "seed": s, "model_name": m, "pipeline_id": pid,
                                         "train_seconds": time_s, "elapsed_seconds": time_s * 1.3, "energy_gpu_estimated_kwh": energy,
                                         "energy_measurement_type": None if np.isnan(energy) else "NVML_POWER_SAMPLING_ESTIMATE",
                                         "execution_backend": "SYNTHETIC", SYNTHETIC_FLAG: True})
                        for p in phases:
                            pi, q = C.PHASE_INDEX[p]
                            st = state[(state.task == t) & (state.window_id == w) & (state.phase_id == p) & (state.eval_split == "TEST")].iloc[0]
                            att = 1.0 - 0.15 * (pi - 1)
                            imp_eff = {"NONE": 0.0, "MEDIAN": 0.6, "MEAN": 0.5, "EXTRATREES": 0.9, "MICE": 1.0}[pipe["imputer"]] * 0.08 * (st.tr_missing_rate - 0.1) * att
                            bal_eff = {"NONE": 0.0, "CDSMOTE": 0.8, "SASMOTE": 1.0, "RADIUS_SMOTE": 0.4}[pipe["balancer"]] * 0.0015 * (st.tr_imbalance_ratio - 10) * att
                            seed_noise = rng.normal(0, noise)
                            for sp in splits:
                                split_shift = 0.03 if sp == "VALIDATION" else 0.0
                                perf_base = 0.60 + 0.05 * pi + model_eff + split_shift
                                mf = float(np.clip(perf_base + imp_eff + bal_eff + seed_noise + rng.normal(0, noise / 2), 0.05, 0.99))
                                ba = float(np.clip(mf - 0.03 + rng.normal(0, noise / 2), 0.05, 0.99))
                                mcc = float(np.clip(mf - 0.2, -1, 1)); kappa = float(np.clip(mf - 0.22, -1, 1))
                                s_perf = float(np.prod(np.clip([mf, ba, (mcc + 1) / 2, (kappa + 1) / 2], C.EPS_FLOOR, 1)) ** 0.25)
                                s_ent = float(np.clip(0.15 + 0.25 * pipe["has_balancing"] - 0.03 * (pi - 1) + rng.normal(0, 0.02), C.EPS_FLOOR, 1))
                                s_cal = float(np.clip(0.97 - 0.01 * pipe["has_balancing"] + rng.normal(0, 0.005), C.EPS_FLOOR, 1))
                                s_maj, s_drift, s_nan = float(np.clip(0.985 + rng.normal(0, 0.005), 0, 1)), 0.98, 1.0
                                # real-row contract: s_eff is a run-level constant (per window); s_leak is a property of
                                # (window, split, phase), identical across pipelines and models (check 38)
                                s_eff = 0.66 + 0.01 * C.WINDOW_INDEX[w]
                                s_leak = 0.25 - 0.02 * (pi - 1) + (0.01 if sp == "VALIDATION" else 0.0) + 0.005 * C.WINDOW_INDEX[w]
                                s_san = float(np.prod(np.clip([s_nan, s_maj, s_ent, s_drift, s_eff, s_leak], C.EPS_FLOOR, 1)) ** (1 / 6))
                                s_san2 = float(np.prod(np.clip([s_nan, s_maj, s_cal, s_drift, s_eff, s_leak], C.EPS_FLOOR, 1)) ** (1 / 6))
                                fact_rows.append({
                                    "task": t, "label_rule_version": "synthetic_rule", "label_threshold_set": "PRIMARY", "feature_regime": "PRIMARY",
                                    "window_id": w, "seed": s, "phase_id": p, "cohort": C.COHORT_FIXED, "eval_split": sp, "subgroup_axis": "ALL",
                                    "subgroup_value": "ALL", "model_name": m, "pipeline_id": pid,
                                    "f1_macro": mf, "balanced_accuracy": ba, "mcc": mcc, "cohen_kappa": kappa, "gmean_recall": ba - 0.02,
                                    "pr_auc_macro": mf - 0.05, "accuracy": 0.96, "roc_auc_macro_ovr": 0.93, "multiclass_nll": 0.15, "multiclass_brier": 0.07,
                                    "top_label_ece_15": 1 - s_cal, "s_perf": s_perf, "s_nan": s_nan, "s_maj_jsd": s_maj, "s_ent": s_ent, "s_cal": s_cal,
                                    "s_drift": s_drift, "s_eff": s_eff, "s_leak": s_leak, "s_san_plus": s_san, "s_san_plus_v2": s_san2,
                                    "acctempo_m3": float(C.acctempo(s_perf, s_san)), "acctempo_m4": float(C.acctempo(s_perf, s_san2)),
                                    "c0_recall": 0.99, "c1_recall": float(np.clip(ba - 0.3, 0, 1)), "c2_recall": float(np.clip(ba - 0.1, 0, 1)),
                                    "n_eval_samples": 178_000, "run_status": "SUCCESS", SYNTHETIC_FLAG: True,
                                })
    facts = pd.DataFrame(fact_rows)
    resources = pd.DataFrame(res_rows)
    extra = [sg for sg in subgroups if tuple(sg) != ("ALL", "ALL")]
    if extra:
        facts, state = _add_subgroups(facts, state, extra, undefined_slices, noise, rng_seed)
    return {"facts": facts, "resources": resources, "state_profile": state, "model_context": mc}


def _add_subgroups(facts: pd.DataFrame, state: pd.DataFrame, subgroups: Sequence[Tuple[str, str]],
                   undefined_slices: Sequence[Tuple[str, str, str, str]], noise: float, rng_seed: int) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """SYNTHETIC subgroup rows derived from the ALL rows (0.2.6). On each axis SEEN and UNSEEN partition the slice: the sizes add up to
    n_eval_samples of ALL; s_eff (run level) and s_leak (window x split x phase) are inherited; the slice metrics get a planted shift
    (SEEN easier than UNSEEN, the effect of imputation larger on UNSEEN) plus noise."""
    rng = np.random.default_rng(rng_seed + 1)
    # share of SEEN enrollments per (task, window, split, phase, axis): grows with the window, a little with the phase
    shares = {}
    for (t, w, sp, p), _ in state.groupby(["task", "window_id", "eval_split", "phase_id"], sort=True):
        pi = C.PHASE_INDEX[p][0]
        shares[(t, w, sp, p, "LEARNER")] = float(np.clip(0.25 + 0.10 * C.WINDOW_INDEX[w] + 0.01 * pi + rng.normal(0, 0.02), 0.05, 0.9))
        shares[(t, w, sp, p, "COURSE")] = float(np.clip(0.55 + 0.08 * C.WINDOW_INDEX[w] + 0.01 * pi + rng.normal(0, 0.02), 0.05, 0.95))
    undefined = {tuple(u) for u in undefined_slices}
    pipe = C.PIPELINE_BY_ID
    f_parts, s_parts = [facts], [state]
    for axis, value in subgroups:
        seen = value == "SEEN"
        f = facts.copy()
        f["subgroup_axis"], f["subgroup_value"] = axis, value
        share = np.array([shares[(t, w, sp, p, axis)] for t, w, sp, p in zip(f["task"], f["window_id"], f["eval_split"], f["phase_id"])])
        n_seen = np.rint(f["n_eval_samples"].to_numpy() * share).astype(int)
        f["n_eval_samples"] = n_seen if seen else f["n_eval_samples"].to_numpy() - n_seen
        has_imp = f["pipeline_id"].map(lambda v: pipe[v]["has_imputation"]).to_numpy()
        shift = (0.02 if seen else -0.03) + (0.0 if seen else 0.01) * has_imp + rng.normal(0, noise / 2, len(f))
        mf = np.clip(f["f1_macro"].to_numpy() + shift, 0.05, 0.99)
        ba = np.clip(f["balanced_accuracy"].to_numpy() + shift, 0.05, 0.99)
        mcc, kappa = np.clip(mf - 0.2, -1, 1), np.clip(mf - 0.22, -1, 1)
        f["f1_macro"], f["balanced_accuracy"], f["mcc"], f["cohen_kappa"], f["gmean_recall"], f["pr_auc_macro"] = mf, ba, mcc, kappa, ba - 0.02, mf - 0.05
        f["s_perf"] = np.prod(np.clip(np.vstack([mf, ba, (mcc + 1) / 2, (kappa + 1) / 2]), C.EPS_FLOOR, 1), axis=0) ** 0.25
        f["s_ent"] = np.clip(f["s_ent"].to_numpy() + rng.normal(0, 0.01, len(f)), C.EPS_FLOOR, 1)
        f["s_cal"] = np.clip(f["s_cal"].to_numpy() + rng.normal(0, 0.003, len(f)), C.EPS_FLOOR, 1)
        f["top_label_ece_15"] = 1 - f["s_cal"]
        f["s_maj_jsd"] = np.clip(f["s_maj_jsd"].to_numpy() + rng.normal(0, 0.003, len(f)), 0, 1)
        comp = lambda third: np.prod(np.clip(np.vstack([f["s_nan"], f["s_maj_jsd"], f[third], f["s_drift"], f["s_eff"], f["s_leak"]]).astype(float),
                                             C.EPS_FLOOR, 1), axis=0) ** (1 / 6)
        f["s_san_plus"], f["s_san_plus_v2"] = comp("s_ent"), comp("s_cal")
        f["acctempo_m3"], f["acctempo_m4"] = C.acctempo(f["s_perf"], f["s_san_plus"]), C.acctempo(f["s_perf"], f["s_san_plus_v2"])
        hit = np.array([(t, w, axis, value) in undefined for t, w in zip(f["task"], f["window_id"])])
        if hit.any():
            metric_cols = ["f1_macro", "balanced_accuracy", "mcc", "cohen_kappa", "gmean_recall", "pr_auc_macro", "accuracy", "roc_auc_macro_ovr",
                           "multiclass_nll", "multiclass_brier", "top_label_ece_15", "s_perf", "s_maj_jsd", "s_ent", "s_cal", "s_drift",
                           "s_san_plus", "s_san_plus_v2", "acctempo_m3", "acctempo_m4", "c0_recall", "c1_recall", "c2_recall"]
            f.loc[hit, metric_cols] = np.nan            # s_nan, s_eff and s_leak do not depend on the slice labels and stay
        f_parts.append(f)
        st = state.copy()
        st["subgroup_axis"], st["subgroup_value"] = axis, value
        sh = np.array([shares[(t, w, sp, p, axis)] for t, w, sp, p in zip(st["task"], st["window_id"], st["eval_split"], st["phase_id"])])
        st["ev_n_enrollments"] = np.rint(st["ev_n_enrollments"].to_numpy() * (sh if seen else 1 - sh)).astype(int)
        st["ev_missing_rate"] = np.clip(st["ev_missing_rate"].to_numpy() + (-0.02 if seen else 0.03) + rng.normal(0, 0.005, len(st)), 0, 1)
        s_parts.append(st)
    return pd.concat(f_parts, ignore_index=True), pd.concat(s_parts, ignore_index=True)
