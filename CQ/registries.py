"""Provisional CQ static-field inventory; not a scientific approval of any feature."""
from copy import deepcopy
from LO.registries import STATIC_FEATURE_CONTRACT as LO_STATIC

_OBSERVED = (
    "ex_counts", "gender", "resource_count", "school_avg_bio_length_chars",
    "school_avg_motto_length_chars", "school_count", "split_rule_version",
    "teacher_avg_bio_length_chars", "teacher_count", "teacher_org_count",
    "timeline_source", "window_duration_seconds",
)
STATIC_FEATURE_CONTRACT = {
    "contract_id": "cq_static_feature_inventory_v1_pending_review",
    "status": "PROVISIONAL_POINT_IN_TIME_REVIEW_REQUIRED",
    "fields": {name: deepcopy(LO_STATIC["fields"][name]) for name in _OBSERVED},
    "course_fingerprint_fields": [name for name in LO_STATIC["course_fingerprint_fields"] if name in _OBSERVED],
    "note": "Describes observed historical layout; field availability and scientific disposition require review. "
            "split_rule_version appeared in old layouts although excluded by the current fit_layout.",
}
STATIC_FEATURE_CONTRACT["fields"]["primary_risk_set"] = {
    "definition": "CQ risk-set indicator; materializer currently writes constant 1.",
    "available": "materialization metadata; point-in-time contract requires review",
    "grain": "RELEASE", "disposition": "REVIEW",
}

# CQ V2.2 closure decisions.  These entries document how the already-locked
# metrics and QA23 review evidence are read; they do not alter historical
# model inputs or the preregistered metric calculation.
CQ_METRIC_AND_QA23_POLICY = {
    "policy_id": "cq_v2_2_metric_qa23_closure_20261023",
    "acctempo": {
        "meta_dataset_primary": "acctempo_m3_v1_jsd_base2_six_components",
        "paper_phase_trend_metrics": ("s_perf", "f1_macro", "balanced_accuracy"),
        "paper_composite_sensitivity": "acctempo_m4__s_cal_based",
        "rule": (
            "M3 remains the preregistered primary composite.  Paper phase trends and rankings "
            "must not be inferred from M3 alone because its entropy component can decrease as "
            "later-prefix predictions become more certain."
        ),
    },
    "qa23_reviewed_behavioural_bases": {
        "status": "APPROVED_PREFIX_OBSERVED_BEHAVIOUR",
        "bases": (
            "problem_count", "exercise_count", "problem_context_count", "score_sum",
            "correct_problem_count", "attempts_sum", "problem_catalog_coverage",
            "problem_score_catalog_coverage",
        ),
        "required_review_note": "reviewed_prefix_observed_behaviour__not_label_derived",
        "rule": (
            "Retain only prefix-observed values available by the prediction cutoff.  Their label "
            "association is reported in QA23 linkage facts; no label-derived final-distance field "
            "may enter imputation or model predictors."
        ),
    },
}
