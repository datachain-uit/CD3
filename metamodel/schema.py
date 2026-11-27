# -*- coding: utf-8 -*-
"""Column roles, blocks and the meta-level leakage checks MQ01 / MQ06 / MQ10 (Meta-Dataset-Report §4.3, §10.12).

The role of a column decides whether it may enter a meta-learner. Roles are assigned from the registered naming
conventions (§4.2) and from explicit lists; anything unrecognised is ``UNASSIGNED`` and is never an input.
"""
from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

import pandas as pd

from . import contracts as C

INPUT_ROLES: Tuple[str, ...] = ("X_STATE", "X_CONTEXT", "X_VAL")
NEVER_INPUT_ROLES: Tuple[str, ...] = ("KEY", "PROV", "X_RESTRICTED", "TARGET", "COST", "DIAG", "DERIVED", "QA", "UNASSIGNED")

KEY_COLUMNS: Set[str] = set(C.KEY_FIELDS) | {
    "meta_obs_id", "rec_group_id", "run_group_id", "meta_cv_group", "phase_index", "q", "window_index",
    "is_primary_cohort", "population_varies_by_phase", "is_primary_regime", "window_test_start_utc", "window_test_end_utc",
}
PROV_COLUMNS: Set[str] = {
    "run_id_after", "attempt_id_after", "run_id_before", "run_id_imp_only", "run_id_ref", "meta_release_id",
    "meta_schema_version", "hparam_config_id", "data_release_id", "split_version", "phase_version",
    "feature_dictionary_version", "pipeline_version", "metric_def_version", "dq_def_version", "code_commit_after",
    "env_id_after", "acctempo_alpha", "acctempo_beta", "acctempo_def_version", "acctempo_eps_floor",
    "s_san_formula_version", "s_eps_floor", "delta_n_boot", "delta_boot_unit", "imputer_params_hash",
    "balancer_params_hash", "fit_scope", "v0_fill_rule", "synthetic_phase_rule", "synthetic_mask_rule",
    "energy_boundary", "energy_measurement_type", "telemetry_missing_rate", "carbon_intensity_g_per_kwh",
    "ci_source_version", "pue", "rec_rule_version", "rec_objective", "rec_eps", "rec_energy_measured_types", "utility_lambda_grid", "cost_basis",
    "s_leak_probe_n_fit", "s_leak_probe_n_eval", "s_leak_probe_eval_split", "execution_backend", "receipt_id",
    "built_at_utc", "builder_version", "source_table_hashes", "model_revision",
    # pipeline reference provenance: the N10 definition used (imp(a) = a) and the pre-N10 registry literal
    "pipeline_before_ref", "pipeline_imputer_only_ref", "pipeline_imputer_only_ref_registry_literal", "imputer_only_pipeline",
}
QA_COLUMNS: Set[str] = {"row_status", "row_status_agg", "run_status", "run_status_after", "run_status_before", "null_reason_map", "n_eval_samples",
                        "ev_n_classes_present", "small_subgroup_flag", "small_support_flag", "cost_shared_across_phases",
                        "n_cells_imputed_in_unavailable", "n_cells_imputed_in_structural"}
CONTEXT_MODEL_COLUMNS: Set[str] = {
    "model_tier", "model_family", "model_name", "variant_role", "is_pretrained", "pretrained_source", "finetune_mode",
    "param_count_total", "param_count_trainable", "log10_param_count", "uses_mask_channels", "uses_delta_t",
    "max_seq_len", "patch_len", "patch_stride", "loss_name", "class_weighting", "lr", "batch_size", "max_epochs",
}
DIAG_MODEL_COLUMNS: Set[str] = {"epochs_trained", "selected_epoch", "val_selection_score", "early_stopped"}
CONTEXT_PIPELINE_COLUMNS: Set[str] = {"pipeline_id", "pipeline_name", "imputer", "balancer", "imputer_family",
                                      "balancer_family", "is_no_intervention", "has_imputation", "has_balancing",
                                      "is_sensitivity", "sampling_strategy_id"}
CONTEXT_KEY_ENCODINGS: Set[str] = {"task", "phase_index", "q", "subgroup_axis", "subgroup_value", "eval_split", "feature_regime",
                                   "model_name", "pipeline_id"}   # keys that Table 17 allows as X_CONTEXT encodings
