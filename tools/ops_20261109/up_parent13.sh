#!/bin/sh
# usage: up_parent13.sh <port> <host> <dest_root> W...   (V13 parent data + adapters for the given windows)
P=$1; H=$2; R=$3; shift 3
S=/d/Source_code/myself/downloads/vastai/CQ_V2_2_clean_grain_seed42
ssh -i ~/.ssh/id_vastai -p $P root@$H "mkdir -p $R" >/dev/null 2>&1
scp -q -i ~/.ssh/id_vastai -P $P $S/download_manifest.json root@$H:$R/download_manifest.json
for W in "$@"; do
  ssh -i ~/.ssh/id_vastai -p $P root@$H "mkdir -p $R/train/$W/V13 $R/evaluation/$W/V13 /workspace/CD3/par13_cache/task=CQ/window=$W/imputer=V13" >/dev/null 2>&1
  scp -q -i ~/.ssh/id_vastai -P $P $S/train/$W/V13/train.parquet root@$H:$R/train/$W/V13/ || exit 1
  scp -q -i ~/.ssh/id_vastai -P $P $S/evaluation/$W/V13/*.parquet root@$H:$R/evaluation/$W/V13/ || exit 1
  ls /tmp/w/ad13/$W/channel_adapter.* >/dev/null 2>&1 && scp -q -i ~/.ssh/id_vastai -P $P /tmp/w/ad13/$W/channel_adapter.* root@$H:/workspace/CD3/par13_cache/task=CQ/window=$W/imputer=V13/
done
echo "parent13 uploaded $P $*"
