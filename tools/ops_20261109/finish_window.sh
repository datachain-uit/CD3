#!/usr/bin/env bash
# usage: finish_window.sh <V> <PARENT> <W> <WORKDIR>   verify the cache, save the adapter, package one completed window, free the synthetic cache
set -uo pipefail
V=$1; PARENT=$2; W=$3; WORK=/workspace/CD3/$4; BASE=/workspace/CD3
cd "$WORK"; source /venv/main/bin/activate; export PYTHONPATH="$WORK/deps:$WORK:$WORK/tools"
test -s runs/$W/$V/COMPLETE || { echo "NOT_COMPLETE $V $W"; exit 1; }
python -u $BASE/verify_mantis_zstd_cache_fixed_20261108.py cache/task=CQ/window=$W --allow-cell-train || { echo "VERIFY_FAILED $V $W"; exit 2; }
echo "CACHE_VERIFIED $W $V $(date -Is)"
mkdir -p adapters/$W; cp -p cache/task=CQ/window=$W/imputer=$PARENT/channel_adapter.* adapters/$W/
OUT=$BASE/runs/mantis_cq_${V}_${W}_20261109_results.tar.gz
tar -czf $OUT.partial -C "$WORK" runs/$W adapters/$W backbone_pin.json state/environment_pip_freeze.txt && mv $OUT.partial $OUT && sha256sum $OUT > $OUT.sha256
rm -rf cache/task=CQ/window=$W/imputer=$PARENT/adapter=*/encoder=*/pipeline=$V
echo "FINISHED $V $W $(ls -la $OUT | awk '{print $5}') $(date -Is)"
