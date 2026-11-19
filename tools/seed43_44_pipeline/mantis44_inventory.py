"""Seed-44 Mantis result-tar inventory by streaming from Drive (name, bytes, sha256, md5, cell identity from the native run manifest). usage: mantis44_inventory.py  -> D:/audit44/mantis44_inventory.json (restartable)"""
import hashlib, json, subprocess, tarfile, time
from pathlib import Path
RC = ['rclone', '--drive-root-folder-id', '1GWiedVROrxp8jvGbd0xmvVmWriZUkpOn']
SRC = {'CQ': 'CQ/L1_runs/S3_model/staging_incoming/mantis_v2_seed44_exploratory_20261116', 'LO': 'LO/L1_runs/S3_model/staging_incoming/mantis_v2_seed44_exploratory_20261118'}
OUT = Path('D:/audit44/mantis44_inventory.json'); done = json.loads(OUT.read_text()) if OUT.exists() else []
have = {r['drive_path'] for r in done}
class H:
    def __init__(s, f): s.f, s.sha, s.md5, s.n = f, hashlib.sha256(), hashlib.md5(), 0
    def read(s, k=-1):
        b = s.f.read(k); s.sha.update(b); s.md5.update(b); s.n += len(b); return b
for task, base in SRC.items():
    lst = [e for e in json.loads(subprocess.run(RC + ['lsjson', '-R', '--files-only', f'gdrive:{base}'], capture_output=True, text=True).stdout) if e['Name'].endswith('_results.tar.gz')]
    for e in sorted(lst, key=lambda e: e['Path']):
        dp = f"{base}/{e['Path']}"
        if dp in have: continue
        p = subprocess.Popen(RC + ['--timeout', '120s', 'cat', f'gdrive:{dp}'], stdout=subprocess.PIPE); h = H(p.stdout); man = None
        with tarfile.open(fileobj=h, mode='r|gz') as tf:
            for m in tf:
                if man is None and m.isfile() and m.name.endswith('run_manifest.json'): man = json.loads(tf.extractfile(m).read())
        while h.read(1 << 22): pass
        p.wait()
        if p.returncode or man is None: print('FAILED', dp, p.returncode, man is None, flush=True); raise SystemExit(1)
        done.append({'file': e['Name'], 'drive_path': dp, 'task': man['task'], 'window': man['window'], 'pipeline': man['pipeline'], 'parent': man.get('parent'), 'seed': man['seed'], 'bytes': h.n, 'sha256': h.sha.hexdigest(), 'md5': h.md5.hexdigest(), 'drive_md5': (e.get('Hashes') or {}).get('md5')})
        OUT.write_text(json.dumps(done, indent=1)); print(time.strftime('%H:%M:%S'), len(done), dp, flush=True)
print('INVENTORY_DONE', len(done), flush=True)
