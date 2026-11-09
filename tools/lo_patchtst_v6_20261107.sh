#!/usr/bin/env bash
set -Eeuo pipefail
BASE=/workspace/CD3
CODE="$BASE/lo_patchtst_v6_20261107"
DATA="$BASE/data/LO_V3_1_clean_grain_seed42"
RUNS="$BASE/runs/lo_patchtst_v6_20261107"
AUDIT="$BASE/runs/lo_patchtst_v6_audit_20261107"
STATE="$BASE/runs/lo_patchtst_v6_state_20261107"
BUNDLE="$BASE/runs/lo_patchtst_v6_20261107.tar.gz"
mkdir -p "$STATE"
trap 'code=$?; echo "FAILED exit=$code $(date -Is)"; touch "$STATE/FAILED"' ERR
source /venv/main/bin/activate
cd "$CODE"
echo "INSTALL_STARTED $(date -Is)"
python -m pip install --no-cache-dir 'torch==2.14.1' 'numpy==2.5.4' 'pandas==3.1.0' 'pyarrow==26.0.0' 'scikit-learn==1.9.1' 'scipy==1.18.1' 'nvidia-ml-py==13.615.71' 'psutil==7.2.2'
python -m pip freeze > "$STATE/environment_pip_freeze.txt"
python -c 'import torch; assert torch.cuda.is_available(), "CUDA unavailable"; print("CUDA_READY", torch.__version__, torch.cuda.get_device_name(0), flush=True)'
test -s "$BASE/lo_static_v2_prediction_salt"
test -s "$DATA/download_manifest.json"
export TEMPO_PREDICTION_SALT="$(cat "$BASE/lo_static_v2_prediction_salt")"
for window in W1 W2 W3; do
  target="$RUNS/LO/$window/V6/PATCHTST/seed=42"
  test ! -e "$target"
  test -s "$DATA/train/$window/V6/balanced_train.parquet"
  free_kb=$(df -Pk /workspace | awk 'NR==2 {print $4}')
  if test "$free_kb" -lt 1572864; then echo "INSUFFICIENT_DISK_KB=$free_kb"; exit 75; fi
  echo "TRAIN_STARTED $window V6 $(date -Is)"
  python -u tools/vastai_train_shared.py --task LO --data-root "$DATA" --output-root "$RUNS" --window "$window" --pipeline-id V6 --model-name PATCHTST --seed 42 --batch-size 2048 --accumulation-steps 4 --workers 2 --max-epochs 50 --patience 5 --static-layout-policy current --run-purpose PRIMARY_GRID --augmentation-seed-policy match_model_seed --energy-sampling-interval-seconds 1.0
  test -s "$target/run_manifest.json"
  test -s "$target/metadata_contract.json"
  for phase in P1 P2 P3 P4; do test -s "$target/predictions/validation_$phase.parquet"; test -s "$target/predictions/test_$phase.parquet"; done
  echo "TRAIN_COMPLETE $window V6 $(date -Is)"
done
echo "AUDIT_STARTED $(date -Is)"
mkdir -p "$AUDIT"
audit_status=FAILED
if python -u tools/vastai_audit_shared.py --task LO --data-root "$DATA" --run-root "$RUNS" --audit-root "$AUDIT" --model-name PATCHTST --seed 42 --bootstrap-repetitions 2000 --allow-partial; then
  if python -c 'import json,sys; m=json.load(open(sys.argv[1])); assert m["runs"]==3 and m["bootstrap_repetitions"]==2000' "$AUDIT/LO/PATCHTST/seed=42/audit_manifest.json"; then audit_status=SUCCESS; fi
fi
echo "$audit_status" > "$STATE/audit_status.txt"
echo "AUDIT_STATUS=$audit_status"
cp "$CODE/train_and_audit.log" "$STATE/train_and_audit.log"
cp "$CODE/train_and_audit.err.log" "$STATE/train_and_audit.err.log"
test ! -e "$BUNDLE"
tar -czf "$BUNDLE.partial" -C "$BASE" runs/lo_patchtst_v6_20261107 runs/lo_patchtst_v6_audit_20261107 runs/lo_patchtst_v6_state_20261107
mv "$BUNDLE.partial" "$BUNDLE"
sha256sum "$BUNDLE" > "$STATE/bundle.sha256"
touch "$STATE/BUNDLE_READY"
echo "BUNDLE_READY $audit_status $(date -Is)"
