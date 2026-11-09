#!/usr/bin/env bash
set -Eeuo pipefail
cd /workspace/CD3
export LD_LIBRARY_PATH="/usr/local/cuda-13.0/compat${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PYTHONPATH=/workspace/CD3/moment_code_20261105
moment_venv_20261105/bin/python -c 'import torch,momentfm; assert torch.cuda.is_available()'
for window in w1 w2 w3; do
  root="/workspace/CD3/moment_v9_20261105/results/$window"
  if test -d "$root" && test -n "$(find "$root" -name COMPLETE -type f -print -quit)"; then echo "SKIP complete V9 $window";continue;fi
  available=$(df -Pk /workspace | awk 'NR==2 {print $4}')
  test "$available" -gt 1048576 || { echo 'Insufficient disk; instance retained' >&2;exit 1; }
  echo "RESUME V9 $window $(date -u -Is)"
  moment_venv_20261105/bin/python -u "/workspace/CD3/moment_v9_20261105/run_${window}.py"
done
export MOMENT_ROOT=/workspace/CD3/moment_v9_20261105
moment_venv_20261105/bin/python -u /workspace/CD3/moment_v9_20261105/build_test_cache.py
test -f /workspace/CD3/moment_v9_20261105/TEST_CACHE_COMPLETE
touch /workspace/CD3/moment_v9_20261105/ALL_WINDOWS_COMPLETE
