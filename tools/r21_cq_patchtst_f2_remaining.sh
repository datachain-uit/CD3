#!/bin/bash
set -Eeuo pipefail
cd /workspace/CD3
source /venv/main/bin/activate
export TEMPO_PREDICTION_SALT="$(< /workspace/CD3/.tempo_prediction_salt)"
data=data/CQ_V2_2_clean_grain_seed42
output=runs/cq_patchtst_v0_current_seed42_r21
audit=runs/cq_patchtst_f2_full_seed42_r21_audit
trap 'touch "$output/F2_FAILED"' ERR
for attempt in $(seq 1 2880); do
  test ! -e "$output/QUEUE_FAILED"
  test ! -e "$data/F2_INPUTS_FAILED"
  if test -e "$output/QUEUE_COMPLETE" && test -e "$data/F2_INPUTS_READY"; then break; fi
  sleep 60
done
test -e "$output/QUEUE_COMPLETE"
test -e "$data/F2_INPUTS_READY"
for window in W1 W2 W3; do
  for index in $(seq 1 16); do
    pipeline=V${index}
    echo "START $window $pipeline PATCHTST seed=42 $(date -u -Is)"
    python -u tools/vastai_train_shared.py --task CQ --data-root "$data" --output-root "$output" \
      --window "$window" --pipeline-id "$pipeline" --model-name PATCHTST --seed 42 \
      --batch-size 2048 --accumulation-steps 4 --workers 2 --max-epochs 50 --patience 5 \
      --learning-rate 0.001 --warmup-epochs 0 --run-purpose PRIMARY_GRID \
      --augmentation-seed-policy fixed --static-layout-policy current
  done
done
python -u tools/vastai_audit_shared.py --task CQ --data-root "$data" --run-root "$output" \
  --audit-root "$audit" --model-name PATCHTST --seed 42 --bootstrap-repetitions 2000
touch "$output/F2_COMPLETE"
