#!/bin/bash
set -Eeuo pipefail
cd /workspace/CD3
source /venv/main/bin/activate
export TEMPO_PREDICTION_SALT="$(< /workspace/CD3/.tempo_prediction_salt)"
output=runs/cq_patchtst_r21_replay_1epoch_20261029
mkdir -p "$output"
trap 'touch "$output/REPLAY_FAILED"' ERR
python -u tools/r21_cq_patchtst_replay_wrapper.py \
  --task CQ --data-root data/CQ_V2_2_clean_grain_seed42 --output-root "$output" \
  --window W1 --pipeline-id V0 --model-name PATCHTST --seed 42 \
  --batch-size 2048 --accumulation-steps 4 --workers 2 --max-epochs 1 --patience 5 \
  --learning-rate 0.001 --warmup-epochs 0 --augmentation-seed-policy match_model_seed \
  --static-layout-policy current
sha256sum tools/r21_cq_patchtst_replay_wrapper.py tools/vastai_train_shared.py model/data.py model/shared_phase.py > "$output/source_sha256.txt"
touch "$output/REPLAY_COMPLETE"
