# -*- coding: utf-8 -*-
"""L3 assembly: long L2 facts -> meta_dataset_seed_level -> meta_dataset_seed_agg (Meta-Dataset-Report §3–§5, §6.4).

Inputs (all pandas frames; column names after :func:`normalise_fact_columns`):

* ``facts``          one row per (KEY_FIELDS) with the metrics of the *after* run measured on the slice of the row:
                     CORE/EXT metrics, sanity components (s_nan … s_leak, s_cal, s_san_plus, s_san_plus_v2), optional
                     per-class columns ``c{0,1,2}_{recall,...}``, optional ``n_eval_samples``, ``run_id`` and ``run_status``.
                     This is the grain of the R4 export ``*_family_pipeline_window_phase_metrics`` plus the key defaults.
* ``resources``      one row per run (RUN_FIELDS): ``train_seconds``, ``elapsed_seconds``, ``energy_gpu_estimated_kwh`` or
                     ``energy_gpu_run_kwh``, ``energy_measurement_type`` (R4 ``*_resource_per_run``).
* ``state_profile``  one row per STATE_SLICE_FIELDS with the Z_D / Z_DQ / Z_T columns measured on S0_RAW (not yet
                     produced by the team; when absent the meta-dataset has no X_STATE block and FS1–FS3 cannot be built).
* ``model_context``  one row per model_name with Z_M columns (param counts, hyper-parameters, ...).
* ``f0_reference``   one row per (task, window_id, phase_id, cohort, eval_split, subgroup_axis, subgroup_value) with the
                     metrics of the deterministic tier-F0 reference.

Nothing is invented: a reference that does not exist yields NULL with a reason code and a row status (§7.2–7.3).
"""
from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import warnings

import numpy as np
import pandas as pd

from . import contracts as C

TOL_IDENTITY = 1e-9       # §3.2 states 1e-12 on exact arithmetic; float32 exports need a looser tolerance, recorded in QA
TOL_RECOMPUTE = 1e-4      # exports are rounded to 4 decimals in the reports; the parquet facts carry full precision
TOL_LEAK_IDENTITY = 1e-9  # check 38 identity across pipelines and models of one (task, regime, window, seed, phase, cohort, split, subgroup).
                          # 1e-9 since release 0.2.4: the author ratified the reference-copy contract on 2026-11-13 (Q-31 (a), decision 42);
                          # check 42 (b) on the copied packages: 0.0 for CQ PatchTST r2 and MANTIS_V2 r3, <= 1.1e-16 for LO Mantis;
                          # the F1 exports equal the registered reference to 4.8e-11. 0.2.2-0.2.3 used 1e-4 while the decision was open.
RUN_LEVEL_INVARIANTS = ("s_eff",)  # QA24 as registered (tempo_fix.qa_checks.RUN_LEVEL_COLS): s_eff is a run-level quantity;
                                    # s_leak is NOT (it is scored on the real evaluation prefix of every phase and split)

REF_METRICS_F0: Tuple[str, ...] = ("macro_f1", "balanced_acc", "mcc", "kappa", "gmean", "s_perf")
# 0.2.6: a row is usable only if every one of these stems that the facts carry has a value on the row's own slice. On a subgroup slice
# they can be undefined (no enrollment, or a single class present: MCC and kappa have no value); the row is then INFEASIBLE (Table 36).
OBJECTIVE_STEMS: Tuple[str, ...] = ("s_perf", "acctempo_m3", "acctempo_m3_cal")
# 0.2.6: slice-size columns kept on the seed-aggregated table (role QA; never an input). They do not depend on the seed.
SLICE_SIZE_COLUMNS: Tuple[str, ...] = ("n_eval_samples", "ev_n_classes_present", "small_subgroup_flag", "small_support_flag")
TOL_RUN_LEVEL_INHERIT = 1e-9   # s_eff of a subgroup row against the ALL row of the same run, split and phase


# ---------------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------------


def normalise_reference_keys(df: pd.DataFrame) -> pd.DataFrame:
    """Key conventions of the context tables (S0 profile, F0 reference), request 2026-11-09 point 2.3 / release 0.2.2:
    a missing ``cohort`` or ``subgroup_*`` column means the whole evaluation split (cohort FIXED, subgroup ALL/ALL), and the
    value ``'ALL'`` in ``cohort`` denotes the same thing and is mapped to :data:`contracts.COHORT_FIXED`. Nothing else is changed."""
    out = df.copy()
    for col, default in (("cohort", C.COHORT_FIXED), ("subgroup_axis", "ALL"), ("subgroup_value", "ALL")):
        if col not in out.columns:
            out[col] = default
    out["cohort"] = out["cohort"].astype(str).replace({"ALL": C.COHORT_FIXED})
    return out


