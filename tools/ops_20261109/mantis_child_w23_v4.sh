#!/usr/bin/env bash
# Mantis CQ balanced child pipeline $V (parent imputer pipeline $PARENT) for windows $WINDOWS.
# Level-A cache is reused when present, otherwise the runner builds it. Fixed verifier, per-window synthetic cache cleanup.
# Required env: V PARENT PARENT_DATA (dir holding download_manifest.json, train/<W>/<PARENT>, evaluation/<W>/<PARENT>)
#               BAL_DATA (dir holding train/<W>/<V>/balanced_train.parquet)   Optional: WINDOWS (default "W2 W3")
set -Eeuo pipefail
BASE=/workspace/CD3
WORK="$BASE/mantis_cq_${V}_20261108"
DATA="$WORK/data"
STATE="$WORK/state"
WINDOWS="${WINDOWS:-W2 W3}"
if test -s "$BASE/windows_override_$V"; then WINDOWS="$(cat "$BASE/windows_override_$V")"; fi
GUARD_KB="${GUARD_KB:-12582912}"
if test -n "${PARENT_CACHE:-}"; then
  for W in $WINDOWS; do
    for i in $(seq 1 4320); do test -s "$PARENT_CACHE/task=CQ/window=$W/imputer=$PARENT/channel_adapter.npz" && break; sleep 10; done
  done
fi
mkdir -p "$WORK" "$STATE" "$DATA"
trap 'touch "$STATE/FAILED"' ERR
rm -f "$STATE/FAILED"
echo 'a8a9a10fc89488a862e7e73d300215d1274b633576eb737fec19477e284cdb1c  /workspace/CD3/mantis_grid_code_20261108.tar' | sha256sum -c -
echo '2561a043df15e3f8539efd6d356c8eb620ccc21ed103044f89c67d1dcd415eba  /workspace/CD3/mantis_cq_prediction_salt' | sha256sum -c - >/dev/null
chmod 600 "$BASE/mantis_cq_prediction_salt"
tar -xf "$BASE/mantis_grid_code_20261108.tar" -C "$WORK"
cp -f "$BASE/verify_mantis_zstd_cache_fixed_20261108.py" "$WORK/tools/verify_mantis_zstd_cache_fixed_20261108.py"
cp -n "$PARENT_DATA/download_manifest.json" "$DATA/download_manifest.json"
for W in $WINDOWS; do
  mkdir -p "$DATA/train/$W/$PARENT" "$DATA/evaluation/$W/$PARENT" "$DATA/train/$W/$V"
  for f in "$PARENT_DATA/train/$W/$PARENT"/*.parquet; do ln -sf "$f" "$DATA/train/$W/$PARENT/$(basename $f)"; done
  for f in "$PARENT_DATA/evaluation/$W/$PARENT"/*.parquet; do ln -sf "$f" "$DATA/evaluation/$W/$PARENT/$(basename $f)"; done
  if test ! -f "$DATA/train/$W/$V/balanced_train.parquet"; then ln -sf "$BAL_DATA/train/$W/$V/balanced_train.parquet" "$DATA/train/$W/$V/balanced_train.parquet"; fi
  test -s "$DATA/train/$W/$V/balanced_train.parquet"
  test -s "$DATA/train/$W/$PARENT/train.parquet"
  test -s "$DATA/evaluation/$W/$PARENT/validation.parquet"
done
if test -n "${PARENT_CACHE:-}"; then
  for W in $WINDOWS; do
    mkdir -p "$WORK/cache/task=CQ/window=$W"
    test -d "$WORK/cache/task=CQ/window=$W/imputer=$PARENT" || cp -al "$PARENT_CACHE/task=CQ/window=$W/imputer=$PARENT" "$WORK/cache/task=CQ/window=$W/"
    test -s "$WORK/cache/task=CQ/window=$W/imputer=$PARENT/channel_adapter.npz"
  done
fi
echo "INPUTS_PRESENT $V $WINDOWS $(date -Is)"
ENVROOT="${ENVROOT:-/venv/main}"
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
for W in $WINDOWS; do
  free_kb=$(df -Pk /workspace | awk 'NR==2 {print $4}')
  if test "$free_kb" -lt "$GUARD_KB"; then echo "INSUFFICIENT_DISK $W available_kb=$free_kb"; exit 1; fi
  if test -d "$WORK/runs/$W/$V" && ! test -s "$WORK/runs/$W/$V/COMPLETE"; then
    echo "PARTIAL_RUN_REMOVED $W $V"; rm -rf "$WORK/runs/$W/$V" "$WORK"/cache/task=CQ/window=$W/imputer=$PARENT/adapter=*/encoder=*/pipeline=$V
  fi
  if test -s "$WORK/runs/$W/$V/COMPLETE"; then echo "WINDOW_ALREADY_COMPLETE $W $V"; else
  echo "TRAIN_STARTED $W $V $(date -Is)"
  python -u tools/run_mantis_cq_grid_zstd_20261108.py --window "$W" --pipeline "$V" --data-root "$DATA" --work-root "$WORK"
  test -s "$WORK/runs/$W/$V/COMPLETE"
  python -u tools/verify_mantis_zstd_cache_fixed_20261108.py "$WORK/cache" --allow-cell-train
  echo "CACHE_VERIFIED $W $V $(date -Is)"
  mkdir -p "$WORK/adapters/$W"
  cp -p "$WORK/cache/task=CQ/window=$W/imputer=$PARENT"/channel_adapter.* "$WORK/adapters/$W/"
  echo "ADAPTER_SAVED $W $PARENT $(sha256sum $WORK/adapters/$W/channel_adapter.npz | cut -c1-16)"
  rm -rf "$WORK"/cache/task=CQ/window=$W/imputer=$PARENT/adapter=*/encoder=*/pipeline=$V
  echo "SYNTH_CACHE_REMOVED $W $V (results kept in runs/$W/$V)"
  fi
done
OUT="$BASE/runs/mantis_cq_${V}_$(echo $WINDOWS | tr ' ' '_')_20261108_results.tar.gz"
tar -czf "$OUT.partial" -C "$WORK" $(for W in $WINDOWS; do echo runs/$W; done) adapters backbone_pin.json state/environment_pip_freeze.txt
mv "$OUT.partial" "$OUT"
sha256sum "$OUT" > "$OUT.sha256"
touch "$STATE/RESULTS_READY"
echo "RESULTS_READY $V $WINDOWS $(date -Is)"
