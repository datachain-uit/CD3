"""Verify seed-42 S2 ledger and manifest coverage and fingerprint ledger files."""
from pathlib import Path
import hashlib, json

BASE=Path('G:/My Drive/Jobs/CQ/organized_moved_20261029/L1_runs/S2_augmentation/provenance_seed42')
OUT=Path('CQ/resuilt/input/results/R21_evidence_20261031/CQ/S2_seed42/ledger_inventory.json')
def main():
    rows=[]
    for w in ('W1','W2','W3'):
        for p in ('V2','V3','V4','V6','V7','V8','V10','V11','V12','V14','V15','V16'):
            folder=BASE/w/p; ledger=folder/'synthetic_ledger.parquet'; manifest=folder/'run_manifest.json'
            row={'window':w,'pipeline':p,'ledger_source':str(ledger),'manifest_source':str(manifest),'ledger_exists':ledger.is_file(),'manifest_exists':manifest.is_file()}
            if row['ledger_exists']:
                with ledger.open('rb') as f: row['ledger_sha256']=hashlib.file_digest(f,'sha256').hexdigest()
                row['ledger_bytes']=ledger.stat().st_size
            if row['manifest_exists']:
                with manifest.open('rb') as f: row['manifest_sha256']=hashlib.file_digest(f,'sha256').hexdigest()
            rows.append(row); print(w,p,flush=True)
    OUT.write_text(json.dumps({'scope':'CQ S2 seed42; source files on Drive; no local ledger copy','entries':rows},indent=2)+'\n',encoding='utf8')
    print('complete',sum(x['ledger_exists'] and x['manifest_exists'] for x in rows),'/ 36')
if __name__=='__main__': main()
