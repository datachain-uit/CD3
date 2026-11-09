#!/bin/sh
# usage: up_lo_parent_w.sh <port> <host> <V> <W>   (code + script + ONE window of data)
P=$1; H=$2; V=$3; W=$4
S=/d/Source_code/myself/downloads/vastai/LO_V3_1_clean_grain_seed42
K="-i /c/Users/manndm/.ssh/id_vastai"
SSH="ssh $K -p $P root@$H"; SCP="scp -q $K -P $P"
$SSH "mkdir -p /workspace/CD3/lo_mantis_data/train/$W/$V /workspace/CD3/lo_mantis_data/evaluation/$W/$V" >/dev/null 2>&1
$SCP /tmp/w/mantis_lo_code_20261109.tar /tmp/w/lo_mantis_parent.sh root@$H:/workspace/CD3/ || exit 1
$SCP $S/download_manifest.json root@$H:/workspace/CD3/lo_mantis_data/ || exit 1
$SCP $S/train/$W/$V/train.parquet root@$H:/workspace/CD3/lo_mantis_data/train/$W/$V/ || exit 1
$SCP $S/evaluation/$W/$V/*.parquet root@$H:/workspace/CD3/lo_mantis_data/evaluation/$W/$V/ || exit 1
echo "LO $V $W data uploaded to $P"
