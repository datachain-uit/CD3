# -*- coding: utf-8 -*-
"""split_version = v2: time-ordered block re-cut and temporal-overlap audit (PLAN v1.6 §2.2, §5.4, QA22).

Design
------
* Block A  = earliest offerings (by offering_end_date) holding ``train_share`` of all enrollments.
* Future pool (remaining offerings, sorted by offering_end_date) is cut into ``n_slices`` consecutive
  time slices T1 < T2 < ... of roughly equal enrollment mass.
* Inside each slice, offerings are split into two blocks (VALIDATION, TEST) by a deterministic greedy
  stratification that balances rare-class enrollment counts and offering size. Stratification never
  crosses a slice boundary, so every TRAIN offering ends no later than every VALIDATION/TEST offering
  of the same window (QA22 end-date ordering).
* Windows follow PLAN Table 6:  W1 = A | B | C,  W2 = A+B+C | D | E,  W3 = A..E | F | G.

The module also audits any existing split (e.g. split_manifest_v1) with ``audit_temporal_overlap``.

Revision 2026-09-28 (SPLIT_V2_QA_INCIDENT_REPORT): the hard temporal rule is *label-time ordering*
(every TRAIN offering ends no later than every VALIDATION/TEST offering of the window) plus one
offering per split. Calendar overlap between concurrent offerings is inherent to MOOC data, so the
P1-cutoff overlap share is REPORTED (ev_train_overlap_share) but no longer gated, and no purge is
applied to the primary split (purge_mode = NONE). Strict temporal validity is evaluated as a slice
instead: subgroup axis TEMPORAL with values STRICT (cutoff_k >= tau_w) / OVERLAP, computed per
(enrollment, phase) from stored predictions (``strict_flags``). ``temporal_profile`` and
``choose_boundaries`` help pick slice boundaries at natural gaps when they exist.

Inputs are pandas DataFrames; column names are configurable via ``SplitSchema``.
"""
from __future__ import annotations

import argparse
import string
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


@dataclass
class SplitSchema:
    enrollment_id: str = 'enrollment_id'
    offering_id: str = 'offering_id'
    course_id: str = 'course_id'
    user_id: str = 'user_id'
    enroll_time: str = 'enroll_time'
    offering_start: str = 'offering_start_date'
    offering_end: str = 'offering_end_date'
    label: str = 'label'                    # class code column (c0/c1/c2 or W/A/G)
    timeline_source: str = 'timeline_source'
    classes: Tuple[str, ...] = ('c0', 'c1', 'c2')
    rare_classes: Tuple[str, ...] = ('c1', 'c2')   # minority classes used for stratification


PHASE_Q = {'P1': 0.25, 'P2': 0.50, 'P3': 0.75, 'P4': 0.90}


# ---------------------------------------------------------------------------------------------
# 1. Offering summary from enrollment-level data
# ---------------------------------------------------------------------------------------------
def summarize_offerings(enrollments: pd.DataFrame, schema: SplitSchema = SplitSchema()) -> pd.DataFrame:
    """One row per offering: dates, n_enrollments, per-class counts, inferred-timeline share."""
    s = schema
    df = enrollments.copy()
    df[s.offering_start] = pd.to_datetime(df[s.offering_start])
    df[s.offering_end] = pd.to_datetime(df[s.offering_end])
    g = df.groupby(s.offering_id, sort=False)
    out = g.agg(**{
        'course_id': (s.course_id, 'first') if s.course_id in df else (s.offering_id, 'first'),
        'offering_start_date': (s.offering_start, 'min'),
        'offering_end_date': (s.offering_end, 'max'),
        'n_enrollments': (s.enrollment_id, 'count'),
    }).reset_index().rename(columns={s.offering_id: 'offering_id'})
    for c in s.classes:
        cnt = df[df[s.label] == c].groupby(s.offering_id)[s.enrollment_id].count()
        out[f'n_{c}'] = out['offering_id'].map(cnt).fillna(0).astype(int)
    if s.timeline_source in df:
        inf = df.assign(_inf=(df[s.timeline_source] != 'course_specific_timeline').astype(int)) \
                .groupby(s.offering_id)['_inf'].mean()
        out['inferred_timeline_share'] = out['offering_id'].map(inf).fillna(0.0)
    return out


