"""For every archive the scan marked non-OK: stream the whole file, hash it (md5 vs Drive), parse it as tar to the end, count members and manifests."""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1] / 'seed43_44_pipeline'))
from tempo_paths import WORK
import hashlib
import json
import subprocess
import tarfile

ROOT = '1GWiedVROrxp8jvGbd0xmvVmWriZUkpOn'
RC = ['rclone', '--drive-root-folder-id', ROOT]
bad = {}
for line in open(f'{WORK}/m15_3seed_v2/release_id_scan.jsonl', encoding='utf-8'):
    r = json.loads(line)
    bad.setdefault(r['path'], []).append(r['status'])
todo = [p for p, s in bad.items() if s[-1] != 'OK']
print('non-OK archives (last status):', len(todo))


class Tee:
    def __init__(self, f):
        self.f, self.h, self.n = f, hashlib.md5(), 0

    def read(self, k=-1):
        b = self.f.read(k)
        self.h.update(b)
        self.n += len(b)
        return b


out = []
for p in todo:
    lj = json.loads(subprocess.run(RC + ['lsjson', 'gdrive:' + p, '--hash'], capture_output=True, text=True).stdout)[0]
    proc = subprocess.Popen(RC + ['cat', 'gdrive:' + p], stdout=subprocess.PIPE)
    t = Tee(proc.stdout)
    err, members, mans = None, 0, 0
    try:
        with tarfile.open(fileobj=t, mode='r|*') as a:
            for m in a:
                members += 1
                if m.isfile() and 'manifest' in m.name.lower():
                    mans += 1
    except Exception as e:
        err = str(e)[:100]
    while True:
        b = t.read(1 << 20)
        if not b:
            break
    proc.wait()
    ok = (err is None and t.n == lj['Size'] and t.h.hexdigest() == lj['Hashes']['md5'])
    row = {'archive': p.split('/')[-1], 'size_drive': lj['Size'], 'bytes_read': t.n, 'md5_equal': t.h.hexdigest() == lj['Hashes']['md5'], 'tar_parse_error': err, 'members': members, 'manifests': mans, 'verdict': 'COMPLETE' if ok else 'PROBLEM'}
    print(row, flush=True)
    out.append(row)
json.dump(out, open(f'{WORK}/m15_3seed_v2/verify_err_tars.json', 'w'), indent=1)
