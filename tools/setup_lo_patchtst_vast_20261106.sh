#!/usr/bin/env bash
set -Eeuo pipefail
mkdir -p /workspace/CD3/lo_patchtst_seed42_code
/venv/main/bin/pip install --no-cache-dir 'torch==2.14.1' 'pandas==3.1.0' 'pyarrow==26.0.0' 'scikit-learn==1.9.1' 'nvidia-ml-py>=12'
touch /workspace/CD3/lo_patchtst_seed42_code/ENV_READY
