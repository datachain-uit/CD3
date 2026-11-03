"""Recompute S0 snapshot identity and classify R4 ingest metadata contracts."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import hashlib,json,os,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from imputation_core.meta_storage import canonical_hash

JOBS=Path(os.environ.get('CD3_JOBS_ROOT','data/Jobs'))
CQ=JOBS/'CQ/organized_moved_20261029'
S0=CQ/'L0_registry/modal_L0_registry/L0_registry/state_manifests/s0_CQ.json'
ART=CQ/'L2_facts/fact_exports/cq_f1_allfamilies_l2_ingest_r3_20261021/artifacts'
OUT=Path('CQ/resuilt/cq_release_identity_partial_20261103')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(path):
    m=json.loads(path.read_text(encoding='utf8'));r=m.get('release') or {};identity=m.get('model_identity') or {}
    return {'relative_path':path.relative_to(ART).as_posix(),'sha256':sha(path),'release':r,'model_identity':identity}
def main():
    source=json.loads(S0.read_text(encoding='utf8'))['release'];computed='sha256:'+canonical_hash({'inventory':source['inventory'],'sidecar':source['input_release_manifest']})
    if computed!=source['data_release_id']:raise ValueError('S0 snapshot identity mismatch')
    paths=sorted(ART.rglob('metadata_contract.json'))
    if len(paths)!=204:raise ValueError(f'expected 204 metadata contracts, got {len(paths)}')
    required={'task':'CQ','release_id':'CQ_V2_2','split_version':'v2_2','phase_version':'wide_prefix_v2_2','label_rule_version':'cq_vector_proximity_v1_zero_activity_policy','label_threshold_set':'CQ_VECTOR_PROXIMITY_PRIMARY_V1'}
    with ThreadPoolExecutor(max_workers=12) as pool:rows=list(pool.map(read,paths))
    counts={}
    for row in rows:
        r=row['release'];contract_ok=all(r.get(k)==v for k,v in required.items())
        row['classification']='CURRENT' if contract_ok and r.get('data_release_id')==computed else 'UNMATCHED_OR_UNVERIFIED'
        counts[row['classification']]=counts.get(row['classification'],0)+1
    OUT.mkdir(parents=True,exist_ok=True)
    result={'created_at_utc':datetime.now(timezone.utc).isoformat(),'status':'PARTIAL_SNAPSHOT_NOT_FULL_LEDGER','task':'CQ','release_id':'CQ_V2_2','current_snapshot_identity':computed,'s0_snapshot_sha256':sha(S0),'current_identity_recomputed_from_saved_inventory':'PASS','contracts_scanned':len(rows),'classifications':counts,'legacy_identity':'NOT_RECONSTRUCTED_WITHOUT_ORIGINAL_LINEAGE_INVENTORY','contracts':rows}
    (OUT/'ledger_snapshot.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    (OUT/'README.md').write_text('# CQ release identity — partial snapshot\n\nRecomputes current data_release_id from the saved S0 inventory and release sidecar, then classifies the 204 R4-ingest metadata contracts against the locked CQ release fields. CURRENT is a snapshot-based classification, not a fresh scan of the original volume. The legacy-with-lineage alias is not reconstructed because the complete original sidecar path/size inventory is not available here. This is not the full release_identity_ledger_app output and does not close M-08.\n',encoding='utf8')
    fs=sorted(p for p in OUT.iterdir() if p.is_file() and p.name!='sha256sums.txt');(OUT/'sha256sums.txt').write_text(''.join(sha(p)+'  '+p.name+'\n' for p in fs),encoding='utf8');print(json.dumps({k:v for k,v in result.items() if k!='contracts'},indent=2))
if __name__=='__main__':main()
