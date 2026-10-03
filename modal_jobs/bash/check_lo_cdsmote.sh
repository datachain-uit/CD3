#!/usr/bin/env bash
# Check LO CDSMOTE outputs V2/V6/V10/V14 for W1-W3.
#
# Default: manifest status only (fast).
# Full page-level Parquet validation: bash modal_jobs/bash/check_lo_cdsmote.sh full
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
python_bin="${PYTHON_BIN:-$project_root/.venv/bin/python}"
check_mode="${1:-status}"

[[ -x "$python_bin" ]] || { echo "Modal Python not found: $python_bin" >&2; exit 1; }
case "$check_mode" in
  status) mode="status_all_windows" ;;
  full) mode="inspect_all_windows" ;;
  *) echo "Usage: $0 [status|full]" >&2; exit 2 ;;
esac

exec "$python_bin" -X utf8 -m modal run "$project_root/modal_jobs/augmentation_app.py" \
  --mode "$mode" --task LO --balance-pipelines V2,V6,V10,V14 --seed 42
