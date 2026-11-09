#!/usr/bin/env bash
set -Eeuo pipefail
BASE=/workspace/CD3
APP="$BASE/mantis_cq_v0_w1_20261107"
DATA="$BASE/data/CQ_V2_2_clean_grain_seed42"
# The existing runner expects this path; this job never alters the LO venv.
EXPECTED_APP="$BASE/mantis_v0_20261107"
test ! -e "$EXPECTED_APP"
test ! -e "$DATA"
mkdir -p "$APP" "$DATA"
ln -s "$APP" "$EXPECTED_APP"
trap 'touch "$APP/FAILED"' ERR
tar -xf "$BASE/mantis_v0_code_20261107.tar" -C "$APP"
tar -xf "$BASE/mantis_v0_cq_w1_input_20261107.tar" -C "$DATA"
source /venv/main/bin/activate
python -m pip install --no-cache-dir --target "$APP/deps" 'einops>=0.8,<0.9' 'huggingface-hub>=0.23' 'safetensors>=0.4' 'zstandard>=0.23'
python -m pip install --no-cache-dir --no-deps --target "$APP/deps" 'mantis-tsfm==1.1.0'
export PYTHONPATH="$APP/deps:$APP:$APP/tools"
export CUBLAS_WORKSPACE_CONFIG=:4096:8
export MALLOC_ARENA_MAX=2
export ARROW_NUM_THREADS=2
cd "$APP"
python -c 'import torch,zstandard,mantis; assert torch.cuda.is_available(); print("CUDA_READY", torch.__version__, torch.cuda.get_device_name(0), flush=True)'
python -m pip freeze > environment_pip_freeze.txt
echo "SMOKE_STARTED $(date -Is)"
python -u tools/run_mantis_v0_cq_zstd_20261107.py --window W1 --smoke-rows 512
test -s smoke/W1/V0/COMPLETE
python -u tools/verify_mantis_zstd_cache_20261107.py smoke/W1/V0/cache
echo "SMOKE_PASS $(date -Is)"
echo "FULL_W1_STARTED $(date -Is)"
python -u tools/run_mantis_v0_cq_zstd_20261107.py --window W1
test -s runs/W1/V0/COMPLETE
python -u tools/verify_mantis_zstd_cache_20261107.py runs/W1/V0/cache
echo "CACHE_VERIFIED $(date -Is)"
touch "$APP/W1_COMPLETE"
