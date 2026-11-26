# -*- coding: utf-8 -*-
"""Evaluation protocols E1-A, E1-B, E2, E3 and the W0_LOCKED fallback (Meta-Dataset-Report §10.6, Table 48).

A *fold* is a dict with boolean masks over the (filtered) meta-dataset: ``train``, ``test`` and a list of inner
(``fit``, ``validate``) mask pairs used only for hyper-parameter selection (MQ05). The split manifest records the
role of every row (MQ09 material).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

from . import contracts as C


@dataclass
class Fold:
    protocol: str
    fold_id: str
    train: pd.Series
    test: pd.Series
    inner: List[Tuple[pd.Series, pd.Series]] = field(default_factory=list)
    note: str = ""
    drop_task: bool = False


def _mask_windows(df: pd.DataFrame, windows: Sequence[str], tasks: Optional[Sequence[str]] = None,
                  tiers: Optional[Sequence[str]] = None) -> pd.Series:
    m = df["window_id"].isin(list(windows))
    if tasks is not None:
        m &= df["task"].isin(list(tasks))
    if tiers is not None:
        m &= df["model_tier"].isin(list(tiers))
    return m


def _group_kfold(df: pd.DataFrame, mask: pd.Series, by: Sequence[str], n_splits: int = 4) -> List[Tuple[pd.Series, pd.Series]]:
    sub = df[mask]
    key = sub[list(by)].astype(str).agg("|".join, axis=1)
    n = min(n_splits, key.nunique())
    if n < 2:
        return []
    gkf = GroupKFold(n_splits=n)
    out = []
    idx = sub.index.to_numpy()
    for fit_i, val_i in gkf.split(np.zeros(len(sub)), groups=key.to_numpy()):
        fit = pd.Series(False, index=df.index)
        val = pd.Series(False, index=df.index)
        fit.loc[idx[fit_i]] = True
        val.loc[idx[val_i]] = True
        out.append((fit, val))
    return out


def make_folds(df: pd.DataFrame, protocol: str, *, tasks: Optional[Sequence[str]] = None,
               inner_splits: int = 4) -> List[Fold]:
    """Build the folds of a protocol over the filtered meta-dataset (TEST rows of the chosen subgroup)."""
    tasks = list(tasks) if tasks is not None else sorted(df["task"].unique())
    folds: List[Fold] = []
    if protocol == "E1-A":
        train, test = _mask_windows(df, ["W1"], tasks), _mask_windows(df, ["W2"], tasks)
        inner = _group_kfold(df, train, ["model_name", "phase_id"], inner_splits)
        folds.append(Fold(protocol, "W1->W2", train, test, inner, "inner: GroupKFold by (model_name, phase_id) within W1"))
    elif protocol == "E1-B":
        train, test = _mask_windows(df, ["W1", "W2"], tasks), _mask_windows(df, ["W3"], tasks)
        inner = [(_mask_windows(df, ["W1"], tasks), _mask_windows(df, ["W2"], tasks))]
        folds.append(Fold(protocol, "W1W2->W3", train, test, inner, "inner: fit W1, validate W2; refit on W1+W2"))
    elif protocol == "E2":
        if len(tasks) < 2:
            raise ValueError("E2 needs two tasks")
        for src in tasks:
            for dst in tasks:
                if src == dst:
                    continue
                train, test = _mask_windows(df, ["W1", "W2"], [src]), _mask_windows(df, ["W3"], [dst])
                inner = [(_mask_windows(df, ["W1"], [src]), _mask_windows(df, ["W2"], [src]))]
                folds.append(Fold(protocol, f"{src}->{dst}", train, test, inner, "inner on the source task only; task is not a feature", drop_task=True))
    elif protocol == "E3":
        tiers = sorted(df["model_tier"].dropna().unique())
        if len(tiers) < 2:
            raise ValueError("E3 needs at least two model tiers")
        for held in tiers:
            others = [t for t in tiers if t != held]
            train, test = _mask_windows(df, ["W1", "W2"], tasks, others), _mask_windows(df, ["W3"], tasks, [held])
            inner = _group_kfold(df, train, ["model_name"], inner_splits)
            folds.append(Fold(protocol, f"holdout:{held}", train, test, inner, "inner: GroupKFold by model_name within the training tiers"))
    elif protocol == "W0_LOCKED":
        all_rows = _mask_windows(df, list(C.WINDOWS), tasks)
        for k, (fit, val) in enumerate(_group_kfold(df, all_rows, ["model_name", "phase_id"], inner_splits)):
            inner = _group_kfold(df, fit, ["model_name", "phase_id"], max(2, inner_splits - 1))
            folds.append(Fold(protocol, f"gkf{k}", fit, val, inner, "single-window fallback: no temporal generalisation claim"))
    else:
        raise ValueError(protocol)
    for f in folds:
        check_fold(df, f)
    return folds


def check_fold(df: pd.DataFrame, fold: Fold, group_col: str = "rec_group_id") -> Dict[str, bool]:
    """MQ02 (disjoint rec_groups), MQ03 (test windows strictly later, except W0_LOCKED), MQ05 (inner inside train)."""
    tr, te = df[fold.train], df[fold.test]
    mq02 = len(set(tr[group_col]) & set(te[group_col])) == 0
    mq03 = True if fold.protocol == "W0_LOCKED" else (te["window_index"].min() > tr["window_index"].max() if len(tr) and len(te) else False)
    mq05 = all(((fit | val) & ~fold.train).sum() == 0 for fit, val in fold.inner)
    if not (mq02 and mq03 and mq05):
        raise ValueError(f"fold {fold.protocol}/{fold.fold_id} fails MQ02={mq02} MQ03={mq03} MQ05={mq05}")
    return {"MQ02": mq02, "MQ03": mq03, "MQ05": mq05}


def split_manifest(df: pd.DataFrame, folds: Sequence[Fold], id_col: str = "meta_obs_id") -> pd.DataFrame:
    """fold x meta_obs_id -> role (TRAIN / TEST / INNER_FIT_k / INNER_VAL_k)."""
    rows = []
    for f in folds:
        ids = df[id_col]
        for role, mask in (("TRAIN", f.train), ("TEST", f.test)):
            rows.append(pd.DataFrame({"protocol": f.protocol, "fold_id": f.fold_id, id_col: ids[mask].to_numpy(), "role": role}))
        for k, (fit, val) in enumerate(f.inner):
            rows.append(pd.DataFrame({"protocol": f.protocol, "fold_id": f.fold_id, id_col: ids[fit].to_numpy(), "role": f"INNER_FIT_{k}"}))
            rows.append(pd.DataFrame({"protocol": f.protocol, "fold_id": f.fold_id, id_col: ids[val].to_numpy(), "role": f"INNER_VAL_{k}"}))
    out = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["protocol", "fold_id", id_col, "role"])
    out["manifest_sha256"] = C.sha256_of(sorted(out[["protocol", "fold_id", id_col, "role"]].astype(str).agg("|".join, axis=1).tolist()))
    return out