# ---------------------------------------------------------------------------------------------
# 2. Block assignment v2
# ---------------------------------------------------------------------------------------------
def _greedy_pair_split(slice_df: pd.DataFrame, rare_cols: Sequence[str], rng: np.random.Generator,
                       pairing: str = 'balanced') -> np.ndarray:
    """Split offerings of one slice into two blocks (0/1) balancing rare-class counts and size.

    Greedy: offerings are visited from the most rare-label-rich (then largest) to the smallest; each
    goes to the block with the larger normalised deficit. Deterministic given ``rng`` (ties only).
    pairing='balanced' weighs every rare class equally (default, used for the locked V2.1 registry);
    pairing='rarest_first' multiplies each rare class by the inverse of its slice share, so the scarcest
    class (e.g. LO class E) dominates the assignment — use when a class has very few enrollments."""
    dims = list(rare_cols) + ['n_enrollments']
    V = slice_df[dims].to_numpy(dtype=float)
    totals = V.sum(axis=0)
    totals[totals == 0] = 1.0
    Vn = V / totals                                        # normalised contribution per dimension
    if pairing == 'rarest_first':
        n_all = slice_df['n_enrollments'].sum()
        shares = np.array([max(slice_df[c].sum() / max(n_all, 1), 1e-9) for c in rare_cols] + [1.0])
        w = 1.0 / shares
        w = w / w.max()
        Vn = Vn * w                                         # scarce classes weigh more in the cost
    priority = Vn[:, :-1].sum(axis=1) * 10 + Vn[:, -1]     # rare classes weigh more than size
    order = np.lexsort((rng.random(len(V)), -priority))
    T = np.zeros((2, len(dims)))
    assign = np.zeros(len(V), dtype=int)
    for i in order:
        cost = [np.abs((T[b] + Vn[i]) - T[1 - b]).sum() for b in (0, 1)]
        b = int(np.argmin(cost)) if cost[0] != cost[1] else int(rng.integers(0, 2))
        assign[i] = b
        T[b] += Vn[i]
    return assign


def assign_blocks_v2(offerings: pd.DataFrame, train_share: float = 0.60, n_slices: int = 3,
                     schema: SplitSchema = SplitSchema(), seed: int = 0,
                     boundaries: Optional[Sequence] = None, a_boundary=None,
                     pairing: str = 'balanced') -> pd.DataFrame:
    """Return offerings with columns block (A..G), slice_id (0 = A, 1..n_slices), pair_role.

    ``offerings`` must contain offering_id, offering_start_date, offering_end_date, n_enrollments and
    n_<class> columns (see summarize_offerings). By default the future pool is cut into ``n_slices``
    slices of equal enrollment mass by offering_end_date; pass ``boundaries`` (n_slices - 1 end-date
    timestamps, e.g. from choose_boundaries) to cut at explicit calendar dates instead."""
    rare_cols = [f'n_{c}' for c in schema.rare_classes]
    df = offerings.copy()
    df['offering_start_date'] = pd.to_datetime(df['offering_start_date'])
    df['offering_end_date'] = pd.to_datetime(df['offering_end_date'])
    df = df.sort_values(['offering_end_date', 'offering_start_date', 'offering_id'], kind='mergesort') \
           .reset_index(drop=True)
    total = df['n_enrollments'].sum()
    cum_before = df['n_enrollments'].cumsum() - df['n_enrollments']
    if a_boundary is not None:      # shared calendar boundary for A (align tasks): A = offerings ending <= a_boundary
        is_train = df['offering_end_date'] <= pd.Timestamp(a_boundary)
    else:
        is_train = (cum_before / total) < train_share
    df['slice_id'] = 0
    df['block'] = ''
    df.loc[is_train, 'block'] = 'A'

    pool = df.loc[~is_train].copy()
    if boundaries is not None:
        bds = sorted(pd.to_datetime(list(boundaries)))
        if len(bds) != n_slices - 1:
            raise ValueError(f'need {n_slices - 1} boundaries, got {len(bds)}')
        slice_id = 1 + np.searchsorted(np.array(bds, dtype='datetime64[ns]'), pool['offering_end_date'].to_numpy(dtype='datetime64[ns]'), side='right')
        pool['slice_id'] = slice_id
    else:
        pool_total = pool['n_enrollments'].sum()
        pool_cum_before = pool['n_enrollments'].cumsum() - pool['n_enrollments']
        slice_id = np.minimum(n_slices - 1, np.floor(pool_cum_before / (pool_total / n_slices))).astype(int) + 1
        pool['slice_id'] = slice_id.values
    rng = np.random.default_rng(seed)
    letters = list(string.ascii_uppercase[1:1 + 2 * n_slices])   # B, C, D, E, F, G, ...
    for sid in range(1, n_slices + 1):
        idx = pool.index[pool['slice_id'] == sid]
        assign = _greedy_pair_split(pool.loc[idx], rare_cols, rng, pairing=pairing)
        val_letter, test_letter = letters[2 * (sid - 1)], letters[2 * (sid - 1) + 1]
        pool.loc[idx, 'block'] = np.where(assign == 0, val_letter, test_letter)
    df.loc[pool.index, ['slice_id', 'block']] = pool[['slice_id', 'block']]
    df['pair_role'] = np.where(df['block'] == 'A', 'TRAIN_BASE',
                               np.where(df['block'].isin(letters[0::2]), 'VALIDATION_OF_SLICE', 'TEST_OF_SLICE'))
    return df


