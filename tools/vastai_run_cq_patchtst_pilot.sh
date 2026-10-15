#!/usr/bin/env bash
# Locked F2 determinism acceptance: two independent CQ/W1/V0/PATCHTST seed-42 runs.
set -euo pipefail

source /venv/main/bin/activate
cd /workspace/CD3

data_root=data/CQ_V2_2_clean_grain_seed42
salt_file=.tempo_prediction_salt
test -s "$salt_file" || { echo "Missing $salt_file" >&2; exit 2; }
export TEMPO_PREDICTION_SALT="$(cat "$salt_file")"

for attempt in A B; do
  root="runs/patchtst_determinism_pilot_${attempt}"
  echo "[$(date -Is)] START CQ/W1/V0/PATCHTST/seed42 pilot=${attempt}"
  python -u code/vastai_train_shared.py \
    --task CQ --data-root "$data_root" --output-root "$root" \
    --window W1 --pipeline-id V0 --model-name PATCHTST --seed 42 \
    --batch-size 2048 --accumulation-steps 4 --workers 2 --max-epochs 50 --patience 5 \
    --energy-sampling-interval-seconds 1.0
done

echo "[$(date -Is)] COMPLETE CQ PatchTST deterministic pilots"
