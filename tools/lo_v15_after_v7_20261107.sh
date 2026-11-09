#!/usr/bin/env bash
set -Eeuo pipefail
BASE=/workspace/CD3
STATE="$BASE/runs/lo_v7_w3_closure_20261107"
DATA="$BASE/data/LO_V3_1_clean_grain_seed42"
echo "QUEUE_WAITING_FOR_V7 $(date -Is)"
for i in $(seq 1 10080); do
  if test -e "$STATE/FAILED"; then echo 'V7_FAILED_NOT_STARTING_V15'; exit 1; fi
  if test -e "$STATE/BUNDLE_READY"; then break; fi
  sleep 30
done
test -e "$STATE/BUNDLE_READY"
sha256sum -c "$STATE/bundle.sha256"
echo "V7_ARCHIVE_VERIFIED $(date -Is)"
INPUT="$BASE/lo_v15_input_20261107.tar"
for i in $(seq 1 2160); do
  if test -f "$INPUT" && test "$(stat -c %s "$INPUT")" -eq 1075936768; then break; fi
  sleep 10
done
test -f "$INPUT" && test "$(stat -c %s "$INPUT")" -eq 1075936768
echo 'c4c35c74aad84c2a530e35e1d69cf86d10283bf1f85f9ea7aa43fb35dfba0d6f  /workspace/CD3/lo_v15_input_20261107.tar' | sha256sum -c -
tar -xf "$INPUT" -C "$DATA"
if test ! -e "$BASE/lo_patchtst_seed42_code"; then ln -s "$BASE/lo_v7_code" "$BASE/lo_patchtst_seed42_code"; fi
if test ! -e "$BASE/lo_static_v2_prediction_salt"; then ln -s "$BASE/lo_grid_prediction_salt" "$BASE/lo_static_v2_prediction_salt"; fi
echo "QUEUE_STARTED V15 $(date -Is)"
exec bash "$BASE/lo_patch_resume_credit_20261107.sh" V15
