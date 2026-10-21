#!/usr/bin/env bash
# Run the CQ RNN family on VastAI with the exact historical static layout used
# by the existing CQ LSTM runs.  Outputs are separate from the current-layout
# grid and carry the reference-layout hash in their immutable sidecars.
set -Eeuo pipefail

ROOT=${1:-/workspace/CD3}
DATA_ROOT=${2:-"$ROOT/data/CQ_V2_2_clean_grain_seed42"}
LSTM_REFERENCE_ROOT=${3:-"$ROOT/runs/recurrent_batch2048_energy_seed42_20261015/lstm"}
OUTPUT_ROOT=${4:-"$ROOT/runs/cq_rnn_historical_layout_batch2048_seed42"}
AUDIT_ROOT=${5:-"$ROOT/runs/audits_cq_rnn_historical_layout_batch2048_seed42"}

cd "$ROOT/code"
source /venv/main/bin/activate
: "${TEMPO_PREDICTION_SALT:=$(< "$ROOT/.tempo_prediction_salt")}"
export TEMPO_PREDICTION_SALT

for window in W1 W2 W3; do
  for pipeline in V{0..16}; do
    reference="$LSTM_REFERENCE_ROOT/CQ/$window/$pipeline/LSTM/seed=42/feature_layout.json"
    test -f "$reference"
    echo "[$(date -Is)] START CQ $window $pipeline RNN seed42 historical_layout"
    python -u tools/vastai_train_shared.py \
      --task CQ --data-root "$DATA_ROOT" --output-root "$OUTPUT_ROOT" \
      --window "$window" --pipeline-id "$pipeline" --model-name RNN --seed 42 \
      --batch-size 2048 --workers 2 --max-epochs 50 --patience 5 \
      --augmentation-seed-policy fixed \
      --static-layout-policy historical_reference --reference-layout "$reference"
  done
done

python -u tools/vastai_audit_shared.py \
  --task CQ --data-root "$DATA_ROOT" --run-root "$OUTPUT_ROOT" \
  --audit-root "$AUDIT_ROOT" --model-name RNN --seed 42 --bootstrap-repetitions 2000
