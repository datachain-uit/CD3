"""Fingerprint selected Drive evidence without copying its content."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib,json,os

BASE=Path('G:/My Drive/Jobs')
QA=BASE/'CQ/organized_moved_20261029/L2_facts/fact_exports/qa23_v2_2'
ARCHIVE=BASE/'LO/organized_moved_20261029/L1_runs/S3_model/run_bundles/lo_static_v2_seed42_20261026/archives/LO_static_v2_closure_20261028.tar.gz'
OUT=Path('CQ/resuilt/input/results/R21_evidence_20261031/drive_sha256_inventory.json')
EXPECTED='9108372950940430d9b72f950637088912bdc476bc062a54527527ddf60740d3'
def hashfile(path):
    with path.open('rb') as f: digest=hashlib.file_digest(f,'sha256').hexdigest()
    return {'path':str(path),'bytes':path.stat().st_size,'sha256':digest}
def main():
    paths=sorted(QA.rglob('*.parquet'))
    if not paths or not ARCHIVE.is_file(): raise RuntimeError('QA23 or closure archive missing')
    rows=[]; errors=[]
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures={pool.submit(hashfile,p):p for p in paths+[ARCHIVE]}
        for index,future in enumerate(as_completed(futures),1):
            try: rows.append(future.result())
            except Exception as e: errors.append({'path':str(futures[future]),'error':str(e)})
            if index%100==0 or index==len(futures): print(f'hashed {index}/{len(futures)}; errors={len(errors)}',flush=True)
    archive=next((r for r in rows if r['path']==str(ARCHIVE)),None)
    result={'scope':'LO closure archive and CQ QA23 parquet files on Drive','qa23_parquet_count_expected':len(paths),'hashed_count':len(rows),'errors':errors,'archive_reference_receipt_sha256':EXPECTED,'archive_matches_reference':archive is not None and archive['sha256']==EXPECTED,'files':sorted(rows,key=lambda x:x['path'])}
    OUT.parent.mkdir(parents=True,exist_ok=True); tmp=OUT.with_suffix('.tmp'); tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8'); os.replace(tmp,OUT)
    print(json.dumps({'inventory':str(OUT),'qa23_parquet':len(paths),'hashed':len(rows),'errors':len(errors),'archive_matches_reference':result['archive_matches_reference']}),flush=True)
    if errors or not result['archive_matches_reference']: raise SystemExit(1)
if __name__=='__main__': main()
