"""Read-only verification of a LO VastAI L2 ingest on the current Modal profile."""
import json
from pathlib import Path

import modal

app = modal.App('tempo-verify-lo-r2-ingest')
volume = modal.Volume.from_name('tempo-data-v1', create_if_missing=False)
image = modal.Image.debian_slim(python_version='3.12').pip_install('pandas>=2.2', 'pyarrow>=16', 'numpy>=1.26')


@app.function(image=image, volumes={'/data': volume}, cpu=2, memory=4096, timeout=1800)
def verify(ingest_id: str):
    import numpy as np
    import pandas as pd

    root = Path('/data/meta_release=imputation-v1')
    receipt_path = root / 'L0_registry' / 'external_fact_ingests' / 'task=LO' / f'ingest_id={ingest_id}' / 'receipt.json'
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    expected = {'sanity_components': 1632, 'metrics_per_class': 4896,
                'bootstrap_metrics_per_class': 14688, 'checkpoint_selection': 204,
                'evaluation_slices': 4896, 'metrics_overall': 1632,
                'resource_usage': 204, 'canonical_s_leak': 120}
    frames, files = {}, {}
    for fact, expected_rows in expected.items():
        base = root / 'L2_facts' / fact / 'task=LO' / 'feature_regime=LO_FULL_EARLY' / 'execution_backend=vastai_portable_runner' / f'ingest_id={ingest_id}'
        paths = sorted(base.rglob('*.parquet'))
        frames[fact] = pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True)
        files[fact] = len(paths)
        if len(frames[fact]) != expected_rows:
            raise ValueError(f'{fact}: expected {expected_rows} rows, got {len(frames[fact])}')
    keys = ['window_id', 'pipeline_id', 'model_name', 'eval_split', 'phase_id']
    slices = frames['evaluation_slices']
    sanity = frames['sanity_components']
    all_rows = slices[slices['slice'] == 'ALL']
    joined = sanity.merge(all_rows, on=keys, suffixes=('_sanity', '_slice'), validate='one_to_one')
    if len(joined) != 1632:
        raise ValueError('Incomplete ALL/sanity join')
    max_diff = {}
    for name in ('macro_f1', 'balanced_acc', 's_perf', 's_nan', 's_maj_jsd', 's_ent', 's_drift', 's_eff', 's_leak', 's_san_plus', 'acctempo_m3'):
        delta = np.abs(joined[name + '_sanity'] - joined[name + '_slice'])
        if not np.isfinite(delta).all() or (delta > 1e-9).any():
            raise ValueError(f'ALL/sanity mismatch: {name}')
        max_diff[name] = float(delta.max())
    bad = 0
    for _, part in slices.groupby(keys):
        m = {r['slice']: np.stack(r['confusion_matrix']) for _, r in part.iterrows()}
        if set(m) != {'ALL', 'STRICT', 'OVERLAP'} or not np.array_equal(m['ALL'], m['STRICT'] + m['OVERLAP']):
            bad += 1
    if bad:
        raise ValueError(f'{bad} partition errors')
    return {'ingest_id': ingest_id, 'receipt_contracts': receipt['contract_count'],
            'rows': {k: len(v) for k, v in frames.items()}, 'partition_files': files,
            'all_slice_max_abs_diff': max_diff, 'slice_partition_violations': bad}


@app.local_entrypoint()
def cli(ingest_id: str = 'vastai_lo_f2_seed42_slice_parent_r2_20261019'):
    print(json.dumps(verify.remote(ingest_id), indent=2))
