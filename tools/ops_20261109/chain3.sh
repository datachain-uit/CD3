#!/usr/bin/env bash
# usage: chain3.sh <V> <PARENT> <WINDOW> <PARENT_DATA> <PARENT_CACHE> <GUARD_KB> <WAIT_REGEX>
set -uo pipefail
V=$1; PARENT=$2; WIN=$3; PD=$4; PC=$5; GUARD=$6; RX=$7
BASE=/workspace/CD3
echo "CHAIN3_WAIT $V $WIN $(date -Is)"
quiet=0
while test $quiet -lt 3; do
  if ps -eo args | grep -E "$RX" | grep -v "chain3.sh" | grep -v grep >/dev/null; then quiet=0; else quiet=$((quiet+1)); fi
  sleep 60
done
for i in $(seq 1 720); do test -f "$BASE/up_cq/$V.READY" && break; sleep 20; done
echo "$WIN" > "$BASE/windows_override_$V"
echo "CHAIN3_START $V $WIN $(date -Is)"
V=$V PARENT=$PARENT PARENT_DATA=$PD BAL_DATA=$BASE/up_cq PARENT_CACHE=$PC GUARD_KB=$GUARD bash $BASE/mantis_child_w23_v2.sh > $BASE/mantis_${V,,}_${WIN,,}_chain3_20261109.log 2> $BASE/mantis_${V,,}_${WIN,,}_chain3_20261109.err.log
echo "CHAIN3_END $V $WIN rc=$? $(date -Is)"
