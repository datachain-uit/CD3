#!/bin/bash
# usage: start_waiter.sh <port> <host> <V> <W> <ENVROOT> [LD_DIR]
P=$1; H=$2; V=$3; W=$4; ENVR=$5; LDD=$6
sed -e "s|@V@|$V|g" -e "s|@W@|$W|g" -e "s|@ENVR@|$ENVR|g" -e "s|@LDD@|$LDD|g" /tmp/w/lo_next_template.sh > /tmp/w/lo_next_${V}_${W}.sh
scp -q -i ~/.ssh/id_vastai -P $P /tmp/w/lo_next_${V}_${W}.sh root@$H:/workspace/CD3/ || exit 1
ssh -o ConnectTimeout=15 -i ~/.ssh/id_vastai -p $P root@$H "cd /workspace/CD3; bash -n lo_next_${V}_${W}.sh || exit 2; nohup bash lo_next_${V}_${W}.sh > mantis_lo_${V}_${W}_20261109.log 2> mantis_lo_${V}_${W}_20261109.err.log < /dev/null &
echo started_${V}_${W}"
