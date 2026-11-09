#!/usr/bin/env bash
set -Eeuo pipefail
cd /workspace/CD3
source /workspace/CD3/.venv-cq/bin/activate
export TEMPO_PREDICTION_SALT="$(< /workspace/CD3/.tempo_prediction_salt)"
data=data/CQ_V2_2_clean_grain_seed42
output=runs/cq_patchtst_v11_seed42_20261104
audit=runs/cq_patchtst_v11_seed42_20261104_audit
mkdir -p "$output"
trap 'touch "$output/FAILED"' ERR
for window in W1 W2 W3; do
  test -f "$data/train/$window/V11/balanced_train.parquet"
  test -f "$data/train/$window/V9/train.parquet"
  test -f "$data/evaluation/$window/V9/validation.parquet"
  for phase in P1 P2 P3 P4; do test -f "$data/evaluation/$window/V9/test_${phase}.parquet"; done
  test ! -e "$output/CQ/$window/V11/PATCHTST/seed=42/run_manifest.json"
done
for window in W1 W2 W3; do
  echo "START CQ $window V11 PATCHTST seed=42 $(date -u -Is)"
  python -u tools/vastai_train_shared.py --task CQ --data-root "$data" --output-root "$output" \
    --window "$window" --pipeline-id V11 --model-name PATCHTST --seed 42 \
    --batch-size 2048 --accumulation-steps 4 --workers 2 --max-epochs 50 --patience 5 \
    --learning-rate 0.001 --warmup-epochs 0 --run-purpose PRIMARY_GRID \
    --augmentation-seed-policy fixed --static-layout-policy current
done
python -u tools/vastai_audit_shared.py --task CQ --data-root "$data" --run-root "$output" \
  --audit-root "$audit" --model-name PATCHTST --seed 42 --bootstrap-repetitions 2000 --allow-partial
touch "$output/COMPLETE"
