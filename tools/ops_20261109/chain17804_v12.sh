#!/bin/bash
# 17804: redundant V12 W3 using the copied V9 W3 level-A cache (the first result to finish is used)
BASE=/workspace/CD3
cd $BASE
for i in $(seq 1 720); do test -f v9w3_cache_copy.done && test -f up_cq/V12.READY && break; sleep 20; done
test -f v9w3_cache_copy.done || { echo CACHE_COPY_TIMEOUT; exit 1; }
rm -f windows_override_V12; echo W3 > windows_override_V12
echo "V12_W3_START $(date -Is)"
V=V12 PARENT=V9 PARENT_DATA=$BASE/up_par9 BAL_DATA=$BASE/up_cq PARENT_CACHE=$BASE/par9_cache GUARD_KB=16252928 bash $BASE/mantis_child_w23_v2.sh > $BASE/mantis_v12_w3_17804_20261109.log 2> $BASE/mantis_v12_w3_17804_20261109.err.log
echo "V12_W3_END rc=$? $(date -Is)"
