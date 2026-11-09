#!/usr/bin/env bash
set -Eeuo pipefail
cd /workspace/CD3
for attempt in $(seq 1 360); do
  ready=1
  test -f V12_ENV_READY || ready=0
  for window in W1 W2 W3; do
    test -f "data/CQ_V2_2_clean_grain_seed42/train/$window/V12/balanced_train.parquet" || ready=0
    test -f "data/CQ_V2_2_clean_grain_seed42/train/$window/V9/train.parquet" || ready=0
    test -f "data/CQ_V2_2_clean_grain_seed42/evaluation/$window/V9/validation.parquet" || ready=0
    for phase in P1 P2 P3 P4; do test -f "data/CQ_V2_2_clean_grain_seed42/evaluation/$window/V9/test_${phase}.parquet" || ready=0; done
  done
  if test "$ready" -eq 1; then exec /bin/bash tools/run_cq_patchtst_v12_seed42.sh; fi
  echo "WAIT V12 environment and verified inputs attempt=$attempt"
  sleep 60
done
echo 'V12 preflight timed out' >&2
exit 1
