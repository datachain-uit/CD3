"""Seed-44 collection pass (one stream over every result tar on Drive, nothing written to disk except the small outputs):
 - M-18: train_history.parquet of every cell (F1 RNN/LSTM/GRU/BILSTM, PatchTST) and the history of every Mantis cell (f3_cell_record.json 'history')
 - runner commit check: run_manifest.json of every cell -> runner_git_commit
 - Mantis result-tar inventory (name, bytes, sha256, md5, cell identity) for the runner evidence of Mantis LO (and CQ)
usage: m43_stream.py     outputs in D:/audit44/m44_collect/  (state: done list, restartable)"""
import hashlib
import io
import json
import re
import subprocess
import sys
import tarfile
import time
from pathlib import Path

import pandas as pd

RC = ['rclone', '--drive-root-folder-id', '1GWiedVROrxp8jvGbd0xmvVmWriZUkpOn']
OUT = Path('D:/audit44/m44_collect')
OUT.mkdir(parents=True, exist_ok=True)
STATE = OUT / 'state.json'
LOG = OUT / 'm44_stream.log'
state = json.loads(STATE.read_text()) if STATE.exists() else {}
HIST = OUT / 'histories'
HIST.mkdir(exist_ok=True)
SRC = {
    ('CQ', 'F1'): 'CQ/L1_runs/S3_model/staging_incoming/f1_recurrent_seed44_20261115',
    ('LO', 'F1'): 'LO/L1_runs/S3_model/staging_incoming/f1_recurrent_seed44_20261115',
    ('CQ', 'PT'): 'CQ/L1_runs/S3_model/staging_incoming/patchtst_seed44_cells_20261116',
    ('LO', 'PT'): 'LO/L1_runs/S3_model/staging_incoming/patchtst_seed44_20261117',
    ('CQ', 'MANTIS'): 'CQ/L1_runs/S3_model/staging_incoming/mantis_v2_seed44_exploratory_20261116',
    ('LO', 'MANTIS'): 'LO/L1_runs/S3_model/staging_incoming/mantis_v2_seed44_exploratory_20261118',
}
PAT = re.compile(r'(?:^|/)(W[123])/(V\d+)/([A-Z0-9_]+)/seed=44/(train_history\.parquet|run_manifest\.json)$')


def log(m):
    with LOG.open('a', encoding='utf-8') as f:
        f.write(f'{time.strftime("%H:%M:%S")} {m}\n')
    print(m, flush=True)


class Hashing:
    """file-like wrapper that hashes everything read"""

    def __init__(self, f):
        self.f, self.sha, self.md5, self.n = f, hashlib.sha256(), hashlib.md5(), 0

    def read(self, k=-1):
        b = self.f.read(k)
        self.sha.update(b)
        self.md5.update(b)
        self.n += len(b)
        return b


def stream(path, gz):
    p = subprocess.Popen(RC + ['--timeout', '120s', '--low-level-retries', '5', 'cat', f'gdrive:{path}'], stdout=subprocess.PIPE)
    h = Hashing(p.stdout)
    return p, h, tarfile.open(fileobj=h, mode='r|gz' if gz else 'r|')


def listing(prefix):
    out = subprocess.run(RC + ['lsjson', '-R', '--files-only', f'gdrive:{prefix}'], capture_output=True, text=True).stdout
    return [e for e in json.loads(out) if e['Name'].endswith(('.tar', '.tar.gz'))]


