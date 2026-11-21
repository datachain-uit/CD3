#!/usr/bin/env bash
# Mantis (MANTIS_V2) seed 43 on task CQ for one imputer-only pipeline (V0 / V1 / V5 / ...), windows in $2 (default "W1 W2 W3").
# Level-A cache stays on disk (children reuse it); per window: verify cache, package results + adapter.
set -Eeuo pipefail
until ! ps -eo args | grep -E '^python -u tools/vastai_train_shared' | grep -v grep >/dev/null; do sleep 60; done
V=$1; WINDOWS="${2:-W1 W2 W3}"
BASE=/workspace/CD3
WORK="$BASE/mantis_cq44_${V}_20261114"
DATA="$BASE/data/CQ_V2_2_clean_grain_seed44"
STATE="$WORK/state"
mkdir -p "$WORK" "$STATE"
trap 'touch "$STATE/FAILED"' ERR
rm -f "$STATE/FAILED"
echo '2561a043df15e3f8539efd6d356c8eb620ccc21ed103044f89c67d1dcd415eba  /workspace/CD3/mantis_cq_prediction_salt' >/dev/null
tar -xf "$BASE/mantis_lo_code_20261109.tar" -C "$WORK"
ENVROOT="${ENVROOT:-/venv/main}"
source "$ENVROOT/bin/activate"
export PYTHONPATH="$WORK/deps:$WORK:$WORK/tools"
export CUBLAS_WORKSPACE_CONFIG=:4096:8 MALLOC_ARENA_MAX=2 ARROW_NUM_THREADS=2
export TEMPO_PREDICTION_SALT="$(cat "$BASE/mantis_cq_prediction_salt")"
uv pip install --python "$ENVROOT/bin/python" --target "$WORK/deps" 'einops>=0.8,<0.9' 'huggingface-hub>=0.23' 'safetensors>=0.4' 'zstandard>=0.23' numpy pandas pyarrow scikit-learn >/dev/null
uv pip install --python "$ENVROOT/bin/python" --no-deps --target "$WORK/deps" 'mantis-tsfm==1.1.0' >/dev/null
cd "$WORK"
python -c 'import torch,zstandard,mantis,numpy,pandas,pyarrow,sklearn; assert torch.cuda.is_available(); print("CUDA_READY",torch.__version__,torch.cuda.get_device_name(0),flush=True)'
python -m pip freeze > "$STATE/environment_pip_freeze.txt" 2>/dev/null || true
python -m f3_mantis.cli pin --out "$WORK/backbone_pin.json"
if test ! -s "$WORK/smoke/W1/$V/COMPLETE"; then
  python -u tools/run_mantis_grid_zstd_20261109.py --task CQ --seed 44 --window W1 --pipeline "$V" --data-root "$DATA" --work-root "$WORK" --smoke-rows 512
  test -s "$WORK/smoke/W1/$V/COMPLETE"
  python -u tools/verify_mantis_zstd_cache_fixed_20261108.py "$WORK/smoke_cache" --allow-cell-train
  echo "SMOKE_PASS CQ44 $V $(date -Is)"
fi
for W in $WINDOWS; do
  free_kb=$(df -Pk /workspace | awk 'NR==2 {print $4}')
  if test "$free_kb" -lt "${MIN_FREE_KB:-7000000}"; then echo "INSUFFICIENT_DISK $W available_kb=$free_kb"; exit 1; fi
  if test -d "$WORK/runs/$W/$V" && ! test -s "$WORK/runs/$W/$V/COMPLETE"; then rm -rf "$WORK/runs/$W/$V" "$WORK/cache/task=CQ/window=$W"; echo "PARTIAL_RUN_REMOVED $W $V"; fi
  if test ! -s "$WORK/runs/$W/$V/COMPLETE"; then
    echo "TRAIN_STARTED CQ44 $W $V $(date -Is)"
    python -u tools/run_mantis_grid_zstd_20261109.py --task CQ --seed 44 --window "$W" --pipeline "$V" --data-root "$DATA" --work-root "$WORK"
    test -s "$WORK/runs/$W/$V/COMPLETE"
  fi
  python -u tools/verify_mantis_zstd_cache_fixed_20261108.py "cache/task=CQ/window=$W" --allow-cell-train
  echo "CACHE_VERIFIED CQ44 $W $V $(date -Is)"
  mkdir -p "adapters/$W"; cp -p "cache/task=CQ/window=$W/imputer=$V"/channel_adapter.* "adapters/$W/"
  OUT="$BASE/runs/mantis_cq44_${V}_${W}_20261114_results.tar.gz"
  tar -czf "$OUT.partial" -C "$WORK" "runs/$W" "adapters/$W" backbone_pin.json state/environment_pip_freeze.txt
  mv "$OUT.partial" "$OUT"; sha256sum "$OUT" > "$OUT.sha256"
  echo "WINDOW_DONE CQ44 $W $V $(date -Is)"
done
touch "$STATE/RESULTS_READY"
echo "RESULTS_READY CQ44 $V $WINDOWS $(date -Is)"
