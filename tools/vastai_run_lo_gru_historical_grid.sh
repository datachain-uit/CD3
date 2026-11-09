#!/usr/bin/env bash
# Re-run the complete LO GRU seed-42 grid under the locked historical layout.
set -euo pipefail

ROOT="${ROOT:-/workspace/CD3/repo}"
DATA_ROOT="${DATA_ROOT:-/workspace/CD3/data/LO_V3_1_clean_grain_seed42}"
OUTPUT_ROOT="${OUTPUT_ROOT:-/workspace/CD3/runs/lo_gru_historical_layout_seed42}"
SALT_FILE="${SALT_FILE:-/workspace/CD3/reference/ablation_salt}"
REFERENCE_LAYOUT="${REFERENCE_LAYOUT:-/workspace/CD3/reference/lo_historical_layout.json}"
MIN_FREE_GB="${MIN_FREE_GB:-4}"

source /venv/main/bin/activate
test -s "$SALT_FILE" || { echo "Missing private prediction salt" >&2; exit 2; }
test -s "$REFERENCE_LAYOUT" || { echo "Missing historical layout" >&2; exit 2; }
test -f "$DATA_ROOT/download_manifest.json" || { echo "Missing LO data manifest" >&2; exit 2; }
export TEMPO_PREDICTION_SALT="$(cat "$SALT_FILE")"
mkdir -p "$OUTPUT_ROOT/logs" "$OUTPUT_ROOT/audits"

for window in W1 W2 W3; do
  for pipeline in V{0..16}; do
    run_dir="$OUTPUT_ROOT/LO/$window/$pipeline/GRU/seed=42"
    if test -f "$run_dir/run_manifest.json" && test -f "$run_dir/metadata_contract.json"; then
      echo "[$(date -Is)] SKIP completed LO/$window/$pipeline/GRU"
      continue
    fi
    free_gb=$(df -Pk /workspace | awk 'NR==2 {print int($4 / 1024 / 1024)}')
    if [ "$free_gb" -lt "$MIN_FREE_GB" ]; then
      echo "[$(date -Is)] STOP free=${free_gb}GB below guard=${MIN_FREE_GB}GB" >&2
      exit 75
    fi
    echo "[$(date -Is)] START LO/$window/$pipeline/GRU free=${free_gb}GB"
    python -u "$ROOT/tools/vastai_train_shared.py" \
      --task LO --data-root "$DATA_ROOT" --output-root "$OUTPUT_ROOT" \
      --window "$window" --pipeline-id "$pipeline" --model-name GRU --seed 42 \
      --batch-size 2048 --accumulation-steps 1 --workers 2 --max-epochs 50 --patience 5 \
      --static-layout-policy historical_reference --reference-layout "$REFERENCE_LAYOUT" \
      --energy-sampling-interval-seconds 1.0
  done
done

python -u "$ROOT/tools/vastai_audit_shared.py" \
  --task LO --data-root "$DATA_ROOT" --run-root "$OUTPUT_ROOT" --audit-root "$OUTPUT_ROOT/audits" \
  --model-name GRU --seed 42 --bootstrap-repetitions 2000
touch "$OUTPUT_ROOT/LO_GRU_HISTORICAL_GRID_COMPLETE"
echo "[$(date -Is)] COMPLETE LO GRU historical-layout grid"
