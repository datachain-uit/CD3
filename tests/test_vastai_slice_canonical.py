import numpy as np
import pandas as pd
from tools.vastai_audit_shared import _slice_rows
from metrics_core.evaluation import classification_metrics

def test_slice_all_uses_parent_contract():
    frame = pd.DataFrame({'y_true':['c0','c1','c2','c0'], 'prob_c0':[.8,.1,.1,.7],
        'prob_c1':[.1,.8,.2,.2], 'prob_c2':[.1,.1,.7,.1], 'temporal_strict_P1':[1,1,0,0]})
    counts = np.array([50,30,20])
    rows = _slice_rows(frame, task='CQ', window='W1', pipeline='V2', model='GRU', seed=42,
                       split='TEST', phase='P1', train_class_counts=counts, s_eff=.7, s_leak=.6)
    allrow = rows[0]
    expected = classification_metrics(np.array([0,1,2,0]), frame[['prob_c0','prob_c1','prob_c2']].to_numpy(),
                                      train_class_counts=counts, s_eff=.7, s_leak=.6)
    for name in ('s_leak','s_eff','s_drift','s_san_plus','acctempo_m3','macro_f1'):
        assert np.isclose(allrow[name], expected[name])
    assert all(r['s_leak']==.6 and r['s_eff']==.7 for r in rows)
    assert sum(r['n_eval_samples'] for r in rows[1:]) == allrow['n_eval_samples']
