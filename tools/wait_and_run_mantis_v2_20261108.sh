#!/usr/bin/env bash
set -Eeuo pipefail
BASE=/workspace/CD3
PART="$BASE/mantis_v2_cq_inputs.tar.partial"
READY="$BASE/mantis_v2_cq_inputs.tar"
EXPECTED=1239582720
for unused in $(seq 1 4320); do
  if test -f "$PART" && test "$(stat -c %s "$PART")" -eq "$EXPECTED"; then
    if echo "fff1287792c4d1e427d3cb3d9295ae72c7c49bda5233766a65cca39010346f27  $PART" | sha256sum -c -; then
      mv "$PART" "$READY"
      exec bash "$BASE/run_mantis_v2_independent_20261108.sh"
    fi
  fi
  sleep 10
done
echo 'INPUT_TRANSFER_TIMEOUT' >&2
exit 1
