"""Step 2: stream every archive that holds accepted predictions and record, for each member that is not a prediction parquet, name/size/sha256 (checkpoint-like, json and npz members);
for prediction parquets only name/size. Resumable: one json per archive in tar_scan/. Two workers claim archives through lock files (max 2 transfers)."""
import os, sys, os, json, hashlib, time, re, hashlib as H
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
from tarlist import scan
OUT = Path(os.environ.get('QA13_DIR', '.')); SD = OUT / 'tar_scan'; SD.mkdir(exist_ok=True)
d = pd.read_csv(OUT / 'work_pred_sources_by_run.csv')
sz = {}
for T in ('CQ', 'LO'):
    for x in json.load(open(OUT / f'work_list_{T}.json')): sz[f'{T}/L1_runs/S3_model/' + x['Path']] = x['Size']
t = d[d.kinds == 'tar'].copy()
t['prio'] = t.model.map(lambda m: 0 if m == 'MANTIS_V2' else 1 if m == 'PATCHTST' else 2)
q = t.groupby('packages').prio.min().reset_index()
ex = set()      # archives of the same rank that also hold predictions of a run (tie check), scanned before the recurrent seed 43/44 archives
for r in d.itertuples():
    if isinstance(r.other_sources, str) and r.other_sources:
        for s_ in r.other_sources.split('|'):
            rk, k2, p2 = s_.split(':', 2)
            if int(rk) <= r.pick_rank and k2 == 'tar': ex.add(p2)
qx = pd.DataFrame({'packages': sorted(ex - set(q.packages))}); qx['prio'] = 1.5
q = pd.concat([q, qx], ignore_index=True)
q['sz'] = q.packages.map(sz)
q = q.sort_values(['prio', 'sz'], ascending=[True, False])
def key(p): return H.sha1(p.encode()).hexdigest()[:16]
wid = sys.argv[1]
for r in q.itertuples():
    f = SD / (key(r.packages) + '.json'); lock = SD / (key(r.packages) + '.lock')
    if f.exists(): continue
    try: fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY); os.close(fd)
    except FileExistsError: continue
    t0 = time.time()
    try:
        res = scan(r.packages); status = 'OK'
    except Exception as e:
        res = []; status = f'ERR {type(e).__name__}: {e}'
    f.write_text(json.dumps({'tar': r.packages, 'size': r.sz, 'status': status, 'seconds': round(time.time() - t0), 'members': res}), encoding='utf-8')
    lock.unlink(missing_ok=True)
    print(time.strftime('%T'), wid, status, round(r.sz / 1e6), 'MB', round(time.time() - t0), 's', r.packages[-80:], flush=True)
