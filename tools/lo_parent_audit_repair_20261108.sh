#!/usr/bin/env bash
set -Eeuo pipefail
PARENT="$1"
BASE=/workspace/CD3
DATA="$BASE/data/LO_V3_1_clean_grain_seed42"
FILE="$BASE/lo_parent_${PARENT}_20261108.tar"
if test "$PARENT" = V5; then SIZE=265625600; HASH=97e87997fb2962953b96dbba20364c89728256d879bd0a06baa4ddc2e245d88c
elif test "$PARENT" = V9; then SIZE=268987392; HASH=12be966e0285a228deb4ac14e0a3f60bd7fa4626b1d3b11d82335ce642fe4b7a
else exit 1; fi
echo "WAIT_PARENT $PARENT $(date -Is)"
for i in $(seq 1 2160); do
  if test -f "$FILE" && test "$(stat -c %s "$FILE")" -eq "$SIZE"; then break; fi
  sleep 10
done
test -f "$FILE" && test "$(stat -c %s "$FILE")" -eq "$SIZE"
echo "$HASH  $FILE" | sha256sum -c -
for W in W1 W2 W3; do test ! -e "$DATA/train/$W/$PARENT/train.parquet"; done
tar -xf "$FILE" -C "$DATA"
echo "PARENT_READY $PARENT $(date -Is)"
if test "$PARENT" = V9; then
  export LO_PY_ENV=/workspace/cuda13_probe/venv
  export LD_LIBRARY_PATH=/workspace/cuda13_probe/extracted/usr/local/cuda-13.0/compat
  export LO_RESUME_SUFFIX=_cuda13_auditfix
  exec bash "$BASE/lo_patchtst_seed42_code/resume_credit_20261107.sh" V10
fi