def normalise_fact_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename exporter column names to the registered metric names (contracts.METRIC_ALIASES)."""
    ren = {c: C.METRIC_ALIASES[c] for c in df.columns if c in C.METRIC_ALIASES and C.METRIC_ALIASES[c] not in df.columns}
    out = df.rename(columns=ren)
    # release 0.2.3: a frame concatenated from several exports can hold BOTH the exporter name and the registered name
    # (R4 writes f1_macro, the PatchTST/Mantis facts write macro_f1). The registered column wins where it is filled and
    # takes the exporter value where it is NaN; the exporter column is then dropped (kept, with a warning, if both are filled and disagree).
    for alias, target in C.METRIC_ALIASES.items():
        if alias in out.columns and target in out.columns:
            both = out[alias].notna() & out[target].notna()
            conflict = False
            if both.any():
                a_num = pd.to_numeric(out.loc[both, alias], errors="coerce").to_numpy(dtype=float)
                t_num = pd.to_numeric(out.loc[both, target], errors="coerce").to_numpy(dtype=float)
                conflict = not np.allclose(a_num, t_num, rtol=0.0, atol=1e-12, equal_nan=True)
            out[target] = out[target].where(out[target].notna(), out[alias])
            if conflict:
                warnings.warn(f"columns {alias!r} and {target!r} are both filled and disagree on some rows; "
                              f"{target!r} is kept where filled and {alias!r} is left in the frame", stacklevel=2)
            else:
                out = out.drop(columns=[alias])
    if "model_name" in out:
        out["model_name"] = out["model_name"].astype(str).str.upper()
    return out


def fill_key_defaults(df: pd.DataFrame, key_defaults: Optional[Mapping[str, Any]] = None) -> pd.DataFrame:
    """Add constant key components that an export omits (label rule, threshold set, regime, cohort, subgroup ALL)."""
    out = df.copy()
    defaults = {"cohort": C.COHORT_FIXED, "subgroup_axis": "ALL", "subgroup_value": "ALL"}
    defaults.update(key_defaults or {})
    for k in C.KEY_FIELDS:
        if k not in out.columns:
            if k not in defaults:
                raise KeyError(f"facts lack key column {k!r} and no default was given")
            out[k] = defaults[k]
        elif out[k].isna().any():
            # release 0.2.3: after concatenating exports, an export that omits the column leaves NaN in its rows
            # (R4 has no feature_regime, the PatchTST facts have it). The constant default fills those rows only.
            if k not in defaults:
                raise KeyError(f"facts have {int(out[k].isna().sum())} rows without key {k!r} and no default was given")
            out[k] = out[k].where(out[k].notna(), defaults[k])
    return out


def _canonical_key(row: Mapping[str, Any], fields: Sequence[str]) -> Dict[str, Any]:
    return {k: (int(row[k]) if k == "seed" else row[k]) for k in fields}


def add_identifiers(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    keys = out[list(C.KEY_FIELDS)].to_dict("records")
    out["meta_obs_id"] = [C.sha256_of(_canonical_key(r, C.KEY_FIELDS)) for r in keys]
    out["rec_group_id"] = [C.sha256_of(_canonical_key(r, C.SITUATION_FIELDS)) for r in keys]
    if "run_id" in out.columns and out["run_id"].notna().all():
        out["run_id_after"] = out["run_id"].astype(str)
    else:
        out["run_id_after"] = [C.sha256_of(_canonical_key(r, C.RUN_FIELDS)) for r in keys]
    out["run_group_id"] = out["run_id_after"]
    out["meta_cv_group"] = out["window_id"]
    out["phase_index"] = out["phase_id"].map(lambda p: C.PHASE_INDEX[p][0])
    out["q"] = out["phase_id"].map(lambda p: C.PHASE_INDEX[p][1])
    out["window_index"] = out["window_id"].map(C.WINDOW_INDEX)
    out["has_prev_phase"] = (out["phase_index"] > 1).astype(int)
    out["is_primary_cohort"] = (out["cohort"] == C.COHORT_FIXED).astype(int)
    out["population_varies_by_phase"] = 0
    return out


def add_composites(df: pd.DataFrame) -> pd.DataFrame:
    """Compute acctempo_m3 (if absent) and acctempo_m3_cal; record the recompute check."""
    out = df.copy()
    if {"s_perf", "s_san_plus"} <= set(out.columns):
        recomputed = C.acctempo(out["s_perf"], out["s_san_plus"])
        if "acctempo_m3" in out.columns:
            out["qa_metric_recompute_ok"] = ((out["acctempo_m3"] - recomputed).abs() <= TOL_RECOMPUTE) | out["acctempo_m3"].isna()
        else:
            out["acctempo_m3"] = recomputed
            out["qa_metric_recompute_ok"] = True
    else:
        out["qa_metric_recompute_ok"] = False
    if {"s_perf", "s_san_plus_v2"} <= set(out.columns):
        cal = C.acctempo(out["s_perf"], out["s_san_plus_v2"])
        if "acctempo_m3_cal" in out.columns:
            out["qa_metric_recompute_ok"] &= ((out["acctempo_m3_cal"] - cal).abs() <= TOL_RECOMPUTE) | out["acctempo_m3_cal"].isna()
        else:
            out["acctempo_m3_cal"] = cal
    return out


def _available(df: pd.DataFrame, names: Iterable[str]) -> List[str]:
    return [n for n in names if n in df.columns]


# ---------------------------------------------------------------------------------------------
# pairing with V0 and imputer-only references
# ---------------------------------------------------------------------------------------------


def pair_references(df: pd.DataFrame, metrics: Sequence[str], components: Sequence[str],
                    per_class: Sequence[str] = ()) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Join before (V0) and imputer-only values on the situation key; return (frame, null_reason frame)."""
    sit = list(C.SITUATION_FIELDS)
    value_cols = list(metrics) + list(components) + list(per_class)
    v0 = df[df["pipeline_id"] == "V0"][sit + value_cols + ["run_id_after"]].rename(
        columns={**{c: f"{c}_before" for c in value_cols}, "run_id_after": "run_id_before"})
    out = df.merge(v0, on=sit, how="left", validate="many_to_one")
    out["imputer_only_pipeline"] = out["pipeline_id"].map(C.IMPUTER_ONLY_REF)
    imp = df[sit + ["pipeline_id"] + list(metrics) + ["run_id_after"]].rename(
        columns={**{c: f"{c}_imp_only" for c in metrics}, "pipeline_id": "imputer_only_pipeline", "run_id_after": "run_id_imp_only"})
    out = out.merge(imp, on=sit + ["imputer_only_pipeline"], how="left", validate="many_to_one")
    nulls = pd.DataFrame(index=out.index)
    for m in metrics:
        out[f"{m}_after"] = out[m]
        out[f"{m}_delta"] = out[f"{m}_after"] - out[f"{m}_before"]
        out[f"{m}_delta_imp"] = out[f"{m}_imp_only"] - out[f"{m}_before"]
        out[f"{m}_delta_bal"] = out[f"{m}_after"] - out[f"{m}_imp_only"]
    for c in list(components) + list(per_class):
        out[f"{c}_after"] = out[c]
        out[f"{c}_delta"] = out[f"{c}_after"] - out[f"{c}_before"]
    # the exact V0 identity: after = before, delta = 0 (floating noise from the join is removed)
    is_v0 = out["pipeline_id"] == "V0"
    for m in metrics:
        out.loc[is_v0, f"{m}_delta"] = 0.0
        out.loc[is_v0, f"{m}_delta_imp"] = 0.0
        out.loc[is_v0, f"{m}_delta_bal"] = 0.0
    nulls["before_missing"] = out["run_id_before"].isna()
    nulls["imp_only_missing"] = out["run_id_imp_only"].isna()
    out = out.drop(columns=value_cols)   # the bare metric name is replaced by *_after (Table 25)
    return out, nulls


def add_log_decomposition(df: pd.DataFrame, floor: float = C.EPS_FLOOR) -> pd.DataFrame:
    """acctempo_{m3,m3_cal}_log_delta_perf_part / _san_part = alpha*dlog S_perf, beta*dlog S_san (§6.11, Table 25)."""
    out = df.copy()
    lg = lambda s: np.log(np.clip(s.astype(float), floor, 1.0))
    pairs = [("acctempo_m3", "s_san_plus"), ("acctempo_m3_cal", "s_san_plus_v2")]
    for comp, san in pairs:
        if {f"{comp}_after", f"s_perf_after", f"s_perf_before", f"{san}_after", f"{san}_before"} <= set(out.columns):
            out[f"{comp}_log_delta_perf_part"] = C.ACCTEMPO_ALPHA * (lg(out["s_perf_after"]) - lg(out["s_perf_before"]))
            out[f"{comp}_log_delta_san_part"] = C.ACCTEMPO_BETA * (lg(out[f"{san}_after"]) - lg(out[f"{san}_before"]))
    return out


def attach_f0_reference(df: pd.DataFrame, f0: Optional[pd.DataFrame]) -> Tuple[pd.DataFrame, pd.Series]:
    """{m}_ref and {m}_delta_ref for the deterministic reference; acctempo_m3_ref is NOT_APPLICABLE (Table 25)."""
    out = df.copy()
    keys = ["task", "window_id", "phase_id", "cohort", "eval_split", "subgroup_axis", "subgroup_value"]
    missing = pd.Series(True, index=out.index)
    if f0 is not None and len(f0):
        f0n = normalise_reference_keys(normalise_fact_columns(f0))
        avail = _available(f0n, REF_METRICS_F0)
        ref = f0n[keys + avail + (["run_id"] if "run_id" in f0n else [])].rename(
            columns={**{m: f"{m}_ref" for m in avail}, "run_id": "run_id_ref"})
        out = out.merge(ref, on=keys, how="left", validate="many_to_one")
        for m in avail:
            out[f"{m}_delta_ref"] = out[f"{m}_after"] - out[f"{m}_ref"]
        missing = out[f"{avail[0]}_ref"].isna() if avail else missing
        if "run_id_ref" not in out:
            out["run_id_ref"] = None
        tasks_with_f0 = set(f0n["task"].astype(str)) if "task" in f0n else set()
        for t in sorted(tasks_with_f0 & set(out["task"].astype(str))):
            if missing[out["task"].astype(str) == t].all():
                raise ValueError(f"f0_reference for task {t!r} joined 0 rows: check its keys {keys} (cohort {C.COHORT_FIXED!r}, "
                                 f"subgroup ALL/ALL; a cohort value 'ALL' is mapped to {C.COHORT_FIXED!r} automatically)")
    else:
        for m in REF_METRICS_F0:
            out[f"{m}_ref"] = np.nan
            out[f"{m}_delta_ref"] = np.nan
        out["run_id_ref"] = None
    out["acctempo_m3_ref"] = np.nan
    out["acctempo_m3_delta_ref"] = np.nan
    return out, missing


