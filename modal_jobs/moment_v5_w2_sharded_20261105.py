"""One-epoch CQ MOMENT cache diagnostic; not a production experiment."""
import hashlib, json, os, time
from pathlib import Path
import modal

os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
app = modal.App('cq-moment-v5-w2-sharded-20261105')
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

    root = Path('/data/meta_release=imputation-v1/L1_runs/task=CQ/feature_regime=CQ_RAW_EARLY/window_id=W2/pipeline_id=V5/model_name=IMPUTATION_ONLY/seed=20260922/run_id=49e320c6724c31ef8bbb1d73d2b4b4fac620d2db846abd3fc41252a829489366/attempt_id=0002')
    manifest = json.loads((root/'run_manifest.json').read_text())
    if manifest.get('run_status') != 'SUCCESS' or manifest.get('release_id') != 'CQ_V2_2':
        raise ValueError('Unexpected input release')
    source = {name:root/'model_inputs'/f'{name}.parquet' for name in ('train','validation')}
    def sha(path):
        with path.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
    hashes = {name:sha(path) for name,path in source.items()}
    frames = {name:pd.read_parquet(path) for name,path in source.items()}
    if len(frames['train'])!=1963060 or len(frames['validation'])!=180485:
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
              'backbone_batch_rows':1024,'micro_batch_size':1024,'accumulation_steps':2,'storage':'sharded_npz_float16_embedding_float32_stats_v1','shard_rows':16384,'torch_version':torch.__version__}
    identity_hash=hashlib.sha256(json.dumps(identity,sort_keys=True,default=str).encode()).hexdigest()
    output=Path('/data/meta_release=imputation-v1/L3_meta/diagnostics/cq_moment_v5_w2_sharded_20261105')
    cache=output/identity_hash
    cache.mkdir(parents=True,exist_ok=True)
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
    (cache/'CACHE_VERIFIED').write_text(json.dumps({'rows':n,'max_abs_logit_diff':maxdiff,'prediction_disagreements':disagreements})+'\n');volume.commit()
    print(json.dumps({'event':'cache_verified','rows':n,'max_abs_logit_diff':maxdiff,'prediction_disagreements':disagreements}),flush=True)
    class CacheDataset(Dataset):
        def __init__(self,name): self.name=name;self.last=-1;self.values=None
        def __len__(self): return len(arrays[self.name][3])
        def __getitem__(self,i):
            shard=i//shard_rows
            if shard!=self.last: self.values=read_shard(cached[self.name][shard]);self.last=shard
            return self.values[i%shard_rows], arrays[self.name][1][i], int(arrays[self.name][3][i])
    optimizer=torch.optim.AdamW(model.head.parameters(),lr=.001,weight_decay=1e-5)
    scaler=torch.amp.GradScaler('cuda'); criterion=nn.CrossEntropyLoss()
    checkpoint=cache/'head_resume.pt'; history=[]; best_state=None; best_score=-float('inf'); best_epoch=0; stale=0; first_epoch=1
    if checkpoint.exists():
        saved=torch.load(checkpoint,map_location='cpu',weights_only=False)
        if saved['identity_sha256']!=identity_hash: raise ValueError('Head checkpoint identity mismatch')
        model.head.load_state_dict(saved['head']);optimizer.load_state_dict(saved['optimizer']);scaler.load_state_dict(saved['scaler'])
        history=saved['history']; best_state=saved['best_state']; best_score=saved['best_score'];best_epoch=saved['best_epoch'];stale=saved['stale'];first_epoch=saved['epoch']+1
        torch.set_rng_state(saved['cpu_rng']);torch.cuda.set_rng_state_all(saved['cuda_rng'])
        print(json.dumps({'event':'head_resume','next_epoch':first_epoch}),flush=True)
    for epoch in range(first_epoch,51):
        generator=torch.Generator().manual_seed(42+epoch)
        order=torch.randperm(len(cached['train']),generator=generator).tolist();indices=[]
        for shard in order:
            count=min(shard_rows,len(arrays['train'][3])-shard*shard_rows)
            indices.extend((torch.randperm(count,generator=generator)+shard*shard_rows).tolist())
        loader=DataLoader(CacheDataset('train'),batch_size=1024,sampler=indices,num_workers=0)
        start=time.perf_counter();model.train();optimizer.zero_grad(set_to_none=True);total=0;rows=0;group=0
        for step,(features,static,y) in enumerate(loader,1):
            features,static,y=features.to(device),static.to(device),y.to(device)
            with torch.autocast(device_type='cuda',dtype=torch.bfloat16):
                out=torch.stack([model.head(torch.cat((features[:,i],static),dim=1)) for i in range(4)],dim=1)
                loss=sum(criterion(out[:,i].float(),y) for i in range(4))/4
            scaler.scale(loss*len(y)).backward();group+=len(y);total+=float(loss.detach())*len(y);rows+=len(y)
            if step%2==0 or step==len(loader):
                scaler.unscale_(optimizer)
                for p in model.head.parameters():
                    if p.grad is not None:p.grad.div_(group)
                scaler.step(optimizer);scaler.update();optimizer.zero_grad(set_to_none=True);group=0
        train_seconds=time.perf_counter()-start;model.eval(); start=time.perf_counter();preds=[[] for _ in range(4)];targets=[];losses=[]
        with torch.no_grad(),torch.autocast(device_type='cuda',dtype=torch.bfloat16):
            for feats,stat,y in DataLoader(CacheDataset('validation'),batch_size=2048,num_workers=0):
                feats,stat=feats.to(device),stat.to(device)
                for i in range(4):preds[i].append(model.head(torch.cat((feats[:,i],stat),dim=1)).float().cpu())
                targets.append(y)
        truth=torch.cat(targets).numpy();metrics={}
        for i in range(4):
            logits=torch.cat(preds[i]);probs=torch.softmax(logits,1).numpy()
            metrics[f'P{i+1}']=classification_metrics(truth,probs.argmax(1),probs,np.arange(3))[0]
            losses.append(float(criterion(logits,torch.from_numpy(truth))))
        score=float(np.mean([metrics[f'P{i}']['f1_macro'] for i in range(1,5)]));ce=float(np.mean(losses))
        previous=(best_score,-history[best_epoch-1]['validation_cross_entropy']) if best_epoch else (-float('inf'),-float('inf'))
        if (score,-ce)>previous:
            best_state={k:v.detach().cpu().clone() for k,v in model.head.state_dict().items()};best_score=score;best_epoch=epoch;stale=0
        else:stale+=1
        history.append({'epoch':epoch,'train_seconds':train_seconds,'validation_seconds':time.perf_counter()-start,'train_loss':total/rows,'validation_macro_f1':score,'validation_cross_entropy':ce})
        state={'identity_sha256':identity_hash,'epoch':epoch,'head':model.head.state_dict(),'optimizer':optimizer.state_dict(),'scaler':scaler.state_dict(),'history':history,'best_state':best_state,'best_score':best_score,'best_epoch':best_epoch,'stale':stale,'cpu_rng':torch.get_rng_state(),'cuda_rng':torch.cuda.get_rng_state_all()}
        temporary=cache/'head_resume.tmp';torch.save(state,temporary);os.replace(temporary,checkpoint);volume.commit()
        print(json.dumps({'event':'epoch_complete',**history[-1],'best_epoch':best_epoch,'stale':stale}),flush=True)
    model.head.load_state_dict(best_state);model.eval();total=history[-1]['train_loss'];rows=1
    # Recompute validation once with the selected head, including after resume.
    preds=[[] for _ in range(4)];targets=[]
    with torch.no_grad(),torch.autocast(device_type='cuda',dtype=torch.bfloat16):
        for feats,stat,y in DataLoader(CacheDataset('validation'),batch_size=2048,num_workers=0):
            feats,stat=feats.to(device),stat.to(device)
            for i in range(4):preds[i].append(model.head(torch.cat((feats[:,i],stat),dim=1)).float().cpu())
            targets.append(y)
    truth=torch.cat(targets).numpy();metrics={}
    for i in range(4):
        logits=torch.cat(preds[i]);probs=torch.softmax(logits,1).numpy()
        metrics[f'P{i+1}']=classification_metrics(truth,probs.argmax(1),probs,np.arange(3))[0]
    timings['head_history']=history; timings['best_epoch']=best_epoch
    # The locked prefix input is loaded independently per phase. This pilot
    # reports test descriptively; test is never used for checkpoint selection.
    from model.shared_phase import evaluate_test_prefix
    test_metrics={}; started=time.perf_counter()
    for phase in ('P1','P2','P3','P4'):
        test_path=Path('/data/diagnostics/cq_moment_v5_w2_test_20261105')/f'test_{phase}.parquet'
        if not test_path.is_file(): raise FileNotFoundError(test_path)
        test_frame=pd.read_parquet(test_path)
        with torch.autocast(device_type='cuda',dtype=torch.bfloat16):
            test_metrics[phase],_=evaluate_test_prefix(model,test_frame,layout,classes,phase,batch_size=1024,workers=2,device=device)
        print(json.dumps({'event':'test_bf16_complete','phase':phase}),flush=True)
        del test_frame
    timings['test_bf16_seconds']=time.perf_counter()-started
    result={'status':'SUCCESS','purpose':'SHARDED_CACHE_MULTI_EPOCH_DIAGNOSTIC_NOT_PRIMARY','identity_sha256':identity_hash,'identity':identity,
            'timings':timings,'cache_direct_max_abs_logit_diff':maxdiff,'selected_validation_metrics':metrics,'selected_epoch':best_epoch,'test_metrics':test_metrics,
            'train_cross_entropy_mean_p1_p4':total/rows,'gpu':torch.cuda.get_device_name(0),
            'peak_gpu_allocated_bytes':torch.cuda.max_memory_allocated(),'cache_files':[str(path) for paths in cached.values() for path in paths], 'shuffle_policy':'SHARD_THEN_ROWS_DIAGNOSTIC'}
    torch.save({'head_state_dict':model.head.state_dict(),'identity':identity},cache/'head_checkpoint.pt')
    (cache/'summary.json').write_text(json.dumps(result,indent=2,default=str)+'\n')
    (cache/'COMPLETE').write_text('verified\n');volume.commit()
    print(json.dumps({'event':'pilot_complete',**result},default=str),flush=True)
    return result

@app.local_entrypoint()
def main(): print(json.dumps(run_one_epoch.remote(),indent=2,default=str))
