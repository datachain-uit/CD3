"""Isolated CQ/W1/V1 MOMENT Small one-epoch pilot; not a primary run."""
import os
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
import json
import time
from pathlib import Path
import modal

app=modal.App('cq-moment-one-epoch-micro1024-20261104')
volume=modal.Volume.from_name('tempo-data-v1',create_if_missing=False)
image=(modal.Image.debian_slim(python_version='3.12').apt_install('git')
       .pip_install('numpy>=1.26','pandas>=2.2','pyarrow>=16','scikit-learn>=1.5',
                    'torch>=2.4','nvidia-ml-py>=12','huggingface_hub>=0.24','transformers>=4.54.1',
                    'git+https://github.com/moment-timeseries-foundation-model/moment.git@38f7310ad594100747ca2a8357e9c7ca7d323e0e')
       .add_local_python_source('model').add_local_python_source('release_core'))

@app.function(image=image,gpu='L4',cpu=8,memory=65536,timeout=86400,volumes={'/data':volume})
def run_one_epoch():
    import pandas as pd
    import torch
    from model.data import fit_layout
    from model.architectures import prepare_moment_snapshot, SharedPhaseMomentClassifier
    original_init=SharedPhaseMomentClassifier.__init__
    def init_micro1024(self, *args, **kwargs):
        kwargs["backbone_batch_rows"]=1024
        original_init(self, *args, **kwargs)
    SharedPhaseMomentClassifier.__init__=init_micro1024
    from model.shared_phase import train_shared_checkpoint
    from release_core import resolve_release

    base=Path('/data/meta_release=imputation-v1/L1_runs/task=CQ/feature_regime=CQ_RAW_EARLY/window_id=W1/pipeline_id=V1/model_name=IMPUTATION_ONLY/seed=20260922')
    spec=resolve_release('CQ','CQ_V2_2')
    candidates=[]
    for p in base.glob('run_id=*/attempt_id=*/run_manifest.json'):
        m=json.loads(p.read_text(encoding='utf8'))
        if (m.get('run_status')=='SUCCESS' and m.get('release_id')==spec['release_id']
            and m.get('split_registry_id')==spec['split_registry_id']
            and m.get('split_version')==spec['split_version'] and m.get('phase_version')==spec['phase_version']
            and (p.parent/'model_inputs/train.parquet').is_file()
            and (p.parent/'model_inputs/validation.parquet').is_file()):
            candidates.append((p.stat().st_mtime,p,m))
    if not candidates: raise RuntimeError('No successful locked CQ W1 V1 imputation input')
    _,manifest_path,manifest=max(candidates,key=lambda x:x[0])
    train=pd.read_parquet(manifest_path.parent/'model_inputs/train.parquet')
    validation=pd.read_parquet(manifest_path.parent/'model_inputs/validation.parquet')
    if len(train)!=1609276 or len(validation)!=175689: raise ValueError('Unexpected CQ W1 V1 row counts')
    layout=fit_layout(train,task='CQ',phase_id='P4',use_masks=True)
    cache='/data/model_cache/huggingface'
    t0=time.perf_counter();snapshot=prepare_moment_snapshot('moment_small',cache_dir=cache)
    download_seconds=time.perf_counter()-t0
    print(json.dumps({'event':'pilot_started','train_rows':len(train),'validation_rows':len(validation),
      'gpu':torch.cuda.get_device_name(0),'batch_size':2048,'accumulation_steps':2,
      'micro_batch_size':1024,'asset_prepare_seconds':download_seconds}),flush=True)
    torch.cuda.reset_peak_memory_stats();t0=time.perf_counter()
    trained,_=train_shared_checkpoint(layout=layout,classes=('warning','average','good'),train_frame=train,
      validation_frame=validation,architecture='moment_small',seed=42,batch_size=2048,accumulation_steps=2,
      max_epochs=1,patience=1,workers=2,moment_cache_dir=cache,moment_snapshot=snapshot['snapshot'])
    elapsed=time.perf_counter()-t0
    out=Path('/data/meta_release=imputation-v1/L3_meta/diagnostics/cq_moment_w1_v1_one_epoch_micro1024_20261104')
    out.mkdir(parents=True,exist_ok=True)
    result={'status':'SUCCESS','purpose':'ONE_EPOCH_TIMING_PILOT_NOT_PRIMARY','task':'CQ','window':'W1',
      'pipeline':'V1','model':'MOMENT_SMALL','seed':42,'batch_size':2048,'micro_batch_size':1024,
      'accumulation_steps':2,'train_rows':len(train),'validation_rows':len(validation),'elapsed_seconds':elapsed,
      'history':trained['history'],'peak_gpu_allocated_bytes':torch.cuda.max_memory_allocated(),
      'backbone_batch_rows':1024,'gpu':torch.cuda.get_device_name(0),'torch_version':torch.__version__,'cuda_version':torch.version.cuda,
      'input_manifest':str(manifest_path),'input_run_id':manifest.get('run_id'),
      'data_release_id':manifest.get('data_release_id'),'moment_snapshot':snapshot}
    (out/'summary.json').write_text(json.dumps(result,indent=2,default=str)+'\n',encoding='utf8')
    torch.save(trained['checkpoint'],out/'checkpoint.pt')
    volume.commit()
    print(json.dumps(result,default=str),flush=True)
    return result

@app.local_entrypoint()
def main():
    print(json.dumps(run_one_epoch.remote(),indent=2,default=str))
