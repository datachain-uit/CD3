#!/bin/bash
BASE=/workspace/CD3
S=$BASE/runs/lo_patch_V16_newhost_20261108
export LD_LIBRARY_PATH="$S/cuda13/usr/local/cuda-13.0/compat${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export ENVROOT=$BASE/.venv-cq
cd $BASE
rm -f skip_V12 windows_override_V12 mantis_cq_V12_20261108/state/FAILED
rm -rf mantis_cq_V12_20261108/runs/W3/V12 mantis_cq_V12_20261108/cache/task=CQ/window=W3/imputer=V9/adapter=*/encoder=*/pipeline=V12
echo W3 > windows_override_V12
df -h /workspace | tail -1 | awk '{print "free", $4}'
V=V12 PARENT=V9 PARENT_DATA=$BASE/b9_data BAL_DATA=$BASE/up_cq PARENT_CACHE=$BASE/mantis_cq_V9b_20261109/cache GUARD_KB=16252928 bash $BASE/mantis_child_w23_v2.sh
