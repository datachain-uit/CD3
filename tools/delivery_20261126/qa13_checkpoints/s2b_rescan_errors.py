"""re-scan archives whose first scan stopped early (transient Drive read errors); up to 3 attempts, partial results are kept and flagged"""
import os, json, glob, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from tarlist import scan
for f in glob.glob(os.environ.get('QA13_DIR', '.') + '/tar_scan/*.json'):
    j = json.load(open(f))
    early = any(m[0].startswith('__STREAM_ENDED_EARLY__') for m in j['members'])
    if j['status'] == 'OK' and not early: continue
    for att in range(3):
        res = scan(j['tar'])
        if not any(m[0].startswith('__STREAM_ENDED_EARLY__') for m in res): break
    j.update(status='OK', members=res, seconds=0, rescanned=att + 1)
    json.dump(j, open(f, 'w'))
    print(j['tar'][-70:], 'attempts', att + 1, 'early' if any(m[0].startswith('__STREAM_ENDED_EARLY__') for m in res) else 'complete', flush=True)
