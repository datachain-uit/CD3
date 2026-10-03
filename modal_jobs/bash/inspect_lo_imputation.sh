#!/usr/bin/env bash
# Read concise LO imputation status for one or more variants.
#
# Examples:
#   bash modal_jobs/bash/inspect_lo_imputation.sh median,mean
#   bash modal_jobs/bash/inspect_lo_imputation.sh all
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
python_bin="${PYTHON_BIN:-$project_root/.venv/bin/python}"
variants="${1:-v0}"

[[ -x "$python_bin" ]] || { echo "Modal Python not found: $python_bin" >&2; exit 1; }
exec "$python_bin" -X utf8 -m modal run "$project_root/modal_jobs/inspect_lo_imputation.py" --variants "$variants"