ONLY = set(sys.argv[1:])           # optional: process only these keys (CQ_F1, LO_F1, CQ_PT, LO_PT, CQ_MANTIS, LO_MANTIS); no argument = merge everything
rows_hist, rows_man, inv = [], [], []
for (task, kind), prefix in SRC.items():
    key = f'{task}_{kind}'
    if ONLY and key not in ONLY:
        continue
    f_hist, f_man, f_inv = HIST / f'{key}_hist.pkl', HIST / f'{key}_man.pkl', HIST / f'{key}_inv.json'
    if state.get(key) == 'done':
        rows_hist.append(pd.read_pickle(f_hist))
        rows_man.append(pd.read_pickle(f_man))
        inv += json.loads(f_inv.read_text()) if f_inv.exists() else []
        continue
    hists, mans, invs = [], [], []
    files = listing(prefix)
    log(f'{key}: {len(files)} archives')   # (restartable per key)
    for e in files:
        rel = e['Path']
        parts = rel.split('/')
        fam_from_path = parts[0] if kind == 'F1' else None
        p, h, tf = stream(f'{prefix}/{rel}', e['Name'].endswith('.gz'))
        try:
            local = {}
            for m in tf:
                if not m.isfile():
                    continue
                name = m.name
                if kind == 'MANTIS':
                    mm = re.search(r'runs/(W[123])/(V\d+)/(result/f3_cell_record\.json|run_manifest\.json)$', name)
                    if not mm:
                        continue
                    local.setdefault((mm.group(1), mm.group(2)), {})[mm.group(3).split('/')[-1]] = tf.extractfile(m).read()
                else:
                    mm = PAT.search(name)
                    if mm:
                        w, v, fam, fn = mm.groups()
                    else:
                        # tars of the F1 bundles hold paths relative to the seed dir: take W/V/family from the Drive path
                        mm2 = re.search(r'(?:^|/)seed=44/(train_history\.parquet|run_manifest\.json)$', name)
                        if not mm2 or fam_from_path is None:
                            continue
                        w, v, fam, fn = parts[1], parts[2], fam_from_path, mm2.group(1)
                    local.setdefault((w, v, fam), {})[fn] = tf.extractfile(m).read()
                    if kind == 'F1' and len(local[(w, v, fam)]) == 2:
                        break          # a bundle holds one cell: nothing more to read
            if kind == 'MANTIS':
                while h.read(1 << 22):      # read to the end for the hashes
                    pass
        except Exception as ex:
            log(f'{key}: SKIP unreadable archive {rel}: {type(ex).__name__}')
            local = {}
        finally:
            p.kill()
        for k, d in local.items():
            if kind == 'MANTIS':
                w, v = k
                rec = json.loads(d['f3_cell_record.json'])
                man = json.loads(d['run_manifest.json'])
                df = pd.DataFrame(rec['history'])
                fam = 'MANTIS_V2'
                mans.append({'task': task, 'model_name': fam, 'window_id': w, 'pipeline_id': v, 'runner_git_commit': man.get('runner_git_commit'), 'best_epoch': rec.get('best_epoch'), 'archive': e['Name']})
                invs.append({'file': e['Name'], 'task': man.get('task', task), 'window': w, 'pipeline': v, 'parent': man.get('parent'), 'seed': man.get('seed'), 'bytes': h.n, 'sha256': h.sha.hexdigest(),
                             'md5': h.md5.hexdigest(), 'drive_md5': e.get('Hashes', {}).get('md5')})
            else:
                w, v, fam = k
                if 'train_history.parquet' not in d:
                    continue
                df = pd.read_parquet(io.BytesIO(d['train_history.parquet']))
                man = json.loads(d['run_manifest.json']) if 'run_manifest.json' in d else {}
                mans.append({'task': task, 'model_name': fam, 'window_id': w, 'pipeline_id': v, 'runner_git_commit': man.get('runner_git_commit'), 'best_epoch': man.get('best_epoch'), 'archive': e['Name']})
            df.insert(0, 'seed', 44)
            df.insert(0, 'model_name', fam)
            df.insert(0, 'pipeline_id', v)
            df.insert(0, 'window_id', w)
            df.insert(0, 'task', task)
            hists.append(df)
        log(f'{key}: {rel} cells={len(local)}')
    dh = pd.concat(hists, ignore_index=True) if hists else pd.DataFrame()
    dm = pd.DataFrame(mans)
    dh.to_pickle(f_hist)
    dm.to_pickle(f_man)
    f_inv.write_text(json.dumps(invs, indent=1))
    state[key] = 'done'
    STATE.write_text(json.dumps(state, indent=1))
    rows_hist.append(dh)
    rows_man.append(dm)
    inv += invs
    log(f'{key}: DONE histories={len(dh)} rows, cells={len(dm)}')
if ONLY:
    log('PARTIAL_DONE ' + ' '.join(sorted(ONLY)))
    sys.exit(0)
pd.concat(rows_hist, ignore_index=True).to_pickle(OUT / 'all_histories.pkl')
pd.concat(rows_man, ignore_index=True).to_pickle(OUT / 'all_manifests.pkl')
(OUT / 'mantis_inventory.json').write_text(json.dumps(inv, indent=1))
log('M44_STREAM_DONE')
