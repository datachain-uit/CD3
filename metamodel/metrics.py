# -*- coding: utf-8 -*-
"""Recommendation metrics and inference (Meta-Dataset-Report §10.7–§10.8; Table 49).

All metrics operate on a *scored frame*: one row per (rec_group, pipeline) with the realised objective delta
``y`` (the truth), a ``score`` used to rank candidates, and the cluster fields for the bootstrap.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy import stats

from . import contracts as C


# ---------------------------------------------------------------------------------------------
# recommendation from scores
# ---------------------------------------------------------------------------------------------


def recommend(scored: pd.DataFrame, *, group_col: str = "rec_group_id", score_col: str = "score",
              conservative: bool = False, eps: float = C.REC_EPS, v0: str = "V0") -> pd.DataFrame:
    """One row per group: the recommended pipeline (argmax score; conservative keeps V0 unless max score > eps)."""
    rows = []
    for g, sub in scored.groupby(group_col, sort=False):
        s = sub[score_col].astype(float)
        if s.notna().sum() == 0:
            pick = sub[sub["pipeline_id"] == v0]
            pick = pick.index[0] if len(pick) else sub.index[0]
        else:
            pick = s.idxmax()
            if conservative and float(s.loc[pick]) <= eps:
                v = sub[sub["pipeline_id"] == v0]
                pick = v.index[0] if len(v) else pick
        rows.append({group_col: g, "pipeline_recommended": sub.loc[pick, "pipeline_id"], "score_recommended": float(s.loc[pick]) if pd.notna(s.loc[pick]) else np.nan})
    return pd.DataFrame(rows)


def group_outcomes(scored: pd.DataFrame, rec: pd.DataFrame, *, group_col: str = "rec_group_id", y_col: str = "y",
                   eps: float = C.REC_EPS, extra_cols: Sequence[str] = (), cost_col: Optional[str] = None,
                   lambda_grid: Sequence[float] = C.LAMBDA_GRID, perf_col: Optional[str] = None,
                   pareto_col: Optional[str] = None) -> pd.DataFrame:
    """Per-group regret, hit, harm, gain, NDCG@3, within-group Spearman and utility regret for a recommendation frame."""
    out = []
    recd = rec.set_index(group_col)["pipeline_recommended"]
    for g, sub in scored.groupby(group_col, sort=False):
        y = sub[y_col].astype(float)
        if y.notna().sum() == 0:
            continue
        best = float(y.max())
        pick = recd.get(g)
        row_pick = sub[sub["pipeline_id"] == pick]
        y_pick = float(row_pick[y_col].iloc[0]) if len(row_pick) and pd.notna(row_pick[y_col].iloc[0]) else np.nan
        rec_row: Dict[str, object] = {group_col: g, "pipeline_recommended": pick, "y_recommended": y_pick, "y_best": best,
                                      "regret": best - y_pick, "hit": float(y_pick >= best - eps), "harm": float(y_pick < -eps),
                                      "gain_over_v0": y_pick, "n_candidates": int(y.notna().sum())}
        # graded relevance (3 within eps of best, 2 beneficial, 1 neutral, 0 harmful) and NDCG@3 of the score ranking
        grade = np.where(y >= best - eps, 3, np.where(y > eps, 2, np.where(y < -eps, 0, 1))).astype(float)
        if "score" in sub.columns and sub["score"].notna().any():
            order = np.argsort(-sub["score"].fillna(-np.inf).to_numpy(), kind="stable")
            rec_row["ndcg_at_3"] = _ndcg(grade[order], grade, k=3)
            rho = _spearman(sub["score"].to_numpy(dtype=float), y.to_numpy())
            rec_row["spearman_in_group"] = rho
        else:
            rec_row["ndcg_at_3"] = np.nan
            rec_row["spearman_in_group"] = np.nan
        for c in extra_cols:
            if c in sub.columns and len(row_pick):
                rec_row[f"{c}_recommended"] = float(row_pick[c].iloc[0]) if pd.notna(row_pick[c].iloc[0]) else np.nan
        if cost_col is not None and cost_col in sub.columns:
            lr = np.log2(sub[cost_col].astype(float).where(sub[cost_col] > 0))
            for j, lam in enumerate(lambda_grid):
                u = y - lam * lr
                if u.notna().any() and len(row_pick):
                    u_pick = float(u.loc[row_pick.index[0]]) if pd.notna(u.loc[row_pick.index[0]]) else np.nan
                    rec_row[f"utility_regret_l{j}"] = float(u.max()) - u_pick
            if len(row_pick):
                rec_row["log2_cost_ratio_recommended"] = float(lr.loc[row_pick.index[0]]) if pd.notna(lr.loc[row_pick.index[0]]) else np.nan
        if pareto_col is not None and pareto_col in sub.columns and len(row_pick):
            rec_row["on_pareto"] = float(bool(row_pick[pareto_col].iloc[0]))
        for c in C.CLUSTER_FIELDS:
            if c in sub.columns:
                rec_row[c] = sub[c].iloc[0]
        out.append(rec_row)
    return pd.DataFrame(out)


def utility_outcomes(scored: pd.DataFrame, lam: float, *, cost_col: str, group_col: str = "rec_group_id", y_col: str = "y",
                     score_col: str = "score") -> pd.DataFrame:
    """Per group: the pipeline recommended by argmax(score - lam * log2 cost_ratio), its realised objective and log2 cost."""
    rows = []
    for g, sub in scored.groupby(group_col, sort=False):
        lr = np.log2(sub[cost_col].astype(float).where(sub[cost_col] > 0))
        u = sub[score_col].astype(float) - lam * lr
        if u.notna().sum() == 0:
            continue
        pick = u.idxmax()
        row = {group_col: g, "lambda": lam, "pipeline_recommended": sub.loc[pick, "pipeline_id"],
               "y_recommended": float(sub.loc[pick, y_col]) if pd.notna(sub.loc[pick, y_col]) else np.nan,
               "log2_cost_ratio_recommended": float(lr.loc[pick]) if pd.notna(lr.loc[pick]) else np.nan}
        for c in C.CLUSTER_FIELDS:
            if c in sub.columns:
                row[c] = sub[c].iloc[0]
        rows.append(row)
    return pd.DataFrame(rows)


def _dcg(grades: np.ndarray, k: int) -> float:
    g = grades[:k]
    return float(np.sum((2.0 ** g - 1.0) / np.log2(np.arange(2, len(g) + 2))))


def _ndcg(ranked_grades: np.ndarray, all_grades: np.ndarray, k: int = 3) -> float:
    ideal = _dcg(np.sort(all_grades)[::-1], k)
    return float(_dcg(ranked_grades, k) / ideal) if ideal > 0 else np.nan


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    m = ~(np.isnan(a) | np.isnan(b))
    if m.sum() < 3 or np.std(a[m]) == 0 or np.std(b[m]) == 0:
        return np.nan
    return float(stats.spearmanr(a[m], b[m]).statistic)


def summarise(groups: pd.DataFrame) -> Dict[str, float]:
    """Mean/median/p90 regret, harm rate, top-1 hit, mean gain, NDCG@3, Spearman and utility regrets."""
    s: Dict[str, float] = {
        "n_groups": int(len(groups)),
        "mean_regret": float(groups["regret"].mean()),
        "median_regret": float(groups["regret"].median()),
        "p90_regret": float(groups["regret"].quantile(0.90)),
        "harm_rate": float(groups["harm"].mean()),
        "top1_hit_rate": float(groups["hit"].mean()),
        "mean_gain_over_v0": float(groups["gain_over_v0"].mean()),
    }
    for c in ("ndcg_at_3", "spearman_in_group", "on_pareto"):
        if c in groups.columns:
            s[f"mean_{c}"] = float(groups[c].mean(skipna=True))
    for c in groups.columns:
        if c.startswith("utility_regret_l") or c.endswith("_recommended") and c not in ("pipeline_recommended", "y_recommended"):
            s[f"mean_{c}"] = float(groups[c].mean(skipna=True))
    return s


def gap_closure(mean_regret_model: float, mean_regret_comparator: float) -> float:
    return float((mean_regret_comparator - mean_regret_model) / mean_regret_comparator) if mean_regret_comparator > 0 else np.nan


def prediction_errors(scored: pd.DataFrame, y_col: str = "y", pred_col: str = "score") -> Dict[str, float]:
    m = scored[[y_col, pred_col]].dropna()
    err = m[pred_col] - m[y_col]
    return {"mae": float(err.abs().mean()), "rmse": float(np.sqrt((err ** 2).mean())), "n_pairs": int(len(m))}


# ---------------------------------------------------------------------------------------------
# objective agreement (RQ7)
# ---------------------------------------------------------------------------------------------


def objective_agreement(frame: pd.DataFrame, obj_a: str, obj_b: str, *, group_col: str = "rec_group_id") -> Dict[str, float]:
    """Kendall tau within groups between two objective deltas and the top-1 agreement rate."""
    taus, same = [], []
    for _, sub in frame.groupby(group_col, sort=False):
        a, b = sub[obj_a].astype(float), sub[obj_b].astype(float)
        m = a.notna() & b.notna()
        if m.sum() >= 3:
            taus.append(float(stats.kendalltau(a[m], b[m]).statistic))
            same.append(float(a[m].idxmax() == b[m].idxmax()))
    return {"mean_kendall_tau": float(np.nanmean(taus)) if taus else np.nan,
            "top1_agreement": float(np.mean(same)) if same else np.nan, "n_groups": len(taus)}


# ---------------------------------------------------------------------------------------------
# inference: cluster bootstrap and Holm correction (§10.8)
# ---------------------------------------------------------------------------------------------


def clusters_by_first_appearance(frame: pd.DataFrame, fields: Sequence[str]) -> List[np.ndarray]:
    """Row positions of every cluster of ``frame``, the clusters enumerated in the order of their first row (0.3.1).

    The bootstrap draws cluster numbers, so the enumeration of the clusters is part of the result. Up to 0.3.0 the enumeration was
    taken from ``DataFrame.groupby(fields, sort=False).indices``, a dict whose key order is an implementation detail of pandas: it is
    the order of first appearance under pandas 3.1.0 (the environment of the runs of record, phase C of 2026-11-24) and another
    order under pandas 3.0.5, which moved interval limits and p values of the same data (estimates were never affected). Here the
    order of first appearance is built without pandas grouping, so every version reproduces the tables of record. As in the pandas
    grouping, a row with a missing value in a cluster field belongs to no cluster.
    """
    fields = list(fields)
    if not fields:
        return [np.arange(len(frame))]
    cols = [frame[c].to_numpy() for c in fields]
    order: Dict[Tuple[Any, ...], List[int]] = {}
    for i, key in enumerate(zip(*cols)):
        if any(pd.isna(k) for k in key):
            continue
        order.setdefault(key, []).append(i)
    return [np.asarray(v, dtype=np.int64) for v in order.values()]


def cluster_bootstrap_mean(groups: pd.DataFrame, value_col: str, *, cluster_fields: Sequence[str] = C.CLUSTER_FIELDS,
                           b: int = C.BOOTSTRAP_B, seed: int = 42, alpha: float = C.ALPHA_STAT) -> Dict[str, float]:
    """Percentile CI of the mean of ``value_col`` by resampling clusters (task, window, model, phase) with replacement."""
    fields = [c for c in cluster_fields if c in groups.columns]
    g = groups.dropna(subset=[value_col])
    clusters = clusters_by_first_appearance(g, fields)          # 0.3.1: explicit order (see clusters_by_first_appearance)
    vals = g[value_col].to_numpy(dtype=float)
    rng = np.random.default_rng(seed)
    n = len(clusters)
    draws = np.empty(b)
    for t in range(b):
        pick = rng.integers(0, n, size=n)
        draws[t] = np.mean(np.concatenate([vals[clusters[k]] for k in pick]))
    lo, hi = np.quantile(draws, [alpha / 2, 1 - alpha / 2])
    return {"estimate": float(vals.mean()), "ci_low": float(lo), "ci_high": float(hi), "n_clusters": int(n), "b": int(b)}


def paired_cluster_bootstrap(groups_a: pd.DataFrame, groups_b: pd.DataFrame, value_col: str, *, group_col: str = "rec_group_id",
                             cluster_fields: Sequence[str] = C.CLUSTER_FIELDS, b: int = C.BOOTSTRAP_B, seed: int = 42,
                             alpha: float = C.ALPHA_STAT) -> Dict[str, float]:
    """CI of mean(a − b) over the same groups, resampling clusters; p is the two-sided bootstrap sign probability."""
    merged = groups_a[[group_col, value_col] + [c for c in cluster_fields if c in groups_a.columns]].merge(
        groups_b[[group_col, value_col]], on=group_col, suffixes=("_a", "_b"))
    merged["diff"] = merged[f"{value_col}_a"] - merged[f"{value_col}_b"]
    res = cluster_bootstrap_mean(merged, "diff", cluster_fields=cluster_fields, b=b, seed=seed, alpha=alpha)
    fields = [c for c in cluster_fields if c in merged.columns]
    clusters = clusters_by_first_appearance(merged, fields)     # 0.3.1: explicit order (see clusters_by_first_appearance)
    vals = merged["diff"].to_numpy(dtype=float)
    rng = np.random.default_rng(seed)
    draws = np.array([np.mean(np.concatenate([vals[clusters[k]] for k in rng.integers(0, len(clusters), size=len(clusters))])) for _ in range(b)])
    p = 2 * min(float((draws <= 0).mean()), float((draws >= 0).mean()))
    res.update({"p_boot": min(1.0, p), "n_groups": int(len(merged))})
    return res


def cluster_spearman(groups: pd.DataFrame, x_col: str, y_col: str, *, cluster_fields: Sequence[str] = C.CLUSTER_FIELDS,
                     b: int = C.BOOTSTRAP_B, seed: int = 42, alpha: float = C.ALPHA_STAT) -> Dict[str, float]:
    """Spearman correlation between the cluster means of ``x_col`` and ``y_col`` (H8), with a cluster-bootstrap CI.

    Each cluster (task, window, model, phase) contributes one point, so the dependence between situations of one run
    does not inflate the sample. The two-sided bootstrap p is the sign probability of the resampled correlation.
    """
    fields = [c for c in cluster_fields if c in groups.columns]
    g = groups.dropna(subset=[x_col, y_col])
    if not fields or len(g) == 0:
        return {"estimate": np.nan, "ci_low": np.nan, "ci_high": np.nan, "n_clusters": 0, "b": int(b), "p_boot": np.nan}
    agg = g.groupby(fields, sort=False)[[x_col, y_col]].mean().reset_index(drop=True)
    x, y = agg[x_col].to_numpy(dtype=float), agg[y_col].to_numpy(dtype=float)
    n = len(agg)
    if n < 4 or np.nanstd(x) == 0 or np.nanstd(y) == 0:
        return {"estimate": np.nan, "ci_low": np.nan, "ci_high": np.nan, "n_clusters": int(n), "b": int(b), "p_boot": np.nan}
    est = _spearman(x, y)
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(b):
        pick = rng.integers(0, n, size=n)
        xb, yb = x[pick], y[pick]
        if np.std(xb) == 0 or np.std(yb) == 0:
            continue
        draws.append(_spearman(xb, yb))
    draws = np.asarray(draws, dtype=float)
    if len(draws) == 0:
        return {"estimate": float(est), "ci_low": np.nan, "ci_high": np.nan, "n_clusters": int(n), "b": int(b), "p_boot": np.nan}
    lo, hi = np.quantile(draws, [alpha / 2, 1 - alpha / 2])
    pval = 2 * min(float((draws <= 0).mean()), float((draws >= 0).mean()))
    return {"estimate": float(est), "ci_low": float(lo), "ci_high": float(hi), "n_clusters": int(n), "b": int(len(draws)), "p_boot": min(1.0, pval)}


def holm(pvalues: Dict[str, float], alpha: float = C.ALPHA_STAT) -> Dict[str, Dict[str, float]]:
    """Holm step-down correction; returns adjusted p and a reject flag per hypothesis."""
    items = sorted(((k, v) for k, v in pvalues.items() if v is not None and not np.isnan(v)), key=lambda kv: kv[1])
    m = len(items)
    out, running = {}, 0.0
    for i, (k, p) in enumerate(items):
        adj = min(1.0, max(running, (m - i) * p))
        running = adj
        out[k] = {"p": p, "p_holm": adj, "reject": bool(adj <= alpha)}
    return out
