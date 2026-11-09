"""Measure one full-grid shuffled batch across the actual W1 compressed cache."""
import json
import modal
app=modal.App('mantis-cache-global-random-probe-20261107')
volume=modal.Volume.from_name('tempo-data-v1',create_if_missing=False)
image=modal.Image.debian_slim(python_version='3.12').pip_install('numpy>=1.26,<3','zstandard>=0.23')
@app.function(image=image,cpu=4,memory=8192,timeout=1800,volumes={'/data':volume})
def probe():
 import json,time,hashlib
 from pathlib import Path
 import numpy as np,zstandard as zstd
 root=Path('/data/diagnostics/mantis_cache_zstd_v1/20261106T181738Z/REAL_TRAIN')
 m=json.loads((root/'manifest.json').read_text()); n=m['shape'][0]
 idx=np.random.default_rng(42).choice(n,size=2048,replace=False); shard_ids=idx//2048
 decoder=zstd.ZstdDecompressor(); out=np.empty((len(idx),4,4096),np.float16); t=time.monotonic(); packed=0;raw=0
 for count,shard in enumerate(np.unique(shard_ids)):
  s=m['shards'][int(shard)];data=(root/s['file']).read_bytes();packed+=len(data)
  if hashlib.sha256(data).hexdigest()!=s['compressed_sha256']:raise ValueError('compressed hash mismatch')
  decoded=decoder.decompress(data);raw+=len(decoded)
  if hashlib.sha256(decoded).hexdigest()!=s['source_sha256']:raise ValueError('source hash mismatch')
  values=np.frombuffer(decoded,np.float16).reshape(s['end']-s['start'],4,4096)
  mask=shard_ids==shard;out[mask]=values[idx[mask]-s['start']]
  if (count+1)%100==0:print(json.dumps({'event':'progress','shards':count+1,'elapsed':round(time.monotonic()-t,2)}),flush=True)
 return {'rows':len(idx),'dataset_rows':n,'shards_touched':len(np.unique(shard_ids)),'total_shards':len(m['shards']), 'compressed_bytes_read':packed,'uncompressed_bytes_decoded':raw,'elapsed_s':time.monotonic()-t,'finite':bool(np.isfinite(out).all()),'batch_sha256':hashlib.sha256(out.tobytes()).hexdigest(),'note':'cold volume reads, SHA checks included; one batch; no model training'}
@app.local_entrypoint()
def main():print(json.dumps(probe.remote(),indent=2))
