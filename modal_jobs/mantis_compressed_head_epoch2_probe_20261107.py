"""Diagnostic additional head epoch, initialized from epoch-1 checkpoint.

Not an exact resume: optimizer and RNG state were not stored by the pilot.
Cache is decompressed into RAM, not disk; source cache remains unchanged.
"""
from pathlib import Path
import sys
import modal

ROOT=Path(__file__).resolve().parents[1]
PKG=ROOT/'docs/06112026/mantis_review/f3_mantis_v0.1.0_2026-11-06'
if (PKG/'f3_mantis').is_dir(): sys.path.insert(0,str(PKG))
image=(modal.Image.debian_slim(python_version='3.12')
       .pip_install('torch==2.5.1','numpy>=1.26','pandas>=2.2','pyarrow>=16','scikit-learn>=1.5','zstandard>=0.23')
       .add_local_python_source('f3_mantis',copy=True).add_local_python_source('model',copy=True))
app=modal.App('mantis-compressed-head-epoch2-probe-20261107')
volume=modal.Volume.from_name('tempo-data-v1',create_if_missing=False)

@app.function(image=image,gpu='L4',cpu=8,memory=98304,timeout=7200,volumes={'/data':volume})
def probe():
    import os,time,json,hashlib,datetime,resource
    os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
    import numpy as np
    import pandas as pd
    import torch
    import zstandard as zstd
    from model.data import fit_layout,_numeric
    from f3_mantis.determinism import configure_determinism
    from f3_mantis.probe import load_probe, evaluate_phases, _batches
    from f3_mantis.spec import MANTIS_V2_SPEC
    root=Path('/data/diagnostics/mantis_cache_zstd_v1/20261106T181738Z')
    summary=json.loads((root/'summary.json').read_text())
    if summary['status']!='SUCCESS': raise ValueError('Compressed cache is incomplete')
    source=Path(summary['source']); checkpoint=source.parent/'result/probe_head.pt'
    input_root=Path('/data/meta_release=imputation-v1/L1_runs/task=CQ/feature_regime=CQ_RAW_EARLY/window_id=W1/pipeline_id=V1/model_name=IMPUTATION_ONLY/seed=20260922/run_id=9ec054562bfc584aba867a5c6f13993e390ad4207d39db11c0ee132b255e5e44/attempt_id=0002/model_inputs')
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out=Path('/data/diagnostics/mantis_compressed_head_epoch2_probe_20261107')/stamp
    out.mkdir(parents=True,exist_ok=False)
    print(json.dumps({'event':'started','output':str(out),'note':'optimizer and RNG restarted; diagnostic only'}),flush=True)
    t0=time.monotonic(); decoder=zstd.ZstdDecompressor()
    def inflate(split):
        meta=json.loads((root/split/'manifest.json').read_text()); shape=tuple(meta['shape'])
        result=np.empty(shape,dtype=np.float16)
        for i,s in enumerate(meta['shards']):
            packed=(root/split/s['file']).read_bytes()
            if hashlib.sha256(packed).hexdigest()!=s['compressed_sha256']:raise ValueError('compressed hash mismatch')
            data=decoder.decompress(packed)
            if hashlib.sha256(data).hexdigest()!=s['source_sha256']:raise ValueError('decoded hash mismatch')
            result[s['start']:s['end']]=np.frombuffer(data,np.float16).reshape(s['end']-s['start'],4,4096)
            if (i+1)%100==0:print(json.dumps({'event':'inflate_progress','split':split,'rows':s['end'],'total':shape[0]}),flush=True)
        return result,meta
    tr,tm=inflate('REAL_TRAIN'); va,vm=inflate('VALIDATION')
    cache_load_s=time.monotonic()-t0
    print(json.dumps({'event':'cache_loaded','seconds':cache_load_s,'train_shape':tr.shape,'validation_shape':va.shape}),flush=True)
    train=pd.read_parquet(input_root/'train.parquet');validation=pd.read_parquet(input_root/'validation.parquet')
    def check_ids(frame,meta):
        original=Path(meta['source_file']).parent/'row_ids.npy'
        ids=np.load(original,allow_pickle=False)
        if not np.array_equal(frame.enrollment_id.astype(str).to_numpy(),ids.astype(str)):raise ValueError('Row IDs/order mismatch')
    check_ids(train,tm);check_ids(validation,vm)
    layout=fit_layout(train,task='CQ',phase_id='P4',use_masks=True)
    static_cols=list(layout.static_columns)+list(layout.mask_static_columns)
    ts=_numeric(train,static_cols);vs=_numeric(validation,static_cols)
    mapping={'warning':0,'average':1,'good':2}
    ty=train['CQ_label_final'].astype('string').map(mapping);vy=validation['CQ_label_final'].astype('string').map(mapping)
    if ty.isna().any() or vy.isna().any():raise ValueError('Invalid labels')
    ty=ty.to_numpy(dtype=np.int64);vy=vy.to_numpy(dtype=np.int64)
    del train,validation
    configure_determinism(42);model=load_probe(checkpoint,device='cuda');model.train()
    optim=torch.optim.AdamW(model.head.parameters(),lr=1e-3,weight_decay=1e-5)
    criterion=torch.nn.CrossEntropyLoss(); generator=torch.Generator().manual_seed(42)
    loss_sum=0.; rows=0;t1=time.monotonic();torch.cuda.reset_peak_memory_stats()
    for i,idx in enumerate(_batches(len(ty),2048,generator)):
        z=torch.from_numpy(np.asarray(tr[idx],dtype=np.float32)).to('cuda')
        s=torch.from_numpy(np.asarray(ts[idx],dtype=np.float32)).to('cuda')
        target=torch.from_numpy(ty[idx]).to('cuda');logits=model(z,s)
        loss=sum(criterion(logits[:,p],target) for p in range(4))/4
        optim.zero_grad(set_to_none=True);loss.backward();optim.step()
        rows+=len(idx);loss_sum+=float(loss.detach())*len(idx)
        if (i+1)%100==0:print(json.dumps({'event':'head_progress','batches':i+1,'rows':rows,'total':len(ty)}),flush=True)
    train_s=time.monotonic()-t1;t2=time.monotonic()
    val=evaluate_phases(model,va,vs,vy,3,device='cuda');val_s=time.monotonic()-t2
    result={'status':'SUCCESS','diagnostic':'additional_epoch_from_epoch1_weights_not_exact_resume',
       'optimizer_state':'REINITIALIZED','rng_state':'REINITIALIZED','checkpoint':str(checkpoint),
       'compressed_cache':str(root),'cache_load_seconds':cache_load_s,'train_seconds':train_s,'validation_seconds':val_s,
       'train_rows':rows,'validation_rows':len(vy),'train_loss':loss_sum/rows,'validation_metrics':val,
       'peak_cuda_allocated_bytes':torch.cuda.max_memory_allocated(),'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
       'cache_storage':'zstd shard on volume; decompressed into RAM','static_columns':static_cols}
    torch.save({'state_dict':model.state_dict(),'optimizer_state_dict':optim.state_dict(),'seed':42,'diagnostic':result['diagnostic']},out/'head_after_additional_epoch.pt')
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');volume.commit();print(json.dumps(result),flush=True)
    return result

@app.local_entrypoint()
def main(): print(probe.remote())
