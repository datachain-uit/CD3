#!/bin/bash
# usage: queue_lo.sh <port> <host> <V> <W> <ENVROOT> [LD_DIR]   upload data, then start a waiter that runs the LO parent window once the host is free
P=$1; H=$2; V=$3; W=$4; ENVR=$5; LDD=$6
/tmp/w/up_lo_parent_w.sh $P $H $V $W || exit 1
ssh -o ConnectTimeout=15 -i ~/.ssh/id_vastai -p $P root@$H "cd /workspace/CD3; cat > lo_next_${V}_${W}.sh <<EOS
cd /workspace/CD3
quiet=0
while test \\$quiet -lt 3; do
  if ps -eo args | grep -E 'run_mantis_grid_zstd|run_mantis_cq_grid|lo_mantis_parent.sh|pkg_w1_|mantis_child_w23|run_lo_|run_v12w3|vastai_train_shared' | grep -v lo_next_ | grep -v grep >/dev/null; then quiet=0; else quiet=\\$((quiet+1)); fi
  sleep 60
done
echo QUEUE_GATE_PASSED \\$(date -Is)
[ -n \"$LDD\" ] && export LD_LIBRARY_PATH=\"$LDD/usr/local/cuda-13.0/compat:\\$LD_LIBRARY_PATH\"
rm -rf mantis_lo_${V}_20261109
ENVROOT=$ENVR bash lo_mantis_parent.sh $V \"$W\"
EOS
nohup bash lo_next_${V}_${W}.sh > mantis_lo_${V}_${W}_20261109.log 2> mantis_lo_${V}_${W}_20261109.err.log < /dev/null &
echo queued_${V}_${W}"
