#!/usr/bin/env bash
# 40077: V6 W3 (retry after disk failure), then V7 W1-W3. V8 runs on other hosts (skip_V8).
BASE=/workspace/CD3
echo "W3" > $BASE/windows_override_V6
echo "W1 W2 W3" > $BASE/windows_override_V7
for V in V6 V7; do
  echo "QUEUE_START $V $(date -Is)"
  V=$V PARENT=V5 PARENT_DATA=$BASE/mantis_cq_V5_20261108/data BAL_DATA=$BASE/up_cq PARENT_CACHE=$BASE/mantis_cq_V5_20261108/cache GUARD_KB=$([ $V = V6 ] && echo 16252928 || echo 13107200) bash $BASE/mantis_child_w23_v2.sh > $BASE/mantis_${V,,}_q3_20261109.log 2> $BASE/mantis_${V,,}_q3_20261109.err.log
  rc=$?; echo "QUEUE_END $V rc=$rc $(date -Is)"
  if test $rc -ne 0; then echo "STOP_ON_FAILURE $V"; break; fi
done
echo QUEUE_DONE
