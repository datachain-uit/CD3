"""Exploratory CQ V0 MantisV2 with verified deduplicated lossless embedding cache."""
import argparse,hashlib,json,os,resource,subprocess,sys,time
from pathlib import Path
import numpy as np
import pandas as pd
import torch
from sklearn.metrics import accuracy_score,balanced_accuracy_score,f1_score
from model.data import fit_layout,transform_frame
from model.energy import GpuPowerSampler
from f3_mantis.determinism import configure_determinism
from f3_mantis.encoder import load_frozen_mantis
from f3_mantis.spec import MANTIS_V2_SPEC
import f3_mantis.cell as cell
from mantis_zstd_dedup_store_20261107 import DedupZstdStore

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--window',choices=['W1','W2','W3'],required=True);p.add_argument('--smoke-rows',type=int,default=0);a=p.parse_args()
    root=Path('/workspace/CD3/data/CQ_V2_2_clean_grain_seed42'); base=Path('/workspace/CD3/mantis_v0_20261107')
    output=base/('smoke' if a.smoke_rows else 'runs')/a.window/'V0';output.mkdir(parents=True,exist_ok=False)
    release=json.loads((root/'download_manifest.json').read_text())
    if release.get('release_id')!='CQ_V2_2' or release.get('data_release_id')!='sha256:8db2b1d375c9cb7cd91cbccb7907fca51a8ab9bcd748c7bde43e879b1237d045':raise ValueError('Unexpected release identity')
    paths={'train':root/'train'/a.window/'V0/train.parquet','validation':root/'evaluation'/a.window/'V0/validation.parquet','test':root/'evaluation'/a.window/'V0/test_P4.parquet'}
    hashes={k:sha(v) for k,v in paths.items()};frames={k:pd.read_parquet(v) for k,v in paths.items()}
    if a.smoke_rows:frames={k:v.head(a.smoke_rows).copy() for k,v in frames.items()}
    for k,f in frames.items():
        if f.enrollment_id.isna().any() or f.enrollment_id.duplicated().any():raise ValueError(f'{k} grain invalid')
    layout=fit_layout(frames['train'],task='CQ',phase_id='P4',use_masks=True)
    names=list(layout.dynamic_bases)+[f'missing__{x}' for x in layout.dynamic_bases if f'missing__{x}_P1' in frames['train'].columns]+list(layout.mask_phase_bases)+['phase_fraction','delta_t']
    def prep(frame):
        x,s,_,y=transform_frame(frame,layout,classes=('warning','average','good'),use_masks=True)
        if x.shape[-1]!=len(names):raise ValueError('Channel layout mismatch')
        return {'dynamic':x,'static':s,'y':y,'row_ids':frame.enrollment_id.astype(str).to_numpy(),'channel_names':names}
    data={k:prep(v) for k,v in frames.items()}
    pin=base/'backbone_pin.json'
    if not pin.exists():subprocess.run([sys.executable,'-m','f3_mantis.cli','pin','--out',str(pin)],check=True)
    pin_data=json.loads(pin.read_text());configure_determinism(42)
    backbone=load_frozen_mantis(device='cuda',snapshot_dir=pin_data['snapshot_dir'])
    cell.EmbeddingStore=DedupZstdStore
    original=cell.train_probe
    def logged(*args,**kwargs):
        kwargs['log']=lambda r:print(json.dumps({'event':'epoch_complete','window':a.window,**r}),flush=True)
        return original(*args,**kwargs)
    cell.train_probe=logged
    spec=json.loads(json.dumps(MANTIS_V2_SPEC))
    if a.smoke_rows:spec['training']['max_epochs']=1;spec['training']['early_stopping_patience']=1
    started=time.monotonic();torch.cuda.reset_peak_memory_stats();energy=GpuPowerSampler(interval_seconds=1.0).start()
    print(json.dumps({'event':'cell_started','window':a.window,'rows':{k:len(v['y']) for k,v in data.items()},'smoke':bool(a.smoke_rows)}),flush=True)
    result=cell.run_cell(task='CQ',window=a.window,pipeline='V0',imputer='V0',seed=42,num_classes=3,train=data['train'],validation=data['validation'],test=data['test'],backbone=backbone,store_root=str(output/'cache'),out_dir=str(output/'result'),device='cuda',backbone_pin=pin_data,spec=spec,microbatch_sequences=4096,precision='bf16')
    metrics=[]
    for split in ('validation','test'):
        probabilities=result[split+'_probabilities'];y=data[split]['y']
        for i in range(4):
            pred=probabilities[:,i].argmax(axis=1)
            metrics.append({'split':split.upper(),'phase':f'P{i+1}','rows':len(y),'accuracy':accuracy_score(y,pred),'balanced_accuracy':balanced_accuracy_score(y,pred),'macro_f1':f1_score(y,pred,labels=[0,1,2],average='macro',zero_division=0)})
    metadata={'task':'CQ','window':a.window,'pipeline':'V0','seed':42,'release_id':release['release_id'],'data_release_id':release['data_release_id'],'input_sha256':hashes,'cache_format':'deduplicated_zstd_rows_v1','run_purpose':'EXPLORATORY_CACHE_VALIDATION','epochs_trained':result['record']['epochs_trained'],'elapsed_seconds':time.monotonic()-started,'peak_cuda_allocated_bytes':torch.cuda.max_memory_allocated(),'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'gpu_energy':energy.stop(),'metrics':metrics}
    (output/'result'/'diagnostic_metrics.json').write_text(json.dumps(metadata,indent=2)+'\n')
    (output/'COMPLETE').write_text('complete\n')
    print(json.dumps({'event':'cell_complete',**metadata}),flush=True)
if __name__=='__main__':main()
