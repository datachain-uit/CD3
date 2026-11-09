#!/bin/sh
# usage: fetch_up.sh <port> <host> <remote_path> <drive_subdir>
RC="rclone --drive-root-folder-id 1GWiedVROrxp8jvGbd0xmvVmWriZUkpOn"
D=gdrive:LO/L1_runs/S3_model/staging_incoming/patchtst_seed42_after_credit_20261108
cd /d/Source_code/myself/upload_staging/lo_bk
f=$(basename "$3")
[ -n "$FETCH" ] && scp -q -i ~/.ssh/id_vastai -P "$1" "root@$2:$3" "$f"
sha256sum "$f" > "$f.local.sha256"
$RC copyto "$f" "$D/$4/$f" && echo "$f md5 local $(md5sum $f | cut -c1-32) drive $($RC md5sum $D/$4/$f | cut -c1-32)" > "$f.up.done"
