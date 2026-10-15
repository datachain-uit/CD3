#!/usr/bin/env bash
# Locked F2 primary grid: CQ, PatchTST, all V0--V16 / W1--W3 / seeds 42,43,44.
set -euo pipefail

source /venv/main/bin/activate
cd /workspace/CD3

task=CQ
model=PATCHTST
# MATCH_MASTER_SEED: every master seed consumes the S2 artifacts of its own seed, so each seed has its own
# compact input tree (built by build_cq_vastai_download_manifest.py for that seed).  A seed whose tree is
# absent is skipped with a message instead of being trained on the seed-42 artifacts; the runner would
# refuse such a balanced cell anyway (MATCH_MASTER_SEED check), but V0/V1/V5/V9/V13 would not be caught.
data_root_for_seed() { printf 'data/CQ_V2_2_clean_grain_seed%s' "$1"; }
run_root=runs/patchtst_channel_independent_v2_1_math_sdp
log_root=runs/logs
salt_file=.tempo_prediction_salt
test -s "$salt_file" || { echo "Missing $salt_file" >&2; exit 2; }
export TEMPO_PREDICTION_SALT="$(cat "$salt_file")"
mkdir -p "$run_root" "$log_root"

for seed in 42 43 44; do
  data_root="$(data_root_for_seed "$seed")"
  if ! test -s "$data_root/download_manifest.json"; then
    echo "[$(date -Is)] SKIP seed=$seed: no input tree at $data_root (materialize S2 seed $seed and build its manifest first)"
    continue
  fi
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
