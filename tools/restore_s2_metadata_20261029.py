"""Compare Modal input hashes to Drive and restore S2 ledger/manifest per run."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

TASK=sys.argv[1].upper()
PROFILE={'CQ':'sghqvbg','LO':'minhman26804'}[TASK]
ROOT=Path(__file__).resolve().parents[1]
RCLONE=Path(os.environ['LOCALAPPDATA'])/'Microsoft/WinGet/Packages/Rclone.Rclone_Microsoft.Winget.Source_8wekyb3d8bbwe/rclone-v1.75.1-windows-amd64/rclone.exe'
hash_file=ROOT/'downloads'/f'modal_input_hashes_{TASK}_20261029.json'
deadline=time.monotonic()+10800
while not hash_file.exists():
    if time.monotonic() > deadline: raise SystemExit('Timed out waiting for Modal checksums')
    time.sleep(15)
records=json.loads(hash_file.read_text(encoding='utf-8'))
remote=f'gdrive:Jobs/{TASK}/organized_moved_20261029/L1_runs'
hashes={}
for stage in ('S1_imputation','S2_augmentation'):
    proc=subprocess.run([str(RCLONE),'md5sum',f'{remote}/{stage}/model_inputs_seed42'],capture_output=True,text=True,check=True)
    for line in proc.stdout.splitlines():
        digest, name=line.split(None,1)
        hashes[(stage,name.strip())]=digest.lower()
bad=[]
for r in records:
    stage='S2_augmentation' if '/balanced_train.parquet' in r['remote_path'] else 'S1_imputation'
    name=f"{r['window']}/{r['pipeline']}/"+('balanced_train.parquet' if stage=='S2_augmentation' else 'train.parquet')
    if r.get('md5') != hashes.get((stage,name)): bad.append({'window':r['window'],'pipeline':r['pipeline'],'reason':'hash mismatch or missing'})
report={'task':TASK,'checked':len(records),'matched':len(records)-len(bad),'failures':bad}
out=ROOT/'downloads'/f'drive_modal_input_comparison_{TASK}_20261029.json'
out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report),flush=True)
if bad: raise SystemExit('Stopping: input comparison did not pass')
staging=ROOT/'downloads'/'s2_provenance_20261029'/TASK
for r in records:
    if 'synthetic_ledger.parquet' not in r: continue
    for name in ('synthetic_ledger.parquet','run_manifest.json'):
        meta=r[name]
        if not meta['exists']: raise SystemExit(f"Missing Modal {r['window']}/{r['pipeline']}/{name}")
        local=staging/r['window']/r['pipeline']/name
        local.parent.mkdir(parents=True,exist_ok=True)
        if not local.exists() or local.stat().st_size != meta['size']:
            subprocess.run([sys.executable,'-X','utf8','-m','modal','volume','get','--profile',PROFILE,'--force','tempo-data-v1',meta['remote_path'],str(local)],check=True)
        if local.stat().st_size != meta['size']: raise SystemExit(f'Bad size: {local}')
    print(f"DOWNLOADED {TASK}/{r['window']}/{r['pipeline']}",flush=True)
dest=f'{remote}/S2_augmentation/provenance_seed42'
subprocess.run([str(RCLONE),'copy',str(staging),dest,'--immutable','--transfers','4','--stats','30s'],check=True)
subprocess.run([str(RCLONE),'check',str(staging),dest,'--one-way'],check=True)
print(f'VERIFIED_S2_PROVENANCE {TASK}',flush=True)
