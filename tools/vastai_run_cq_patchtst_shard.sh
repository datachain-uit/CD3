#!/usr/bin/env bash
# One shard of the CQ PatchTST F2 grid on one VastAI instance (review patch 2026-10-25).
#
# The sequential launcher (vastai_run_cq_patchtst_grid.sh) skips a cell only when its run directory exists on
# the local disk, so several instances started with it would train the same cells twice.  This script trains
# exactly the cells that tools/f2_shard_plan.py assigned to SHARD_INDEX, with the same registered protocol as
# the pilot (2048 = 4 x 512, static_layout_policy current, NVML 1 s) and the same runner checkout on every
# instance (the ingest asserts one runner commit per receipt).
#
#   python tools/f2_shard_plan.py plan --task CQ --model-name PATCHTST --seed 42 --shard-count 6 \
#       --exclude-completed runs/patchtst_pilot --out runs/shard_plan_cq_patchtst_seed42.json
#   SHARD_INDEX=0 PLAN=runs/shard_plan_cq_patchtst_seed42.json bash tools/vastai_run_cq_patchtst_shard.sh
#   ... SHARD_INDEX=5 on the sixth instance; afterwards download every shard under one run root and
#   python tools/f2_shard_plan.py verify --plan <plan> --run-root <root> --expect-static-layout-policy current
set -euo pipefail

ROOT="${ROOT:-/workspace/CD3}"
PLAN="${PLAN:?PLAN=<shard_plan.json from tools/f2_shard_plan.py> is required}"
SHARD_INDEX="${SHARD_INDEX:?SHARD_INDEX=<0..shard_count-1> is required}"
SEED="${SEED:-42}"
TASK="${TASK:-CQ}"
MODEL="${MODEL:-PATCHTST}"
DATA_ROOT="${DATA_ROOT:-$ROOT/data/${TASK}_V2_2_clean_grain_seed${SEED}}"
OUTPUT_ROOT="${OUTPUT_ROOT:-$ROOT/runs/patchtst_channel_independent_v2_1_math_sdp_shard${SHARD_INDEX}}"
SALT_FILE="${SALT_FILE:-$ROOT/.tempo_prediction_salt}"
STATIC_LAYOUT_POLICY="${STATIC_LAYOUT_POLICY:-current}"   # the pilot ran with 'current'; keep one policy per grid
MIN_FREE_GB="${MIN_FREE_GB:-4}"

source /venv/main/bin/activate
cd "$ROOT"
test -s "$SALT_FILE" || { echo "Missing private prediction salt: $SALT_FILE" >&2; exit 2; }
test -s "$DATA_ROOT/download_manifest.json" || { echo "No input tree for seed $SEED at $DATA_ROOT (materialize S2 seed $SEED and build its download manifest first)" >&2; exit 2; }
test -s "$PLAN" || { echo "Missing shard plan: $PLAN" >&2; exit 2; }
export TEMPO_PREDICTION_SALT="$(cat "$SALT_FILE")"
mkdir -p "$OUTPUT_ROOT/logs"
runner_commit="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
python - "$PLAN" "$SHARD_INDEX" "$TASK" "$MODEL" "$SEED" <<'EOF'
import json, sys
plan = json.load(open(sys.argv[1], encoding="utf-8"))
shard, task, model, seed = int(sys.argv[2]), sys.argv[3], sys.argv[4], int(sys.argv[5])
if (plan["task"], plan["model_name"], plan["seed"]) != (task, model, seed):
    raise SystemExit(f"plan is for {plan['task']}/{plan['model_name']}/seed={plan['seed']}, not {task}/{model}/seed={seed}")
if not 0 <= shard < plan["shard_count"]:
    raise SystemExit(f"shard {shard} outside 0..{plan['shard_count'] - 1}")
EOF
cp "$PLAN" "$OUTPUT_ROOT/shard_plan.json"
printf '{"shard_index": %s, "runner_git_commit": "%s", "static_layout_policy": "%s"}\n' "$SHARD_INDEX" "$runner_commit" "$STATIC_LAYOUT_POLICY" > "$OUTPUT_ROOT/shard_receipt.json"

python tools/f2_shard_plan.py cells --plan "$PLAN" --shard "$SHARD_INDEX" | while read -r window pipeline; do
  run_dir="$OUTPUT_ROOT/$TASK/$window/$pipeline/$MODEL/seed=$SEED"
  if test -f "$run_dir/run_manifest.json" && test -f "$run_dir/metadata_contract.json"; then
    echo "[$(date -Is)] SKIP completed $TASK/$window/$pipeline/$MODEL/seed=$SEED"
    continue
  fi
  free_gb=$(df -Pk "$ROOT" | awk 'NR==2 {print int($4 / 1024 / 1024)}')
  if [ "$free_gb" -lt "$MIN_FREE_GB" ]; then
    echo "[$(date -Is)] STOP free=${free_gb}GB below guard=${MIN_FREE_GB}GB" >&2
    exit 75
  fi
  echo "[$(date -Is)] START shard=$SHARD_INDEX $TASK/$window/$pipeline/$MODEL/seed=$SEED runner=$runner_commit free=${free_gb}GB"
  python -u tools/vastai_train_shared.py \
    --task "$TASK" --data-root "$DATA_ROOT" --output-root "$OUTPUT_ROOT" \
    --window "$window" --pipeline-id "$pipeline" --model-name "$MODEL" --seed "$SEED" \
    --batch-size 2048 --accumulation-steps 4 --workers 2 --max-epochs 50 --patience 5 \
    --static-layout-policy "$STATIC_LAYOUT_POLICY" \
    --energy-sampling-interval-seconds 1.0 \
    2>&1 | tee "$OUTPUT_ROOT/logs/${window}_${pipeline}.log"
done
echo "[$(date -Is)] COMPLETE shard=$SHARD_INDEX of $(python -c "import json;print(json.load(open('$PLAN'))['shard_count'])")"
