#!/bin/sh
# usage: upload_cq_family.sh <port> <host> <up_dir> V...
P=$1; H=$2; U=$3; shift 3
S=/d/Source_code/myself/downloads/vastai/CQ_V2_2_clean_grain_seed42/train
for V in "$@"; do
  for W in W1 W2 W3; do
    ssh -i ~/.ssh/id_vastai -p $P root@$H "mkdir -p $U/train/$W/$V" >/dev/null 2>&1
    scp -q -i ~/.ssh/id_vastai -P $P $S/$W/$V/balanced_train.parquet root@$H:$U/train/$W/$V/balanced_train.parquet || exit 1
  done
  ssh -i ~/.ssh/id_vastai -p $P root@$H "touch $U/$V.READY" >/dev/null 2>&1
  echo "$V uploaded $(date -u +%T)"
done
