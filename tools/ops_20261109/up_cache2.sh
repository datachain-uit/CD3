#!/bin/bash
# like up_cache.sh but keeps rclone stderr, verifies the object exists afterwards and retries once
P=$1; H=$2; ROOT=$3; PAR=$4; W=$5
RC="rclone --drive-root-folder-id 1GWiedVROrxp8jvGbd0xmvVmWriZUkpOn"
D=gdrive:CQ/L1_runs/S3_model/caches/mantis_v2_seed42_exploratory_20261108/parent_caches_20261109/$PAR
NAME=parent_cache_${PAR}_${W}_20261109.tar
cd /d/Source_code/myself/upload_staging/cache_bk
for try in 1 2; do
  ssh -i ~/.ssh/id_vastai -p $P root@$H "tar -C $ROOT -cf - task=CQ/window=$W/imputer=$PAR" 2>>$NAME.err \
    | tee >(md5sum | cut -c1-32 > $NAME.md5) >(sha256sum | cut -c1-64 > $NAME.sha256) \
    | $RC rcat -v $D/$NAME 2>>$NAME.err
  sleep 3
  DM=$($RC md5sum $D/$NAME 2>>$NAME.err | cut -c1-32)
  if [ -n "$DM" ] && [ "$DM" = "$(cat $NAME.md5)" ]; then break; fi
  echo "try $try failed (drive_md5='$DM' local='$(cat $NAME.md5)')" >> $NAME.err
done
echo "$NAME local_md5=$(cat $NAME.md5) drive_md5=$DM sha256=$(cat $NAME.sha256)" > $NAME.done2
