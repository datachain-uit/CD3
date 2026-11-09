#!/usr/bin/env bash
set -Eeuo pipefail
BASE=/workspace/CD3
WORK="$BASE/mantis_cq_V2_independent_20261108"
DATA="$WORK/data"
CUDA_PROBE=/workspace/cuda13_probe
source "$CUDA_PROBE/venv/bin/activate"
export LD_LIBRARY_PATH="$CUDA_PROBE/extracted/usr/local/cuda-13.0/compat${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PYTHONPATH="$WORK/deps:$WORK:$WORK/tools"
export TEMPO_PREDICTION_SALT="$(cat "$BASE/mantis_cq_prediction_salt")"
export CUBLAS_WORKSPACE_CONFIG=:4096:8
export MALLOC_ARENA_MAX=2
export ARROW_NUM_THREADS=2
cd "$WORK"
python -c 'import torch; assert torch.cuda.is_available(); print("CUDA_READY",torch.__version__,flush=True)'
A="$WORK/cache/task=CQ/window=W3/imputer=V1"
mkdir -p "$A"
cp -n "$BASE/v1_w3_adapter/channel_adapter.npz" "$BASE/v1_w3_adapter/channel_adapter.json" "$A/"
test -s "$A/channel_adapter.npz"
rm -rf "$WORK/runs/W3/V2"
echo "TRAIN_STARTED W3 V2 $(date -Is)"
python -u tools/run_mantis_cq_grid_zstd_20261108.py --window W3 --pipeline V2 --data-root "$DATA" --work-root "$WORK"
test -s "$WORK/runs/W3/V2/COMPLETE"
echo "TRAIN_COMPLETE W3 V2 $(date -Is)"
bash "$BASE/finish_window.sh" V2 V1 W3 mantis_cq_V2_independent_20261108
