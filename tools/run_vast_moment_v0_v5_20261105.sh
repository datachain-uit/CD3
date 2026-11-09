#!/usr/bin/env bash
set -Eeuo pipefail
cd /workspace/CD3
for i in $(seq 1 360); do
  if test -f moment_inputs_verified_20261105 && test -f moment_environment_ready_20261105; then break; fi
  echo "WAIT input/environment $i";sleep 60
done
test -f moment_inputs_verified_20261105
test -f moment_environment_ready_20261105
export PYTHONPATH=/workspace/CD3/moment_code_20261105
for version in v5 v0; do
  for window in w1 w2 w3; do
    available=$(df -Pk /workspace | awk 'NR==2 {print $4}')
    test "$available" -gt 1048576 || { echo 'Insufficient disk: retaining data and pausing';exit 1; }
    echo "START ${version} ${window} $(date -u -Is)"
    /workspace/CD3/moment_venv_20261105/bin/python -u "/workspace/CD3/moment_${version}_20261105/run_${window}.py"
  done
done
echo "ALL MOMENT V0 V5 COMPLETE $(date -u -Is)"
