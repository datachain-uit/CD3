"""Read-only sample of Mantis cache; compression and shuffled batch access."""
import json
from pathlib import Path
import modal

app = modal.App('mantis-cache-shard-bench-20261107')
volume = modal.Volume.from_name('tempo-data-v1', create_if_missing=False)
image = modal.Image.debian_slim(python_version='3.12').pip_install('numpy>=1.26,<3', 'zstandard>=0.23')


@app.function(image=image, cpu=4, memory=8192, timeout=1800, volumes={'/data': volume})
def bench():
    import time
    import tempfile
    import hashlib
    import numpy as np
    import zstandard as zstd

    root = Path('/data/diagnostics/mantis_v2_cq_w1_v1_one_epoch/20261106T125608Z/cache')
    found = {p.parent.name.replace('split=', ''): p for p in root.rglob('embeddings.npy') if (p.parent/'manifest.json').exists()}
    if not {'REAL_TRAIN', 'VALIDATION', 'TEST'} <= found.keys():
        raise ValueError('Missing completed cache split')
    result = {'codec': 'zstd_level_3', 'shard_rows': 2048, 'source': str(root), 'splits': {}}
    compressor, decoder = zstd.ZstdCompressor(level=3), zstd.ZstdDecompressor()
    with tempfile.TemporaryDirectory() as tmp:
        for split in ('REAL_TRAIN', 'VALIDATION', 'TEST'):
            arr = np.load(found[split], mmap_mode='r')
            sample_shards = 8 if split == 'REAL_TRAIN' else 4
            starts = [int(x) for x in np.linspace(0, len(arr)-2048, sample_shards)]
            files, raw_samples, packed_bytes = [], [], 0
            t0 = time.perf_counter()
            for i, start in enumerate(starts):
                sample = np.ascontiguousarray(arr[start:start+2048]); raw = sample.tobytes()
                out = Path(tmp)/f'{split}_{i}.zst'; packed = compressor.compress(raw); out.write_bytes(packed)
                if hashlib.sha256(decoder.decompress(packed)).digest() != hashlib.sha256(raw).digest():
                    raise ValueError('lossless check failed')
                packed_bytes += len(packed); files.append(out); raw_samples.append(sample)
            encode_and_verify_s = time.perf_counter()-t0
            sample_n = sample_shards*2048
            sample_bytes = sample_n*4*4096*2
            diversity = []
            for phase in range(4):
                rows = np.concatenate([x[::16,phase,:] for x in raw_samples], axis=0)
                diversity.append({'phase':phase+1, 'sample_rows':len(rows), 'unique_vectors':int(np.unique(rows,axis=0).shape[0])})
            data = {'rows_total':len(arr), 'shards_sampled':sample_shards, 'sample_rows':sample_n,
                'raw_bytes':sample_bytes, 'packed_bytes':packed_bytes, 'ratio':packed_bytes/sample_bytes,
                'encode_verify_and_write_s':encode_and_verify_s, 'byte_exact':True, 'diversity':diversity}
            if split == 'REAL_TRAIN':
                rng = np.random.default_rng(42)
                batches = [rng.permutation(sample_n)[0:2048] for _ in range(8)]
                t0=time.perf_counter(); checksum_ref=0.0
                for idx in batches:
                    for shard in range(sample_shards):
                        local=idx[idx//2048==shard] % 2048
                        checksum_ref += float(raw_samples[shard][local].sum(dtype=np.float64))
                baseline=time.perf_counter()-t0
                t0=time.perf_counter(); checksum_zstd=0.0; shards_loaded=0
                for idx in batches:
                    for shard in range(sample_shards):
                        local=idx[idx//2048==shard] % 2048
                        if len(local):
                            values=np.frombuffer(decoder.decompress(files[shard].read_bytes()),np.float16).reshape(2048,4,4096)
                            checksum_zstd += float(values[local].sum(dtype=np.float64)); shards_loaded += 1
                data['shuffled_access']={'batches':len(batches),'batch_size':2048,'sample_population':sample_n,
                    'uncompressed_s':baseline,'compressed_s':time.perf_counter()-t0,'shards_loaded':shards_loaded,
                    'checksum_matches':bool(checksum_ref==checksum_zstd),
                    'note':'warm local temporary filesystem; CPU only; not full training benchmark'}
            result['splits'][split]=data
    return result


@app.local_entrypoint()
def main():
    result=bench.remote()
    out=Path('CQ/resuilt/mantis_cache_shard_bench_20261107.json')
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
