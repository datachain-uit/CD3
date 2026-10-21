#!/usr/bin/env bash
set -euo pipefail
cd /workspace/CD3/code
source /venv/main/bin/activate
export TEMPO_PREDICTION_SALT="$(< /workspace/CD3/reference/ablation_salt)"
data=/workspace/CD3/data/LO_V3_1_clean_grain_seed42
reference=/workspace/CD3/code/LO/resuilt/vastai_f2_batch2048_seed42_20261013/lstm_seed42/LO/W1
for pipeline in V0 V8; do
  for variant in no_static gender_duration; do
    printf '[%s] START %s %s\n' "$(date -Is)" "$pipeline" "$variant"
    python -u tools/vastai_train_shared.py --task LO --data-root "$data" \
      --output-root "/workspace/CD3/runs/lo_static_ablation/$variant" --window W1 \
      --pipeline-id "$pipeline" --model-name LSTM --seed 42 --batch-size 2048 \
      --workers 2 --max-epochs 50 --patience 5 --augmentation-seed-policy fixed \
      --static-ablation "$variant" --reference-layout "$reference/$pipeline/LSTM/seed=42/feature_layout.json"
    printf '[%s] COMPLETE %s %s\n' "$(date -Is)" "$pipeline" "$variant"
  done
done
