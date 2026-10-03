#!/usr/bin/env bash
# Upload and run the LO V3.1 release in dependency order on Modal.
#
# Usage:
#   bash modal_jobs/run_lo_sequential.sh upload
#   bash modal_jobs/run_lo_sequential.sh s0
#   bash modal_jobs/run_lo_sequential.sh impute-v0
#   bash modal_jobs/run_lo_sequential.sh impute
#   bash modal_jobs/run_lo_sequential.sh model-pilot
#
# Run one stage at a time. Each Modal invocation is synchronous, so this
# runner never fans out LO windows or imputation variants concurrently.
set -euo pipefail

stage="${1:-}"
if [[ ! "$stage" =~ ^(upload|s0|impute-v0|impute|model-pilot)$ ]]; then
  echo "Usage: $0 {upload|s0|impute-v0|impute|model-pilot}" >&2
  exit 2
fi

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
python_bin="${PYTHON_BIN:-$project_root/.venv/bin/python}"
modal_volume="${MODAL_VOLUME:-tempo-data-v1}"
input_root="/input/LO_v3_1"
phase_source="$project_root/LO/resuilt/phase_views_v3_1_scored_signal_excluded/phase_views_v3_1_scored_signal_excluded"
test_source="$project_root/LO/resuilt/test_prefix_views_v3_1_scored_signal_excluded/test_prefix_views_v3_1_scored_signal_excluded"

if [[ ! -x "$python_bin" ]]; then
  echo "Modal Python not found: $python_bin" >&2
  exit 1
fi

modal_run() {
  "$python_bin" -X utf8 -m modal run "$@"
}

case "$stage" in
  upload)
    [[ -d "$phase_source" ]] || { echo "Missing extracted artifact: $phase_source" >&2; exit 1; }
    [[ -f "$phase_source/_SUCCESS" ]] || { echo "Phase view is incomplete (missing _SUCCESS)" >&2; exit 1; }
    [[ -d "$test_source" ]] || { echo "Missing extracted artifact: $test_source" >&2; exit 1; }
    for phase in P1 P2 P3 P4; do
      [[ -f "$test_source/$phase/_SUCCESS" ]] ||
        { echo "Test prefix is incomplete (missing $phase/_SUCCESS)" >&2; exit 1; }
    done
    "$python_bin" -m modal volume put --force "$modal_volume" "$phase_source" "$input_root/"
    "$python_bin" -m modal volume put --force "$modal_volume" "$test_source" "$input_root/"
    "$python_bin" -m modal volume put --force "$modal_volume" \
      "$project_root/modal_jobs/lo_v3_1_release_manifest.json" \
      "$input_root/release_manifest.json"
    ;;
  s0)
    modal_run "$project_root/modal_jobs/imputation_app.py" --mode s0 --task LO --seed 20260922
    ;;
  impute-v0)
    for window in W1 W2 W3; do
      modal_run "$project_root/modal_jobs/imputation_app.py" \
        --mode impute --task LO --window "$window" --test-phase ALL \
        --variant v0 --seed 20260922
    done
    ;;
  impute)
    for window in W1 W2 W3; do
      for variant in median mean extra_trees mice; do
        modal_run "$project_root/modal_jobs/imputation_app.py" \
          --mode impute --task LO --window "$window" --test-phase ALL \
          --variant "$variant" --seed 20260922
      done
    done
    ;;
  model-pilot)
    for window in W1 W2 W3; do
      modal_run "$project_root/modal_jobs/model_app.py" \
        --task LO --window "$window" --pipeline-id V0 --model-name RNN \
        --seed 42 --split-version v3_1 --phase-version wide_prefix_v3_1
      modal_run "$project_root/modal_jobs/model_sanity_app.py" \
        --task LO --window "$window" --pipeline-id V0 --model-name RNN \
        --seed 42 --split-version v3_1 --phase-version wide_prefix_v3_1
    done
    ;;
esac
