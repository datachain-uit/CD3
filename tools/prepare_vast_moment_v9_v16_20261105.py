"""Create isolated sharded MOMENT runners for CQ V9 and V16."""
from pathlib import Path
import json

manifest=json.loads(Path('downloads/vastai/CQ_V2_2_clean_grain_seed42/download_manifest.json').read_text())
for version,parent in [('V9','V9'),('V16','V13')]:
    root=Path(f'upload_staging/vast_moment_{version.lower()}_20261105');root.mkdir(parents=True,exist_ok=True)
    for window in ('W1','W2','W3'):
        rows=[x for x in manifest['files'] if x['local_path'].replace('\\','/')==f"train/{window}/{version}/"+('train.parquet' if version=='V9' else 'balanced_train.parquet')]
        if len(rows)!=1:raise ValueError(f'Unexpected train provenance {version} {window}')
        import pyarrow.parquet as pq
        train_n=pq.ParquetFile(Path('downloads/vastai/CQ_V2_2_clean_grain_seed42')/rows[0]['local_path']).metadata.num_rows
        base=Path(f'upload_staging/vast_moment_v5_20261105/run_{window.lower()}.py').read_text(encoding='utf8')
        original={'W1':1609276,'W2':1963060,'W3':2324027}[window]
        base=base.replace(f"len(frames['train'])!={original}",f"len(frames['train'])!={train_n}")
        base=base.replace('moment_v5_20261105',f'moment_{version.lower()}_20261105')
        base=base.replace("identity={'input_sha256':hashes,",f"identity={{'pipeline':'{version}','parent_imputer':'{parent}','train_source':{rows[0]['remote_path']!r},'input_sha256':hashes,")
        anchor="    identity={'pipeline':"
        pos=base.index(anchor)
        preflight='''    # Reject lossy cache layouts before computing a full cache.
    sample_dynamic=torch.as_tensor(arrays['validation'][0][:8],device=device)
    sample_static=torch.as_tensor(arrays['validation'][1][:8],device=device)
    model.eval()
    with torch.no_grad(),torch.autocast(device_type='cuda',dtype=torch.bfloat16):
        direct=model(sample_dynamic,sample_static).float();sample_logits=[]
        for phase in range(1,5):
            embedding,stats=model._embedding(sample_dynamic[:,:phase])
            if not torch.isfinite(embedding).all() or torch.any(embedding.abs()>65504):raise ValueError('Embedding out of float16 range')
            cached_embedding=embedding.half().float()
            sample_logits.append(model.head(torch.cat((cached_embedding,stats,sample_static),dim=1)))
        restored=torch.stack(sample_logits,dim=1).float()
    if not torch.allclose(direct,restored,atol=1e-2,rtol=1e-2) or torch.any(direct.argmax(-1)!=restored.argmax(-1)):
        raise RuntimeError('Cache precision preflight failed')
    print(json.dumps({'event':'precision_preflight_passed','rows':8,'max_abs_logit_diff':float((direct-restored).abs().max())}),flush=True)
'''
        base=base[:pos]+preflight+base[pos:]
        (root/f'run_{window.lower()}.py').write_text(base,encoding='utf8',newline='\n')
