#!/bin/sh
# usage: up_lo_parent.sh <port> <host> <V>
P=$1; H=$2; V=$3
S=/d/Source_code/myself/downloads/vastai/LO_V3_1_clean_grain_seed42
K="-i /c/Users/manndm/.ssh/id_vastai"
SSH="ssh $K -p $P root@$H"; SCP="scp -q $K -P $P"
$SSH "mkdir -p /workspace/CD3/lo_mantis_data/train/W1/$V /workspace/CD3/lo_mantis_data/train/W2/$V /workspace/CD3/lo_mantis_data/train/W3/$V /workspace/CD3/lo_mantis_data/evaluation/W1/$V /workspace/CD3/lo_mantis_data/evaluation/W2/$V /workspace/CD3/lo_mantis_data/evaluation/W3/$V" >/dev/null 2>&1
$SCP /tmp/w/mantis_lo_code_20261109.tar /tmp/w/lo_mantis_parent.sh root@$H:/workspace/CD3/ || exit 1
$SCP $S/download_manifest.json root@$H:/workspace/CD3/lo_mantis_data/ || exit 1
for W in W1 W2 W3; do
  $SCP $S/train/$W/$V/train.parquet root@$H:/workspace/CD3/lo_mantis_data/train/$W/$V/ || exit 1
  $SCP $S/evaluation/$W/$V/*.parquet root@$H:/workspace/CD3/lo_mantis_data/evaluation/$W/$V/ || exit 1
done
echo "LO $V data uploaded to $P"
