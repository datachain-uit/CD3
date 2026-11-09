import torch
print('torch',torch.__version__,'cuda_build',torch.version.cuda,flush=True)
print('available',torch.cuda.is_available(),flush=True)
assert torch.cuda.is_available(), 'CUDA unavailable with the locked torch build'
x=torch.ones((128,128),device='cuda',dtype=torch.bfloat16)
y=x@x
torch.cuda.synchronize()
print('gpu',torch.cuda.get_device_name(0),'result',y[0,0].item(),flush=True)
