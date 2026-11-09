#!/usr/bin/env bash
set -Eeuo pipefail
CODE=/workspace/CD3/lo_patchtst_seed42_code
DATA=/workspace/CD3/data/LO_V3_1_clean_grain_seed42
OUT=/workspace/CD3/runs/lo_patchtst_seed42
SALT=/workspace/CD3/lo_static_v2_prediction_salt
RUN="$OUT/LO/W3/V2/PATCHTST/seed=42"
test -s "$SALT"
test -s "$DATA/download_manifest.json"
test -s "$DATA/train/W3/V2/balanced_train.parquet"
test ! -e "$RUN"
free_kb=$(df -Pk /workspace | awk 'NR==2 {print $4}')
if test "$free_kb" -lt 1572864; then echo "INSUFFICIENT_DISK_KB=$free_kb" >&2; exit 75; fi
source /venv/main/bin/activate
cd "$CODE"
export TEMPO_PREDICTION_SALT="$(cat "$SALT")"
echo "START LO W3 V2 $(date -Is)"
exec python -u tools/vastai_train_shared.py --task LO --data-root "$DATA" --output-root "$OUT" --window W3 --pipeline-id V2 --model-name PATCHTST --seed 42 --batch-size 2048 --accumulation-steps 4 --workers 2 --max-epochs 50 --patience 5 --static-layout-policy current --run-purpose PRIMARY_GRID --augmentation-seed-policy match_model_seed --energy-sampling-interval-seconds 1.0
