#!/usr/bin/env bash
# Locked F2 primary grid: CQ, PatchTST, all V0--V16 / W1--W3 / seeds 42,43,44.
set -euo pipefail

source /venv/main/bin/activate
cd /workspace/CD3

task=CQ
model=PATCHTST
data_root=data/CQ_V2_2_clean_grain_seed42
run_root=runs/patchtst_channel_independent_v2_1_math_sdp
log_root=runs/logs
salt_file=.tempo_prediction_salt
test -s "$salt_file" || { echo "Missing $salt_file" >&2; exit 2; }
export TEMPO_PREDICTION_SALT="$(cat "$salt_file")"
mkdir -p "$run_root" "$log_root"

for seed in 42 43 44; do
  for window in W1 W2 W3; do
    for index in $(seq 0 16); do
      pipeline="V${index}"
      run_dir="$run_root/$task/$window/$pipeline/$model/seed=$seed"
      if test -f "$run_dir/run_manifest.json" && test -f "$run_dir/metadata_contract.json"; then
        echo "[$(date -Is)] SKIP completed $task/$window/$pipeline/$model/seed=$seed"
        continue
      fi
      echo "[$(date -Is)] START $task/$window/$pipeline/$model/seed=$seed"
      python -u code/vastai_train_shared.py \
        --task "$task" --data-root "$data_root" --output-root "$run_root" \
        --window "$window" --pipeline-id "$pipeline" --model-name "$model" --seed "$seed" \
        --batch-size 2048 --accumulation-steps 4 --workers 2 --max-epochs 50 --patience 5 \
        --energy-sampling-interval-seconds 1.0
    done
  done
  echo "[$(date -Is)] START $task/$model post-hoc audit seed=$seed"
  python -u code/vastai_audit_shared.py \
    --task "$task" --data-root "$data_root" --run-root "$run_root" \
    --audit-root "runs/audits_patchtst_v2_1_math_sdp_seed=$seed" \
    --model-name "$model" --seed "$seed" --bootstrap-repetitions 2000
done

echo "[$(date -Is)] COMPLETE CQ PatchTST F2 grid"
