import numpy as np
import pandas as pd
import pytest

from tempo_fix import split_v2 as sv


def test_windows_match_plan_table6():
    w = sv.windows_from_blocks(3)
    assert w['W1'] == {'TRAIN': ['A'], 'VALIDATION': ['B'], 'TEST': ['C']}
    assert w['W2'] == {'TRAIN': ['A', 'B', 'C'], 'VALIDATION': ['D'], 'TEST': ['E']}
    assert w['W3'] == {'TRAIN': ['A', 'B', 'C', 'D', 'E'], 'VALIDATION': ['F'], 'TEST': ['G']}


def test_v2_recut_is_time_ordered_and_passes_qa22(enrollments):
    offers = sv.summarize_offerings(enrollments)
    blk = sv.assign_blocks_v2(offers, train_share=0.6, n_slices=3, seed=0)
    assert set(blk['block']) == set('ABCDEFG')
    # A ≈ 60% of enrollments, decided at offering level
    share_a = blk.loc[blk.block == 'A', 'n_enrollments'].sum() / blk['n_enrollments'].sum()
    assert 0.55 <= share_a <= 0.65
    # end-date ordering across slices
    end_max = blk.groupby('slice_id')['offering_end_date'].max()
    end_min = blk.groupby('slice_id')['offering_end_date'].min()
    for s in range(0, 3):
        assert end_max[s] <= end_min[s + 1]
    audit = sv.audit_temporal_overlap(blk, enrollments=enrollments)
    assert audit['end_order_ok'].all()
    ok, table = sv.qa22(audit)                            # label-time ordering + non-empty eval sets
    assert ok and (table['n_enrollments_test'] > 0).all() and 'tau_w' in table
    # overlap is reported, never gated (2026-09-28 revision)
    ok2, table2 = sv.qa22(audit, overlap_threshold=0.0)
    assert ok2 and table2['overlap_flag'].all()
    # stratification inside a slice: rare-class counts of the two blocks are close
    for v, t in (('B', 'C'), ('D', 'E'), ('F', 'G')):
        rv = blk.loc[blk.block == v, ['n_c1', 'n_c2']].sum().sum()
        rt = blk.loc[blk.block == t, ['n_c1', 'n_c2']].sum().sum()
        assert 0.7 <= rv / rt <= 1.3, (v, t, rv, rt)
    # manifest covers every offering in every window
    man = sv.split_manifest(blk)
    assert len(man) == 3 * len(blk)
    assert set(man['split']) <= {'TRAIN', 'VALIDATION', 'TEST', 'UNUSED'}


def test_v1_like_stratified_split_fails_qa22(enrollments):
    """Reproduce the stage-1 situation: future pool cut into six equal stratified blocks ignoring time."""
    offers = sv.summarize_offerings(enrollments)
    blk = sv.assign_blocks_v2(offers, train_share=0.6, n_slices=3, seed=0)
    rng = np.random.default_rng(3)
    pool_idx = blk.index[blk.block != 'A']
    letters = np.array(list('BCDEFG'))
    shuffled = rng.permutation(pool_idx)
    blk_v1 = blk.copy()
    blk_v1.loc[shuffled, 'block'] = letters[np.arange(len(shuffled)) % 6]
    audit = sv.audit_temporal_overlap(blk_v1, enrollments=enrollments)
    assert audit.loc[audit.window_id == 'W1', 'end_order_ok'].item()          # A precedes everything
    assert not audit.loc[audit.window_id.isin(['W2', 'W3']), 'end_order_ok'].any()
    ok, _ = sv.qa22(audit)
    assert not ok


def test_embargo_exclusions_and_tables(enrollments):
    offers = sv.summarize_offerings(enrollments)
    blk = sv.assign_blocks_v2(offers, seed=0)
    ex = sv.embargo_exclusions(blk, gap_days=30)
    assert set(ex.columns) == {'window_id', 'offering_id', 'reason'}
    tbl = sv.block_label_table(blk)
    assert 'Tổng' in tbl.index and abs(tbl.loc['Tổng', 'n_c0_pct'] + tbl.loc['Tổng', 'n_c1_pct'] + tbl.loc['Tổng', 'n_c2_pct'] - 100) < 1e-9
    wt = sv.window_label_table(blk)
    assert len(wt) == 9
    assert (offers['inferred_timeline_share'].between(0, 1)).all()


