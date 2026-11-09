#!/usr/bin/env bash
set -Eeuo pipefail
V="$1"
BASE=/workspace/CD3
CODE="$BASE/lo_patchtst_seed42_code"
DATA="$BASE/data/LO_V3_1_clean_grain_seed42"
STATE="$BASE/runs/lo_patch_${V}_newhost_20261108"
mkdir -p "$STATE" "$DATA" "$CODE"
trap 'touch "$STATE/FAILED"' ERR
if test "$V" = V5; then
  FILE="$BASE/lo_patch_v5_input_20261108.tar"; SIZE=368082432; HASH=bdafb0522fcdbc96e46cd25aa236f39e7e758158d5d224660ced55711f759126
elif test "$V" = V16; then
  FILE="$BASE/lo_patch_v16_input_20261108.tar"; SIZE=1065886208; HASH=81257ba76fa96ff8145189e752a99a6c15907e8cf02b42ce3a1517f2df1b53a2
else echo 'unsupported pipeline' >&2; exit 1; fi
wait_file() {
  local path="$1" size="$2" hash="$3"
  for i in $(seq 1 2160); do
    if test -f "$path" && test "$(stat -c %s "$path")" -eq "$size"; then
      echo "$hash  $path" | sha256sum -c -; return 0
    fi
    sleep 10
  done
  echo "TRANSFER_TIMEOUT $path" >&2; return 1
}
echo "ENV_SETUP_STARTED $V $(date -Is)"
wait_file "$BASE/cuda-compat-13-0_580.196.07-1ubuntu1_amd64.deb" 65411554 b0ee4fb1f439e919ca5c5fd7c5cff3e8b8afdbdb0b5ee38f7c09c047ea41a035
mkdir -p "$STATE/cuda13"
dpkg-deb -x "$BASE/cuda-compat-13-0_580.196.07-1ubuntu1_amd64.deb" "$STATE/cuda13"
export LD_LIBRARY_PATH="$STATE/cuda13/usr/local/cuda-13.0/compat${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export LO_PY_ENV="$BASE/.venv-cq"
export LO_RESUME_SUFFIX=_newhost_20261108
export PYTHONPATH="$STATE/deps${PYTHONPATH:+:$PYTHONPATH}"
uv pip install --python "$LO_PY_ENV/bin/python" --target "$STATE/deps" numpy==2.5.4 pandas==3.1.0 pyarrow==26.0.0 scikit-learn==1.9.1 scipy==1.18.1 nvidia-ml-py==13.615.71 psutil==7.2.2
"$LO_PY_ENV/bin/python" -c 'import torch,numpy,pandas,pyarrow; assert torch.cuda.is_available(); print("CUDA_READY",torch.__version__,torch.cuda.get_device_name(0),flush=True)'
wait_file "$BASE/lo_v7_runner_code_20261107.tar" 808960 bb2f8ff69c4c778439f42e9026e0fb29fc9c67d8ddd122bbb38373549f223ed9
wait_file "$FILE" "$SIZE" "$HASH"
echo '0848aebef0ae711d0bc6ad2cad84d785d27218ccb8adbb8df7fb41a3650ffdcc  /workspace/CD3/lo_static_v2_prediction_salt' | sha256sum -c - >/dev/null
chmod 600 "$BASE/lo_static_v2_prediction_salt"
tar -xf "$BASE/lo_v7_runner_code_20261107.tar" -C "$CODE"
tar -xf "$FILE" -C "$DATA"
echo "INPUT_READY $V $(date -Is)"
exec bash "$BASE/lo_patch_resume_credit_20261107.sh" "$V"
