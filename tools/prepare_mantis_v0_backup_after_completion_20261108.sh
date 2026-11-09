#!/usr/bin/env bash
set -Eeuo pipefail
BASE=/workspace/CD3
APP=$BASE/mantis_v0_20261107
QUEUE=$BASE/mantis_v0_w2_w3_queue_20261108
STATE=$BASE/mantis_v0_backup_for_v13_20261108
mkdir -p "$STATE"
trap 'touch "$STATE/FAILED"' ERR
for unused in $(seq 1 10080); do
  test ! -f "$QUEUE/FAILED" || exit 1
  test ! -f "$APP/FAILED" || exit 1
  test -f "$QUEUE/ALL_COMPLETE" && break
  sleep 30
done
test -f "$QUEUE/ALL_COMPLETE"
for W in W1 W2 W3; do
  test -s "$APP/runs/$W/V0/COMPLETE"
  test -s "$APP/runs/$W/V0/result/f3_cell_record.json"
  test -s "$APP/runs/$W/V0/result/probe_head.pt"
  test -s "$APP/runs/$W/V0/result/validation_probabilities.npy"
  test -s "$APP/runs/$W/V0/result/test_probabilities.npy"
done
tar -czf "$STATE/mantis_v0_results.tar.gz.partial" --exclude='*/cache' -C "$APP" runs backbone_pin.json
mv "$STATE/mantis_v0_results.tar.gz.partial" "$STATE/mantis_v0_results.tar.gz"
sha256sum "$STATE/mantis_v0_results.tar.gz" > "$STATE/result.sha256"
touch "$STATE/RESULTS_READY"
