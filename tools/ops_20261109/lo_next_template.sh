#!/bin/bash
# waits until the host has no other training job for 3 minutes, then runs one LO Mantis parent window
cd /workspace/CD3
# one waiter at a time per host: the lock is held until the whole window has run
exec 9>/workspace/CD3/lo_queue.lock
flock 9
quiet=0
while [ $quiet -lt 3 ]; do
  if ps -eo args | grep -E 'run_mantis_grid_zstd|run_mantis_cq_grid|lo_mantis_parent.sh|pkg_w1_|mantis_child_w23|run_lo_|run_v12w3|vastai_train_shared' | grep -v lo_next_ | grep -v grep >/dev/null; then quiet=0; else quiet=$((quiet+1)); fi
  sleep 60
done
echo QUEUE_GATE_PASSED $(date -Is)
LDD='@LDD@'
if [ -n "$LDD" ]; then export LD_LIBRARY_PATH="$LDD/usr/local/cuda-13.0/compat:$LD_LIBRARY_PATH"; fi
rm -rf mantis_lo_@V@_20261109
ENVROOT=@ENVR@ bash lo_mantis_parent.sh @V@ "@W@"
