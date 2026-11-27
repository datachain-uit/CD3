# -*- coding: utf-8 -*-
"""Registered constants of the meta-dataset and the meta-model plan.

Every value here mirrors a registered source and names it. When ``tempo_fix/examples/registries_v1.6`` is
available, :func:`load_registry_overrides` re-reads the pipeline grid, the recommendation rule and the
AccTEMPO definition from the JSON exports so that the code cannot drift from the registry silently.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------------------------
# Canonical hashing (identical to tempo_fix/seeds.py: sorted keys, no whitespace, non-ASCII kept)
# ---------------------------------------------------------------------------------------------


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def sha256_of(obj: Any) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------------------------
# Keys and axes (Meta-Dataset-Report §3.1, Table 13; tempo_fix/l3_pilot.py KEY_FIELDS)
# ---------------------------------------------------------------------------------------------
KEY_FIELDS: Tuple[str, ...] = (
    "task", "label_rule_version", "label_threshold_set", "feature_regime", "window_id", "seed", "phase_id",
    "cohort", "eval_split", "subgroup_axis", "subgroup_value", "model_name", "pipeline_id",
)
SITUATION_FIELDS: Tuple[str, ...] = tuple(k for k in KEY_FIELDS if k != "pipeline_id")
STATE_SLICE_FIELDS: Tuple[str, ...] = (  # Z_D / Z_DQ / Z_T repeat on every row of one state slice (§3.4)
    "task", "feature_regime", "window_id", "phase_id", "cohort", "eval_split", "subgroup_axis", "subgroup_value",
)
RUN_FIELDS: Tuple[str, ...] = ("task", "feature_regime", "window_id", "seed", "model_name", "pipeline_id")

WINDOWS: Tuple[str, ...] = ("W1", "W2", "W3")
WINDOW_INDEX: Dict[str, int] = {"W1": 1, "W2": 2, "W3": 3}
PHASES: Tuple[str, ...] = ("P1", "P2", "P3", "P4")
PHASE_INDEX: Dict[str, Tuple[int, float]] = {"P1": (1, 0.25), "P2": (2, 0.50), "P3": (3, 0.75), "P4": (4, 0.90)}
EVAL_SPLITS: Tuple[str, ...] = ("VALIDATION", "TEST")
MANDATORY_SUBGROUPS: Tuple[Tuple[str, str], ...] = (
    ("ALL", "ALL"), ("LEARNER", "SEEN"), ("LEARNER", "UNSEEN"), ("COURSE", "SEEN"), ("COURSE", "UNSEEN"),
)
# 0.2.6: on each of these axes SEEN and UNSEEN partition the (ALL, ALL) slice of the same run, split and phase (§2.5, Table 10)
SUBGROUP_PARTITION_AXES: Tuple[str, ...] = ("LEARNER", "COURSE")
MAIN_REPORT_SUBGROUP: Tuple[str, str] = ("ALL", "ALL")   # §10.3, Table 42: main report slice
# 0.3.0: options of the full-design run. Registered primary set (author decisions of 2026-11-21, registry decisions 52-54):
# training on the five mandatory subgroups (Table 42), one model per task and fold (§10.10, decision 52 (a)), baselines and inner
# selection on the matched slice (decision 53 (a)), one Holm family over every test row of mm_hypotheses (decision 54 (b)).
SECONDARY_SUBGROUPS: Tuple[Tuple[str, str], ...] = tuple(s for s in MANDATORY_SUBGROUPS if s != MAIN_REPORT_SUBGROUP)
E1_SCOPE_POOLED, E1_SCOPE_PER_TASK = "POOLED", "PER_TASK"
E1_SCOPES: Tuple[str, ...] = (E1_SCOPE_POOLED, E1_SCOPE_PER_TASK)
PER_TASK_PROTOCOLS: Tuple[str, ...] = ("E1-A", "E1-B", "E3")   # trained once per task under PER_TASK; E2 is cross-task by definition
BASELINE_SCOPE_MATCHED, BASELINE_SCOPE_ALL_ROWS = "MATCHED_SLICE", "ALL_ROWS"
BASELINE_SCOPES: Tuple[str, ...] = (BASELINE_SCOPE_MATCHED, BASELINE_SCOPE_ALL_ROWS)
HYP_ROWS_PRIMARY_ONLY, HYP_ROWS_REGISTERED = "PRIMARY_ONLY", "REGISTERED"
HYP_ROW_SETS: Tuple[str, ...] = (HYP_ROWS_PRIMARY_ONLY, HYP_ROWS_REGISTERED)
SMALL_SUBGROUP_KEEP, SMALL_SUBGROUP_DROP = "KEEP", "DROP_FROM_TRAINING"
SMALL_SUBGROUP_POLICIES: Tuple[str, ...] = (SMALL_SUBGROUP_KEEP, SMALL_SUBGROUP_DROP)
SMALL_SUBGROUP_FLAG = "small_subgroup_flag"       # facts column (n < 30 or a class support < 5), carried to the seed-aggregated table
REPLICATION_PROTOCOL = "E1-A"                      # §10.8: E1-B is the primary fold, E1-A the replication
POOLED_PROTOCOL_LABEL = "E1-A+E1-B"                # §10.8: the two tasks and the two folds together
ROLE_PRIMARY, ROLE_PER_TASK, ROLE_REPLICATION, ROLE_POOLED_2FOLD, ROLE_TRANSFER = (
    "PRIMARY", "PER_TASK", "REPLICATION_E1A", "POOLED_2FOLD", "TRANSFER_E2")
MASTER_SEEDS: Tuple[int, ...] = (42, 43, 44)          # registries EXPERIMENT_SEEDS
COHORT_FIXED = "FIXED"

# ---------------------------------------------------------------------------------------------
# Pipelines V0–V16 (registries build_pipeline_registry; Meta-Dataset-Report Table 7; confirmed against
# imputation_core/meta_storage.PIPELINE_ID and augmentation_core/storage.BALANCE_PIPELINES, CD3 @ 5b14052)
# ---------------------------------------------------------------------------------------------
IMPUTERS: Tuple[Tuple[str, str], ...] = (("NONE", "V0"), ("MEDIAN", "V1"), ("MEAN", "V5"), ("EXTRATREES", "V9"), ("MICE", "V13"))
BALANCERS: Tuple[str, ...] = ("NONE", "CDSMOTE", "SASMOTE", "RADIUS_SMOTE")
IMPUTER_FAMILY: Dict[str, str] = {"NONE": "NONE", "MEDIAN": "UNIVARIATE", "MEAN": "UNIVARIATE",
                                  "EXTRATREES": "MULTIVARIATE_MODEL", "MICE": "MULTIVARIATE_MODEL"}


def build_pipelines() -> List[Dict[str, Any]]:
    rows, vid = [], 0
    for imp, imp_only in IMPUTERS:
        for bal in BALANCERS:
            if imp == "NONE" and bal != "NONE":
                continue
            pid = f"V{vid}"
            rows.append({
                "pipeline_id": pid, "imputer": imp, "balancer": bal,
                "imputer_family": IMPUTER_FAMILY[imp], "balancer_family": "NONE" if bal == "NONE" else "SMOTE_VARIANT",
                "is_no_intervention": int(pid == "V0"), "has_imputation": int(imp != "NONE"), "has_balancing": int(bal != "NONE"),
                # N10 (author decision 2026-10-24): imp(a) = a for a pipeline without balancer; registry literal kept below
                "before_ref": "V0", "imputer_only_ref": pid if bal == "NONE" else imp_only,
                "imputer_only_ref_registry_literal": "V0" if bal == "NONE" else imp_only,
                "is_sensitivity": int(bal == "RADIUS_SMOTE"),   # registered fallback warning > 0.50 (GRID_POLICY)
            })
            vid += 1
    assert vid == 17, vid
    return rows


PIPELINES: List[Dict[str, Any]] = build_pipelines()
PIPELINE_IDS: Tuple[str, ...] = tuple(p["pipeline_id"] for p in PIPELINES)
PIPELINE_BY_ID: Dict[str, Dict[str, Any]] = {p["pipeline_id"]: p for p in PIPELINES}
# N10 resolved by the author on 2026-10-24: the imputer-only reference of a pipeline without balancer is the pipeline
# itself (imp(a) = a), so delta_imp = delta and delta_bal = 0 for V1/V5/V9/V13 and imp(V0) = V0. Table 14 of the
# Meta-Dataset-Report (v1.9) and the reference registry tempo_fix/registries.py (rev 2026-10-24) are corrected; the
# execution registries of the repository (CQ/registries.py, LO/registries.py) still read V0 for these pipelines until
# the team applies tempo_fix/patches/2026-10-24_imputer_only_ref_N10.patch. The loader accepts the old literal and
# reports it in the manifest (see ``load_registry_overrides``).
IMPUTER_ONLY_REF: Dict[str, str] = {p["pipeline_id"]: p["imputer_only_ref"] for p in PIPELINES}
IMPUTER_ONLY_REF_REGISTRY: Dict[str, str] = {p["pipeline_id"]: p["imputer_only_ref_registry_literal"] for p in PIPELINES}  # pre-N10 literal
PIPELINE_OF: Dict[Tuple[str, str], str] = {(p["imputer"], p["balancer"]): p["pipeline_id"] for p in PIPELINES}

# ---------------------------------------------------------------------------------------------
# Metrics (Meta-Dataset-Report §4.2 Table 16; metrics_core/evaluation.py; registries METRIC_DEF v1.2)
# ---------------------------------------------------------------------------------------------
CORE_METRICS: Tuple[str, ...] = ("acctempo_m3", "s_perf", "macro_f1", "balanced_acc", "mcc", "kappa", "pr_auc_macro", "gmean")
EXT_METRICS: Tuple[str, ...] = ("accuracy", "weighted_f1", "roc_auc_macro_ovr", "log_loss", "brier", "ece")
SAN_COMPONENTS_V1: Tuple[str, ...] = ("s_nan", "s_maj_jsd", "s_ent", "s_drift", "s_eff", "s_leak")
SAN_COMPONENTS: Tuple[str, ...] = SAN_COMPONENTS_V1 + ("s_cal", "s_san_plus", "s_san_plus_v2")
COMPOSITES: Tuple[str, ...] = ("acctempo_m3", "acctempo_m3_cal")   # acctempo_m3_cal = AccTEMPO_M3^(cal) (D-18, 2026-10-24)
CLASSES: Tuple[str, ...] = ("c0", "c1", "c2")
PER_CLASS_METRICS: Tuple[str, ...] = ("precision", "recall", "specificity", "f1", "gmean", "ap")
ALL_PAIRED_METRICS: Tuple[str, ...] = tuple(dict.fromkeys(CORE_METRICS + ("acctempo_m3_cal",) + EXT_METRICS))

# column aliases: names written by model/metrics.py and the R3/R4 exports -> registered names
METRIC_ALIASES: Dict[str, str] = {
    "f1_macro": "macro_f1", "balanced_accuracy": "balanced_acc", "cohen_kappa": "kappa", "gmean_recall": "gmean",
    "multiclass_nll": "log_loss", "multiclass_brier": "brier", "top_label_ece_15": "ece", "f1_weighted": "weighted_f1",
    "acctempo_m4": "acctempo_m3_cal",   # the exporter's M4 is the calibration composite; the paper writes M3^(cal)
    "n_rows": "n_eval_samples",
}

# AccTEMPO definition (registries ACCTEMPO_DEF acctempo_m3_v1.1, LOCKED 2026-10-05)
ACCTEMPO_ALPHA, ACCTEMPO_BETA, EPS_FLOOR = 0.6, 0.4, 1e-3
PRIMARY_S_SAN_VERSION = "v1"

# Recommendation rule (registries REC_RULE rec_v1.1) and the paper's objectives after D-18 (2026-10-24)
REC_EPS = 0.005
LAMBDA_GRID: Tuple[float, ...] = (0.0, 0.01, 0.02, 0.05)
OBJECTIVES: Dict[str, str] = {
    # objective id -> target column stem in the meta-dataset
    "META_PRIMARY_M3_V1": "acctempo_m3",          # pre-registered primary of the meta-dataset (REC_RULE TEST_ACCTEMPO_M3_DELTA)
    "PAPER_COMPOSITE_CAL": "acctempo_m3_cal",     # paper composite objective (D-18 (b))
    "PAPER_PERF_AXIS": "s_perf",                  # paper performance axis (D-18 (c))
    "SECONDARY_MACRO_F1": "macro_f1",             # REC_RULE secondary objective (RQ7)
}
DEFAULT_OBJECTIVE = "PAPER_COMPOSITE_CAL"

# Cost basis (registries REC_RULE ENERGY_IF_MEASURED_ELSE_TIME). NVML power-sampling estimates are treated as
# MEASURED only when decision D-15 is ratified by the author; the default follows REC_RULE strictly.
COST_ENERGY_COL, COST_TIME_COL = "energy_gpu_run_kwh", "time_run_total_s"
ENERGY_MEASURED_TYPES_STRICT: Tuple[str, ...] = ("MEASURED", "NVML_COUNTER")
ENERGY_MEASURED_TYPES_WITH_ESTIMATE: Tuple[str, ...] = ENERGY_MEASURED_TYPES_STRICT + ("NVML_POWER_SAMPLING_ESTIMATE", "ESTIMATED")

# Support flags (METRIC_DEF v1.2)
SMALL_SUPPORT_N = 400
SMALL_SUBGROUP_N, SMALL_SUBGROUP_CLASS_N = 30, 5

# Model tiers (registries MODEL_REGISTRY, rev 2026-11-06: F3 = MANTIS_V2, EXPLORATORY)
MODEL_TIER: Dict[str, str] = {
    "RNN": "F1_RECURRENT", "LSTM": "F1_RECURRENT", "GRU": "F1_RECURRENT", "BILSTM": "F1_RECURRENT",
    "PATCHTST": "F2_TS_TRANSFORMER", "MANTIS_V2": "F3_TS_FOUNDATION",
    # retired 2026-11-06 (registries decision 37); kept so that historical smoke manifests still map
    "MOMENT_SMALL": "F3_TS_FOUNDATION", "MOMENT_BASE": "F3_TS_FOUNDATION",
    "CQ_PARTIAL_TRIAD": "F0_REFERENCE", "LO_HEURISTIC_PROGRESS_GRADE": "F0_REFERENCE",
}
MODEL_FAMILY: Dict[str, str] = {
    "RNN": "RECURRENT", "LSTM": "RECURRENT", "GRU": "RECURRENT", "BILSTM": "RECURRENT",
    "PATCHTST": "TRANSFORMER", "MANTIS_V2": "FOUNDATION",
    "MOMENT_SMALL": "FOUNDATION", "MOMENT_BASE": "FOUNDATION",   # retired 2026-11-06 (decision 37)
}
F0_REFERENCE_MODELS: Tuple[str, ...] = ("CQ_PARTIAL_TRIAD", "LO_HEURISTIC_PROGRESS_GRADE")

# NULL reason codes and row status (Meta-Dataset-Report §7.2–7.3)
NULL_REASONS: Tuple[str, ...] = ("NOT_APPLICABLE", "NO_PREVIOUS_PHASE", "NO_PREVIOUS_WINDOW", "CLASS_ABSENT", "NO_PREDICTION",
                                 "ZERO_DIVISION", "RUN_FAILED", "BASELINE_MISSING", "TELEMETRY_UNAVAILABLE", "NOT_COMPUTED")
ROW_STATUS: Tuple[str, ...] = ("COMPLETE", "MISSING_BASELINE", "RUN_FAILED", "INFEASIBLE", "PARTIAL")

# Meta-model plan constants (Meta-Dataset-Report §10)
FEATURE_SETS: Tuple[str, ...] = ("FS0", "FS1", "FS2", "FS3", "FS4", "FS5")
SCENARIO_OF_FS: Dict[str, str] = {"FS0": "COLD", "FS1": "COLD", "FS2": "COLD", "FS3": "COLD", "FS4": "WARM", "FS5": "FULL"}
SCENARIOS: Tuple[str, ...] = ("COLD", "WARM", "FULL")      # plan codes S1 / S2 / S3 (renamed, 01_notation decision 2)
PROTOCOLS: Tuple[str, ...] = ("E1-A", "E1-B", "E2", "E3", "W0_LOCKED")
PRIMARY_PROTOCOL, PRIMARY_FEATURE_SET, PRIMARY_LEARNER, MAIN_COMPARATOR = "E1-B", "FS3", "L3", "B3"
CLUSTER_FIELDS: Tuple[str, ...] = ("task", "window_id", "model_name", "phase_id")   # bootstrap unit (§10.8)
BOOTSTRAP_B = 2000
ALPHA_STAT = 0.05
LEARNER_SEEDS: Tuple[int, ...] = (0, 1, 2, 3, 4)
ALPHA_BETA_GRID: Tuple[Tuple[float, float], ...] = ((0.5, 0.5), (0.6, 0.4), (0.7, 0.3), (0.9, 0.1))
EPS_GRID: Tuple[float, ...] = (0.002, 0.005, 0.01)
GRADED_RELEVANCE: Dict[str, int] = {"WITHIN_EPS_BEST": 3, "BENEFIT": 2, "NEUTRAL": 1, "HARM": 0}

# TEMPO-DQ diagnostic plane (50-IPM-Publish Table 4): x = S_san+, y = S_perf; x0 = 0.75, y0 = 0.70
TEMPO_DQ_X0, TEMPO_DQ_Y0 = 0.75, 0.70
# B7 = TEMPO-DQ diagnosis table as a deterministic warm-start policy (contract since 2026-10-24, D-S1-3):
# Q1 -> V0, Q2 -> V0 (no anti-leakage action in the intervention space), Q3/Q4 -> B7_DEFAULT_REPAIR.
B7_STATUS = "IN_CONTRACT_2026-10-24"
B7_DEFAULT_REPAIR = "V2"           # MEDIAN + CDSMOTE; a registered constant of the frozen configuration, configurable

# Pre-registered hypotheses (Meta-Dataset-Report Table 50, H1-H7) plus H8 (mechanism decomposition, contract 2026-10-24)
HYPOTHESES: Tuple[str, ...] = ("H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8")
# Objective each hypothesis is measured on (author confirmation 2026-10-24; to be registered as METRIC_DEF v1.3).
# H1-H6: effects in AccTEMPO_M3^(cal); H7: composite objective against macro-F1; H8: mechanism shares of the chosen
# objective; every test is repeated with META_PRIMARY_M3_V1 as sensitivity.
HYPOTHESIS_OBJECTIVES: Dict[str, str] = {h: "PAPER_COMPOSITE_CAL" for h in ("H1", "H2", "H3", "H4", "H5", "H6", "H8")}
HYPOTHESIS_OBJECTIVES["H7"] = "PAPER_COMPOSITE_CAL vs SECONDARY_MACRO_F1"
SENSITIVITY_OBJECTIVE = "META_PRIMARY_M3_V1"
H3_NONINFERIORITY_MARGIN = 0.05
H6_LAMBDA = 0.02
H8_STATE_FEATURE = "tr_missing_rate"      # Z_DQ column of the S0 profile (Meta-Dataset-Report Table 21)
# Author decision 2026-11-13 (Q-34 (a), registry decision 45), taken before any three-seed run: the phase part is THE test of H8
# (Spearman(imp_share, phase_index) < 0); the state-feature part is reported descriptively and is no longer a test, because
# tr_missing_rate rises monotonically with the phase in every task x window of the S0 profile v4, so the two parts registered
# on 2026-10-24 exclude each other; a verdict requires at least H8_MIN_CLUSTERS clusters.
H8_MIN_CLUSTERS = 10
H8_RESTATED_ON = "2026-11-13"


# ---------------------------------------------------------------------------------------------
# Registry overrides from the JSON exports of tempo_fix (optional, recommended)
# ---------------------------------------------------------------------------------------------


def load_registry_overrides(registry_dir: Optional[Path]) -> Dict[str, Any]:
    """Read pipeline_registry / rec_rule / acctempo_def exports and verify this module against them.

    Returns a dict with the parsed exports; raises ``ValueError`` when the exported pipeline grid or the
    recommendation constants disagree with the constants above (the module is then out of date).
    """
    if registry_dir is None:
        return {}
    registry_dir = Path(registry_dir)
    out: Dict[str, Any] = {}
    pr = registry_dir / "pipeline_registry.json"
    if pr.exists():
        rows = json.loads(pr.read_text(encoding="utf-8"))
        rows = rows if isinstance(rows, list) else rows.get("pipeline_registry", rows)
        exported = {r["pipeline_id"]: (r["imputer"], r["balancer"]) for r in rows}
        local = {p["pipeline_id"]: (p["imputer"], p["balancer"]) for p in PIPELINES}
        if exported != local:
            diff = {k: (local.get(k), exported.get(k)) for k in sorted(set(local) | set(exported)) if local.get(k) != exported.get(k)}
            raise ValueError(f"pipeline grid differs from the registry export: {diff}")
        exp_ref = {r["pipeline_id"]: r.get("imputer_only_ref") for r in rows}
        if exp_ref == IMPUTER_ONLY_REF:
            out["imputer_only_ref_status"] = "N10_APPLIED"
        elif exp_ref == IMPUTER_ONLY_REF_REGISTRY:
            # registry export still carries the pre-N10 literal (V1/V5/V9/V13 -> V0); the decomposition uses imp(a) = a
            out["imputer_only_ref_status"] = "PRE_N10_LITERAL_IN_REGISTRY (decomposition uses imp(a) = a per author decision 2026-10-24; registry to be corrected)"
        else:
            diff = {k: (IMPUTER_ONLY_REF.get(k), exp_ref.get(k)) for k in sorted(set(exp_ref) | set(IMPUTER_ONLY_REF)) if IMPUTER_ONLY_REF.get(k) != exp_ref.get(k)}
            raise ValueError(f"imputer_only_ref differs from both the N10 definition and the pre-N10 literal: {diff}")
        out["pipeline_registry"] = rows
    rr = registry_dir / "rec_rule.json"
    if rr.exists():
        rec = json.loads(rr.read_text(encoding="utf-8"))
        if abs(float(rec.get("rec_eps", REC_EPS)) - REC_EPS) > 1e-12 or tuple(rec.get("utility_lambda_grid", LAMBDA_GRID)) != LAMBDA_GRID:
            raise ValueError(f"REC_RULE export differs: {rec}")
        out["rec_rule"] = rec
    ad = registry_dir / "acctempo_def.json"
    if ad.exists():
        acc = json.loads(ad.read_text(encoding="utf-8"))
        if (abs(float(acc.get("alpha", ACCTEMPO_ALPHA)) - ACCTEMPO_ALPHA) > 1e-12
                or abs(float(acc.get("beta", ACCTEMPO_BETA)) - ACCTEMPO_BETA) > 1e-12
                or abs(float(acc.get("acctempo_eps_floor", EPS_FLOOR)) - EPS_FLOOR) > 1e-15):
            raise ValueError(f"ACCTEMPO_DEF export differs: {acc}")
        out["acctempo_def"] = acc
    return out


def acctempo(s_perf, s_san, alpha: float = ACCTEMPO_ALPHA, beta: float = ACCTEMPO_BETA, floor: float = EPS_FLOOR):
    """AccTEMPO composite with the registered floor on both factors (array-safe)."""
    import numpy as np
    sp = np.clip(np.asarray(s_perf, dtype=float), floor, 1.0)
    ss = np.clip(np.asarray(s_san, dtype=float), floor, 1.0)
    return sp ** alpha * ss ** beta

# 0.3.1 (2026-11-26): negative control MQ08. The permutation of the state block keeps the dtype of every column; the assignment of
# metamodel <= 0.3.0 (one mixed-type block, numeric state columns turned into object columns and one-hot encoded) is kept as a replay
# mode only (experiment.permute_state_across_situations). Registry: POST_MATERIALIZE_CHECKS[47]['correction_2026-11-26'], decision 59.
NEG_CONTROL_DTYPE_PRESERVED = "DTYPE_PRESERVED"
NEG_CONTROL_LEGACY_BLOCK = "LEGACY_MIXED_BLOCK_UP_TO_0_3_0"
NEG_CONTROL_EXPLORATORY_LABEL = "EXPLORATORY_POST_HOC_NOT_THE_REGISTERED_CONTROL"
