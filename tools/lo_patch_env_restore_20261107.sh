#!/usr/bin/env bash
set -Eeuo pipefail
V="$1"
source /venv/main/bin/activate
echo "ENV_RESTORE_STARTED $(date -Is) $V"
python -m pip install --no-cache-dir torch==2.14.1 numpy==2.5.4 pandas==3.1.0 pyarrow==26.0.0 scikit-learn==1.9.1 scipy==1.18.1 nvidia-ml-py==13.615.71 psutil==7.2.2
python -c 'import torch,numpy,pandas,pyarrow,sklearn; assert torch.cuda.is_available(); print("ENV_READY",torch.__version__,flush=True)'
export LO_RESUME_SUFFIX=_env_restore
exec bash /workspace/CD3/lo_patchtst_seed42_code/resume_credit_20261107.sh "$V"
