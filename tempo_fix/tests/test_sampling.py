import math
from tempo_fix import sampling as sp


def test_ir_target_and_multiplier_arithmetic():
    counts = {'c0': 1576716, 'c1': 19394, 'c2': 13166}          # CQ W1 TRAIN (REPORT §7)
    t = sp.plan_targets(counts, ir_target=10).set_index('class')
    assert t.loc['c0', 'synthetic'] == 0 and t.loc['c0', 'binding'] == 'MAJORITY'
    assert t.loc['c1', 'n_target'] == math.ceil(1576716 / 10) == 157672
    assert abs(t.loc['c2', 'expansion'] - 157672 / 13166) < 1e-12 and abs(t.loc['c2', 'post_ir'] - 10) < 0.01
    k = sp.plan_targets(counts, k_max=10).set_index('class')
    assert k.loc['c2', 'n_target'] == 131660 and k.loc['c2', 'binding'] == 'K_MAX'
    both = sp.plan_targets(counts, ir_target=10, k_max=10).set_index('class')
    assert both.loc['c1', 'binding'] == 'IR_TARGET' and both.loc['c1', 'n_target'] == 157672   # x8.1 < cap
    assert both.loc['c2', 'binding'] == 'K_MAX' and both.loc['c2', 'n_target'] == 131660       # x12 capped at x10
    s = sp.summarize(sp.plan_targets(counts, ir_target=10))
    assert s['n_synthetic'] == (157672 - 19394) + (157672 - 13166) and abs(s["expansion_ratio"] - 1892060 / 1609276) < 1e-12


def test_no_oversampling_when_class_already_above_target():
    counts = {'c0': 2947015, 'c1': 8886, 'c2': 31441}            # LO population (June report)
    t = sp.plan_targets(counts, ir_target=100).set_index('class')
    assert t.loc['c2', 'binding'] == 'NONE' and t.loc['c2', 'synthetic'] == 0      # 31 441 > ceil(2 947 015/100)
    assert t.loc['c1', 'n_target'] == 29471
    g = sp.grid(counts, sp.DEFAULT_SCHEMES, dataset='LO')
    assert set(g['scheme_id']) == {s['scheme_id'] for s in sp.DEFAULT_SCHEMES}


def test_registry_primary_matches_decision():
    from tempo_fix import registries
    prim = registries.SAMPLING_STRATEGY['primary']
    assert prim['sampling_strategy_id'] == 'IR10_K10' and prim['ir_target'] == 10 and prim['max_expansion_per_class'] == 10
    counts = {'c0': 1576716, 'c1': 19394, 'c2': 13166}
    t = sp.targets_from_registry(counts, prim).set_index('class')
    assert t.loc['c1', 'n_target'] == 157672 and t.loc['c2', 'n_target'] == 131660
    lo = {'c0': 2947015, 'c1': 8886, 'c2': 31441}
    tl = sp.targets_from_registry(lo, prim).set_index('class')
    assert tl.loc['c1', 'binding'] == 'K_MAX' and abs(tl.loc['c1', 'post_ir'] - 33.165) < 0.01
    assert tl.loc['c2', 'binding'] == 'IR_TARGET' and tl.loc['c2', 'n_target'] == 294702
    chk = sp.check_synthetic_counts(counts, {'c0': 0, 'c1': 157672 - 19394, 'c2': 131660 - 13166}, prim)
    assert (chk['diff'] == 0).all()
    by = {r['pipeline_id']: r for r in registries.build_pipeline_registry()}
    assert by['V14']['balancer_params']['max_expansion_per_class'] == 10 and by['V14']['sampling_strategy_id'] == 'IR10_K10'
    # LO V3.1 train pools [V3.1 §6.1]: the k_max cap binds for both minority classes in every window
    ref = registries.SAMPLING_STRATEGY['reference_train_pools']['LO']
    for w, expect_ir in [('W1', (37.76, 272.09)), ('W2', (33.52, 101.55)), ('W3', (40.15, 121.47))]:
        t = sp.targets_from_registry(ref[w], prim).set_index('class')
        assert (t.loc[['c1', 'c2'], 'binding'] == 'K_MAX').all(), w
        assert abs(t.loc['c1', 'post_ir'] - expect_ir[0]) < 0.01 and abs(t.loc['c2', 'post_ir'] - expect_ir[1]) < 0.01, w
    t1 = sp.targets_from_registry(ref['W1'], prim).set_index('class')
    assert t1.loc['c2', 'n_target'] == 6550 and t1.loc['c1', 'n_target'] == 47200
