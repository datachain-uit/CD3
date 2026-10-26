#!/usr/bin/env bash
# Full LO F1 seed-42 replay under the locked 13-column static-v2 contract.
#
# This deliberately writes to a new root and never reads a historical
# feature_layout.json.  It is therefore safe to run alongside the archived
# 15-column historical-layout campaign.  Set FAMILIES to one family per
# instance when distributing work (for example: FAMILIES=GRU).
set -euo pipefail

ROOT="${ROOT:-/workspace/CD3/repo}"
DATA_ROOT="${DATA_ROOT:-/workspace/CD3/data/LO_V3_1_clean_grain_seed42}"
OUTPUT_ROOT="${OUTPUT_ROOT:-/workspace/CD3/runs/lo_f1_static_v2_seed42}"
SALT_FILE="${SALT_FILE:-/workspace/CD3/reference/ablation_salt}"
FAMILIES="${FAMILIES:-RNN LSTM GRU BILSTM}"
MIN_FREE_GB="${MIN_FREE_GB:-4}"

source /venv/main/bin/activate
cd "$ROOT"
test -s "$SALT_FILE" || { echo "Missing private prediction salt: $SALT_FILE" >&2; exit 2; }
test -s "$DATA_ROOT/download_manifest.json" || { echo "Missing immutable LO input manifest: $DATA_ROOT/download_manifest.json" >&2; exit 2; }
export TEMPO_PREDICTION_SALT="$(cat "$SALT_FILE")"
mkdir -p "$OUTPUT_ROOT/logs" "$OUTPUT_ROOT/audits"

for family in $FAMILIES; do
  case "$family" in RNN|LSTM|GRU|BILSTM) ;; *) echo "Unsupported F1 family: $family" >&2; exit 2;; esac
  for window in W1 W2 W3; do
    for pipeline in V{0..16}; do
      run_dir="$OUTPUT_ROOT/LO/$window/$pipeline/$family/seed=42"
      if test -f "$run_dir/run_manifest.json" && test -f "$run_dir/metadata_contract.json"; then
        echo "[$(date -Is)] SKIP completed LO/$window/$pipeline/$family/seed42"
        continue
      fi
      free_gb=$(df -Pk "$ROOT" | awk 'NR==2 {print int($4 / 1024 / 1024)}')
      if [ "$free_gb" -lt "$MIN_FREE_GB" ]; then
        echo "[$(date -Is)] STOP free=${free_gb}GB below guard=${MIN_FREE_GB}GB" >&2
        exit 75
      fi
      echo "[$(date -Is)] START LO/$window/$pipeline/$family/seed42 static=v2 free=${free_gb}GB"
      python -u tools/vastai_train_shared.py \
        --task LO --data-root "$DATA_ROOT" --output-root "$OUTPUT_ROOT" \
        --window "$window" --pipeline-id "$pipeline" --model-name "$family" --seed 42 \
        --batch-size 2048 --accumulation-steps 1 --workers 2 --max-epochs 50 --patience 5 \
        --static-layout-policy current --energy-sampling-interval-seconds 1.0 \
        2>&1 | tee "$OUTPUT_ROOT/logs/${family}_${window}_${pipeline}.log"
    done
  done
  echo "[$(date -Is)] AUDIT LO/$family static=v2"
  python -u tools/vastai_audit_shared.py \
    --task LO --data-root "$DATA_ROOT" --run-root "$OUTPUT_ROOT" --audit-root "$OUTPUT_ROOT/audits" \
    --model-name "$family" --seed 42 --bootstrap-repetitions 2000
done

touch "$OUTPUT_ROOT/LO_F1_STATIC_V2_SEED42_COMPLETE"
echo "[$(date -Is)] COMPLETE LO F1 static-v2 seed42 families=$FAMILIES"
