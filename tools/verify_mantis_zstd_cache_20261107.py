"""Verify all compressed cache component hashes and require expected splits."""
import argparse,hashlib,json
from pathlib import Path
parser=argparse.ArgumentParser()
parser.add_argument('root',type=Path)
parser.add_argument('--allow-cell-train',action='store_true',help='Allow a balanced cell to build an independent CELL_TRAIN cache.')
args=parser.parse_args()
root=args.root;manifests=list(root.rglob('manifest.json'))
found=set()
for path in manifests:
    m=json.loads(path.read_text());found.add(m['key']['split'])
    for name,key in [('frames.bin','frames_sha256'),('index.npy','index_sha256'),('row_ids.npy','row_ids_sha256')]:
        h=hashlib.sha256()
        with (path.parent/name).open('rb') as f:
            for chunk in iter(lambda:f.read(4*1024*1024),b''):h.update(chunk)
        if h.hexdigest()!=m[key]:raise ValueError(f'Hash mismatch: {path.parent/name}')
expected=[{'REAL_TRAIN','VALIDATION','TEST'}]
if args.allow_cell_train:
    expected.extend([{'CELL_TRAIN','VALIDATION','TEST'}, {'REAL_TRAIN','SYNTH_TRAIN','VALIDATION','TEST'}])
if found not in expected:raise ValueError(f'Unexpected cache splits: {found}')
print(json.dumps({'status':'CACHE_HASH_VERIFIED','splits':sorted(found),'manifests':len(manifests)}),flush=True)
