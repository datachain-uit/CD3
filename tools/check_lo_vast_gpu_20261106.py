import sys
import torch
print('torch',torch.__version__,'cuda_build',torch.version.cuda,flush=True)
print('available',torch.cuda.is_available(),flush=True)
if not torch.cuda.is_available():sys.exit(2)
x=torch.ones(1024,device='cuda');print('gpu',torch.cuda.get_device_name(0),'sum',x.sum().item(),flush=True)
