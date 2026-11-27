# -*- coding: utf-8 -*-
"""seen / unseen flags at prediction level (PLAN §2.5, Table 10; QA15).

Definitions (window w, phase k, evaluated enrollment e with cutoff(e, k)):
  seen_learner  : the learner has at least one other enrollment in the TRAIN partition of w whose
                  history ended (offering_end_date) before cutoff(e, k)
  seen_course   : course_id of e appears in TRAIN history ending before cutoff
  seen_offering : offering_id of e appears in TRAIN (must be 0 on VALIDATION/TEST → QA15)
  joint_seen_status : SL_SC / SL_UC / UL_SC / UL_UC
seen_history_reference = TRAIN_PARTITION_ONLY (primary). Flags are stored per prediction row so that
the rule can be changed and subgroup metrics recomputed without re-inference.
"""
from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pandas as pd

from .split_v2 import PHASE_Q, SplitSchema


def _earliest_end_by(train: pd.DataFrame, key: str, end_col: str) -> pd.Series:
    return train.groupby(key)[end_col].min()


def compute_seen_flags(eval_rows: pd.DataFrame, train_rows: pd.DataFrame, schema: SplitSchema = SplitSchema(),
                       phase_col: str = 'phase_id', course_family_col: Optional[str] = None,
                       seen_rule_version: str = 'seen_v1_train_partition_only') -> pd.DataFrame:
    """eval_rows: one row per (enrollment, phase) with user_id, course_id, offering_id, enroll_time,
    offering_end_date, phase_id. train_rows: TRAIN enrollments of the same window with user_id,
    course_id, offering_id, offering_end_date. Returns eval_rows + flags."""
    s = schema
    ev = eval_rows.copy()
    tr = train_rows.copy()
    for df in (ev, tr):
        df[s.offering_end] = pd.to_datetime(df[s.offering_end])
    ev[s.enroll_time] = pd.to_datetime(ev[s.enroll_time])
    q = ev[phase_col].map(PHASE_Q).astype(float)
    ev['cutoff_time'] = ev[s.enroll_time] + (ev[s.offering_end] - ev[s.enroll_time]) * q.values

    first_user = _earliest_end_by(tr, s.user_id, s.offering_end)
    first_course = _earliest_end_by(tr, s.course_id, s.offering_end)
    train_offerings = set(tr[s.offering_id].unique())

    ev['seen_learner'] = (ev[s.user_id].map(first_user) < ev['cutoff_time']).fillna(False).astype(int)
    ev['seen_course'] = (ev[s.course_id].map(first_course) < ev['cutoff_time']).fillna(False).astype(int)
    ev['seen_offering'] = ev[s.offering_id].isin(train_offerings).astype(int)
    if course_family_col and course_family_col in ev and course_family_col in tr:
        first_family = _earliest_end_by(tr, course_family_col, s.offering_end)
        ev['seen_course_family'] = (ev[course_family_col].map(first_family) < ev['cutoff_time']).fillna(False).astype(int)
    ev['joint_seen_status'] = np.select(
        [(ev.seen_learner == 1) & (ev.seen_course == 1), (ev.seen_learner == 1) & (ev.seen_course == 0),
         (ev.seen_learner == 0) & (ev.seen_course == 1)], ['SL_SC', 'SL_UC', 'UL_SC'], default='UL_UC')
    ev['seen_rule_version'] = seen_rule_version
    ev['seen_history_reference'] = 'TRAIN_PARTITION_ONLY'
    return ev


def subgroup_slices(flagged: pd.DataFrame) -> Dict[tuple, pd.Series]:
    """Boolean masks for the five mandatory subgroups (PLAN §2.2)."""
    return {('ALL', 'ALL'): pd.Series(True, index=flagged.index),
            ('LEARNER', 'SEEN'): flagged['seen_learner'] == 1, ('LEARNER', 'UNSEEN'): flagged['seen_learner'] == 0,
            ('COURSE', 'SEEN'): flagged['seen_course'] == 1, ('COURSE', 'UNSEEN'): flagged['seen_course'] == 0}


def qa15(flagged: pd.DataFrame) -> bool:
    """seen_offering must be 0 on every VALIDATION/TEST row."""
    return bool((flagged['seen_offering'] == 0).all())


def seen_shares(flagged: pd.DataFrame) -> Dict[str, float]:
    """ev_seen_learner_share, ev_seen_course_share for the Z_D block."""
    return {'ev_seen_learner_share': float(flagged['seen_learner'].mean()),
            'ev_seen_course_share': float(flagged['seen_course'].mean())}
