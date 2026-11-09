#!/bin/sh
# usage: fetch_up_m.sh <port> <host> <remote_path> <drive_subdir>
RC="rclone --drive-root-folder-id 1GWiedVROrxp8jvGbd0xmvVmWriZUkpOn"
D=gdrive:CQ/L1_runs/S3_model/staging_incoming/mantis_v2_seed42_exploratory_20261108
cd /d/Source_code/myself/upload_staging/mantis_bk
f=$(basename "$3")
scp -q -i ~/.ssh/id_vastai -P "$1" "root@$2:$3" "$f" || exit 1
scp -q -i ~/.ssh/id_vastai -P "$1" "root@$2:$3.sha256" "$f.remote.sha256" 2>/dev/null
$RC copyto "$f" "$D/$4/$f" && echo "$f md5 local $(md5sum $f | cut -c1-32) drive $($RC md5sum $D/$4/$f | cut -c1-32) sha_local $(sha256sum $f | cut -c1-16) sha_remote $(cut -c1-16 $f.remote.sha256 2>/dev/null)" > "$f.up.done"
