"""Prepare separate V5 runs from the sharded diagnostic, preserving run identity."""
from pathlib import Path

source=Path('modal_jobs/moment_sharded_pilot_20261105.py').read_text(encoding='utf8')
old='9ec054562bfc584aba867a5c6f13993e390ad4207d39db11c0ee132b255e5e44'
runs={'W1':('04e7241f978790313ff54c38afcb665169aec5cb49603c6d655abc21658657da',1609276,175689),
      'W2':('49e320c6724c31ef8bbb1d73d2b4b4fac620d2db846abd3fc41252a829489366',1963060,180485),
      'W3':('fab7783b0adafb3edff612b92b573a9ff2e0627f07fffd058f76d47950533d38',2324027,180032)}
train_start=source.index('    generator=torch.Generator().manual_seed(42)')
train_end=source.index('    # The locked prefix input is loaded independently per phase.',train_start)
training='''    optimizer=torch.optim.AdamW(model.head.parameters(),lr=.001,weight_decay=1e-5)
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
'''
source=source[:train_start]+training+source[train_end:]
source=source.replace("'purpose':'ONE_EPOCH_CACHE_DIAGNOSTIC_NOT_PRIMARY'", "'purpose':'SHARDED_CACHE_MULTI_EPOCH_DIAGNOSTIC_NOT_PRIMARY'")
source=source.replace("'validation_metrics':metrics,'test_metrics':test_metrics", "'selected_validation_metrics':metrics,'selected_epoch':best_epoch,'test_metrics':test_metrics")
for window,(run,ntrain,nval) in runs.items():
    s=source.replace(old,run).replace('window_id=W1/pipeline_id=V1',f'window_id={window}/pipeline_id=V5')
    s=s.replace("len(frames['train'])!=1609276 or len(frames['validation'])!=175689",f"len(frames['train'])!={ntrain} or len(frames['validation'])!={nval}")
    s=s.replace('cq-moment-sharded-cache-pilot-20261105',f'cq-moment-v5-{window.lower()}-sharded-20261105')
    s=s.replace('cq_moment_sharded_cache_w1_v1_20261105',f'cq_moment_v5_{window.lower()}_sharded_20261105')
    s=s.replace('cq_moment_pilot_input_20261105',f'cq_moment_v5_{window.lower()}_test_20261105')
    Path(f'modal_jobs/moment_v5_{window.lower()}_sharded_20261105.py').write_text(s,encoding='utf8',newline='\n')
