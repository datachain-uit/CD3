#!/bin/bash
# 37774: after LO V16 finishes -> rebuild V9 W3 level-A (imputer-only run, original adapter pre-placed) -> V10, V11, V12 W3 children (sequential, parent cache hard-linked)
set -uo pipefail
BASE=/workspace/CD3
S=$BASE/runs/lo_patch_V16_newhost_20261108
export LD_LIBRARY_PATH="$S/cuda13/usr/local/cuda-13.0/compat${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export ENVROOT=$BASE/.venv-cq
cd $BASE
echo "BLOCK_WAIT_LO $(date -Is)"
quiet=0
while test $quiet -lt 3; do
  if ps -eo args | grep -E "[v]astai_train_shared|[l]o_patch_.*\.sh|[l]o_v7_.*\.sh" | grep -v block_v9 >/dev/null; then quiet=0; else quiet=$((quiet+1)); fi
  sleep 60
done
echo "LO_FINISHED $(date -Is)"
rm -rf $BASE/data/LO_V3_1_clean_grain_seed42
for i in $(seq 1 720); do test -f $BASE/up_cq/V12.READY && break; sleep 20; done
# --- parent V9 W3 (imputer-only) in its own work dir
W=$BASE/mantis_cq_V9b_20261109
mkdir -p $W/state $W/cache/task=CQ/window=W3/imputer=V9
tar -xf $BASE/mantis_grid_code_20261108.tar -C $W
cp -f $BASE/verify_mantis_zstd_cache_fixed_20261108.py $W/tools/
cp -n $BASE/b9_cache/task=CQ/window=W3/imputer=V9/channel_adapter.* $W/cache/task=CQ/window=W3/imputer=V9/
ln -sfn $BASE/b9_data $W/data
source $ENVROOT/bin/activate
export PYTHONPATH="$W/deps:$W:$W/tools" CUBLAS_WORKSPACE_CONFIG=:4096:8 MALLOC_ARENA_MAX=2 ARROW_NUM_THREADS=2
export TEMPO_PREDICTION_SALT="$(cat $BASE/mantis_cq_prediction_salt)"
uv pip install --python $ENVROOT/bin/python --target $W/deps 'einops>=0.8,<0.9' 'huggingface-hub>=0.23' 'safetensors>=0.4' 'zstandard>=0.23' >/dev/null
uv pip install --python $ENVROOT/bin/python --no-deps --target $W/deps 'mantis-tsfm==1.1.0' >/dev/null
cd $W
python -c 'import torch,zstandard,mantis; assert torch.cuda.is_available(); print("CUDA_READY",torch.__version__,flush=True)'
python -m f3_mantis.cli pin --out $W/backbone_pin.json
echo "PARENT_V9_W3_START $(date -Is)"
python -u tools/run_mantis_cq_grid_zstd_20261108.py --window W3 --pipeline V9 --data-root $BASE/b9_data --work-root $W
test -s $W/runs/W3/V9/COMPLETE && echo "PARENT_V9_W3_DONE $(date -Is)" || { echo "PARENT_V9_W3_FAILED"; exit 1; }
python -u tools/verify_mantis_zstd_cache_fixed_20261108.py cache/task=CQ/window=W3 --allow-cell-train && echo "PARENT_CACHE_VERIFIED $(date -Is)"
cd $BASE
for V in V10 V11 V12; do
  echo W3 > $BASE/windows_override_$V
  echo "CHILD_START $V $(date -Is)"
  V=$V PARENT=V9 PARENT_DATA=$BASE/b9_data BAL_DATA=$BASE/up_cq PARENT_CACHE=$W/cache GUARD_KB=16252928 bash $BASE/mantis_child_w23_v2.sh > $BASE/mantis_${V,,}_w3_blk_20261109.log 2> $BASE/mantis_${V,,}_w3_blk_20261109.err.log
  echo "CHILD_END $V rc=$? $(date -Is)"
done
echo BLOCK_DONE
