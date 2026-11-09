#!/usr/bin/env bash
# usage: relaunch.sh <V> <WINDOWS> <PARENT_DATA> <PARENT_CACHE> <GUARD_KB> <LOGTAG>
V=$1; WIN=$2; PD=$3; PC=$4; GUARD=$5; TAG=$6; BASE=/workspace/CD3; W=$BASE/mantis_cq_${V}_20261108
for w in $WIN; do rm -rf $W/runs/$w/$V; rm -rf $W/cache/task=CQ/window=$w/imputer=V13/adapter=*/encoder=*/pipeline=$V; done
rm -f $W/state/FAILED
echo "$WIN" > $BASE/windows_override_$V
df -h /workspace | tail -1 | awk '{print "free after cleanup", $4}'
V=$V PARENT=V13 PARENT_DATA=$PD BAL_DATA=$BASE/up_cq PARENT_CACHE=$PC GUARD_KB=$GUARD nohup bash $BASE/mantis_child_w23_v2.sh > $BASE/mantis_${V,,}_${TAG}_20261109.log 2> $BASE/mantis_${V,,}_${TAG}_20261109.err.log < /dev/null &
sleep 1; echo launched
