"""Verify downloaded subgroup packages before five-subgroup assembly."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'tmp/s0_v5_inputs/subgroup_facts'
OUT=ROOT/'CQ/resuilt/s0_v5_subgroup_preflight_20261122'
expected={(t,m,s) for t in ('CQ','LO') for m in ('RNN','LSTM','GRU','BILSTM','PATCHTST','MANTIS_V2') for s in (42,43,44)}
seen=set(); bad=[]; statuses=Counter(); total=0
for folder in sorted(p for p in SOURCE.iterdir() if p.is_dir()):
    try:
        for line in (folder/'sha256sums.txt').read_text(encoding='utf8').splitlines():
            digest,name=line.split(None,1); path=folder/name.strip()
            actual=hashlib.sha256(path.read_bytes()).hexdigest()
            if actual.lower()!=digest.lower(): bad.append(f'{path}: hash mismatch')
        meta=json.loads((folder/'summary.json').read_text(encoding='utf8'))
        key=(meta['task'],meta['model'],int(meta['seed']))
        if key in seen: bad.append(f'duplicate {key}')
        seen.add(key); statuses[meta.get('status','MISSING')]+=1
        frame=pd.read_parquet(folder/'subgroup_components.parquet')
        total+=len(frame)
        if len(frame)!=1632: bad.append(f'{key}: rows={len(frame)}')
    except Exception as exc:
        bad.append(f'{folder}: {exc}')
report={'status':'PASS' if not bad and seen==expected and total==58752 else 'FAIL',
        'packages':len(seen),'rows':total,'statuses':dict(statuses),'missing':[list(x) for x in sorted(expected-seen)],'errors':bad}
(OUT/'subgroup_packages_verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
print(json.dumps(report,indent=2),flush=True)
if report['status']!='PASS': raise SystemExit(1)
