import numpy as np
import pandas as pd

from tempo_fix import feature_dictionary as fd

REPORT_FEATURES = [
    'segment_duration_seconds', 'avg_segment_duration', 'avg_real_watch_time', 'unique_video_count', 'course_video_count',
    'video_catalog_coverage', 'segment_count', 'video_active_day_count', 'video_events_per_active_day', 'avg_playback_speed',
    'var_playback_speed', 'fast_forward_ratio', 'session_duration_std', 'first_video_day_from_enroll', 'problem_count',
    'exercise_count', 'problem_context_count', 'score_sum', 'score_mean', 'score_fraction_mean', 'score_fraction_std',
    'correct_problem_count', 'incorrect_problem_count', 'correct_ratio', 'attempts_sum', 'attempts_mean',
    'problem_catalog_coverage', 'problem_score_catalog_coverage', 'comment_count', 'unique_commented_resource_count',
    'gender', 'year_of_birth', 'age_at_enroll', 'resource_count', 'teacher_count', 'video_observed_mask',
    'problem_observed_mask', 'user_id', 'course_id', 'coelo_partial', 'CQ_proximity_final',
]


def test_classification_rules():
    d = fd.build_feature_dictionary(REPORT_FEATURES)
    by = d.set_index('column_name')
    for c in ['video_catalog_coverage', 'problem_catalog_coverage', 'problem_score_catalog_coverage', 'score_fraction_mean', 'correct_ratio']:
        assert by.loc[c, 'is_label_proxy'] == 1 and by.loc[c, 'regimes_included'] == 'CQ_REDUCED_DIRECT', c
    for c in ['segment_count', 'attempts_sum', 'score_sum', 'comment_count', 'avg_real_watch_time']:
        assert by.loc[c, 'is_label_proxy'] == 0 and 'CQ_RAW_EARLY' in by.loc[c, 'regimes_included'], c
    assert by.loc['coelo_partial', 'regimes_included'] == 'CQ_EARLY_COMPONENT'
    assert by.loc['CQ_proximity_final', 'role'] == 'LABEL'
    assert by.loc['user_id', 'role'] == 'KEY' and by.loc['video_observed_mask', 'role'] == 'MASK'
    assert by.loc['gender', 'block'] == 'STATIC'
    # fast_forward_ratio is a behavioural ratio, not a label component: stays RAW unless overridden
    assert by.loc['fast_forward_ratio', 'is_label_proxy'] == 0
    raw = fd.regime_columns(d, 'CQ_RAW_EARLY')
    assert 'video_catalog_coverage' not in raw and 'segment_count' in raw
    preds = fd.imputer_predictor_columns(d, 'CQ_REDUCED_DIRECT')
    assert 'video_catalog_coverage' not in preds and 'gender' in preds


def test_override_and_audit_flags_hidden_proxy():
    rng = np.random.default_rng(0)
    n = 5000
    g = rng.beta(1, 8, n)                                  # cq_score_g_final-like, skewed
    df = pd.DataFrame({
        'cq_score_g_final': g,
        'segment_count': rng.poisson(5, n) * 1.0,          # unrelated
        'hidden_ratio_feature': g * 0.9 + rng.normal(0, 0.02, n),   # strongly related but not caught by patterns
        'video_catalog_coverage': g + rng.normal(0, 0.05, n),
    })
    feats = ['segment_count', 'hidden_ratio_feature', 'video_catalog_coverage']
    d = fd.build_feature_dictionary(feats, overrides={'segment_count': {'proxy_review_note': 'raw count, keep'}})
    audit = fd.audit_label_proxy(df, feats, 'cq_score_g_final', dictionary=d, rho_threshold=0.5)
    a = audit.set_index('column_name')
    assert a.loc['hidden_ratio_feature', 'needs_review']            # high |rho|, not flagged by rule
    assert not a.loc['video_catalog_coverage', 'needs_review']      # already flagged by rule
    assert not a.loc['segment_count', 'needs_review']
    assert a.loc['hidden_ratio_feature', 'nmi'] > a.loc['segment_count', 'nmi']
    ok, det = fd.qa23(audit, d, 'CQ_RAW_EARLY', imputer_predictors=['segment_count'])
    assert not ok and det['unreviewed'] == ['hidden_ratio_feature']
    d2 = fd.build_feature_dictionary(feats, overrides={'hidden_ratio_feature': {'is_label_proxy': 1, 'regimes_included': 'CQ_REDUCED_DIRECT', 'proxy_review_note': 'reviewed: derived ratio'}})
    audit2 = fd.audit_label_proxy(df, feats, 'cq_score_g_final', dictionary=d2)
    ok2, det2 = fd.qa23(audit2, d2, 'CQ_RAW_EARLY', imputer_predictors=['segment_count'])
    assert ok2, det2
    ok3, det3 = fd.qa23(audit2, d2, 'CQ_RAW_EARLY', imputer_predictors=['segment_count', 'video_catalog_coverage'])
    assert not ok3 and det3['proxy_in_imputer_predictors'] == ['video_catalog_coverage']
