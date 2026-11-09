"""Measure lossless compression on existing, completed Mantis embeddings."""
import json
import modal

app = modal.App('mantis-cache-compression-probe-20261107')
volume = modal.Volume.from_name('tempo-data-v1', create_if_missing=False)
image = modal.Image.debian_slim(python_version='3.12').pip_install('numpy>=1.26,<3', 'zstandard>=0.23')


@app.function(image=image, cpu=4, memory=8192, timeout=1800, volumes={'/data': volume})
def probe():
    import hashlib
    import time
    from pathlib import Path
    import numpy as np
    import zstandard as zstd

    root = Path('/data/diagnostics/mantis_v2_cq_w1_v1_one_epoch/20261106T125608Z/cache')
    candidates = sorted(p for p in root.rglob('embeddings.npy') if (p.parent / 'manifest.json').is_file())
    if not candidates:
        raise RuntimeError(f'No complete embedding cache found under {root}')
    results = []
    for path in candidates:
        arr = np.load(path, mmap_mode='r')
        n = min(2048, len(arr))
        if not n:
            continue
        starts = sorted(set([0, max(0, (len(arr) - n) // 2), max(0, len(arr) - n)]))
        sample = np.concatenate([np.asarray(arr[start:start+n]) for start in starts], axis=0)
        if sample.dtype != np.float16:
            raise ValueError(f'Unexpected dtype {sample.dtype}')
        raw = sample.tobytes()
        for mode in ('raw', 'byte_shuffle'):
            t0 = time.perf_counter()
            data = raw if mode == 'raw' else np.frombuffer(raw, np.uint8).reshape(-1, 2).T.copy().tobytes()
            packed = zstd.ZstdCompressor(level=3).compress(data)
            compress_s = time.perf_counter() - t0
            t0 = time.perf_counter()
            decoded = zstd.ZstdDecompressor().decompress(packed)
            if mode == 'byte_shuffle':
                decoded = np.frombuffer(decoded, np.uint8).reshape(2, -1).T.copy().tobytes()
            decode_s = time.perf_counter() - t0
            results.append({'path': str(path), 'shape': list(arr.shape), 'sample_starts': starts,
                'sample_rows': len(sample), 'dtype': str(arr.dtype), 'mode': mode, 'raw_bytes': len(raw),
                'zero_fraction': float(np.count_nonzero(sample == 0) / sample.size),
                'sample_distinct_prefix_rows': int(np.unique(sample[:, 0, :], axis=0).shape[0]),
                'compressed_bytes': len(packed), 'ratio': len(packed)/len(raw),
                'compression_s': compress_s, 'decompression_s': decode_s,
                'byte_exact': hashlib.sha256(raw).digest() == hashlib.sha256(decoded).digest()})
    return {'codec': 'zstd_level_3', 'results': results, 'note': 'samples only; no input artifacts modified'}


@app.local_entrypoint()
def main():
    print(json.dumps(probe.remote(), indent=2))
