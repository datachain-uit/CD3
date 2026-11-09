#!/usr/bin/env bash
set -Eeuo pipefail
cd /workspace/CD3
for i in $(seq 1 10080); do
  if test -f moment_v1_20261105/ALL_WINDOWS_COMPLETE; then break; fi
  status=$(supervisorctl status cd3_moment_v1_20261105 || true)
  case "$status" in *FATAL*|*EXITED*) echo 'V1 did not complete; test cache will not run' >&2;exit 1;; esac
  sleep 60
done
test -f moment_v1_20261105/ALL_WINDOWS_COMPLETE
export LD_LIBRARY_PATH="/usr/local/cuda-13.0/compat${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PYTHONPATH=/workspace/CD3/moment_code_20261105
/workspace/CD3/moment_v1_venv_20261105/bin/python -u /workspace/CD3/moment_v1_20261105/build_test_cache.py
