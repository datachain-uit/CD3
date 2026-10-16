#!/usr/bin/env bash
# Post-hoc CQ F1 audit for completed VastAI recurrent runs.
# This script never trains, changes checkpoints, or writes model inputs.
set -euo pipefail

source /venv/main/bin/activate
cd /workspace/CD3

task=CQ
data_root="${DATA_ROOT:-data/CQ_V2_2_clean_grain_seed42}"
runs_root="${RUNS_ROOT:-runs}"
audit_root="${AUDIT_ROOT:-runs/audits_seed42}"
seed="${SEED:-42}"
families="${FAMILIES:-RNN LSTM GRU BILSTM}"
completed=0

for family in $families; do
  run_root="$runs_root/${family,,}_seed${seed}"
  if ! test -d "$run_root/$task"; then
    echo "[$(date -Is)] SKIP missing run root: $run_root/$task" >&2
    continue
  fi
  echo "[$(date -Is)] AUDIT $task/$family/seed=$seed"
  python -u code/vastai_audit_shared.py \
    --task "$task" \
    --data-root "$data_root" \
    --run-root "$run_root" \
    --audit-root "$audit_root" \
    --model-name "$family" \
    --seed "$seed" \
    --bootstrap-repetitions 2000
  completed=$((completed + 1))
done

test "$completed" -gt 0 || {
  echo "No requested CQ family run roots exist under $runs_root." >&2
  exit 2
}
echo "[$(date -Is)] COMPLETE CQ F1 post-hoc audit"
