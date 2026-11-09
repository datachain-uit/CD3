"""Isolated CQ/W1/V1 MOMENT Small one-epoch pilot; not a primary run."""
import os
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
import json
import time
from pathlib import Path
import modal

app=modal.App('cq-moment-bf16-validation-one-epoch-20261105')
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
    from model.architectures import prepare_moment_snapshot
    import model.shared_phase as shared
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
      'gpu':torch.cuda.get_device_name(0),'batch_size':2048,'accumulation_steps':32,
      'micro_batch_size':64,'asset_prepare_seconds':download_seconds}),flush=True)
    # One-epoch diagnostic: checkpoint 1 is the only possible selected state.
    # Cache that checkpoint's validation result so the final evaluation can
    # reuse it; this is deliberately not applied to general multi-epoch runs.
    original_eval = shared._evaluate_prefixes
    validation_cache = []
    timings = {}
    def evaluate_bf16(model, dynamic, static, y, batch_size, workers, device, class_ids, *, seed=0):
        if validation_cache:
            print(json.dumps({'event':'reuse_validation_predictions'}), flush=True)
            return validation_cache[0]
        count = min(128, len(y))
        model.eval()
        dx = torch.as_tensor(dynamic[:count], device=device)
        sx = torch.as_tensor(static[:count], device=device)
        with torch.no_grad():
            fp32 = model(dx, sx).float()
            with torch.autocast(device_type='cuda', dtype=torch.bfloat16):
                bf16 = model(dx, sx).float()
        delta = (fp32 - bf16).abs()
        timings['sample_equivalence'] = {'rows':count, 'logit_abs_max':float(delta.max().item()),
            'logit_abs_mean':float(delta.mean().item()),
            'prediction_disagreements':int((fp32.argmax(-1) != bf16.argmax(-1)).sum().item()),
            'phase_predictions':int(fp32.shape[0] * fp32.shape[1])}
        started = time.perf_counter()
        with torch.autocast(device_type='cuda', dtype=torch.bfloat16):
            result = original_eval(model, dynamic, static, y, batch_size, workers, device, class_ids, seed=seed)
        timings['validation_bf16_seconds'] = time.perf_counter() - started
        print(json.dumps({'event':'validation_bf16_complete', **timings}), flush=True)
        validation_cache.append(result)
        return result
    shared._evaluate_prefixes = evaluate_bf16
    torch.cuda.reset_peak_memory_stats();t0=time.perf_counter()
    trained,_=train_shared_checkpoint(layout=layout,classes=('warning','average','good'),train_frame=train,
      validation_frame=validation,architecture='moment_small',seed=42,batch_size=2048,accumulation_steps=32,
      max_epochs=1,patience=1,workers=2,moment_cache_dir=cache,moment_snapshot=snapshot['snapshot'])
    elapsed=time.perf_counter()-t0
    out=Path('/data/meta_release=imputation-v1/L3_meta/diagnostics/cq_moment_w1_v1_bf16_validation_20261105')
    out.mkdir(parents=True,exist_ok=True)
    result={'status':'SUCCESS','purpose':'ONE_EPOCH_TIMING_PILOT_NOT_PRIMARY','task':'CQ','window':'W1',
      'pipeline':'V1','model':'MOMENT_SMALL','seed':42,'batch_size':2048,'micro_batch_size':64,
      'accumulation_steps':32,'train_rows':len(train),'validation_rows':len(validation),'elapsed_seconds':elapsed,
      'history':trained['history'],'validation_diagnostic':timings,'validation_autocast':'BF16',
      'final_validation':'REUSED_ONE_EPOCH_SELECTED_CHECKPOINT',
      'peak_gpu_allocated_bytes':torch.cuda.max_memory_allocated(),
      'gpu':torch.cuda.get_device_name(0),'torch_version':torch.__version__,'cuda_version':torch.version.cuda,
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
