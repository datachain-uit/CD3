#!/usr/bin/env bash
set -Eeuo pipefail
cd /workspace/CD3
for i in $(seq 1 360); do
  if test -f moment_v1_inputs_verified_20261105 && test -f moment_v1_environment_ready_20261105 && test -f moment_v1_donor_verified_20261105; then break; fi
  echo "WAIT V1 input/environment/donor $i"; sleep 60
done
test -f moment_v1_inputs_verified_20261105
test -f moment_v1_environment_ready_20261105
test -f moment_v1_donor_verified_20261105
export LD_LIBRARY_PATH="/usr/local/cuda-13.0/compat${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PYTHONPATH=/workspace/CD3/moment_code_20261105
for window in w1 w2 w3; do
  available=$(df -Pk /workspace | awk 'NR==2 {print $4}')
  test "$available" -gt 1048576 || { echo 'Insufficient disk; instance retained';exit 1; }
  echo "START V1 $window $(date -u -Is)"
  moment_v1_venv_20261105/bin/python -u "/workspace/CD3/moment_v1_20261105/run_${window}.py"
done
touch /workspace/CD3/moment_v1_20261105/ALL_WINDOWS_COMPLETE
