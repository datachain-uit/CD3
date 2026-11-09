"""One-epoch CQ MOMENT cache diagnostic; not a production experiment."""
import hashlib, json, os, time
from pathlib import Path
import modal

os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
app = modal.App('cq-moment-cache-bf16-pilot-20261105')
volume = modal.Volume.from_name('tempo-data-v1', create_if_missing=False)
image = (modal.Image.debian_slim(python_version='3.12').apt_install('git')
    .pip_install('numpy>=1.26', 'pandas>=2.2', 'pyarrow>=16', 'scikit-learn>=1.5',
                 'torch>=2.4', 'nvidia-ml-py>=12', 'huggingface_hub>=0.24', 'transformers>=4.54.1',
                 'git+https://github.com/moment-timeseries-foundation-model/moment.git@38f7310ad594100747ca2a8357e9c7ca7d323e0e')
    .add_local_python_source('model').add_local_python_source('release_core'))

@app.function(image=image, gpu='L4', cpu=8, memory=65536, timeout=86400, volumes={'/data':volume})
def run_one_epoch():
    import numpy as np
    import pandas as pd
    import torch
    from torch import nn
    from torch.utils.data import Dataset, DataLoader
    from model.data import fit_layout, transform_frame
    from model.architectures import prepare_moment_snapshot, SharedPhaseMomentClassifier
    from model.shared_phase import seed_everything
    from model.metrics import classification_metrics

    root = Path('/data/meta_release=imputation-v1/L1_runs/task=CQ/feature_regime=CQ_RAW_EARLY/window_id=W1/pipeline_id=V1/model_name=IMPUTATION_ONLY/seed=20260922/run_id=9ec054562bfc584aba867a5c6f13993e390ad4207d39db11c0ee132b255e5e44/attempt_id=0002')
    manifest = json.loads((root/'run_manifest.json').read_text())
    if manifest.get('run_status') != 'SUCCESS' or manifest.get('release_id') != 'CQ_V2_2':
        raise ValueError('Unexpected input release')
    source = {name:root/'model_inputs'/f'{name}.parquet' for name in ('train','validation')}
    def sha(path):
        with path.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
    hashes = {name:sha(path) for name,path in source.items()}
    frames = {name:pd.read_parquet(path) for name,path in source.items()}
    if len(frames['train'])!=1609276 or len(frames['validation'])!=175689:
        raise ValueError('Unexpected input row counts')
    classes=('warning','average','good')
    layout=fit_layout(frames['train'],task='CQ',phase_id='P4',use_masks=True)
    arrays={name:transform_frame(frame,layout,classes=classes,use_masks=True) for name,frame in frames.items()}
    del frames
    seed_everything(42)
    snapshot=prepare_moment_snapshot('moment_small',cache_dir='/data/model_cache/huggingface')
    device=torch.device('cuda')
    model=SharedPhaseMomentClassifier(arrays['train'][0].shape[2],arrays['train'][1].shape[1],len(classes),variant='moment_small',resolved_snapshot=snapshot['snapshot'],backbone_batch_rows=1024).to(device)
    identity={'input_sha256':hashes,'input_run_id':manifest.get('run_id'),'data_release_id':manifest.get('data_release_id'),
              'layout':layout.as_dict(),'backbone_revision':snapshot['resolved_revision'], 'precision':'BF16',
              'encoding':'phase_as_patch_v1_1','architecture':'moment_frozen_linear_probe_v2_1_phase_patch',
              'backbone_batch_rows':1024,'micro_batch_size':1024,'accumulation_steps':2}
    identity_hash=hashlib.sha256(json.dumps(identity,sort_keys=True,default=str).encode()).hexdigest()
    output=Path('/data/meta_release=imputation-v1/L3_meta/diagnostics/cq_moment_cache_w1_v1_20261105')
    cache=output/identity_hash
    if cache.exists(): raise RuntimeError('Cache exists; refusing to overwrite')
    cache.mkdir(parents=True)
    (cache/'identity.json').write_text(json.dumps(identity,indent=2,default=str))
    timings={}
    cached={}
    for name,(dynamic,static,_,labels) in arrays.items():
        start=time.perf_counter(); rows=len(labels)
        # Physical ordering follows the immutable parquet row order and the
        # sidecar stores its SHA; index travels with every shuffled item.
        width=int(model.backbone.config.d_model)+2*dynamic.shape[2]
        maps=[np.lib.format.open_memmap(cache/f'{name}_P{phase}.npy',mode='w+',dtype=np.float32,shape=(rows,width)) for phase in range(1,5)]
        model.eval()
        with torch.no_grad(),torch.autocast(device_type='cuda',dtype=torch.bfloat16):
            for i in range(0,rows,1024):
                dx=torch.as_tensor(dynamic[i:i+1024],device=device)
                for phase in range(1,5):
                    emb,stats=model._embedding(dx[:,:phase])
                    maps[phase-1][i:i+len(dx)]=torch.cat((emb,stats),dim=1).float().cpu().numpy()
                if i % (1024*100)==0: print(json.dumps({'event':'cache_progress','split':name,'rows':i,'total':rows}),flush=True)
        for m in maps: m.flush()
        timings[f'{name}_cache_seconds']=time.perf_counter()-start
        cached[name]=maps
        print(json.dumps({'event':'cache_complete','split':name,'seconds':timings[f'{name}_cache_seconds']}),flush=True)
    # Direct vs cached logits, same precision and head, all prefixes.
    dynamic,static,_,_=arrays['validation']; n=min(64,len(static))
    dx=torch.as_tensor(dynamic[:n],device=device); sx=torch.as_tensor(static[:n],device=device)
    with torch.no_grad(),torch.autocast(device_type='cuda',dtype=torch.bfloat16):
        direct=model(dx,sx).float()
        logits=torch.stack([model.head(torch.cat((torch.as_tensor(m[:n],device=device),sx),dim=1)) for m in cached['validation']],dim=1).float()
    delta=(direct-logits).abs(); maxdiff=float(delta.max().item())
    if not torch.allclose(direct,logits,atol=1e-3,rtol=1e-3): raise ValueError(f'Cached/direct logits mismatch {maxdiff}')
    print(json.dumps({'event':'cache_equivalence','rows':n,'max_abs_logit_diff':maxdiff}),flush=True)
    (cache/'CACHE_VERIFIED').write_text(json.dumps({'rows':n,'max_abs_logit_diff':maxdiff})+'\n')
    volume.commit()
    print(json.dumps({'event':'cache_committed','identity_sha256':identity_hash}),flush=True)
    class CacheDataset(Dataset):
        def __init__(self,name): self.name=name
        def __len__(self): return len(arrays[self.name][3])
        def __getitem__(self,i):
            return np.stack([m[i] for m in cached[self.name]]), arrays[self.name][1][i], int(arrays[self.name][3][i])
    generator=torch.Generator().manual_seed(42)
    loader=DataLoader(CacheDataset('train'),batch_size=1024,shuffle=True,num_workers=2,generator=generator)
    optimizer=torch.optim.AdamW(model.head.parameters(),lr=.001,weight_decay=1e-5)
    scaler=torch.amp.GradScaler('cuda'); criterion=nn.CrossEntropyLoss(); start=time.perf_counter()
    model.train(); optimizer.zero_grad(set_to_none=True); total=0; rows=0; group=0
    for step,(features,static,y) in enumerate(loader,1):
        features,static,y=features.to(device),static.to(device),y.to(device)
        with torch.autocast(device_type='cuda',dtype=torch.bfloat16):
            out=torch.stack([model.head(torch.cat((features[:,i],static),dim=1)) for i in range(4)],dim=1)
            loss=sum(criterion(out[:,i].float(),y) for i in range(4))/4
        scaler.scale(loss*len(y)).backward(); group+=len(y);total+=float(loss.detach())*len(y);rows+=len(y)
        if step%2==0 or step==len(loader):
            scaler.unscale_(optimizer)
            for p in model.head.parameters():
                if p.grad is not None:p.grad.div_(group)
            scaler.step(optimizer);scaler.update();optimizer.zero_grad(set_to_none=True);group=0
    timings['head_train_seconds']=time.perf_counter()-start
    model.eval(); start=time.perf_counter(); preds=[[] for _ in range(4)]; targets=[]
    with torch.no_grad(),torch.autocast(device_type='cuda',dtype=torch.bfloat16):
        for feats,stat,y in DataLoader(CacheDataset('validation'),batch_size=2048,num_workers=2):
            feats,stat=feats.to(device),stat.to(device)
            for i in range(4): preds[i].append(model.head(torch.cat((feats[:,i],stat),dim=1)).float().cpu())
            targets.append(y)
    truth=torch.cat(targets).numpy(); metrics={}
    for i in range(4):
        logits=torch.cat(preds[i]); probs=torch.softmax(logits,1).numpy()
        metrics[f'P{i+1}']=classification_metrics(truth,probs.argmax(1),probs,np.arange(3))[0]
    timings['cached_validation_seconds']=time.perf_counter()-start
    # The locked prefix input is loaded independently per phase. This pilot
    # reports test descriptively; test is never used for checkpoint selection.
    from model.shared_phase import evaluate_test_prefix
    test_metrics={}; started=time.perf_counter()
    for phase in ('P1','P2','P3','P4'):
        test_path=Path('/data/diagnostics/cq_moment_pilot_input_20261105')/f'test_{phase}.parquet'
        if not test_path.is_file(): raise FileNotFoundError(test_path)
        test_frame=pd.read_parquet(test_path)
        with torch.autocast(device_type='cuda',dtype=torch.bfloat16):
            test_metrics[phase],_=evaluate_test_prefix(model,test_frame,layout,classes,phase,batch_size=1024,workers=2,device=device)
        print(json.dumps({'event':'test_bf16_complete','phase':phase}),flush=True)
        del test_frame
    timings['test_bf16_seconds']=time.perf_counter()-started
    result={'status':'SUCCESS','purpose':'ONE_EPOCH_CACHE_DIAGNOSTIC_NOT_PRIMARY','identity_sha256':identity_hash,'identity':identity,
            'timings':timings,'cache_direct_max_abs_logit_diff':maxdiff,'validation_metrics':metrics,'test_metrics':test_metrics,
            'train_cross_entropy_mean_p1_p4':total/rows,'gpu':torch.cuda.get_device_name(0),
            'peak_gpu_allocated_bytes':torch.cuda.max_memory_allocated(),'cache_files':[str(cache/f'{name}_P{p}.npy') for name in arrays for p in range(1,5)]}
    torch.save({'head_state_dict':model.head.state_dict(),'identity':identity},cache/'head_checkpoint.pt')
    (cache/'summary.json').write_text(json.dumps(result,indent=2,default=str)+'\n')
    (cache/'COMPLETE').write_text('verified\n');volume.commit()
    print(json.dumps({'event':'pilot_complete',**result},default=str),flush=True)
    return result

@app.local_entrypoint()
def main(): print(json.dumps(run_one_epoch.remote(),indent=2,default=str))
