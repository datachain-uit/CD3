#!/usr/bin/env bash
set -Eeuo pipefail
cd /workspace/CD3_CQ
source /workspace/CD3_CQ/.venv-cq/bin/activate

export TEMPO_PREDICTION_SALT="$(< /workspace/CD3_CQ/.tempo_prediction_salt)"
data=data/CQ_V2_2_clean_grain_seed42
output=runs/cq_patchtst_v6_seed42_20261101
audit=runs/cq_patchtst_v6_seed42_20261101_audit
mkdir -p "$output"
trap 'touch "$output/FAILED"' ERR
python tools/preflight_cq_v2_vast_20261101.py > "$output/machine_preflight.json"
for window in W1 W2 W3; do
  for attempt in $(seq 1 180); do
    ready=1
    test -f "$data/train/$window/V6/balanced_train.parquet" || ready=0
    test -f "$data/train/$window/V5/train.parquet" || ready=0
    test -f "$data/evaluation/$window/V5/validation.parquet" || ready=0
    for phase in P1 P2 P3 P4; do test -f "$data/evaluation/$window/V5/test_${phase}.parquet" || ready=0; done
    test "$ready" -eq 1 && break
    echo "WAIT verified inputs for $window attempt=$attempt"
    sleep 60
  done
  test "$ready" -eq 1
  test ! -e "$output/CQ/$window/V6/PATCHTST/seed=42/run_manifest.json"
  echo "START CQ $window V6 PATCHTST seed=42 $(date -u -Is)"
  python -u tools/vastai_train_shared.py --task CQ --data-root "$data" --output-root "$output" \
    --window "$window" --pipeline-id V6 --model-name PATCHTST --seed 42 \
    --batch-size 2048 --accumulation-steps 4 --workers 2 --max-epochs 50 --patience 5 \
    --learning-rate 0.001 --warmup-epochs 0 --run-purpose PRIMARY_GRID \
    --augmentation-seed-policy fixed --static-layout-policy current
done
python -u tools/vastai_audit_shared.py --task CQ --data-root "$data" --run-root "$output" \
  --audit-root "$audit" --model-name PATCHTST --seed 42 --bootstrap-repetitions 2000 --allow-partial
touch "$output/COMPLETE"
