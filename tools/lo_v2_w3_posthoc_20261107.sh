#!/usr/bin/env bash
set -Eeuo pipefail
CODE=/workspace/CD3/lo_patchtst_seed42_code
DATA=/workspace/CD3/data/LO_V3_1_clean_grain_seed42
RUNS=/workspace/CD3/runs/lo_patchtst_seed42
RUN="$RUNS/LO/W3/V2/PATCHTST/seed=42"
AUDIT=/workspace/CD3/runs/lo_patchtst_v2_w3_audit_20261107
BUNDLE=/workspace/CD3/runs/lo_patchtst_v2_w3_20261107.tar.gz
STATE=/workspace/CD3/runs/lo_patchtst_v2_w3_posthoc_20261107
mkdir -p "$STATE"
source /venv/main/bin/activate
cd "$CODE"
echo "WAITING_FOR_TRAIN $(date -Is)"
while true; do
  status=$(supervisorctl status lo_patchtst_v2_w3_20261107 || true)
  echo "$status"
  case "$status" in
    *RUNNING*|*STARTING*) sleep 60 ;;
    *EXITED*) break ;;
    *) echo "TRAIN_NOT_COMPLETE $status"; touch "$STATE/TRAIN_FAILED"; exit 1 ;;
  esac
done
for name in model.pt train_history.parquet metrics_overall.parquet feature_layout.json run_manifest.json metadata_contract.json; do
  if ! test -s "$RUN/$name"; then echo "MISSING $name"; touch "$STATE/TRAIN_FAILED"; exit 1; fi
done
for phase in P1 P2 P3 P4; do
  for split in validation test; do
    if ! test -s "$RUN/predictions/${split}_${phase}.parquet"; then echo "MISSING $split $phase"; touch "$STATE/TRAIN_FAILED"; exit 1; fi
  done
done
echo "AUDIT_STARTED $(date -Is)"
mkdir -p "$AUDIT"
audit_status=FAILED
if python -u tools/vastai_audit_shared.py --task LO --data-root "$DATA" --run-root "$RUNS" --audit-root "$AUDIT" --model-name PATCHTST --seed 42 --bootstrap-repetitions 2000 --allow-partial; then
  if test -s "$AUDIT/LO/PATCHTST/seed=42/audit_manifest.json"; then audit_status=SUCCESS; fi
fi
echo "AUDIT_STATUS=$audit_status"
echo "$audit_status" > "$STATE/audit_status.txt"
test ! -e "$BUNDLE"
tar -czf "$BUNDLE.partial" -C /workspace/CD3 runs/lo_patchtst_seed42/LO/W3/V2 runs/lo_patchtst_v2_w3_audit_20261107 lo_patchtst_seed42_code/v2_w3_20261107.log lo_patchtst_seed42_code/v2_w3_20261107.err.log runs/lo_patchtst_v2_w3_posthoc_20261107/audit_status.txt
mv "$BUNDLE.partial" "$BUNDLE"
sha256sum "$BUNDLE" > "$STATE/bundle.sha256"
echo "BUNDLE_READY $audit_status $(date -Is)"
touch "$STATE/BUNDLE_READY"
