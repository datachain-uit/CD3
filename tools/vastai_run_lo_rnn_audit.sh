#!/usr/bin/env bash
# Resume-safe LO RNN seed-42 grid followed by the portable post-hoc audit.
set -euo pipefail

source /venv/main/bin/activate
cd /workspace/CD3

task=LO
data_root=data/LO_V3_1_clean_grain_seed42
run_root=runs/rnn_seed42
audit_root=runs/audits_seed42
log_root=runs/logs
salt_file=.tempo_prediction_salt

test -s "$salt_file" || { echo "Missing $salt_file" >&2; exit 2; }
export TEMPO_PREDICTION_SALT="$(cat "$salt_file")"
mkdir -p "$log_root"

for window in W1 W2 W3; do
  for index in $(seq 0 16); do
    pipeline="V${index}"
    run_dir="$run_root/$task/$window/$pipeline/RNN/seed=42"
    if test -f "$run_dir/run_manifest.json" && test -f "$run_dir/metadata_contract.json"; then
      echo "[$(date -Is)] SKIP completed $task/$window/$pipeline/RNN/seed=42"
      continue
    fi
    echo "[$(date -Is)] START $task/$window/$pipeline/RNN/seed=42"
    python -u code/vastai_train_shared.py \
      --task "$task" --data-root "$data_root" --output-root "$run_root" \
      --window "$window" --pipeline-id "$pipeline" --model-name RNN --seed 42 \
      --batch-size 2048 --accumulation-steps 1 --workers 2 --max-epochs 50 --patience 5 \
      --energy-sampling-interval-seconds 1.0
  done
done

echo "[$(date -Is)] START post-hoc audit"
python -u code/vastai_audit_shared.py \
  --task "$task" --data-root "$data_root" --run-root "$run_root" \
  --audit-root "$audit_root" --model-name RNN --seed 42 --bootstrap-repetitions 2000
echo "[$(date -Is)] COMPLETE LO RNN + audit"
