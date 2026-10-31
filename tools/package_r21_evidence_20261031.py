"""Package selected R21 evidence with a manifest of every archive member."""
from pathlib import Path
import hashlib,json,zipfile

BASE=Path('CQ/resuilt/input/results/R21_evidence_20261031')
OUT=BASE.parent/'R21_evidence_20261031_REVIEW.zip'
def main():
    files=sorted(p for p in BASE.rglob('*') if p.is_file())
    forbidden=('salt','secret','token','credential','.env')
    if any(any(x in p.name.lower() for x in forbidden) for p in files): raise ValueError('Private file name found in evidence tree')
    rows=[]
    with zipfile.ZipFile(OUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for path in files:
            rel=path.relative_to(BASE).as_posix(); raw=path.read_bytes()
            rows.append({'path':rel,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
            z.writestr('R21_evidence_20261031/'+rel,raw)
        z.writestr('R21_evidence_20261031/PACKAGE_SHA256_MANIFEST.json',json.dumps({'files':rows},ensure_ascii=False,indent=2)+'\n')
    with zipfile.ZipFile(OUT) as z:
        if z.testzip() is not None: raise ValueError('ZIP CRC failure')
        saved=json.loads(z.read('R21_evidence_20261031/PACKAGE_SHA256_MANIFEST.json'))
        for item in saved['files']:
            raw=z.read('R21_evidence_20261031/'+item['path'])
            if len(raw)!=item['bytes'] or hashlib.sha256(raw).hexdigest()!=item['sha256']: raise ValueError(item['path'])
    print(json.dumps({'archive':str(OUT),'files':len(rows),'bytes':OUT.stat().st_size,'sha256':hashlib.file_digest(OUT.open('rb'),'sha256').hexdigest()}))
if __name__=='__main__': main()
