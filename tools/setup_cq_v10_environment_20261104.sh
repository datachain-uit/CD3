#!/usr/bin/env bash
set -Eeuo pipefail
apt-get install -y --no-install-recommends cuda-compat-13-0
export LD_LIBRARY_PATH="/usr/local/cuda-13.0/compat${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
if ! test -x /workspace/CD3/.venv-cq/bin/python; then
  uv venv --python 3.12.15 /workspace/CD3/.venv-cq
fi
source /workspace/CD3/.venv-cq/bin/activate
uv pip install --no-cache 'torch==2.14.1' 'numpy==2.5.4' 'scipy==1.18.1' 'pandas==3.0.0' 'pyarrow==25.0.1' 'scikit-learn==1.8.0' 'nvidia-ml-py' joblib
python -c 'import torch, pandas, pyarrow, sklearn, pynvml; print("versions",torch.__version__,torch.version.cuda,pandas.__version__,pyarrow.__version__,sklearn.__version__); assert torch.cuda.is_available()'
touch /workspace/CD3/V10_ENV_READY
