# -*- coding: utf-8 -*-
"""L0 registries required by PLAN v1.6 G0 (§2.3, §2.4, §5.5, §5.6, §6.10, §6.11, §12.3).

Each registry is a plain dict serialisable to YAML/JSON; ``write_registries`` writes them together
with a sha256 manifest so that run_manifest can reference exact versions. Values below are the
v1.6 decisions plus the operational decisions locked between 28/09 and 30/09/2026
(SPLIT_V2_2_OVERALL_CLOSURE, REPORT_LO_V3). Change them here, never inside experiment code.

Revision 2026-10-01 (registries_rev_2026-10-01), on top of 2026-09-30:
  * LABEL_ARTIFACTS['LO']  -> V3.1: courses without any observed attempt in a weighted assignment/exam component
                              excluded (no_scored_signal_in_course: 102 courses, 172,003 enrollments) [V3.1 §4];
                              cohort 2,605,423 / 711 courses; course score-ceiling table [V3.1 §5]; current-grade group [V3.1 §6].
  * SPLIT_REGISTRY['tasks']['LO'] -> split_version v3_1_scored_signal_excluded, blocks re-paired on the same calendar [V3.1 §8].
  * SAMPLING_STRATEGY      -> LO reference train pools under V3.1 (c0 only changes) [V3.1 §6.1].
  * PENDING_DECISIONS      -> 0, 1, 2, 3 closed (1 and 3 with a remainder); new items 6-8 opened.
Revision 2026-09-30 (registries_rev_2026-09-30):
  * LABEL_ARTIFACTS['LO']  -> catalog-normalised final_score contract V3 (REPORT_LO_V3 §1-§4, §7),
                              sensitivity set TEMPO_LEGACY_CLIP, 19-field label-proxy contract, cohort.
  * SPLIT_REGISTRY         -> shared CQ calendar, per-task split_version (CQ v2.2, LO v3_catalog_normalized),
                              QA22 as locked (label-end order + non-empty arms), two overlap metrics,
                              long-offering decision (keep units, context flags).
  * METRIC_DEF v1.1        -> cell-level small_support_flag (< 400), small_subgroup_flag kept, CLASS_ABSENT,
                              bootstrap / paired-bootstrap policy, checkpoint rule, prediction-level context columns.
  * SAMPLING_STRATEGY      -> unchanged IR10_K10; reference train-pool counts under LO V3 added (cap binds).
  * PENDING_DECISIONS      -> items still open on 2026-09-30; nothing in them is to be treated as locked.
Sources are tagged [CL §k] = REPORT_SPLIT_V2_2_OVERALL_CLOSURE_2026-09-30, [V3 §k] = REPORT_LO_V3 (30/09/2026),
[LO §k] = REPORT_LO_V2.2 (30/09/2026), [V3.1 §k] = REPORT_LO_V3_1 (01/10/2026), [PLAN §k] = Mo_ta_meta-dataset_v1.6.
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

from .seeds import sha256_of, SEED_PREPROCESS

REGISTRY_REVISION = 'registries_rev_2026-10-01_r2'

# ---------------------------------------------------------------------------------------------
# Pipeline registry V0–V16 (PLAN Table 7 / Table 14)
# ---------------------------------------------------------------------------------------------
IMPUTERS = [('NONE', 'V0'), ('MEDIAN', 'V1'), ('MEAN', 'V5'), ('EXTRATREES', 'V9'), ('MICE', 'V13')]
BALANCERS = ['NONE', 'CDSMOTE', 'SASMOTE', 'RADIUS_SMOTE']
IMPUTER_FAMILY = {'NONE': 'NONE', 'MEDIAN': 'UNIVARIATE', 'MEAN': 'UNIVARIATE',
                  'EXTRATREES': 'MULTIVARIATE_MODEL', 'MICE': 'MULTIVARIATE_MODEL'}

V0_FILL_RULE = {
    'rule_id': 'ZERO_RAW_PRE_TRANSFORM',
    'fill_value': 0.0,
    'fill_space': 'RAW',                      # RAW | POST_LOG | POST_SCALE
    'applies_to': 'OBSERVED_MISSING_ONLY',
    'future_unavailable': {'fill_value': 0.0, 'mask': 'M_available=0'},
    'note': 'Filled before log transform and RobustScaler; carries "no activity" semantics for counts; '
            'M_missing=1 keeps the cell distinguishable from a real zero.',
}
SAMPLING_STRATEGY = {
    # Decided 2026-09-27 (Phuong_an_sampling_strategy.docx): IR target with a per-class expansion cap.
    'primary': {'sampling_strategy_id': 'IR10_K10', 'type': 'IR_TARGET_WITH_CAP', 'ir_target': 10, 'max_expansion_per_class': 10,
                'rule': 'n_target_c = min(max(n_c, ceil(n_max / ir_target)), max_expansion_per_class * n_c); majority never undersampled',
                'decided_on': '2026-09-27', 'basis': 'Phuong_an_sampling_strategy.docx; tempo_fix.sampling.plan_targets'},
    'sensitivity': [
        {'sampling_strategy_id': 'IR5_K20', 'type': 'IR_TARGET_WITH_CAP', 'ir_target': 5, 'max_expansion_per_class': 20},
        {'sampling_strategy_id': 'IR20_K5', 'type': 'IR_TARGET_WITH_CAP', 'ir_target': 20, 'max_expansion_per_class': 5},
    ],
    # Targets are always recomputed from the real TRAIN pool of the window (sampling.targets_from_registry);
    # the counts below are the reference values used in the plan text and in the sampling note.
    'reference_train_pools': {
        'CQ': {'W1': {'c0': 1576716, 'c1': 19394, 'c2': 13166}, 'source': '[CL §7.5] CQ W1 train (block A), release V1 population 2,684,090'},
        'LO': {'W1': {'c0': 1782182, 'c1': 4720, 'c2': 655}, 'W2': {'c0': 1936554, 'c1': 5777, 'c2': 1907},
               'W3': {'c0': 2338176, 'c1': 5823, 'c2': 1925},
               'source': '[V3.1 §6.1] LO train pools under lo_final_score_catalog_normalized_v3_1 (c1, c2 identical to V3; '
                         'c0 smaller by the excluded courses); replaces the June 2026 counts (c0 2,947,015 / c1 8,886 / '
                         'c2 31,441) used in Phuong_an_sampling_strategy.docx'},
    },
    'v3_consequence': 'Under LO V3.1 the max_expansion_per_class = 10 cap binds for c1 and c2 in every window: post-sampling IR '
                      'is 37.8/272.1 (W1), 33.5/101.5 (W2), 40.2/121.5 (W3) for c1/c2 instead of approaching ir_target '
                      '[V3.1 §6.1]. The reason for the cap (synthetic share <= 90% of a class) is unchanged, so the primary '
                      'scheme is kept; the consequence table in PLAN §2.3 and the sampling note must be rewritten with these numbers.',
    'status': 'PRIMARY_CONFIRMED 2026-10-01 [V3.1 §6]',
}
MICE_PARAMS = {'initial_strategy': 'constant_zero_first_round_only', 'max_iter': 10, 'tol': 1e-3,
               'internal_scaler': 'RobustScaler(train_only, inverse_transform_before_output)',
               'sparse_predictor_fallback': 'train_median (0 if all missing)',
               'report': 'trpool_post_fallback_rate'}
EXTRATREES_PARAMS = {'n_estimators': 100, 'max_depth': None, 'min_samples_leaf': 5, 'n_jobs': -1}
BALANCER_PARAMS = {'CDSMOTE': {'k_neighbors': 5}, 'SASMOTE': {'k_neighbors': 5}, 'RADIUS_SMOTE': {'radius_quantile': 0.5}}


def build_pipeline_registry(sampling: Dict = SAMPLING_STRATEGY['primary']) -> List[Dict]:
    rows = []
    vid = 0
    for imp, imp_only in IMPUTERS:
        for bal in BALANCERS:
            if imp == 'NONE' and bal != 'NONE':
                continue                       # SMOTE needs NaN-free data (PLAN §2.3)
            pid = f'V{vid}'
            name = 'V0-Raw' if pid == 'V0' else f'{pid}-' + '-'.join(
                x for x in (imp.title().replace('Extratrees', 'ExtraTrees').replace('Mice', 'MICE'),
                            {'NONE': '', 'CDSMOTE': 'CDSMOTE', 'SASMOTE': 'SASMOTE', 'RADIUS_SMOTE': 'RadiusSMOTE'}[bal]) if x)
            imputer_params = {'NONE': V0_FILL_RULE, 'MEDIAN': {'strategy': 'median'}, 'MEAN': {'strategy': 'mean'},
                              'EXTRATREES': EXTRATREES_PARAMS, 'MICE': MICE_PARAMS}[imp]
            balancer_params = None if bal == 'NONE' else {**BALANCER_PARAMS[bal], **sampling}
            row = {
                'pipeline_id': pid, 'pipeline_name': name, 'imputer': imp, 'balancer': bal,
                'imputer_family': IMPUTER_FAMILY[imp], 'balancer_family': 'NONE' if bal == 'NONE' else 'SMOTE_VARIANT',
                'is_no_intervention': int(pid == 'V0'), 'has_imputation': int(imp != 'NONE'), 'has_balancing': int(bal != 'NONE'),
                'before_ref': 'V0', 'imputer_only_ref': 'V0' if bal == 'NONE' else imp_only,
                'fit_scope': 'TRAIN_POOLED_P1_P4', 'impute_scope': 'OBSERVED_MISSING_ONLY',
                'v0_fill_rule': V0_FILL_RULE['rule_id'], 'seed_preprocess': SEED_PREPROCESS,
                'synthetic_phase_rule': 'SAME_PHASE_ONLY', 'synthetic_mask_rule': 'INTERSECTION_OF_PARENTS',
                'sampling_strategy_id': None if bal == 'NONE' else sampling['sampling_strategy_id'],
                'imputer_params': imputer_params, 'balancer_params': balancer_params,
            }
            row['imputer_params_hash'] = sha256_of(imputer_params)
            row['balancer_params_hash'] = sha256_of(balancer_params) if balancer_params else None
            rows.append(row)
            vid += 1
    assert vid == 17, vid
    return rows


def validate_pipeline_registry(rows: List[Dict]) -> None:
    ids = [r['pipeline_id'] for r in rows]
    assert ids == [f'V{i}' for i in range(17)], ids
    by = {r['pipeline_id']: r for r in rows}
    # PLAN Table 14 mapping
    expect = {'V2': 'V1', 'V3': 'V1', 'V4': 'V1', 'V6': 'V5', 'V7': 'V5', 'V8': 'V5', 'V10': 'V9', 'V11': 'V9',
              'V12': 'V9', 'V14': 'V13', 'V15': 'V13', 'V16': 'V13', 'V1': 'V0', 'V5': 'V0', 'V9': 'V0', 'V13': 'V0', 'V0': 'V0'}
    for k, v in expect.items():
        assert by[k]['imputer_only_ref'] == v, (k, by[k]['imputer_only_ref'], v)


# ---------------------------------------------------------------------------------------------
# Model registry (PLAN Table 8, §2.4; v1.6: selection metric, mandatory channels)
# ---------------------------------------------------------------------------------------------
INPUT_CHANNELS = ['X', 'M_missing', 'M_available', 'delta_t', 'phase_id', 'observed_length']
COMMON_HPARAMS = {'hparam_config_id': 'HP_RNN_FAMILY_v1', 'loss_name': 'cross_entropy', 'class_weighting': 'NONE',
                  'lr': 1e-3, 'batch_size': 256, 'max_epochs': 50, 'early_stopping_patience': 5,
                  'selection_metric': 'MEAN_PHASE_MACRO_F1', 'selection_tiebreak': 'MEAN_PHASE_CROSS_ENTROPY_MIN',
                  'selection_log': ['selection_margin', 'selected_epoch', 'n_checkpoints_within_margin'],
                  'amp_dtype': 'bfloat16'}
MODEL_REGISTRY = [
    {'model_name': 'CQ_PARTIAL_TRIAD', 'model_tier': 'F0_REFERENCE', 'model_family': 'DETERMINISTIC', 'variant_role': 'REFERENCE', 'task': 'CQ'},
    {'model_name': 'LO_HEURISTIC_PROGRESS_GRADE', 'model_tier': 'F0_REFERENCE', 'model_family': 'DETERMINISTIC', 'variant_role': 'REFERENCE', 'task': 'LO'},
    {'model_name': 'RNN', 'model_tier': 'F1_RECURRENT', 'model_family': 'RNN', 'variant_role': 'PRIMARY'},
    {'model_name': 'LSTM', 'model_tier': 'F1_RECURRENT', 'model_family': 'LSTM', 'variant_role': 'PRIMARY'},
    {'model_name': 'GRU', 'model_tier': 'F1_RECURRENT', 'model_family': 'GRU', 'variant_role': 'ROBUSTNESS'},
    {'model_name': 'BILSTM', 'model_tier': 'F1_RECURRENT', 'model_family': 'LSTM', 'variant_role': 'ROBUSTNESS'},
    {'model_name': 'PATCHTST', 'model_tier': 'F2_TS_TRANSFORMER', 'model_family': 'PATCHTST', 'variant_role': 'PRIMARY'},
    {'model_name': 'MOMENT_SMALL', 'model_tier': 'F3_TS_FOUNDATION', 'model_family': 'MOMENT', 'variant_role': 'PRIMARY', 'is_pretrained': 1, 'finetune_mode': 'LINEAR_PROBE'},
    {'model_name': 'MOMENT_BASE', 'model_tier': 'F3_TS_FOUNDATION', 'model_family': 'MOMENT', 'variant_role': 'PRIMARY', 'is_pretrained': 1, 'finetune_mode': 'LINEAR_PROBE'},
]
for _m in MODEL_REGISTRY:
    if _m['model_tier'] != 'F0_REFERENCE':
        _m.update({'input_channels': INPUT_CHANNELS, 'uses_mask_channels': 1, 'uses_delta_t': 1, 'uses_phase_id': 1,
                   'uses_observed_length': 1, 'identifier_embeddings': 0, **COMMON_HPARAMS})

# ---------------------------------------------------------------------------------------------
# Metric, sanity, AccTEMPO and recommendation definitions
# ---------------------------------------------------------------------------------------------
METRIC_DEF = {
    'metric_def_version': 'metric_def_v1.2',
    'class_index': {'CQ': {'c0': 'W', 'c1': 'A', 'c2': 'G'}, 'LO': {'c0': 'ID', 'c1': 'G', 'c2': 'E'}},
    'risk_class': 'c0',
    'majority_class': {'CQ': 'c0', 'LO': 'c0'},   # both tasks: the risk class is the majority class ([CL §7.5], [V3 §6])
    'macro_policy': 'FIXED_K_CLASSES',       # macro averages over all K classes (absent class -> NULL/CLASS_ABSENT)
    'zero_division': 'NULL',
    'core_metrics': ['acctempo_m3', 's_perf', 'macro_f1', 'balanced_acc', 'mcc', 'kappa', 'pr_auc_macro', 'gmean'],
    'extended_metrics': ['accuracy', 'weighted_f1', 'roc_auc_macro_ovr', 'log_loss', 'brier', 'ece'],
    'ece_bins': 15, 'ece_type': 'top_label', 'probability_clip': 1e-12, 'prob_sum_tolerance': 1e-4,
    'per_class': ['precision', 'recall', 'specificity', 'f1', 'gmean', 'ap', 'support', 'predicted_count'],
    'bootstrap': {'B': 2000, 'unit': 'ENROLLMENT', 'ci': 0.95},
    'probability_reporting': {
        'LO_W2': ['log_loss', 'pr_auc_macro'],
        'rule': 'report beside macro_f1; PR-AUC macro is NULL/CLASS_ABSENT if a required class is absent',
    },
    'offering_cluster_bootstrap': {
        'rule': 'when n_offerings_with_class <= 2, additionally resample whole offerings with replacement',
        'B': 2000, 'ci': 0.95, 'unit': 'OFFERING',
        'report': 'report alongside enrollment bootstrap; never substitute the latter',
        'known_cells': ['LO W1 TEST E', 'LO W3 TEST G'],
    },
    # --- support and uncertainty policy locked 30/09/2026 ([CL §6], [V3 §6]; thresholds from Danh_gia_Split_V2.2_closure) ---
    'support_flags': {
        'small_support_flag': {'rule': 'n_support < 400', 'granularity': 'cell = (task, window, phase, eval_split, subgroup, class); '
                               'applies to the TEMPORAL STRICT/OVERLAP slice and to every mandatory subgroup',
                               'rationale': '95% CI of a proportion near 0.5 wider than +/-5 points',
                               'effect': 'per-class metrics kept, always reported with bootstrap CI; never used alone as pipeline evidence'},
        'small_subgroup_flag': {'rule': 'n_g < 30 or any class support < 5', 'source': '[PLAN §2.5]', 'kept_separately': True},
        'class_absent': {'rule': 'per-class metrics NULL with null_reason = CLASS_ABSENT; never 0 or interpolated'},
    },
    'pipeline_comparison': {'rule': 'paired_bootstrap_delta, B = 2000, unit ENROLLMENT; mandatory for every LO W2/W3 cell and '
                                    'for every cell with small_support_flag = 1'},
    'checkpoint_selection': {'metric': 'MEAN_PHASE_MACRO_F1', 'split': 'VALIDATION', 'tiebreak': 'MEAN_PHASE_CROSS_ENTROPY_MIN',
                             'log': ['selection_margin', 'selected_epoch', 'n_checkpoints_within_margin'],
                             'note': 'LO W1 VALIDATION minority classes come from a single offering (E 1,000 of 1,000; G 525) '
                                     '[V3 §6, §8]; read selection_margin before interpreting LO W1'},
    'prediction_level_context_columns': ['timeline_source', 'duration_days', 'long_offering_flag', 'label_threshold_set',
                                         'n_offerings_with_class'],
    'long_offering_flag': {'rule': 'offering duration > 270 days', 'source': '[CL §8], [V3 §8]',
                           'use': 'report-only stratification; not a filter; not a new mandatory subgroup'},
    'sanity_reporting': {'rule': 'S_san+ v1 and s_cal-based v2 reported side by side in every cell; the v1 s_ent component '
                                 'sits at the eps floor on 99.8-99.9%-majority slices (LO W2/W3), so v2 is the informative lens there'},
}
S_SAN_FORMULA = {
    'v1': {'s_san_formula_version': 's_san_v1_jsd_base2_six_components',
           'components': ['s_nan', 's_maj_jsd', 's_ent', 's_drift', 's_eff', 's_leak'], 'aggregation': 'geometric_mean',
           's_eps_floor': 1e-3, 'jsd_base': 2,
           's_ent': '1 - min(|median(h_i) - 0.5| / 0.5, 1), h_i normalised entropy',
           's_eff': 'run-level: mean(mask) over the TRAIN tensor actually used for training (S3_MODEL_INPUT, pooled P1-P4)',
           's_leak': '1 - 2*max(AUC_probe - 0.5, 0); probe = multinomial logistic regression (L2, C=1.0) on missingness '
                     'indicators only; fit on TRAIN after pipeline pooled P1-P4 (4 views per real enrollment + synthetic); '
                     'evaluated on the row slice (eval_split, phase) at S3_MODEL_INPUT; record n_fit, n_eval, eval_split',
           's_drift_reference': 'TRAIN real class distribution before balancing (trpool_class_count)',
           's_maj_jsd_reference': 'true class distribution of the evaluated slice'},
    'v2': {'s_san_formula_version': 's_san_v2_calibration', 'components': ['s_nan', 's_maj_jsd', 's_cal', 's_drift', 's_eff', 's_leak'],
           'aggregation': 'geometric_mean', 's_eps_floor': 1e-3, 's_cal': '1 - ECE_15 (top-label, 15 equal-width bins)'},
}
ACCTEMPO_DEF = {'acctempo_def_version': 'acctempo_m3_v1.1', 'alpha': 0.6, 'beta': 0.4, 'acctempo_eps_floor': 1e-3,
                'primary_s_san_version': 'v1', 'also_compute': ['v2'],
                'report_rule': 'v1 and v2 always side by side ([V3 §6]); LO W2/W3 discussion uses v2 as the informative lens',
                'bootstrap_rule': 'S_perf, s_nan, s_maj_jsd, s_ent/s_cal, s_drift recomputed per resample; s_eff, s_leak fixed (run-level)',
                'decision_pending': 'primary v1 vs v2 to be fixed after the 24-cell component table of the V0 runs, before mm_config lock'}
REC_RULE = {'rec_rule_version': 'rec_v1.1', 'rec_objective': 'TEST_ACCTEMPO_M3_DELTA', 'rec_eps': 0.005,
            'secondary_objective': 'TEST_MACRO_F1_DELTA', 'utility_lambda_grid': [0, 0.01, 0.02, 0.05],
            'cost_basis': 'ENERGY_IF_MEASURED_ELSE_TIME',
            'cost_basis_rule': 'energy_gpu_run_kwh_ratio when every candidate in the rec_group has a MEASURED value; '
                               'otherwise time_run_total_s_ratio; never mixed inside a rec_group'}

# ---------------------------------------------------------------------------------------------
# Label artifacts (PLAN Table 4; LO replaced by the V3 catalog-normalised contract on 30/09/2026)
# ---------------------------------------------------------------------------------------------
LO_PROXY_CONTRACT = {
    # 19 canonical fields [V3 §4]; every canonical field and every _P1.._P4 variant has is_label_proxy = 1 and is
    # excluded from imputer predictors and from model input in every LO regime. Four names marked in
    # ``names_to_confirm`` are inferred from the group description in [V3 §4] and must be checked against
    # final_score_contract_audit_v3_catalog_normalized/proxy_feature_contract before feature_dictionary_v1 is locked.
    'contract_id': 'lo_proxy_contract_v3',
    'canonical_fields': {
        'score_weights': ['performance_score', 'video_weight', 'assignment_weight', 'exam_weight', 'course_weight_total'],
        'video': ['watched_videos', 'video_counts', 'watch_percent', 'video_catalog_coverage'],
        'problem': ['assignment_problem_catalog_count', 'exam_problem_catalog_count',
                    'assignment_best_correct_sum', 'exam_best_correct_sum',
                    'assignment_ratio_catalog', 'exam_ratio_catalog',
                    'problem_catalog_coverage', 'problem_score_catalog_coverage'],
        'sensitivity': ['tempo_legacy_unclipped_score', 'tempo_legacy_score_clipped'],
    },
    'n_canonical_fields': 19,
    'verified_problem_fields': ['assignment_problem_catalog_count', 'exam_problem_catalog_count',
                                'assignment_best_correct_sum', 'exam_best_correct_sum'],
    'phase_variants_rule': 'any canonical field with suffix _P1, _P2, _P3, _P4 (or the pipeline equivalent) inherits is_label_proxy = 1',
    'exclusion_scope': ['imputer_predictors (QA21)', 'model input of LO_FULL_EARLY, LO_NO_CURRENT_GRADE, LO_NO_PROGRESS'],
    'audit_artifact': 'final_score_contract_audit_v3_1_scored_signal_excluded/{label_semantics_contract, proxy_feature_contract, '
                      'exclusion_reason_summary, score_range_by_profile}',
    'audit_status': 'verified against the V3.1 final-score contract; all 19 fields are label proxies and are excluded from imputer/model predictors',
    'current_grade_group': {'status': 'LOCKED 2026-10-01 [V3.1 §6]',
                            'columns': ['score_sum', 'score_mean', 'score_std', 'score_fraction_mean', 'score_fraction_std',
                                        'correct_problem_count', 'incorrect_problem_count', 'correct_ratio', 'correct_ratio_std'],
                            'regimes': {'LO_FULL_EARLY': 'included', 'LO_NO_CURRENT_GRADE': 'removed', 'LO_NO_PROGRESS': 'per PLAN §2.6'},
                            'note': 'attempt-level, not catalog-normalised; problem_score_catalog_coverage stays a label proxy in every '
                                    'regime; QA23 (Spearman |rho|, NMI vs final_score) is run per phase on this group and reported'},
}
LABEL_ARTIFACTS = {
    'CQ': {'label_rule_version': 'CQ_TRIAD_PROXIMITY_v1', 'label_threshold_set': 'PRIMARY',
           'score': 'cq_score_g_final = 1 - TRIAD_distance_final/sqrt(3) (alias CQ_proximity_final)',
           'thresholds': {'W': '< 0.10', 'A': '[0.10, 0.30)', 'G': '>= 0.30'},
           'invalid_component_policy': 'NULL with exclusion_reason; never coerced to W',
           'population': {'n_enrollments': 2684090, 'source': 'release V1 (REPORT_CQ_V1); [CL §8.3] distinct enrollment 2,684,090',
                          'class_counts': {'c0': 2582414, 'c1': 56129, 'c2': 45547}}},
    'LO': {
        'label_rule_version': 'lo_final_score_catalog_normalized_v3_1',
        'label_threshold_set': 'CATALOG_NORMALIZED_PRIMARY_V3',
        'v3_1_change': 'same formula and bands as V3; courses without any observed attempt in every weighted assignment/exam '
                       'component are excluded with reason no_scored_signal_in_course (102 courses, 172,003 enrollments) [V3.1 §4]',
        'label_field': 'LO_performance_label_3', 'score_field': 'performance_score',
        'score_semantics': 'activity_derived_weighted_score',
        'final_grade_claim': 'not_an_independently_observed_final_grade',
        'formula': 'performance_score = video_weight*watch_percent + assignment_weight*assignment_ratio_catalog '
                   '+ exam_weight*exam_ratio_catalog',
        'components': {
            'watch_percent': 'min(1, watched_videos / video_counts)',
            'assignment_ratio_catalog': 'sum over catalog assignment problems of best automatic correct ratio '
                                        '(best score / full score over attempts) / catalog assignment problem count; unattempted = 0',
            'exam_ratio_catalog': 'same rule over catalog exam problems; unattempted = 0',
            'exam_problem_rule': 'exam problems = problems of the last hierarchical chapter when the course has exam_weight; '
                                 'every other problem is an assignment problem [LO §5]',
            'weights': 'course_limit.csv (video, assignment, exam); weight total must equal 100',
        },
        'structural_bound': [0.0, 100.0],
        'thresholds': {'ID': '[0, 60)', 'G': '[60, 85)', 'E': '[85, 100]'},
        'monotone_in_performance': True,
        'sensitivity_sets': {
            'TEMPO_LEGACY_CLIP': {'rule': 'legacy attempt-level score (exam component = sum of correct ratios over attempted exam '
                                          'problems, not normalised) clipped at 100; same bands', 'role': 'SENSITIVITY_ONLY',
                                  'note': 'reproduces the CD2/TEMPO prevalence regime; identical to the 2026-09-30 morning label '
                                          'except for the clip'},
        },
        'superseded_versions': [
            {'label_rule_version': 'lo_operational_performance_v1', 'reason': 'exam component unbounded (sum of correct ratios), '
             'score > 100 kept as E; 21,141 enrollments > 100 [LO §8]'},
            {'label_rule_version': 'lo_final_score_sourcefaithful_v2', 'reason': 'score > 100 mapped to I/D: non-monotone in '
             'performance (Danh_gia_LO_V2.2_nhan.docx §2); replaced by V3 [V3 §2]'},
            {'label_rule_version': 'lo_final_score_catalog_normalized_v3', 'reason': 'kept courses with no scored signal at all '
             '(profile EXAM max 0.000); replaced by V3.1 after the course-ceiling audit [V3.1 §4, §5]'},
        ],
        'cohort': {
            'raw_enrollments': 11807090, 'eligible_enrollments': 2605423, 'eligible_share_of_raw': 0.22067, 'eligible_courses': 711,
            'class_counts': {'c0': 2596424, 'c1': 6996, 'c2': 2003},
            'exclusion_reasons': {'missing_course_limit_weights': {'enrollments': 8615401, 'courses': 3610},
                                  'missing_assignment_problem_catalog': {'enrollments': 200140, 'courses': 159},
                                  'no_scored_signal_in_course': {'enrollments': 172003, 'courses': 102,
                                                                 'rule': 'no observed attempt in every weighted assignment/exam component'},
                                  'nonpositive_course_weight_total': {'enrollments': 134618, 'courses': 102},
                                  'course_weight_total_not_100': {'enrollments': 69729, 'courses': 16},
                                  'missing_exam_problem_catalog': {'enrollments': 9776, 'courses': 1}},
            'source': '[V3.1 §4]',
            'technical_exclusions_inside_assigned_slices': {
                # label rows that carry a rolling block but are not label-eligible; outside the split population [V3.1 §9]
                'by_slice_and_reason': {'A': {'missing_assignment_problem_catalog': 37, 'course_weight_total_not_100': 154,
                                              'missing_exam_problem_catalog': 943, 'nonpositive_course_weight_total': 1},
                                        'T1': {'missing_assignment_problem_catalog': 1},
                                        'T2': {'missing_assignment_problem_catalog': 2453, 'course_weight_total_not_100': 361,
                                               'missing_exam_problem_catalog': 55, 'nonpositive_course_weight_total': 6},
                                        'T3': {'missing_assignment_problem_catalog': 8946, 'course_weight_total_not_100': 4980,
                                               'missing_exam_problem_catalog': 61, 'nonpositive_course_weight_total': 10}},
                'total': 18008},
        },
        'course_score_ceiling': {
            # course_score_ceiling_observed = highest PRIMARY score observed in the course [V3.1 §5]
            'ceiling_below_60': {'courses': 493, 'enrollments': 1668604, 'share_of_cohort': 0.64043},
            'ceiling_below_85': {'courses': 675, 'enrollments': 2372394, 'share_of_cohort': 0.91056},
            'remaining_no_scored_signal_candidates': 0,
            'decision': 'no automatic drop of low-ceiling courses [V3.1 §5]',
            'implication': 'class G can only occur in 218 courses (936,819 enrollments, 35.96%), class E in 36 courses '
                           '(233,029 enrollments, 8.94%). The catalog-denominator audit found active ratios p50=0.900 and p90=1.000 '
                           'in the <60 band; retain V3.1 rather than construct V3.2.',
        },
        'score_range_by_profile': {
            # [V3.1 §7] after the no_scored_signal exclusion; profile EXAM no longer exists
            'VIDEO': {'eligible': 7377, 'min': 0.0, 'max': 25.806, 'E': 0, 'G': 0},
            'ASSIGNMENT+EXAM': {'eligible': 76661, 'min': 0.0, 'max': 100.0, 'E': 220, 'G': 150},
            'ASSIGNMENT': {'eligible': 15069, 'min': 0.0, 'max': 100.0, 'E': 28, 'G': 25},
            'VIDEO+ASSIGNMENT': {'eligible': 887408, 'min': 0.0, 'max': 90.0, 'E': 4, 'G': 623},
            'VIDEO+ASSIGNMENT+EXAM': {'eligible': 1618809, 'min': 0.0, 'max': 97.198, 'E': 1751, 'G': 6198},
            'VIDEO+EXAM': {'eligible': 99, 'min': 0.0, 'max': 5.0, 'E': 0, 'G': 0},
            'removed_by_no_scored_signal': {'EXAM': 31334, 'VIDEO+ASSIGNMENT+EXAM': 117389, 'VIDEO+ASSIGNMENT': 22097,
                                            'VIDEO+EXAM': 922, 'ASSIGNMENT': 200, 'ASSIGNMENT+EXAM': 61, 'total': 172003},
        },
        'proxy_contract': LO_PROXY_CONTRACT,
        'invalid_component_policy': 'enrollment not label-eligible -> excluded with proxy_exclusion_reason; never coerced to ID',
    },
}

# ---------------------------------------------------------------------------------------------
# Split registry: shared CQ calendar, per-task split_version (locked 29-30/09/2026)
# ---------------------------------------------------------------------------------------------
SPLIT_REGISTRY = {
    'scheme_version': 'v2_family_shared_calendar',
    'scenario': 'hybrid',
    'scheme': 'A = offerings ending on or before a_boundary (CQ anchor: earliest 60% CQ enrollments by offering_end_date); '
              'future pool cut at explicit calendar boundaries into T1, T2, T3; inside each slice whole units are paired '
              'into VALIDATION/TEST blocks (T1->B,C; T2->D,E; T3->F,G) with tempo_fix.split_v2._greedy_pair_split',
    'unit': 'offering_id x timeline_source; a unit is never split across blocks; an enrollment belongs to exactly one block',
    'windows': {'W1': ['A', 'B', 'C'], 'W2': ['A+B+C', 'D', 'E'], 'W3': ['A+B+C+D+E', 'F', 'G']},
    'calendar': {
        'anchor_task': 'CQ',
        'a_boundary': '2020-07-31', 'slice_boundaries': {'T1': '2020-09-13', 'T2': '2020-12-31', 'T3': '2022-01-18'},
        'tau_w': {'W1': '2020-07-31', 'W2': '2020-09-13', 'W3': '2020-12-31'},
        'slice_calendar_days': {'T1': 44, 'T2': 109, 'T3': 383},
        'source': '[CL §2 boundaries], [V3 §5 tau_w]; both tasks use the same four dates',
    },
    'temporal_rule': 'LABEL_TIME_ORDERING: tau_w = latest TRAIN offering_end_date <= earliest VALIDATION/TEST offering_end_date '
                     'in every window',
    'qa22': {'hard': ['end_order_ok', 'eval_size_ok'], 'min_eval_enrollments': 1,
             'reported_only': ['ev_train_overlap_share', 'p1_cutoff_overlap_share', 'days_train_end_to_test_start',
                               'temporal_strict_share_P1_P4'],
             'revised_on': '2026-09-28', 'locked_on': '2026-09-30',
             'reason': 'SPLIT_V2_QA_INCIDENT_REPORT: concurrent offerings make any start-date purge remove 90-100% of the '
                       'evaluation sets; overlap is inherent to MOOC data and is analysed as a slice'},
    'overlap_metrics': {
        'ev_train_overlap_share': 'share of evaluation enrollments whose offering_start_date < tau_w (offering-start based) [CL §3]',
        'p1_cutoff_overlap_share': '1 - temporal_strict_share(P1, split): share whose P1 cutoff < tau_w [CL §3]',
        'rule': 'both columns are kept; neither replaces the other',
    },
    'purge_mode': 'NONE',
    'sensitivity_exclusions': ['TEST_SIDE_PURGE', 'TRAIN_EMBARGO'],
    'embargo_gap_days': 0,
    'temporal_slice': {'subgroup_axis': 'TEMPORAL', 'values': ['STRICT', 'OVERLAP'],
                       'rule': 'STRICT when cutoff_k(e) = enroll_time + q_k*(offering_end_date - enroll_time) >= tau_w; computed per '
                               '(enrollment, phase) from stored predictions; reported for every run and every phase P1-P4; '
                               'not part of the five mandatory meta-model subgroups; empty slice -> NULL with SLICE_EMPTY'},
    'long_offering': {'decision': 'KEEP_UNITS', 'decided_on': '2026-09-30', 'source': '[V3 §8]',
                      'threshold_days': 270,
                      'context_columns': ['timeline_source', 'duration_days', 'long_offering_flag'],
                      'no_new_mandatory_subgroup': True,
                      'evidence': {'course_specific_timeline': {'p50': 121, 'p90': 345, 'max': 506, 'enrollment_share_gt_270d': 0.01457},
                                   'global_template_fallback': {'p50': 127, 'p90': 426, 'max': 481, 'enrollment_share_gt_270d': 0.55124},
                                   'enrollment_anchored_proxy': {'p50': 152, 'p90': 212, 'max': 212, 'enrollment_share_gt_270d': 0.0}}},
    'tasks': {
        'CQ': {'split_version': 'v2.2', 'registry_id': 'split_registry_v2_2_overlap_audit_v1_r2', 'pairing': 'balanced',
               'population': 2684090, 'label_rule_version': 'CQ_TRIAD_PROXIMITY_v1',
               'blocks': {'A': 1609276, 'B': 175689, 'C': 178095, 'D': 180485, 'E': 180482, 'F': 180032, 'G': 180031},
               'qa22': {'W1': 'PASS', 'W2': 'PASS', 'W3': 'PASS'},
               'assignment_qa': {'multi_block_enrollments': 0, 'multi_split_per_window': 0, 'multi_block_units': 0, 'unmapped': 0},
               'status': 'LOCKED', 'source': '[CL §2, §7.5, §8.3]'},
        'LO': {'split_version': 'v3_1_scored_signal_excluded', 'registry_id': 'split_registry_v3_1_scored_signal_excluded_overlap_audit_v1',
               'pairing': 'rarest_first', 'population': 2605423, 'label_rule_version': 'lo_final_score_catalog_normalized_v3_1',
               'blocks': {'A': 1787557, 'B': 78090, 'C': 78591, 'D': 200842, 'E': 200844, 'F': 129426, 'G': 130073},
               'block_classes': {'A': {'c0': 1782182, 'c1': 4720, 'c2': 655}, 'B': {'c0': 77306, 'c1': 532, 'c2': 252},
                                 'C': {'c0': 77066, 'c1': 525, 'c2': 1000}, 'D': {'c0': 200812, 'c1': 23, 'c2': 7},
                                 'E': {'c0': 200810, 'c1': 23, 'c2': 11}, 'F': {'c0': 129283, 'c1': 94, 'c2': 49},
                                 'G': {'c0': 128965, 'c1': 1079, 'c2': 29}},
               'qa22': {'W1': 'PASS', 'W2': 'PASS', 'W3': 'PASS'},
               'assignment_qa': {'multi_block_enrollments': 0, 'multi_split_per_window': 0, 'multi_block_units': 0, 'unmapped': 0,
                                 'note': 'source audits available; refresh against the V3.1 release after materialize [V3.1 §13]'},
               'superseded': ['v2_2_reference (label lo_operational_performance_v1)',
                              'v2.2.sourcefaithful (label lo_final_score_sourcefaithful_v2)',
                              'v3_catalog_normalized (label lo_final_score_catalog_normalized_v3)'],
               'relation_to_cq': 'same calendar, same unit rule, different population and label; distinct split_version by design',
               'single_offering_cells': {'W1_TEST_c2': '1,000 of 1,000 E from the top-E offering of T1 (79.87% of 1,252)',
                                         'W3_TEST_c1': '1,074 of 1,079 G from the top-G offering of T3'},
               'status': 'LOCKED by the experiment team 2026-10-01; V3.1 retained after catalog-denominator audit',
               'source': '[V3.1 §6.1, §8]'},
    },
    'evaluation_windows': {'CQ': {'primary': ['W1', 'W2', 'W3']},
                           'LO': {'primary': ['W1'], 'exploratory': ['W2', 'W3'],
                                  'reason': 'LO W2 minority support 7-23 per split, LO W3 E 29-49 and TEST G 99.5% from one '
                                            'offering [V3 §6, §8]; all windows are still run so the meta-dataset is complete',
                                  'status': 'CONFIRMED 2026-10-01 [V3.1 §6]'}},
    'run_manifest_required': ['scenario', 'split_version', 'split_registry_id', 'parent_manifest_id', 'parent_audit_ids',
                              'code_hash', 'config_hash', 'seed', 'label_rule_version', 'label_threshold_set'],
}

# ---------------------------------------------------------------------------------------------
# Open decisions on 2026-09-30 (nothing here is locked; indices are referenced above)
# ---------------------------------------------------------------------------------------------
PENDING_DECISIONS = [
    {'id': 0, 'topic': 'LO courses with no scored signal', 'status': 'CLOSED 2026-10-01',
     'resolution': 'excluded with reason no_scored_signal_in_course (102 courses, 172,003 enrollments); LO re-paired as '
                   'v3_1_scored_signal_excluded; no remaining candidates [V3.1 §4, §5, §8]'},
    {'id': 1, 'topic': 'LO current-grade column group and the four inferred proxy field names', 'status': 'CLOSED_PARTIAL 2026-10-01',
     'resolution': 'current-grade group locked (9 columns) [V3.1 §6]; the four problem-field names remain open as item 7'},
    {'id': 2, 'topic': 'proxy_exclusion_reason per slice for the 18,008 ineligible rows', 'status': 'CLOSED 2026-10-01',
     'resolution': 'table by slice and reason recorded in LABEL_ARTIFACTS.LO.cohort.technical_exclusions_inside_assigned_slices [V3.1 §9]'},
    {'id': 3, 'topic': 'IR10_K10 PRIMARY; LO evaluation windows; probability metric for LO W2', 'status': 'CLOSED_PARTIAL 2026-10-01',
     'resolution': 'IR10_K10 and W1-primary / W2-W3-exploratory confirmed [V3.1 §6]; the probability-based metric for W2 '
                   '(log_loss or pr_auc_macro) was not addressed and is carried into item 8'},
    {'id': 4, 'topic': 'BALANCER_PARAMS k_neighbors = 5 and radius_quantile = 0.5 are starting values, not confirmed',
     'blocks': ['pilot balancer'], 'needs': 'QA11/QA12 on the V0 W1 pilot'},
    {'id': 5, 'topic': 'AccTEMPO primary S_san+ version v1 vs v2', 'blocks': ['mm_config lock'], 'needs': '24-cell component table of the V0 runs'},
    {'id': 6, 'topic': 'LO catalog denominator: 493/711 courses (64.0% of enrollments) have an observed ceiling < 60 and 675 courses '
                       '(91.1%) < 85 [V3.1 §5]. Reading (i): true completion pattern, V3.1 final. Reading (ii): catalogs contain problems '
                       'never offered in the offering, so the catalog-normalised ratios are capped for everyone; then V3.2 = same '
                       'formula with the course-level active catalog (problems with >= 1 attempt by anyone in the course) as denominator',
     'diagnostic': 'per course: catalog assignment/exam problem counts vs problems ever attempted by anyone; ceiling band; plus the '
                   'share of enrollments in courses with ceiling >= 60 / >= 85 per slice A/T1/T2/T3 (decomposes the T1 vs T2/T3 contrast)',
     'blocks': ['LO model runs', 'PLAN Table 4 text', 'temporal-drift claims for LO'], 'does_not_block': ['LO materialize', 'S0', 'P0', 'imputation'],
     'cost_if_ii': 'label V3.2, re-pair on the same calendar, QA22, views regenerated; imputers unaffected except W2/W3 train membership'},
    {'id': 7, 'topic': 'exact names of the four problem fields in the 19-field proxy contract (catalog counts and best-correct sums '
                       'for assignment and exam)', 'blocks': ['feature_dictionary_v1 (LO part)'], 'needs': 'proxy_feature_contract artifact'},
    {'id': 8, 'topic': 'reporting policy additions: (a) probability-based metric for LO W2 (log_loss or pr_auc_macro) next to macro-F1; '
                       '(b) offering-cluster bootstrap CI (resample offerings) for cells with n_offerings_with_class <= 2 '
                       '(LO W1 TEST class E, LO W3 TEST class G)', 'blocks': ['METRIC_DEF v1.2'], 'needs': 'author confirmation'},
]

# V3.1 closure addendum, approved after the catalog-denominator audit.  Keep
# the historical declarations above for provenance, but export their resolved
# forms to every JSON/YAML registry consumer.
PENDING_DECISIONS = [item for item in PENDING_DECISIONS if item['id'] not in {1, 3, 6, 7, 8}]
PENDING_DECISIONS.extend([
    {'id': 1, 'topic': 'LO current-grade group and exact proxy field names', 'status': 'CLOSED 2026-10-01',
     'resolution': 'current-grade group locked (9 columns); verified fields: assignment_problem_catalog_count, '
                   'exam_problem_catalog_count, assignment_best_correct_sum, exam_best_correct_sum'},
    {'id': 3, 'topic': 'IR10_K10, LO evaluation windows, probability metric for LO W2', 'status': 'CLOSED 2026-10-01',
     'resolution': 'IR10_K10 and W1-primary/W2-W3-exploratory retained; W2 reports log_loss and pr_auc_macro beside macro_f1'},
    {'id': 6, 'topic': 'LO catalog denominator diagnostic', 'status': 'CLOSED 2026-10-01',
     'resolution': 'active catalog ratio in the <60 band is p50=0.900 and p90=1.000; retain V3.1 and do not construct V3.2'},
    {'id': 7, 'topic': 'Exact problem proxy field names', 'status': 'CLOSED 2026-10-01',
     'resolution': 'assignment_problem_catalog_count, exam_problem_catalog_count, assignment_best_correct_sum, exam_best_correct_sum'},
    {'id': 8, 'topic': 'Probability and clustered-uncertainty reporting', 'status': 'CLOSED 2026-10-01',
     'resolution': 'LO W2: log_loss + pr_auc_macro. When n_offerings_with_class<=2, also report offering-cluster bootstrap B=2000, CI=95%; applies to LO W1 TEST E and LO W3 TEST G'},
])


def all_registries() -> Dict[str, object]:
    pipes = build_pipeline_registry()
    validate_pipeline_registry(pipes)
    return {'pipeline_registry': pipes, 'model_registry': MODEL_REGISTRY, 'metric_def': METRIC_DEF,
            's_san_formula': S_SAN_FORMULA, 'acctempo_def': ACCTEMPO_DEF, 'rec_rule': REC_RULE,
            'label_artifacts': LABEL_ARTIFACTS, 'split_registry': SPLIT_REGISTRY, 'sampling_strategy': SAMPLING_STRATEGY,
            'pending_decisions': PENDING_DECISIONS}


def write_registries(outdir: str) -> Dict[str, str]:
    """Write every registry as YAML (if PyYAML available) and JSON, plus registry_manifest.json with sha256."""
    os.makedirs(outdir, exist_ok=True)
    regs = all_registries()
    manifest = {'registry_revision': REGISTRY_REVISION}
    try:
        import yaml  # type: ignore
    except Exception:  # pragma: no cover
        yaml = None
    for name, obj in regs.items():
        with open(os.path.join(outdir, f'{name}.json'), 'w', encoding='utf-8') as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        if yaml is not None:
            with open(os.path.join(outdir, f'{name}.yaml'), 'w', encoding='utf-8') as f:
                yaml.safe_dump(obj, f, allow_unicode=True, sort_keys=False)
        manifest[name] = sha256_of(obj)
    with open(os.path.join(outdir, 'registry_manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)
    return manifest


if __name__ == '__main__':  # pragma: no cover
    import sys
    print(json.dumps(write_registries(sys.argv[1] if len(sys.argv) > 1 else 'registries_out'), indent=2))
