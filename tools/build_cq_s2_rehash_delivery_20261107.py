import hashlib,json,shutil
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'CQ/resuilt/cq_s2_sampling_seed42_partial_20261103'
BASE=ROOT/'CQ/resuilt/cq_s2_rehash_20261107'
SOURCE=BASE/'source'
OUT=BASE/'delivery'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    inv=json.loads((OLD/'ledger_inventory.json').read_text(encoding='utf8'))['entries']
    if len(inv)!=36:raise ValueError('expected 36 ledger entries')
    entries=[]
    for x in inv:
        m=SOURCE/x['manifest_relative_path'];l=SOURCE/x['ledger_relative_path']
        actual_m,actual_l=sha(m),sha(l)
        if actual_m!=x['manifest_sha256'] or actual_l!=x['ledger_sha256_previously_recorded'] or l.stat().st_size!=x['ledger_bytes']:
            raise ValueError('prior inventory mismatch '+str(l))
        manifest=json.loads(m.read_text(encoding='utf8'))
        if (manifest.get('task'),manifest.get('window_id'),manifest.get('balance_pipeline'))!=('CQ',x['window_id'],x['pipeline_id']):raise ValueError('identity mismatch '+str(m))
        entries.append({**x,'ledger_sha256_recomputed':actual_l,'ledger_hash_status':'MATCHES_PRIOR_INVENTORY','manifest_hash_status':'MATCHES_PRIOR_INVENTORY'})
    OUT.mkdir(parents=True,exist_ok=True)
    for name in ('s2_sampling_summary_cq_seed42.csv','s2_sampling_summary_cq_seed42.parquet'):shutil.copy2(OLD/name,OUT/name)
    (OUT/'ledger_inventory.json').write_text(json.dumps({'entries':entries},indent=2)+'\n',encoding='utf8')
    summary={'task':'CQ','seed':42,'created_at_utc':datetime.now(timezone.utc).isoformat(),'runs':36,'sampling_summary_rows':108,'manifest_hash_matches':36,'ledger_hash_matches':36,'radius_fallback_rows':24,'kappa':'UNRESOLVED_DEFINITION','status':'PARTIAL_KAPPA_UNRESOLVED','source':'Drive shared Jobs/CQ/organized_moved_20261029/L1_runs/S2_augmentation/provenance_seed42'}
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf8')
    (OUT/'README.md').write_text('# CQ S2 seed 42 — ledger rehash\n\nAll 36 manifest and ledger SHA-256 values were recomputed from copies downloaded from the shared Drive and match the earlier inventory. Sampling summary is the previous 108-row export, including 24 verified Radius class fallback rows. kappa_reached remains null because its definition has not been ratified. This package does not resolve that definition and is not a fresh generation of S2 data.\n',encoding='utf8')
    (OUT/'sha256sums.txt').write_text(''.join(f'{sha(p)}  {p.name}\n' for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='sha256sums.txt'),encoding='utf8')
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