def attach_validation_copies(df: pd.DataFrame, metrics: Sequence[str], components: Sequence[str]) -> pd.DataFrame:
    """val_{m}_{before,after,delta} and val_s_*_{before,after} on TEST rows from the VALIDATION row of the same run/phase."""
    out = df.copy()
    keys = [k for k in C.KEY_FIELDS if k != "eval_split"]
    val = out[out["eval_split"] == "VALIDATION"]
    cols = {}
    for m in metrics:
        for suf in ("_before", "_after", "_delta"):
            cols[f"{m}{suf}"] = f"val_{m}{suf}"
    for c in components:
        for suf in ("_before", "_after", "_delta"):
            if f"{c}{suf}" in out.columns:
                cols[f"{c}{suf}"] = f"val_{c}{suf}"
    present = {k: v for k, v in cols.items() if k in val.columns}
    valx = val[keys + list(present)].rename(columns=present)
    out = out.merge(valx, on=keys, how="left", validate="many_to_one")
    is_val = out["eval_split"] == "VALIDATION"
    out.loc[is_val, list(present.values())] = np.nan    # NOT_APPLICABLE on VALIDATION rows
    return out


def attach_pipeline_context(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    pipe = pd.DataFrame(C.PIPELINES).rename(columns={"before_ref": "pipeline_before_ref", "imputer_only_ref": "pipeline_imputer_only_ref",
                                                     "imputer_only_ref_registry_literal": "pipeline_imputer_only_ref_registry_literal"})
    out = out.merge(pipe, on="pipeline_id", how="left", validate="many_to_one")
    for imp, _ in C.IMPUTERS:
        out[f"a_imp_{imp.lower()}"] = (out["imputer"] == imp).astype("int8")
    for bal in C.BALANCERS:
        out[f"a_bal_{bal.lower()}"] = (out["balancer"] == bal).astype("int8")
    out["pipeline_name"] = out["pipeline_id"]
    return out


def attach_model_context(df: pd.DataFrame, model_context: Optional[pd.DataFrame]) -> pd.DataFrame:
    out = df.copy()
    out["model_tier"] = out["model_name"].map(C.MODEL_TIER)
    out["model_family"] = out["model_name"].map(C.MODEL_FAMILY)
    if model_context is not None and len(model_context):
        mc = model_context.copy()
        mc["model_name"] = mc["model_name"].astype(str).str.upper()
        mc = mc.drop(columns=[c for c in mc.columns if c in out.columns and c != "model_name"])
        out = out.merge(mc, on="model_name", how="left", validate="many_to_one")
    return out


def attach_cost(df: pd.DataFrame, resources: Optional[pd.DataFrame]) -> Tuple[pd.DataFrame, pd.Series]:
    """Block C from per-run resources: time_train_s, time_run_total_s, energy_gpu_run_kwh (+ V0 before and ratio)."""
    out = df.copy()
    tele_missing = pd.Series(True, index=out.index)
    if resources is None or not len(resources):
        for c in ("time_train_s", "time_run_total_s", "energy_gpu_run_kwh"):
            for suf in ("_after", "_before", "_ratio"):
                out[f"{c}{suf}"] = np.nan
        out["energy_measurement_type"] = None
        out["cost_shared_across_phases"] = 1
        return out, tele_missing
    res = resources.copy()
    res["model_name"] = res["model_name"].astype(str).str.upper()
    res = res.drop(columns=[c for c in res.columns if c in out.columns and c not in C.RUN_FIELDS])
    ren = {"train_seconds": "time_train_s", "elapsed_seconds": "time_run_total_s"}
    if "energy_gpu_estimated_kwh" in res.columns:
        if "energy_gpu_run_kwh" not in res.columns:
            ren["energy_gpu_estimated_kwh"] = "energy_gpu_run_kwh"
        else:
            # 0.2.5: a resource table (or a concatenation of several) may carry both columns, e.g. the LO static-v2 table of seed 42 has an
            # entirely empty energy_gpu_run_kwh next to the filled NVML estimate. Until 0.2.4 the estimate was then ignored and every LO
            # energy column of the release stayed empty. The estimate now fills the rows whose run column is empty; energy_measurement_type
            # keeps saying what the value is, and the cost basis still decides whether an estimate counts (energy_measured_types).
            run = pd.to_numeric(res["energy_gpu_run_kwh"], errors="coerce")
            res["energy_gpu_run_kwh"] = run.where(run.notna(), pd.to_numeric(res["energy_gpu_estimated_kwh"], errors="coerce"))
    res = res.rename(columns=ren)
    join = [k for k in C.RUN_FIELDS if k in res.columns]
    keep = join + [c for c in ("time_train_s", "time_run_total_s", "energy_gpu_run_kwh", "energy_measurement_type", "gpu",
                               "batch_size", "micro_batch_size", "accumulation_steps", "execution_backend") if c in res.columns]
    res = res[keep].drop_duplicates(join)
    cost_cols = [c for c in ("time_train_s", "time_run_total_s", "energy_gpu_run_kwh") if c in res.columns]
    after = res.rename(columns={c: f"{c}_after" for c in cost_cols})
    out = out.merge(after, on=join, how="left", validate="many_to_one")
    v0 = res[res["pipeline_id"] == "V0"][[k for k in join if k != "pipeline_id"] + cost_cols].rename(
        columns={c: f"{c}_before" for c in cost_cols})
    out = out.merge(v0, on=[k for k in join if k != "pipeline_id"], how="left", validate="many_to_one")
    for c in cost_cols:
        before = out[f"{c}_before"]
        ratio = out[f"{c}_after"] / before.where(before != 0)
        out[f"{c}_ratio"] = ratio
        out[f"{c}_delta"] = out[f"{c}_after"] - before
    for c in ("time_train_s", "time_run_total_s", "energy_gpu_run_kwh"):
        for suf in ("_after", "_before", "_ratio", "_delta"):
            if f"{c}{suf}" not in out.columns:
                out[f"{c}{suf}"] = np.nan
    if "energy_measurement_type" not in out.columns:
        out["energy_measurement_type"] = None
    out["cost_shared_across_phases"] = 1
    tele_missing = out["time_run_total_s_after"].isna() & out["time_train_s_after"].isna()
    return out, tele_missing


def attach_state_profile(df: pd.DataFrame, state_profile: Optional[pd.DataFrame]) -> Tuple[pd.DataFrame, bool]:
    """Left-join the S0 profile on STATE_SLICE_FIELDS. Release 0.2.2: key conventions are normalised
    (:func:`normalise_reference_keys`), a profile that joins no row raises instead of leaving every X_STATE column NULL,
    and ``df.attrs['state_profile_join']`` records how many rows received a profile."""
    if state_profile is None or not len(state_profile):
        out = df.copy()
        out.attrs["state_profile_join"] = {"provided": False}
        return out, False
    sp = normalise_reference_keys(state_profile)
    keys = [k for k in C.STATE_SLICE_FIELDS if k in sp.columns]
    value_cols = [c for c in sp.columns if c not in keys]
    sp = sp.drop(columns=[c for c in value_cols if c in df.columns])
    value_cols = [c for c in sp.columns if c not in keys]
    if sp.duplicated(keys).any():
        raise ValueError("state_profile has duplicate state-slice keys")
    out = df.merge(sp, on=keys, how="left", validate="many_to_one", indicator="_sp_merge")
    matched = int((out["_sp_merge"] == "both").sum())
    by_subgroup = _coverage_by_subgroup(out, out["_sp_merge"] == "both")   # 0.2.6
    out = out.drop(columns="_sp_merge")
    if matched == 0:
        raise ValueError(f"state_profile joined 0 of {len(out)} rows on {keys}: check the key conventions of the profile "
                         f"(cohort {C.COHORT_FIXED!r} or 'ALL', subgroup ALL/ALL, feature_regime equal to the facts key)")
    out.attrs["state_profile_join"] = {"provided": True, "keys": keys, "rows_matched": matched, "rows_total": int(len(out)),
                                       "value_columns": len(value_cols), "by_subgroup": by_subgroup}
    return out, True


def _coverage_by_subgroup(df: pd.DataFrame, matched: pd.Series) -> Dict[str, Dict[str, int]]:
    """Rows and matched rows of a context join per subgroup (0.2.6): a profile or an F0 table written for the ALL slice only leaves the
    four other subgroups without values, and the total alone does not show it."""
    if not {"subgroup_axis", "subgroup_value"} <= set(df.columns):
        return {}
    lab = df["subgroup_axis"].astype(str) + "/" + df["subgroup_value"].astype(str)
    m = pd.Series(np.asarray(matched, dtype=bool), index=df.index)
    return {k: {"rows_matched": int(m[lab == k].sum()), "rows_total": int((lab == k).sum())} for k in sorted(lab.unique())}


# ---------------------------------------------------------------------------------------------
# QA flags, null reasons and row status
# ---------------------------------------------------------------------------------------------


def qa_flags(df: pd.DataFrame, metrics: Sequence[str], pairing_nulls: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["qa_pairing_ok"] = ~(pairing_nulls["before_missing"] | pairing_nulls["imp_only_missing"])
    ident = pd.Series(True, index=out.index)
    decomp = pd.Series(True, index=out.index)
    for m in metrics:
        a, b, d = out[f"{m}_after"], out[f"{m}_before"], out[f"{m}_delta"]
        ident &= ((a - b - d).abs() <= TOL_IDENTITY) | a.isna() | b.isna()
        di, db = out[f"{m}_delta_imp"], out[f"{m}_delta_bal"]
        decomp &= ((d - di - db).abs() <= TOL_IDENTITY) | d.isna() | di.isna() | db.isna()
    out["qa_delta_identity_ok"] = ident
    out["qa_decomposition_ok"] = decomp
    # QA24 as registered (tempo_fix.qa_checks.RUN_LEVEL_COLS): run-level quantities (s_eff) are constant across the phases and
    # evaluation splits of one run. Release 0.2.2 removes s_leak from this check: s_leak is scored on the real evaluation prefix
    # of every (window, split, phase) and legitimately varies within a run (CD3 M-14 RUN_LOG, 2026-11-10).
    inv = pd.Series(True, index=out.index)
    for comp in RUN_LEVEL_INVARIANTS:
        col = f"{comp}_after"
        if col in out.columns:
            spread = out.groupby("run_group_id")[col].transform(lambda s: s.max() - s.min())
            inv &= (spread.fillna(0.0) <= 1e-9)
    out["qa_run_level_invariant_ok"] = inv
    # leak-probe identity (check 38 of the registry): s_leak is a property of (task, regime, window, seed, phase, cohort, split,
    # subgroup) and must agree across every pipeline and model of that situation within TOL_LEAK_IDENTITY
    if "s_leak_after" in out.columns:
        sit = [k for k in C.SITUATION_FIELDS if k != "model_name" and k in out.columns]
        spread = out.groupby(sit)["s_leak_after"].transform(lambda s: s.max() - s.min())
        out["qa_leak_probe_identity_ok"] = spread.fillna(0.0) <= TOL_LEAK_IDENTITY
    else:
        out["qa_leak_probe_identity_ok"] = True
    v0 = out["pipeline_id"] == "V0"
    out["qa_v0_zero_delta_ok"] = True
    for m in metrics:
        out.loc[v0, "qa_v0_zero_delta_ok"] &= out.loc[v0, f"{m}_delta"].abs().fillna(0.0) <= TOL_IDENTITY
    return out


def finalise_status(df: pd.DataFrame, pairing_nulls: pd.DataFrame, f0_missing: pd.Series, tele_missing: pd.Series,
                    metrics: Sequence[str], components: Sequence[str], has_state: bool) -> pd.DataFrame:
    out = df.copy()
    status, reasons = [], []
    run_failed = out["run_status"].astype(str).str.upper().eq("FAILED") if "run_status" in out.columns else pd.Series(False, index=out.index)
    is_val = out["eval_split"] == "VALIDATION"
    # 0.2.6: the objective of the row itself, of its V0 reference and of its imputer-only reference must have a value. Until 0.2.5 a row
    # with an undefined metric was COMPLETE; on the ALL slice no such row exists, on a subgroup slice it does (empty slice, one class).
    stems = [m for m in OBJECTIVE_STEMS if m in metrics]

    def _undefined(suffix: str) -> pd.Series:
        cols = [f"{m}{suffix}" for m in stems if f"{m}{suffix}" in out.columns]
        return out[cols].isna().any(axis=1) if cols else pd.Series(False, index=out.index)

    after_undef, before_undef, imp_undef = _undefined("_after"), _undefined("_before"), _undefined("_imp_only")
    for i in out.index:
        nulls: Dict[str, str] = {}
        if run_failed.loc[i]:
            st = "RUN_FAILED"
            for m in metrics:
                for suf in ("_after", "_delta", "_delta_imp", "_delta_bal"):
                    nulls[f"{m}{suf}"] = "RUN_FAILED"
        elif after_undef.loc[i]:
            st = "INFEASIBLE"       # Table 36: the combination cannot be evaluated (here: the slice has no enrollment or lacks a class)
            for m in metrics:
                for suf in ("_after", "_delta", "_delta_imp", "_delta_bal"):
                    nulls[f"{m}{suf}"] = "CLASS_ABSENT"
        elif pairing_nulls.loc[i, "before_missing"] or before_undef.loc[i]:
            st = "MISSING_BASELINE"
            for m in metrics:
                for suf in ("_before", "_delta", "_delta_imp", "_delta_bal"):
                    nulls[f"{m}{suf}"] = "BASELINE_MISSING"
        elif pairing_nulls.loc[i, "imp_only_missing"] or imp_undef.loc[i]:
            st = "PARTIAL"
            for m in metrics:
                for suf in ("_imp_only", "_delta_imp", "_delta_bal"):
                    nulls[f"{m}{suf}"] = "BASELINE_MISSING"
        else:
            st = "COMPLETE"
        if f0_missing.loc[i]:
            for m in REF_METRICS_F0:
                nulls[f"{m}_ref"] = nulls[f"{m}_delta_ref"] = "BASELINE_MISSING"
        nulls["acctempo_m3_ref"] = nulls["acctempo_m3_delta_ref"] = "NOT_APPLICABLE"
        if tele_missing.loc[i]:
            for c in ("time_train_s", "time_run_total_s", "energy_gpu_run_kwh"):
                nulls[f"{c}_after"] = "TELEMETRY_UNAVAILABLE"
        elif pd.isna(out.loc[i, "energy_gpu_run_kwh_after"]) if "energy_gpu_run_kwh_after" in out.columns else False:
            nulls["energy_gpu_run_kwh_after"] = "TELEMETRY_UNAVAILABLE"
        if is_val.loc[i]:
            nulls["val_*"] = "NOT_APPLICABLE"
        if out.loc[i, "phase_id"] == "P1":
            nulls["*_prev"] = nulls["*_delta_prev"] = "NO_PREVIOUS_PHASE"
        if out.loc[i, "window_id"] == "W1":
            nulls["drift_window_prev_*"] = nulls["label_drift_window_prev_jsd"] = "NO_PREVIOUS_WINDOW"
        if not has_state:
            nulls["Z_D/Z_DQ/Z_T"] = "NOT_COMPUTED"
        status.append(st)
        reasons.append(json.dumps(nulls, sort_keys=True))
    out["row_status"] = status
    out["null_reason_map"] = reasons
    infeasible = out["row_status"] == "INFEASIBLE"
    if infeasible.any():            # 0.2.6: NULL, not 0 (§7.2); the reason of each column is in null_reason_map
        cols = [f"{m}{suf}" for m in metrics for suf in ("_delta", "_delta_imp", "_delta_bal") if f"{m}{suf}" in out.columns]
        out.loc[infeasible, cols] = np.nan
    return out


# ---------------------------------------------------------------------------------------------
# recommendation block R (§5.10, §6.4) — recomputable for any objective, eps, lambda grid and cost basis
# ---------------------------------------------------------------------------------------------


def _pareto_mask(perf: np.ndarray, cost: np.ndarray) -> np.ndarray:
    """True for points on the (max perf, min cost) frontier; NaN cost never on the frontier."""
    n = len(perf)
    on = np.zeros(n, dtype=bool)
    for i in range(n):
        if np.isnan(perf[i]) or np.isnan(cost[i]):
            continue
        dominated = False
        for j in range(n):
            if i == j or np.isnan(perf[j]) or np.isnan(cost[j]):
                continue
            if (perf[j] >= perf[i] and cost[j] <= cost[i]) and (perf[j] > perf[i] or cost[j] < cost[i]):
                dominated = True
                break
        on[i] = not dominated
    return on


ENERGY_N_SEEDS_COL = "energy_ratio_n_seeds"        # seed_agg (0.2.5): number of seeds whose row carries an energy ratio
ENERGY_TYPES_COL = "energy_measurement_types"      # seed_agg (0.2.5): '|'-joined measurement types of those seeds


def cost_basis_frame(df: pd.DataFrame, *, value_suffix: str = "_delta", group_col: str = "rec_group_id",
                     energy_measured_types: Sequence[str] = C.ENERGY_MEASURED_TYPES_STRICT) -> Tuple[pd.DataFrame, str]:
    """Cost basis of every recommendation group (REC_RULE ENERGY_IF_MEASURED_ELSE_TIME).

    ENERGY if every candidate of the group has an accepted energy ratio, else TIME if every candidate has a run-time ratio, else NONE.
    * seed-level table: a row's ratio is accepted when it is present and ``energy_measurement_type`` is in ``energy_measured_types``.
    * seed-aggregated table (0.2.5): in addition every planned seed must carry the ratio (``energy_ratio_n_seeds == n_seeds_planned``)
      and the measurement type of every seed must be accepted (``energy_measurement_types``). A table written by an assembler older than
      0.2.5 has neither column; the 0.2.4 rule (mean ratio present, type of the first seed) is then applied and reported as LEGACY.
    Returns (frame with ``cost_basis`` and ``cost_ratio_used`` on the index of ``df``, name of the rule applied).
    """
    agg = value_suffix.endswith("_mean")
    e_col = f"{C.COST_ENERGY_COL}_ratio" + ("_mean" if agg else "")
    t_col = f"{C.COST_TIME_COL}_ratio" + ("_mean" if agg else "")
    types = set(energy_measured_types)
    g = df[group_col]
    if e_col not in df.columns:
        e_ok, rule = pd.Series(False, index=df.index), "NO_ENERGY_COLUMN"
    elif agg and ENERGY_N_SEEDS_COL in df.columns and ENERGY_TYPES_COL in df.columns:
        planned = df["n_seeds_planned"].astype(float) if "n_seeds_planned" in df.columns else float(df[ENERGY_N_SEEDS_COL].max())
        types_ok = df[ENERGY_TYPES_COL].fillna("").map(lambda v: bool(v) and set(str(v).split("|")) <= types)
        e_ok, rule = df[e_col].notna() & (df[ENERGY_N_SEEDS_COL].astype(float) == planned) & types_ok, "ALL_PLANNED_SEEDS"
    else:
        etype = df["energy_measurement_type"] if "energy_measurement_type" in df.columns else pd.Series(None, index=df.index)
        e_ok, rule = df[e_col].notna() & etype.isin(list(types)), ("LEGACY_FIRST_SEED_TYPE" if agg else "ROW")
    t_ok = df[t_col].notna() if t_col in df.columns else pd.Series(False, index=df.index)
    e_all = e_ok.groupby(g).transform("all").astype(bool)
    t_all = t_ok.groupby(g).transform("all").astype(bool)
    basis = np.where(e_all, "ENERGY", np.where(t_all, "TIME", "NONE"))
    ratio = pd.Series(np.nan, index=df.index)
    if e_col in df.columns:
        ratio = ratio.where(~(e_all), df[e_col])
    if t_col in df.columns:
        ratio = ratio.where(~((~e_all) & t_all), df[t_col])
    return pd.DataFrame({"cost_basis": basis, "cost_ratio_used": ratio}, index=df.index), rule


def pareto_flags(df: pd.DataFrame, basis: pd.Series, *, value_suffix: str = "_delta", group_col: str = "rec_group_id",
                 perf_col: str = "macro_f1_after") -> np.ndarray:
    """Pareto frontier of (performance after, cost after) inside each group, with the cost column of the group's basis."""
    agg = value_suffix.endswith("_mean")
    pcol = perf_col + ("_mean" if agg and f"{perf_col}_mean" in df.columns else "")
    ccol_e = f"{C.COST_ENERGY_COL}_after" + ("_mean" if agg else "")
    ccol_t = f"{C.COST_TIME_COL}_after" + ("_mean" if agg else "")
    flag = np.zeros(len(df), dtype=bool)
    if pcol in df.columns and (ccol_e in df.columns or ccol_t in df.columns):
        b_arr = np.asarray(basis)
        for _, idx in df.groupby(group_col).indices.items():
            sub_ = df.iloc[idx]
            b = b_arr[idx][0]
            ccol = ccol_e if b == "ENERGY" else (ccol_t if b == "TIME" else None)
            if ccol is None or ccol not in sub_.columns:
                continue
            flag[idx] = _pareto_mask(sub_[pcol].to_numpy(dtype=float), sub_[ccol].to_numpy(dtype=float))
    return flag


def recommendation_labels(df: pd.DataFrame, objective_stem: str = C.OBJECTIVES[C.DEFAULT_OBJECTIVE], *,
                          value_suffix: str = "_delta", group_col: str = "rec_group_id", eps: float = C.REC_EPS,
                          lambda_grid: Sequence[float] = C.LAMBDA_GRID, label_suffix: str = "",
                          energy_measured_types: Sequence[str] = C.ENERGY_MEASURED_TYPES_STRICT,
                          perf_col: str = "macro_f1_after") -> pd.DataFrame:
    """Rank, regret, within-eps, beats/harms, graded relevance, utility per lambda and Pareto flag within each group.

    ``value_suffix`` is ``_delta`` on the seed-level table and ``_delta_mean`` on the seed-aggregated table.
    """
    out = df.copy()
    d = out[f"{objective_stem}{value_suffix}"].astype(float)
    g = out[group_col]
    best = d.groupby(g).transform("max")
    out[f"n_candidates{label_suffix}"] = d.groupby(g).transform("count")
    out[f"rank_delta{label_suffix}"] = (-d).groupby(g).rank(method="min")
    out[f"best_delta_in_group{label_suffix}"] = best
    d_filled = d.fillna(-np.inf)
    idx_best = d_filled.groupby(g).idxmax()
    best_pipe = out.loc[idx_best.to_numpy()].set_index(group_col)["pipeline_id"]
    out[f"best_pipeline_in_group{label_suffix}"] = g.map(best_pipe).where(best.notna())
    out[f"regret{label_suffix}"] = best - d
    out[f"is_best{label_suffix}"] = (d == best)
    out[f"within_eps_best{label_suffix}"] = d >= best - eps
    out[f"recommended{label_suffix}"] = out[f"within_eps_best{label_suffix}"]
    out[f"beats_v0{label_suffix}"] = d > eps
    out[f"harms_v0{label_suffix}"] = d < -eps
    grade = np.where(out[f"within_eps_best{label_suffix}"], 3, np.where(out[f"beats_v0{label_suffix}"], 2,
                     np.where(out[f"harms_v0{label_suffix}"], 0, 1)))
    out[f"relevance_grade{label_suffix}"] = grade.astype(int)
    out[f"rec_objective{label_suffix}"] = objective_stem
    out[f"rec_eps{label_suffix}"] = eps
    # cost basis per group: ENERGY if every candidate has an accepted energy ratio, else TIME, else NONE (one rule for the assembler and
    # for the experiment runner since 0.2.5: cost_basis_frame)
    cb, _ = cost_basis_frame(out, value_suffix=value_suffix, group_col=group_col, energy_measured_types=energy_measured_types)
    basis = cb["cost_basis"].to_numpy()
    ratio = cb["cost_ratio_used"]
    out[f"cost_basis{label_suffix}"] = basis
    out[f"cost_ratio_used{label_suffix}"] = ratio
    out[f"rec_energy_measured_types{label_suffix}"] = json.dumps(sorted(energy_measured_types))
    log_ratio = np.log2(ratio.where(ratio > 0))
    for j, lam in enumerate(lambda_grid):
        u = d - lam * log_ratio
        u = u.where(basis != "NONE", d if lam == 0 else np.nan)
        out[f"utility_l{j}{label_suffix}"] = u
        out[f"rank_utility_l{j}{label_suffix}"] = (-u).groupby(g).rank(method="min")
        umax = u.groupby(g).transform("max")
        out[f"recommended_utility_l{j}{label_suffix}"] = (u == umax) & u.notna()
    out[f"utility_lambda_grid{label_suffix}"] = json.dumps(list(lambda_grid))
    # Pareto frontier of (performance after, cost after) inside the group
    out[f"is_pareto_f1_cost{label_suffix}"] = pareto_flags(out, out[f"cost_basis{label_suffix}"], value_suffix=value_suffix,
                                                           group_col=group_col, perf_col=perf_col)
    return out


# ---------------------------------------------------------------------------------------------
# public entry points
# ---------------------------------------------------------------------------------------------


def assemble_seed_level(facts: pd.DataFrame, *, resources: Optional[pd.DataFrame] = None,
                        state_profile: Optional[pd.DataFrame] = None, model_context: Optional[pd.DataFrame] = None,
                        f0_reference: Optional[pd.DataFrame] = None, key_defaults: Optional[Mapping[str, Any]] = None,
                        provenance: Optional[Mapping[str, Any]] = None, objective_stem: str = C.OBJECTIVES[C.DEFAULT_OBJECTIVE],
                        energy_measured_types: Sequence[str] = C.ENERGY_MEASURED_TYPES_STRICT) -> pd.DataFrame:
    """Build meta_dataset_seed_level from long facts. See the module docstring for the input contract."""
    df = fill_key_defaults(normalise_fact_columns(facts), key_defaults)
    if df.duplicated(list(C.KEY_FIELDS)).any():
        dup = df[df.duplicated(list(C.KEY_FIELDS), keep=False)][list(C.KEY_FIELDS)].head()
        raise ValueError(f"facts have duplicate meta-observation keys, e.g.\n{dup}")
    unknown = sorted(set(df["pipeline_id"]) - set(C.PIPELINE_IDS))
    if unknown:
        raise ValueError(f"unknown pipeline ids {unknown}")
    df = add_identifiers(add_composites(df))
    metrics = _available(df, C.ALL_PAIRED_METRICS)
    components = _available(df, C.SAN_COMPONENTS + ("s_leak_probe_auc",))
    per_class = [c for c in df.columns if c.startswith(("c0_", "c1_", "c2_")) and c.split("_", 1)[1] in C.PER_CLASS_METRICS]
    df, pairing_nulls = pair_references(df, metrics, components, per_class)
    df = add_log_decomposition(df)
    df, f0_missing = attach_f0_reference(df, f0_reference)
    df = attach_validation_copies(df, metrics, components)
    df = attach_pipeline_context(df)
    df = attach_model_context(df, model_context)
    df, tele_missing = attach_cost(df, resources)
    df, has_state = attach_state_profile(df, state_profile)
    join_stats = dict(df.attrs.get("state_profile_join", {}))
    df = qa_flags(df, metrics, pairing_nulls)
    df = finalise_status(df, pairing_nulls, f0_missing, tele_missing, metrics, components, has_state)
    df.attrs["join_stats"] = {"state_profile": join_stats,
                              "f0_reference": {"provided": bool(f0_reference is not None and len(f0_reference)),
                                               "rows_matched": int((~f0_missing).sum()), "rows_total": int(len(df)),
                                               "by_task_subgroup": {t: _coverage_by_subgroup(df[df["task"].astype(str) == t],
                                                                                             (~f0_missing)[df["task"].astype(str) == t])
                                                                    for t in sorted(df["task"].astype(str).unique())}}}
    df["acctempo_alpha"], df["acctempo_beta"], df["acctempo_eps_floor"] = C.ACCTEMPO_ALPHA, C.ACCTEMPO_BETA, C.EPS_FLOOR
    df["acctempo_def_version"] = "acctempo_m3_v1.1"
    df["n_classes"] = 3
    if provenance:
        for k, v in provenance.items():
            df[k] = v
    df = recommendation_labels(df, objective_stem, energy_measured_types=energy_measured_types)
    return df


AGG_STATS: Tuple[Tuple[str, Any], ...] = (("mean", "mean"), ("sd", "std"), ("median", "median"), ("min", "min"), ("max", "max"),
                                          ("p90", lambda s: s.quantile(0.90)), ("p95", lambda s: s.quantile(0.95)))


def aggregate_seeds(seed_level: pd.DataFrame, *, planned_seeds: Optional[Sequence[int]] = None,
                    objective_stem: str = C.OBJECTIVES[C.DEFAULT_OBJECTIVE],
                    energy_measured_types: Sequence[str] = C.ENERGY_MEASURED_TYPES_STRICT,
                    sign_metrics: Sequence[str] = C.CORE_METRICS + ("acctempo_m3_cal",)) -> pd.DataFrame:
    """meta_dataset_seed_agg (§5.12): keys without seed; TARGET/DIAG/COST numeric columns -> 7 statistics; R recomputed."""
    from .schema import role_of
    keys = [k for k in C.KEY_FIELDS if k != "seed"]
    if planned_seeds is None:                      # default: the seeds present in the table; pass MASTER_SEEDS for the registered plan
        planned_seeds = tuple(sorted(int(s) for s in seed_level["seed"].unique()))
    complete = seed_level[seed_level["row_status"] == "COMPLETE"]
    agg_cols, carry_cols = [], []
    for c in seed_level.columns:
        block, role = role_of(c)
        if c in keys or c == "seed":
            continue
        if role in ("TARGET", "DIAG", "COST") and pd.api.types.is_numeric_dtype(seed_level[c]) and not c.startswith(("rank_", "regret")):
            agg_cols.append(c)
        elif role in ("KEY", "X_STATE", "X_CONTEXT", "X_VAL", "PROV") and c not in ("meta_obs_id", "run_id_after", "run_id_before",
                                                                                     "run_id_imp_only", "run_group_id", "attempt_id_after"):
            carry_cols.append(c)
        elif c == "synthetic":                     # the fixture flag must survive aggregation so that no synthetic table is mistaken for evidence
            carry_cols.append(c)
        elif c in SLICE_SIZE_COLUMNS:              # 0.2.6: size and support flags of the evaluated slice (they do not depend on the seed)
            carry_cols.append(c)
    grp = complete.groupby(keys, sort=False, dropna=False)
    pieces = [grp[carry_cols].first()] if carry_cols else []
    num = complete[agg_cols].astype(float)
    g_num = num.groupby([complete[k] for k in keys], sort=False, dropna=False)
    stat_frames = {"mean": g_num.mean(), "sd": g_num.std(), "median": g_num.median(), "min": g_num.min(), "max": g_num.max(),
                   "p90": g_num.quantile(0.90), "p95": g_num.quantile(0.95)}
    for name, frame in stat_frames.items():
        frame = frame.copy()
        frame.columns = [f"{c}_{name}" for c in frame.columns]
        pieces.append(frame)
    counts = pd.DataFrame({"n_seeds_success": grp.size(), "n_seeds_planned": len(planned_seeds)})
    pieces.append(counts)
    e_ratio = f"{C.COST_ENERGY_COL}_ratio"
    if e_ratio in complete.columns:                # 0.2.5: how many seeds carry an energy ratio, and with which measurement types
        by = [complete[k] for k in keys]
        has = complete[e_ratio].notna()
        pieces.append(has.groupby(by, sort=False, dropna=False).sum().astype(int).rename(ENERGY_N_SEEDS_COL).to_frame())
        etype = complete["energy_measurement_type"] if "energy_measurement_type" in complete.columns else pd.Series(None, index=complete.index, dtype=object)
        pieces.append(etype.where(has).groupby(by, sort=False, dropna=False).agg(lambda s: "|".join(sorted({str(v) for v in s.dropna()})))
                      .rename(ENERGY_TYPES_COL).to_frame())
    sign_cols = [f"{m}_delta" for m in sign_metrics if f"{m}_delta" in complete.columns]
    if sign_cols:
        d = complete[sign_cols].astype(float)
        gd = d.groupby([complete[k] for k in keys], sort=False, dropna=False)
        pos = (d > 0).groupby([complete[k] for k in keys], sort=False, dropna=False).sum()
        mn, mx = gd.min(), gd.max()
        cons = (mn > 0) | (mx < 0) | ((mn == 0) & (mx == 0))
        pos.columns = [f"{c}_n_positive_seeds" for c in pos.columns]
        cons.columns = [f"{c}_sign_consistent" for c in cons.columns]
        pieces += [pos.astype(int), cons.astype(bool)]
    agg = pd.concat(pieces, axis=1).reset_index()
    agg = agg.copy()
    agg["meta_obs_id_agg"] = [C.sha256_of({k: (r[k] if k != "seed" else None) for k in keys}) for r in agg[keys].to_dict("records")]
    agg["rec_group_id_agg"] = [C.sha256_of({k: r[k] for k in keys if k != "pipeline_id"}) for r in agg[keys].to_dict("records")]
    agg["meta_cv_group"] = agg["window_id"]
    agg["row_status_agg"] = np.where(agg["n_seeds_success"] == len(planned_seeds), "COMPLETE", "PARTIAL")
    agg["planned_seeds"] = json.dumps(list(planned_seeds))
    agg = recommendation_labels(agg, objective_stem, value_suffix="_delta_mean", group_col="rec_group_id_agg",
                                label_suffix="_agg", energy_measured_types=energy_measured_types)
    return agg


# ---------------------------------------------------------------------------------------------
# five-subgroup releases (0.2.6): integrity report and comparison of the main slice with an accepted release
# ---------------------------------------------------------------------------------------------

SUBGROUP_PARENT_KEYS: Tuple[str, ...] = tuple(k for k in C.KEY_FIELDS if k not in ("subgroup_axis", "subgroup_value"))


def _slice(df: pd.DataFrame, axis: str, value: str) -> pd.DataFrame:
    return df[(df["subgroup_axis"].astype(str) == axis) & (df["subgroup_value"].astype(str) == value)]


def subgroup_report(seed_level: pd.DataFrame, required: Sequence[Tuple[str, str]] = C.MANDATORY_SUBGROUPS, *,
                    require_state: bool = True, max_examples: int = 5) -> Dict[str, Any]:
    """Integrity of a seed-level table that carries subgroup rows (Meta-Dataset-Report §2.5, §3.3, §10.3; QA01, QA06, QA24).

    Checked against the (ALL, ALL) row of the same run, evaluation split and phase:
      * every required subgroup has rows, and every subgroup row has its ALL row and vice versa (QA01: no combination left out silently);
      * on each axis of :data:`contracts.SUBGROUP_PARTITION_AXES`, n_eval_samples and the class supports of SEEN and UNSEEN add up to ALL (QA06);
        n_eval_samples is required on the three rows, the class supports are compared where the three rows carry them;
      * s_eff (run level, QA24) and s_leak (one value per window x split x phase, the rule the facts packages apply to the STRICT/OVERLAP
        slices) equal the ALL row;
      * the state profile, when one was given, covers every subgroup.
    Returns a JSON-serialisable dict with ``ok`` and the list ``violations``; counts by subgroup and by row status are always reported.
    """
    df = seed_level
    lab = df["subgroup_axis"].astype(str) + "/" + df["subgroup_value"].astype(str)
    rep: Dict[str, Any] = {"rows_by_subgroup": {k: int(v) for k, v in lab.value_counts().sort_index().items()},
                           "required": [f"{a}/{v}" for a, v in required]}
    violations: List[str] = []
    if "row_status" in df.columns:
        ct = pd.crosstab(lab, df["row_status"])
        rep["row_status_by_subgroup"] = {k: {c: int(ct.loc[k, c]) for c in ct.columns if ct.loc[k, c]} for k in ct.index}
    missing = [k for k in rep["required"] if k not in rep["rows_by_subgroup"]]
    if missing:
        violations.append(f"required subgroups without rows: {missing}")
    keys = list(SUBGROUP_PARENT_KEYS)
    all_rows = _slice(df, "ALL", "ALL").set_index(keys)
    if all_rows.index.has_duplicates:
        violations.append("duplicate keys on the (ALL, ALL) slice")
        rep.update({"ok": False, "violations": violations})
        return rep
    grid, inherit = {}, {}
    for k in rep["rows_by_subgroup"]:
        if k == "ALL/ALL":
            continue
        a, v = k.split("/", 1)
        sub_ = _slice(df, a, v).set_index(keys)
        no_parent = sub_.index.difference(all_rows.index)
        no_child = all_rows.index.difference(sub_.index)
        grid[k] = {"rows": int(len(sub_)), "rows_without_all_row": int(len(no_parent)), "all_rows_without_this_subgroup": int(len(no_child))}
        if len(no_parent) or len(no_child):
            violations.append(f"{k}: {len(no_parent)} rows without an ALL row and {len(no_child)} ALL rows without a {k} row (QA01)")
        common = sub_.index.intersection(all_rows.index)
        inherit[k] = {}
        for comp, tol in (("s_eff_after", TOL_RUN_LEVEL_INHERIT), ("s_leak_after", TOL_LEAK_IDENTITY)):
            if comp not in df.columns or not len(common):
                continue
            d = (sub_.loc[common, comp].astype(float) - all_rows.loc[common, comp].astype(float)).abs()
            n_null = int(sub_.loc[common, comp].isna().sum())
            worst = float(d.max()) if d.notna().any() else 0.0
            inherit[k][comp] = {"max_abs_diff_to_all": worst, "rows_null": n_null, "tolerance": tol}
            if worst > tol:
                violations.append(f"{k}: {comp} differs from the ALL row of the same run, split and phase by up to {worst:.3g} (> {tol:g})")
    rep["grid"], rep["inherited_components"] = grid, inherit
    part = {}
    count_cols = [c for c in ["n_eval_samples"] + [f"{c}_support" for c in C.CLASSES] if c in df.columns]
    for axis in C.SUBGROUP_PARTITION_AXES:
        seen, unseen = _slice(df, axis, "SEEN").set_index(keys), _slice(df, axis, "UNSEEN").set_index(keys)
        if not len(seen) and not len(unseen):
            continue
        part[axis] = {}
        for c in count_cols:
            tot = all_rows[c].astype(float)
            s_ = seen[c].astype(float).reindex(tot.index)
            u_ = unseen[c].astype(float).reindex(tot.index)
            known = tot.notna() & s_.notna() & u_.notna()
            bad = known & ((s_ + u_ - tot).abs() > 0.5)
            part[axis][c] = {"cells_checked": int(known.sum()), "cells_not_adding_up": int(bad.sum()),
                             "cells_without_a_count": int((~known).sum())}
            if bad.any():
                ex = [dict(zip(keys, i)) for i in tot.index[bad][:max_examples]]
                violations.append(f"{axis}: SEEN + UNSEEN != ALL on {c} in {int(bad.sum())} cells (QA06), e.g. {ex[0]}")
            if (~known).any() and c == "n_eval_samples":      # class supports are checked where the three rows carry them; the slice size is required
                violations.append(f"{axis}: {int((~known).sum())} cells without {c} on ALL, SEEN or UNSEEN (an empty slice is a row with count 0, QA01)")
    rep["partition"] = part
    if not count_cols and len(rep["rows_by_subgroup"]) > 1:
        violations.append("no n_eval_samples / c*_support column: the partition SEEN + UNSEEN = ALL cannot be checked")
    sp = dict(df.attrs.get("join_stats", {}).get("state_profile", {}))
    if require_state and sp.get("provided"):
        short = {k: v for k, v in sp.get("by_subgroup", {}).items() if v["rows_matched"] < v["rows_total"]}
        rep["state_profile_rows_unmatched"] = {k: v["rows_total"] - v["rows_matched"] for k, v in short.items()}
        if short:
            violations.append(f"state profile does not cover every row: unmatched rows by subgroup {rep['state_profile_rows_unmatched']}")
    rep["ok"], rep["violations"] = (len(violations) == 0), violations
    return rep


def compare_main_slice(candidate: pd.DataFrame, reference: pd.DataFrame, *, id_col: Optional[str] = None,
                       atol: float = 1e-12, ignore: Sequence[str] = ()) -> Dict[str, Any]:
    """Acceptance check of a five-subgroup release (0.2.6): its (ALL, ALL) rows must be the rows of the accepted release.

    ``candidate`` and ``reference`` are two seed-level tables or two seed-aggregated tables. The rows of ``candidate`` on the (ALL, ALL)
    slice are matched to ``reference`` on the row identifier (meta_obs_id or meta_obs_id_agg); every column the two tables share is
    compared (numeric: absolute difference, NaN equal to NaN; other: equality). Provenance columns that name the release or the builder
    are skipped. Returns counts, the largest numeric difference and the columns that differ.
    """
    id_col = id_col or ("meta_obs_id" if "meta_obs_id" in candidate.columns and "meta_obs_id" in reference.columns else "meta_obs_id_agg")
    skip = set(ignore) | {"meta_release_id", "builder_version", "meta_schema_version", "null_reason_map"}
    cand = _slice(candidate, "ALL", "ALL").set_index(id_col)
    ref = _slice(reference, "ALL", "ALL").set_index(id_col)
    rep: Dict[str, Any] = {"id_column": id_col, "rows_candidate_all_slice": int(len(cand)), "rows_reference_all_slice": int(len(ref)),
                           "rows_only_in_candidate": int(len(cand.index.difference(ref.index))),
                           "rows_only_in_reference": int(len(ref.index.difference(cand.index))),
                           "columns_only_in_candidate": sorted(set(cand.columns) - set(ref.columns)),
                           "columns_only_in_reference": sorted(set(ref.columns) - set(cand.columns))}
    common = cand.index.intersection(ref.index)
    cand, ref = cand.loc[common], ref.loc[common]
    differing, worst = {}, 0.0
    for c in [c for c in ref.columns if c in cand.columns and c not in skip]:
        a, b = cand[c], ref[c]
        if pd.api.types.is_numeric_dtype(a) and pd.api.types.is_numeric_dtype(b) and not pd.api.types.is_bool_dtype(a):
            x, y = a.to_numpy(dtype=float), b.to_numpy(dtype=float)
            nan_mismatch = int((np.isnan(x) != np.isnan(y)).sum())
            d = np.abs(x - y)
            m = float(np.nanmax(d)) if np.isfinite(d).any() else 0.0
            worst = max(worst, m)
            if nan_mismatch or m > atol:
                differing[c] = {"max_abs_diff": m, "null_mismatch_rows": nan_mismatch}
        else:
            ne = ~((a.astype(str) == b.astype(str)) | (a.isna() & b.isna()))
            if ne.any():
                differing[c] = {"rows_different": int(ne.sum())}
    rep.update({"columns_compared": int(len([c for c in ref.columns if c in cand.columns and c not in skip])), "max_abs_diff": worst,
                "columns_differing": differing, "atol": atol})
    rep["ok"] = (rep["rows_only_in_candidate"] == 0 and rep["rows_only_in_reference"] == 0 and not differing
                 and not rep["columns_only_in_reference"])
    return rep