def slice_boundaries(blocks: pd.DataFrame) -> Dict[str, object]:
    """Calendar boundaries realised by an existing block table, to re-use for another task so that both
    tasks share the same tau_w: a_boundary = latest end in A; boundaries = latest end of slices 1..n-1."""
    b = blocks.copy()
    b['offering_end_date'] = pd.to_datetime(b['offering_end_date'])
    a_boundary = b.loc[b['slice_id'] == 0, 'offering_end_date'].max()
    n_slices = int(b['slice_id'].max())
    bds = [b.loc[b['slice_id'] == k, 'offering_end_date'].max() for k in range(1, n_slices)]
    return {'a_boundary': a_boundary, 'boundaries': bds, 'n_slices': n_slices}


def windows_from_blocks(n_slices: int = 3) -> Dict[str, Dict[str, List[str]]]:
    """PLAN Table 6 generalised: W_k trains on A + all blocks of earlier slices."""
    letters = list(string.ascii_uppercase[1:1 + 2 * n_slices])
    windows = {}
    for k in range(1, n_slices + 1):
        train = ['A'] + letters[:2 * (k - 1)]
        windows[f'W{k}'] = {'TRAIN': train, 'VALIDATION': [letters[2 * (k - 1)]], 'TEST': [letters[2 * (k - 1) + 1]]}
    return windows


