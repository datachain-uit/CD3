#!/usr/bin/env bash
set -Eeuo pipefail
cd /workspace/CD3
test -f moment_inputs_verified_20261105
test -f moment_environment_ready_20261105
export PYTHONPATH=/workspace/CD3/moment_code_20261105
for version in v5 v0; do
  for window in w1 w2 w3; do
    root="/workspace/CD3/moment_${version}_20261105/results/$window"
    if test -d "$root" && test -n "$(find "$root" -name COMPLETE -type f -print -quit)"; then
      echo "SKIP verified complete $version $window";continue
    fi
    available=$(df -Pk /workspace | awk 'NR==2 {print $4}')
    test "$available" -gt 1048576 || { echo 'Insufficient disk; instance retained' >&2;exit 1; }
    echo "RESUME $version $window $(date -u -Is)"
    /workspace/CD3/moment_venv_20261105/bin/python -u "/workspace/CD3/moment_${version}_20261105/run_${window}.py"
  done
done
echo "ALL MOMENT V0 V5 COMPLETE $(date -u -Is)"
