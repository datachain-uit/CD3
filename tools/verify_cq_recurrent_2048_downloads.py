"""Read-only cross-host SHA-256 and CQ seed-42 fact checks."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import json
import subprocess
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'CQ/resuilt/cq_recurrent_batch2048_seed42_20261019'
CONFIG = {
    'LSTM': (ROOT/'CQ/resuilt/cq_lstm_batch2048_full_20261018/lstm', '/workspace/CD3/runs/recurrent_batch2048_energy_seed42_20261015/lstm', ROOT/'CQ/resuilt/cq_lstm_batch2048_audit_20261018/CQ/LSTM/seed=42'),
    'GRU': (BASE/'gru', '/workspace/CD3/runs/cq_recurrent_batch2048_20261018/gru', BASE/'audits/CQ/GRU/seed=42'),
    'BILSTM': (BASE/'bilstm', '/workspace/CD3/runs/cq_recurrent_batch2048_20261018/bilstm', BASE/'audits/CQ/BILSTM/seed=42'),
}
HOST = 'root@185.101.222.18'

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''): h.update(block)
    return h.hexdigest()

def check(model, cfg):
    local, remote, audit = cfg
    print(f'{model}: hashing remote', flush=True)
    cmd = ['ssh','-o','BatchMode=yes','-o','ConnectTimeout=20','-p','17350',HOST,
           f'find {remote} -type f -exec sha256sum {{}} +']
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    remote_hashes = {}
    for line in proc.stdout.splitlines():
        checksum, name = line.split('  ', 1)
        remote_hashes[name.removeprefix(remote+'/')] = checksum
    local_paths = {p.relative_to(local).as_posix(): p for p in local.rglob('*') if p.is_file()}
    missing = sorted(remote_hashes.keys() - local_paths.keys())
    extra = sorted(local_paths.keys() - remote_hashes.keys())
    errors = []
    print(f'{model}: hashing {len(local_paths)} local files', flush=True)
    for i, name in enumerate(sorted(remote_hashes.keys() & local_paths.keys()), 1):
        if digest(local_paths[name]) != remote_hashes[name]: errors.append(name)
        if i % 200 == 0: print(f'{model}: {i}/{len(local_paths)}', flush=True)
    manifest_paths = list(local.rglob('run_manifest.json'))
    runs = [json.loads(p.read_text(encoding='utf-8')) for p in manifest_paths]
    patterns = Counter((str(r.get('model_name')),str(r.get('window_id')),str(r.get('batch_size')),str(r.get('micro_batch_size')),str(r.get('seed')),str(r.get('gpu'))) for r in runs)
    ids = Counter((r.get('window_id'),r.get('pipeline_id')) for r in runs)
    expected_ids = {(f'W{w}',f'V{v}') for w in range(1,4) for v in range(17)}
    checks = {}
    expected = {'canonical_s_leak':120,'sanity_components':408,'evaluation_slices':1224,'metrics_per_class':1224,'bootstrap_metrics_per_class':3672,'checkpoint_selection':51}
    for name, count in expected.items():
        f = pd.read_parquet(audit / (name+'.parquet'))
        checks[name] = {'rows':len(f), 'expected_rows':count}
        if 'acctempo_m3' in f:
            cols = ['acctempo_m3','s_perf','s_nan','s_maj_jsd','s_ent','s_drift','s_eff','s_leak','s_san_plus']
            checks[name]['nulls'] = {c:int(f[c].isna().sum()) for c in cols if c in f.columns}
            checks[name]['nonfinite_predictions'] = int(f['prediction_nan_inf_count'].fillna(0).sum())
        if name == 'bootstrap_metrics_per_class': checks[name]['repetitions'] = sorted(f.bootstrap_repetitions.dropna().astype(int).unique().tolist())
        if name == 'canonical_s_leak':
            key = ['window_id','parent_pipeline','eval_split','phase_id']
            checks[name]['duplicate_keys'] = int(f.duplicated(key).sum())
        if name == 'sanity_components':
            key = ['window_id','pipeline_id','eval_split','phase_id']
            checks[name]['duplicate_keys'] = int(f.duplicated(key).sum())
    audit_manifest = json.loads((audit/'audit_manifest.json').read_text(encoding='utf-8'))
    result = {'local_files':len(local_paths),'remote_files':len(remote_hashes),'missing':missing,'extra':extra,'sha256_mismatch':errors,'run_count':len(runs),'missing_run_cells':sorted(list(expected_ids-ids.keys())),'duplicate_run_cells':[str(k) for k,v in ids.items() if v!=1], 'run_config_counts':{str(k):v for k,v in patterns.items()},'facts':checks,'audit_manifest':audit_manifest}
    print(f'{model}: finished hash_mismatch={len(errors)}', flush=True)
    return model,result

if __name__ == '__main__':
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = dict(pool.map(lambda item: check(*item), CONFIG.items()))
    out = BASE/'verification_sha256_facts_20261019.json'
    out.write_text(json.dumps(results,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('RESULT:',out,flush=True)
