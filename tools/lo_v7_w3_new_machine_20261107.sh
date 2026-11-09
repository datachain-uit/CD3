#!/usr/bin/env bash
set -Eeuo pipefail
BASE=/workspace/CD3
CODE="$BASE/lo_v7_code"
DATA="$BASE/data/LO_V3_1_clean_grain_seed42"
OUT="$BASE/runs/lo_v7_w3_seed42"
STATE="$BASE/runs/lo_v7_w3_closure_20261107"
mkdir -p "$STATE"
trap 'touch "$STATE/FAILED"' ERR
wait_file() {
  local path="$1" size="$2" hash="$3"
  for i in $(seq 1 1080); do
    if test -f "$path" && test "$(stat -c %s "$path")" -eq "$size"; then
      echo "$hash  $path" | sha256sum -c -
      return 0
    fi
    sleep 10
  done
  echo "TRANSFER_TIMEOUT $path" >&2
  return 1
}
source /venv/main/bin/activate
echo "ENV_SETUP_STARTED $(date -Is)"
uv pip install --python /venv/main/bin/python torch==2.14.1 numpy==2.5.4 pandas==3.1.0 pyarrow==26.0.0 scikit-learn==1.9.1 scipy==1.18.1 nvidia-ml-py==13.615.71 psutil==7.2.2
python -c 'import torch; assert torch.cuda.is_available(); print("CUDA_READY",torch.__version__,torch.cuda.get_device_name(0),flush=True)'
wait_file "$BASE/lo_v7_runner_code_20261107.tar" 808960 bb2f8ff69c4c778439f42e9026e0fb29fc9c67d8ddd122bbb38373549f223ed9
wait_file "$BASE/lo_v7_w3_input_20261107.tar" 215487488 b5ea281ff5f2d367d5fcd75a70096f2b91a0d6111121884d5dfda132a983daa6
echo '0848aebef0ae711d0bc6ad2cad84d785d27218ccb8adbb8df7fb41a3650ffdcc  /workspace/CD3/lo_grid_prediction_salt' | sha256sum -c - >/dev/null
chmod 600 "$BASE/lo_grid_prediction_salt"
test ! -e "$OUT/LO/W3/V7/PATCHTST/seed=42"
mkdir -p "$CODE" "$DATA"
tar -xf "$BASE/lo_v7_runner_code_20261107.tar" -C "$CODE"
tar -xf "$BASE/lo_v7_w3_input_20261107.tar" -C "$DATA"
export TEMPO_PREDICTION_SALT="$(cat "$BASE/lo_grid_prediction_salt")"
export MALLOC_ARENA_MAX=2
cd "$CODE"
python -m pip freeze > "$STATE/environment_pip_freeze.txt"
echo "TRAIN_STARTED W3 V7 $(date -Is)"
python -u tools/vastai_train_shared.py --task LO --data-root "$DATA" --output-root "$OUT" --window W3 --pipeline-id V7 --model-name PATCHTST --seed 42 --batch-size 2048 --accumulation-steps 4 --workers 2 --max-epochs 50 --patience 5 --static-layout-policy current --run-purpose PRIMARY_GRID --augmentation-seed-policy match_model_seed --energy-sampling-interval-seconds 1.0
TARGET="$OUT/LO/W3/V7/PATCHTST/seed=42"
test -s "$TARGET/run_manifest.json"
for P in P1 P2 P3 P4; do test -s "$TARGET/predictions/validation_$P.parquet"; test -s "$TARGET/predictions/test_$P.parquet"; done
echo "TRAIN_COMPLETE W3 V7 $(date -Is)"
wait_file "$BASE/lo_v7_w3_parent_20261107.tar" 108371456 73d091772137d38e4306b776c6a32c96851bb09061643825dde371d8e9596e9a
tar -xf "$BASE/lo_v7_w3_parent_20261107.tar" -C "$DATA"
python -u tools/vastai_audit_shared.py --task LO --data-root "$DATA" --run-root "$OUT" --audit-root "$STATE/audit" --model-name PATCHTST --seed 42 --bootstrap-repetitions 2000 --allow-partial
python -c 'import json,sys; m=json.load(open(sys.argv[1])); assert m["runs"]==1 and m["bootstrap_repetitions"]==2000' "$STATE/audit/LO/PATCHTST/seed=42/audit_manifest.json"
tar -czf "$BASE/runs/lo_v7_w3_closure_20261107.tar.gz.partial" -C "$OUT" LO/W3/V7 -C "$STATE" audit environment_pip_freeze.txt
mv "$BASE/runs/lo_v7_w3_closure_20261107.tar.gz.partial" "$BASE/runs/lo_v7_w3_closure_20261107.tar.gz"
sha256sum "$BASE/runs/lo_v7_w3_closure_20261107.tar.gz" > "$STATE/bundle.sha256"
touch "$STATE/BUNDLE_READY"
echo "BUNDLE_READY $(date -Is)"
