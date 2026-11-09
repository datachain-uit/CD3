#!/usr/bin/env bash
set -Eeuo pipefail
cd /workspace/CD3
source /venv/main/bin/activate
export TEMPO_PREDICTION_SALT="$(< /workspace/CD3/.tempo_prediction_salt)"
python -u tools/vastai_train_shared.py \
  --task CQ --data-root data/CQ_V2_2_clean_grain_seed42 \
  --output-root runs/cq_rnn_matched_historical_20261029 \
  --window W1 --pipeline-id V0 --model-name RNN --seed 42 \
  --batch-size 2048 --workers 2 --max-epochs 50 --patience 5 \
  --augmentation-seed-policy fixed --static-layout-policy historical_reference \
  --reference-layout /workspace/CD3/cq_w1_v0_baseline_layout_20261029.json