DIAG_PIPELINE_COLUMNS: Set[str] = {"trpool_n_real", "trpool_n_synth", "synthetic_ratio", "expansion_ratio",
                                   "trpool_post_imbalance_ratio", "trpool_post_class_entropy_norm", "trpool_post_fallback_rate"}

RESTRICTED_PREFIXES: Tuple[str, ...] = ("ev_class_count_", "ev_class_prop_", "ev_imbalance_ratio", "ev_minority_ratio",
                                        "ev_class_entropy", "ev_n_classes_present", "label_drift_tr_ev")
STATE_PREFIXES: Tuple[str, ...] = ("tr_", "trpool_", "ev_", "drift_", "label_drift_window", "days_train_end_to_test_start",
                                   "embargo_gap_days", "train_history_span_days", "has_prev_phase", "n_classes")
COST_PREFIXES: Tuple[str, ...] = ("time_", "peak_", "energy_", "co2e_", "cost_usd", "samples_per_s", "j_per_", "kwh_per_", "gco2e_per_", "macro_f1_per_kwh")
DERIVED_PREFIXES: Tuple[str, ...] = ("rank_", "regret", "is_best", "within_eps_best", "recommended", "beats_v0", "harms_v0",
                                     "delta_ci_excludes_zero", "utility_l", "is_pareto", "best_delta_in_group", "best_pipeline_in_group",
                                     "n_candidates", "relevance_grade", "cost_ratio_used", "cost_basis", "rec_objective", "rec_eps", "rec_energy_measured_types",
                                     "utility_lambda_grid", "n_seeds_", "meta_obs_id_agg", "rec_group_id_agg", "planned_seeds")
TARGET_SUFFIXES: Tuple[str, ...] = ("_before", "_after", "_delta", "_imp_only", "_delta_imp", "_delta_bal", "_ref", "_delta_ref",
                                    "_delta_ci_low", "_delta_ci_high", "_delta_p_boot", "_after_ci_low", "_after_ci_high",
                                    "_log_delta_perf_part", "_log_delta_san_part")
SAN_STEMS: Tuple[str, ...] = C.SAN_COMPONENTS + ("s_leak_probe_auc",)
AGG_SUFFIXES: Tuple[str, ...] = ("_mean", "_sd", "_median", "_min", "_max", "_p90", "_p95", "_n_positive_seeds", "_sign_consistent")

_METRIC_STEMS = tuple(sorted(set(C.ALL_PAIRED_METRICS) | set(C.CORE_METRICS), key=len, reverse=True))
_PER_CLASS_RE = re.compile(r"^(c[012])_(precision|recall|specificity|f1|gmean|ap|support|predicted_count)")


def _strip_agg(name: str) -> str:
    for suf in AGG_SUFFIXES:
        if name.endswith(suf):
            return name[: -len(suf)]
    return name


def _metric_stem(name: str) -> Optional[str]:
    for stem in _METRIC_STEMS:
        if name == stem or name.startswith(stem + "_"):
            return stem
    return None


def role_of(column: str) -> Tuple[str, str]:
    """Return (block, role) for one column name."""
    c = column
    base = _strip_agg(c)
    if c in KEY_COLUMNS:
        return "K", "KEY"
    if c in PROV_COLUMNS:
        return "K", "PROV"
    if c in QA_COLUMNS or c.startswith("qa_"):
        return "QA", "QA"
    if base.startswith("val_"):
        return "Y", "X_VAL"
    if c in CONTEXT_PIPELINE_COLUMNS or c.startswith(("a_imp_", "a_bal_")):
        return "Z_A", "X_CONTEXT"
    if c in CONTEXT_MODEL_COLUMNS:
        return "Z_M", "X_CONTEXT"
    if c in DIAG_MODEL_COLUMNS:
        return "Z_M", "DIAG"
    if base in DIAG_PIPELINE_COLUMNS or base.startswith("trpool_post_"):
        return "Z_A", "DIAG"
    if base.startswith(DERIVED_PREFIXES):
        return "R", "DERIVED"
    if base.startswith(COST_PREFIXES):
        return "C", "COST"
    if base.startswith(("obs_vs_imp_", "real_vs_synth_", "synth_", "ev_post_", "consistency_rate_before", "consistency_rate_after",
                        "consistency_rate_delta", "completeness_grain_mean_before", "completeness_grain_mean_after",
                        "completeness_grain_mean_delta")):
        return "Y_DQ", "DIAG"
    if _PER_CLASS_RE.match(base):
        return "Y", "TARGET"
    for stem in SAN_STEMS:
        if base == stem or base.startswith(stem + "_"):
            return "Y_DQ", "DIAG"      # health components measured on the evaluated slice: target material, never input (MQ10)
    stem = _metric_stem(base)
    if stem is not None:
        if base == stem or any(base.endswith(s) for s in TARGET_SUFFIXES) or base.startswith(stem + "_v2"):
            return "Y", "TARGET"
    if base.startswith(RESTRICTED_PREFIXES):
        return "Z_D", "X_RESTRICTED"
    if base.startswith(STATE_PREFIXES) or base in {"ev_train_overlap_share", "ev_behavior_growth_rate", "ev_attrition_prev",
                                                   "ev_delta_n_enrollments_prev", "ev_mean_observed_fraction",
                                                   "ev_median_cutoff_days_since_start"}:
        block = "Z_T" if (base.startswith(("drift_", "label_drift_window")) or base.endswith(("_prev", "_delta_prev", "_delta_p1"))
                          or base in {"ev_behavior_growth_rate", "ev_attrition_prev", "ev_delta_n_enrollments_prev",
                                      "days_train_end_to_test_start", "embargo_gap_days", "train_history_span_days",
                                      "ev_train_overlap_share", "has_prev_phase"}) else ("Z_DQ" if _is_dq(base) else "Z_D")
        return block, "X_STATE"
    return "UNASSIGNED", "UNASSIGNED"


