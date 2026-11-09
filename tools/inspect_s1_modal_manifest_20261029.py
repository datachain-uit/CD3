"""Read-only inventory of S1 manifests; no data or secret values are printed."""
import json
from pathlib import Path
import re
import modal

app = modal.App('s1-manifest-inventory-20261029')
volume = modal.Volume.from_name('tempo-data-v1', create_if_missing=False)

@app.function(image=modal.Image.debian_slim(python_version='3.12'), volumes={'/data': volume}, cpu=1, memory=1024, timeout=600)
def inspect(task: str, expected: list[dict]):
    root = Path('/data/meta_release=imputation-v1/L1_runs') / f'task={task}'
    result = []
    for p in root.glob('feature_regime=*/window_id=*/pipeline_id=*/model_name=IMPUTATION_ONLY/seed=*/run_id=*/attempt_id=*/run_manifest.json'):
        try:
            m = json.loads(p.read_text(encoding='utf-8'))
            result.append({'path': str(p), 'window_id': m.get('window_id'), 'pipeline_id': m.get('pipeline_id'), 'run_status': m.get('run_status'), 'release_id': m.get('release_id'), 'split_version': m.get('split_version'), 'phase_version': m.get('phase_version'), 'data_release_id': m.get('data_release_id'), 'run_id': m.get('run_id'), 'attempt_id': m.get('attempt_id'), 'attempt_number': m.get('attempt_number'), 'created_at_utc': m.get('created_at_utc'), 'mtime': p.stat().st_mtime})
        except (OSError, ValueError) as e:
            result.append({'path': str(p), 'error': str(e)})
    index = {x['path'].removesuffix('/run_manifest.json'): x for x in result if 'run_status' in x}
    checked = []
    for entry in expected:
        is_s2 = entry['remote_path'].endswith('/balanced_train.parquet')
        directory = '/data/' + entry['remote_path'].removesuffix('/balanced_train.parquet' if is_s2 else '/model_inputs/train.parquet')
        m = index.get(directory)
        if is_s2:
            manifest = Path(directory) / 'run_manifest.json'
            m = json.loads(manifest.read_text(encoding='utf-8')) if manifest.is_file() else None
        checked.append({'window': entry['window_id'], 'pipeline': entry['pipeline_id'],
                        'status': m.get('run_status') if m else 'MANIFEST_MISSING',
                        'release_id': m.get('release_id') if m else None,
                        'data_release_id': m.get('data_release_id') if m else None,
                        'train_exists': (Path('/data') / entry['remote_path']).is_file(),
                        'ledger_exists': (Path(directory) / 'synthetic_ledger.parquet').is_file() if is_s2 else None,
                        'remote_path': entry['remote_path']})
    return {'task': task, 'manifest_count': len(result), 'expected_count': len(checked), 'checked': checked}

@app.local_entrypoint()
def main(task: str = 'CQ'):
    filename = 'CQ_V2_2_clean_grain_seed42' if task == 'CQ' else 'LO_V3_1_clean_grain_seed42'
    data = json.loads((Path('downloads/vastai') / filename / 'download_manifest.json').read_text(encoding='utf-8'))
    expected = [e for e in data['files'] if e.get('kind') == 'train']
    report = inspect.remote(task, expected)
    rows = report['checked']
    print(json.dumps({'task': task, 'total_s1_manifests': report['manifest_count'], 'expected': len(rows), 'successful_matching_release': sum(r['status'] == 'SUCCESS' and r['release_id'] == data['release_id'] and r['data_release_id'] == data['data_release_id'] and r['train_exists'] for r in rows), 's2_ledger_found': sum(r['ledger_exists'] is True for r in rows), 'failures': [r for r in rows if not (r['status'] == 'SUCCESS' and r['release_id'] == data['release_id'] and r['data_release_id'] == data['data_release_id'] and r['train_exists'])]}, ensure_ascii=False))
