#!/usr/bin/env bash
set -Eeuo pipefail
BASE=/workspace/CD3
WORK=$BASE/mantis_cq_V2_independent_20261108
STATE=$WORK/state
DATA=$WORK/data
M03=$BASE/runs/lo_m03_static_v2_rnn_20261108
mkdir -p "$STATE" "$DATA"
trap 'touch "$STATE/FAILED"' ERR
test -f "$M03/M03_TABLES_COMPLETE"
test -s "$M03/m03_tables/ablation_comparison.csv"
test -s "$M03/m03_tables/ablation_seen_course_x_strict.csv"
echo 'fff1287792c4d1e427d3cb3d9295ae72c7c49bda5233766a65cca39010346f27  /workspace/CD3/mantis_v2_cq_inputs.tar' | sha256sum -c -
echo 'a8a9a10fc89488a862e7e73d300215d1274b633576eb737fec19477e284cdb1c  /workspace/CD3/mantis_grid_code_20261108.tar' | sha256sum -c -
echo '2561a043df15e3f8539efd6d356c8eb620ccc21ed103044f89c67d1dcd415eba  /workspace/CD3/mantis_cq_prediction_salt' | sha256sum -c - >/dev/null
chmod 600 "$BASE/mantis_cq_prediction_salt"
tar -xf "$BASE/mantis_grid_code_20261108.tar" -C "$WORK"
tar -xf "$BASE/mantis_v2_cq_inputs.tar" -C "$DATA"
source /workspace/cuda13_probe/venv/bin/activate
export LD_LIBRARY_PATH="/workspace/cuda13_probe/extracted/usr/local/cuda-13.0/compat:${LD_LIBRARY_PATH:-}"
export PYTHONPATH="$WORK/deps:$WORK:$WORK/tools"
export TEMPO_PREDICTION_SALT="$(cat "$BASE/mantis_cq_prediction_salt")"
export CUBLAS_WORKSPACE_CONFIG=:4096:8 MALLOC_ARENA_MAX=2 ARROW_NUM_THREADS=2
uv pip install --python /workspace/cuda13_probe/venv/bin/python --target "$WORK/deps" 'einops>=0.8,<0.9' 'huggingface-hub>=0.23' 'safetensors>=0.4' 'zstandard>=0.23'
uv pip install --python /workspace/cuda13_probe/venv/bin/python --no-deps --target "$WORK/deps" 'mantis-tsfm==1.1.0'
cd "$WORK"
python -c 'import torch,zstandard,mantis; assert torch.cuda.is_available(); print("CUDA_READY",torch.__version__,torch.cuda.get_device_name(0),flush=True)'
python -m pip freeze > "$STATE/environment_pip_freeze.txt"
python -m f3_mantis.cli pin --out "$WORK/backbone_pin.json"
for W in W1 W2 W3; do
  free_kb=$(df -Pk /workspace | awk 'NR==2 {print $4}')
  if test "$free_kb" -lt 6291456; then echo "INSUFFICIENT_DISK $W $free_kb"; exit 1; fi
  echo "ADAPTER_STARTED $W $(date -Is)"
  python -u "$BASE/prepare_mantis_v2_parent_adapter_20261108.py" --window "$W" --data-root "$DATA" --work-root "$WORK"
  echo "TRAIN_STARTED $W V2 $(date -Is)"
  python -u tools/run_mantis_cq_grid_zstd_20261108.py --window "$W" --pipeline V2 --data-root "$DATA" --work-root "$WORK"
  test -s "$WORK/runs/$W/V2/COMPLETE"
  python -u tools/verify_mantis_zstd_cache_20261107.py "$WORK/cache"
  echo "TRAIN_COMPLETE $W V2 $(date -Is)"
done
tar -czf "$BASE/runs/mantis_cq_V2_independent_20261108_results.tar.gz.partial" -C "$WORK" runs state backbone_pin.json
mv "$BASE/runs/mantis_cq_V2_independent_20261108_results.tar.gz.partial" "$BASE/runs/mantis_cq_V2_independent_20261108_results.tar.gz"
sha256sum "$BASE/runs/mantis_cq_V2_independent_20261108_results.tar.gz" > "$STATE/result.sha256"
touch "$STATE/RESULTS_READY"
