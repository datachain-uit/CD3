#!/usr/bin/env bash
set -Eeuo pipefail
V="$1"
BASE=/workspace/CD3
WORK="$BASE/mantis_cq_${V}_20261108"
DATA="$WORK/data"
STATE="$WORK/state"
mkdir -p "$WORK" "$STATE"
trap 'touch "$STATE/FAILED"' ERR
case "$V" in
  V1) SIZE=365133312; HASH=a95da48ef7c17c3c54ce087919f386ea571aa4b580a55bdd7d31447531ccfb03;;
  V5) SIZE=366891008; HASH=7073381796ccc023275585309fe0a67cbda5a890893c4dea6b42ce6edc2eb743;;
  V9) SIZE=370115584; HASH=d0efcf9e700d472d66f7ab755f832268a5d3774f2d47fbb0157976f2c35cbabf;;
  V13) SIZE=474460160; HASH=14223bca48ce24eb9221dc7ed9253200251f8b5d5cc3bd2e5af264c1fd26e2aa;;
  *) echo 'This launcher accepts imputer-only V1/V5/V9/V13' >&2; exit 1;;
esac
echo "WAITING_LO_VERIFIED $V $(date -Is)"
for i in $(seq 1 10080); do
  test -f "$BASE/mantis_LO_archive_verified_${V}" && break
  sleep 30
done
test -f "$BASE/mantis_LO_archive_verified_${V}"
echo "LO_ARCHIVE_GATE_PASS $V $(date -Is)"
INPUT="$BASE/mantis_${V}_input_20261108.tar"
for i in $(seq 1 2160); do
  if test -f "$INPUT" && test "$(stat -c %s "$INPUT")" -eq "$SIZE"; then break; fi
  sleep 10
done
test -f "$INPUT" && test "$(stat -c %s "$INPUT")" -eq "$SIZE"
echo "$HASH  $INPUT" | sha256sum -c -
echo 'a8a9a10fc89488a862e7e73d300215d1274b633576eb737fec19477e284cdb1c  /workspace/CD3/mantis_grid_code_20261108.tar' | sha256sum -c -
echo '2561a043df15e3f8539efd6d356c8eb620ccc21ed103044f89c67d1dcd415eba  /workspace/CD3/mantis_cq_prediction_salt' | sha256sum -c - >/dev/null
chmod 600 "$BASE/mantis_cq_prediction_salt"
mkdir -p "$DATA"
tar -xf "$BASE/mantis_grid_code_20261108.tar" -C "$WORK"
tar -xf "$INPUT" -C "$DATA"
if test "$V" = V13; then ENVROOT="$BASE/lo_patchtst_seed42_code/venv_py312_20261107"; else ENVROOT=/venv/main; fi
source "$ENVROOT/bin/activate"
export PYTHONPATH="$WORK/deps:$WORK:$WORK/tools"
export CUBLAS_WORKSPACE_CONFIG=:4096:8
export MALLOC_ARENA_MAX=2
export ARROW_NUM_THREADS=2
export TEMPO_PREDICTION_SALT="$(cat "$BASE/mantis_cq_prediction_salt")"
uv pip install --python "$ENVROOT/bin/python" --target "$WORK/deps" 'einops>=0.8,<0.9' 'huggingface-hub>=0.23' 'safetensors>=0.4' 'zstandard>=0.23'
uv pip install --python "$ENVROOT/bin/python" --no-deps --target "$WORK/deps" 'mantis-tsfm==1.1.0'
cd "$WORK"
python -c 'import torch,zstandard,mantis; assert torch.cuda.is_available(); print("CUDA_READY",torch.__version__,torch.cuda.get_device_name(0),flush=True)'
python -m pip freeze > "$STATE/environment_pip_freeze.txt" || true
python -m f3_mantis.cli pin --out "$WORK/backbone_pin.json"
python -u tools/run_mantis_cq_grid_zstd_20261108.py --window W1 --pipeline "$V" --data-root "$DATA" --work-root "$WORK" --smoke-rows 512
test -s "$WORK/smoke/W1/$V/COMPLETE"
python -u tools/verify_mantis_zstd_cache_20261107.py "$WORK/smoke_cache"
echo "SMOKE_PASS $V $(date -Is)"
for W in W1 W2 W3; do
  free_kb=$(df -Pk /workspace | awk 'NR==2 {print $4}')
  if test "$free_kb" -lt 6291456; then echo "INSUFFICIENT_DISK $W available_kb=$free_kb"; exit 1; fi
  echo "TRAIN_STARTED $W $V $(date -Is)"
  python -u tools/run_mantis_cq_grid_zstd_20261108.py --window "$W" --pipeline "$V" --data-root "$DATA" --work-root "$WORK"
  test -s "$WORK/runs/$W/$V/COMPLETE"
  python -u tools/verify_mantis_zstd_cache_20261107.py "$WORK/cache"
  echo "CACHE_VERIFIED $W $V $(date -Is)"
done
tar -czf "$BASE/runs/mantis_cq_${V}_20261108_results.tar.gz.partial" -C "$WORK" runs backbone_pin.json state/environment_pip_freeze.txt
mv "$BASE/runs/mantis_cq_${V}_20261108_results.tar.gz.partial" "$BASE/runs/mantis_cq_${V}_20261108_results.tar.gz"
sha256sum "$BASE/runs/mantis_cq_${V}_20261108_results.tar.gz" > "$STATE/result.sha256"
touch "$STATE/RESULTS_READY"
echo "RESULTS_READY $V $(date -Is)"
