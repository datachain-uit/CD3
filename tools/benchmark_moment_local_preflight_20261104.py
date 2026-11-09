"""Small preflight on real CQ rows; never represents a full epoch or a primary run."""
import os
import sys
import time
from pathlib import Path

os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyarrow.parquet as pq
import torch
from model.data import fit_layout, transform_frame
from model.architectures import build_shared_phase_model

path = Path('downloads/vastai/CQ_V2_2_clean_grain_seed42/train/W1/V1/train.parquet')
frame = next(pq.ParquetFile(path).iter_batches(batch_size=2)).to_pandas()
layout = fit_layout(frame, task='CQ', phase_id='P4', use_masks=True)
dynamic, static, _, labels = transform_frame(frame, layout, classes=('warning','average','good'), use_masks=True)
print('input',dynamic.shape,static.shape,'gpu',torch.cuda.get_device_name(0),flush=True)
t0=time.perf_counter()
model=build_shared_phase_model(dynamic.shape[2],static.shape[1],3,'moment_small',moment_cache_dir=str(Path('.moment_cache/hf/hub').resolve())).cuda()
print('model_loaded_seconds',time.perf_counter()-t0,flush=True)
x=torch.from_numpy(dynamic).cuda(); s=torch.from_numpy(static).cuda(); y=torch.from_numpy(labels).long().cuda()
opt=torch.optim.AdamW((p for p in model.parameters() if p.requires_grad),lr=.001)
torch.cuda.reset_peak_memory_stats(); torch.cuda.synchronize();t0=time.perf_counter()
model.train();opt.zero_grad();z=model(x,s);loss=sum(torch.nn.functional.cross_entropy(z[:,i,:].float(),y) for i in range(4))/4;loss.backward();opt.step();torch.cuda.synchronize()
print('two_rows_forward_backward_seconds',time.perf_counter()-t0,'peak_allocated_mb',torch.cuda.max_memory_allocated()/2**20,'loss',float(loss),flush=True)
