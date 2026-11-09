#!/usr/bin/env bash
set -Eeuo pipefail
BASE=/workspace/CD3
CODE="$BASE/mantis_v0_code_20261107.tar"
DATA="$BASE/mantis_v0_cq_w1_input_20261107.tar"
echo "WAIT_INPUT_STARTED $(date -Is)"
for i in $(seq 1 720); do
  if test -f "$DATA" && test "$(stat -c %s "$DATA")" -eq 98334208; then
    echo 'a2f731cd3f33eab7fe0c88dbe4a5fbe9a84fdeda2677c979e24d9ca19ace5f25  /workspace/CD3/mantis_v0_code_20261107.tar' | sha256sum -c -
    echo '41150d0099d14eae5f0cf78518991c2fcc9083ebd31fbcf8b075a68dcd052753  /workspace/CD3/mantis_v0_cq_w1_input_20261107.tar' | sha256sum -c -
    echo "INPUT_HASH_PASS $(date -Is)"
    exec bash "$BASE/mantis_cq_v0_w1_vast_44016_20261107.sh"
  fi
  sleep 10
done
echo 'INPUT_TRANSFER_TIMEOUT'
exit 1
