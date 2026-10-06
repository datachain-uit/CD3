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
# The uploader consumes a caller-provided extracted release rather than an
# analyst-specific results path.  Defaults match the WSL staging instructions;
# set LO_ARTIFACT_ROOT, LO_PHASE_SOURCE, or LO_TEST_SOURCE when stored elsewhere.
artifact_root="${LO_ARTIFACT_ROOT:-$project_root/upload_staging/LO}"
phase_source="${LO_PHASE_SOURCE:-$artifact_root/phase_views_v3_1_scored_signal_excluded}"
test_source="${LO_TEST_SOURCE:-$artifact_root/test_prefix_views_v3_1_scored_signal_excluded}"

if [[ ! -x "$python_bin" ]]; then
  echo "Modal Python not found: $python_bin" >&2
  exit 1
fi

modal_run() {
  "$python_bin" -X utf8 -m modal run "$@"
}

replace_remote_directory() {
  local source="$1"
  local destination="$2"
  # ``volume put --force`` can retain obsolete Parquet parts. Clear only this
  # release-owned input directory; never touch meta_release.
  if "$python_bin" -m modal volume ls "$modal_volume" "$destination" >/dev/null 2>&1; then
    "$python_bin" -m modal volume rm --recursive "$modal_volume" "$destination"
  fi
  "$python_bin" -m modal volume put --force "$modal_volume" "$source" "$(dirname "$destination")/"
}

case "$stage" in
  upload)
    [[ -d "$phase_source" ]] || { echo "Missing extracted artifact: $phase_source" >&2; exit 1; }
    compgen -G "$phase_source/*.parquet" >/dev/null ||
      { echo "Phase view has no Parquet data: $phase_source" >&2; exit 1; }
    [[ -d "$test_source" ]] || { echo "Missing extracted artifact: $test_source" >&2; exit 1; }
    for phase in P1 P2 P3 P4; do
      compgen -G "$test_source/$phase/*.parquet" >/dev/null ||
        { echo "Test prefix has no Parquet data: $test_source/$phase" >&2; exit 1; }
    done
    replace_remote_directory "$phase_source" "$input_root/phase_views_v3_1_scored_signal_excluded"
    replace_remote_directory "$test_source" "$input_root/test_prefix_views_v3_1_scored_signal_excluded"
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
