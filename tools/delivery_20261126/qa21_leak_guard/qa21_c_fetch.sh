#!/bin/bash
# QA21 phan 5: tai (chi doc) fitted_pipeline.joblib + sha256.json + duoi (footer) cua model_inputs/train.parquet cua 12 trang thai S1 dung imputer co predictor (V9 extra_trees, V13 mice).
# Moi trang thai vao thu muc rieng; 1 luong; khong ghi len Drive.
export MSYS_NO_PATHCONV=1
OUT=${QA21_DL:?thu muc tai ve (rieng, khong tin cay)}
SRC=${QA5M_SRC:?thu muc qa5m/src chua manifest S1}
R="rclone --drive-root-folder-id 1GWiedVROrxp8jvGbd0xmvVmWriZUkpOn --transfers 1 --checkers 1"
for t in CQ LO; do for w in W1 W2 W3; do for v in V9 V13; do
  a=$(ls $SRC/S1_$t/$w/$v)
  d=$OUT/${t}_${w}_${v}; mkdir -p "$d"
  base="gdrive:$t/L1_runs/S1_imputation/complete_seed20260922/$w/$v/$a"
  [ -s "$d/fitted_pipeline.joblib" ] || $R copyto "$base/fitted_preprocessors/fitted_pipeline.joblib" "$d/fitted_pipeline.joblib"
  $R copyto "$base/fitted_preprocessors/sha256.json" "$d/sha256.json"
  # footer: 3 MB cuoi cua train.parquet
  sz=$($R lsl "$base/model_inputs/train.parquet" | awk '{print $1}')
  off=$((sz-3000000)); [ $off -lt 0 ] && off=0
  $R cat --offset $off "$base/model_inputs/train.parquet" > "$d/train_tail.bin"
  echo "$t $w $v $a size=$sz offset=$off" >> "$OUT/fetch.log"
done; done; done
echo DONE >> "$OUT/fetch.log"
