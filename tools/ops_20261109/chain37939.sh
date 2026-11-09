#!/usr/bin/env bash
# After Mantis V9 (parent) finishes on this host: V10 W1 W2 (child, parent cache hard-linked). W3 is left for later: disk.
set -uo pipefail
BASE=/workspace/CD3
echo "CHAIN_WAIT_V9 $(date -Is)"
while ! test -f $BASE/mantis_cq_V9_20261108/state/RESULTS_READY; do
  if test -f $BASE/mantis_cq_V9_20261108/state/FAILED; then echo "V9_FAILED $(date -Is)"; exit 1; fi
  sleep 120
done
echo "V9_READY $(date -Is)"
for i in $(seq 1 720); do test -f $BASE/up_cq/V10.READY && break; sleep 20; done
echo "W1 W2" > $BASE/windows_override_V10
V=V10 PARENT=V9 PARENT_DATA=$BASE/mantis_cq_V9_20261108/data BAL_DATA=$BASE/up_cq PARENT_CACHE=$BASE/mantis_cq_V9_20261108/cache GUARD_KB=10485760 bash $BASE/mantis_child_w23_v2.sh > $BASE/mantis_v10_chain_20261109.log 2> $BASE/mantis_v10_chain_20261109.err.log
echo "V10_END rc=$? $(date -Is)"
