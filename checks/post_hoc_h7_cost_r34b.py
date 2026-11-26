#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Two labelled post hoc analyses computed by the writing side from delivered files (author decisions of 2026-11-26, second pass).

A. H7 AS REGISTERED (question Q-50, option (a); registry decision 61).
   Meta-Dataset-Report v1.9.1, Table 50: "L3-FS3 with the composite objective against L3-FS3 with the Macro-F1 objective, E1-B";
   support criterion: mean difference of the S_san+ change above 0 (interval above 0) and lower limit of the difference of the
   Macro-F1 change at or above -eps. D-18 maps the composite objective to AccTEMPO_M3^(cal) (configuration full_main_cal_time) and the
   Macro-F1 objective to SECONDARY_MACRO_F1 (configuration full_obj_macrof1). The row of mm_hypotheses compares the recommended
   pipeline with V0 instead; it is copied next to the registered comparison.
   Sensitivity, as the design document repeats every test with the composite v1: full_sens_v1 against full_obj_macrof1 on S_san+ v1.

B. COST AT THE DECISION MOMENT (question Q-49, option (a); registry decision 60).
   The utility rule of the runs of record uses the relative cost RECORDED for every candidate of the scored group. Here the rule is
   applied again to the stored scores of L3-FS3 with a cost that is known before the candidate is run: the mean recorded log2
   relative cost of the same pipeline for the same task and probe model over the training rows of the fold (main report slice).
   The estimator was fixed before any of its results was computed. Outcomes are always read with the recorded cost.

Nothing is fitted. Inputs: the ten delivered run directories of phase C, the seed-aggregated table of release r2, and the analysis
package (metamodel >= 0.3.1 for the explicit cluster order of the bootstrap; frame preparation and folds are those of 0.3.0).
Every table carries the label POST_HOC. The rows are not part of the Holm family of the delivered tables.

usage: python3 post_hoc_h7_cost_r34b.py --pkg <dir that contains metamodel/> --phasec <dir with the ten runs> --meta <seed_agg.parquet> --out <dir>
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

