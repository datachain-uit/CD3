#!/usr/bin/env bash
set -Eeuo pipefail
BASE=/workspace/CD3
APP="$BASE/mantis_v0_20261107"
DATA="$BASE/data/CQ_V2_2_clean_grain_seed42"
INPUT="$BASE/mantis_v0_cq_w2_w3_input_20261108.tar"
STATE="$BASE/mantis_v0_w2_w3_queue_20261108"
mkdir -p "$STATE"
trap 'touch "$STATE/FAILED"' ERR
echo "WAIT_W1_COMPLETE $(date -Is)"
for i in $(seq 1 10080); do
  if test -f "$APP/FAILED"; then echo 'W1_FAILED_QUEUE_STOPPED'; exit 1; fi
  if test -f "$APP/W1_COMPLETE"; then break; fi
  sleep 30
done
test -s "$APP/runs/W1/V0/COMPLETE" && test -f "$APP/W1_COMPLETE"
echo "WAIT_W2_W3_INPUT $(date -Is)"
for i in $(seq 1 2160); do
  if test -f "$INPUT" && test "$(stat -c %s "$INPUT")" -eq 266335232; then break; fi
  sleep 10
done
test -f "$INPUT" && test "$(stat -c %s "$INPUT")" -eq 266335232
echo '6a9dde1df8912c2a0f495398bc91af656b9e2e0ce1a3245b371165ce23a2a1e4  /workspace/CD3/mantis_v0_cq_w2_w3_input_20261108.tar' | sha256sum -c -
tar -xf "$INPUT" -C "$DATA"
source /venv/main/bin/activate
export PYTHONPATH="$APP/deps:$APP:$APP/tools"
export CUBLAS_WORKSPACE_CONFIG=:4096:8
export MALLOC_ARENA_MAX=2
export ARROW_NUM_THREADS=2
cd "$APP"
for W in W2 W3; do
  free_kb=$(df -Pk /workspace | awk 'NR==2 {print $4}')
  if test "$free_kb" -lt 8388608; then echo "INSUFFICIENT_DISK $W available_kb=$free_kb"; exit 1; fi
  test ! -e "$APP/runs/$W/V0"
  echo "TRAIN_STARTED $W $(date -Is)"
  python -u tools/run_mantis_v0_cq_zstd_20261107.py --window "$W"
  test -s "$APP/runs/$W/V0/COMPLETE"
  python -u tools/verify_mantis_zstd_cache_20261107.py "$APP/runs/$W/V0/cache"
  echo "CACHE_VERIFIED $W $(date -Is)"
  touch "$STATE/${W}_COMPLETE"
done
touch "$STATE/ALL_COMPLETE"
echo "ALL_COMPLETE $(date -Is)"
