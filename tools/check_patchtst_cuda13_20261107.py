import torch
from architectures import SharedPhasePatchTSTClassifier
torch.manual_seed(42)
torch.use_deterministic_algorithms(True)
model=SharedPhasePatchTSTClassifier(dynamic_dim=40,static_dim=13,num_classes=3).cuda().train()
optimizer=torch.optim.AdamW(model.parameters(),lr=1e-4)
x=torch.randn(16,4,40,device='cuda')
s=torch.randn(16,13,device='cuda')
with torch.autocast(device_type='cuda',dtype=torch.bfloat16):
    pred=model(x,s)
    loss=pred.float().square().mean()
loss.backward()
optimizer.step()
torch.cuda.synchronize()
assert torch.isfinite(loss)
print('PATCHTST_FORWARD_BACKWARD_OK', 'loss',float(loss), 'shape',tuple(pred.shape), 'peak_mib',torch.cuda.max_memory_allocated()/1048576, flush=True)
