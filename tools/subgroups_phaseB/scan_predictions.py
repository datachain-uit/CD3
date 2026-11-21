"""Read-only member listing of every result archive under CQ|LO/L1_runs/S3_model (except caches/): records every member whose path contains 'predictions' or ends with run_manifest.json,
with its size. Streams each tar with rclone cat, nothing is extracted. Resumable (JSONL; status OK archives are skipped). usage: scan_predictions.py [workers]"""
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
OUT = Path(f'{WORK}/phaseB/pred_scan.jsonl')
LOG = Path(f'{WORK}/phaseB/pred_scan.log')
LOCK = threading.Lock()


def log(m):
    with LOCK, LOG.open('a', encoding='utf-8') as h:
        h.write(time.strftime('%F %T ') + m + '\n')


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
    mem, status, err = [], 'OK', ''
    try:
        with tarfile.open(fileobj=proc.stdout, mode='r|*') as a:
            for m in a:
                n = m.name
                if m.isfile() and ('predictions' in n or n.endswith('run_manifest.json')):
                    mem.append([n, m.size])
        while True:  # drain the tail so rclone exits cleanly
            if not proc.stdout.read(1 << 20):
                break
        err = proc.stderr.read().decode('utf-8', 'replace')[-300:]
        if proc.wait() != 0:
            status = 'ERROR'
    except Exception as e:
        status, err = 'ERROR', str(e)[:300]
        proc.kill()
        proc.wait()
    with LOCK, OUT.open('a', encoding='utf-8') as h:
        h.write(json.dumps({'path': full, 'size': size, 'status': status, 'error': err, 'members': mem}) + '\n')
    log(f'{status} {full} members={len(mem)}')


with ThreadPoolExecutor(int(sys.argv[1]) if len(sys.argv) > 1 else 8) as ex:
    list(ex.map(scan, sorted(todo, key=lambda x: x[2])))
log('DONE')
