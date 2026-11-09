import hashlib,tarfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=root/'downloads/vastai/LO_V3_1_clean_grain_seed42'
archives=['lo_patchtst_v2_inputs_20261106.tar.gz','lo_patchtst_v3_inputs_20261106.tar.gz','lo_patchtst_v4_inputs_20261107.tar.gz','lo_patchtst_v6_inputs_20261107.tar.gz']
for name in archives:
    path=root/'LO/resuilt'/name
    if not path.is_file(): continue
    ok=True; count=0
    with tarfile.open(path,'r:gz') as tar:
        for m in tar:
            if not m.isfile(): continue
            p=(source/m.name).resolve()
            if not p.is_relative_to(source.resolve()) or not p.is_file() or p.stat().st_size!=m.size:
                print('SKIP',name,m.name,'missing_or_size',flush=True);ok=False;break
            inp=tar.extractfile(m)
            with p.open('rb') as f:
                if hashlib.file_digest(inp,'sha256').digest()!=hashlib.file_digest(f,'sha256').digest():
                    print('SKIP',name,m.name,'hash',flush=True);ok=False;break
            count+=1
    if ok and count:
        size=path.stat().st_size;path.unlink();print('DELETED',name,'bytes',size,'verified_files',count,flush=True)
