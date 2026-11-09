"""Export S0 facts for one locked release/account without profiling or retraining."""
import hashlib
import json
from pathlib import Path
import tempfile
import zipfile
import modal

app = modal.App('cd3-m13-s0-export-20261108')
volume = modal.Volume.from_name('tempo-data-v1', create_if_missing=False)
image = modal.Image.debian_slim(python_version='3.12')
EXPECTED = {'CQ': ('CQ_RAW_EARLY', 'CQ_V2_2', 'sha256:8db2b1d375c9cb7cd91cbccb7907fca51a8ab9bcd748c7bde43e879b1237d045'),
            'LO': ('LO_FULL_EARLY', 'LO_V3_1', 'sha256:2edf8cc293044d29c360cb2db71b8d21e26e2187cf40c6d45266f342a826d35b')}

@app.function(image=image, volumes={'/data': volume}, cpu=1, memory=1024, timeout=1800)
def export(task: str):
    if task not in EXPECTED:
        raise ValueError('task must be CQ or LO')
    regime, release_id, identity = EXPECTED[task]
    root = Path('/data/meta_release=imputation-v1')
    manifest_path = root / 'L0_registry/state_manifests' / f's0_{task}.json'
    manifest = json.loads(manifest_path.read_text())
    release = manifest.get('release', {})
    if manifest.get('profile_scope') != 'ALL_ROWS' or release.get('data_release_id') != identity or release.get('release_id') != release_id:
        raise ValueError('S0 manifest is not the locked all-row release')
    states = manifest['state_ids']
    if len(states) != 3:
        raise ValueError('expected one state ID per window')
    kinds = ('dq_feature_profile', 'dataset_quality_summary', 'distribution_sketch', 'class_distribution', 'drift_measures')
    missing, included = [], []
    with tempfile.TemporaryDirectory() as temporary:
        archive = Path(temporary) / f'{task}_s0_current.zip'
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as out:
            out.write(manifest_path, f'manifests/s0_{task}.json')
            for window, state in zip(('W1', 'W2', 'W3'), states):
                for phase in ('P1', 'P2', 'P3', 'P4'):
                    for kind in kinds:
                        source = root / 'L2_facts' / kind / f'task={task}' / f'feature_regime={regime}' / f'window_id={window}' / f'phase_id={phase}' / 'stage=S0_RAW' / f'state_id={state}' / 'part-00000.parquet'
                        dest = f'L2_facts/task={task}/window_id={window}/phase_id={phase}/{kind}.parquet'
                        if source.is_file():
                            out.write(source, dest); included.append(dest)
                        else:
                            missing.append(str(source))
                source = root / 'L2_facts/bin_scheme' / f'task={task}' / f'feature_regime={regime}' / f'window_id={window}' / 'fit_scope=TRAIN_POOLED_P1_P4' / 'stage=S0_RAW' / f'state_id={state}' / 'part-00000.parquet'
                if source.is_file():
                    dest = f'L2_facts/task={task}/window_id={window}/bin_scheme.parquet'
                    out.write(source, dest); included.append(dest)
                else:
                    missing.append(str(source))
            out.writestr('EXPORT_MANIFEST.json', json.dumps({'task': task, 'release_id': release_id, 'data_release_id': identity,
                          'state_ids': states, 'included': included, 'missing': missing}, indent=2))
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        target = root / 'exports/m13_s0_20261108' / task / f's0_{task}_{digest}.zip'
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_bytes(archive.read_bytes())
        elif hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise RuntimeError('Existing immutable output has unexpected hash')
    volume.commit()
    return {'task': task, 'archive': str(target), 'sha256': digest, 'included': len(included), 'missing': missing}

@app.local_entrypoint()
def cli(task: str = 'CQ'):
    print(json.dumps(export.remote(task), indent=2))
