"""Smoke test of compressed cache round-trip and shuffled access."""
from pathlib import Path
import tempfile
import numpy as np
from f3_mantis.store import CacheKey,StackedFeatures
from mantis_zstd_dedup_store_20261107 import DedupZstdStore

class Adapter:
    def digest(self):return 'adapter_identity'
class Encoder:
    adapter=Adapter();fingerprint_digest='encoder_identity';embedding_dim=4
    def fingerprint(self):return {'name':'fake'}
    def encode(self,x):
        out=np.zeros((len(x),4,4),dtype=np.float16)
        out[:,:,0]=x[:,0,0,None];out[:,:,1]=np.arange(4);return out

with tempfile.TemporaryDirectory() as tmp:
    x=np.zeros((40,4,2),np.float32);x[:,0,0]=np.arange(40)%7
    ids=np.array([f'id_{i}' for i in range(40)])
    encoder=Encoder();key=CacheKey('CQ','W1','V0','adapter_identity','encoder_identity','REAL_TRAIN')
    store=DedupZstdStore(tmp);emb,pos,reused,manifest=store.ensure(key,encoder,x,ids)
    assert not reused and manifest['unique_rows']==7
    indices=np.array([39,0,13,13,21,5])
    expected=encoder.encode(x)[indices]
    assert np.array_equal(emb[indices],expected)
    assert np.array_equal(StackedFeatures([emb],[pos])[indices],expected)
    restored,stored,_=store.open(key,verify=True)
    assert np.array_equal(stored,ids) and np.array_equal(restored[indices],expected)
    _,_,reused,_=store.ensure(key,encoder,x,ids);assert reused
    bad=x.copy();bad[0,0,0]+=1
    try:store.ensure(key,encoder,bad,ids)
    except RuntimeError:pass
    else:raise AssertionError('Changed input accepted')
    path=store.path(key)/'frames.bin'
    with path.open('ab') as f:f.write(b'x')
    try:store.open(key,verify=True)
    except ValueError:pass
    else:raise AssertionError('Corrupted cache accepted')
print('MANTIS_ZSTD_STORE_SMOKE_PASS')
