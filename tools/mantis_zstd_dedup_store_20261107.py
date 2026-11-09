"""Experimental byte-exact compressed Mantis store; separate from registered store.

Each distinct (P1..P4, embedding) float16 row is zstd-compressed once. A fixed
index maps every original row to its frame; random indexing preserves requested
batch order. Written last, manifest.json marks a complete cache entry.
"""
from collections import OrderedDict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import numpy as np
import zstandard as zstd
from f3_mantis.store import EmbeddingStore, input_sha256


class ZstdRows:
    def __init__(self, leaf, manifest, max_cached_rows=8192):
        self.leaf=Path(leaf);self.manifest=manifest
        self.shape=(manifest['rows'],4,manifest['embedding_dim']);self.dtype=np.dtype('float16')
        self.index=np.load(self.leaf/'index.npy',mmap_mode='r')
        if self.index.shape != (self.shape[0],2):raise ValueError('Cache index shape mismatch')
        self.handle=(self.leaf/'frames.bin').open('rb');self.decoder=zstd.ZstdDecompressor()
        self.cache=OrderedDict();self.max_cached_rows=max_cached_rows
    def __len__(self):return self.shape[0]
    def __getitem__(self, indices):
        idx=np.asarray(indices,dtype=np.int64)
        if idx.ndim!=1 or np.any(idx<0) or np.any(idx>=len(self)):raise IndexError('Invalid row indices')
        out=np.empty((len(idx),4,self.shape[2]),dtype=np.float16)
        references=self.index[idx]
        for offset in np.unique(references[:,0]):
            mask=references[:,0]==offset; lengths=references[mask,1]
            if not np.all(lengths==lengths[0]):raise ValueError('Inconsistent frame length')
            key=(int(offset),int(lengths[0]));value=self.cache.pop(key,None)
            if value is None:
                self.handle.seek(key[0]);packed=self.handle.read(key[1])
                if len(packed)!=key[1]:raise IOError('Truncated compressed frame')
                raw=self.decoder.decompress(packed)
                value=np.frombuffer(raw,dtype=np.float16).reshape(4,self.shape[2])
            self.cache[key]=value
            if len(self.cache)>self.max_cached_rows:self.cache.popitem(last=False)
            out[mask]=value
        return out


class DedupZstdStore(EmbeddingStore):
    def write(self,key,encoder,dynamic,row_ids,backbone_pin=None,extra=None,overwrite=False,input_digest=None):
        leaf=self.path(key)
        if leaf.exists():raise FileExistsError(f'Refusing to overwrite partial or complete cache: {leaf}')
        if key.adapter_digest!=encoder.adapter.digest() or key.encoder_digest!=encoder.fingerprint_digest:raise ValueError('Encoder identity mismatch')
        ids=np.asarray(row_ids)
        if len(ids)!=len(dynamic) or len(np.unique(ids.astype(str)))!=len(ids):raise ValueError('Invalid row IDs')
        leaf.mkdir(parents=True,exist_ok=False)
        index=np.lib.format.open_memmap(leaf/'index.npy.partial',mode='w+',dtype=np.uint64,shape=(len(ids),2))
        compressor=zstd.ZstdCompressor(level=3);decoder=zstd.ZstdDecompressor();dedup={};bytes_written=0
        with (leaf/'frames.bin.partial').open('wb') as out:
            for start in range(0,len(ids),2048):
                end=min(start+2048,len(ids));encoded=encoder.encode(dynamic[start:end])
                if encoded.shape!=(end-start,4,encoder.embedding_dim) or encoded.dtype!=np.float16:raise ValueError('Unexpected encoder output')
                for j,row in enumerate(encoded):
                    raw=np.ascontiguousarray(row).tobytes();digest=hashlib.sha256(raw).digest();ref=dedup.get(digest)
                    if ref is None:
                        packed=compressor.compress(raw)
                        if decoder.decompress(packed)!=raw:raise ValueError('Lossless frame round-trip failed')
                        ref=(bytes_written,len(packed));out.write(packed)
                        bytes_written+=len(packed);dedup[digest]=ref
                    index[start+j]=ref
                out.flush();index.flush()
                if shutil.disk_usage(leaf).free<3*1024**3:raise RuntimeError('Less than 3 GiB free; retained partial cache')
                print(json.dumps({'event':'compressed_cache_progress','split':key.split,'rows':end,'total':len(ids),'unique_rows':len(dedup),'compressed_bytes':bytes_written}),flush=True)
        del index
        os.replace(leaf/'index.npy.partial',leaf/'index.npy');os.replace(leaf/'frames.bin.partial',leaf/'frames.bin')
        np.save(leaf/'row_ids.npy',ids.astype(str) if ids.dtype.kind in 'OU' else ids)
        def sha_file(path):
            h=hashlib.sha256()
            with path.open('rb') as f:
                for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
            return h.hexdigest()
        manifest={'key':key.__dict__,'rows':len(ids),'prefixes':[1,2,3,4],'embedding_dim':encoder.embedding_dim,
                  'dtype':'float16','format':'deduplicated_zstd_rows_v1','input_sha256':input_digest or input_sha256(dynamic,ids),
                  'adapter_digest':encoder.adapter.digest(),'encoder_digest':encoder.fingerprint_digest,
                  'encoder_fingerprint':encoder.fingerprint(),'backbone_pin':backbone_pin or {},'unique_rows':len(dedup),
                  'frames_sha256':sha_file(leaf/'frames.bin'),'index_sha256':sha_file(leaf/'index.npy'),
                  'row_ids_sha256':sha_file(leaf/'row_ids.npy'),'timing':{'note':'timing recorded per cache progress'},
                  'created_at_utc':datetime.now(timezone.utc).isoformat()}
        (leaf/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
        return manifest
    def open(self,key,verify=True):
        leaf=self.path(key);manifest=json.loads((leaf/'manifest.json').read_text(encoding='utf-8'))
        if manifest.get('format')!='deduplicated_zstd_rows_v1':raise ValueError('Unexpected cache format')
        if verify:
            for filename,field in [('frames.bin','frames_sha256'),('index.npy','index_sha256'),('row_ids.npy','row_ids_sha256')]:
                h=hashlib.sha256()
                with (leaf/filename).open('rb') as f:
                    for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
                if h.hexdigest()!=manifest[field]:raise ValueError(f'Hash mismatch: {filename}')
        return ZstdRows(leaf,manifest),np.load(leaf/'row_ids.npy',allow_pickle=False),manifest
