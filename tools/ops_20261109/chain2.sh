#!/usr/bin/env bash
# usage: chain2.sh <V> <WINDOW> <PARENT_DATA> <PARENT_CACHE> <GUARD_KB> <WAIT_REGEX>
# Second stage on a host: wait until the first-stage process (WAIT_REGEX) is gone, then run the Mantis child for WINDOW
# (the child script itself waits for the parent's channel adapter of that window).
set -uo pipefail
V=$1; WIN=$2; PD=$3; PC=$4; GUARD=$5; RX=$6
BASE=/workspace/CD3
echo "CHAIN2_WAIT $V $WIN $(date -Is)"
quiet=0
while test $quiet -lt 3; do
  if ps -eo args | grep -E "$RX" | grep -v "chain2.sh" | grep -v grep >/dev/null; then quiet=0; else quiet=$((quiet+1)); fi
  sleep 60
done
for i in $(seq 1 720); do test -f "$BASE/up_cq/$V.READY" && break; sleep 20; done
echo "$WIN" > "$BASE/windows_override_$V"
echo "CHAIN2_START $V $WIN $(date -Is)"
V=$V PARENT=V13 PARENT_DATA=$PD BAL_DATA=$BASE/up_cq PARENT_CACHE=$PC GUARD_KB=$GUARD bash $BASE/mantis_child_w23_v2.sh > $BASE/mantis_${V,,}_${WIN,,}_chain2_20261109.log 2> $BASE/mantis_${V,,}_${WIN,,}_chain2_20261109.err.log
echo "CHAIN2_END $V $WIN rc=$? $(date -Is)"
