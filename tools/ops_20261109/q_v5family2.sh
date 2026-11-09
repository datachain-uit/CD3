#!/usr/bin/env bash
BASE=/workspace/CD3
echo "W2 W3" > $BASE/windows_override_V6
rm -f $BASE/windows_override_V7 $BASE/windows_override_V8
for V in V6 V7 V8; do
  echo "QUEUE_START $V $(date -Is)"
  V=$V PARENT=V5 PARENT_DATA=$BASE/mantis_cq_V5_20261108/data BAL_DATA=$BASE/up_cq PARENT_CACHE=$BASE/mantis_cq_V5_20261108/cache GUARD_KB=11534336 WINDOWS="W1 W2 W3" bash $BASE/mantis_child_w23.sh > $BASE/mantis_${V,,}_q2_20261109.log 2> $BASE/mantis_${V,,}_q2_20261109.err.log
  rc=$?; echo "QUEUE_END $V rc=$rc $(date -Is)"
  if test $rc -eq 0; then rm -rf "$BASE/mantis_cq_${V}_20261108/cache"; fi
done
echo QUEUE_DONE
