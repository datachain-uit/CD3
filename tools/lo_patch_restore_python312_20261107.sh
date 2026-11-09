#!/usr/bin/env bash
set -Eeuo pipefail
V="$1"
BASE=/workspace/CD3/lo_patchtst_seed42_code
ENV="$BASE/venv_py312_20261107"
echo "PY312_ENV_STARTED $V $(date -Is)"
uv python install 3.12
uv venv --python 3.12 "$ENV"
uv pip install --python "$ENV/bin/python" torch==2.14.1 numpy==2.5.4 pandas==3.1.0 pyarrow==26.0.0 scikit-learn==1.9.1 scipy==1.18.1 nvidia-ml-py==13.615.71 psutil==7.2.2
"$ENV/bin/python" -c 'import torch,numpy,pandas,pyarrow,sklearn; assert torch.cuda.is_available(); print("ENV_READY",torch.__version__,flush=True)'
export LO_PY_ENV="$ENV"
export LO_RESUME_SUFFIX=_python312
exec bash "$BASE/resume_credit_20261107.sh" "$V"
