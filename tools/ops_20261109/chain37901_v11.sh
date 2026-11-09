#!/bin/bash
# 37901: V11 W3 once the V9 W3 cache copy and data are in place
BASE=/workspace/CD3
CP=$BASE/cuda13_probe
[ -d $CP ] || CP=/workspace/cuda13_probe
export LD_LIBRARY_PATH="$CP/extracted/usr/local/cuda-13.0/compat${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export ENVROOT=$CP/venv
cd $BASE
for i in $(seq 1 720); do test -f v9w3_cache_copy.done && test -f up_cq/V11.READY && break; sleep 20; done
test -f v9w3_cache_copy.done || { echo CACHE_COPY_TIMEOUT; exit 1; }
echo W3 > windows_override_V11
echo "V11_W3_START $(date -Is)"
V=V11 PARENT=V9 PARENT_DATA=$BASE/up_par9 BAL_DATA=$BASE/up_cq PARENT_CACHE=$BASE/par9_cache GUARD_KB=16252928 bash $BASE/mantis_child_w23_v2.sh > $BASE/mantis_v11_w3_37901_20261109.log 2> $BASE/mantis_v11_w3_37901_20261109.err.log
echo "V11_W3_END rc=$? $(date -Is)"
