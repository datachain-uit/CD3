#!/usr/bin/env bash
# Low-priority complete artifact audit for the three LSTM windows on VastAI.
set -euo pipefail

task="${1:?task is required}"
root="${2:?runs root is required}"

source /venv/main/bin/activate
cd /workspace/CD3
export ARROW_NUM_THREADS=1
for window in W1 W2 W3; do
  printf '[%s] auditing %s %s\n' "$(date -Is)" "$task" "$window"
  nice -n 19 python code/vastai_audit_w1.py \
    --root "$root/$task/$window" \
    --task "$task" \
    --window "$window" \
    --model-name LSTM \
    --seed 42
done
