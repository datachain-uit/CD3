#!/usr/bin/env bash
set -Eeuo pipefail
BASE=/workspace/CD3/mantis_v0_20261107
STATE="$BASE/state"
mkdir -p "$STATE" "$BASE/packages"
trap 'code=$?; echo "FAILED exit=$code $(date -Is)"; touch "$STATE/FAILED"' ERR
source /venv/main/bin/activate
cd "$BASE"
export PYTHONPATH="$BASE:$BASE/tools"
export CUBLAS_WORKSPACE_CONFIG=:4096:8
test -f ENV_READY
test -f smoke/W1/V0/COMPLETE
for window in W1 W2 W3; do
  target="$BASE/runs/$window/V0"
  test ! -e "$target"
  echo "TRAIN_STARTED $window $(date -Is)"
  python -u tools/run_mantis_v0_cq_zstd_20261107.py --window "$window"
  test -s "$target/COMPLETE"
  test -s "$target/result/probe_head.pt"
  test -s "$target/result/f3_cell_record.json"
  test -s "$target/result/diagnostic_metrics.json"
  echo "CACHE_VERIFY_STARTED $window $(date -Is)"
  python -u tools/verify_mantis_zstd_cache_20261107.py "$target/cache"
  size_kb=$(du -sk "$target" | awk '{print $1}')
  free_kb=$(df -Pk /workspace | awk 'NR==2 {print $4}')
  if test "$free_kb" -lt "$((size_kb + 2097152))"; then echo "INSUFFICIENT_SPACE_TO_PACKAGE window=$window"; exit 75; fi
  archive="$BASE/packages/mantis_cq_v0_${window}_20261107.tar"
  test ! -e "$archive"
  tar -cf "$archive.partial" -C "$BASE" "runs/$window/V0" tools/mantis_v0_cq_prefix_check_20261107.json
  mv "$archive.partial" "$archive"
  sha256sum "$archive" > "$STATE/$window.sha256"
  touch "$STATE/${window}_BUNDLE_READY"
  echo "BUNDLE_READY $window $(date -Is)"
done
touch "$STATE/ALL_COMPLETE"
echo "ALL_COMPLETE $(date -Is)"
