import json

import numpy as np
import pandas as pd

from tempo_fix import seen_flags as sf
from tempo_fix import qa_checks as qa
from tempo_fix import l3_pilot as l3
from tempo_fix import split_v2 as sv


def test_seen_flags_rules():
    train = pd.DataFrame({
        'enrollment_id': ['t1', 't2', 't3'], 'user_id': ['u1', 'u2', 'u2'], 'course_id': ['cA', 'cB', 'cA'],
        'offering_id': ['oA1', 'oB1', 'oA2'], 'offering_end_date': ['2019-01-31', '2019-06-30', '2019-12-31'],
    })
    ev = pd.DataFrame({
        'enrollment_id': ['e1', 'e2', 'e3'], 'user_id': ['u1', 'u3', 'u2'], 'course_id': ['cB', 'cA', 'cC'],
        'offering_id': ['oB9', 'oA9', 'oC9'], 'enroll_time': ['2020-01-01'] * 3, 'offering_end_date': ['2020-05-01'] * 3,
        'phase_id': ['P1', 'P1', 'P1'],
    })
    out = sf.compute_seen_flags(ev, train)
    assert out['seen_learner'].tolist() == [1, 0, 1]
    assert out['seen_course'].tolist() == [1, 1, 0]
    assert out['seen_offering'].tolist() == [0, 0, 0] and sf.qa15(out)
    assert out['joint_seen_status'].tolist() == ['SL_SC', 'UL_SC', 'SL_UC']
    slices = sf.subgroup_slices(out)
    assert slices[('LEARNER', 'SEEN')].sum() == 2
    # a train history ending after the cutoff must not count as seen
    train2 = train.assign(offering_end_date=['2020-04-30'] * 3)
    out2 = sf.compute_seen_flags(ev, train2)
    assert out2['seen_learner'].sum() == 0


def _fake_l2():
    rows = []
    vals = {'W1': (0.586045, 0.536872), 'W2': (0.695191, 0.579973), 'W3': (0.558751, 0.596628)}
    for w in ['W1', 'W2', 'W3']:
        for split in ['VALIDATION', 'TEST']:
            for p in ['P1', 'P2', 'P3', 'P4']:
                sperf, ssan = vals[w]
                rows.append({'window_id': w, 'eval_split': split, 'phase_id': p, 'macro_f1': 0.5, 'balanced_acc': 0.6,
                             'mcc': 0.3, 'kappa': 0.3, 'gmean': 0.4, 'pr_auc_macro': 0.45, 's_perf': sperf,
                             'accuracy': 0.9, 'weighted_f1': 0.9, 'roc_auc_macro_ovr': 0.8, 'log_loss': 0.3, 'brier': 0.1, 'ece': 0.05,
                             's_cal': 0.95, 's_san_plus_v2': ssan + 0.2,
                             'acctempo_m3': sperf ** 0.6 * ssan ** 0.4, 's_nan': 1.0, 's_maj_jsd': 0.99, 's_ent': 0.08,
                             's_drift': 0.99, 's_eff': 0.697, 's_leak': 0.45, 's_san_plus': ssan})
    return pd.DataFrame(rows)


