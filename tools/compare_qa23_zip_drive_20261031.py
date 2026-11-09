"""Compare each QA23 parquet in a source ZIP against the Drive SHA-256 inventory."""
import hashlib,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ZIP=ROOT/'CQ/resuilt/qa23_v2_2.zip'
INV=ROOT/'CQ/resuilt/input/results/R21_evidence_20261031/drive_sha256_inventory.json'
OUT=ROOT/'CQ/resuilt/input/results/R21_evidence_20261031/qa23_zip_drive_comparison.json'
def main():
    inv=json.loads(INV.read_text(encoding='utf8'))
    drive={r['path'].replace('\\','/').split('/qa23_v2_2/',1)[1]:r for r in inv['files'] if '/qa23_v2_2/' in r['path'].replace('\\','/')}
    with zipfile.ZipFile(ZIP) as z:
        files=[x for x in z.infolist() if x.filename.endswith('.parquet')]
        source={x.filename.split('qa23_v2_2/',1)[1]:x for x in files}
        if len(source)!=len(files): raise ValueError('Duplicate parquet path in ZIP')
        only_source=sorted(set(source)-set(drive)); only_drive=sorted(set(drive)-set(source)); mismatches=[]
        for name in sorted(set(source)&set(drive)):
            with z.open(source[name]) as f: digest=hashlib.file_digest(f,'sha256').hexdigest()
            if digest!=drive[name]['sha256'] or source[name].file_size!=drive[name]['bytes']:
                mismatches.append({'path':name,'zip_sha256':digest,'drive_sha256':drive[name]['sha256']})
    result={'source_zip':str(ZIP),'drive_inventory':str(INV),'source_parquet_count':len(source),'drive_parquet_count':len(drive),'matched_count':len(set(source)&set(drive))-len(mismatches),'missing_on_drive':only_source,'missing_in_zip':only_drive,'mismatches':mismatches,'pass':not only_source and not only_drive and not mismatches}
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
