"""Check the CQ V2 Vast environment without exposing private values."""
import json,sys
import torch,numpy,pandas,pyarrow,sklearn
import pynvml
pynvml.nvmlInit()
gpu=pynvml.nvmlDeviceGetName(pynvml.nvmlDeviceGetHandleByIndex(0))
gpu=gpu.decode() if isinstance(gpu,bytes) else gpu
out={'python':sys.version.split()[0],'torch':torch.__version__,'cuda':torch.version.cuda,'cuda_available':torch.cuda.is_available(),
     'gpu':gpu,'numpy':numpy.__version__,'pandas':pandas.__version__,'pyarrow':pyarrow.__version__,'sklearn':sklearn.__version__}
driver=pynvml.nvmlSystemGetDriverVersion();out['host_driver']=driver.decode() if isinstance(driver,bytes) else driver
if out['cuda_available']:
    x=torch.ones((64,64),device='cuda',dtype=torch.bfloat16);out['bf16_matmul_sum']=float((x@x).float().sum().item());torch.cuda.synchronize()
print(json.dumps(out))
if out['python']!='3.12.15' or not out['cuda_available'] or gpu!='NVIDIA L4' or out['cuda']!='13.0' or out.get('bf16_matmul_sum')!=262144:raise SystemExit('Incompatible environment')