def test_strict_flags_temporal_profile_and_boundaries(enrollments):
    offers = sv.summarize_offerings(enrollments)
    blk = sv.assign_blocks_v2(offers, seed=0)
    audit = sv.audit_temporal_overlap(blk, enrollments=enrollments)
    tau = dict(zip(audit['window_id'], audit['tau_w']))
    man = sv.split_manifest(blk)
    ev = enrollments.merge(man[man['split'].isin(['VALIDATION', 'TEST'])][['window_id', 'offering_id', 'split']], on='offering_id')
    ev = ev.rename(columns={'split': 'eval_split'})
    rows = pd.concat([ev.assign(phase_id=p) for p in ['P1', 'P2', 'P3', 'P4']], ignore_index=True)
    fl = sv.strict_flags(rows, tau)
    assert set(fl['subgroup_value']) <= {'STRICT', 'OVERLAP'}
    tab = sv.strict_share_table(fl)
    # strict share is non-decreasing in phase within each window x split
    for (w, sp), g in tab.groupby(['window_id', 'eval_split']):
        v = g.set_index('phase_id').reindex(['P1', 'P2', 'P3', 'P4'])['strict_share'].to_numpy()
        assert np.all(np.diff(v) >= -1e-12), (w, sp, v)
    # P1 strict share equals 1 - overlap share reported by the audit (same definition)
    a1 = audit.set_index('window_id')
    for w in ['W1', 'W2', 'W3']:
        p1 = tab[(tab.window_id == w) & (tab.eval_split == 'TEST') & (tab.phase_id == 'P1')]['strict_share'].item()
        assert abs((1 - p1) - a1.loc[w, 'test_train_overlap_share']) < 1e-9
    prof = sv.temporal_profile(offers)
    assert {'straddle_share_if_boundary_here', 'cum_enrollment_share_ended'} <= set(prof.columns) and len(prof) > 12
    dur = sv.duration_summary(offers)
    assert 'share_ending_at_data_end' in dur and dur['dur_p50'].between(60, 200).all()
    bds, cand = sv.choose_boundaries(offers, n_slices=3, min_slice_share=0.08)
    assert len(bds) == 2 and cand['feasible'].any()
    blk2 = sv.assign_blocks_v2(offers, boundaries=bds)
    audit2 = sv.audit_temporal_overlap(blk2, enrollments=enrollments)
    assert audit2['end_order_ok'].all() and sv.qa22(audit2)[0]
    # boundaries are respected: slice end dates never cross a boundary
    for sid, bd in zip([1, 2], bds):
        assert blk2.loc[blk2.slice_id == sid, 'offering_end_date'].max() <= bd
        assert blk2.loc[blk2.slice_id == sid + 1, 'offering_end_date'].min() > bd


def test_test_side_purge_removes_overlap(enrollments):
    offers = sv.summarize_offerings(enrollments)
    blk = sv.assign_blocks_v2(offers, seed=0)
    audit0 = sv.audit_temporal_overlap(blk, enrollments=enrollments)
    excl = sv.remedy_exclusions(blk, 'TEST_SIDE_PURGE')
    audit1 = sv.audit_temporal_overlap(blk, enrollments=enrollments, exclusions=excl)
    assert (audit1['ev_train_overlap_share'] == 0).all() and audit1['end_order_ok'].all()
    assert (audit1['days_train_end_to_test_start'] >= 0).all()
    ok, table = sv.qa22(audit1)
    assert ok
    assert (audit1['n_purged_train'] == 0).all() and (audit1['purged_enrollment_share_test'] > 0).all()
    man = sv.split_manifest(blk, exclusions=excl)
    assert (man['split'] == 'PURGED').sum() == len(excl)
    # train-side embargo alternative reduces but need not eliminate overlap
    assert len(sv.remedy_exclusions(blk)) == 0                      # default: no purge
    emb = sv.remedy_exclusions(blk, 'TRAIN_EMBARGO', gap_days=120)
    audit2 = sv.audit_temporal_overlap(blk, enrollments=enrollments, exclusions=emb)
    assert (audit2['ev_train_overlap_share'] <= audit0['ev_train_overlap_share'] + 1e-12).all()
    assert (audit2['n_purged_train'] > 0).any()


def test_shared_boundaries_align_two_tasks_and_rarest_first(enrollments):
    offers = sv.summarize_offerings(enrollments)
    blk_cq = sv.assign_blocks_v2(offers, seed=0)
    sb = sv.slice_boundaries(blk_cq)
    # a second "task" with a different labelled population (drop 15% of enrollments at random)
    rng = np.random.default_rng(5)
    enr_lo = enrollments[rng.random(len(enrollments)) > 0.15]
    offers_lo = sv.summarize_offerings(enr_lo)
    blk_lo = sv.assign_blocks_v2(offers_lo, boundaries=sb['boundaries'], a_boundary=sb['a_boundary'])
    sb_lo = sv.slice_boundaries(blk_lo)
    # A ends at the same calendar date for both tasks; slice ends never exceed the shared boundaries
    assert sb_lo['a_boundary'] <= sb['a_boundary']
    for k in range(2):
        assert sb_lo['boundaries'][k] <= sb['boundaries'][k]
    a_cq = sv.audit_temporal_overlap(blk_cq, enrollments=enrollments).set_index('window_id')
    a_lo = sv.audit_temporal_overlap(blk_lo, enrollments=enr_lo).set_index('window_id')
    for w in ['W1', 'W2', 'W3']:
        assert abs((a_cq.loc[w, 'tau_w'] - a_lo.loc[w, 'tau_w']).days) <= 31      # same calendar windows
    assert sv.qa22(a_lo.reset_index())[0]
    # rarest_first pairing balances the scarcest class at least as well as balanced pairing on this data
    blk_rf = sv.assign_blocks_v2(offers, seed=0, pairing='rarest_first')
    def imbalance(blk, col):
        out = []
        for v, t_ in (('B', 'C'), ('D', 'E'), ('F', 'G')):
            a, b = blk.loc[blk.block == v, col].sum(), blk.loc[blk.block == t_, col].sum()
            out.append(abs(a - b) / max(a + b, 1))
        return max(out)
    rare_col = 'n_c1' if offers['n_c1'].sum() < offers['n_c2'].sum() else 'n_c2'
    assert imbalance(blk_rf, rare_col) <= imbalance(blk_cq, rare_col) + 0.05
