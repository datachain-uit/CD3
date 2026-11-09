#!/usr/bin/env bash
set -Eeuo pipefail
source /venv/main/bin/activate
cd /workspace/CD3/mantis_v0_20261107
export PYTHONPATH=/workspace/CD3/mantis_v0_20261107:/workspace/CD3/mantis_v0_20261107/tools
export CUBLAS_WORKSPACE_CONFIG=:4096:8
test -f ENV_READY
exec python -u tools/run_mantis_v0_cq_zstd_20261107.py --window W1 --smoke-rows 512