def test_l3_pilot_rows_and_qa():
    l2 = _fake_l2()
    defaults = dict(task='CQ', label_rule_version='CQ_TRIAD_PROXIMITY_v1', label_threshold_set='PRIMARY',
                    feature_regime='CQ_RAW_EARLY', seed=42, cohort='FIXED', model_name='RNN')
    rows = l3.build_v0_rows(l2, defaults, run_ids={'W1': 'r1', 'W2': 'r2', 'W3': 'r3'},
                            provenance={'meta_schema_version': '1.1.0', 'split_version': 'v2'})
    assert len(rows) == 3 * 2 * 4 * 5 == 120
    assert rows['meta_obs_id'].is_unique and rows['rec_group_id'].nunique() == 120   # one pipeline per group so far
    assert (rows['acctempo_m3_delta'].dropna() == 0).all() and (rows['is_no_intervention'] == 1).all()
    ok03, _ = qa.qa03_delta_identity(rows); assert ok03
    ok20, _ = qa.qa20_unique_keys(rows); assert ok20
    ok18, det18 = qa.qa18_null_reasons(rows); assert ok18, det18.head()
    ok24, _ = qa.qa24_run_level_invariants(rows); assert ok24
    # subgroup rows without metrics are PARTIAL with NOT_COMPUTED reasons; ALL rows are COMPLETE
    assert set(rows.loc[rows.subgroup_axis == 'ALL', 'row_status']) == {'COMPLETE'}
    assert set(rows.loc[rows.subgroup_axis != 'ALL', 'row_status']) == {'PARTIAL'}
    nr = json.loads(rows.iloc[0]['null_reason_map'])
    assert nr['acctempo_m3_ref'] == 'NOT_APPLICABLE' and nr['macro_f1_ref'] == 'BASELINE_MISSING'
    # deterministic ids
    key = l3.meta_key(pipeline_id='V0', window_id='W1', phase_id='P1', eval_split='TEST', subgroup_axis='ALL', subgroup_value='ALL', **defaults)
    assert l3.meta_obs_id(key) == rows.loc[(rows.window_id == 'W1') & (rows.phase_id == 'P1') & (rows.eval_split == 'TEST') & (rows.subgroup_axis == 'ALL'), 'meta_obs_id'].item()
    assert l3.rec_group_id(key) == l3.rec_group_id({**key, 'pipeline_id': 'V14'})
    # column dictionary: every column gets a role except UNASSIGNED ones we can list
    d = l3.build_column_dictionary(rows)
    assert (d['role'] != '').all(), d[d.role == '']
    ok19, _ = qa.qa19_roles(rows, d); assert ok19
    # break a delta -> QA03 fails; break s_eff -> QA24 fails
    bad = rows.copy(); bad.loc[bad.index[0], 'macro_f1_delta'] = 0.01
    assert not qa.qa03_delta_identity(bad)[0]
    bad2 = rows.copy(); bad2.loc[bad2.index[0], 's_eff_after'] = 0.1
    assert not qa.qa24_run_level_invariants(bad2)[0]


def test_qa08_qa09_qa10():
    df = pd.DataFrame({
        'task': 'CQ', 'feature_regime': 'R', 'window_id': 'W1', 'cohort': 'FIXED', 'eval_split': 'TEST', 'subgroup_axis': 'ALL', 'subgroup_value': 'ALL',
        'phase_id': ['P1', 'P2', 'P3', 'P4'], 'ev_unavailable_rate': [0.75, 0.5, 0.25, 0.1],
        'ev_class_count_c0': [100] * 4, 'ev_class_count_c1': [5] * 4, 'ev_class_count_c2': [3] * 4,
        'tr_n_cells_total': [100] * 4, 'tr_n_cells_unavailable': [60, 40, 20, 5], 'tr_n_cells_eligible': [40, 60, 80, 95],
        'tr_n_cells_structural_absence': [10] * 4, 'tr_n_cells_observed_eligible': [30, 50, 70, 85],
        'tr_n_cells_observed_value': [20, 30, 50, 60], 'tr_n_cells_observed_missing': [10, 20, 20, 25],
    })
    assert qa.qa08_cell_accounting(df)[0] and qa.qa09_unavailable_monotone(df)[0] and qa.qa10_fixed_labels(df)[0]
    bad = df.copy(); bad.loc[1, 'ev_unavailable_rate'] = 0.9
    assert not qa.qa09_unavailable_monotone(bad)[0]
    bad2 = df.copy(); bad2.loc[2, 'ev_class_count_c2'] = 4
    assert not qa.qa10_fixed_labels(bad2)[0]
    bad3 = df.copy(); bad3.loc[0, 'tr_n_cells_eligible'] = 41
    assert not qa.qa08_cell_accounting(bad3)[0]


def test_run_all_summary(enrollments):
    offers = sv.summarize_offerings(enrollments)
    blk = sv.assign_blocks_v2(offers)
    audit = sv.audit_temporal_overlap(blk, enrollments=enrollments)
    l2 = _fake_l2()
    defaults = dict(task='CQ', label_rule_version='v1', label_threshold_set='PRIMARY', feature_regime='CQ_RAW_EARLY', seed=42, cohort='FIXED', model_name='RNN')
    rows = l3.build_v0_rows(l2, defaults, run_ids={'W1': 'r1', 'W2': 'r2', 'W3': 'r3'})
    summary = qa.run_all(rows, dictionary=l3.build_column_dictionary(rows), split_audit=audit)
    assert summary['QA03']['passed'] and summary['QA20']['passed'] and 'QA22' in summary
