#!/bin/bash
set -Eeuo pipefail
V="$1"
BASE=/workspace/CD3
CODE="$BASE/lo_patchtst_seed42_code"
DATA="$BASE/data/LO_V3_1_clean_grain_seed42"
RUNS="$BASE/runs/lo_patchtst_seed42"
STATE="$BASE/runs/lo_patch_${V}_closure"
AUDIT="$STATE/audit"
mkdir -p "$STATE"
trap 'touch "$STATE/FAILED"' ERR
if test -x /workspace/cuda13_probe/venv/bin/python; then
  source /workspace/cuda13_probe/venv/bin/activate
  export LD_LIBRARY_PATH="/workspace/cuda13_probe/extracted/usr/local/cuda-13.0/compat${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
elif test -x /workspace/CD3/.venv-cq/bin/python; then
  source /workspace/CD3/.venv-cq/bin/activate
else
  source /venv/main/bin/activate
fi
python -m pip install --no-cache-dir torch==2.14.1 numpy==2.5.4 pandas==3.1.0 pyarrow==26.0.0 scikit-learn==1.9.1 scipy==1.18.1 nvidia-ml-py==13.615.71 psutil==7.2.2
python -c 'import torch; assert torch.cuda.is_available()'
python -m pip freeze > "$STATE/environment_pip_freeze.txt"
nvidia-smi > "$STATE/nvidia_smi.txt"
printf '%s\n' "${LD_LIBRARY_PATH:-}" > "$STATE/ld_library_path.txt"
export TEMPO_PREDICTION_SALT="$(cat "$BASE/lo_static_v2_prediction_salt")"
cd "$CODE"
for W in W1 W2 W3; do
  TARGET="$RUNS/LO/$W/$V/PATCHTST/seed=42"
  test ! -e "$TARGET"
  echo "TRAIN_STARTED $W $V $(date -Is)"
  python -u tools/vastai_train_shared.py --task LO --data-root "$DATA" --output-root "$RUNS" --window "$W" --pipeline-id "$V" --model-name PATCHTST --seed 42 --batch-size 2048 --accumulation-steps 4 --workers 2 --max-epochs 50 --patience 5 --static-layout-policy current --run-purpose PRIMARY_GRID --augmentation-seed-policy match_model_seed --energy-sampling-interval-seconds 1.0
  test -s "$TARGET/run_manifest.json"
  test -s "$TARGET/metadata_contract.json"
  for P in P1 P2 P3 P4; do test -s "$TARGET/predictions/validation_$P.parquet"; test -s "$TARGET/predictions/test_$P.parquet"; done
done
mkdir -p "$STATE/selected/LO" "$AUDIT"
for W in W1 W2 W3; do
  mkdir -p "$STATE/selected/LO/$W/$V"
  ln -s "$RUNS/LO/$W/$V/PATCHTST" "$STATE/selected/LO/$W/$V/PATCHTST"
done
python -u tools/vastai_audit_shared.py --task LO --data-root "$DATA" --run-root "$STATE/selected" --audit-root "$AUDIT" --model-name PATCHTST --seed 42 --bootstrap-repetitions 2000 --allow-partial
python -c 'import json,sys; m=json.load(open(sys.argv[1])); assert m["runs"]==3 and m["bootstrap_repetitions"]==2000' "$AUDIT/LO/PATCHTST/seed=42/audit_manifest.json"
mkdir -p "$STATE/artifacts/LO"
for W in W1 W2 W3; do mkdir -p "$STATE/artifacts/LO/$W"; cp -a "$RUNS/LO/$W/$V" "$STATE/artifacts/LO/$W/"; done
tar -czf "$BASE/runs/lo_patch_${V}_closure.tar.gz.partial" -C "$STATE" artifacts audit environment_pip_freeze.txt nvidia_smi.txt ld_library_path.txt
mv "$BASE/runs/lo_patch_${V}_closure.tar.gz.partial" "$BASE/runs/lo_patch_${V}_closure.tar.gz"
sha256sum "$BASE/runs/lo_patch_${V}_closure.tar.gz" > "$STATE/bundle.sha256"
touch "$STATE/BUNDLE_READY"
