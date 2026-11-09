#!/bin/bash
# usage: launch_lo_win.sh <port> <host> <V> <WINDOW> <ENVROOT> [LD_DIR]   (data + code upload, then start the driver for ONE window)
P=$1; H=$2; V=$3; W=$4; ENVR=$5; LDD=$6
/tmp/w/up_lo_parent.sh $P $H $V || exit 1
ssh -o ConnectTimeout=15 -i ~/.ssh/id_vastai -p $P root@$H "cd /workspace/CD3; rm -rf mantis_lo_${V}_20261109; cat > run_lo_${V}_${W}.sh <<EOS
cd /workspace/CD3
[ -n \"$LDD\" ] && export LD_LIBRARY_PATH=\"$LDD/usr/local/cuda-13.0/compat:\\$LD_LIBRARY_PATH\"
ENVROOT=$ENVR bash lo_mantis_parent.sh $V \"$W\"
EOS
nohup bash run_lo_${V}_${W}.sh > mantis_lo_${V}_${W}_20261109.log 2> mantis_lo_${V}_${W}_20261109.err.log < /dev/null &
echo started_$V_$W"
