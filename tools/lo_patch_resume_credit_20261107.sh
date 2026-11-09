#!/usr/bin/env bash
set -Eeuo pipefail
V="$1"
BASE=/workspace/CD3
CODE="$BASE/lo_patchtst_seed42_code"
DATA="$BASE/data/LO_V3_1_clean_grain_seed42"
RUNS="$BASE/runs/lo_patchtst_seed42"
STATE="$BASE/runs/lo_patch_${V}_resume_credit_20261107${LO_RESUME_SUFFIX:-}"
mkdir -p "$STATE"
trap 'touch "$STATE/FAILED"' ERR
source "${LO_PY_ENV:-/venv/main}/bin/activate"
export TEMPO_PREDICTION_SALT="$(cat "$BASE/lo_static_v2_prediction_salt")"
export MALLOC_ARENA_MAX=2
cd "$CODE"
for W in W1 W2 W3; do
  TARGET="$RUNS/LO/$W/$V/PATCHTST/seed=42"
  if test -d "$TARGET"; then
    python - "$TARGET" "$W" "$V" <<'PY'
import json,pathlib,sys
import pyarrow.parquet as pq
p=pathlib.Path(sys.argv[1]); w=sys.argv[2]; v=sys.argv[3]
m=json.loads((p/'run_manifest.json').read_text())
expected={'task':'LO','window_id':w,'pipeline_id':v,'model_name':'PATCHTST','seed':42,'batch_size':2048,'micro_batch_size':512,'accumulation_steps':4,'release_id':'LO_V3_1','static_layout_policy':'current'}
assert all(m.get(k)==val for k,val in expected.items()),(w,v,expected)
assert m['feature_layout_sha256']=='sha256:847617755f0d0190efdc52ecada53772f24117e7034885e3432f609b604e17d1'
for f in ['model.pt','train_history.parquet','metrics_overall.parquet','metadata_contract.json','feature_layout.json']:
    assert (p/f).is_file() and (p/f).stat().st_size>0,(w,v,f)
for split in ('validation','test'):
    for phase in ('P1','P2','P3','P4'):
        rows=m['validation_rows'] if split=='validation' else m['test_rows'][phase]
        assert pq.ParquetFile(p/'predictions'/f'{split}_{phase}.parquet').metadata.num_rows==rows,(w,v,split,phase)
print('PREVIOUS_WINDOW_VERIFIED',w,v,'best_epoch',m['best_epoch'],flush=True)
PY
  else
    echo "TRAIN_STARTED $W $V $(date -Is)"
    python -u tools/vastai_train_shared.py --task LO --data-root "$DATA" --output-root "$RUNS" --window "$W" --pipeline-id "$V" --model-name PATCHTST --seed 42 --batch-size 2048 --accumulation-steps 4 --workers 2 --max-epochs 50 --patience 5 --static-layout-policy current --run-purpose PRIMARY_GRID --augmentation-seed-policy match_model_seed --energy-sampling-interval-seconds 1.0
    test -s "$TARGET/run_manifest.json"
    echo "TRAIN_COMPLETE $W $V $(date -Is)"
  fi
done
mkdir -p "$STATE/selected/LO"
for W in W1 W2 W3; do
  mkdir -p "$STATE/selected/LO/$W/$V"
  ln -s "$RUNS/LO/$W/$V/PATCHTST" "$STATE/selected/LO/$W/$V/PATCHTST"
done
python -u tools/vastai_audit_shared.py --task LO --data-root "$DATA" --run-root "$STATE/selected" --audit-root "$STATE/audit" --model-name PATCHTST --seed 42 --bootstrap-repetitions 2000 --allow-partial
python -c 'import json,sys; m=json.load(open(sys.argv[1])); assert m["runs"]==3 and m["bootstrap_repetitions"]==2000' "$STATE/audit/LO/PATCHTST/seed=42/audit_manifest.json"
mkdir -p "$STATE/artifacts/LO"
for W in W1 W2 W3; do mkdir -p "$STATE/artifacts/LO/$W"; cp -a "$RUNS/LO/$W/$V" "$STATE/artifacts/LO/$W/"; done
tar -czf "$BASE/runs/lo_patch_${V}_resume_credit_20261107.tar.gz.partial" -C "$STATE" artifacts audit
mv "$BASE/runs/lo_patch_${V}_resume_credit_20261107.tar.gz.partial" "$BASE/runs/lo_patch_${V}_resume_credit_20261107.tar.gz"
sha256sum "$BASE/runs/lo_patch_${V}_resume_credit_20261107.tar.gz" > "$STATE/bundle.sha256"
touch "$STATE/BUNDLE_READY"
echo "BUNDLE_READY $V $(date -Is)"
