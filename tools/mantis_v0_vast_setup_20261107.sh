#!/usr/bin/env bash
set -Eeuo pipefail
source /venv/main/bin/activate
echo "SETUP_STARTED $(date -Is)"
python -m pip install --no-cache-dir 'torch==2.5.1' 'numpy>=1.26,<3' 'pandas>=2.2' 'pyarrow>=16' 'scikit-learn>=1.5' 'einops>=0.8,<0.9' 'huggingface-hub>=0.23' 'safetensors>=0.4' 'nvidia-ml-py>=12' 'zstandard>=0.23'
python -m pip install --no-cache-dir --no-deps 'mantis-tsfm==1.1.0'
python -c 'import torch,zstandard; assert torch.cuda.is_available(); print("CUDA_READY",torch.__version__,torch.cuda.get_device_name(0),flush=True)'
python -m pip freeze > /workspace/CD3/mantis_v0_20261107/environment_pip_freeze.txt
touch /workspace/CD3/mantis_v0_20261107/ENV_READY
echo "SETUP_COMPLETE $(date -Is)"
