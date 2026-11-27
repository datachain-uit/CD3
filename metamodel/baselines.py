# -*- coding: utf-8 -*-
"""Non-learning strategies B0–B6 (Meta-Dataset-Report Table 46) and the proposed B7 (TEMPO-DQ diagnosis policy).

Every baseline returns the meta-test frame with a ``score`` column, so that recommendation and evaluation use the
same code path as the learners (:func:`metamodel.metrics.recommend`). ``y`` is the realised objective delta.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from . import contracts as C
from . import features as F
from . import metrics as M


def b0_oracle(test: pd.DataFrame, y_col: str = "y") -> pd.DataFrame:
    out = test.copy()
    out["score"] = out[y_col].astype(float)
    out["strategy"] = "B0"
    return out


def b1_always_v0(test: pd.DataFrame) -> pd.DataFrame:
    out = test.copy()
    out["score"] = (out["pipeline_id"] == "V0").astype(float)
    out["strategy"] = "B1"
    return out


def b2_global_best(train: pd.DataFrame, test: pd.DataFrame, y_col: str = "y", by_task: bool = True) -> pd.DataFrame:
    keys = ["task", "pipeline_id"] if by_task and "task" in train.columns else ["pipeline_id"]
    means = train.groupby(keys)[y_col].mean().rename("score").reset_index()
    out = test.merge(means, on=keys, how="left")
    if out["score"].isna().any():   # task unseen in training (transfer): fall back to the pooled pipeline means
        pooled = train.groupby("pipeline_id")[y_col].mean()
        out["score"] = out["score"].fillna(out["pipeline_id"].map(pooled))
    out["strategy"] = "B2"
    return out


def b3_best_per_model_phase(train: pd.DataFrame, test: pd.DataFrame, y_col: str = "y") -> pd.DataFrame:
    keys = ["model_name", "phase_id", "pipeline_id"]
    means = train.groupby(keys)[y_col].mean().rename("score").reset_index()
    out = test.merge(means, on=keys, how="left")
    if out["score"].isna().any():   # unseen (model, phase): fall back to the phase mean, then to B2
        ph = train.groupby(["phase_id", "pipeline_id"])[y_col].mean().rename("s2").reset_index()
        out = out.merge(ph, on=["phase_id", "pipeline_id"], how="left")
        out["score"] = out["score"].fillna(out["s2"])
        out = out.drop(columns=["s2"])
        pooled = train.groupby("pipeline_id")[y_col].mean()
        out["score"] = out["score"].fillna(out["pipeline_id"].map(pooled))
    out["strategy"] = "B3"
    return out


@dataclass
class DQHeuristic:
    """B4: imputer by a threshold on tr_missing_rate, balancer by a threshold on tr_imbalance_ratio (Table 46).

    Thresholds are chosen on meta-training by grid search over quantiles, minimising mean regret.
    """
    missing_col: str = "tr_missing_rate"
    ir_col: str = "tr_imbalance_ratio"
    low_imputer: str = "MEDIAN"
    high_imputer: str = "MICE"
    low_balancer: str = "NONE"
    high_balancer: str = "CDSMOTE"
    quantiles: Sequence[float] = (0.1, 0.25, 0.5, 0.75, 0.9)
    t_missing_: float = np.nan
    t_ir_: float = np.nan
    fitted_: bool = False

    def _pipeline(self, missing: float, ir: float) -> str:
        imp = self.low_imputer if (np.isnan(missing) or missing <= self.t_missing_) else self.high_imputer
        bal = self.low_balancer if (np.isnan(ir) or ir <= self.t_ir_) else self.high_balancer
        return C.PIPELINE_OF[(imp, bal)]

    def fit(self, train: pd.DataFrame, y_col: str = "y", group_col: str = "rec_group_id") -> "DQHeuristic":
        if self.missing_col not in train.columns or self.ir_col not in train.columns:
            raise KeyError(f"B4 needs {self.missing_col} and {self.ir_col} (Z_D / Z_DQ state columns)")
        sit = train.groupby(group_col, sort=False).agg(missing=(self.missing_col, "first"), ir=(self.ir_col, "first"))
        truth = train.pivot_table(index=group_col, columns="pipeline_id", values=y_col, aggfunc="first")
        best = truth.max(axis=1)
        cand_m = np.unique(np.nanquantile(sit["missing"].dropna(), list(self.quantiles))) if sit["missing"].notna().any() else np.array([np.inf])
        cand_i = np.unique(np.nanquantile(sit["ir"].dropna(), list(self.quantiles))) if sit["ir"].notna().any() else np.array([np.inf])
        best_score, best_pair = np.inf, (np.inf, np.inf)
        for tm in cand_m:
            for ti in cand_i:
                self.t_missing_, self.t_ir_ = float(tm), float(ti)
                picks = [self._pipeline(m, i) for m, i in zip(sit["missing"], sit["ir"])]
                chosen = np.array([truth.loc[g, p] if p in truth.columns else np.nan for g, p in zip(sit.index, picks)], dtype=float)
                regret = np.nanmean(best.to_numpy() - chosen)
                if regret < best_score:
                    best_score, best_pair = regret, (float(tm), float(ti))
        self.t_missing_, self.t_ir_ = best_pair
        self.fitted_ = True
        return self

    def score(self, test: pd.DataFrame, group_col: str = "rec_group_id") -> pd.DataFrame:
        if not self.fitted_:
            raise RuntimeError("fit first")
        out = test.copy()
        sit = out.groupby(group_col, sort=False).agg(missing=(self.missing_col, "first"), ir=(self.ir_col, "first"))
        picks = {g: self._pipeline(m, i) for g, m, i in zip(sit.index, sit["missing"], sit["ir"])}
        out["score"] = (out["pipeline_id"] == out[group_col].map(picks)).astype(float)
        out["strategy"] = "B4"
        return out


@dataclass
class KNNMeta:
    """B5: k nearest training situations in the standardised FS3 state space; pipeline with the best mean delta."""
    k: int = 5
    feature_set: str = "FS3"
    pre_: Optional[F.Preprocessor] = None
    train_sit_: Optional[pd.DataFrame] = None
    train_truth_: Optional[pd.DataFrame] = None

    def fit(self, train: pd.DataFrame, y_col: str = "y", group_col: str = "rec_group_id", drop_task: bool = False) -> "KNNMeta":
        state_cols = [c for c in F.select_columns(train.columns, self.feature_set, drop_task=drop_task)
                      if F.S.role_of(c)[1] == "X_STATE" and pd.api.types.is_numeric_dtype(train[c])]   # 0.2.3: *_prev_reason are strings
        if not state_cols:
            raise KeyError("B5 needs X_STATE columns (no state profile in the meta-dataset)")
        sit = train.groupby(group_col, sort=False)[state_cols].first()
        self.pre_ = F.Preprocessor(feature_set=self.feature_set, drop_task=drop_task)
        self.pre_.columns_ = state_cols
        self.pre_.numeric_ = state_cols
        self.pre_.categorical_ = []
        self.pre_.log_cols_ = [c for c in state_cols if F._is_count_column(c, sit[c])]
        X = self.pre_._raw_numeric(sit).fillna(0.0)
        self.pre_.null_indicator_cols_ = []
        self.pre_.dropped_ = {}
        self.pre_.mean_ = {c: float(X[c].mean()) for c in state_cols}
        self.pre_.scale_ = {c: float(X[c].std(ddof=0)) or 1.0 for c in state_cols}
        self.pre_.output_columns_ = [f"num__{c}" for c in state_cols]
        self.train_sit_ = self.pre_.transform(sit)
        self.train_truth_ = train.pivot_table(index=group_col, columns="pipeline_id", values=y_col, aggfunc="first").reindex(sit.index)
        return self

    def score(self, test: pd.DataFrame, group_col: str = "rec_group_id") -> pd.DataFrame:
        assert self.pre_ is not None and self.train_sit_ is not None and self.train_truth_ is not None
        out = test.copy()
        sit = out.groupby(group_col, sort=False)[self.pre_.numeric_].first()
        Z = self.pre_.transform(sit).to_numpy(dtype=float)
        T = self.train_sit_.to_numpy(dtype=float)
        scores: Dict[Tuple[str, str], float] = {}
        k = min(self.k, len(T))
        for g, z in zip(sit.index, Z):
            d = np.sqrt(((T - z) ** 2).sum(axis=1))
            nn = np.argsort(d, kind="stable")[:k]
            means = self.train_truth_.iloc[nn].mean(axis=0)
            for pid, v in means.items():
                scores[(g, pid)] = float(v) if pd.notna(v) else np.nan
        out["score"] = [scores.get((g, p), np.nan) for g, p in zip(out[group_col], out["pipeline_id"])]
        out["strategy"] = "B5"
        return out


def b6_validation_selection(test: pd.DataFrame, objective_stem: str, value_suffix: str = "_delta") -> pd.DataFrame:
    """B6: argmax of the VALIDATION delta of the same objective (full-validation scenario)."""
    col = f"val_{objective_stem}{value_suffix}"
    if col not in test.columns:
        # the seed-aggregated table carries val_*_delta_mean
        alt = f"val_{objective_stem}{value_suffix}_mean"
        if alt not in test.columns:
            raise KeyError(f"B6 needs {col} (X_VAL, full-validation scenario)")
        col = alt
    out = test.copy()
    out["score"] = out[col].astype(float)
    out["strategy"] = "B6"
    return out


@dataclass
class TempoDQPolicy:
    """B7 (in the contribution contract since 2026-10-24, D-S1-3): TEMPO-DQ Table 4 as a deterministic warm-start policy.

    Quadrants of the diagnostic plane (x = S_san+, y = S_perf of the V0 run on VALIDATION; x0 = 0.75, y0 = 0.70):
    Q1 fit for purpose -> keep V0; Q2 (low health, high performance) -> leakage actions, none in the action space -> V0;
    Q3 (low, low) -> imputation and balancing -> ``q3_pipeline``; Q4 (high health, low performance) -> ``q4_pipeline``.
    Defaults map Q3 and Q4 to ``contracts.B7_DEFAULT_REPAIR`` (V2 = MEDIAN + CDSMOTE; median and CDSMOTE were both part
    of the TEMPO-DQ variant grid). B7 belongs to the warm-start scenario and is compared with learners on FS4.
    """
    x0: float = C.TEMPO_DQ_X0
    y0: float = C.TEMPO_DQ_Y0
    q1_pipeline: str = "V0"
    q2_pipeline: str = "V0"
    q3_pipeline: str = C.B7_DEFAULT_REPAIR
    q4_pipeline: str = C.B7_DEFAULT_REPAIR
    san_col: str = "val_s_san_plus_before"
    perf_col: str = "val_s_perf_before"
    status: str = C.B7_STATUS

    def score(self, test: pd.DataFrame, group_col: str = "rec_group_id") -> pd.DataFrame:
        san = self.san_col if self.san_col in test.columns else f"{self.san_col}_mean"
        perf = self.perf_col if self.perf_col in test.columns else f"{self.perf_col}_mean"
        if san not in test.columns or perf not in test.columns:
            raise KeyError(f"B7 needs {self.san_col} and {self.perf_col} (warm-start X_VAL columns)")
        out = test.copy()
        sit = out.groupby(group_col, sort=False).agg(x=(san, "first"), y=(perf, "first"))
        picks = {}
        quadrant = {}
        for g, x, y in zip(sit.index, sit["x"], sit["y"]):
            if np.isnan(x) or np.isnan(y):
                picks[g], quadrant[g] = self.q1_pipeline, "UNKNOWN"
            elif x >= self.x0 and y >= self.y0:
                picks[g], quadrant[g] = self.q1_pipeline, "Q1"
            elif x < self.x0 and y >= self.y0:
                picks[g], quadrant[g] = self.q2_pipeline, "Q2"
            elif x < self.x0 and y < self.y0:
                picks[g], quadrant[g] = self.q3_pipeline, "Q3"
            else:
                picks[g], quadrant[g] = self.q4_pipeline, "Q4"
        out["score"] = (out["pipeline_id"] == out[group_col].map(picks)).astype(float)
        out["tempo_dq_quadrant"] = out[group_col].map(quadrant)
        out["strategy"] = "B7"
        return out


def run_baselines(train: pd.DataFrame, test: pd.DataFrame, *, objective_stem: str, y_col: str = "y",
                  group_col: str = "rec_group_id", include: Sequence[str] = ("B0", "B1", "B2", "B3", "B4", "B5", "B6"),
                  knn_k: int = 5, drop_task: bool = False, include_b7: bool = True) -> Dict[str, pd.DataFrame]:
    """Score the meta-test frame with every requested baseline; failures from missing columns are recorded, not hidden."""
    out: Dict[str, pd.DataFrame] = {}
    for b in include:
        try:
            if b == "B0":
                out[b] = b0_oracle(test, y_col)
            elif b == "B1":
                out[b] = b1_always_v0(test)
            elif b == "B2":
                out[b] = b2_global_best(train, test, y_col, by_task=not drop_task)
            elif b == "B3":
                out[b] = b3_best_per_model_phase(train, test, y_col)
            elif b == "B4":
                out[b] = DQHeuristic().fit(train, y_col, group_col).score(test, group_col)
            elif b == "B5":
                out[b] = KNNMeta(k=knn_k).fit(train, y_col, group_col, drop_task=drop_task).score(test, group_col)
            elif b == "B6":
                out[b] = b6_validation_selection(test, objective_stem)
        except KeyError as exc:
            out[b] = pd.DataFrame({"error": [str(exc)]})
    if include_b7:
        try:
            out["B7"] = TempoDQPolicy().score(test, group_col)
        except KeyError as exc:
            out["B7"] = pd.DataFrame({"error": [str(exc)]})
    return out
