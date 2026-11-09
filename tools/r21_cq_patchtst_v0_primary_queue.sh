#!/bin/bash
# CQ F2 primary V0: launch only after Q-06 is approved.
set -Eeuo pipefail
cd /workspace/CD3
source /venv/main/bin/activate
export TEMPO_PREDICTION_SALT="$(< /workspace/CD3/.tempo_prediction_salt)"
data=data/CQ_V2_2_clean_grain_seed42
output=runs/cq_patchtst_v0_current_seed42_r21
audit=runs/cq_patchtst_v0_current_seed42_r21_audit
mkdir -p "$output"
trap 'touch "$output/QUEUE_FAILED"' ERR
for window in W1 W2 W3; do
  test -f "$data/train/$window/V0/train.parquet"
  for phase in P1 P2 P3 P4; do test -f "$data/evaluation/$window/V0/test_${phase}.parquet"; done
  test -f "$data/evaluation/$window/V0/validation.parquet"
done
for window in W1 W2 W3; do
  echo "START $window V0 PATCHTST seed=42 $(date -u -Is)"
  python -u tools/vastai_train_shared.py --task CQ --data-root "$data" --output-root "$output" \
    --window "$window" --pipeline-id V0 --model-name PATCHTST --seed 42 \
    --batch-size 2048 --accumulation-steps 4 --workers 2 --max-epochs 50 --patience 5 \
    --learning-rate 0.001 --warmup-epochs 0 --run-purpose PRIMARY_GRID \
    --augmentation-seed-policy fixed --static-layout-policy current
done
python -u tools/vastai_audit_shared.py --task CQ --data-root "$data" --run-root "$output" \
  --audit-root "$audit" --model-name PATCHTST --seed 42 --bootstrap-repetitions 2000 --allow-partial
touch "$output/QUEUE_COMPLETE"
