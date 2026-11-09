"""Build an isolated resumable, sharded MOMENT diagnostic from the pilot."""
from pathlib import Path

source=Path('modal_jobs/moment_cached_pilot_20261105.py').read_text(encoding='utf8')
source=source.replace("cq-moment-cache-bf16-pilot-20261105", "cq-moment-sharded-cache-pilot-20261105")
source=source.replace("'backbone_batch_rows':1024,'micro_batch_size':1024,'accumulation_steps':2}", "'backbone_batch_rows':1024,'micro_batch_size':1024,'accumulation_steps':2,'storage':'sharded_npz_float16_embedding_float32_stats_v1','shard_rows':16384,'torch_version':torch.__version__}")
source=source.replace("cq_moment_cache_w1_v1_20261105", "cq_moment_sharded_cache_w1_v1_20261105")
start=source.index("    if cache.exists(): raise RuntimeError('Cache exists; refusing to overwrite')")
end=source.index('    generator=torch.Generator().manual_seed(42)',start)
source=source[:start]+'''    cache.mkdir(parents=True,exist_ok=True)
    identity_path=cache/'identity.json'
    if identity_path.exists() and json.loads(identity_path.read_text()) != json.loads(json.dumps(identity,default=str)):
        raise RuntimeError('Cache identity mismatch')
    identity_path.write_text(json.dumps(identity,indent=2,default=str))
    volume.commit()
    timings={}; shard_rows=16384; cached={}
    for name,(dynamic,static,_,labels) in arrays.items():
        start=time.perf_counter(); rows=len(labels); cached[name]=[]
        for offset in range(0,rows,shard_rows):
            end=min(offset+shard_rows,rows); path=cache/f'{name}_{offset:09d}.npz'; marker=cache/f'{name}_{offset:09d}.json'
            if marker.exists():
                record=json.loads(marker.read_text())
                if not path.is_file() or sha(path)!=record['sha256'] or record['rows']!=end-offset:
                    raise RuntimeError(f'Cache shard verification failed: {path}')
                cached[name].append(path);continue
            chunks=[[] for _ in range(4)]; statistics=[[] for _ in range(4)]
            model.eval()
            with torch.no_grad(),torch.autocast(device_type='cuda',dtype=torch.bfloat16):
                for i in range(offset,end,1024):
                    dx=torch.as_tensor(dynamic[i:min(i+1024,end)],device=device)
                    for phase in range(1,5):
                        emb,stats=model._embedding(dx[:,:phase])
                        if not torch.isfinite(emb).all() or torch.any(emb.abs()>65504):
                            raise ValueError('Embedding outside finite float16 range')
                        chunks[phase-1].append(emb.half().cpu().numpy())
                        statistics[phase-1].append(stats.float().cpu().numpy())
            content={}
            for phase in range(4):
                content[f'emb_P{phase+1}']=np.concatenate(chunks[phase])
                content[f'stats_P{phase+1}']=np.concatenate(statistics[phase])
            temporary=cache/f'{name}_{offset:09d}.tmp.npz'
            np.savez_compressed(temporary,**content)
            os.replace(temporary,path)
            marker.write_text(json.dumps({'start':offset,'rows':end-offset,'sha256':sha(path),'bytes':path.stat().st_size}))
            volume.commit();cached[name].append(path)
            print(json.dumps({'event':'shard_committed','split':name,'rows_done':end,'total':rows,'bytes':path.stat().st_size}),flush=True)
        timings[f'{name}_cache_seconds_this_attempt']=time.perf_counter()-start
    def read_shard(path):
        with np.load(path,allow_pickle=False) as data:
            return np.stack([np.concatenate((data[f'emb_P{i}'].astype(np.float32),data[f'stats_P{i}']),axis=1) for i in range(1,5)],axis=1)
    # Check the saved precision against direct BF16 for the same prefixes.
    dynamic,static,_,_=arrays['validation']; n=min(64,len(static))
    dx=torch.as_tensor(dynamic[:n],device=device); sx=torch.as_tensor(static[:n],device=device)
    model.eval()
    with torch.no_grad(),torch.autocast(device_type='cuda',dtype=torch.bfloat16):
        direct=model(dx,sx).float(); features=torch.as_tensor(read_shard(cached['validation'][0])[:n],device=device)
        logits=torch.stack([model.head(torch.cat((features[:,i],sx),dim=1)) for i in range(4)],dim=1).float()
    delta=(direct-logits).abs(); maxdiff=float(delta.max().item()); disagreements=int((direct.argmax(-1)!=logits.argmax(-1)).sum().item())
    if not torch.allclose(direct,logits,atol=1e-2,rtol=1e-2) or disagreements: raise ValueError(f'Cache precision mismatch max={maxdiff} disagreements={disagreements}')
    (cache/'CACHE_VERIFIED').write_text(json.dumps({'rows':n,'max_abs_logit_diff':maxdiff,'prediction_disagreements':disagreements})+'\\n');volume.commit()
    print(json.dumps({'event':'cache_verified','rows':n,'max_abs_logit_diff':maxdiff,'prediction_disagreements':disagreements}),flush=True)
    class CacheDataset(Dataset):
        def __init__(self,name): self.name=name;self.last=-1;self.values=None
        def __len__(self): return len(arrays[self.name][3])
        def __getitem__(self,i):
            shard=i//shard_rows
            if shard!=self.last: self.values=read_shard(cached[self.name][shard]);self.last=shard
            return self.values[i%shard_rows], arrays[self.name][1][i], int(arrays[self.name][3][i])
''' + source[end:]
# Compressed shards are expensive with per-row random access. Shuffle shards,
# then rows within each shard; use batch size 1024 and preserve accumulation.
source=source.replace("loader=DataLoader(CacheDataset('train'),batch_size=1024,shuffle=True,num_workers=2,generator=generator)", """order=torch.randperm(len(cached['train']),generator=generator).tolist()
    indices=[]
    for shard in order:
        count=min(shard_rows,len(arrays['train'][3])-shard*shard_rows)
        indices.extend((torch.randperm(count,generator=generator)+shard*shard_rows).tolist())
    loader=DataLoader(CacheDataset('train'),batch_size=1024,sampler=indices,num_workers=0)""")
source=source.replace("DataLoader(CacheDataset('validation'),batch_size=2048,num_workers=2)","DataLoader(CacheDataset('validation'),batch_size=2048,num_workers=0)")
source=source.replace("'cache_files':[str(cache/f'{name}_P{p}.npy') for name in arrays for p in range(1,5)]", "'cache_files':[str(path) for paths in cached.values() for path in paths], 'shuffle_policy':'SHARD_THEN_ROWS_DIAGNOSTIC'")
Path('modal_jobs/moment_sharded_pilot_20261105.py').write_text(source,encoding='utf8',newline='\n')
