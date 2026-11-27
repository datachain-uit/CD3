# -*- coding: utf-8 -*-
"""Synthetic fixtures shared by the tempo_fix tests (no real data needed)."""
import numpy as np
import pandas as pd
import pytest


def make_enrollments(n_offerings=600, seed=1, start='2016-01-01', years=4.0):
    """Enrollment-level table with offering dates, labels (c0 majority) and timeline_source."""
    rng = np.random.default_rng(seed)
    t0 = pd.Timestamp(start)
    starts = t0 + pd.to_timedelta(rng.uniform(0, 365 * years, n_offerings), unit='D')
    durations = rng.integers(60, 200, n_offerings)
    sizes = np.clip(rng.lognormal(5.0, 1.0, n_offerings).astype(int), 5, 20000)
    rows = []
    eid = 0
    for i in range(n_offerings):
        oid = f'off{i:04d}'
        cid = f'course{i % 150:03d}'
        # label prevalence drifts with time so that slices differ (realistic)
        p_good = 0.01 + 0.03 * (i / n_offerings) * rng.uniform(0.5, 1.5)
        p_avg = 0.02 * rng.uniform(0.5, 1.5)
        n = int(sizes[i])
        labs = rng.choice(['c0', 'c1', 'c2'], size=n, p=[1 - p_good - p_avg, p_avg, p_good])
        enroll = starts[i] + pd.to_timedelta(rng.uniform(0, 30, n), unit='D')
        users = rng.integers(0, 40000, n)
        inferred = rng.random() < 0.3
        for j in range(n):
            rows.append((f'e{eid}', oid, cid, f'u{users[j]}', enroll[j], starts[i], starts[i] + pd.Timedelta(days=int(durations[i])),
                         labs[j], 'enrollment_anchored_proxy' if inferred else 'course_specific_timeline'))
            eid += 1
    return pd.DataFrame(rows, columns=['enrollment_id', 'offering_id', 'course_id', 'user_id', 'enroll_time',
                                       'offering_start_date', 'offering_end_date', 'label', 'timeline_source'])


@pytest.fixture(scope='session')
def enrollments():
    return make_enrollments()
