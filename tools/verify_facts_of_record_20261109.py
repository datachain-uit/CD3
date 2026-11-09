"""E4 (request 2026-11-09): re-hash every file listed in FACTS_OF_RECORD_sha256.txt as it is on Drive now and compare with the listed sha256/bytes.
Usage: python tools/verify_facts_of_record_20261109.py --sums FILE --work DIR --out report.json   (needs rclone remote `gdrive:` and --drive-root-folder-id inside RCLONE_ARGS env)
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument('--sums', type=Path, required=True)
ap.add_argument('--work', type=Path, required=True)
ap.add_argument('--out', type=Path, required=True)
ap.add_argument('--root-id', default='1GWiedVROrxp8jvGbd0xmvVmWriZUkpOn')
args = ap.parse_args()
rows = []
for line in args.sums.read_text(encoding='utf-8').splitlines():
    m = re.match(r'([0-9a-f]{64})\s+(\d+)\s+(.+)$', line.strip())
    if m:
        rows.append((m.group(1), int(m.group(2)), m.group(3)))
if args.work.exists():
    shutil.rmtree(args.work)
args.work.mkdir(parents=True)
lst = args.work / 'files.txt'
lst.write_text('\n'.join(r[2] for r in rows) + '\n', encoding='utf-8')
dest = args.work / 'dl'
proc = subprocess.run(['rclone', '--drive-root-folder-id', args.root_id, 'copy', 'gdrive:', str(dest), '--files-from', str(lst), '--transfers', '8', '-q'],
                      capture_output=True, text=True)
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
missing, mismatch, ok = [], [], 0
for digest, size, rel in rows:
    p = dest / rel
    if not p.is_file():
        missing.append(rel)
    elif sha(p) != digest or p.stat().st_size != size:
        mismatch.append({'path': rel, 'listed_sha256': digest[:16], 'actual_sha256': sha(p)[:16], 'listed_bytes': size, 'actual_bytes': p.stat().st_size})
    else:
        ok += 1
out = {'listed_files': len(rows), 'ok': ok, 'missing_on_drive': missing, 'mismatch': mismatch, 'rclone_stderr': proc.stderr[-400:]}
args.out.write_text(json.dumps(out, indent=1) + '\n', encoding='utf-8')
print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in out.items() if k != 'rclone_stderr'}))
for m in mismatch[:10]:
    print('MISMATCH', m)
for m in missing[:10]:
    print('MISSING', m)
