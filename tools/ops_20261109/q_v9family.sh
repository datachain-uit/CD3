#!/usr/bin/env bash
# On the V9 host: after the running V10 job, run V11 then V12 for W1 W2 (V9 level-A caches are hard-linked).
set -uo pipefail
BASE=/workspace/CD3
export ENVROOT=/workspace/CD3/lo_patchtst_seed42_code/venv_py312_20261107
echo "Q9_WAIT $(date -Is)"
quiet=0
while test $quiet -lt 3; do
  if ps -eo args | grep -E "mantis_child_w23_v2.sh|run_v10.sh|run_mantis_cq_grid" | grep -v grep | grep -v q_v9family >/dev/null; then quiet=0; else quiet=$((quiet+1)); fi
  sleep 60
done
for V in V11 V12; do
  for i in $(seq 1 720); do test -f "$BASE/up_cq/$V.READY" && break; sleep 20; done
  echo "W1 W2" > "$BASE/windows_override_$V"
  echo "Q9_START $V $(date -Is)"
  V=$V PARENT=V9 PARENT_DATA=$BASE/mantis_cq_V9_20261108/data BAL_DATA=$BASE/up_cq PARENT_CACHE=$BASE/mantis_cq_V9_20261108/cache GUARD_KB=9961472 bash $BASE/mantis_child_w23_v2.sh > $BASE/mantis_${V,,}_q9_20261109.log 2> $BASE/mantis_${V,,}_q9_20261109.err.log
  echo "Q9_END $V rc=$? $(date -Is)"
done
echo Q9_DONE
