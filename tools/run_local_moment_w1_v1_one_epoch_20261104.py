"""Exploratory local one-epoch timing; not an L4 primary-grid result."""
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
os.environ.setdefault('HF_HUB_OFFLINE', '1')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
import torch
from model.data import fit_layout
from model.shared_phase import train_shared_checkpoint

base=Path('downloads/vastai/CQ_V2_2_clean_grain_seed42')
out=Path('CQ/resuilt/cq_moment_small_local_w1_v1_one_epoch_20261104')
out.mkdir(parents=True,exist_ok=True)
print('Loading full W1 V1 TRAIN and VALIDATION',flush=True)
t0=time.perf_counter()
train=pd.read_parquet(base/'train/W1/V1/train.parquet')
validation=pd.read_parquet(base/'evaluation/W1/V1/validation.parquet')
print('Loaded rows',len(train),len(validation),'seconds',round(time.perf_counter()-t0,2),flush=True)
layout=fit_layout(train,task='CQ',phase_id='P4',use_masks=True)
print('Starting one epoch; local exploratory benchmark, batch_size=16, workers=0',flush=True)
t0=time.perf_counter()
checkpoint,history=train_shared_checkpoint(layout=layout,classes=('warning','average','good'),train_frame=train,
 validation_frame=validation,architecture='moment_small',seed=42,batch_size=16,max_epochs=1,patience=1,workers=0,
 moment_cache_dir=str(Path('.moment_cache/hf/hub').resolve()))
result={'task':'CQ','window':'W1','pipeline':'V1','model':'MOMENT_SMALL','benchmark_only':True,
 'train_rows':len(train),'validation_rows':len(validation),'batch_size':16,'max_epochs':1,
 'gpu':torch.cuda.get_device_name(0),'bf16_native':torch.cuda.is_bf16_supported(including_emulation=False),
 'torch_version':torch.__version__,'training_seconds':time.perf_counter()-t0,'history':history}
(out/'summary.json').write_text(json.dumps(result,indent=2,default=str)+'\n',encoding='utf8')
torch.save(checkpoint,out/'checkpoint.pt')
print(json.dumps(result,default=str),flush=True)
