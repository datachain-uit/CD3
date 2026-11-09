"""Diagnostic only: CQ W1 V1 MantisV2, one probe epoch and persistent caches."""
from pathlib import Path
import sys,modal

ROOT=Path(__file__).resolve().parents[1]
PKG=ROOT/'docs/06112026/mantis_review/f3_mantis_v0.1.0_2026-11-06'
if (PKG/'f3_mantis').is_dir():sys.path.insert(0,str(PKG))
image=(modal.Image.debian_slim(python_version='3.12')
 .pip_install('torch==2.5.1','numpy>=1.26','pandas>=2.2','pyarrow>=16','scikit-learn>=1.5','einops>=0.8,<0.9','huggingface-hub>=0.23','safetensors>=0.4','nvidia-ml-py>=12')
 .run_commands('pip install --no-deps mantis-tsfm==1.1.0')
 .add_local_python_source('f3_mantis',copy=True).add_local_python_source('model',copy=True))
app=modal.App('cq-mantis-v2-w1-v1-micro4096-20261107')
volume=modal.Volume.from_name('tempo-data-v1',create_if_missing=False)

@app.function(image=image,gpu='L4',cpu=8,memory=131072,timeout=86400,volumes={'/data':volume})
def run():
 import os,json,copy,subprocess,time,hashlib
 from datetime import datetime,timezone
 from pathlib import Path
 os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
 import numpy as np
 import pandas as pd
 import torch
 from model.data import fit_layout,transform_frame
 from f3_mantis.cell import run_cell
 from f3_mantis.encoder import load_frozen_mantis
 from f3_mantis.spec import MANTIS_V2_SPEC
 from f3_mantis.determinism import configure_determinism
 root=Path('/data/meta_release=imputation-v1/L1_runs/task=CQ/feature_regime=CQ_RAW_EARLY/window_id=W1/pipeline_id=V1/model_name=IMPUTATION_ONLY/seed=20260922')
 candidates=[]
 for path in root.glob('run_id=*/attempt_id=*/run_manifest.json'):
  m=json.loads(path.read_text())
  if m.get('run_status')=='SUCCESS' and m.get('release_id')=='CQ_V2_2' and m.get('split_version')=='v2_2' and m.get('phase_version')=='wide_prefix_v2_2' and (path.parent/'model_inputs/train.parquet').exists():candidates.append(path)
 if not candidates:raise RuntimeError('No verified CQ_V2_2 V1 imputation input in this volume')
 if len(candidates)!=1:raise RuntimeError(f'Ambiguous V1 candidates: {len(candidates)}; select an immutable run explicitly')
 source=candidates[0].parent; inputs=source/'model_inputs'
 source_manifest=json.loads(candidates[0].read_text())
 if source_manifest.get('data_release_id')!='sha256:8db2b1d375c9cb7cd91cbccb7907fca51a8ab9bcd748c7bde43e879b1237d045' or source_manifest.get('run_id')!='9ec054562bfc584aba867a5c6f13993e390ad4207d39db11c0ee132b255e5e44':raise ValueError('Pilot input release/run does not match downloaded test provenance')
 test_path=Path('/data/diagnostics/mantis_v2_cq_w1_v1_inputs_20261106/test_P4.parquet')
 test_sha=hashlib.sha256(test_path.read_bytes()).hexdigest()
 if test_sha!='21ed2522ef6fa84aa474f46eb9c6eff14de5e81b4ddb48ed3db56015e51dddac':raise ValueError('Pilot test file SHA mismatch')
 stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
 out=Path('/data/diagnostics/mantis_v2_cq_w1_v1_micro4096_one_epoch')/stamp;out.mkdir(parents=True,exist_ok=False)
 print(json.dumps({'event':'started','source':str(source),'out':str(out),'microbatch':4096,'max_epochs':1}),flush=True)
 t=time.monotonic();subprocess.run([sys.executable,'-m','f3_mantis.cli','pin','--out',str(out/'backbone_pin.json')],check=True)
 pin=json.loads((out/'backbone_pin.json').read_text()); configure_determinism(42)
 classes=('warning','average','good'); train=pd.read_parquet(inputs/'train.parquet');validation=pd.read_parquet(inputs/'validation.parquet');test=pd.read_parquet(test_path)
 for label,df in [('train',train),('validation',validation),('test',test)]:
  if df.enrollment_id.isna().any() or df.enrollment_id.duplicated().any():raise ValueError(f'{label} enrollment grain invalid')
 layout=fit_layout(train,task='CQ',phase_id='P4',use_masks=True)
 names=list(layout.dynamic_bases)+[f'missing__{x}' for x in layout.dynamic_bases if f'missing__{x}_P1' in train.columns]+list(layout.mask_phase_bases)+['phase_fraction','delta_t']
 def prep(frame):
  x,s,_,y=transform_frame(frame,layout,classes=classes,use_masks=True)
  if x.shape[2]!=len(names):raise ValueError('Dynamic channel names do not match tensor')
  return {'dynamic':x,'static':s,'y':y,'row_ids':frame.enrollment_id.astype(str).to_numpy(),'channel_names':names}
 tr,va,te=prep(train),prep(validation),prep(test);del train,validation,test
 print(json.dumps({'event':'data_ready','train_rows':len(tr['y']),'validation_rows':len(va['y']),'test_rows':len(te['y']),'channels':len(names),'seconds':round(time.monotonic()-t,2)}),flush=True)
 spec=copy.deepcopy(MANTIS_V2_SPEC);spec['training']['max_epochs']=1;spec['training']['early_stopping_patience']=1
 backbone=load_frozen_mantis(device='cuda',snapshot_dir=pin['snapshot_dir'])
 torch.cuda.reset_peak_memory_stats()
 result=run_cell(task='CQ',window='W1',pipeline='V1',imputer='V1',seed=42,num_classes=3,train=tr,validation=va,test=te,backbone=backbone,store_root=str(out/'cache'),out_dir=str(out/'result'),device='cuda',backbone_pin=pin,spec=spec,microbatch_sequences=4096,precision='bf16')
 info={'status':'COMPLETE_DIAGNOSTIC','source_manifest':str(candidates[0]),'test_source':str(test_path),'test_sha256':test_sha,'elapsed_seconds':time.monotonic()-t,'peak_cuda_allocated_bytes':torch.cuda.max_memory_allocated(),'peak_cuda_reserved_bytes':torch.cuda.max_memory_reserved(),'microbatch':4096,'epochs':result['record']['epochs_trained'],'out':str(out),'note':'one epoch and microbatch 4096; not registered full-grid protocol'}
 (out/'pilot_summary.json').write_text(json.dumps(info,indent=2)+'\n');volume.commit();print(json.dumps(info),flush=True);return info

@app.local_entrypoint()
def main():print(run.remote())
