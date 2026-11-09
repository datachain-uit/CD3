"""Create a verified, lossless sharded copy of an existing Mantis cache."""
import modal

app = modal.App('mantis-cache-full-compress-20261107')
volume = modal.Volume.from_name('tempo-data-v1', create_if_missing=False)
image = modal.Image.debian_slim(python_version='3.12').pip_install('numpy>=1.26,<3', 'zstandard>=0.23')


@app.function(image=image, cpu=4, memory=8192, timeout=43200, volumes={'/data': volume})
def compress():
    import datetime
    import hashlib
    import json
    import os
    import time
    from pathlib import Path
    import numpy as np
    import zstandard as zstd

    source = Path('/data/diagnostics/mantis_v2_cq_w1_v1_one_epoch/20261106T125608Z/cache')
    found = {p.parent.name.replace('split=', ''): p for p in source.rglob('embeddings.npy') if (p.parent/'manifest.json').is_file()}
    required = ('REAL_TRAIN', 'VALIDATION', 'TEST')
    if not set(required) <= found.keys():
        raise RuntimeError('Missing completed source cache split')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    root = Path('/data/diagnostics/mantis_cache_zstd_v1') / stamp
    root.mkdir(parents=True, exist_ok=False)
    info = {'source': str(source), 'output': str(root), 'codec': 'zstd', 'level': 3,
            'shard_rows': 2048, 'status': 'RUNNING', 'splits': {}}
    compressor, decoder = zstd.ZstdCompressor(level=3), zstd.ZstdDecompressor()
    t0 = time.monotonic()
    print(json.dumps({'event':'started','output':str(root)}), flush=True)
    for split in required:
        p = found[split]; arr = np.load(p, mmap_mode='r')
        if arr.dtype != np.float16 or arr.shape[1:] != (4,4096):
            raise ValueError(f'Unexpected shape/dtype: {p} {arr.shape} {arr.dtype}')
        out = root / split; out.mkdir()
        manifest = {'source_file': str(p), 'source_manifest': json.loads((p.parent/'manifest.json').read_text()),
                    'shape': list(arr.shape), 'dtype': str(arr.dtype), 'shards': []}
        raw_total = compressed_total = 0
        for i, start in enumerate(range(0, len(arr), 2048)):
            end = min(start + 2048, len(arr)); data = np.ascontiguousarray(arr[start:end]).tobytes()
            sha = hashlib.sha256(data).hexdigest(); packed = compressor.compress(data)
            dest = out / f'{i:06d}.zst'; temp = dest.with_suffix('.zst.partial')
            temp.write_bytes(packed); os.replace(temp, dest)
            restored = decoder.decompress(dest.read_bytes())
            if hashlib.sha256(restored).hexdigest() != sha:
                raise RuntimeError(f'Round-trip verification failed: {dest}')
            raw_total += len(data); compressed_total += dest.stat().st_size
            manifest['shards'].append({'file':dest.name, 'start':start, 'end':end,
              'source_bytes':len(data), 'compressed_bytes':dest.stat().st_size, 'source_sha256':sha,
              'compressed_sha256':hashlib.sha256(packed).hexdigest()})
            if (i+1) % 25 == 0 or end == len(arr):
                print(json.dumps({'event':'progress','split':split,'rows':end,'rows_total':len(arr),
                      'shards':i+1,'raw_bytes':raw_total,'compressed_bytes':compressed_total,
                      'elapsed_seconds':round(time.monotonic()-t0,1)}),flush=True)
            if sum(x.get('compressed_bytes',0) for x in info['splits'].values()) + compressed_total > 20 * 1024**3:
                raise RuntimeError('Safety limit: compressed output exceeded 20 GiB')
        (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        info['splits'][split] = {'rows':len(arr),'shards':len(manifest['shards']),'raw_bytes':raw_total,
            'compressed_bytes':compressed_total,'ratio':compressed_total/raw_total,'all_shards_roundtrip_verified':True}
        (root/'summary.json').write_text(json.dumps(info,indent=2)+'\n')
        volume.commit()
    info['status']='SUCCESS';info['elapsed_seconds']=round(time.monotonic()-t0,1)
    (root/'summary.json').write_text(json.dumps(info,indent=2)+'\n');volume.commit()
    print(json.dumps(info),flush=True)
    return info


@app.local_entrypoint()
def main():
    print(compress.remote())
