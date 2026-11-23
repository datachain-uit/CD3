"""Read-only coverage audit for S0 v5 subgroup inputs; not a finished S0 profile."""
import hashlib
import json
import os
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
V4 = ROOT / 'CQ/resuilt/m13a_s0_profile_20261109_v4/s0_profile.parquet'
FLAGS = Path(os.environ.get('TEMPO_PHASEB_FLAGS_ROOT', ROOT / 'tmp/phaseB'))
OUT = ROOT / 'CQ/resuilt/s0_v5_subgroup_preflight_20261122'
KEYS = ['task', 'window_id', 'eval_split', 'phase_id']
SUBGROUPS = [('ALL', 'ALL'), ('LEARNER', 'SEEN'), ('LEARNER', 'UNSEEN'),
             ('COURSE', 'SEEN'), ('COURSE', 'UNSEEN')]


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    v4 = pd.read_parquet(V4)
    if len(v4) != 48 or v4.duplicated(KEYS).any():
        raise ValueError('S0 v4 must contain 48 unique task/window/split/phase rows')
    chunks = []
    for task in ('CQ', 'LO'):
        source = FLAGS / f'seen_flags_{task}.parquet'
        columns = ['window_id', 'split_name', 'phase_id', 'seen_learner', 'seen_course', 'seen_offering']
        for batch in pq.ParquetFile(source).iter_batches(batch_size=250000, columns=columns):
            f = batch.to_pandas().rename(columns={'split_name': 'eval_split'})
            for col in ('seen_learner', 'seen_course', 'seen_offering'):
                if f[col].isna().any() or not f[col].isin([0, 1]).all():
                    raise ValueError(f'{task} invalid {col}')
            if f.seen_offering.any():
                raise ValueError(f'{task} violates QA15')
            f['task'] = task
            f['ALL'] = 1
            for axis, col in [('ALL', 'ALL'), ('LEARNER', 'seen_learner'), ('COURSE', 'seen_course')]:
                for value in (['ALL'] if axis == 'ALL' else ['SEEN', 'UNSEEN']):
                    g = f if axis == 'ALL' else f[f[col].eq(1 if value == 'SEEN' else 0)]
                    counts = g.groupby(KEYS, observed=True).size().rename('n_eval').reset_index()
                    counts['subgroup_axis'], counts['subgroup_value'] = axis, value
                    chunks.append(counts)
    grouped = pd.concat(chunks, ignore_index=True).groupby(KEYS + ['subgroup_axis', 'subgroup_value'], observed=True, as_index=False).n_eval.sum()
    skeleton = v4[KEYS + ['ev_n_enrollments']].merge(pd.DataFrame(SUBGROUPS, columns=['subgroup_axis', 'subgroup_value']), how='cross')
    out = skeleton.merge(grouped, on=KEYS + ['subgroup_axis', 'subgroup_value'], how='left', validate='one_to_one')
    out['n_eval'] = out.n_eval.fillna(0).astype('int64')
    all_rows = out[out.subgroup_axis.eq('ALL')]
    mismatches = all_rows[all_rows.n_eval.ne(all_rows.ev_n_enrollments)]
    if len(out) != 240 or len(mismatches):
        raise ValueError(f'Coverage or v4 cohort mismatch: rows={len(out)}, mismatches={len(mismatches)}')
    for axis in ('LEARNER', 'COURSE'):
        parts = out[out.subgroup_axis.eq(axis)].groupby(KEYS).n_eval.sum()
        reference = all_rows.set_index(KEYS).n_eval
        if not parts.sort_index().equals(reference.sort_index()):
            raise ValueError(f'{axis} partition does not match ALL')
    out['slice_status'] = out.n_eval.map(lambda n: 'SLICE_EMPTY' if n == 0 else 'NONEMPTY')
    out.to_csv(OUT / 'subgroup_support_preflight.csv', index=False)
    out.to_parquet(OUT / 'subgroup_support_preflight.parquet', index=False)
    summary = {'status': 'PREFLIGHT_ONLY_NOT_S0_V5', 'rows': len(out), 'all_rows': len(all_rows),
               'all_row_count_matches_v4': True, 'partition_and_qa15': 'PASS',
               'empty_slices': int(out.n_eval.eq(0).sum()),
               'limits': ['Only sample counts were computed; S0 subgroup statistics and ALL-value parity remain pending.',
                          'No cross-batch enrollment uniqueness check is performed here; see source seen-flags QA.'],
               'sources_sha256': {str(p): sha256(p) for p in [V4, FLAGS / 'seen_flags_CQ.parquet', FLAGS / 'seen_flags_LO.parquet']}}
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == '__main__':
    main()
