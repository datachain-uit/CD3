#!/bin/bash
# usage: up_cache.sh <port> <host> <remote_cache_root> <parent> <window>
# streams one level-A cache window (cache/task=CQ/window=W/imputer=P) from a Vast host to Drive; records MD5 + SHA-256 of the stream
P=$1; H=$2; ROOT=$3; PAR=$4; W=$5
RC="rclone --drive-root-folder-id 1GWiedVROrxp8jvGbd0xmvVmWriZUkpOn"
D=gdrive:CQ/L1_runs/S3_model/caches/mantis_v2_seed42_exploratory_20261108/parent_caches_20261109/$PAR
NAME=parent_cache_${PAR}_${W}_20261109.tar
cd /d/Source_code/myself/upload_staging/cache_bk
BYTES=$(ssh -i ~/.ssh/id_vastai -p $P root@$H "du -sb $ROOT/task=CQ/window=$W/imputer=$PAR | cut -f1" 2>/dev/null | tail -1)
ssh -i ~/.ssh/id_vastai -p $P root@$H "tar -C $ROOT -cf - task=CQ/window=$W/imputer=$PAR" 2>/dev/null \
  | tee >(md5sum | cut -c1-32 > $NAME.md5) >(sha256sum | cut -c1-64 > $NAME.sha256) \
  | $RC rcat $D/$NAME
sleep 2
echo "$NAME dir_bytes=$BYTES local_md5=$(cat $NAME.md5) drive_md5=$($RC md5sum $D/$NAME | cut -c1-32) sha256=$(cat $NAME.sha256) drive_size=$($RC size --json $D/$NAME 2>/dev/null | grep -o '"bytes":[0-9]*')" > $NAME.done
