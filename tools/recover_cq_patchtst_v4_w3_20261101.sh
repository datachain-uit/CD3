#!/usr/bin/env bash
set -Eeuo pipefail
cd /workspace/CD3_CQ
source .venv-cq/bin/activate
export TEMPO_PREDICTION_SALT="$(< .tempo_prediction_salt)"
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
data=data/CQ_V2_2_clean_grain_seed42
output=runs/cq_patchtst_v4_seed42_20261101
audit=runs/cq_patchtst_v4_seed42_20261101_audit
test ! -e "$output/CQ/W3/V4/PATCHTST/seed=42/run_manifest.json"
echo "START recovery CQ W3 V4 workers=0 $(date -u -Is)"
python -u tools/vastai_train_shared.py --task CQ --data-root "$data" --output-root "$output" \
  --window W3 --pipeline-id V4 --model-name PATCHTST --seed 42 \
  --batch-size 2048 --accumulation-steps 4 --workers 0 --max-epochs 50 --patience 5 \
  --learning-rate 0.001 --warmup-epochs 0 --run-purpose PRIMARY_GRID \
  --augmentation-seed-policy fixed --static-layout-policy current
echo "START audit $(date -u -Is)"
python -u tools/vastai_audit_shared.py --task CQ --data-root "$data" --run-root "$output" \
  --audit-root "$audit" --model-name PATCHTST --seed 42 --bootstrap-repetitions 2000 --allow-partial
touch "$output/RECOVERY_COMPLETE"
echo "RECOVERY_COMPLETE $(date -u -Is)"
