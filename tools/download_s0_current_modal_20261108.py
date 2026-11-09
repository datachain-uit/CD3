"""Read current S0 partitions from Modal Volume without running a Modal app."""
import hashlib
import json
import os
from pathlib import Path
import sys

task, profile = sys.argv[1:3]
if task not in ('CQ', 'LO'):
    raise ValueError('task must be CQ or LO')
os.environ['MODAL_PROFILE'] = profile
import modal

volume = modal.Volume.from_name('tempo-data-v1', create_if_missing=False)
out = Path(f'{task}/resuilt/s0_current_{task.lower()}_modal_20261108')
out.mkdir(parents=True, exist_ok=True)
root = '/meta_release=imputation-v1'

def read(remote, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + '.partial')
    h = hashlib.sha256()
    with temporary.open('wb') as stream:
        for block in volume.read_file(remote):
            stream.write(block)
            h.update(block)
    temporary.replace(destination)
    return h.hexdigest()

manifest_path = out / f's0_{task}.json'
read(f'{root}/L0_registry/state_manifests/s0_{task}.json', manifest_path)
manifest = json.loads(manifest_path.read_text(encoding='utf8'))
ids = {'CQ': ('CQ_RAW_EARLY', 'CQ_V2_2', 'sha256:8db2b1d375c9cb7cd91cbccb7907fca51a8ab9bcd748c7bde43e879b1237d045'),
       'LO': ('LO_FULL_EARLY', 'LO_V3_1', 'sha256:2edf8cc293044d29c360cb2db71b8d21e26e2187cf40c6d45266f342a826d35b')}
regime, release, expected = ids[task]
if manifest.get('profile_scope') != 'ALL_ROWS' or manifest['release'].get('data_release_id') != expected or manifest['release'].get('release_id') != release:
    raise ValueError('S0 manifest does not match the locked all-row release')
if len(manifest['state_ids']) != 3:
    raise ValueError('expected three window state IDs')
records = []
for window, state in zip(('W1', 'W2', 'W3'), manifest['state_ids']):
    for phase in ('P1', 'P2', 'P3', 'P4'):
        for kind in ('dq_feature_profile', 'dataset_quality_summary', 'distribution_sketch', 'class_distribution', 'drift_measures'):
            remote = f'{root}/L2_facts/{kind}/task={task}/feature_regime={regime}/window_id={window}/phase_id={phase}/stage=S0_RAW/state_id={state}/part-00000.parquet'
            local = out / 'L2_facts' / f'window_id={window}' / f'phase_id={phase}' / f'{kind}.parquet'
            try:
                sha = read(remote, local)
                records.append({'remote_path': remote, 'local_path': str(local.relative_to(out)), 'sha256': sha})
                print(json.dumps({'window': window, 'phase': phase, 'kind': kind, 'status': 'OK'}), flush=True)
            except Exception as exc:
                records.append({'remote_path': remote, 'error': str(exc)})
                print(json.dumps({'window': window, 'phase': phase, 'kind': kind, 'status': 'FAILED', 'error': str(exc)}), flush=True)
    remote = f'{root}/L2_facts/bin_scheme/task={task}/feature_regime={regime}/window_id={window}/fit_scope=TRAIN_POOLED_P1_P4/stage=S0_RAW/state_id={state}/part-00000.parquet'
    local = out / 'L2_facts' / f'window_id={window}' / 'bin_scheme.parquet'
    try:
        sha = read(remote, local)
        records.append({'remote_path': remote, 'local_path': str(local.relative_to(out)), 'sha256': sha})
    except Exception as exc:
        records.append({'remote_path': remote, 'error': str(exc)})
(out / 'inventory.json').write_text(json.dumps({'task': task, 'release_id': release, 'data_release_id': expected,
    'files': records, 'missing': sum('error' in item for item in records)}, indent=2), encoding='utf8')
print(json.dumps({'task': task, 'total': len(records), 'missing': sum('error' in item for item in records), 'output': str(out)}), flush=True)
