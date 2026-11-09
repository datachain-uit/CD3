#!/usr/bin/env bash
# After V14 W2 finishes on this host: refit V13 W1 adapter (same host as the original -> expect identical digest), then V14 W3.
set -uo pipefail
BASE=/workspace/CD3
echo "CHAIN_WAIT_V14W2 $(date -Is)"
while ps -eo args | grep -E "[m]antis_child_w23.sh|[r]un_mantis_cq_grid" >/dev/null; do sleep 60; done
echo "V14W2_PROCESS_ENDED $(date -Is) result=$(ls $BASE/runs/mantis_cq_V14_W2_20261108_results.tar.gz 2>&1)"
source /venv/main/bin/activate
W=$BASE/mantis_cq_V14_20261108
export PYTHONPATH=$W/deps:$W:$W/tools
cd $W
python -u tools/refit_mantis_parent_adapter_20261109.py --window W1 --parent V13 --data-root $BASE/mantis_cq_V13_20261108/data --work-root $BASE/v13_refit44016 --expected-cell-record $BASE/v13_cell_record_W1.json > $BASE/v13_refit44016_W1.log 2>&1
echo "REFIT_W1_RC=$? $(date -Is)"
mkdir -p $BASE/v13_refit44016/cache/task=CQ/window=W3/imputer=V13
cp $BASE/par13_adapter_W3/channel_adapter.* $BASE/v13_refit44016/cache/task=CQ/window=W3/imputer=V13/
echo W3 > $BASE/windows_override_V14
V=V14 PARENT=V13 PARENT_DATA=$BASE/mantis_cq_V13_20261108/data BAL_DATA=$W/data PARENT_CACHE=$BASE/v13_refit44016/cache GUARD_KB=12582912 bash $BASE/mantis_child_w23_v2.sh > $BASE/mantis_v14_w3_chain_20261109.log 2> $BASE/mantis_v14_w3_chain_20261109.err.log
echo "V14W3_END rc=$? $(date -Is)"
