#!/usr/bin/env bash
# CQ seed 42: run each new recurrent family, then audit without retraining.
set -euo pipefail
cd /workspace/CD3
export TEMPO_PREDICTION_SALT="$(< .tempo_prediction_salt)"
root=/workspace/CD3/runs/cq_recurrent_batch2048_20261018
data=/workspace/CD3/data/CQ_V2_2_clean_grain_seed42
mkdir -p "$root/logs"
exec >> "$root/logs/queue.log" 2>&1
for family in GRU BILSTM; do
  family_root="$root/${family,,}"
  for window in W1 W2 W3; do
    for pipeline in V{0..16}; do
      free_kb=$(df -Pk /workspace | awk 'NR==2 {print $4}')
      if (( free_kb < 2097152 )); then
        echo "[$(date -Is)] STOP: less than 2 GiB free"
        exit 75
      fi
      target="$family_root/CQ/$window/$pipeline/$family/seed=42"
      if [[ -e "$target" ]]; then
        echo "[$(date -Is)] STOP: output already exists: $target"
        exit 1
      fi
      echo "[$(date -Is)] TRAIN CQ $window $pipeline $family seed42 batch2048"
      /venv/main/bin/python -u /workspace/CD3/code/tools/vastai_train_shared.py \
        --task CQ --data-root "$data" --output-root "$family_root" \
        --window "$window" --pipeline-id "$pipeline" --model-name "$family" \
        --seed 42 --batch-size 2048 --workers 2 --max-epochs 50 --patience 5
    done
  done
  echo "[$(date -Is)] AUDIT CQ $family seed42 bootstrap2000"
  /venv/main/bin/python -u /workspace/CD3/code/vastai_audit_shared.py \
    --task CQ --data-root "$data" --run-root "$family_root" \
    --audit-root "$root/audits" --model-name "$family" --seed 42 \
    --bootstrap-repetitions 2000
done
echo "[$(date -Is)] COMPLETE CQ GRU and BILSTM batch2048"
