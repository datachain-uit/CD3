import hashlib,json,tarfile,time
from pathlib import Path
root=Path(__file__).resolve().parents[1]
archive=root/'LO/resuilt/LO_V3_1_clean_grain_seed42_20261023.tar'
dest=root/'downloads/vastai/LO_V3_1_clean_grain_seed42'
out=root/'LO/resuilt/lo_input_tar_comparison_20261107.json'
results={'archive':str(archive),'destination':str(dest),'status':'RUNNING','verified':0,'different':[],'missing':[]}
out.write_text(json.dumps(results,indent=2),encoding='utf-8')
with tarfile.open(archive,'r:') as tf:
    for m in tf:
        if not m.isfile(): continue
        rel=Path(m.name).relative_to('LO_V3_1_clean_grain_seed42')
        target=(dest/rel).resolve()
        if not target.is_relative_to(dest.resolve()): raise ValueError('unsafe archive path')
        if not target.is_file():results['missing'].append(str(rel));continue
        if target.stat().st_size!=m.size:results['different'].append({'path':str(rel),'reason':'size'});continue
        inp=tf.extractfile(m)
        with target.open('rb') as f:
            if hashlib.file_digest(inp,'sha256').digest()!=hashlib.file_digest(f,'sha256').digest():
                results['different'].append({'path':str(rel),'reason':'sha256'});continue
        results['verified']+=1
results['status']='MATCH' if not results['missing'] and not results['different'] else 'DIFFERENCES'
out.write_text(json.dumps(results,indent=2),encoding='utf-8')
print(json.dumps(results,indent=2))
