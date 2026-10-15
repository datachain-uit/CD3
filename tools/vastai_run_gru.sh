#!/usr/bin/env bash
# Start the complete seed-42 GRU grid for one task on a prepared VastAI host.
set -euo pipefail

task="${1:?task is required}"
data_root="${2:?data root is required}"
output_root="${3:?output root is required}"

source /venv/main/bin/activate
cd /workspace/CD3
export TEMPO_PREDICTION_SALT="$(cat .tempo_prediction_salt)"

for window in W1 W2 W3; do
  for pipeline in V{0..16}; do
    printf '[%s] START %s %s %s GRU seed42\n' "$(date -Is)" "$task" "$window" "$pipeline"
    python -u code/vastai_train_shared.py \
      --task "$task" \
      --data-root "$data_root" \
      --output-root "$output_root" \
      --window "$window" \
      --pipeline-id "$pipeline" \
      --model-name GRU \
      --seed 42 \
      --batch-size 2048 \
      --accumulation-steps 1 \
      --workers 2 \
      --max-epochs 50 \
      --patience 5 \
      --energy-sampling-interval-seconds 1.0
  done
done
