#!/usr/bin/env bash
# Mantis (MANTIS_V2) on task LO for one balanced child pipeline $V (parent imputer pipeline $PARENT), windows in $WINDOWS.
# Reuses the parent's level-A cache by hard link (no extra disk), builds only the synthetic (level-B) cache of the child,
# packages one tar per window and removes the child's synthetic cache afterwards.
# Required env: V PARENT   Optional: WINDOWS ("W1 W2"), ENVROOT, LDD (cuda13 compat dir)
# Layout on the host: /workspace/CD3/lo_mantis_data/{download_manifest.json,train/<W>/<PARENT>,evaluation/<W>/<PARENT>},
#   /workspace/CD3/lo_mantis_children/train/<W>/<V>/balanced_train.parquet, /workspace/CD3/mantis_lo_<PARENT>_20261109/cache (parent cache)
set -Eeuo pipefail
BASE=/workspace/CD3
WORK="$BASE/mantis_lo_${V}_20261109"
DATA="$WORK/data"
STATE="$WORK/state"
PARENT_WORK="$BASE/mantis_lo_${PARENT}_20261109"
PARENT_DATA="$BASE/lo_mantis_data"
BAL="$BASE/lo_mantis_children"
WINDOWS="${WINDOWS:-W1 W2}"
GUARD_KB="${GUARD_KB:-6291456}"
mkdir -p "$WORK" "$STATE" "$DATA"
trap 'touch "$STATE/FAILED"' ERR
rm -f "$STATE/FAILED"
if test -n "${LDD:-}"; then export LD_LIBRARY_PATH="$LDD/usr/local/cuda-13.0/compat:${LD_LIBRARY_PATH:-}"; fi
tar -xf "$BASE/mantis_lo_code_20261109.tar" -C "$WORK"
cp -n "$PARENT_DATA/download_manifest.json" "$DATA/download_manifest.json"
for W in $WINDOWS; do
  mkdir -p "$DATA/train/$W/$PARENT" "$DATA/evaluation/$W/$PARENT" "$DATA/train/$W/$V"
  for f in "$PARENT_DATA/train/$W/$PARENT"/*.parquet; do ln -sf "$f" "$DATA/train/$W/$PARENT/$(basename "$f")"; done
  for f in "$PARENT_DATA/evaluation/$W/$PARENT"/*.parquet; do ln -sf "$f" "$DATA/evaluation/$W/$PARENT/$(basename "$f")"; done
  ln -sf "$BAL/train/$W/$V/balanced_train.parquet" "$DATA/train/$W/$V/balanced_train.parquet"
  test -s "$DATA/train/$W/$V/balanced_train.parquet"
  test -s "$DATA/train/$W/$PARENT/train.parquet"
  test -s "$DATA/evaluation/$W/$PARENT/validation.parquet"
  mkdir -p "$WORK/cache/task=LO/window=$W"
  test -d "$WORK/cache/task=LO/window=$W/imputer=$PARENT" || cp -al "$PARENT_WORK/cache/task=LO/window=$W/imputer=$PARENT" "$WORK/cache/task=LO/window=$W/"
  test -s "$WORK/cache/task=LO/window=$W/imputer=$PARENT/channel_adapter.npz"
done
echo "INPUTS_PRESENT LO $V $WINDOWS $(date -Is)"
ENVROOT="${ENVROOT:-/venv/main}"
source "$ENVROOT/bin/activate"
export PYTHONPATH="$WORK/deps:$WORK:$WORK/tools"
export CUBLAS_WORKSPACE_CONFIG=:4096:8 MALLOC_ARENA_MAX=2 ARROW_NUM_THREADS=2
export TEMPO_PREDICTION_SALT="$(cat "$BASE/lo_static_v2_prediction_salt")"
uv pip install --python "$ENVROOT/bin/python" --target "$WORK/deps" 'einops>=0.8,<0.9' 'huggingface-hub>=0.23' 'safetensors>=0.4' 'zstandard>=0.23' numpy pandas pyarrow scikit-learn >/dev/null
uv pip install --python "$ENVROOT/bin/python" --no-deps --target "$WORK/deps" 'mantis-tsfm==1.1.0' >/dev/null
cd "$WORK"
python -c 'import torch,zstandard,mantis,numpy,pandas,pyarrow,sklearn; assert torch.cuda.is_available(); print("CUDA_READY",torch.__version__,torch.cuda.get_device_name(0),flush=True)'
python -m pip freeze > "$STATE/environment_pip_freeze.txt" 2>/dev/null || true
python -m f3_mantis.cli pin --out "$WORK/backbone_pin.json"
for W in $WINDOWS; do
  free_kb=$(df -Pk /workspace | awk 'NR==2 {print $4}')
  if test "$free_kb" -lt "$GUARD_KB"; then echo "INSUFFICIENT_DISK $W available_kb=$free_kb"; exit 1; fi
  if test -d "$WORK/runs/$W/$V" && ! test -s "$WORK/runs/$W/$V/COMPLETE"; then
    rm -rf "$WORK/runs/$W/$V" "$WORK"/cache/task=LO/window=$W/imputer=$PARENT/adapter=*/encoder=*/pipeline=$V; echo "PARTIAL_RUN_REMOVED $W $V"
  fi
  if ! test -s "$WORK/runs/$W/$V/COMPLETE"; then
    echo "TRAIN_STARTED LO $W $V $(date -Is)"
    python -u tools/run_mantis_grid_zstd_20261109.py --task LO --window "$W" --pipeline "$V" --data-root "$DATA" --work-root "$WORK"
    test -s "$WORK/runs/$W/$V/COMPLETE"
  fi
  python -u tools/verify_mantis_zstd_cache_fixed_20261108.py "cache/task=LO/window=$W" --allow-cell-train
  echo "CACHE_VERIFIED LO $W $V $(date -Is)"
  mkdir -p "adapters/$W"; cp -p "cache/task=LO/window=$W/imputer=$PARENT"/channel_adapter.* "adapters/$W/"
  OUT="$BASE/runs/mantis_lo_${V}_${W}_20261109_results.tar.gz"
  tar -czf "$OUT.partial" -C "$WORK" "runs/$W" "adapters/$W" backbone_pin.json state/environment_pip_freeze.txt
  mv "$OUT.partial" "$OUT"; sha256sum "$OUT" > "$OUT.sha256"
  rm -rf "$WORK"/cache/task=LO/window=$W/imputer=$PARENT/adapter=*/encoder=*/pipeline=$V
  echo "WINDOW_DONE LO $W $V $(date -Is)"
done
touch "$STATE/RESULTS_READY"
echo "RESULTS_READY LO $V $WINDOWS $(date -Is)"
