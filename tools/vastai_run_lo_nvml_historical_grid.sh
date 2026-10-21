#!/usr/bin/env bash
# Full LO matched replay: batch 2048, historical static layout, NVML GPU-only energy.
# Run from the VastAI checkout after setting DATA_ROOT, OUTPUT_ROOT and SALT_FILE if needed.
set -euo pipefail

ROOT="${ROOT:-/workspace/CD3/repo}"
DATA_ROOT="${DATA_ROOT:-/workspace/CD3/data/LO_V3_1_clean_grain_seed42}"
OUTPUT_ROOT="${OUTPUT_ROOT:-/workspace/CD3/runs/lo_nvml_historical_layout_seed42}"
SALT_FILE="${SALT_FILE:-/workspace/CD3/reference/ablation_salt}"
REFERENCE_LAYOUT="${REFERENCE_LAYOUT:-/workspace/CD3/reference/lo_historical_layout.json}"
MIN_FREE_GB="${MIN_FREE_GB:-4}"

source /venv/main/bin/activate
test -s "$SALT_FILE" || { echo "Missing private prediction salt: $SALT_FILE" >&2; exit 2; }
test -s "$REFERENCE_LAYOUT" || { echo "Missing historical layout: $REFERENCE_LAYOUT" >&2; exit 2; }
export TEMPO_PREDICTION_SALT="$(cat "$SALT_FILE")"
mkdir -p "$OUTPUT_ROOT/logs" "$OUTPUT_ROOT/audits"

for family in RNN LSTM GRU BILSTM; do
  for window in W1 W2 W3; do
    for pipeline in V{0..16}; do
      run_dir="$OUTPUT_ROOT/LO/$window/$pipeline/$family/seed=42"
      if test -f "$run_dir/run_manifest.json" && test -f "$run_dir/metadata_contract.json"; then
        echo "[$(date -Is)] SKIP completed LO/$window/$pipeline/$family"
        continue
      fi
      free_gb=$(df -Pk /workspace | awk 'NR==2 {print int($4 / 1024 / 1024)}')
      if [ "$free_gb" -lt "$MIN_FREE_GB" ]; then
        echo "[$(date -Is)] STOP free=${free_gb}GB below guard=${MIN_FREE_GB}GB" >&2
        exit 75
      fi
      echo "[$(date -Is)] START LO/$window/$pipeline/$family free=${free_gb}GB"
      python -u "$ROOT/tools/vastai_train_shared.py" \
        --task LO --data-root "$DATA_ROOT" --output-root "$OUTPUT_ROOT" \
        --window "$window" --pipeline-id "$pipeline" --model-name "$family" --seed 42 \
        --batch-size 2048 --accumulation-steps 1 --workers 2 --max-epochs 50 --patience 5 \
        --static-layout-policy historical_reference --reference-layout "$REFERENCE_LAYOUT" \
        --energy-sampling-interval-seconds 1.0
    done
  done
  echo "[$(date -Is)] AUDIT $family"
  python -u "$ROOT/tools/vastai_audit_shared.py" \
    --task LO --data-root "$DATA_ROOT" --run-root "$OUTPUT_ROOT" --audit-root "$OUTPUT_ROOT/audits" \
    --model-name "$family" --seed 42 --bootstrap-repetitions 2000
done
touch "$OUTPUT_ROOT/LO_NVML_HISTORICAL_GRID_COMPLETE"
echo "[$(date -Is)] COMPLETE LO NVML historical-layout grid"
