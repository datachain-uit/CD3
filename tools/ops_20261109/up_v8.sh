#!/bin/sh
# usage: up_v8.sh <port> <host> <W>   uploads V5 parent data + V5 adapter + V8 balanced for one window and marks V8.READY
P=$1; H=$2; W=$3
S=/d/Source_code/myself/downloads/vastai/CQ_V2_2_clean_grain_seed42
A=/d/Source_code/myself/upload_staging/adapters/V5/$W
SSH="ssh -i /c/Users/manndm/.ssh/id_vastai -p $P root@$H"
SCP="scp -q -i /c/Users/manndm/.ssh/id_vastai -P $P"
$SSH "mkdir -p /workspace/CD3/up_par5/train/$W/V5 /workspace/CD3/up_par5/evaluation/$W/V5 /workspace/CD3/par5_cache/task=CQ/window=$W/imputer=V5 /workspace/CD3/up_cq/train/$W/V8" >/dev/null 2>&1
$SCP $S/download_manifest.json root@$H:/workspace/CD3/up_par5/ || exit 1
$SCP $S/train/$W/V5/train.parquet root@$H:/workspace/CD3/up_par5/train/$W/V5/ || exit 1
$SCP $S/evaluation/$W/V5/*.parquet root@$H:/workspace/CD3/up_par5/evaluation/$W/V5/ || exit 1
$SCP $A/channel_adapter.* root@$H:/workspace/CD3/par5_cache/task=CQ/window=$W/imputer=V5/ || exit 1
$SCP $S/train/$W/V8/balanced_train.parquet root@$H:/workspace/CD3/up_cq/train/$W/V8/ || exit 1
$SSH "touch /workspace/CD3/up_cq/V8.READY" >/dev/null 2>&1
echo "V8 $W uploaded to $P"
