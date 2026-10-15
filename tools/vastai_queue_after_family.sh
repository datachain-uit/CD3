#!/usr/bin/env bash
# Wait for a complete prior family, then start the next one without GPU overlap.
set -euo pipefail

task="${1:?task is required}"
prior_root="${2:?prior root is required}"
data_root="${3:?data root is required}"
next_root="${4:?next root is required}"
next_model="${5:?next model is required}"
min_free_gb="${6:?minimum free GB is required}"

cd /workspace/CD3
while true; do
  completed=$(find "$prior_root/$task" -name run_manifest.json 2>/dev/null | wc -l)
  free_gb=$(df -Pk /workspace | awk 'NR==2 {print int($4 / 1024 / 1024)}')
  printf '[%s] prerequisite=%s/51; free=%sGB; required=%sGB\n' \
    "$(date -Is)" "$completed" "$free_gb" "$min_free_gb"
  if [ "$completed" -eq 51 ] && [ "$free_gb" -ge "$min_free_gb" ]; then
    exec bash code/vastai_run_family.sh "$task" "$data_root" "$next_root" "$next_model" "$min_free_gb"
  fi
  sleep 120
done
