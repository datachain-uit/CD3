"""Check phase-1 fact coverage without representing this as an official MDS release."""
from pathlib import Path
import hashlib
import json
import pandas as pd

root = Path('CQ/resuilt/meta_phase1_preflight_20261108')
root.mkdir(parents=True, exist_ok=True)
inputs = {
    'cq_f1': Path('CQ/resuilt/input/results/GD1_CQ_V2_2_clean_r1/cq_family_pipeline_window_phase_metrics.parquet'),
    'cq_f2': Path('CQ/resuilt/cq_patchtst_v0_v6_full_facts_20261103/sanity_components.parquet'),
    'lo_f1': Path('LO/resuilt/lo_static_v2_grid_seed42_20261102/lo_family_pipeline_window_phase_metrics.parquet'),
    'cq_f1_resource': Path('CQ/resuilt/input/results/GD1_CQ_V2_2_clean_r1/cq_resource_per_run.parquet'),
    'cq_f2_resource': Path('CQ/resuilt/cq_patchtst_v0_v6_full_facts_20261103/resource_per_run.parquet'),
    'lo_f1_resource': Path('LO/resuilt/lo_static_v2_grid_seed42_20261102/lo_resource_per_run.parquet'),
}
expected = {'cq_f1': 1632, 'cq_f2': 168, 'lo_f1': 1632, 'cq_f1_resource': 204, 'cq_f2_resource': 21, 'lo_f1_resource': 204}
keys = ['task', 'window_id', 'pipeline_id', 'model_name', 'seed', 'eval_split', 'phase_id']
inventory = []
frames = []
for name, path in inputs.items():
    frame = pd.read_parquet(path)
    if len(frame) != expected[name]:
        raise ValueError(f'{name}: expected {expected[name]}, found {len(frame)}')
    if name in ('cq_f1', 'cq_f2', 'lo_f1'):
        missing = set(keys).difference(frame.columns)
        if missing or frame.duplicated(keys).any():
            raise ValueError(f'{name}: missing/duplicate keys {missing}')
        if set(frame.seed.astype(int)) != {42}:
            raise ValueError(f'{name}: unexpected seed')
        frames.append(frame[keys].assign(source_fact=name))
    inventory.append({'name': name, 'path': str(path), 'rows': len(frame),
                      'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
combined = pd.concat(frames, ignore_index=True)
if len(combined) != 3432 or combined.duplicated(keys).any():
    raise ValueError('Combined fact keys are not 3432 unique cells')
combined.to_parquet(root / 'fact_keys_preflight.parquet', index=False)
(root / 'inventory.json').write_text(json.dumps(inventory, indent=2) + '\n', encoding='utf8')
(root / 'README.md').write_text('# Phase-1 fact preflight — NOT an official meta-release\n\nVerified row counts, seed and unique fact keys for CQ F1, CQ PatchTST V0–V6 and LO F1. Resource files are counted only. No S0, F0, model context, QA01–QA24, objective, official assembler or meta-model output is provided. This directory is not eligible as an official M-14 release.\n', encoding='utf8')
print(json.dumps({'fact_rows': len(combined), 'resource_rows': sum(expected[k] for k in expected if k.endswith('resource')), 'status': 'PREFLIGHT_ONLY', 'inputs': inventory}, indent=2))
