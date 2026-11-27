# -*- coding: utf-8 -*-
"""Feature sets FS0–FS5, information scenarios and train-only preprocessing (Meta-Dataset-Report §10.4).

* FS0 : context only (Z_M, Z_A, task*, phase_index, q, subgroup codes)
* FS1 : FS0 + Z_D (tr_, trpool_ and label-free ev_ columns)
* FS2 : FS1 + Z_DQ                                  ("natural")
* FS3 : FS2 + Z_T                                   ("natural + temporal", primary cold-start set)
* FS4 : FS3 + val_{m}_before, val_s_*_before        (warm start)
* FS5 : FS4 + val_{m}_after, val_{m}_delta, val_s_san_plus_{after,delta}   (full validation)

Preprocessing is fitted on the meta-training rows only (MQ04): log1p on count columns, z-scoring, one-hot encoding
of categorical codes, zero-fill with an indicator for nulls that carry a registered reason, removal of near-constant
columns and of one column of every pair with |rho| > 0.95. ``task`` is dropped in transfer experiments (MQ07).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from . import contracts as C
from . import schema as S

CATEGORICAL_CONTEXT: Tuple[str, ...] = ("task", "model_name", "model_tier", "model_family", "variant_role", "pipeline_id",
                                        "imputer", "balancer", "imputer_family", "balancer_family", "subgroup_axis",
                                        "subgroup_value", "finetune_mode", "pretrained_source", "loss_name", "class_weighting")
NUMERIC_CONTEXT: Tuple[str, ...] = ("phase_index", "q", "is_no_intervention", "has_imputation", "has_balancing", "is_sensitivity",
                                    "is_pretrained", "param_count_total", "param_count_trainable", "log10_param_count",
                                    "uses_mask_channels", "uses_delta_t", "max_seq_len", "patch_len", "patch_stride", "lr",
                                    "batch_size", "max_epochs")
ONEHOT_CONTEXT_PREFIXES: Tuple[str, ...] = ("a_imp_", "a_bal_")


def _strip(c: str) -> str:
    return S._strip_agg(c)


def select_columns(columns: Iterable[str], feature_set: str, *, drop_task: bool = False) -> List[str]:
    """Columns of the frame that belong to ``feature_set`` according to their block and role."""
    if feature_set not in C.FEATURE_SETS:
        raise ValueError(feature_set)
    level = C.FEATURE_SETS.index(feature_set)
    cols: List[str] = []
    for c in columns:
        base = _strip(c)
        block, role = S.role_of(c)
        if role == "X_CONTEXT" or c in CATEGORICAL_CONTEXT or c in NUMERIC_CONTEXT or c.startswith(ONEHOT_CONTEXT_PREFIXES):
            if c in ("task",) and drop_task:
                continue
            if c in S.CONTEXT_KEY_ENCODINGS or role == "X_CONTEXT" or c in NUMERIC_CONTEXT or c.startswith(ONEHOT_CONTEXT_PREFIXES):
                if c not in ("eval_split", "feature_regime"):
                    cols.append(c)
            continue
        if role == "X_STATE":
            if block == "Z_D" and level >= 1:
                cols.append(c)
            elif block == "Z_DQ" and level >= 2:
                cols.append(c)
            elif block == "Z_T" and level >= 3:
                cols.append(c)
            continue
        if role == "X_VAL":
            if level >= 4 and base.endswith("_before"):
                cols.append(c)
            elif level >= 5 and (base.endswith(("_after", "_delta"))):
                cols.append(c)
            continue
    # de-duplicate while keeping order
    seen, out = set(), []
    for c in cols:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def check_inputs(columns: Sequence[str], feature_set: str, *, transfer: bool = False) -> Dict[str, Tuple[bool, List[str]]]:
    """MQ01, MQ06, MQ10 (and MQ07 in transfer) on a selected input column list."""
    scenario = C.SCENARIO_OF_FS[feature_set]
    checks = {"MQ01": S.mq01_input_roles(columns), "MQ06": S.mq06_scenario_columns(columns, scenario),
              "MQ10": S.mq10_no_target_components(columns)}
    if transfer:
        checks["MQ07"] = S.mq07_no_task_feature(columns)
    return checks


def assert_inputs(columns: Sequence[str], feature_set: str, *, transfer: bool = False) -> None:
    failed = {k: v[1] for k, v in check_inputs(columns, feature_set, transfer=transfer).items() if not v[0]}
    if failed:
        raise ValueError(f"meta-level leakage checks failed: {failed}")


def _is_count_column(name: str, s: pd.Series) -> bool:
    base = _strip(name)
    if not pd.api.types.is_numeric_dtype(s):
        return False
    looks = any(t in base for t in ("_n_", "n_cells", "_count", "n_enrollments", "n_learners", "n_courses", "n_offerings",
                                    "n_features", "n_timesteps", "param_count", "n_views", "n_real", "n_synth"))
    vals = s.dropna()
    nonneg_int = len(vals) > 0 and bool((vals >= 0).all()) and bool(np.allclose(vals, np.round(vals)))
    return looks and nonneg_int


@dataclass
class Preprocessor:
    """Train-only preprocessing (MQ04). ``fit`` learns everything from the meta-training frame."""
    feature_set: str
    drop_task: bool = False
    add_interactions: bool = False
    near_constant_tol: float = 1e-12
    collinear_rho: float = 0.95
    columns_: List[str] = field(default_factory=list)
    numeric_: List[str] = field(default_factory=list)
    log_cols_: List[str] = field(default_factory=list)
    categorical_: List[str] = field(default_factory=list)
    categories_: Dict[str, List[str]] = field(default_factory=dict)
    null_indicator_cols_: List[str] = field(default_factory=list)
    mean_: Dict[str, float] = field(default_factory=dict)
    scale_: Dict[str, float] = field(default_factory=dict)
    dropped_: Dict[str, str] = field(default_factory=dict)
    output_columns_: List[str] = field(default_factory=list)
    interaction_pairs_: List[Tuple[str, str]] = field(default_factory=list)

    def fit(self, train: pd.DataFrame) -> "Preprocessor":
        self.columns_ = select_columns(train.columns, self.feature_set, drop_task=self.drop_task)
        assert_inputs(self.columns_, self.feature_set, transfer=self.drop_task)
        self.numeric_, self.categorical_ = [], []
        for c in self.columns_:
            if c in CATEGORICAL_CONTEXT or train[c].dtype == object or isinstance(train[c].dtype, pd.CategoricalDtype) or pd.api.types.is_string_dtype(train[c]):
                self.categorical_.append(c)
            else:
                self.numeric_.append(c)
        self.categories_ = {c: sorted(train[c].dropna().astype(str).unique().tolist()) for c in self.categorical_}
        self.log_cols_ = [c for c in self.numeric_ if _is_count_column(c, train[c])]
        X = self._raw_numeric(train)
        self.null_indicator_cols_ = [c for c in self.numeric_ if train[c].isna().any()]
        # near-constant and collinear pruning on the training fold only
        self.dropped_ = {}
        kept = []
        for c in self.numeric_:
            v = X[c].fillna(0.0)
            if float(v.var()) <= self.near_constant_tol:
                self.dropped_[c] = "NEAR_CONSTANT"
            else:
                kept.append(c)
        if len(kept) > 1:
            corr = X[kept].fillna(0.0).corr().abs().to_numpy()
            drop = set()
            for i in range(len(kept)):
                if kept[i] in drop:
                    continue
                for j in range(i + 1, len(kept)):
                    if kept[j] in drop:
                        continue
                    if corr[i, j] > self.collinear_rho:
                        drop.add(kept[j])
                        self.dropped_[kept[j]] = f"COLLINEAR_WITH:{kept[i]}"
            kept = [c for c in kept if c not in drop]
        self.numeric_ = kept
        self.null_indicator_cols_ = [c for c in self.null_indicator_cols_ if c in kept]
        self.mean_ = {c: float(X[c].fillna(0.0).mean()) for c in kept}
        self.scale_ = {c: float(X[c].fillna(0.0).std(ddof=0)) or 1.0 for c in kept}
        self.interaction_pairs_ = []
        if self.add_interactions:
            codes = [c for c in self.columns_ if c.startswith(ONEHOT_CONTEXT_PREFIXES) and c in kept]
            states = [c for c in kept if S.role_of(c)[1] == "X_STATE"]
            self.interaction_pairs_ = [(a, s) for a in codes for s in states]
        self.output_columns_ = self._output_names()
        return self

    def _raw_numeric(self, df: pd.DataFrame) -> pd.DataFrame:
        X = df[self.numeric_].astype(float).copy() if self.numeric_ else pd.DataFrame(index=df.index)
        for c in self.log_cols_:
            if c in X:
                X[c] = np.log1p(X[c].clip(lower=0))
        return X

    def _output_names(self) -> List[str]:
        names = [f"num__{c}" for c in self.numeric_]
        names += [f"isnull__{c}" for c in self.null_indicator_cols_]
        for c in self.categorical_:
            names += [f"cat__{c}__{v}" for v in self.categories_[c]]
        names += [f"inter__{a}__{s}" for a, s in self.interaction_pairs_]
        return names

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        X = self._raw_numeric(df)
        blocks = []
        num = pd.DataFrame(index=df.index)
        for c in self.numeric_:
            v = X[c].fillna(0.0)
            num[f"num__{c}"] = (v - self.mean_[c]) / self.scale_[c]
        blocks.append(num)
        if self.null_indicator_cols_:
            blocks.append(pd.DataFrame({f"isnull__{c}": df[c].isna().astype(float) for c in self.null_indicator_cols_}, index=df.index))
        for c in self.categorical_:
            vals = df[c].astype(str)
            blocks.append(pd.DataFrame({f"cat__{c}__{v}": (vals == v).astype(float) for v in self.categories_[c]}, index=df.index))
        if self.interaction_pairs_:
            inter = {f"inter__{a}__{s}": num[f"num__{a}"] * num[f"num__{s}"] for a, s in self.interaction_pairs_}
            blocks.append(pd.DataFrame(inter, index=df.index))
        out = pd.concat(blocks, axis=1) if blocks else pd.DataFrame(index=df.index)
        return out.reindex(columns=self.output_columns_, fill_value=0.0)

    def fit_transform(self, train: pd.DataFrame) -> pd.DataFrame:
        return self.fit(train).transform(train)


def situation_frame(df: pd.DataFrame, group_col: str = "rec_group_id") -> pd.DataFrame:
    """One row per situation (rec_group) with its state columns, used by the kNN baseline B5."""
    state_cols = [c for c in df.columns if S.role_of(c)[1] == "X_STATE"]
    return df.groupby(group_col, sort=False)[state_cols].first()
