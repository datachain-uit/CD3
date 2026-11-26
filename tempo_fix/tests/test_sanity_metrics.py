import math
import numpy as np
import pytest

from tempo_fix import sanity as sn
from tempo_fix import metrics_extra as mx


def test_reproduces_report_w1_p1_numbers():
    comp = [1.000000, 0.992046, 0.076604, 0.999927, 0.697147, 0.452014]
    ssan, at_floor = sn.geometric_mean(comp, eps_floor=1e-3)
    assert abs(ssan - 0.536872) < 1e-5 and at_floor == 0
    acc = sn.acctempo_m3(0.586045, ssan)
    assert abs(acc - 0.565857) < 1e-5
    assert abs(sn.s_leak_from_auc(0.773993) - 0.452014) < 1e-6
    # s_ent = 0.076604 <-> median normalised entropy 0.0383
    P = np.tile([[0.99, 0.005, 0.005]], (101, 1))
    m = float(np.median(sn.normalised_entropy(P)))
    assert sn.s_ent_v1(P) == pytest.approx(1 - min(abs(m - 0.5) / 0.5, 1))
    dec = sn.log_decomposition(0.586045, 0.536872, 0.676861, 0.507194)
    assert dec['log_delta_total'] == pytest.approx(math.log(0.603072) - math.log(0.565857), abs=2e-6)


def test_s_cal_rewards_calibrated_confident_model():
    rng = np.random.default_rng(0)
    n = 20000
    y = (rng.random(n) < 0.05).astype(int)              # 95% majority class 0
    P = np.zeros((n, 3))
    # perfectly calibrated & confident: p(class0)=0.95 for everyone
    P[:, 0] = 0.95; P[:, 1] = 0.05; P[:, 2] = 1e-9
    P /= P.sum(1, keepdims=True)
    s_ent = sn.s_ent_v1(P)
    s_cal = sn.s_cal_v2(P, y)
    assert s_ent < 0.40            # v1 penalises the confident (correct) model
    assert s_cal > 0.97            # v2 recognises calibration
    assert 0 <= sn.ece_top_label(P, y) < 0.03


def test_components_and_floor():
    rng = np.random.default_rng(1)
    y = rng.integers(0, 3, 500)
    P = rng.dirichlet([1, 1, 1], 500)
    r = sn.compute_sanity(P, y, train_prior_counts=[400, 60, 40], s_eff_value=0.7, s_leak_value=0.0)
    assert r.s_nan == 1.0 and 0 <= r.s_maj_jsd <= 1 and 0 <= r.s_drift <= 1
    assert r.n_at_floor_v1 == 1 and r.n_at_floor_v2 == 1      # s_leak = 0 hits the floor
    assert abs(sn.jsd_base2([1, 0, 0], [0, 1, 0]) - 1.0) < 1e-12
    assert sn.s_nan(np.array([[0.5, 0.6, 0.0]])) == 0.0
    b = sn.acctempo_bundle(0.6, r)
    assert set(b) == {'s_perf', 'acctempo_m3', 'acctempo_m3_v2'}


def test_overall_and_per_class_metrics_and_bootstrap():
    rng = np.random.default_rng(2)
    n = 3000
    y = rng.choice(3, n, p=[0.9, 0.06, 0.04])
    logits = rng.normal(0, 1, (n, 3)); logits[np.arange(n), y] += 2.0
    P_after = np.exp(logits) / np.exp(logits).sum(1, keepdims=True)
    noisy = logits + rng.normal(0, 2.0, logits.shape)
    P_before = np.exp(noisy) / np.exp(noisy).sum(1, keepdims=True)
    m = mx.overall_metrics(y, P_after)
    assert 0 < m['macro_f1'] <= 1 and 0 < m['pr_auc_macro'] <= 1 and 0 < m['roc_auc_macro_ovr'] <= 1
    assert abs(m['s_perf'] - sn.s_perf(m['macro_f1'], m['balanced_acc'], m['mcc'], m['kappa'])) < 1e-12
    pc = mx.per_class_metrics(y, P_after.argmax(1), P_after)
    assert pc['c0']['support'] + pc['c1']['support'] + pc['c2']['support'] == n
    # absent class -> NULL recall, not 0
    pc2 = mx.per_class_metrics(np.zeros(10, int), np.zeros(10, int), None)
    assert math.isnan(pc2['c1']['recall']) and pc2['c1']['support'] == 0
    bs = mx.paired_bootstrap_delta(y, P_after, P_before, mx.macro_f1_fn, B=200, seed=0)
    assert bs['delta_ci_low'] <= bs['delta'] <= bs['delta_ci_high']
    assert bs['delta'] > 0 and bs['delta_p_boot_le0'] < 0.05
