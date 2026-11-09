#!/usr/bin/env bash
# usage: chain_after_lo.sh <V> <PARENT> <WINDOWS> <PARENT_DATA> <PARENT_CACHE> [GUARD_KB]
# Waits until the LO PatchTST job on this host has finished, deletes the LO INPUT data (results stay), then runs the Mantis child.
set -uo pipefail
V=$1; PARENT=$2; WINDOWS=$3; PARENT_DATA=$4; PARENT_CACHE=$5; GUARD=${6:-12582912}
BASE=/workspace/CD3
echo "CHAIN_WAIT_LO $V $WINDOWS $(date -Is)"
quiet=0
while test $quiet -lt 3; do
  if ps -eo args | grep -E "[v]astai_train_shared|[l]o_patch_.*\.sh|[l]o_v7_.*\.sh|[l]o_patchtst_v2" | grep -v "chain_after_lo" >/dev/null; then quiet=0; else quiet=$((quiet+1)); fi
  sleep 60
done
echo "LO_FINISHED $(date -Is)"
rm -rf "$BASE/data/LO_V3_1_clean_grain_seed42"
echo "LO_INPUTS_REMOVED free=$(df -h /workspace|tail -1|awk '{print $4}')"
for i in $(seq 1 720); do test -f "$BASE/up_cq/$V.READY" && break; sleep 20; done
test -f "$BASE/up_cq/$V.READY" || { echo "DATA_TIMEOUT $V"; exit 1; }
echo "$WINDOWS" > "$BASE/windows_override_$V"
echo "MANTIS_START $V $WINDOWS $(date -Is)"
V=$V PARENT=$PARENT PARENT_DATA=$PARENT_DATA BAL_DATA=$BASE/up_cq PARENT_CACHE=$PARENT_CACHE GUARD_KB=$GUARD bash $BASE/mantis_child_w23_v2.sh > $BASE/mantis_${V,,}_chain_20261109.log 2> $BASE/mantis_${V,,}_chain_20261109.err.log
echo "MANTIS_END $V rc=$? $(date -Is)"
