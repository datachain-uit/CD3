#!/usr/bin/env bash
# Wait for the immutable LO bundle to be complete, then resume the guarded grid.
set -euo pipefail

DATA_ROOT="${DATA_ROOT:-/workspace/CD3/data/LO_V3_1_clean_grain_seed42}"
ROOT="${ROOT:-/workspace/CD3/repo}"
LOG_ROOT="${LOG_ROOT:-/workspace/CD3/runs/lo_nvml_historical_layout_seed42/logs}"
mkdir -p "$LOG_ROOT"

while true; do
  train_count=$(find "$DATA_ROOT/train" -type f -name '*.parquet' -printf x | wc -c)
  evaluation_count=$(find "$DATA_ROOT/evaluation" -type f -name '*.parquet' -printf x | wc -c)
  echo "[$(date -Is)] bundle train=${train_count}/51 evaluation=${evaluation_count}/75" | tee -a "$LOG_ROOT/resume_watch.log"
  if [ "$train_count" -eq 51 ] && [ "$evaluation_count" -eq 75 ]; then
    break
  fi
  sleep 60
done

echo "[$(date -Is)] immutable LO bundle complete; resuming grid" | tee -a "$LOG_ROOT/resume_watch.log"
exec bash "$ROOT/tools/vastai_run_lo_nvml_historical_grid.sh" >> "$LOG_ROOT/grid.log" 2>&1