_DQ_MARKERS = ("n_cells_", "completeness", "missing", "unavailable", "structural", "sparsity", "zero_activity", "inactive",
               "incomplete_history", "skewness", "kurtosis", "outlier", "low_variance", "high_corr", "mean_abs_corr",
               "duplicate", "orphan", "consistency", "unseen_category", "event_sparsity", "mean_events")


def _is_dq(base: str) -> bool:
    b = base[3:] if base.startswith(("tr_", "ev_")) else base
    return any(m in b for m in _DQ_MARKERS)


def build_column_dictionary(df: pd.DataFrame) -> pd.DataFrame:
    """meta_column_dictionary (Table 18) for the columns of a frame: one role per column."""
    rows = []
    for c in df.columns:
        block, role = role_of(c)
        rows.append({"column_name": c, "block": block, "role": role, "dtype": str(df[c].dtype),
                     "nullable": bool(df[c].isna().any()) if len(df) else True})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------------------------
# Meta-level leakage checks on a chosen input column list
# ---------------------------------------------------------------------------------------------


def mq01_input_roles(input_columns: Iterable[str], allow_context_keys: bool = True) -> Tuple[bool, List[str]]:
    """MQ01: no X_RESTRICTED / DIAG / DERIVED / QA / PROV / identifier column among the inputs."""
    bad = []
    for c in input_columns:
        block, role = role_of(c)
        if role in INPUT_ROLES:
            continue
        if allow_context_keys and c in CONTEXT_KEY_ENCODINGS:
            continue
        bad.append(f"{c}:{role}")
    return (len(bad) == 0), bad


def mq06_scenario_columns(input_columns: Iterable[str], scenario: str) -> Tuple[bool, List[str]]:
    """MQ06: COLD has no val_* column; WARM only val_*_before (and val_s_*_before); FULL may use after/delta too."""
    bad = []
    for c in input_columns:
        base = _strip_agg(c)
        if not base.startswith("val_"):
            continue
        if scenario == "COLD":
            bad.append(c)
        elif scenario == "WARM" and not base.endswith("_before"):
            bad.append(c)
    return (len(bad) == 0), bad


def mq10_no_target_components(input_columns: Iterable[str]) -> Tuple[bool, List[str]]:
    """MQ10: no S_perf / S_san+ / component / AccTEMPO column measured on the evaluated slice among the inputs."""
    bad = []
    for c in input_columns:
        base = _strip_agg(c)
        if base.startswith("val_"):
            continue
        if base.startswith(("s_perf", "s_san_plus", "acctempo")) or any(base == s or base.startswith(s + "_") for s in C.SAN_COMPONENTS_V1 + ("s_cal",)):
            bad.append(c)
    return (len(bad) == 0), bad


def mq07_no_task_feature(input_columns: Iterable[str]) -> Tuple[bool, List[str]]:
    bad = [c for c in input_columns if c == "task" or c.startswith("task_")]
    return (len(bad) == 0), bad
