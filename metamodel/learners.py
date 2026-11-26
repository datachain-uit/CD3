# -*- coding: utf-8 -*-
"""Meta-learners L1–L6 (Meta-Dataset-Report Table 47) with an inner loop whose objective is the mean regret.

* L1  elastic net with intervention-by-state interactions (F-REG)
* L2  ExtraTrees regression (F-REG)
* L3  LightGBM regression (F-REG, primary; also F-COST)
* L4  LightGBM LambdaRank grouped by situation, graded relevance (F-RANK)
* L5  LightGBM 3-class HARM / NEUTRAL / BENEFIT (F-CLS); score = P(BENEFIT) - P(HARM)
* L6  two LightGBM regressors for alpha*dlog S_perf and beta*dlog S_san (F-DEC); recombined at recommendation time

LightGBM and Optuna are optional imports: without them the fallbacks (sklearn HistGradientBoosting; random search)
are used and the run registry records ``fallback`` so that a result is never mistaken for the registered learner.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import ElasticNet

from . import contracts as C
from . import metrics as M

try:  # optional
    import lightgbm as lgb
    HAS_LGB = True
except Exception:  # pragma: no cover
    lgb = None
    HAS_LGB = False
try:  # optional
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    HAS_OPTUNA = True
except Exception:  # pragma: no cover
    optuna = None
    HAS_OPTUNA = False

LEARNERS: Tuple[str, ...] = ("L1", "L2", "L3", "L4", "L5", "L6")
FORMULATION: Dict[str, str] = {"L1": "F-REG", "L2": "F-REG", "L3": "F-REG", "L4": "F-RANK", "L5": "F-CLS", "L6": "F-DEC"}
RANDOMISED: Tuple[str, ...] = ("L2", "L3", "L4", "L5", "L6")


# ---------------------------------------------------------------------------------------------
# search spaces (Table 47)
# ---------------------------------------------------------------------------------------------


def sample_params(learner: str, trial_or_rng, as_rng: bool = False) -> Dict[str, Any]:
    """Draw hyper-parameters from the registered search space, from an Optuna trial or a numpy RNG."""
    if learner == "L1":
        if as_rng:
            return {"alpha": float(10 ** trial_or_rng.uniform(-4, 1)), "l1_ratio": float(trial_or_rng.choice([0.1, 0.5, 0.9]))}
        return {"alpha": trial_or_rng.suggest_float("alpha", 1e-4, 10.0, log=True),
                "l1_ratio": trial_or_rng.suggest_categorical("l1_ratio", [0.1, 0.5, 0.9])}
    if learner == "L2":
        if as_rng:
            options = [0.3, 0.5, "sqrt"]          # 0.2.5: index draw, numpy.choice would turn the floats into strings
            return {"max_features": options[int(trial_or_rng.integers(len(options)))], "min_samples_leaf": int(trial_or_rng.choice([5, 10, 20]))}
        return {"max_features": trial_or_rng.suggest_categorical("max_features", [0.3, 0.5, "sqrt"]),
                "min_samples_leaf": trial_or_rng.suggest_categorical("min_samples_leaf", [5, 10, 20])}
    # L3–L6 share the LightGBM space
    if as_rng:
        return {"num_leaves": int(trial_or_rng.integers(7, 64)), "learning_rate": float(10 ** trial_or_rng.uniform(-2, -1)),
                "min_data_in_leaf": int(trial_or_rng.integers(10, 101)), "feature_fraction": float(trial_or_rng.uniform(0.5, 1.0)),
                "lambda_l2": float(trial_or_rng.uniform(0.0, 10.0))}
    return {"num_leaves": trial_or_rng.suggest_int("num_leaves", 7, 63),
            "learning_rate": trial_or_rng.suggest_float("learning_rate", 0.01, 0.1, log=True),
            "min_data_in_leaf": trial_or_rng.suggest_int("min_data_in_leaf", 10, 100),
            "feature_fraction": trial_or_rng.suggest_float("feature_fraction", 0.5, 1.0),
            "lambda_l2": trial_or_rng.suggest_float("lambda_l2", 0.0, 10.0)}


L1_GRID: Tuple[Dict[str, Any], ...] = tuple({"alpha": a, "l1_ratio": l} for a in (1e-4, 1e-3, 1e-2, 1e-1, 1.0, 10.0) for l in (0.1, 0.5, 0.9))


# ---------------------------------------------------------------------------------------------
# the learner wrapper
# ---------------------------------------------------------------------------------------------


@dataclass
class MetaLearner:
    """A fitted meta-learner producing a per-row score for ranking candidates within a situation."""
    name: str
    params: Dict[str, Any] = field(default_factory=dict)
    seed: int = 0
    n_estimators: int = 400
    early_stopping_rounds: int = 50
    alpha_beta: Tuple[float, float] = (C.ACCTEMPO_ALPHA, C.ACCTEMPO_BETA)
    model_: Any = None
    model2_: Any = None
    y_loc_: float = 0.0
    y_scale_: float = 1.0
    fallback_: bool = False
    best_iteration_: Optional[int] = None

    # -- fit -----------------------------------------------------------------------------------
    def fit(self, X: pd.DataFrame, y: pd.Series, *, groups: Optional[pd.Series] = None, eps: float = C.REC_EPS,
            y_parts: Optional[Tuple[pd.Series, pd.Series]] = None, X_val: Optional[pd.DataFrame] = None,
            y_val: Optional[pd.Series] = None, groups_val: Optional[pd.Series] = None,
            y_val_parts: Optional[Tuple[pd.Series, pd.Series]] = None) -> "MetaLearner":
        Xn, yn = X.to_numpy(dtype=float), y.to_numpy(dtype=float)
        if self.name == "L1":
            # the target is standardised so that the registered alpha grid keeps its meaning whatever the delta scale;
            # scores are mapped back to the delta scale (ranking is invariant to the affine map)
            self.y_loc_, self.y_scale_ = float(np.mean(yn)), float(np.std(yn)) or 1.0
            self.model_ = ElasticNet(alpha=self.params.get("alpha", 1e-2), l1_ratio=self.params.get("l1_ratio", 0.5),
                                     max_iter=5000, random_state=self.seed)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                self.model_.fit(Xn, (yn - self.y_loc_) / self.y_scale_)
        elif self.name == "L2":
            self.model_ = ExtraTreesRegressor(n_estimators=500, max_features=self.params.get("max_features", "sqrt"),
                                              min_samples_leaf=self.params.get("min_samples_leaf", 10), random_state=self.seed, n_jobs=-1)
            self.model_.fit(Xn, yn)
        elif self.name == "L3":
            self.model_ = self._fit_regressor(Xn, yn, X_val, y_val)
        elif self.name == "L4":
            self.model_ = self._fit_ranker(X, y, groups, eps, X_val, y_val, groups_val)
        elif self.name == "L5":
            cls = _class_labels(yn, eps)
            self.model_ = self._fit_classifier(Xn, cls, X_val, None if y_val is None else _class_labels(y_val.to_numpy(dtype=float), eps))
        elif self.name == "L6":
            if y_parts is None:
                raise ValueError("L6 needs y_parts = (alpha*dlog S_perf, beta*dlog S_san)")
            yv1 = yv2 = None
            if y_val_parts is not None:
                yv1, yv2 = y_val_parts
            self.model_ = self._fit_regressor(Xn, y_parts[0].to_numpy(dtype=float), X_val, yv1)
            self.model2_ = self._fit_regressor(Xn, y_parts[1].to_numpy(dtype=float), X_val, yv2)
        else:
            raise ValueError(self.name)
        return self

    def _lgb_params(self, objective: str, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        p = {"objective": objective, "num_leaves": int(self.params.get("num_leaves", 15)),
             "learning_rate": float(self.params.get("learning_rate", 0.05)), "min_data_in_leaf": int(self.params.get("min_data_in_leaf", 20)),
             "feature_fraction": float(self.params.get("feature_fraction", 0.9)), "lambda_l2": float(self.params.get("lambda_l2", 1.0)),
             "n_estimators": self.n_estimators, "random_state": self.seed, "verbose": -1, "n_jobs": -1}
        p.update(extra or {})
        return p

    def _fit_regressor(self, Xn, yn, X_val, y_val):
        if HAS_LGB:
            model = lgb.LGBMRegressor(**self._lgb_params("regression"))
            if X_val is not None and y_val is not None and len(y_val):
                model.fit(Xn, yn, eval_set=[(X_val.to_numpy(dtype=float), np.asarray(y_val, dtype=float))],
                          callbacks=[lgb.early_stopping(self.early_stopping_rounds, verbose=False)])
                self.best_iteration_ = int(model.best_iteration_ or model.n_estimators)
            else:
                model.fit(Xn, yn)
            return model
        self.fallback_ = True
        model = HistGradientBoostingRegressor(max_leaf_nodes=int(self.params.get("num_leaves", 15)),
                                              learning_rate=float(self.params.get("learning_rate", 0.05)),
                                              min_samples_leaf=int(self.params.get("min_data_in_leaf", 20)),
                                              l2_regularization=float(self.params.get("lambda_l2", 1.0)), max_iter=self.n_estimators,
                                              early_stopping=X_val is not None, random_state=self.seed)
        model.fit(Xn, yn)
        return model

    def _fit_classifier(self, Xn, cls, X_val, cls_val):
        if HAS_LGB:
            model = lgb.LGBMClassifier(**self._lgb_params("multiclass", {"num_class": 3, "class_weight": "balanced"}))
            if X_val is not None and cls_val is not None and len(cls_val) and len(np.unique(cls_val)) == 3 and len(np.unique(cls)) == 3:
                model.fit(Xn, cls, eval_set=[(X_val.to_numpy(dtype=float), cls_val)],
                          callbacks=[lgb.early_stopping(self.early_stopping_rounds, verbose=False)])
            else:
                model.fit(Xn, cls)
            return model
        self.fallback_ = True
        model = HistGradientBoostingClassifier(max_leaf_nodes=int(self.params.get("num_leaves", 15)),
                                               learning_rate=float(self.params.get("learning_rate", 0.05)),
                                               min_samples_leaf=int(self.params.get("min_data_in_leaf", 20)),
                                               l2_regularization=float(self.params.get("lambda_l2", 1.0)), max_iter=self.n_estimators,
                                               class_weight="balanced", random_state=self.seed)
        model.fit(Xn, cls)
        return model

    def _fit_ranker(self, X, y, groups, eps, X_val, y_val, groups_val):
        if groups is None:
            raise ValueError("L4 needs rec_group ids")
        order = np.argsort(groups.to_numpy(), kind="stable")
        Xs, ys, gs = X.iloc[order], y.iloc[order], groups.iloc[order]
        rel = _relevance(ys.to_numpy(dtype=float), gs.to_numpy(), eps)
        sizes = gs.groupby(gs.to_numpy(), sort=False).size().to_numpy()  # contiguous group sizes
        if HAS_LGB:
            model = lgb.LGBMRanker(**self._lgb_params("lambdarank", {"metric": "ndcg", "eval_at": [3], "label_gain": [0, 1, 3, 7]}))
            if X_val is not None and y_val is not None and groups_val is not None and len(y_val):
                ov = np.argsort(groups_val.to_numpy(), kind="stable")
                Xv, yv, gv = X_val.iloc[ov], y_val.iloc[ov], groups_val.iloc[ov]
                relv = _relevance(yv.to_numpy(dtype=float), gv.to_numpy(), eps)
                sizes_v = gv.groupby(gv.to_numpy(), sort=False).size().to_numpy()
                model.fit(Xs.to_numpy(dtype=float), rel, group=sizes, eval_set=[(Xv.to_numpy(dtype=float), relv)], eval_group=[sizes_v],
                          callbacks=[lgb.early_stopping(self.early_stopping_rounds, verbose=False)])
            else:
                model.fit(Xs.to_numpy(dtype=float), rel, group=sizes)
            return model
        # fallback: regression on the graded relevance (not a listwise ranker; recorded as fallback)
        self.fallback_ = True
        model = HistGradientBoostingRegressor(max_iter=self.n_estimators, random_state=self.seed)
        model.fit(Xs.to_numpy(dtype=float), rel.astype(float))
        return model

    # -- predict -------------------------------------------------------------------------------
    def score(self, X: pd.DataFrame, alpha_beta: Optional[Tuple[float, float]] = None) -> np.ndarray:
        Xn = X.to_numpy(dtype=float)
        if self.name == "L5":
            proba = self.model_.predict_proba(Xn)
            classes = list(getattr(self.model_, "classes_", [0, 1, 2]))
            p_harm = proba[:, classes.index(0)] if 0 in classes else np.zeros(len(Xn))
            p_ben = proba[:, classes.index(2)] if 2 in classes else np.zeros(len(Xn))
            return p_ben - p_harm
        if self.name == "L1":
            return self.model_.predict(Xn) * self.y_scale_ + self.y_loc_
        if self.name == "L6":
            a, b = alpha_beta or self.alpha_beta
            part1 = self.model_.predict(Xn) / self.alpha_beta[0] * a      # re-weight the stored alpha-part to the requested alpha
            part2 = self.model2_.predict(Xn) / self.alpha_beta[1] * b
            return part1 + part2
        return self.model_.predict(Xn)

    def predicted_parts(self, X: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        if self.name != "L6":
            raise ValueError("parts only exist for L6")
        Xn = X.to_numpy(dtype=float)
        return self.model_.predict(Xn), self.model2_.predict(Xn)

    def feature_importance(self, columns: Sequence[str]) -> pd.DataFrame:
        imp = None
        if hasattr(self.model_, "feature_importances_"):
            imp = np.asarray(self.model_.feature_importances_, dtype=float)
            if self.model2_ is not None and hasattr(self.model2_, "feature_importances_"):
                imp = imp + np.asarray(self.model2_.feature_importances_, dtype=float)
        elif hasattr(self.model_, "coef_"):
            imp = np.abs(np.asarray(self.model_.coef_, dtype=float))
        if imp is None:
            return pd.DataFrame({"feature": list(columns), "importance": np.nan})
        return pd.DataFrame({"feature": list(columns), "importance": imp}).sort_values("importance", ascending=False)


def _class_labels(y: np.ndarray, eps: float) -> np.ndarray:
    return np.where(y < -eps, 0, np.where(y > eps, 2, 1)).astype(int)


def _relevance(y: np.ndarray, groups: np.ndarray, eps: float) -> np.ndarray:
    rel = np.zeros(len(y), dtype=int)
    df = pd.DataFrame({"y": y, "g": groups})
    best = df.groupby("g")["y"].transform("max").to_numpy()
    rel = np.where(y >= best - eps, 3, np.where(y > eps, 2, np.where(y < -eps, 0, 1)))
    return rel.astype(int)


# ---------------------------------------------------------------------------------------------
# inner loop: hyper-parameter search on mean regret
# ---------------------------------------------------------------------------------------------


def mean_regret_of_scores(frame: pd.DataFrame, scores: np.ndarray, y_col: str = "y", group_col: str = "rec_group_id",
                          conservative: bool = False, eps: float = C.REC_EPS) -> float:
    sc = frame[[group_col, "pipeline_id", y_col]].copy()
    sc["score"] = scores
    rec = M.recommend(sc, group_col=group_col, conservative=conservative, eps=eps)
    g = M.group_outcomes(sc, rec, group_col=group_col, y_col=y_col, eps=eps)
    return float(g["regret"].mean()) if len(g) else np.inf


@dataclass
class InnerLoop:
    """Hyper-parameter search with Optuna TPE (50 trials; L1 grid search), objective = mean regret on inner validation."""
    learner: str
    n_trials: int = 50
    seed: int = 0
    conservative: bool = False
    eps: float = C.REC_EPS
    best_params_: Dict[str, Any] = field(default_factory=dict)
    best_value_: float = np.inf
    trials_: List[Dict[str, Any]] = field(default_factory=list)
    search_backend_: str = ""

    def _evaluate(self, params: Dict[str, Any], folds: Sequence[Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]],
                  y_col: str, group_col: str, parts_cols: Optional[Tuple[str, str]]) -> float:
        regrets = []
        for Xtr, ftr, Xva, fva in folds:
            m = MetaLearner(self.learner, params=params, seed=self.seed)
            kwargs: Dict[str, Any] = {"groups": ftr[group_col], "eps": self.eps}
            if self.learner == "L6":
                kwargs["y_parts"] = (ftr[parts_cols[0]], ftr[parts_cols[1]])
            m.fit(Xtr, ftr[y_col], **kwargs)
            regrets.append(mean_regret_of_scores(fva, m.score(Xva), y_col, group_col, self.conservative, self.eps))
        return float(np.mean(regrets))

    def run(self, folds: Sequence[Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]], *, y_col: str = "y",
            group_col: str = "rec_group_id", parts_cols: Optional[Tuple[str, str]] = None) -> "InnerLoop":
        if self.learner == "L1":
            self.search_backend_ = "grid"
            for params in L1_GRID:
                v = self._evaluate(params, folds, y_col, group_col, parts_cols)
                self.trials_.append({**params, "mean_regret": v})
                if v < self.best_value_:
                    self.best_value_, self.best_params_ = v, dict(params)
            return self
        if HAS_OPTUNA:
            self.search_backend_ = "optuna_tpe"
            study = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=self.seed))

            def objective(trial):
                params = sample_params(self.learner, trial)
                v = self._evaluate(params, folds, y_col, group_col, parts_cols)
                self.trials_.append({**params, "mean_regret": v})
                return v

            study.optimize(objective, n_trials=self.n_trials, show_progress_bar=False)
            self.best_params_, self.best_value_ = dict(study.best_params), float(study.best_value)
            return self
        self.search_backend_ = "random_fallback"
        rng = np.random.default_rng(self.seed)
        for _ in range(self.n_trials):
            params = sample_params(self.learner, rng, as_rng=True)
            v = self._evaluate(params, folds, y_col, group_col, parts_cols)
            self.trials_.append({**params, "mean_regret": v})
            if v < self.best_value_:
                self.best_value_, self.best_params_ = v, dict(params)
        return self
