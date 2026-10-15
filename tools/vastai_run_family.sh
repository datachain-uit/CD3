#!/usr/bin/env bash
# Run one recurrent family sequentially; optionally stop before disk exhaustion.
set -euo pipefail

task="${1:?task is required}"
data_root="${2:?data root is required}"
output_root="${3:?output root is required}"
model_name="${4:?model name is required}"
min_free_gb="${5:-0}"
batch_size="${6:-2048}"
accumulation_steps="${7:-}"
if [ -z "$accumulation_steps" ]; then
  if [ "$model_name" = "PATCHTST" ]; then accumulation_steps=4; else accumulation_steps=1; fi
fi

source /venv/main/bin/activate
cd /workspace/CD3
export TEMPO_PREDICTION_SALT="$(cat .tempo_prediction_salt)"

for window in W1 W2 W3; do
  for pipeline in V{0..16}; do
    free_gb=$(df -Pk /workspace | awk 'NR==2 {print int($4 / 1024 / 1024)}')
    if [ "$free_gb" -lt "$min_free_gb" ]; then
      printf '[%s] STOP: only %s GB free; guard=%s GB\n' "$(date -Is)" "$free_gb" "$min_free_gb" >&2
      exit 75
    fi
    printf '[%s] START %s %s %s %s seed42; free=%sGB\n' \
      "$(date -Is)" "$task" "$window" "$pipeline" "$model_name" "$free_gb"
    python -u code/vastai_train_shared.py \
      --task "$task" --data-root "$data_root" --output-root "$output_root" \
      --window "$window" --pipeline-id "$pipeline" --model-name "$model_name" \
      --seed 42 --batch-size "$batch_size" --accumulation-steps "$accumulation_steps" \
      --workers 2 --max-epochs 50 --patience 5 --energy-sampling-interval-seconds 1.0
  done
done
