# -*- coding: utf-8 -*-
"""Frozen configuration, run registry and the main grid of the meta-model experiment (Meta-Dataset-Report §10.5–§10.13).

Artefacts written to ``out_dir`` (Table 51): mm_config.yaml (+ sha256), mm_split_manifest, mm_run_registry,
mm_predictions, mm_recommendations, mm_metrics, mm_hypotheses, mm_feature_importance, mm_negative_control.
"""
from __future__ import annotations

import json
import platform
import re
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from . import assemble as A
from . import baselines as B
from . import contracts as C
from . import features as F
from . import learners as L
from . import metrics as M
from . import protocols as P
from . import schema as S

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


@dataclass
class MMConfig:
    """The pre-registered plan. Freeze (sha256) before any result of the primary test window is inspected."""
    meta_release_id: str = "UNRELEASED"
    config_version: str = "mm_config_v0.2"
    objective: str = C.DEFAULT_OBJECTIVE               # key of contracts.OBJECTIVES
    table: str = "seed_agg"                            # seed_agg (primary) or seed_level (robustness)
    protocols: Tuple[str, ...] = ("E1-A", "E1-B")
    feature_sets: Tuple[str, ...] = C.FEATURE_SETS
    learners: Tuple[str, ...] = ("L1", "L2", "L3", "L4")
    extra_learners: Tuple[str, ...] = ("L5", "L6")     # F-CLS and F-DEC on the primary feature set only
    baselines: Tuple[str, ...] = ("B0", "B1", "B2", "B3", "B4", "B5", "B6")
    include_b7: bool = True                            # B7 in the contract since 2026-10-24 (D-S1-3)
    learner_seeds: Tuple[int, ...] = C.LEARNER_SEEDS
    n_trials: int = 50
    eps: float = C.REC_EPS
    lambda_grid: Tuple[float, ...] = C.LAMBDA_GRID
    alpha_beta_grid: Tuple[Tuple[float, float], ...] = C.ALPHA_BETA_GRID
    conservative: bool = False
    eval_split: str = "TEST"
    subgroup: Tuple[str, str] = ("ALL", "ALL")
    row_status: str = "COMPLETE"
    primary_regime_only: bool = True
    label_threshold_set: Optional[str] = None
    cluster_fields: Tuple[str, ...] = C.CLUSTER_FIELDS
    bootstrap_b: int = C.BOOTSTRAP_B
    alpha_stat: float = C.ALPHA_STAT
    energy_measured_types: Tuple[str, ...] = C.ENERGY_MEASURED_TYPES_STRICT
    knn_k_grid: Tuple[int, ...] = (3, 5, 10)
    negative_control: bool = True
    hypotheses: Tuple[str, ...] = C.HYPOTHESES          # H1-H7 (Table 50) + H8 (mechanism decomposition, 2026-10-24)
    h8_state_feature: str = C.H8_STATE_FEATURE          # Z_DQ feature the imputation share is correlated with (descriptive since 0.2.4)
    h8_min_clusters: int = C.H8_MIN_CLUSTERS            # clusters needed for a verdict on H8 (author decision 2026-11-13)
    b7_default_repair: str = C.B7_DEFAULT_REPAIR
    notes: str = ""
    # 0.3.0, full-design run (decisions 52-54 of 2026-11-21). The defaults are the analysis of 0.2.x: one slice, one model for every
    # task of the table, hypothesis rows of the primary fold only; with them the configuration digest is the digest of 0.2.x.
    training_subgroups: Optional[Tuple[Tuple[str, str], ...]] = None   # None: the report slice only; Table 42 primary set: C.MANDATORY_SUBGROUPS
    e1_scope: str = C.E1_SCOPE_POOLED                                  # PER_TASK: one model per task and fold for E1-A, E1-B, E3 (§10.10)
    baseline_scope: str = C.BASELINE_SCOPE_MATCHED                     # baselines and inner selection on the slice they score, or on all rows
    hypothesis_rows: str = C.HYP_ROWS_PRIMARY_ONLY                     # REGISTERED: primary, per task, E1-A replication, 96-cluster pooled rows
    small_subgroup_policy: str = C.SMALL_SUBGROUP_KEEP                 # DROP_FROM_TRAINING: flagged secondary rows never enter a fit (sensitivity)

    V03_FIELDS = ("training_subgroups", "e1_scope", "baseline_scope", "hypothesis_rows", "small_subgroup_policy")

    def slices(self) -> Tuple[Tuple[str, str], ...]:
        """Subgroup slices that enter the run: the main report slice first, then the other training subgroups."""
        out = [tuple(self.subgroup)]
        for s in (self.training_subgroups or ()):
            if tuple(s) not in out:
                out.append(tuple(s))
        return tuple(out)

    def is_legacy_design(self) -> bool:
        return (len(self.slices()) == 1 and self.e1_scope == C.E1_SCOPE_POOLED and self.baseline_scope == C.BASELINE_SCOPE_MATCHED
                and self.hypothesis_rows == C.HYP_ROWS_PRIMARY_ONLY and self.small_subgroup_policy == C.SMALL_SUBGROUP_KEEP)

    def validate(self) -> None:
        for value, allowed, name in ((self.e1_scope, C.E1_SCOPES, "e1_scope"), (self.baseline_scope, C.BASELINE_SCOPES, "baseline_scope"),
                                     (self.hypothesis_rows, C.HYP_ROW_SETS, "hypothesis_rows"),
                                     (self.small_subgroup_policy, C.SMALL_SUBGROUP_POLICIES, "small_subgroup_policy")):
            if value not in allowed:
                raise ValueError(f"{name} = {value!r}; allowed: {allowed}")
        if self.e1_scope == C.E1_SCOPE_PER_TASK and self.hypothesis_rows != C.HYP_ROWS_REGISTERED:
            raise ValueError("per-task E1 needs hypothesis_rows = REGISTERED: the verdict rows are the joint rows of the two tasks (decision 52 (a))")

    def to_dict(self) -> Dict[str, Any]:
        d = json.loads(json.dumps(asdict(self), default=list))
        if self.is_legacy_design():
            for k in self.V03_FIELDS:      # the 0.2.x plan keeps its 0.2.x digest
                d.pop(k, None)
        else:
            d["config_version"] = "mm_config_v0.3"
            d["training_subgroups"] = [list(s) for s in self.slices()]
        return d

    def sha256(self) -> str:
        return C.sha256_of(self.to_dict())

    def freeze(self, out_dir: Path) -> str:
        out_dir.mkdir(parents=True, exist_ok=True)
        d = self.to_dict()
        digest = self.sha256()
        if yaml is not None:
            (out_dir / "mm_config.yaml").write_text(yaml.safe_dump(d, sort_keys=True, allow_unicode=True), encoding="utf-8")
        (out_dir / "mm_config.json").write_text(C.canonical_json(d), encoding="utf-8")
        (out_dir / "mm_config_sha256.txt").write_text(digest + "\n", encoding="utf-8")
        return digest


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return "UNKNOWN"


def _package_version() -> str:
    """Version string of the package (0.2.5): the run machines hold no git checkout, so code_commit is UNKNOWN there."""
    import sys
    return str(getattr(sys.modules.get(__name__.rsplit(".", 1)[0]), "__version__", "UNKNOWN"))


def cost_basis_table(df: pd.DataFrame, names: Dict[str, str], digest: str) -> pd.DataFrame:
    """Number of recommendation groups per (task, cost basis) of the run (0.2.5): written as mm_cost_basis so that the basis used by a
    configuration is a recorded count, not an inference from identical outputs."""
    if names.get("cost_basis") not in df.columns:
        return pd.DataFrame()
    g = df.drop_duplicates("rec_group_id")
    by = [c for c in ("task", "model_name") if c in g.columns] + [names["cost_basis"]]
    out = g.groupby(by, dropna=False).size().rename("n_groups").reset_index().rename(columns={names["cost_basis"]: "cost_basis"})
    out["cost_basis_rule"] = names.get("cost_basis_rule")
    out["config_sha256"] = digest
    return out


SLICE_COL, MAIN_COL, TRAIN_OK_COL = "mm_report_slice", "mm_is_main_slice", "mm_train_ok"   # run-time helpers, never inputs (role UNASSIGNED)
PROGRESS = False       # cli `run --progress`: one line per learner cell on stdout


