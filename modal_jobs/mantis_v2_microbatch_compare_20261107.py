"""Compare pretrained Mantis embeddings for two microbatch sizes on real V1 TRAIN rows."""
from pathlib import Path
import sys,modal
ROOT=Path(__file__).resolve().parents[1]
PKG=ROOT/'docs/06112026/mantis_review/f3_mantis_v0.1.0_2026-11-06'
if (PKG/'f3_mantis').is_dir():sys.path.insert(0,str(PKG))
image=(modal.Image.debian_slim(python_version='3.12').pip_install('torch==2.5.1','numpy>=1.26','pandas>=2.2','pyarrow>=16','scikit-learn>=1.5','einops>=0.8,<0.9','huggingface-hub>=0.23','safetensors>=0.4','nvidia-ml-py>=12').run_commands('pip install --no-deps mantis-tsfm==1.1.0').add_local_python_source('f3_mantis',copy=True).add_local_python_source('model',copy=True))
app=modal.App('cq-mantis-v2-microbatch-comparison-20261107')
volume=modal.Volume.from_name('tempo-data-v1',create_if_missing=False)
@app.function(image=image,gpu='L4',cpu=4,memory=32768,timeout=1200,volumes={'/data':volume})
def run():
 import os,json,time
 os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
 import numpy as np,pandas as pd,pyarrow.parquet as pq,torch
 from huggingface_hub import snapshot_download
 from f3_mantis.adapter import ChannelPCAAdapter
 from f3_mantis.encoder import MantisPrefixEncoder,load_frozen_mantis
 from f3_mantis.determinism import configure_determinism
 from model.data import fit_layout,transform_frame
 configure_determinism(42)
 source=Path('/data/meta_release=imputation-v1/L1_runs/task=CQ/feature_regime=CQ_RAW_EARLY/window_id=W1/pipeline_id=V1/model_name=IMPUTATION_ONLY/seed=20260922/run_id=9ec054562bfc584aba867a5c6f13993e390ad4207d39db11c0ee132b255e5e44/attempt_id=0002/model_inputs/train.parquet')
 previous=Path('/data/diagnostics/mantis_v2_cq_w1_v1_one_epoch/20261106T125608Z/cache')
 adapter=ChannelPCAAdapter.load(previous/'task=CQ/window=W1/imputer=V1/channel_adapter')
 df=next(pq.ParquetFile(source).iter_batches(batch_size=512)).to_pandas();layout=fit_layout(df,task='CQ',phase_id='P4',use_masks=True)
 names=list(layout.dynamic_bases)+[f'missing__{x}' for x in layout.dynamic_bases if f'missing__{x}_P1' in df.columns]+list(layout.mask_phase_bases)+['phase_fraction','delta_t']
 adapter.check_channel_names(names);dynamic,_,_,_=transform_frame(df,layout,classes=('warning','average','good'),use_masks=True)
 snapshot=snapshot_download(repo_id='paris-noah/MantisV2',revision='8f6ca35cb54ab14b120618943c6fca5ddf5a76a6')
 backbone=load_frozen_mantis(device='cuda',snapshot_dir=snapshot); results={};values={}
 for n in (2048,4096):
  torch.cuda.empty_cache();torch.cuda.reset_peak_memory_stats();encoder=MantisPrefixEncoder(backbone,adapter,device='cuda',microbatch_sequences=n,precision='bf16');start=time.monotonic();z=encoder.encode(dynamic);torch.cuda.synchronize()
  values[n]=z;results[str(n)]={'peak_allocated_bytes':torch.cuda.max_memory_allocated(),'peak_reserved_bytes':torch.cuda.max_memory_reserved(),'seconds':time.monotonic()-start,'shape':list(z.shape),'finite':bool(np.isfinite(z).all()),'timing':encoder.last_timing}
 diff=np.abs(values[2048].astype(np.float32)-values[4096].astype(np.float32));comparison={'bitwise_equal':bool(np.array_equal(values[2048],values[4096])),'different_values':int(np.count_nonzero(diff)),'max_abs_diff':float(diff.max()),'mean_abs_diff':float(diff.mean())}
 out=Path('/data/diagnostics/mantis_v2_microbatch_compare_20261107');out.mkdir(parents=True,exist_ok=True)
 result={'scope':'512 real CQ/W1/V1 TRAIN rows; diagnostic only','device':torch.cuda.get_device_name(0),'adapter_digest':adapter.digest(),'results':results,'comparison':comparison,'weights_sha256':backbone.f3_weights_sha256}
 (out/'comparison.json').write_text(json.dumps(result,indent=2)+'\n');volume.commit();print(json.dumps(result,indent=2),flush=True);return result
@app.local_entrypoint()
def main():print(run.remote())