LABEL = "POST_HOC (computed from delivered files after the runs of record; outside the Holm family of the delivered tables)"
L3FS3 = "L3-FS3"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pkg", required=True)
    ap.add_argument("--phasec", required=True)
    ap.add_argument("--meta", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    sys.path.insert(0, args.pkg)
    from metamodel import contracts as C
    from metamodel import experiment as E
    from metamodel import metrics as M
    from metamodel import verify as V

    phasec, out = Path(args.phasec), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    inputs = {}

    def read(cfg_name: str, table: str) -> pd.DataFrame:
        p = phasec / cfg_name / f"{table}.parquet"
        inputs[f"{cfg_name}/{table}.parquet"] = sha256(p)
        return pd.read_parquet(p)

    def cfg_of(cfg_name: str):
        p = phasec / cfg_name / "mm_config.json"
        inputs[f"{cfg_name}/mm_config.json"] = sha256(p)
        cfg = E.MMConfig(**json.loads(p.read_text(encoding="utf-8")))
        frozen = (phasec / cfg_name / "mm_config_sha256.txt").read_text().split()[0]
        assert cfg.sha256() == frozen, (cfg_name, cfg.sha256(), frozen)
        return cfg

    # ------------------------------------------------------------------------------------------------------------------
    # A. H7 as registered
    # ------------------------------------------------------------------------------------------------------------------
    def role_units(rec: pd.DataFrame, tasks):
        joint = "+".join(tasks)
        ua = {p: V._units(rec, p, L3FS3, tasks) for p in (C.PRIMARY_PROTOCOL, C.REPLICATION_PROTOCOL)}
        units = {(C.ROLE_PRIMARY, joint): ua[C.PRIMARY_PROTOCOL][joint]}
        for t in tasks:
            units[(C.ROLE_PER_TASK, t)] = ua[C.PRIMARY_PROTOCOL][t]
        units[(C.ROLE_REPLICATION, joint)] = ua[C.REPLICATION_PROTOCOL][joint]
        units[(C.ROLE_POOLED_2FOLD, joint)] = pd.concat([ua[C.REPLICATION_PROTOCOL][joint], ua[C.PRIMARY_PROTOCOL][joint]], ignore_index=True)
        return units

    def h7_registered(composite_cfg: str, san_col: str, tag: str):
        cfg = cfg_of(composite_cfg)
        cfg_f1 = cfg_of("full_obj_macrof1")
        assert cfg.cluster_fields == cfg_f1.cluster_fields and cfg.bootstrap_b == cfg_f1.bootstrap_b and cfg.eps == cfg_f1.eps
        rec_a, rec_b = read(composite_cfg, "mm_recommendations"), read("full_obj_macrof1", "mm_recommendations")
        hyp = read(composite_cfg, "mm_hypotheses")
        tasks = sorted(rec_a["task"].astype(str).unique())
        ua, ub = role_units(rec_a, tasks), role_units(rec_b, tasks)
        mf_col = "macro_f1_delta_mean_recommended"
        rows = []
        for (role, scope), fa in ua.items():
            fb = ub[(role, scope)]
            assert len(fa) == len(fb) and set(fa["rec_group_id"]) == set(fb["rec_group_id"]) and fa["rec_group_id"].is_unique, (role, scope)
            r_san = M.paired_cluster_bootstrap(fa, fb, san_col, cluster_fields=cfg.cluster_fields, b=cfg.bootstrap_b)
            r_mf = M.paired_cluster_bootstrap(fa, fb, mf_col, cluster_fields=cfg.cluster_fields, b=cfg.bootstrap_b)
            merged = fa[["rec_group_id", "pipeline_recommended"]].merge(fb[["rec_group_id", "pipeline_recommended"]], on="rec_group_id", suffixes=("_composite", "_macro_f1"))
            same = merged["pipeline_recommended_composite"] == merged["pipeline_recommended_macro_f1"]
            row = {"analysis": "H7_AS_REGISTERED", "variant": tag, "label": LABEL, "analysis_role": role, "task_scope": scope,
                   "composite_configuration": composite_cfg, "macro_f1_configuration": "full_obj_macrof1", "s_san_column": san_col,
                   "n_groups": r_san["n_groups"], "n_clusters": r_san["n_clusters"], "b": r_san["b"],
                   "d_s_san_mean": r_san["estimate"], "d_s_san_ci_low": r_san["ci_low"], "d_s_san_ci_high": r_san["ci_high"], "d_s_san_p_boot": r_san["p_boot"],
                   "d_macro_f1_mean": r_mf["estimate"], "d_macro_f1_ci_low": r_mf["ci_low"], "d_macro_f1_ci_high": r_mf["ci_high"],
                   "eps": cfg.eps, "supported_as_registered": bool(r_san["ci_low"] > 0 and r_mf["ci_low"] >= -cfg.eps),
                   "groups_with_the_same_recommendation": int(same.sum()), "share_same_recommendation": float(same.mean()),
                   "mean_s_san_change_composite": float(fa[san_col].mean()), "mean_s_san_change_macro_f1": float(fb[san_col].mean()),
                   "mean_macro_f1_change_composite": float(fa[mf_col].mean()), "mean_macro_f1_change_macro_f1": float(fb[mf_col].mean())}
            st = hyp[(hyp["analysis_role"] == role) & (hyp["task_scope"] == scope) & (hyp["hypothesis"] == "H7")]
            if len(st) == 1:
                st = st.iloc[0]
                row.update({"implemented_row_d_s_san_vs_V0": float(st["estimate"]), "implemented_row_ci_low": float(st["ci_low"]),
                            "implemented_row_ci_high": float(st["ci_high"]), "implemented_row_macro_f1_vs_V0_mean": float(st["macro_f1_delta_mean"]),
                            "implemented_row_macro_f1_vs_V0_ci_low": float(st["macro_f1_delta_ci_low"]), "implemented_row_supported": bool(st["supported"])})
            rows.append(row)
        return rows

    h7 = pd.DataFrame(h7_registered("full_main_cal_time", "s_san_plus_v2_delta_mean_recommended", "REGISTERED_UNDER_D18 (composite cal, S_san+ v2)")
                      + h7_registered("full_sens_v1", "s_san_plus_delta_mean_recommended", "SENSITIVITY (composite v1, S_san+ v1)"))
    h7.to_csv(out / "h7_as_registered.csv", index=False)

    # ------------------------------------------------------------------------------------------------------------------
    # B. cost at the decision moment (main configuration)
    # ------------------------------------------------------------------------------------------------------------------
    name = "full_main_cal_time"
    cfg = cfg_of(name)
    meta_path = Path(args.meta)
    inputs[f"release/{meta_path.name}"] = sha256(meta_path)
    df, names = E.prepare_frame(pd.read_parquet(meta_path), cfg)
    cost = names["cost_ratio"]
    main_mask, ok_mask = df[E.MAIN_COL].astype(bool), df[E.TRAIN_OK_COL].astype(bool)
    pred = read(name, "mm_predictions")
    pred = pred[pred["strategy"] == L3FS3]
    hyp = read(name, "mm_hypotheses")
    keep = ["meta_obs_id", "task", "window_id", "model_name", "phase_id", cost]
    tasks = sorted(df["task"].astype(str).unique())
    joint = "+".join(tasks)
    scored_units, est_rows = {}, []
    for protocol in (C.REPLICATION_PROTOCOL, C.PRIMARY_PROTOCOL):
        for fold, task, base_id in E._fold_units(df, protocol, cfg):
            train = df[fold.train & ok_mask & main_mask]
            test = df[fold.test & main_mask]
            p = pred[(pred["protocol"] == protocol) & (pred["fold_id"] == fold.fold_id)]
            assert len(p) == len(test) and set(p["meta_obs_id"]) == set(test["meta_obs_id"]), (protocol, fold.fold_id, len(p), len(test))
            sc = p[["meta_obs_id", "rec_group_id", "pipeline_id", "y", "score"]].merge(test[keep], on="meta_obs_id", how="left", validate="one_to_one")
            assert (sc["meta_obs_id"].to_numpy() == p["meta_obs_id"].to_numpy()).all()             # stored order kept
            # decision-time estimate: mean recorded log2 relative cost of the pipeline for the same task and probe model on the training rows
            tr = train[["task", "model_name", "pipeline_id", cost]].copy()
            tr["log2_cost"] = np.log2(tr[cost].astype(float).where(tr[cost] > 0))
            by_model = tr.groupby(["task", "model_name", "pipeline_id"], sort=False)["log2_cost"].mean().rename("log2_cost_estimate").reset_index()
            by_pipeline = tr.groupby(["task", "pipeline_id"], sort=False)["log2_cost"].mean().rename("log2_cost_estimate_fallback").reset_index()
            sc = sc.merge(by_model, on=["task", "model_name", "pipeline_id"], how="left").merge(by_pipeline, on=["task", "pipeline_id"], how="left")
            sc["estimate_source"] = np.where(sc["log2_cost_estimate"].notna(), "TASK_MODEL_PIPELINE", np.where(sc["log2_cost_estimate_fallback"].notna(), "TASK_PIPELINE", "NONE"))
            sc["log2_cost_estimate"] = sc["log2_cost_estimate"].fillna(sc["log2_cost_estimate_fallback"])
            sc["log2_cost_recorded"] = np.log2(sc[cost].astype(float).where(sc[cost] > 0))
            sc["cost_estimate"] = 2.0 ** sc["log2_cost_estimate"]
            sc["protocol"], sc["fold_id"] = protocol, fold.fold_id
            scored_units[(protocol, task)] = sc
            est_rows.append(sc)
    for protocol in (C.REPLICATION_PROTOCOL, C.PRIMARY_PROTOCOL):
        scored_units[(protocol, joint)] = pd.concat([scored_units[(protocol, t)] for t in tasks], ignore_index=True)
    units = {(C.ROLE_PRIMARY, joint): scored_units[(C.PRIMARY_PROTOCOL, joint)]}
    for t in tasks:
        units[(C.ROLE_PER_TASK, t)] = scored_units[(C.PRIMARY_PROTOCOL, t)]
    units[(C.ROLE_REPLICATION, joint)] = scored_units[(C.REPLICATION_PROTOCOL, joint)]
    units[(C.ROLE_POOLED_2FOLD, joint)] = pd.concat([scored_units[(C.REPLICATION_PROTOCOL, joint)], scored_units[(C.PRIMARY_PROTOCOL, joint)]], ignore_index=True)

    def picks(sc: pd.DataFrame, lam: float, cost_log2_col: str) -> pd.DataFrame:
        """argmax(score - lam * log2 cost) per group with the cost column given; the outcome columns are always the recorded ones."""
        rows = []
        for g, sub in sc.groupby("rec_group_id", sort=False):
            u = sub["score"].astype(float) - lam * sub[cost_log2_col]
            if u.notna().sum() == 0:
                continue
            i = u.idxmax()
            row = {"rec_group_id": g, "lambda": lam, "pipeline_recommended": sub.loc[i, "pipeline_id"], "y_recommended": float(sub.loc[i, "y"]),
                   "log2_cost_ratio_recommended": float(sub.loc[i, "log2_cost_recorded"]) if pd.notna(sub.loc[i, "log2_cost_recorded"]) else np.nan}
            for c in C.CLUSTER_FIELDS:
                row[c] = sub[c].iloc[0]
            rows.append(row)
        return pd.DataFrame(rows)

    h6_rows, agree_rows = [], []
    for (role, scope), sc in units.items():
        u0 = picks(sc, 0.0, "log2_cost_recorded")
        # replay of the row of record (recorded cost) with the functions of the package
        u0_pkg, u2_pkg = M.utility_outcomes(sc, 0.0, cost_col=cost), M.utility_outcomes(sc, 0.02, cost_col=cost)
        assert (u0_pkg["pipeline_recommended"].to_numpy() == u0["pipeline_recommended"].to_numpy()).all()
        r_cost = M.paired_cluster_bootstrap(u2_pkg, u0_pkg, "log2_cost_ratio_recommended", cluster_fields=cfg.cluster_fields, b=cfg.bootstrap_b)
        r_obj = M.paired_cluster_bootstrap(u2_pkg, u0_pkg, "y_recommended", cluster_fields=cfg.cluster_fields, b=cfg.bootstrap_b)
        st = hyp[(hyp["analysis_role"] == role) & (hyp["task_scope"] == scope) & (hyp["hypothesis"] == "H6")].iloc[0]
        replay_diff = max(abs(r_cost[k] - float(st[k])) for k in ("estimate", "ci_low", "ci_high", "p_boot"))
        replay_diff = max(replay_diff, abs(r_obj["estimate"] - float(st["objective_diff_mean"])), abs(r_obj["ci_low"] - float(st["objective_diff_ci_low"])))
        for lam in cfg.lambda_grid:
            if lam == 0:
                continue
            rec_run, rec_est = picks(sc, lam, "log2_cost_recorded"), picks(sc, lam, "log2_cost_estimate")
            same = rec_run["pipeline_recommended"].to_numpy() == rec_est["pipeline_recommended"].to_numpy()
            agree_rows.append({"analysis": "COST_AT_DECISION_TIME", "label": LABEL, "analysis_role": role, "task_scope": scope, "lambda": lam,
                               "n_groups": int(len(rec_run)), "groups_with_the_same_recommendation": int(same.sum()), "share_same_recommendation": float(same.mean()),
                               "groups_moved_from_lambda0_recorded_cost": int((rec_run["pipeline_recommended"].to_numpy() != u0["pipeline_recommended"].to_numpy()).sum()),
                               "groups_moved_from_lambda0_estimated_cost": int((rec_est["pipeline_recommended"].to_numpy() != u0["pipeline_recommended"].to_numpy()).sum()),
                               "mean_log2_cost_recorded_rule": float(rec_run["log2_cost_ratio_recommended"].mean()),
                               "mean_log2_cost_estimated_rule": float(rec_est["log2_cost_ratio_recommended"].mean()),
                               "mean_log2_cost_lambda0": float(u0["log2_cost_ratio_recommended"].mean()),
                               "mean_objective_recorded_rule": float(rec_run["y_recommended"].mean()),
                               "mean_objective_estimated_rule": float(rec_est["y_recommended"].mean()),
                               "mean_objective_lambda0": float(u0["y_recommended"].mean())})
            if abs(lam - 0.02) < 1e-12:
                e_cost = M.paired_cluster_bootstrap(rec_est, u0, "log2_cost_ratio_recommended", cluster_fields=cfg.cluster_fields, b=cfg.bootstrap_b)
                e_obj = M.paired_cluster_bootstrap(rec_est, u0, "y_recommended", cluster_fields=cfg.cluster_fields, b=cfg.bootstrap_b)
                h6_rows.append({"analysis": "COST_AT_DECISION_TIME", "label": LABEL, "analysis_role": role, "task_scope": scope, "lambda": lam,
                                "n_groups": e_cost["n_groups"], "n_clusters": e_cost["n_clusters"], "b": e_cost["b"],
                                "record_d_log2_cost": float(st["estimate"]), "record_ci_low": float(st["ci_low"]), "record_ci_high": float(st["ci_high"]),
                                "record_objective_diff_mean": float(st["objective_diff_mean"]), "record_objective_diff_ci_low": float(st["objective_diff_ci_low"]),
                                "record_supported": bool(st["supported"]), "replay_of_record_max_abs_diff": float(replay_diff),
                                "decision_time_d_log2_cost": e_cost["estimate"], "decision_time_ci_low": e_cost["ci_low"], "decision_time_ci_high": e_cost["ci_high"],
                                "decision_time_p_boot": e_cost["p_boot"], "decision_time_objective_diff_mean": e_obj["estimate"],
                                "decision_time_objective_diff_ci_low": e_obj["ci_low"], "eps": cfg.eps,
                                "decision_time_supported_by_the_criterion_of_H6": bool(e_cost["estimate"] < 0 and e_obj["ci_low"] >= -cfg.eps)})
    h6 = pd.DataFrame(h6_rows)
    agree = pd.DataFrame(agree_rows)
    h6.to_csv(out / "cost_decision_time_h6.csv", index=False)
    agree.to_csv(out / "cost_decision_time_agreement.csv", index=False)

    # how well the cost is anticipated: candidates other than V0 (the relative cost of V0 is 1 by construction)
    allsc = pd.concat(est_rows, ignore_index=True)
    cand = allsc[allsc["pipeline_id"] != "V0"].copy()
    cand["error"] = cand["log2_cost_estimate"] - cand["log2_cost_recorded"]
    ant_rows = []
    for (protocol, task), g in list(cand.groupby(["protocol", "task"], sort=False)) + [((p_, joint), cand[cand["protocol"] == p_]) for p_ in (C.REPLICATION_PROTOCOL, C.PRIMARY_PROTOCOL)]:
        e = g["error"].dropna()
        rho, cheapest = [], []
        for _gid, sub in g.groupby("rec_group_id", sort=False):
            if sub["log2_cost_estimate"].notna().sum() >= 3 and sub["log2_cost_estimate"].nunique() > 1 and sub["log2_cost_recorded"].nunique() > 1:
                rho.append(float(sub["log2_cost_estimate"].rank().corr(sub["log2_cost_recorded"].rank())))
            cheapest.append(bool(sub.loc[sub["log2_cost_estimate"].idxmin(), "pipeline_id"] == sub.loc[sub["log2_cost_recorded"].idxmin(), "pipeline_id"]))
        ant_rows.append({"analysis": "COST_AT_DECISION_TIME", "label": LABEL, "protocol": protocol, "task_scope": task, "n_candidate_rows": int(len(g)),
                         "rows_with_estimate": int(g["log2_cost_estimate"].notna().sum()), "rows_with_recorded_cost": int(g["log2_cost_recorded"].notna().sum()),
                         "estimate_source_task_model_pipeline": int((g["estimate_source"] == "TASK_MODEL_PIPELINE").sum()),
                         "estimate_source_task_pipeline": int((g["estimate_source"] == "TASK_PIPELINE").sum()),
                         "mean_error_log2": float(e.mean()), "mean_abs_error_log2": float(e.abs().mean()), "rmse_log2": float(np.sqrt((e ** 2).mean())),
                         "median_abs_error_log2": float(e.abs().median()), "p90_abs_error_log2": float(e.abs().quantile(0.9)),
                         "sd_recorded_log2": float(g["log2_cost_recorded"].std()), "n_groups": int(g["rec_group_id"].nunique()),
                         "mean_rank_correlation_in_group": float(np.mean(rho)) if rho else np.nan, "groups_with_rank_correlation": int(len(rho)),
                         "share_groups_cheapest_candidate_identified": float(np.mean(cheapest)) if cheapest else np.nan})
    ant = pd.DataFrame(ant_rows)
    ant.to_csv(out / "cost_anticipation.csv", index=False)

    summary = {"label": LABEL, "author_decisions": {"Q-50": "(a), registry decision 61", "Q-49": "(a), registry decision 60"},
               "h7_registered_source": "Meta-Dataset-Report v1.9.1, Table 50, row H7; mapping of objectives D-18 (2026-10-24)",
               "cost_estimator": "mean recorded log2 relative cost of the same pipeline for the same task and probe model over the training rows of the fold on the main report slice; fixed before its results were computed",
               "main_configuration_digest": cfg.sha256(), "replay_of_H6_rows_of_record_max_abs_diff": float(h6["replay_of_record_max_abs_diff"].max()),
               "environment": E.environment_record(), "inputs_sha256": inputs,
               "outputs": ["h7_as_registered.csv", "cost_decision_time_h6.csv", "cost_decision_time_agreement.csv", "cost_anticipation.csv"]}
    (out / "post_hoc_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    pd.set_option("display.width", 250)
    print(h7[["variant", "analysis_role", "task_scope", "n_groups", "n_clusters", "d_s_san_mean", "d_s_san_ci_low", "d_s_san_ci_high", "d_macro_f1_mean",
              "d_macro_f1_ci_low", "supported_as_registered", "share_same_recommendation", "implemented_row_supported"]].to_string(index=False))
    print(h6[["analysis_role", "task_scope", "record_d_log2_cost", "record_supported", "replay_of_record_max_abs_diff", "decision_time_d_log2_cost",
              "decision_time_ci_low", "decision_time_ci_high", "decision_time_objective_diff_ci_low", "decision_time_supported_by_the_criterion_of_H6"]].to_string(index=False))
    print(agree[["analysis_role", "task_scope", "lambda", "n_groups", "share_same_recommendation", "groups_moved_from_lambda0_recorded_cost",
                 "groups_moved_from_lambda0_estimated_cost"]].to_string(index=False))
    print(ant[["protocol", "task_scope", "n_candidate_rows", "mean_error_log2", "mean_abs_error_log2", "rmse_log2", "sd_recorded_log2",
               "mean_rank_correlation_in_group", "share_groups_cheapest_candidate_identified"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