def _progress(msg: str) -> None:
    if PROGRESS:
        print(f"[mm {time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _env_id() -> str:
    return C.sha256_of({"python": platform.python_version(), "platform": platform.platform(), "lgb": L.HAS_LGB, "optuna": L.HAS_OPTUNA})[:16]


def environment_record() -> Dict[str, Any]:
    """Versions and thread settings of the running environment (0.3.1). Written next to every control-only and verification result,
    so that the environment that reproduced a delivered table is a recorded fact. No host name, user name or path is recorded."""
    import importlib
    import os
    libs: Dict[str, Optional[str]] = {}
    for name in ("pandas", "numpy", "sklearn", "scipy", "lightgbm", "optuna", "pyarrow", "yaml"):
        try:
            libs[name] = str(getattr(importlib.import_module(name), "__version__", "UNKNOWN"))
        except Exception:
            libs[name] = None
    try:                 # L2 (ExtraTrees) and L3-L6 (LightGBM) are built with n_jobs=-1, which both libraries resolve through joblib:
        import joblib    # the count below honours LOKY_MAX_CPU_COUNT, CPU affinity and container limits, not OMP_NUM_THREADS
        learner_threads: Optional[int] = int(joblib.cpu_count())
    except Exception:
        learner_threads = None
    return {"python": platform.python_version(), "python_implementation": platform.python_implementation(), "platform": platform.platform(),
            "machine": platform.machine(), "cpu_count": os.cpu_count(), "learner_threads_n_jobs_minus_one": learner_threads, "libraries": libs,
            "thread_env": {k: os.environ.get(k) for k in ("LOKY_MAX_CPU_COUNT", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                                                          "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")},
            "metamodel_version": _package_version(), "env_id": _env_id()}


# ---------------------------------------------------------------------------------------------
# frame preparation
# ---------------------------------------------------------------------------------------------


def prepare_frame(meta: pd.DataFrame, cfg: MMConfig) -> Tuple[pd.DataFrame, Dict[str, str]]:
    """Filter the meta-dataset per the plan (§10.3) and name the target / group / part columns."""
    suffix = "_mean" if cfg.table == "seed_agg" else ""
    stem = C.OBJECTIVES[cfg.objective]
    group_col = "rec_group_id_agg" if cfg.table == "seed_agg" else "rec_group_id"
    status_col = "row_status_agg" if cfg.table == "seed_agg" else "row_status"
    df = meta.copy()
    df = df[df["eval_split"] == cfg.eval_split]
    slices = cfg.slices()
    if len(slices) == 1:
        df = df[(df["subgroup_axis"] == cfg.subgroup[0]) & (df["subgroup_value"] == cfg.subgroup[1])]
    else:       # 0.3.0: Table 42 primary set, the subgroups are training rows and subgroup_axis / subgroup_value are context features (FS0)
        slice_key = df["subgroup_axis"].astype(str) + "/" + df["subgroup_value"].astype(str)
        df = df[slice_key.isin([f"{a}/{v}" for a, v in slices])]
    if status_col in df.columns:
        df = df[df[status_col] == cfg.row_status]
    if cfg.primary_regime_only and "is_primary_regime" in df.columns:
        df = df[df["is_primary_regime"].astype(int) == 1]
    if cfg.label_threshold_set is not None:
        df = df[df["label_threshold_set"] == cfg.label_threshold_set]
    y_col = f"{stem}_delta{suffix}"
    if y_col not in df.columns:
        raise KeyError(f"target column {y_col} not in the meta-dataset")
    names = {"y": y_col, "group": group_col, "suffix": suffix, "stem": stem,
             "part_perf": f"{stem}_log_delta_perf_part{suffix}", "part_san": f"{stem}_log_delta_san_part{suffix}",
             "cost_ratio": f"cost_ratio_used{'_agg' if cfg.table == 'seed_agg' else ''}",
             "pareto": f"is_pareto_f1_cost{'_agg' if cfg.table == 'seed_agg' else ''}",
             "macro_f1_delta": f"macro_f1_delta{suffix}", "s_san_delta": f"s_san_plus_delta{suffix}",
             "s_san_v2_delta": f"s_san_plus_v2_delta{suffix}", "s_perf_delta": f"s_perf_delta{suffix}",
             "delta_imp": f"{stem}_delta_imp{suffix}", "delta_bal": f"{stem}_delta_bal{suffix}"}
    df = df.reset_index(drop=True)
    df["y"] = df[y_col].astype(float)
    df["rec_group_id"] = df[group_col]            # uniform name for the downstream code
    if "meta_obs_id" not in df.columns:            # seed_agg carries meta_obs_id_agg
        df["meta_obs_id"] = df["meta_obs_id_agg"]
    if "model_tier" not in df.columns:
        df["model_tier"] = df["model_name"].map(C.MODEL_TIER)
    # 0.2.5: the cost basis follows the configuration of THIS run (cfg.energy_measured_types), not the labels stored in the release.
    # Until 0.2.4 the stored cost_ratio_used[_agg] was read, so `run --accept-energy-estimates` changed the configuration digest only.
    cb, rule = A.cost_basis_frame(df, value_suffix="_delta" + suffix, group_col="rec_group_id", energy_measured_types=cfg.energy_measured_types)
    if rule == "LEGACY_FIRST_SEED_TYPE" and tuple(sorted(cfg.energy_measured_types)) != tuple(sorted(C.ENERGY_MEASURED_TYPES_STRICT)):
        raise ValueError("this seed-aggregated table was assembled with metamodel < 0.2.5 and does not say how many seeds carry an energy value "
                         f"(columns {A.ENERGY_N_SEEDS_COL}, {A.ENERGY_TYPES_COL}); an energy cost basis that accepts estimates cannot be verified. "
                         "Assemble the release again with metamodel >= 0.2.5, or run with the strict measurement types.")
    df["cost_basis_run"] = cb["cost_basis"].to_numpy()
    df["cost_ratio_run"] = cb["cost_ratio_used"].to_numpy()
    df["is_pareto_f1_cost_run"] = A.pareto_flags(df, df["cost_basis_run"], value_suffix="_delta" + suffix, group_col="rec_group_id")
    names.update({"cost_ratio": "cost_ratio_run", "pareto": "is_pareto_f1_cost_run", "cost_basis": "cost_basis_run", "cost_basis_rule": rule})
    # 0.3.0: slice bookkeeping of the run
    df[SLICE_COL] = (df["subgroup_axis"].astype(str) + "/" + df["subgroup_value"].astype(str)).to_numpy()
    df[MAIN_COL] = ((df["subgroup_axis"] == cfg.subgroup[0]) & (df["subgroup_value"] == cfg.subgroup[1])).to_numpy()
    if len(slices) > 1:
        present = set(df[SLICE_COL].unique())
        missing = [f"{a}/{v}" for a, v in slices if f"{a}/{v}" not in present]
        if missing:
            raise KeyError(f"subgroups {missing} belong to the design but have no {cfg.row_status} {cfg.eval_split} row in the table; "
                           "the full-design run needs a five-subgroup release (assemble --require-subgroups)")
    df[TRAIN_OK_COL] = True
    if cfg.small_subgroup_policy == C.SMALL_SUBGROUP_DROP:
        if C.SMALL_SUBGROUP_FLAG not in df.columns:
            raise KeyError(f"small_subgroup_policy = {C.SMALL_SUBGROUP_DROP} needs the column {C.SMALL_SUBGROUP_FLAG} (releases assembled with metamodel >= 0.2.6)")
        small = df[C.SMALL_SUBGROUP_FLAG].map(lambda v: bool(v) if pd.notna(v) else False).to_numpy()
        df[TRAIN_OK_COL] = ~(small & ~df[MAIN_COL].to_numpy())
    return df, names


# ---------------------------------------------------------------------------------------------
# one (protocol, fold, feature set, learner) cell
# ---------------------------------------------------------------------------------------------


@dataclass
class CellResult:
    strategy: str
    feature_set: str
    scored: pd.DataFrame
    outcomes: pd.DataFrame
    summary: Dict[str, float]
    extra: Dict[str, Any] = field(default_factory=dict)


def _evaluate_scored(scored: pd.DataFrame, names: Dict[str, str], cfg: MMConfig) -> Tuple[pd.DataFrame, Dict[str, float]]:
    rec = M.recommend(scored, conservative=cfg.conservative, eps=cfg.eps)
    extra_cols = [c for c in (names["macro_f1_delta"], names["s_san_delta"], names["s_san_v2_delta"], names["s_perf_delta"],
                              names["delta_imp"], names["delta_bal"]) if c in scored.columns]
    out = M.group_outcomes(scored, rec, y_col="y", eps=cfg.eps, extra_cols=extra_cols,
                           cost_col=names["cost_ratio"] if names["cost_ratio"] in scored.columns else None,
                           lambda_grid=cfg.lambda_grid, pareto_col=names["pareto"] if names["pareto"] in scored.columns else None)
    summary = M.summarise(out) if len(out) else {}
    if "score" in scored.columns and scored["score"].notna().any() and scored["score"].nunique() > 2:
        summary.update(M.prediction_errors(scored, "y", "score"))
    return out, summary


def _learner_cell(train: pd.DataFrame, test: pd.DataFrame, inner: Sequence[Tuple[pd.Series, pd.Series]], df: pd.DataFrame,
                  learner: str, fs: str, names: Dict[str, str], cfg: MMConfig, drop_task: bool) -> Tuple[Optional[CellResult], Dict[str, Any]]:
    """Inner loop on the inner folds, refit on the full training fold with the learner seeds, score the test fold."""
    registry: Dict[str, Any] = {"learner": learner, "feature_set": fs, "scenario": C.SCENARIO_OF_FS[fs], "formulation": L.FORMULATION[learner]}
    parts = (names["part_perf"], names["part_san"])
    if learner == "L6" and not all(p in train.columns for p in parts):
        registry["status"] = f"SKIPPED: decomposition parts {parts} absent (objective {names['stem']})"
        return None, registry
    pre_cols = F.select_columns(train.columns, fs, drop_task=drop_task)
    if not any(S.role_of(c)[1] == "X_STATE" for c in pre_cols) and fs in ("FS1", "FS2", "FS3"):
        registry["status"] = f"SKIPPED: no X_STATE columns for {fs} (state profile not in the meta-dataset)"
        return None, registry
    if fs in ("FS4", "FS5") and not any(S.role_of(c)[1] == "X_VAL" for c in pre_cols):
        registry["status"] = f"SKIPPED: no X_VAL columns for {fs}"
        return None, registry
    # inner loop with preprocessing fitted on the inner fit rows only (MQ04/MQ05)
    folds = []
    for fit_m, val_m in inner:
        ftr, fva = df[fit_m], df[val_m]
        if len(ftr) == 0 or len(fva) == 0:
            continue
        pre = F.Preprocessor(fs, drop_task=drop_task, add_interactions=(learner == "L1")).fit(ftr)
        folds.append((pre.transform(ftr), ftr, pre.transform(fva), fva))
    inner_loop = L.InnerLoop(learner, n_trials=cfg.n_trials, seed=0, conservative=cfg.conservative, eps=cfg.eps)
    if folds:
        inner_loop.run(folds, y_col="y", group_col="rec_group_id", parts_cols=parts if learner == "L6" else None)
        params = inner_loop.best_params_
    else:
        params = {}
        inner_loop.search_backend_ = "none (no inner folds)"
    pre = F.Preprocessor(fs, drop_task=drop_task, add_interactions=(learner == "L1")).fit(train)
    Xtr, Xte = pre.transform(train), pre.transform(test)
    seeds = cfg.learner_seeds if learner in L.RANDOMISED else (0,)
    scores, importances, fallback = [], [], False
    for sd in seeds:
        m = L.MetaLearner(learner, params=params, seed=sd)
        kw: Dict[str, Any] = {"groups": train["rec_group_id"], "eps": cfg.eps}
        if learner == "L6":
            kw["y_parts"] = (train[parts[0]], train[parts[1]])
        m.fit(Xtr, train["y"], **kw)
        scores.append(m.score(Xte))
        importances.append(m.feature_importance(pre.output_columns_))
        fallback |= m.fallback_
    S_ = np.vstack(scores)
    scored = test.copy()
    scored["score"] = S_.mean(axis=0)
    scored["score_sd_over_seeds"] = S_.std(axis=0) if len(seeds) > 1 else 0.0
    scored["strategy"] = f"{learner}-{fs}"
    scored_all = scored                      # 0.3.0: every scored test row; the cell is evaluated on the main report slice (Table 42)
    if MAIN_COL in scored.columns and not bool(scored[MAIN_COL].all()):
        scored = scored_all[scored_all[MAIN_COL].astype(bool)]
    outcomes, summary = _evaluate_scored(scored, names, cfg)
    imp = pd.concat(importances).groupby("feature")["importance"].agg(["mean", "std"]).reset_index().sort_values("mean", ascending=False)
    registry.update({"status": "OK", "best_params": json.dumps(params), "inner_best_mean_regret": inner_loop.best_value_,
                     "search_backend": inner_loop.search_backend_, "n_inner_folds": len(folds), "n_features": len(pre.output_columns_),
                     "dropped_features": json.dumps(pre.dropped_), "fallback_models": fallback, "n_learner_seeds": len(seeds)})
    return CellResult(f"{learner}-{fs}", fs, scored, outcomes, summary,
                      {"importance": imp, "preprocessor": pre, "params": params, "scored_all": scored_all}), registry


def permute_state_across_situations(train: pd.DataFrame, state_cols: Sequence[str], seed: int = 0, *, preserve_dtype: bool = True) -> pd.DataFrame:
    """MQ08: give every situation (recommendation group) of ``train`` the state of another situation; the context is untouched.

    0.3.1 (``preserve_dtype=True``): the permuted state is written column by column and every column keeps its dtype, so the
    preprocessor treats the control frame exactly as it treats the training frame.
    ``preserve_dtype=False`` reproduces the assignment of metamodel <= 0.3.0, ``perm[state_cols] = block.to_numpy()``: the mixed-type
    block is an object array, the numeric state columns become object columns and the preprocessor one-hot encodes them. That control
    differs from the model in the encoding of the state as well as in its assignment (defect found by the code team on 2026-11-24). The
    mode is kept only so that the tables delivered with 0.3.0 can be replayed and recognised.
    """
    rng = np.random.default_rng(seed)
    perm = train.copy()
    groups = perm["rec_group_id"].to_numpy()
    uniq = pd.unique(groups)
    mapping = dict(zip(uniq, rng.permutation(uniq)))
    first = perm.groupby("rec_group_id")[list(state_cols)].first()
    permuted_groups = pd.Series(groups).map(mapping).to_numpy()
    if not preserve_dtype:
        perm[list(state_cols)] = first.loc[permuted_groups].to_numpy()
        return perm
    mapped = first.loc[permuted_groups]
    for col in state_cols:
        perm[col] = pd.Series(mapped[col].array, index=perm.index).astype(train[col].dtype)
    return perm


def _negative_control(train: pd.DataFrame, test: pd.DataFrame, names: Dict[str, str], cfg: MMConfig, params: Dict[str, Any],
                      drop_task: bool, seed: int = 0, *, preserve_dtype: bool = True) -> Dict[str, float]:
    """MQ08: permute the state features across situations in meta-train (context untouched) and re-fit L3-FS3.
    One permutation and one learner seed (the registered control). 0.3.1: the permutation keeps the dtype of every state column."""
    state_cols = [c for c in F.select_columns(train.columns, "FS3", drop_task=drop_task) if S.role_of(c)[1] == "X_STATE"]
    perm = permute_state_across_situations(train, state_cols, seed, preserve_dtype=preserve_dtype)
    pre = F.Preprocessor("FS3", drop_task=drop_task).fit(perm)
    m = L.MetaLearner("L3", params=params, seed=seed).fit(pre.transform(perm), perm["y"], groups=perm["rec_group_id"], eps=cfg.eps)
    scored = test.copy()
    scored["score"] = m.score(pre.transform(test))
    out, summary = _evaluate_scored(scored, names, cfg)
    return {"mean_regret_permuted": summary.get("mean_regret", np.nan), "harm_rate_permuted": summary.get("harm_rate", np.nan),
            "control_n_features": int(len(pre.output_columns_)),
            "control_state_columns_with_changed_dtype": int(sum(perm[c].dtype != train[c].dtype for c in state_cols)),
            "control_permutation": C.NEG_CONTROL_DTYPE_PRESERVED if preserve_dtype else C.NEG_CONTROL_LEGACY_BLOCK}


def _l3_fs3_ensemble(train: pd.DataFrame, test: pd.DataFrame, names: Dict[str, str], cfg: MMConfig, params: Dict[str, Any],
                     drop_task: bool, *, perm_seed: Optional[int] = None) -> Dict[str, float]:
    """L3-FS3 fitted as ``_learner_cell`` fits the model of record: one preprocessor on the training fold, one fit per learner seed of
    the configuration, the mean score, the evaluation on ``test``. ``perm_seed=None`` uses the training fold as it is (the replay of
    the model of record); an integer first permutes the state across situations with that seed and keeps every dtype (0.3.1)."""
    frame = train
    if perm_seed is not None:
        state_cols = [c for c in F.select_columns(train.columns, C.PRIMARY_FEATURE_SET, drop_task=drop_task) if S.role_of(c)[1] == "X_STATE"]
        frame = permute_state_across_situations(train, state_cols, perm_seed, preserve_dtype=True)
    pre = F.Preprocessor(C.PRIMARY_FEATURE_SET, drop_task=drop_task).fit(frame)
    Xtr, Xte = pre.transform(frame), pre.transform(test)
    scores = [L.MetaLearner(C.PRIMARY_LEARNER, params=params, seed=sd).fit(Xtr, frame["y"], groups=frame["rec_group_id"], eps=cfg.eps).score(Xte)
              for sd in cfg.learner_seeds]
    scored = test.copy()
    scored["score"] = np.vstack(scores).mean(axis=0)
    _out, summary = _evaluate_scored(scored, names, cfg)
    return {"mean_regret": float(summary.get("mean_regret", np.nan)), "harm_rate": float(summary.get("harm_rate", np.nan)),
            "n_features": int(len(pre.output_columns_))}


def negative_control_only(meta: pd.DataFrame, run_dir: Path, out_dir: Path, *, expect_digest: Optional[str] = None,
                          tol: float = 1e-10, permutations: int = 0, write: bool = True) -> Dict[str, Any]:
    """Re-run the negative control alone for a delivered run (0.3.1; author decision of 2026-11-26 on question Q-48).

    Nothing of the analysis is fitted again apart from the control: the frozen configuration, the folds and the hyper-parameters of
    L3-FS3 are read from ``run_dir`` (mm_config.json, mm_run_registry.parquet) and the regret of the model of record from
    mm_negative_control.parquet. For every fold two controls are fitted with the registered design (one permutation, seed 0; one
    learner seed, 0): the replay of the control as the delivering package computed it, and the dtype-preserving control. The model of
    record is fitted again as well (stored hyper-parameters, the learner seeds of the configuration). Both replays must equal the
    delivered table within ``tol``; if one does not, the environment is not the one of the run and the fold is marked NOT_COMPARABLE.
    Writes mm_negative_control_r2.parquet / .csv and negative_control_r2_summary.json to ``out_dir``.

    ``permutations = K > 0`` adds a LABELLED EXPLORATORY table, mm_negative_control_r2_permutations: for the permutation seeds
    0..K-1 the dtype-preserving control is fitted with every learner seed of the configuration and scored as the model of record is
    (mean score over the learner seeds). That comparison is symmetric in the number of learner seeds, which the registered control
    is not (one seed against the mean of the seeds). It is not the registered control and never changes the flags of the first table.
    """
    run_dir, out_dir = Path(run_dir), Path(out_dir)
    cfg = MMConfig(**json.loads((run_dir / "mm_config.json").read_text(encoding="utf-8")))
    cfg.validate()
    digest = cfg.sha256()
    frozen = (run_dir / "mm_config_sha256.txt").read_text(encoding="utf-8").split()[0].strip().lower() if (run_dir / "mm_config_sha256.txt").exists() else None
    if frozen is not None and frozen != digest:
        raise ValueError(f"mm_config.json of {run_dir} has digest {digest}, mm_config_sha256.txt says {frozen}")
    if expect_digest and expect_digest.strip().lower() != digest:
        raise ValueError(f"the configuration digest {digest} is not the expected digest {expect_digest.strip().lower()}; nothing was run")
    reg = pd.read_parquet(run_dir / "mm_run_registry.parquet")
    delivered = pd.read_parquet(run_dir / "mm_negative_control.parquet")
    key = f"{C.PRIMARY_LEARNER}-{C.PRIMARY_FEATURE_SET}"
    versions = sorted(set(str(v) for v in reg["metamodel_version"].dropna().unique())) if "metamodel_version" in reg.columns else []
    delivered_mode = C.NEG_CONTROL_DTYPE_PRESERVED if (versions and all(_version_tuple(v) >= (0, 3, 1) for v in versions)) else C.NEG_CONTROL_LEGACY_BLOCK
    df, names = prepare_frame(meta, cfg)
    main_mask, ok_mask = df[MAIN_COL].astype(bool), df[TRAIN_OK_COL].astype(bool)
    one_slice = bool(main_mask.all())
    rows: List[Dict[str, Any]] = []
    perm_rows: List[Dict[str, Any]] = []
    for protocol in cfg.protocols:
        for fold, _task, _base in _fold_units(df, protocol, cfg):
            if not bool(ok_mask.all()):          # as in run_experiment: flagged secondary rows never enter a fit
                fold.train = fold.train & ok_mask
            train, test_all = df[fold.train], df[fold.test]
            test = test_all if one_slice else test_all[test_all[MAIN_COL].astype(bool)]
            base = {"protocol": protocol, "fold_id": fold.fold_id, "config_sha256": digest, "strategy": key}
            d = delivered[(delivered["protocol"] == protocol) & (delivered["fold_id"] == fold.fold_id)]
            r = reg[(reg["protocol"] == protocol) & (reg["fold_id"] == fold.fold_id) & (reg["strategy"] == key)]
            if len(d) != 1 or len(r) != 1 or len(train) == 0 or len(test) == 0:
                rows.append({**base, "status": "SKIPPED: the delivered run has no control or no L3-FS3 cell for this fold"})
                continue
            d, r = d.iloc[0], r.iloc[0]
            if str(r.get("status", "OK")) != "OK" or not isinstance(r.get("best_params"), str):
                rows.append({**base, "status": "SKIPPED: the L3-FS3 cell of the delivered run is not OK"})
                continue
            params = json.loads(r["best_params"])
            legacy = _negative_control(train, test, names, cfg, params, fold.drop_task, preserve_dtype=False)
            kept = _negative_control(train, test, names, cfg, params, fold.drop_task, preserve_dtype=True)
            replay = legacy if delivered_mode == C.NEG_CONTROL_LEGACY_BLOCK else kept
            replay_diff = abs(float(replay["mean_regret_permuted"]) - float(d["mean_regret_permuted"]))
            model = float(d["mean_regret_model"])
            model_replay = _l3_fs3_ensemble(train, test, names, cfg, params, fold.drop_task)
            model_diff = abs(model_replay["mean_regret"] - model)
            status = "OK"
            if replay_diff > tol:
                status = "NOT_COMPARABLE: the replay of the delivered control differs from the delivered table"
            elif model_diff > tol:
                status = "NOT_COMPARABLE: the replay of the model of record differs from the delivered table"
            if permutations > 0 and status == "OK":
                for ps in range(int(permutations)):
                    e = _l3_fs3_ensemble(train, test, names, cfg, params, fold.drop_task, perm_seed=ps)
                    perm_rows.append({**base, "analysis_label": C.NEG_CONTROL_EXPLORATORY_LABEL, "permutation_seed": ps,
                                      "n_learner_seeds": len(cfg.learner_seeds), "mean_regret_model": model,
                                      "mean_regret_permuted_ensemble": e["mean_regret"], "harm_rate_permuted_ensemble": e["harm_rate"],
                                      "delta_control_minus_model": e["mean_regret"] - model, "control_n_features": e["n_features"]})
                    _progress(f"exploratory control {protocol} {fold.fold_id} permutation {ps}: delta {e['mean_regret'] - model:+.6f}")
            rows.append({**base, "status": status,
                         "mean_regret_model": model, "mean_regret_B3": float(d["mean_regret_B3"]) if pd.notna(d.get("mean_regret_B3")) else np.nan,
                         "replay_mean_regret_model": model_replay["mean_regret"], "replay_model_abs_diff": model_diff,
                         "n_learner_seeds_model": len(cfg.learner_seeds), "n_learner_seeds_control": 1,
                         "delivered_mean_regret_permuted": float(d["mean_regret_permuted"]), "delivered_MQ08_pass": bool(d["MQ08_pass"]),
                         "delivered_control_permutation": delivered_mode, "replay_mean_regret_permuted": float(replay["mean_regret_permuted"]),
                         "replay_abs_diff": replay_diff,
                         "legacy_control_n_features": legacy["control_n_features"], "legacy_state_columns_with_changed_dtype": legacy["control_state_columns_with_changed_dtype"],
                         "mean_regret_permuted": float(kept["mean_regret_permuted"]), "harm_rate_permuted": float(kept["harm_rate_permuted"]),
                         "control_n_features": kept["control_n_features"], "control_state_columns_with_changed_dtype": kept["control_state_columns_with_changed_dtype"],
                         "control_permutation": kept["control_permutation"],
                         "MQ08_pass": bool(float(kept["mean_regret_permuted"]) >= model),
                         "n_train_rows": int(len(train)), "n_test_rows": int(len(test)), "best_params": r["best_params"]})
            _progress(f"negative control {protocol} {fold.fold_id}: delivered {bool(d['MQ08_pass'])} -> dtype-preserved {rows[-1]['MQ08_pass']} (replay diff {replay_diff:.2e})")
    table = pd.DataFrame(rows)
    ok = table[table["status"] == "OK"] if "status" in table.columns else table.iloc[0:0]
    summary = {"metamodel_version": _package_version(), "delivering_metamodel_versions": versions, "delivered_control_permutation": delivered_mode,
               "config_sha256": digest, "run_dir": run_dir.name, "folds": int(len(table)), "folds_ok": int(len(ok)),      # the directory name only: no machine path in a result file
               "folds_not_ok": sorted(f"{a}|{b}: {c}" for a, b, c in zip(table.get("protocol", []), table.get("fold_id", []), table.get("status", [])) if c != "OK"),
               "replay_max_abs_diff": float(ok["replay_abs_diff"].max()) if len(ok) else None,
               "replay_model_max_abs_diff": float(ok["replay_model_abs_diff"].max()) if len(ok) else None, "tolerance": tol,
               "registered_control": "one permutation (seed 0), one learner seed (0), against the model of record (mean score of the learner seeds of the configuration)",
               "delivered_passes": int(ok["delivered_MQ08_pass"].sum()) if len(ok) else None,
               "dtype_preserved_passes": int(ok["MQ08_pass"].sum()) if len(ok) else None,
               "flags_changed": sorted(f"{a}|{b}: {c} -> {e}" for a, b, c, e in zip(ok["protocol"], ok["fold_id"], ok["delivered_MQ08_pass"], ok["MQ08_pass"]) if bool(c) != bool(e)) if len(ok) else [],
               "all_state_dtypes_kept": bool((ok["control_state_columns_with_changed_dtype"] == 0).all()) if len(ok) else None,
               "env_id": _env_id(), "code_commit": _git_commit(), "environment": environment_record()}
    summary["verdict"] = "PASS" if (len(table) and len(ok) == len(table) and summary["all_state_dtypes_kept"]) else "FAIL"
    perm_table = pd.DataFrame(perm_rows)
    if len(perm_table):
        per_fold = []
        for (pr, fid), g in perm_table.groupby(["protocol", "fold_id"], sort=False):
            dlt = g["delta_control_minus_model"].to_numpy(dtype=float)
            per_fold.append({"protocol": pr, "fold_id": fid, "n": int(len(dlt)), "delta_min": float(dlt.min()), "delta_max": float(dlt.max()),
                             "delta_mean": float(dlt.mean()), "negative": int((dlt < 0).sum()), "positive": int((dlt > 0).sum()),
                             "ties": int((dlt == 0).sum())})
        summary["exploratory_permutations"] = {"label": C.NEG_CONTROL_EXPLORATORY_LABEL, "permutation_seeds": list(range(int(permutations))),
                                               "learner_seeds": [int(x) for x in cfg.learner_seeds], "delta": "control minus model (mean regret)",
                                               "per_fold": per_fold}
    if write:
        out_dir.mkdir(parents=True, exist_ok=True)
        table.to_parquet(out_dir / "mm_negative_control_r2.parquet", index=False)
        table.to_csv(out_dir / "mm_negative_control_r2.csv", index=False)
        if len(perm_table):
            perm_table.to_parquet(out_dir / "mm_negative_control_r2_permutations.parquet", index=False)
            perm_table.to_csv(out_dir / "mm_negative_control_r2_permutations.csv", index=False)
        (out_dir / "negative_control_r2_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"table": table, "permutations": perm_table, "summary": summary}


def _version_tuple(text: str) -> Tuple[int, ...]:
    m = re.match(r"\s*(\d+)\.(\d+)\.(\d+)", str(text))
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)


# ---------------------------------------------------------------------------------------------
# the experiment
# ---------------------------------------------------------------------------------------------


def _fold_units(df: pd.DataFrame, protocol: str, cfg: MMConfig) -> List[Tuple[P.Fold, Optional[str], str]]:
    """Folds of one protocol with the task they are trained on (None: one model for every task of the table) and their base fold id.
    Under E1_SCOPE_PER_TASK (decision 52 (a), §10.10) E1-A, E1-B and E3 are built once per task: one model per task and fold, scored on
    its own task. E2 is cross-task by definition and is never split."""
    if cfg.e1_scope == C.E1_SCOPE_PER_TASK and protocol in C.PER_TASK_PROTOCOLS:
        out: List[Tuple[P.Fold, Optional[str], str]] = []
        for t in sorted(df["task"].astype(str).unique()):
            for f in P.make_folds(df, protocol, tasks=[t]):
                base_id = f.fold_id
                f.fold_id = f"{t}:{base_id}"
                f.note = f"{f.note} | trained and scored on task {t} only"
                out.append((f, t, base_id))
        return out
    return [(f, None, f.fold_id) for f in P.make_folds(df, protocol)]


def evaluation_units(store: Dict[Tuple[str, str, str], pd.DataFrame], fold_index: Dict[Tuple[str, str], Tuple[str, Optional[str]]],
                     tasks: Sequence[str]) -> Dict[Tuple[str, str, str], Dict[str, pd.DataFrame]]:
    """(protocol, base fold id, task scope) -> {strategy: frame}. The task scope is one task or the joint label 'CQ+LO'.
    A fold trained on every task is the joint unit and its tasks are subsets of it; folds trained per task are units of their task and
    the joint unit is their concatenation (every situation scored by the model of its own task). §10.8: the joint units of E1-A and
    E1-B together form the pooled unit of the two tasks and the two folds. E2 folds are not units (H5 reads them directly)."""
    joint = "+".join(tasks)
    units: Dict[Tuple[str, str, str], Dict[str, pd.DataFrame]] = {}
    per_task_bases = set()
    for (protocol, fold_id, strategy), frame in store.items():
        if protocol == "E2" or (protocol, fold_id) not in fold_index:
            continue
        base_id, task = fold_index[(protocol, fold_id)]
        if task is None:
            units.setdefault((protocol, base_id, joint), {})[strategy] = frame
            if len(tasks) > 1 and "task" in frame.columns:
                for t in tasks:
                    part = frame[frame["task"].astype(str) == t]
                    if len(part):
                        units.setdefault((protocol, base_id, t), {})[strategy] = part
        else:
            units.setdefault((protocol, base_id, task), {})[strategy] = frame
            per_task_bases.add((protocol, base_id))
    if len(tasks) > 1:
        for protocol, base_id in sorted(per_task_bases):
            per = [units.get((protocol, base_id, t), {}) for t in tasks]
            if not all(per):
                continue
            for s in sorted(set.intersection(*[set(d) for d in per])):
                units.setdefault((protocol, base_id, joint), {})[s] = pd.concat([d[s] for d in per], ignore_index=True)
    a = sorted(k for k in units if k[0] == C.REPLICATION_PROTOCOL and k[2] == joint)
    b = sorted(k for k in units if k[0] == C.PRIMARY_PROTOCOL and k[2] == joint)
    if len(a) == 1 and len(b) == 1:
        common = sorted(set(units[a[0]]) & set(units[b[0]]))
        if common:
            units[(C.POOLED_PROTOCOL_LABEL, f"{a[0][1]}+{b[0][1]}", joint)] = {
                s: pd.concat([units[a[0]][s], units[b[0]][s]], ignore_index=True) for s in common}
    return units


def unit_metric_rows(units: Dict[Tuple[str, str, str], Dict[str, pd.DataFrame]], cfg: MMConfig, digest: str, report_slice: str,
                     descriptive_vs: Optional[str] = None) -> List[Dict[str, Any]]:
    """One row per evaluation unit and strategy: the summary of mm_metrics with its cluster-bootstrap intervals. ``descriptive_vs``
    (secondary slices): paired difference of the mean regret to that comparator with its interval, a description without a verdict."""
    rows: List[Dict[str, Any]] = []
    for (protocol, base_id, scope) in sorted(units):
        d = units[(protocol, base_id, scope)]
        for strategy in d:
            out = d[strategy]
            if not len(out):
                continue
            row = {"protocol": protocol, "fold_id": base_id, "task_scope": scope, "report_slice": report_slice, "config_sha256": digest,
                   "strategy": strategy, "feature_set": strategy.split("-", 1)[1] if "-" in strategy else "-", **M.summarise(out),
                   **_ci(out, "regret", cfg, "mean_regret"), **_ci(out, "harm", cfg, "harm_rate")}
            if descriptive_vs and descriptive_vs in d and strategy != descriptive_vs and len(d[descriptive_vs]):
                r = M.paired_cluster_bootstrap(out, d[descriptive_vs], "regret", cluster_fields=cfg.cluster_fields, b=cfg.bootstrap_b)
                row.update({f"regret_minus_{descriptive_vs}": r["estimate"], f"regret_minus_{descriptive_vs}_ci_low": r["ci_low"],
                            f"regret_minus_{descriptive_vs}_ci_high": r["ci_high"], f"regret_minus_{descriptive_vs}_n_clusters": r["n_clusters"],
                            "status": "DESCRIPTIVE"})
            rows.append(row)
    return rows


def run_experiment(meta: pd.DataFrame, cfg: MMConfig, out_dir: Path, *, write: bool = True) -> Dict[str, pd.DataFrame]:
    out_dir = Path(out_dir)
    cfg.validate()
    digest = cfg.freeze(out_dir) if write else cfg.sha256()
    t0 = time.time()
    df, names = prepare_frame(meta, cfg)
    legacy = cfg.is_legacy_design()
    main_mask, ok_mask = df[MAIN_COL].astype(bool), df[TRAIN_OK_COL].astype(bool)
    one_slice = bool(main_mask.all())
    matched = cfg.baseline_scope == C.BASELINE_SCOPE_MATCHED
    main_label = f"{cfg.subgroup[0]}/{cfg.subgroup[1]}"
    tasks_all = sorted(df["task"].astype(str).unique())
    metrics_rows, rec_rows, pred_rows, reg_rows, imp_rows, neg_rows, manifests = [], [], [], [], [], [], []
    comp_rows: List[Dict[str, Any]] = []
    sec_rec_rows: List[pd.DataFrame] = []
    outcomes_store: Dict[Tuple[str, str, str], pd.DataFrame] = {}
    scored_store: Dict[Tuple[str, str, str], pd.DataFrame] = {}
    sec_store: Dict[str, Dict[Tuple[str, str, str], pd.DataFrame]] = {}
    fold_index: Dict[Tuple[str, str], Tuple[str, Optional[str]]] = {}

    def baselines_of(train_: pd.DataFrame, test_: pd.DataFrame, drop_task: bool, include: Sequence[str], knn_k: int = 5) -> Dict[str, pd.DataFrame]:
        bl_ = B.run_baselines(train_, test_, objective_stem=names["stem"], include=include, knn_k=knn_k, drop_task=drop_task,
                              include_b7=cfg.include_b7)
        if cfg.include_b7 and cfg.b7_default_repair != C.B7_DEFAULT_REPAIR:
            try:
                bl_["B7"] = B.TempoDQPolicy(q3_pipeline=cfg.b7_default_repair, q4_pipeline=cfg.b7_default_repair).score(test_)
            except KeyError as exc:
                bl_["B7"] = pd.DataFrame({"error": [str(exc)]})
        return bl_

    for protocol in cfg.protocols:
        try:
            units = _fold_units(df, protocol, cfg)
        except ValueError as exc:
            reg_rows.append({"protocol": protocol, "fold_id": "-", "status": f"SKIPPED: {exc}"})
            continue
        for fold, _task, _base in units:
            if not bool(ok_mask.all()):          # small-subgroup policy: flagged secondary rows never enter a fit
                fold.train = fold.train & ok_mask
                fold.inner = [(fit & ok_mask, val) for fit, val in fold.inner]
            if matched and not one_slice:        # decision 53 (a): the inner selection minimises the regret of the main report slice
                fold.inner = [(fit, val & main_mask) for fit, val in fold.inner]
        manifests.append(P.split_manifest(df, [u[0] for u in units]))
        for fold, task, base_id in units:
            fold_index[(protocol, fold.fold_id)] = (base_id, task)
            train, test_all = df[fold.train], df[fold.test]
            test = test_all if one_slice else test_all[test_all[MAIN_COL].astype(bool)]
            if len(train) == 0 or len(test) == 0:
                reg_rows.append({"protocol": protocol, "fold_id": fold.fold_id, "status": "SKIPPED: empty train or test"})
                continue
            base = {"protocol": protocol, "fold_id": fold.fold_id, "config_sha256": digest}
            # ---- baselines (decision 53 (a): estimated on the training rows of the slice they score; ALL_ROWS: on every training row)
            bl_train = train if (one_slice or not matched) else train[train[MAIN_COL].astype(bool)]
            bl = baselines_of(bl_train, test, fold.drop_task, cfg.baselines)
            # B5: choose k on the inner folds (Table 46), inner fit rows only
            best_k: Optional[int] = None
            if "B5" in bl and "error" not in bl["B5"].columns and fold.inner:
                best_k, best_r = cfg.knn_k_grid[0], np.inf
                for k in cfg.knn_k_grid:
                    rs = []
                    for fit_m, val_m in fold.inner:
                        fit_rows = df[fit_m] if (one_slice or not matched) else df[fit_m & main_mask]
                        try:
                            sc = B.KNNMeta(k=k).fit(fit_rows, drop_task=fold.drop_task).score(df[val_m])
                            rs.append(L.mean_regret_of_scores(sc, sc["score"].to_numpy(), conservative=cfg.conservative, eps=cfg.eps))
                        except KeyError:
                            rs.append(np.inf)
                    r = float(np.mean(rs)) if rs else np.inf
                    if r < best_r:
                        best_k, best_r = k, r
                bl["B5"] = B.KNNMeta(k=best_k).fit(bl_train, drop_task=fold.drop_task).score(test)
                bl["B5"]["knn_k"] = best_k
            for name, scored in bl.items():
                if "error" in scored.columns:
                    reg_rows.append({**base, "strategy": name, "status": f"SKIPPED: {scored['error'].iloc[0]}"})
                    continue
                outcomes, summary = _evaluate_scored(scored, names, cfg)
                outcomes_store[(protocol, fold.fold_id, name)] = outcomes
                metrics_rows.append({**base, "strategy": name, "feature_set": "-", **summary,
                                     **_ci(outcomes, "regret", cfg, "mean_regret"), **_ci(outcomes, "harm", cfg, "harm_rate")})
                rec_rows.append(outcomes.assign(**base, strategy=name))
                reg_rows.append({**base, "strategy": name, "status": "OK", "learner": name, "feature_set": "-"})
            # ---- learners x feature sets (trained on every training row of the fold, scored on every test row, evaluated on the main slice)
            cells: Dict[str, CellResult] = {}
            grid = [(lr, fs) for lr in cfg.learners for fs in cfg.feature_sets] + [(lr, C.PRIMARY_FEATURE_SET) for lr in cfg.extra_learners]
            for i_cell, (learner, fs) in enumerate(grid):
                t_cell = time.time()
                _progress(f"{protocol} {fold.fold_id} cell {i_cell + 1}/{len(grid)} {learner}-{fs} start (train {len(train)} rows, test {len(test_all)} rows)")
                cell, reg = _learner_cell(train, test_all, fold.inner, df, learner, fs, names, cfg, fold.drop_task)
                _progress(f"{protocol} {fold.fold_id} cell {i_cell + 1}/{len(grid)} {learner}-{fs} {reg.get('status')} in {time.time() - t_cell:.0f} s")
                reg_rows.append({**base, "strategy": f"{learner}-{fs}", **reg})
                if cell is None:
                    continue
                cells[cell.strategy] = cell
                outcomes_store[(protocol, fold.fold_id, cell.strategy)] = cell.outcomes
                scored_store[(protocol, fold.fold_id, cell.strategy)] = cell.scored
                b3 = metrics_rows_lookup(metrics_rows, protocol, fold.fold_id, C.MAIN_COMPARATOR)
                gap = M.gap_closure(cell.summary.get("mean_regret", np.nan), b3.get("mean_regret", np.nan)) if b3 else np.nan
                metrics_rows.append({**base, "strategy": cell.strategy, "feature_set": fs, **cell.summary, "gap_closure_vs_B3": gap,
                                     **_ci(cell.outcomes, "regret", cfg, "mean_regret"), **_ci(cell.outcomes, "harm", cfg, "harm_rate")})
                rec_rows.append(cell.outcomes.assign(**base, strategy=cell.strategy))
                pred = cell.scored[["meta_obs_id", "rec_group_id", "pipeline_id", "y", "score", "score_sd_over_seeds"]].copy()
                pred_rows.append(pred.assign(**base, strategy=cell.strategy))
                imp_rows.append(cell.extra["importance"].assign(**base, strategy=cell.strategy))
            # ---- negative control (MQ08) on L3-FS3
            key = f"{C.PRIMARY_LEARNER}-{C.PRIMARY_FEATURE_SET}"
            if cfg.negative_control and key in cells:
                nc = _negative_control(train, test, names, cfg, cells[key].extra["params"], fold.drop_task)
                b3 = metrics_rows_lookup(metrics_rows, protocol, fold.fold_id, C.MAIN_COMPARATOR)
                neg_rows.append({**base, "strategy": key, **nc, "mean_regret_model": cells[key].summary.get("mean_regret", np.nan),   # 0.3.1: nc carries the dtype-preserving control
                                 "mean_regret_B3": b3.get("mean_regret", np.nan) if b3 else np.nan,
                                 "MQ08_pass": bool(nc["mean_regret_permuted"] >= cells[key].summary.get("mean_regret", np.nan))})
            if legacy:
                continue
            # ---- 0.3.0: what the fold was trained and scored on, and the secondary report slices (Table 42)
            for sl_name in pd.unique(df[SLICE_COL]):
                tr_s, te_s = train[train[SLICE_COL] == sl_name], test_all[test_all[SLICE_COL] == sl_name]
                comp_rows.append({**base, "base_fold_id": base_id, "task": task if task is not None else "+".join(tasks_all),
                                  "report_slice": sl_name, "is_main_slice": bool(sl_name == main_label),
                                  "n_train_rows": int(len(tr_s)), "n_train_groups": int(tr_s["rec_group_id"].nunique()),
                                  "n_test_rows": int(len(te_s)), "n_test_groups": int(te_s["rec_group_id"].nunique()),
                                  "n_inner_folds": int(len(fold.inner)),
                                  "n_inner_fit_groups": int(sum(df[f_ & (df[SLICE_COL] == sl_name)]["rec_group_id"].nunique() for f_, _v in fold.inner)),
                                  "n_inner_val_groups": int(sum(df[v_ & (df[SLICE_COL] == sl_name)]["rec_group_id"].nunique() for _f, v_ in fold.inner))})
            for sl_name in [s for s in pd.unique(test_all[SLICE_COL]) if s != main_label]:
                te_s = test_all[test_all[SLICE_COL] == sl_name]
                if len(te_s) == 0:
                    continue
                tr_s = train[train[SLICE_COL] == sl_name] if matched else train
                include = cfg.baselines if len(tr_s) else tuple(b for b in cfg.baselines if b in ("B0", "B1", "B6"))
                st = sec_store.setdefault(sl_name, {})
                bl_s = baselines_of(tr_s, te_s, fold.drop_task, include, knn_k=best_k if best_k is not None else cfg.knn_k_grid[0])
                for name, scored in bl_s.items():
                    if "error" in scored.columns:
                        continue
                    out_s, _ = _evaluate_scored(scored, names, cfg)
                    st[(protocol, fold.fold_id, name)] = out_s
                    sec_rec_rows.append(out_s.assign(**base, strategy=name, report_slice=sl_name))
                for cell in cells.values():
                    sc_all = cell.extra["scored_all"]
                    out_s, _ = _evaluate_scored(sc_all[sc_all[SLICE_COL] == sl_name], names, cfg)
                    st[(protocol, fold.fold_id, cell.strategy)] = out_s
                    sec_rec_rows.append(out_s.assign(**base, strategy=cell.strategy, report_slice=sl_name))
    joint_metrics, sec_metrics = pd.DataFrame(), pd.DataFrame()
    units_out = evaluation_units(outcomes_store, fold_index, tasks_all) if not (legacy and cfg.hypothesis_rows == C.HYP_ROWS_PRIMARY_ONLY) else {}
    if cfg.hypothesis_rows == C.HYP_ROWS_PRIMARY_ONLY:
        hyp = hypothesis_tests(outcomes_store, df, names, cfg, scored_store)
    else:
        hyp = hypothesis_tests_registered(units_out, evaluation_units(scored_store, fold_index, tasks_all), outcomes_store, df, names, cfg, tasks_all)
    if not legacy:
        joint_metrics = pd.DataFrame(unit_metric_rows(units_out, cfg, digest, main_label))
        sec_rows: List[Dict[str, Any]] = []
        for sl_name in sorted(sec_store):
            sec_rows += unit_metric_rows(evaluation_units(sec_store[sl_name], fold_index, tasks_all), cfg, digest, sl_name,
                                         descriptive_vs=C.MAIN_COMPARATOR)
        sec_metrics = pd.DataFrame(sec_rows)
    registry = pd.DataFrame(reg_rows).assign(code_commit=_git_commit(), env_id=_env_id(), config_sha256=digest,
                                             elapsed_s_total=time.time() - t0, lightgbm=L.HAS_LGB, optuna=L.HAS_OPTUNA,
                                             metamodel_version=_package_version(), cost_basis_rule=names.get("cost_basis_rule"))
    if not legacy:
        registry = registry.assign(e1_scope=cfg.e1_scope, baseline_scope=cfg.baseline_scope, hypothesis_rows=cfg.hypothesis_rows,
                                   training_subgroups="|".join(f"{a}/{v}" for a, v in cfg.slices()), small_subgroup_policy=cfg.small_subgroup_policy)
    results = {
        "mm_metrics": pd.DataFrame(metrics_rows),
        "mm_recommendations": pd.concat(rec_rows, ignore_index=True) if rec_rows else pd.DataFrame(),
        "mm_predictions": pd.concat(pred_rows, ignore_index=True) if pred_rows else pd.DataFrame(),
        "mm_run_registry": registry,
        "mm_cost_basis": cost_basis_table(df, names, digest),
        "mm_feature_importance": pd.concat(imp_rows, ignore_index=True) if imp_rows else pd.DataFrame(),
        "mm_negative_control": pd.DataFrame(neg_rows),
        "mm_hypotheses": hyp,
        "mm_split_manifest": pd.concat(manifests, ignore_index=True) if manifests else pd.DataFrame(),
        # 0.3.0 (empty, hence not written, for the 0.2.x plan)
        "mm_metrics_joint": joint_metrics,
        "mm_metrics_secondary": sec_metrics,
        "mm_recommendations_secondary": pd.concat(sec_rec_rows, ignore_index=True) if sec_rec_rows else pd.DataFrame(),
        "mm_fold_composition": pd.DataFrame(comp_rows),
    }
    if write:
        for name, frame in results.items():
            if len(frame):
                try:
                    frame.to_parquet(out_dir / f"{name}.parquet", index=False)
                except Exception:
                    pass
                frame.to_csv(out_dir / f"{name}.csv", index=False)
    return results


def metrics_rows_lookup(rows: List[Dict[str, Any]], protocol: str, fold_id: str, strategy: str) -> Dict[str, Any]:
    for r in rows:
        if r.get("protocol") == protocol and r.get("fold_id") == fold_id and r.get("strategy") == strategy:
            return r
    return {}


def _ci(outcomes: pd.DataFrame, col: str, cfg: MMConfig, label: str) -> Dict[str, float]:
    if not len(outcomes) or col not in outcomes.columns:
        return {}
    r = M.cluster_bootstrap_mean(outcomes, col, cluster_fields=cfg.cluster_fields, b=min(cfg.bootstrap_b, 2000), alpha=cfg.alpha_stat)
    return {f"{label}_ci_low": r["ci_low"], f"{label}_ci_high": r["ci_high"], f"{label}_n_clusters": r["n_clusters"]}


# ---------------------------------------------------------------------------------------------
# pre-registered hypotheses (Table 50) on the primary protocol
# ---------------------------------------------------------------------------------------------


def _h8_rows(outcomes: pd.DataFrame, df: pd.DataFrame, names: Dict[str, str], cfg: MMConfig, fold_id: str) -> List[Dict[str, Any]]:
    """H8 (contract 2026-10-24): among situations whose recommended pipeline is not V0 and whose realised effect is
    beneficial (delta > eps), the imputation share delta_imp / delta rises with the training missing rate and falls with
    the phase index. Spearman on cluster means with cluster-bootstrap intervals; nothing is retrained.
    """
    imp_col, bal_col = f"{names['delta_imp']}_recommended", f"{names['delta_bal']}_recommended"
    if imp_col not in outcomes.columns or "y_recommended" not in outcomes.columns:
        return [{"hypothesis": "H8", "comparison": "imputation share vs state / phase", "fold_id": fold_id,
                 "status": f"SKIPPED: {imp_col} not in outcomes (decomposition columns absent)"}]
    o = outcomes[(outcomes["pipeline_recommended"] != "V0") & (outcomes["y_recommended"] > cfg.eps)].copy()
    if len(o) == 0:
        return [{"hypothesis": "H8", "comparison": "imputation share vs state / phase", "fold_id": fold_id,
                 "status": "SKIPPED: no beneficial non-V0 recommendation"}]
    o["imp_share"] = o[imp_col].astype(float) / o["y_recommended"].astype(float)
    # situation-level state feature and phase index, joined through the situation id
    sit_cols = [c for c in (cfg.h8_state_feature, "phase_index") if c in df.columns]
    if "phase_index" not in sit_cols:
        return [{"hypothesis": "H8", "comparison": "imputation share vs state / phase", "fold_id": fold_id,
                 "status": "SKIPPED: phase_index absent"}]
    sit = df.groupby("rec_group_id", sort=False)[sit_cols].first()
    o = o.join(sit, on="rec_group_id")
    rows = []
    r_phase = M.cluster_spearman(o, "phase_index", "imp_share", cluster_fields=cfg.cluster_fields, b=cfg.bootstrap_b)
    n_cl = int(r_phase.get("n_clusters") or 0)
    enough = n_cl >= cfg.h8_min_clusters
    phase_row = {"hypothesis": "H8", "comparison": "Spearman(imp_share, phase_index) on cluster means, expected < 0", "fold_id": fold_id,
                 **r_phase, "n_groups": int(len(o)),
                 "supported": bool(enough and np.isfinite(r_phase["ci_high"]) and r_phase["ci_high"] < 0)}
    if not enough:
        phase_row["status"] = f"NO VERDICT: {n_cl} clusters < {cfg.h8_min_clusters} (author decision {C.H8_RESTATED_ON})"
    rows.append(phase_row)
    if cfg.h8_state_feature in o.columns and o[cfg.h8_state_feature].notna().any():
        r_state = M.cluster_spearman(o, cfg.h8_state_feature, "imp_share", cluster_fields=cfg.cluster_fields, b=cfg.bootstrap_b)
        # descriptive since 0.2.4 (author decision 2026-11-13): reported with its interval, never counted as support, outside Holm
        rows.append({"hypothesis": "H8", "comparison": f"Spearman(imp_share, {cfg.h8_state_feature}) on cluster means, descriptive",
                     "fold_id": fold_id, **r_state, "n_groups": int(len(o)), "supported": False, "status": "DESCRIPTIVE"})
    else:
        rows.append({"hypothesis": "H8", "comparison": f"Spearman(imp_share, {cfg.h8_state_feature})", "fold_id": fold_id,
                     "status": f"SKIPPED: {cfg.h8_state_feature} not in the meta-dataset (state profile S0 missing)"})
    return rows


def _hypothesis_rows(get, sc: Optional[pd.DataFrame], fid: str, df: pd.DataFrame, names: Dict[str, str], cfg: MMConfig) -> List[Dict[str, Any]]:
    """Rows of H1-H4 and H6-H8 for one evaluation unit. ``get(strategy)`` returns the group outcomes of the unit, ``sc`` the scored
    rows of L3-FS3 on it (H6). The tests are those of Table 50; 0.3.0 only separates them from the choice of the unit."""
    rows: List[Dict[str, Any]] = []
    L3FS3, L3FS2, L3FS4 = f"L3-{C.PRIMARY_FEATURE_SET}", "L3-FS2", "L3-FS4"
    a = get(L3FS3)
    if "H1" in cfg.hypotheses and a is not None and get("B3") is not None:
        r = M.paired_cluster_bootstrap(a, get("B3"), "regret", cluster_fields=cfg.cluster_fields, b=cfg.bootstrap_b)
        rows.append({"hypothesis": "H1", "comparison": f"{L3FS3} - B3 (mean regret)", "fold_id": fid, **r, "supported": r["ci_high"] < 0})
    if "H2" in cfg.hypotheses and a is not None and get(L3FS2) is not None:
        r = M.paired_cluster_bootstrap(a, get(L3FS2), "regret", cluster_fields=cfg.cluster_fields, b=cfg.bootstrap_b)
        rows.append({"hypothesis": "H2", "comparison": f"{L3FS3} - {L3FS2} (mean regret)", "fold_id": fid, **r, "supported": r["ci_high"] < 0})
    if "H3" in cfg.hypotheses and a is not None and get("B2") is not None:
        r = M.paired_cluster_bootstrap(a, get("B2"), "harm", cluster_fields=cfg.cluster_fields, b=cfg.bootstrap_b)
        rows.append({"hypothesis": "H3", "comparison": f"{L3FS3} - B2 (harm rate), non-inferiority margin +0.05", "fold_id": fid, **r,
                     "supported": r["ci_high"] < 0.05})
    if "H4" in cfg.hypotheses and a is not None and get(L3FS4) is not None:
        r = M.paired_cluster_bootstrap(get(L3FS4), a, "regret", cluster_fields=cfg.cluster_fields, b=cfg.bootstrap_b)
        rows.append({"hypothesis": "H4", "comparison": f"{L3FS4} - {L3FS3} (mean regret)", "fold_id": fid, **r, "supported": r["ci_high"] < 0})
    if "H6" in cfg.hypotheses and sc is not None and names["cost_ratio"] in sc.columns and sc[names["cost_ratio"]].notna().any():
        # lambda = 0.02 against lambda = 0 on the same scores: cost of the recommended pipeline falls, objective loss within eps
        u0 = M.utility_outcomes(sc, 0.0, cost_col=names["cost_ratio"])
        u2 = M.utility_outcomes(sc, 0.02, cost_col=names["cost_ratio"])
        if len(u0) and len(u2):
            r_cost = M.paired_cluster_bootstrap(u2, u0, "log2_cost_ratio_recommended", cluster_fields=cfg.cluster_fields, b=cfg.bootstrap_b)
            r_obj = M.paired_cluster_bootstrap(u2, u0, "y_recommended", cluster_fields=cfg.cluster_fields, b=cfg.bootstrap_b)
            rows.append({"hypothesis": "H6", "comparison": "L3-FS3 utility lambda=0.02 - lambda=0: mean log2 cost ratio (CI) and objective of the recommended pipeline",
                         "fold_id": fid, "estimate": r_cost["estimate"], "ci_low": r_cost["ci_low"], "ci_high": r_cost["ci_high"],
                         "n_clusters": r_cost["n_clusters"], "b": r_cost["b"], "p_boot": r_cost["p_boot"], "n_groups": r_cost["n_groups"],
                         "objective_diff_mean": r_obj["estimate"], "objective_diff_ci_low": r_obj["ci_low"],
                         "supported": bool(r_cost["estimate"] < 0 and r_obj["ci_low"] >= -cfg.eps)})
    if "H7" in cfg.hypotheses and a is not None:
        san_col = f"{names['s_san_v2_delta']}_recommended" if names["stem"] == "acctempo_m3_cal" else f"{names['s_san_delta']}_recommended"
        mf_col = f"{names['macro_f1_delta']}_recommended"
        if san_col in a.columns and mf_col in a.columns:
            ci_san = M.cluster_bootstrap_mean(a, san_col, cluster_fields=cfg.cluster_fields, b=cfg.bootstrap_b)
            ci_mf = M.cluster_bootstrap_mean(a, mf_col, cluster_fields=cfg.cluster_fields, b=cfg.bootstrap_b)
            rows.append({"hypothesis": "H7", "comparison": "composite recommendation: dS_san > 0 and dMacroF1 lower CI >= -eps", "fold_id": fid,
                         "estimate": ci_san["estimate"], "ci_low": ci_san["ci_low"], "ci_high": ci_san["ci_high"],
                         "macro_f1_delta_mean": ci_mf["estimate"], "macro_f1_delta_ci_low": ci_mf["ci_low"],
                         "supported": bool(ci_san["ci_low"] > 0 and ci_mf["ci_low"] >= -cfg.eps)})
    if "H8" in cfg.hypotheses and a is not None:
        rows.extend(_h8_rows(a, df, names, cfg, fid))
    return rows


def _h5_rows(store: Dict[Tuple[str, str, str], pd.DataFrame], cfg: MMConfig) -> List[Dict[str, Any]]:
    """H5: cross-task transfer (E2) — the learner keeps lower regret than B2 estimated on the source task, both directions."""
    rows: List[Dict[str, Any]] = []
    if "H5" not in cfg.hypotheses:
        return rows
    L3FS3 = f"L3-{C.PRIMARY_FEATURE_SET}"
    e2_folds = sorted({f for (p, f, s) in store if p == "E2"})
    per_dir = []
    for fid in e2_folds:
        a2, b2 = store.get(("E2", fid, L3FS3)), store.get(("E2", fid, "B2"))
        if a2 is None or b2 is None:
            continue
        r = M.paired_cluster_bootstrap(a2, b2, "regret", cluster_fields=cfg.cluster_fields, b=cfg.bootstrap_b)
        per_dir.append(bool(r["ci_high"] < 0))
        rows.append({"hypothesis": "H5", "comparison": f"E2 {L3FS3} - B2(source task) (mean regret)", "fold_id": fid, **r,
                     "supported": bool(r["ci_high"] < 0)})
    if per_dir:
        rows.append({"hypothesis": "H5", "comparison": "both transfer directions", "fold_id": "E2-all",
                     "supported": bool(len(per_dir) >= 2 and all(per_dir)), "n_directions": len(per_dir)})
    return rows


def _holm_one_family(out: pd.DataFrame, cfg: MMConfig, key_cols: Sequence[str]) -> pd.DataFrame:
    """Holm at alpha_stat over every test row of the table (Appendix E; decision 54 (b) for the full-design table): every row with a
    bootstrap p, except the rows marked DESCRIPTIVE, which are not tests (author decision 2026-11-13)."""
    if len(out) and "p_boot" in out.columns:
        keys = ["|".join(str(v) for v in t) for t in zip(*[out[c] for c in key_cols])]
        status = out["status"] if "status" in out.columns else pd.Series([None] * len(out))
        pv = {k: p for k, p, s in zip(keys, out["p_boot"], status) if pd.notna(p) and s != "DESCRIPTIVE"}   # descriptive rows are not tests
        adj = M.holm(pv, alpha=cfg.alpha_stat)
        out["p_holm"] = [adj.get(k, {}).get("p_holm", np.nan) for k in keys]
    return out


def hypothesis_tests(store: Dict[Tuple[str, str, str], pd.DataFrame], df: pd.DataFrame, names: Dict[str, str], cfg: MMConfig,
                     scored_store: Optional[Dict[Tuple[str, str, str], pd.DataFrame]] = None) -> pd.DataFrame:
    """The table of 0.2.x: H1-H4 and H6-H8 on every fold of the primary protocol found in the store, H5 on E2, one Holm family."""
    rows: List[Dict[str, Any]] = []
    prim = C.PRIMARY_PROTOCOL
    L3FS3 = f"L3-{C.PRIMARY_FEATURE_SET}"
    for fid in sorted({f for (p, f, s) in store if p == prim}):
        sc = scored_store.get((prim, fid, L3FS3)) if scored_store else None
        rows.extend(_hypothesis_rows(lambda strategy, _f=fid: store.get((prim, _f, strategy)), sc, fid, df, names, cfg))
    rows.extend(_h5_rows(store, cfg))
    return _holm_one_family(pd.DataFrame(rows), cfg, ("hypothesis", "fold_id", "comparison"))


def hypothesis_tests_registered(units: Dict[Tuple[str, str, str], Dict[str, pd.DataFrame]],
                                units_scored: Dict[Tuple[str, str, str], Dict[str, pd.DataFrame]],
                                store: Dict[Tuple[str, str, str], pd.DataFrame], df: pd.DataFrame, names: Dict[str, str], cfg: MMConfig,
                                tasks: Sequence[str]) -> pd.DataFrame:
    """The registered rows of the full-design table (0.3.0), each marked with its analysis_role:
    PRIMARY          E1-B on the clusters of every task together (decision 52 (a): the rows that carry the verdicts);
    PER_TASK         E1-B on the clusters of one task (reported beside the primary rows);
    REPLICATION_E1A  E1-A on the clusters of every task together (§10.8);
    POOLED_2FOLD     E1-A and E1-B together, the two tasks and the two folds (§10.8, 96 clusters on the registered grid);
    TRANSFER_E2      H5 on the E2 folds.
    Holm: one family over every test row of the table (decision 54 (b)). The secondary SEEN / UNSEEN slices are reports, not tests
    (Table 42): they are written to mm_metrics_secondary as descriptions and do not enter this table."""
    joint = "+".join(tasks)
    L3FS3 = f"L3-{C.PRIMARY_FEATURE_SET}"
    plan: List[Tuple[str, Tuple[str, str, str]]] = [(C.ROLE_PRIMARY, k) for k in sorted(units) if k[0] == C.PRIMARY_PROTOCOL and k[2] == joint]
    if len(tasks) > 1:
        plan += [(C.ROLE_PER_TASK, k) for t in tasks for k in sorted(units) if k[0] == C.PRIMARY_PROTOCOL and k[2] == t]
    plan += [(C.ROLE_REPLICATION, k) for k in sorted(units) if k[0] == C.REPLICATION_PROTOCOL and k[2] == joint]
    plan += [(C.ROLE_POOLED_2FOLD, k) for k in sorted(units) if k[0] == C.POOLED_PROTOCOL_LABEL and k[2] == joint]
    rows: List[Dict[str, Any]] = []
    for role, key in plan:
        d = units[key]
        sc = units_scored.get(key, {}).get(L3FS3)
        for r in _hypothesis_rows(d.get, sc, key[1], df, names, cfg):
            rows.append({"analysis_role": role, "protocol": key[0], "task_scope": key[2], **r})
    for r in _h5_rows(store, cfg):
        rows.append({"analysis_role": C.ROLE_TRANSFER, "protocol": "E2", "task_scope": r["fold_id"], **r})
    return _holm_one_family(pd.DataFrame(rows), cfg, ("analysis_role", "protocol", "task_scope", "hypothesis", "fold_id", "comparison"))
