"""Export the verified V1 cache only, with independently checked shard hashes."""
import hashlib,json,tarfile
from pathlib import Path
import modal

app=modal.App('export-cq-moment-v1-cache-20261105')
volume=modal.Volume.from_name('tempo-data-v1',create_if_missing=False)
@app.function(image=modal.Image.debian_slim(python_version='3.12'),volumes={'/data':volume},timeout=3600,cpu=2,memory=4096)
def export():
    cache=Path('/data/meta_release=imputation-v1/L3_meta/diagnostics/cq_moment_sharded_cache_w1_v1_20261105/8c66c22f24cb4e59892267057966163517c0ff6d1d245dcb6b7b34f7237124d1')
    if not (cache/'CACHE_VERIFIED').is_file():raise ValueError('Cache is not verified')
    files=[cache/'identity.json',cache/'CACHE_VERIFIED']
    for split,rows in [('train',1609276),('validation',175689)]:
        for offset in range(0,rows,16384):
            marker=cache/f'{split}_{offset:09d}.json'; shard=cache/f'{split}_{offset:09d}.npz'
            record=json.loads(marker.read_text())
            with shard.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
            if digest!=record['sha256'] or record['rows']!=min(16384,rows-offset):raise ValueError(f'Invalid shard: {shard.name}')
            files.extend([shard,marker])
    dest=Path('/data/diagnostics/cq_moment_v1_cache_transfer_20261105.tar.gz')
    if dest.exists():raise ValueError('Archive exists; refusing overwrite')
    with tarfile.open(dest,'w:gz',compresslevel=1) as archive:
        for f in files:archive.add(f,arcname=f.name,recursive=False)
    with dest.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
    volume.commit();result={'archive':str(dest),'sha256':digest,'files':len(files),'bytes':dest.stat().st_size}
    print(json.dumps(result),flush=True);return result
@app.local_entrypoint()
def main():print(json.dumps(export.remote()))