def split_manifest(blocks: pd.DataFrame, windows: Optional[Dict[str, Dict[str, List[str]]]] = None,
                   split_version: str = 'v2', exclusions: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """Long manifest: one row per (window, offering) with its split role, UNUSED, or PURGED (+ reason)."""
    windows = windows or windows_from_blocks()
    excl = {}
    if exclusions is not None and len(exclusions):
        excl = {(r.window_id, r.offering_id): r.reason for r in exclusions.itertuples()}
    rows = []
    for w, roles in windows.items():
        role_of = {b: r for r, bl in roles.items() for b in bl}
        for _, o in blocks.iterrows():
            split = role_of.get(o['block'], 'UNUSED')
            reason = excl.get((w, o['offering_id']))
            if reason:
                split = 'PURGED'
            rows.append({'split_version': split_version, 'window_id': w, 'offering_id': o['offering_id'],
                         'block': o['block'], 'split': split, 'purge_reason': reason})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------------------------
# 3. Temporal-overlap audit (works for v1 and v2 manifests)
# ---------------------------------------------------------------------------------------------
def _cutoff(start: pd.Series, end: pd.Series, q: float) -> pd.Series:
    return start + (end - start) * q


def audit_temporal_overlap(blocks: pd.DataFrame, windows: Optional[Dict[str, Dict[str, List[str]]]] = None,
                           enrollments: Optional[pd.DataFrame] = None, schema: SplitSchema = SplitSchema(),
                           q_first: float = PHASE_Q['P1'], exclusions: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """Per-window calendar diagnostics required by PLAN §5.4 and QA22.

    blocks: offerings with block, offering_start_date, offering_end_date, n_enrollments.
    enrollments (optional): enrollment-level table to compute exact P1 cutoffs
    (cutoff = enroll_time + q * (offering_end - enroll_time), REPORT §4); otherwise the offering-level
    approximation start + q*(end-start) weighted by n_enrollments is used.
    exclusions (optional): rows (window_id, offering_id, reason) produced by ``purge_exclusions`` /
    ``embargo_exclusions``; excluded offerings are removed from the window before the statistics are
    computed and their count / enrollment share is reported (n_purged_*, purged_enrollment_share_*).
    """
    windows = windows or windows_from_blocks()
    b = blocks.copy()
    b['offering_start_date'] = pd.to_datetime(b['offering_start_date'])
    b['offering_end_date'] = pd.to_datetime(b['offering_end_date'])
    if enrollments is not None:
        e = enrollments[[schema.enrollment_id, schema.offering_id, schema.enroll_time, schema.offering_end]].copy()
        e[schema.enroll_time] = pd.to_datetime(e[schema.enroll_time])
        e[schema.offering_end] = pd.to_datetime(e[schema.offering_end])
        e['cutoff_p1'] = _cutoff(e[schema.enroll_time], e[schema.offering_end], q_first)
        e = e.merge(b[['offering_id', 'block']], left_on=schema.offering_id, right_on='offering_id', how='inner')
    rows = []
    for w, roles in windows.items():
        excl = set()
        if exclusions is not None and len(exclusions):
            excl = set(exclusions.loc[exclusions['window_id'] == w, 'offering_id'])
        bw = b[~b['offering_id'].isin(excl)]
        tr = bw[bw['block'].isin(roles['TRAIN'])]
        va = bw[bw['block'].isin(roles['VALIDATION'])]
        te = bw[bw['block'].isin(roles['TEST'])]
        if len(tr) == 0 or len(va) == 0 or len(te) == 0:
            rows.append({'window_id': w, 'error': 'empty split'})
            continue
        max_train_end = tr['offering_end_date'].max()
        purge_stats = {}
        for name, bl in (('train', roles['TRAIN']), ('val', roles['VALIDATION']), ('test', roles['TEST'])):
            full = b[b['block'].isin(bl)]
            gone = full[full['offering_id'].isin(excl)]
            purge_stats[f'n_purged_{name}'] = int(len(gone))
            purge_stats[f'purged_enrollment_share_{name}'] = float(gone['n_enrollments'].sum() / max(full['n_enrollments'].sum(), 1))
        rec = {
            'window_id': w, **purge_stats,
            'train_min_start': tr['offering_start_date'].min(), 'train_max_end': max_train_end,
            'val_min_start': va['offering_start_date'].min(), 'val_min_end': va['offering_end_date'].min(),
            'val_max_end': va['offering_end_date'].max(),
            'test_min_start': te['offering_start_date'].min(), 'test_min_end': te['offering_end_date'].min(),
            'test_max_end': te['offering_end_date'].max(),
        }
        rec['n_enrollments_train'] = int(tr['n_enrollments'].sum())
        rec['n_enrollments_val'] = int(va['n_enrollments'].sum())
        rec['n_enrollments_test'] = int(te['n_enrollments'].sum())
        rec['tau_w'] = max_train_end                      # window boundary used by strict_flags
        rec['end_order_ok'] = bool(max_train_end <= min(rec['val_min_end'], rec['test_min_end']))
        rec['days_train_end_to_test_start'] = (rec['test_min_start'] - max_train_end).days
        rec['days_train_end_to_val_start'] = (rec['val_min_start'] - max_train_end).days
        rec['train_history_span_days'] = (max_train_end - rec['train_min_start']).days
        rec['window_test_start_utc'] = rec['test_min_start']
        rec['window_test_end_utc'] = rec['test_max_end']
        for name, part in (('test', te), ('val', va)):
            if enrollments is not None:
                ep = e[e['offering_id'].isin(part['offering_id'])]
                share = float((ep['cutoff_p1'] < max_train_end).mean()) if len(ep) else np.nan
                n_off_overlap = int(part['offering_start_date'].lt(max_train_end).sum())
            else:
                cut = _cutoff(part['offering_start_date'], part['offering_end_date'], q_first)
                wgt = part['n_enrollments'].to_numpy(dtype=float)
                share = float(np.average((cut < max_train_end).to_numpy(), weights=wgt)) if wgt.sum() else np.nan
                n_off_overlap = int(part['offering_start_date'].lt(max_train_end).sum())
            rec[f'{name}_train_overlap_share'] = share
            rec[f'{name}_n_offerings_started_before_train_end'] = n_off_overlap
            rec[f'{name}_n_offerings'] = int(len(part))
        rec['ev_train_overlap_share'] = rec['test_train_overlap_share']
        rows.append(rec)
    return pd.DataFrame(rows)


def qa22(audit: pd.DataFrame, min_eval_enrollments: int = 1, overlap_threshold: Optional[float] = None
         ) -> Tuple[bool, pd.DataFrame]:
    """QA22 (revised 2026-09-28): passes when, in every window, (i) label-time ordering holds
    (latest TRAIN offering_end_date <= earliest VALIDATION and TEST offering_end_date) and (ii) both
    VALIDATION and TEST hold at least ``min_eval_enrollments`` enrollments. ``ev_train_overlap_share``
    is always reported; if ``overlap_threshold`` is given it only raises ``overlap_flag`` for the
    limitations section, it never fails the check. Returns (passed, per-window table)."""
    a = audit.copy()
    if 'error' in a.columns and a['error'].notna().any():
        a['qa22_ok'] = False
        return False, a
    a['eval_size_ok'] = (a['n_enrollments_val'] >= min_eval_enrollments) & (a['n_enrollments_test'] >= min_eval_enrollments)
    a['overlap_flag'] = (a['ev_train_overlap_share'] > overlap_threshold) if overlap_threshold is not None else False
    a['qa22_ok'] = a['end_order_ok'] & a['eval_size_ok']
    return bool(a['qa22_ok'].all()), a


def purge_exclusions(blocks: pd.DataFrame, windows: Optional[Dict[str, Dict[str, List[str]]]] = None,
                     enrollments: Optional[pd.DataFrame] = None, schema: SplitSchema = SplitSchema()) -> pd.DataFrame:
    """Test-side purge — SENSITIVITY ONLY since 2026-09-28 (it removed 90–100% of the evaluation sets on
    the real data, see SPLIT_V2_QA_INCIDENT_REPORT). For each window, drop from VALIDATION/TEST the
    offerings whose offering_start_date is earlier than the latest offering_end_date of TRAIN. Prefer
    ``strict_flags`` (row-level STRICT/OVERLAP slice) for the strict-temporal analysis."""
    windows = windows or windows_from_blocks()
    b = blocks.copy()
    b['offering_start_date'] = pd.to_datetime(b['offering_start_date'])
    b['offering_end_date'] = pd.to_datetime(b['offering_end_date'])
    rows = []
    for w, roles in windows.items():
        max_train_end = b[b['block'].isin(roles['TRAIN'])]['offering_end_date'].max()
        ev = b[b['block'].isin(roles['VALIDATION'] + roles['TEST']) & (b['offering_start_date'] < max_train_end)]
        for oid in ev['offering_id']:
            rows.append({'window_id': w, 'offering_id': oid, 'reason': 'TEST_SIDE_PURGE_STARTS_BEFORE_TRAIN_END'})
    return pd.DataFrame(rows, columns=['window_id', 'offering_id', 'reason'])


def remedy_exclusions(blocks: pd.DataFrame, purge_mode: str = 'NONE', gap_days: int = 0,
                      windows: Optional[Dict[str, Dict[str, List[str]]]] = None) -> pd.DataFrame:
    """Dispatch an exclusion rule: NONE (primary since 2026-09-28) | TEST_SIDE_PURGE | TRAIN_EMBARGO
    (the latter two only for sensitivity variants)."""
    if purge_mode == 'NONE':
        return pd.DataFrame(columns=['window_id', 'offering_id', 'reason'])
    if purge_mode == 'TEST_SIDE_PURGE':
        return purge_exclusions(blocks, windows)
    if purge_mode == 'TRAIN_EMBARGO':
        return embargo_exclusions(blocks, windows, gap_days)
    raise ValueError(purge_mode)


def embargo_exclusions(blocks: pd.DataFrame, windows: Optional[Dict[str, Dict[str, List[str]]]] = None,
                       gap_days: int = 0) -> pd.DataFrame:
    """Offerings to drop from TRAIN of each window under an embargo of ``gap_days`` before the
    earliest VALIDATION/TEST end date. Returns rows (window_id, offering_id, reason)."""
    windows = windows or windows_from_blocks()
    b = blocks.copy()
    b['offering_end_date'] = pd.to_datetime(b['offering_end_date'])
    rows = []
    for w, roles in windows.items():
        boundary = b[b['block'].isin(roles['VALIDATION'] + roles['TEST'])]['offering_end_date'].min()
        cut = boundary - pd.Timedelta(days=int(gap_days))
        tr = b[b['block'].isin(roles['TRAIN']) & (b['offering_end_date'] > cut)]
        for oid in tr['offering_id']:
            rows.append({'window_id': w, 'offering_id': oid, 'reason': f'EMBARGO_{gap_days}D'})
    return pd.DataFrame(rows, columns=['window_id', 'offering_id', 'reason'])


# ---------------------------------------------------------------------------------------------
# 3b. Strict-temporal slice, temporal profile and boundary choice (2026-09-28)
# ---------------------------------------------------------------------------------------------
def strict_flags(eval_rows: pd.DataFrame, tau_by_window: Mapping[str, pd.Timestamp],
                 schema: SplitSchema = SplitSchema(), phase_col: str = 'phase_id',
                 window_col: str = 'window_id') -> pd.DataFrame:
    """Row-level strict-temporal flag for the subgroup axis TEMPORAL.

    eval_rows: one row per (enrollment, phase) of VALIDATION/TEST with enroll_time, offering_end_date,
    phase_id and window_id. tau_by_window: window_id -> tau_w (latest TRAIN offering_end_date, taken
    from audit_temporal_overlap['tau_w']). A row is STRICT when its phase cutoff
    enroll_time + q_k * (offering_end_date - enroll_time) is >= tau_w, i.e. the prediction moment lies
    after every TRAIN label was realised; otherwise OVERLAP. Higher phases are STRICT more often."""
    s = schema
    ev = eval_rows.copy()
    ev[s.enroll_time] = pd.to_datetime(ev[s.enroll_time])
    ev[s.offering_end] = pd.to_datetime(ev[s.offering_end])
    q = ev[phase_col].map(PHASE_Q).astype(float)
    ev['cutoff_time'] = ev[s.enroll_time] + (ev[s.offering_end] - ev[s.enroll_time]) * q.values
    tau = ev[window_col].map({k: pd.Timestamp(v) for k, v in tau_by_window.items()})
    ev['tau_w'] = tau
    ev['temporal_strict'] = (ev['cutoff_time'] >= tau).astype(int)
    ev['subgroup_axis'] = 'TEMPORAL'
    ev['subgroup_value'] = np.where(ev['temporal_strict'] == 1, 'STRICT', 'OVERLAP')
    return ev


def strict_share_table(flagged: pd.DataFrame, window_col: str = 'window_id', split_col: str = 'eval_split',
                       phase_col: str = 'phase_id') -> pd.DataFrame:
    """Share and count of STRICT rows per window x split x phase (goes to the manifest)."""
    g = flagged.groupby([window_col, split_col, phase_col])['temporal_strict']
    out = g.agg(n_rows='count', n_strict='sum').reset_index()
    out['strict_share'] = out['n_strict'] / out['n_rows']
    return out


def temporal_profile(offerings: pd.DataFrame, freq: str = 'MS') -> pd.DataFrame:
    """Calendar profile of the offerings: per period, offerings/enrollments starting and ending,
    offerings active at the period start, and the enrollment-weighted share of offerings that would
    straddle a boundary placed at the period start (the quantity that drives the P1 overlap)."""
    o = offerings.copy()
    o['offering_start_date'] = pd.to_datetime(o['offering_start_date'])
    o['offering_end_date'] = pd.to_datetime(o['offering_end_date'])
    periods = pd.date_range(o['offering_start_date'].min().to_period('M').to_timestamp(),
                            o['offering_end_date'].max() + pd.offsets.MonthBegin(1), freq=freq)
    rows = []
    total = o['n_enrollments'].sum()
    for t0, t1 in zip(periods[:-1], periods[1:]):
        starting = o[(o['offering_start_date'] >= t0) & (o['offering_start_date'] < t1)]
        ending = o[(o['offering_end_date'] >= t0) & (o['offering_end_date'] < t1)]
        active = o[(o['offering_start_date'] < t0) & (o['offering_end_date'] > t0)]
        ended_before = o[o['offering_end_date'] <= t0]
        rows.append({'period_start': t0, 'n_offerings_starting': len(starting), 'n_offerings_ending': len(ending),
                     'enrollments_starting': int(starting['n_enrollments'].sum()), 'enrollments_ending': int(ending['n_enrollments'].sum()),
                     'n_offerings_active_at_start': len(active), 'enrollments_active_at_start': int(active['n_enrollments'].sum()),
                     'straddle_share_if_boundary_here': float(active['n_enrollments'].sum() / total) if total else np.nan,
                     'cum_enrollment_share_ended': float(ended_before['n_enrollments'].sum() / total) if total else np.nan})
    prof = pd.DataFrame(rows)
    return prof


def duration_summary(offerings: pd.DataFrame, source_col: Optional[str] = 'timeline_source') -> pd.DataFrame:
    """Duration quantiles (days) overall and by timeline source (if the column exists); also reports the
    truncation pile-up: share of offerings whose end date equals the latest end date in the data."""
    o = offerings.copy()
    o['offering_start_date'] = pd.to_datetime(o['offering_start_date'])
    o['offering_end_date'] = pd.to_datetime(o['offering_end_date'])
    o['duration_days'] = (o['offering_end_date'] - o['offering_start_date']).dt.days
    last = o['offering_end_date'].max()
    o['ends_at_data_end'] = (last - o['offering_end_date']).dt.days <= 1
    keys = [source_col] if (source_col and source_col in o) else []
    g = o.groupby(keys) if keys else o.assign(_all='ALL').groupby('_all')
    out = g.agg(n_offerings=('offering_id', 'count'), enrollments=('n_enrollments', 'sum'),
                dur_p10=('duration_days', lambda x: x.quantile(0.10)), dur_p50=('duration_days', 'median'),
                dur_p90=('duration_days', lambda x: x.quantile(0.90)), dur_max=('duration_days', 'max'),
                share_ending_at_data_end=('ends_at_data_end', 'mean')).reset_index()
    return out


def choose_boundaries(offerings: pd.DataFrame, n_slices: int = 3, train_share: float = 0.60,
                      min_slice_share: float = 0.08, freq: str = 'MS', q_first: float = PHASE_Q['P1']
                      ) -> Tuple[List[pd.Timestamp], pd.DataFrame]:
    """Pick n_slices-1 end-date boundaries for the future pool from a calendar grid, minimising the
    enrollment-weighted P1 overlap of the resulting windows subject to every slice holding at least
    ``min_slice_share`` of all enrollments. Returns (best_boundaries, table of all feasible candidates).
    Equal-mass slicing is the fallback when no candidate is feasible."""
    o = offerings.copy()
    o['offering_start_date'] = pd.to_datetime(o['offering_start_date'])
    o['offering_end_date'] = pd.to_datetime(o['offering_end_date'])
    o = o.sort_values('offering_end_date').reset_index(drop=True)
    total = o['n_enrollments'].sum()
    cum_before = o['n_enrollments'].cumsum() - o['n_enrollments']
    pool = o[(cum_before / total) >= train_share]
    if len(pool) == 0:
        raise ValueError('future pool is empty')
    grid = pd.date_range(pool['offering_end_date'].min().to_period('M').to_timestamp() + pd.offsets.MonthBegin(1),
                         pool['offering_end_date'].max(), freq=freq)
    from itertools import combinations
    cut_p1 = _cutoff(o['offering_start_date'], o['offering_end_date'], q_first)
    rows = []
    for combo in combinations(grid, n_slices - 1):
        bds = list(combo)
        edges = [pool['offering_end_date'].min() - pd.Timedelta(days=1)] + bds + [pool['offering_end_date'].max() + pd.Timedelta(days=1)]
        shares, overlaps, ok = [], [], True
        for k in range(n_slices):
            sl = pool[(pool['offering_end_date'] > edges[k]) & (pool['offering_end_date'] <= edges[k + 1])]
            share = sl['n_enrollments'].sum() / total
            shares.append(float(share))
            if share < min_slice_share:
                ok = False
            # window k: TRAIN = everything ending <= edges[k]; overlap = eval enrollments with P1 cutoff < tau
            tau = o.loc[o['offering_end_date'] <= edges[k], 'offering_end_date'].max() if k > 0 else o.loc[cum_before / total < train_share, 'offering_end_date'].max()
            wgt = sl['n_enrollments'].to_numpy(dtype=float)
            ov = float(np.average((cut_p1.loc[sl.index] < tau).to_numpy(), weights=wgt)) if wgt.sum() else np.nan
            overlaps.append(ov)
        rows.append({'boundaries': bds, 'slice_shares': shares, 'overlap_by_window': overlaps,
                     'mean_overlap': float(np.nanmean(overlaps)), 'feasible': ok})
    cand = pd.DataFrame(rows)
    feas = cand[cand['feasible']]
    if len(feas) == 0:
        return [], cand
    best = feas.sort_values('mean_overlap').iloc[0]
    return list(best['boundaries']), cand.sort_values('mean_overlap').reset_index(drop=True)


# ---------------------------------------------------------------------------------------------
# 4. Reporting helpers
# ---------------------------------------------------------------------------------------------
def block_label_table(blocks: pd.DataFrame, schema: SplitSchema = SplitSchema()) -> pd.DataFrame:
    """REPORT §9-style table: offerings, enrollments and class counts (with %) per block."""
    cols = [f'n_{c}' for c in schema.classes]
    g = blocks.groupby('block').agg(offerings=('offering_id', 'count'), enrollments=('n_enrollments', 'sum'),
                                    start_min=('offering_start_date', 'min'), end_min=('offering_end_date', 'min'),
                                    end_max=('offering_end_date', 'max'), **{c: (c, 'sum') for c in cols})
    for c in cols:
        g[c + '_pct'] = 100 * g[c] / g['enrollments']
    tot = g[['offerings', 'enrollments'] + cols].sum()
    g.loc['Tổng', ['offerings', 'enrollments'] + cols] = tot
    for c in cols:
        g.loc['Tổng', c + '_pct'] = 100 * tot[c] / tot['enrollments']
    return g


def window_label_table(blocks: pd.DataFrame, windows: Optional[Dict[str, Dict[str, List[str]]]] = None,
                       schema: SplitSchema = SplitSchema()) -> pd.DataFrame:
    """REPORT §7-style table: class counts per window × split."""
    windows = windows or windows_from_blocks()
    cols = [f'n_{c}' for c in schema.classes]
    rows = []
    for w, roles in windows.items():
        for split, bl in roles.items():
            part = blocks[blocks['block'].isin(bl)]
            rec = {'window_id': w, 'split': split, 'enrollments': int(part['n_enrollments'].sum())}
            for c in cols:
                rec[c] = int(part[c].sum())
                rec[c + '_pct'] = 100 * rec[c] / max(rec['enrollments'], 1)
            rows.append(rec)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------------------------
# 5. CLI
# ---------------------------------------------------------------------------------------------
def _read(path: str) -> pd.DataFrame:
    return pd.read_parquet(path) if path.endswith('.parquet') else pd.read_csv(path)


def main(argv: Optional[Iterable[str]] = None) -> None:  # pragma: no cover
    ap = argparse.ArgumentParser(description='Re-cut blocks A-G by time (split_version v2) and audit QA22.')
    ap.add_argument('--enrollments', required=True, help='enrollment-level table (parquet/csv) with labels')
    ap.add_argument('--out', required=True, help='output directory')
    ap.add_argument('--train-share', type=float, default=0.60)
    ap.add_argument('--n-slices', type=int, default=3)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--overlap-threshold', type=float, default=None, help='report-only flag; never gates QA22')
    ap.add_argument('--purge-mode', default='NONE', choices=['NONE', 'TEST_SIDE_PURGE', 'TRAIN_EMBARGO'],
                    help='NONE is the primary split; the others produce sensitivity manifests only')
    ap.add_argument('--optimize-boundaries', action='store_true', help='pick slice boundaries at calendar dates minimising overlap')
    ap.add_argument('--min-slice-share', type=float, default=0.08)
    ap.add_argument('--embargo-gap-days', type=int, default=0)
    ap.add_argument('--audit-only-blocks', default=None,
                    help='optional existing offering->block table (e.g. V1) to audit instead of re-cutting')
    a = ap.parse_args(list(argv) if argv is not None else None)
    import os
    os.makedirs(a.out, exist_ok=True)
    enr = _read(a.enrollments)
    offers = summarize_offerings(enr)
    temporal_profile(offers).to_csv(os.path.join(a.out, 'temporal_profile_monthly.csv'), index=False)
    duration_summary(offers).to_csv(os.path.join(a.out, 'duration_summary.csv'), index=False)
    if a.audit_only_blocks:
        blk = offers.merge(_read(a.audit_only_blocks)[['offering_id', 'block']], on='offering_id')
        tag = 'v1_audit'
    else:
        bds = None
        if a.optimize_boundaries:
            bds, cand = choose_boundaries(offers, a.n_slices, a.train_share, a.min_slice_share)
            cand.to_csv(os.path.join(a.out, 'boundary_candidates.csv'), index=False)
            bds = bds or None
        blk = assign_blocks_v2(offers, a.train_share, a.n_slices, seed=a.seed, boundaries=bds)
        tag = 'v2'
        split_manifest(blk).to_csv(os.path.join(a.out, 'split_manifest_v2.csv'), index=False)   # primary: no purge
    blk.to_csv(os.path.join(a.out, f'blocks_{tag}.csv'), index=False)
    audit = audit_temporal_overlap(blk, enrollments=enr)
    ok, table = qa22(audit, overlap_threshold=a.overlap_threshold)
    if a.purge_mode != 'NONE' and not a.audit_only_blocks:      # sensitivity manifest only
        excl = remedy_exclusions(blk, a.purge_mode, a.embargo_gap_days)
        excl.to_csv(os.path.join(a.out, f'exclusions_{a.purge_mode}.csv'), index=False)
        split_manifest(blk, exclusions=excl).to_csv(os.path.join(a.out, f'split_manifest_v2_{a.purge_mode}_sensitivity.csv'), index=False)
        audit_s = audit_temporal_overlap(blk, enrollments=enr, exclusions=excl)
        audit_s.to_csv(os.path.join(a.out, f'audit_{a.purge_mode}_sensitivity.csv'), index=False)
    table.to_csv(os.path.join(a.out, f'qa22_{tag}.csv'), index=False)
    block_label_table(blk).to_csv(os.path.join(a.out, f'block_label_table_{tag}.csv'))
    window_label_table(blk).to_csv(os.path.join(a.out, f'window_label_table_{tag}.csv'), index=False)
    print('QA22 passed' if ok else 'QA22 FAILED', '\n', table.to_string())


if __name__ == '__main__':  # pragma: no cover
    main()
