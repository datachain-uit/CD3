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
