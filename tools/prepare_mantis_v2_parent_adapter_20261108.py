"""Create the V1 real-train adapter without computing parent embeddings."""
import argparse
import json
from pathlib import Path

import pandas as pd
from model.data import fit_layout, transform_frame
from f3_mantis.adapter import ChannelPCAAdapter
from f3_mantis.cell import adapter_path_for
from f3_mantis.spec import MANTIS_V2_SPEC
from f3_mantis.store import input_sha256

parser = argparse.ArgumentParser()
parser.add_argument('--window', required=True)
parser.add_argument('--data-root', type=Path, required=True)
parser.add_argument('--work-root', type=Path, required=True)
args = parser.parse_args()
parent_path = args.data_root / 'train' / args.window / 'V1/train.parquet'
balanced_path = args.data_root / 'train' / args.window / 'V2/balanced_train.parquet'
parent = pd.read_parquet(parent_path)
if parent.enrollment_id.isna().any() or parent.enrollment_id.duplicated().any():
    raise ValueError('Invalid V1 parent enrollment grain')
layout = fit_layout(parent, task='CQ', phase_id='P4', use_masks=True)
names = (list(layout.dynamic_bases) + [f'missing__{base}' for base in layout.dynamic_bases
         if f'missing__{base}_P1' in parent.columns] + list(layout.mask_phase_bases) + ['phase_fraction', 'delta_t'])
dynamic, _, _, _ = transform_frame(parent, layout, classes=('warning', 'average', 'good'), use_masks=True)
ids = parent.enrollment_id.astype(str).to_numpy()
digest = input_sha256(dynamic, ids)
balanced = pd.read_parquet(balanced_path)
if 'synthetic_id' not in balanced:
    raise ValueError('V2 is missing synthetic_id')
real = balanced.loc[balanced.synthetic_id.isna()].copy()
if len(real) != len(parent) or real.enrollment_id.isna().any() or real.enrollment_id.duplicated().any():
    raise ValueError('V2 real rows do not match V1 enrollment grain')
other_layout = fit_layout(balanced, task='CQ', phase_id='P4', use_masks=True)
if layout != other_layout:
    raise ValueError('V1 and V2 feature layouts differ')
real_dynamic, _, _, _ = transform_frame(real, layout, classes=('warning', 'average', 'good'), use_masks=True)
if input_sha256(real_dynamic, real.enrollment_id.astype(str).to_numpy()) != digest:
    raise ValueError('V2 real TRAIN differs from V1 parent input')
del balanced, real, real_dynamic, parent
cfg = MANTIS_V2_SPEC['channel_adapter']
adapter = ChannelPCAAdapter(n_components=int(cfg['n_components']), standardize=bool(cfg['standardize']),
                            sample_rows_max=int(cfg['sample_rows_max']), sample_seed=int(cfg['sample_seed']))
adapter.fit(dynamic, channel_names=names, row_ids=ids, rows_digest=digest)
path = adapter_path_for(args.work_root / 'cache', 'CQ', args.window, 'V1')
adapter.save(path)
receipt = {'window': args.window, 'parent': 'V1', 'pipeline': 'V2', 'fit_rows': len(ids),
           'real_train_input_sha256': digest, 'v2_real_rows_match_v1': True, 'adapter_digest': adapter.digest(),
           'parent_embedding_cache_used': False}
(args.work_root / 'state').mkdir(parents=True, exist_ok=True)
(args.work_root / 'state' / f'adapter_{args.window}.json').write_text(json.dumps(receipt, indent=2))
print(json.dumps({'event': 'adapter_ready', **receipt}), flush=True)
