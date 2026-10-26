#!/usr/bin/env bash
# D-23(b) diagnostic only: choose one stable PatchTST configuration before
# pre-registering and replaying the complete V0 W1--W3 pilot / F2 grid.
set -euo pipefail

source /venv/main/bin/activate
cd /workspace/CD3

readonly TASK=CQ
readonly MODEL=PATCHTST
readonly SEED=42
readonly DATA_ROOT=data/CQ_V2_2_clean_grain_seed42
readonly RUN_ROOT=runs/cq_patchtst_v3_stability_pilot_seed42
readonly LOG_ROOT=runs/logs
readonly SALT_FILE=.tempo_prediction_salt

test -s "$SALT_FILE" || { echo "Missing $SALT_FILE" >&2; exit 2; }
test -s "$DATA_ROOT/download_manifest.json" || { echo "Missing $DATA_ROOT/download_manifest.json" >&2; exit 2; }
export TEMPO_PREDICTION_SALT="$(cat "$SALT_FILE")"
mkdir -p "$RUN_ROOT" "$LOG_ROOT"

# D-23(b) candidate.  These two runs are diagnostics, never primary-grid facts.
for WINDOW in W2 W3; do
  RUN_DIR="$RUN_ROOT/$TASK/$WINDOW/V0/$MODEL/seed=$SEED"
  if test -f "$RUN_DIR/run_manifest.json"; then
    echo "[$(date -Is)] SKIP completed $TASK/$WINDOW/V0/$MODEL/seed=$SEED"
    continue
  fi
  echo "[$(date -Is)] START D23 stability pilot $TASK/$WINDOW/V0/$MODEL/seed=$SEED"
  python -u code/vastai_train_shared.py \
    --task "$TASK" --data-root "$DATA_ROOT" --output-root "$RUN_ROOT" \
    --window "$WINDOW" --pipeline-id V0 --model-name "$MODEL" --seed "$SEED" \
    --batch-size 2048 --accumulation-steps 4 --workers 2 --max-epochs 50 --patience 5 \
    --learning-rate 3e-4 --warmup-epochs 1 --gradient-clip-norm 1.0 \
    --static-layout-policy current --run-purpose STABILITY_PILOT_D23 \
    --energy-sampling-interval-seconds 1.0 \
    2>&1 | tee "$LOG_ROOT/${TASK}_${WINDOW}_V0_${MODEL}_D23_seed${SEED}.log"
done

echo "[$(date -Is)] COMPLETE D23 PatchTST stability pilots"
