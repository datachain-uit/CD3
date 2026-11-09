#!/usr/bin/env bash
set -Eeuo pipefail
PIPELINE="$1"; ENVROOT="$2"
CODE=/workspace/CD3/lo_patchtst_seed42_code
DATA=/workspace/CD3/data/LO_V3_1_clean_grain_seed42
OUT=/workspace/CD3/runs/lo_patchtst_seed42
SALT=/workspace/CD3/lo_static_v2_prediction_salt
source "$ENVROOT/bin/activate"
cd "$CODE"
test -s "$SALT" && test -s "$DATA/download_manifest.json"
export TEMPO_PREDICTION_SALT="$(cat "$SALT")"
for window in W1 W2 W3; do
  run_dir="$OUT/LO/$window/$PIPELINE/PATCHTST/seed=42"
  if test -f "$run_dir/_SUCCESS"; then echo "SKIP $window $PIPELINE"; continue; fi
  free_kb=$(df -Pk /workspace | awk 'NR==2 {print $4}')
  if test "$free_kb" -lt 1572864; then echo "INSUFFICIENT_DISK_KB=$free_kb" >&2; exit 75; fi
  echo "START $window $PIPELINE $(date -Is)"
  python -u tools/vastai_train_shared.py --task LO --data-root "$DATA" --output-root "$OUT" --window "$window" --pipeline-id "$PIPELINE" --model-name PATCHTST --seed 42 --batch-size 2048 --accumulation-steps 4 --workers 2 --max-epochs 50 --patience 5 --static-layout-policy current --run-purpose PRIMARY_GRID --energy-sampling-interval-seconds 1.0
done
echo "ALL_WINDOWS_COMPLETE $PIPELINE $(date -Is)"
