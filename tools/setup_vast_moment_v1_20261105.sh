#!/usr/bin/env bash
set -Eeuo pipefail
cd /workspace/CD3
uv venv --python 3.12.15 moment_v1_venv_20261105
uv pip install --no-cache --python moment_v1_venv_20261105/bin/python 'torch==2.14.1' 'numpy==2.5.4' 'pandas>=2.2' 'pyarrow>=16' 'scikit-learn>=1.5' 'transformers==5.22.1' 'huggingface_hub>=0.24' 'nvidia-ml-py>=12' 'git+https://github.com/moment-timeseries-foundation-model/moment.git@38f7310ad594100747ca2a8357e9c7ca7d323e0e'
export LD_LIBRARY_PATH="/usr/local/cuda-13.0/compat${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
moment_v1_venv_20261105/bin/python -c 'import torch,momentfm; assert torch.cuda.is_available();print(torch.__version__,torch.cuda.get_device_name(0))'
touch moment_v1_environment_ready_20261105
