#!/usr/bin/env bash
set -Eeuo pipefail
cd /workspace/CD3
for i in $(seq 1 10080); do
  if grep -q 'ALL MOMENT V0 V5 COMPLETE' /workspace/CD3/moment_queue_20261105.log; then break; fi
  status=$(supervisorctl status cd3_moment_v0_v5_20261105 || true)
  case "$status" in *FATAL*|*EXITED*) echo 'MOMENT train did not complete; test cache retained' >&2;exit 1;; esac
  sleep 60
done
grep -q 'ALL MOMENT V0 V5 COMPLETE' /workspace/CD3/moment_queue_20261105.log
export PYTHONPATH=/workspace/CD3/moment_code_20261105
for version in v5 v0; do
  export MOMENT_ROOT=/workspace/CD3/moment_${version}_20261105
  /workspace/CD3/moment_venv_20261105/bin/python -u /workspace/CD3/moment_test_cache_20261105.py
  test -f "$MOMENT_ROOT/TEST_CACHE_COMPLETE"
done
touch /workspace/CD3/moment_v0_v5_test_cache_complete_20261105
