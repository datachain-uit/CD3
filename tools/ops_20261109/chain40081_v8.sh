#!/bin/bash
# 40081: redundant V8 W3 using the copied V5 W3 level-A cache (first result to finish is used)
BASE=/workspace/CD3
cd $BASE
for i in $(seq 1 720); do test -f v5w3_cache_copy.done && test -f up_cq/V8.READY && break; sleep 20; done
test -f v5w3_cache_copy.done || { echo CACHE_COPY_TIMEOUT; exit 1; }
rm -f windows_override_V8; echo W3 > windows_override_V8
echo "V8_W3_START $(date -Is)"
V=V8 PARENT=V5 PARENT_DATA=$BASE/up_par5 BAL_DATA=$BASE/up_cq PARENT_CACHE=$BASE/par5_cache GUARD_KB=16252928 bash $BASE/mantis_child_w23_v2.sh > $BASE/mantis_v8_w3_40081_20261109.log 2> $BASE/mantis_v8_w3_40081_20261109.err.log
echo "V8_W3_END rc=$? $(date -Is)"
