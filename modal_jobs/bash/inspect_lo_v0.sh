#!/usr/bin/env bash
# Print compact Modal status for the three sequential LO V0 imputation runs.
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
python_bin="${PYTHON_BIN:-$project_root/.venv/bin/python}"

[[ -x "$python_bin" ]] || { echo "Modal Python not found: $python_bin" >&2; exit 1; }
exec "$python_bin" -X utf8 -m modal run "$project_root/modal_jobs/inspect_lo_v0.py"
