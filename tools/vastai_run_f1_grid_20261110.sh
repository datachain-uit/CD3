#!/usr/bin/env bash
# F1 recurrent grid (RNN LSTM GRU BILSTM) of one task and one master seed on one VastAI instance (request 2026-11-10 7.2).
# Generalised from tools/vastai_run_lo_static_v2_grid.sh (task and seed are parameters; the training flags are those of that script).
#   TASK=CQ|LO SEED=43 ROOT=<repo checkout> DATA_ROOT=<seed data root> OUTPUT_ROOT=<run root> SALT_FILE=<private salt> FAMILIES="RNN LSTM GRU BILSTM" bash tools/vastai_run_f1_grid_20261110.sh
# Parents (V0 V1 V5 V9 V13) are trained first, then the balanced children, which wait for $DATA_ROOT/READY_CHILDREN.
# The audit (bootstrap 2000, deterministic probe, --s-leak-reference) is run per family at the end of the family.
set -uo pipefail

TASK="${TASK:?TASK=CQ|LO}"
SEED="${SEED:?SEED}"
ROOT="${ROOT:?ROOT}"
DATA_ROOT="${DATA_ROOT:?DATA_ROOT}"
OUTPUT_ROOT="${OUTPUT_ROOT:?OUTPUT_ROOT}"
SALT_FILE="${SALT_FILE:?SALT_FILE}"
FAMILIES="${FAMILIES:-RNN LSTM GRU BILSTM}"
S_LEAK_REFERENCE="${S_LEAK_REFERENCE:-}"
MIN_FREE_GB="${MIN_FREE_GB:-4}"
LAYOUT_POLICY="${LAYOUT_POLICY:-current}"

test -s "$SALT_FILE" || { echo "Missing private prediction salt: $SALT_FILE" >&2; exit 2; }
test -s "$DATA_ROOT/download_manifest.json" || { echo "Missing input manifest: $DATA_ROOT/download_manifest.json" >&2; exit 2; }
cd "$ROOT"
export PYTHONPATH="$ROOT"
export TEMPO_PREDICTION_SALT="$(cat "$SALT_FILE")"
mkdir -p "$OUTPUT_ROOT/logs" "$OUTPUT_ROOT/audits"
echo "RUNNER_COMMIT $(git rev-parse --short HEAD) TASK=$TASK SEED=$SEED FAMILIES=$FAMILIES"

PARENTS="V0 V1 V5 V9 V13"
CHILDREN="V2 V3 V4 V6 V7 V8 V10 V11 V12 V14 V15 V16"
for family in $FAMILIES; do
  for group in PARENTS CHILDREN; do
    if [ "$group" = CHILDREN ]; then until test -f "$DATA_ROOT/READY_CHILDREN"; do sleep 60; done; pipes="$CHILDREN"; else pipes="$PARENTS"; fi
    for window in W1 W2 W3; do
      for pipeline in $pipes; do
        run_dir="$OUTPUT_ROOT/$TASK/$window/$pipeline/$family/seed=$SEED"
        if test -f "$run_dir/run_manifest.json" && test -f "$run_dir/metadata_contract.json"; then
          echo "[$(date -Is)] SKIP $TASK/$window/$pipeline/$family/seed$SEED"; continue
        fi
        free_gb=$(df -Pk "$ROOT" | awk 'NR==2 {print int($4 / 1024 / 1024)}')
        if [ "$free_gb" -lt "$MIN_FREE_GB" ]; then echo "[$(date -Is)] STOP free=${free_gb}GB below guard=${MIN_FREE_GB}GB" >&2; exit 75; fi
        echo "[$(date -Is)] START $TASK/$window/$pipeline/$family/seed$SEED"
        python -u tools/vastai_train_shared.py \
          --task "$TASK" --data-root "$DATA_ROOT" --output-root "$OUTPUT_ROOT" \
          --window "$window" --pipeline-id "$pipeline" --model-name "$family" --seed "$SEED" \
          --batch-size 2048 --accumulation-steps 1 --workers 2 --max-epochs 50 --patience 5 \
          --static-layout-policy "$LAYOUT_POLICY" --energy-sampling-interval-seconds 1.0 \
          > "$OUTPUT_ROOT/logs/${family}_${window}_${pipeline}.log" 2>&1 \
          && echo "[$(date -Is)] DONE $TASK/$window/$pipeline/$family" || echo "[$(date -Is)] FAILED $TASK/$window/$pipeline/$family"
      done
    done
  done
  echo "[$(date -Is)] AUDIT $TASK/$family seed$SEED"
  ref_args=()
  if [ -n "$S_LEAK_REFERENCE" ]; then ref_args=(--s-leak-reference "$S_LEAK_REFERENCE"); fi
  python -u tools/vastai_audit_shared.py --task "$TASK" --data-root "$DATA_ROOT" --run-root "$OUTPUT_ROOT" --audit-root "$OUTPUT_ROOT/audits" \
    --model-name "$family" --seed "$SEED" --bootstrap-repetitions 2000 "${ref_args[@]}" \
    > "$OUTPUT_ROOT/logs/audit_${family}.log" 2>&1 && echo "[$(date -Is)] AUDIT_DONE $family" || echo "[$(date -Is)] AUDIT_FAILED $family"
done
touch "$OUTPUT_ROOT/F1_${TASK}_SEED${SEED}_COMPLETE"
echo "[$(date -Is)] COMPLETE $TASK F1 seed$SEED families=$FAMILIES"
