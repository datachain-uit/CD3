"""Read-only scan of every result archive under CQ|LO/L1_runs/S3_model on Drive: streams each tar (rclone cat), reads only *manifest*.json members and records
data_release_id (searched recursively) per manifest. Nothing is extracted to disk. Resumable (JSONL, status OK archives are skipped). usage: scan_release_ids.py [workers]"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1] / 'seed43_44_pipeline'))
from tempo_paths import WORK
import json
import subprocess
import sys
import tarfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = '1GWiedVROrxp8jvGbd0xmvVmWriZUkpOn'
OUT = Path(f'{WORK}/m15_3seed_v2/release_id_scan.jsonl')
LOG = Path(f'{WORK}/m15_3seed_v2/release_id_scan.log')
LOCK = threading.Lock()


def log(m):
    with LOCK, LOG.open('a', encoding='utf-8') as h:
        h.write(time.strftime('%F %T ') + m + '\n')


def find(o, key, out):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == key and isinstance(v, str):
                out.append(v)
            else:
                find(v, key, out)
    elif isinstance(o, list):
        for v in o:
            find(v, key, out)


def lsjson(task):
    r = subprocess.run(['rclone', 'lsjson', f'gdrive:{task}/L1_runs/S3_model', '-R', '--files-only', '--drive-root-folder-id', ROOT], capture_output=True, check=True)
    return [(task, x['Path'], x['Size']) for x in json.loads(r.stdout) if x['Path'].lower().endswith(('.tar', '.tar.gz', '.tgz')) and not x['Path'].startswith('caches/')]


done = set()
if OUT.exists():
    for line in OUT.read_text(encoding='utf-8').splitlines():
        try:
            r = json.loads(line)
            if r['status'] == 'OK':
                done.add(r['path'])
        except Exception:
            pass
items = lsjson('CQ') + lsjson('LO')
todo = [(t, p, s) for t, p, s in items if f'{t}/L1_runs/S3_model/{p}' not in done]
log(f'BEGIN archives={len(items)} todo={len(todo)} bytes_todo={sum(s for _, _, s in todo) / 1e9:.1f} GB')


def scan(item):
    task, p, size = item
    full = f'{task}/L1_runs/S3_model/{p}'
    proc = subprocess.Popen(['rclone', 'cat', 'gdrive:' + full, '--drive-root-folder-id', ROOT, '--retries', '3'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    mans, status, err = [], 'OK', ''
    try:
        with tarfile.open(fileobj=proc.stdout, mode='r|*') as a:
            for m in a:
                if m.isfile() and 'manifest' in m.name.lower() and m.name.lower().endswith('.json') and m.size < 5_000_000:
                    try:
                        d = json.load(a.extractfile(m))
                        ids = []
                        find(d, 'data_release_id', ids)
                        mans.append({'member': m.name, 'ids': sorted(set(ids))})
                    except Exception as e:
                        mans.append({'member': m.name, 'ids': [], 'error': str(e)[:80]})
        proc.stdout.close()
        err = proc.stderr.read().decode('utf-8', 'replace')[-500:]
        if proc.wait() != 0:
            status = 'ERROR'
    except Exception as e:
        status, err = 'ERROR', str(e)[:300]
        proc.kill()
        proc.wait()
    with LOCK, OUT.open('a', encoding='utf-8') as h:
        h.write(json.dumps({'path': full, 'size': size, 'status': status, 'error': err, 'manifests': mans}) + '\n')
    log(f'{status} {full} manifests={len(mans)}')


with ThreadPoolExecutor(int(sys.argv[1]) if len(sys.argv) > 1 else 8) as ex:
    list(ex.map(scan, sorted(todo, key=lambda x: x[2])))
log('DONE')
