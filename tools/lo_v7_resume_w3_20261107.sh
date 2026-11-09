#!/usr/bin/env bash
set -Eeuo pipefail
BASE=/workspace/CD3
CODE="$BASE/lo_patchtst_seed42_code"
DATA="$BASE/data/LO_V3_1_clean_grain_seed42"
RUNS="$BASE/runs/lo_patchtst_seed42"
STATE="$BASE/runs/lo_patch_V7_resume_20261107"
mkdir -p "$STATE"
trap 'touch "$STATE/FAILED"' ERR
source /venv/main/bin/activate
export TEMPO_PREDICTION_SALT="$(cat "$BASE/lo_static_v2_prediction_salt")"
export MALLOC_ARENA_MAX=2
export ARROW_NUM_THREADS=2
cd "$CODE"
python - "$RUNS" "$STATE" <<'PY'
import json, pathlib, sys
import pyarrow.parquet as pq
root=pathlib.Path(sys.argv[1])/"LO"
summary=[]
for w in ("W1", "W2"):
    p=root/w/"V7/PATCHTST/seed=42"
    m=json.loads((p/"run_manifest.json").read_text())
    expected={"task":"LO", "window_id":w, "pipeline_id":"V7", "model_name":"PATCHTST", "seed":42,
              "batch_size":2048, "micro_batch_size":512, "accumulation_steps":4,
              "static_layout_policy":"current", "release_id":"LO_V3_1"}
    assert all(m.get(k)==v for k,v in expected.items()), (w,expected)
    assert m["feature_layout_sha256"]=="sha256:847617755f0d0190efdc52ecada53772f24117e7034885e3432f609b604e17d1"
    for name in ("model.pt", "train_history.parquet", "metrics_overall.parquet", "metadata_contract.json", "feature_layout.json"):
        assert (p/name).is_file() and (p/name).stat().st_size>0, (w,name)
    assert pq.ParquetFile(p/"train_history.parquet").metadata.num_rows >= m["best_epoch"]
    for split in ("validation", "test"):
        for phase in ("P1", "P2", "P3", "P4"):
            f=p/"predictions"/f"{split}_{phase}.parquet"
            expected_rows=m["validation_rows"] if split=="validation" else m["test_rows"][phase]
            assert pq.ParquetFile(f).metadata.num_rows==expected_rows, (w,str(f))
    summary.append({"window":w,"best_epoch":m["best_epoch"],"prediction_row_counts":"PASS",
                    "feature_layout_sha256":m["feature_layout_sha256"],"reference_layout_sha256":m.get("reference_layout_sha256"),
                    "runner_git_commit":m.get("runner_git_commit"),"success_marker_present":(p/"_SUCCESS").exists()})
pathlib.Path(sys.argv[2],"preflight_W1_W2.json").write_text(json.dumps(summary,indent=2)+"\n")
print("PREFLIGHT_PASS",json.dumps(summary),flush=True)
PY
TARGET="$RUNS/LO/W3/V7/PATCHTST/seed=42"
test ! -e "$TARGET"
echo "TRAIN_STARTED W3 V7 $(date -Is) workers=0"
python -u tools/vastai_train_shared.py --task LO --data-root "$DATA" --output-root "$RUNS" --window W3 --pipeline-id V7 --model-name PATCHTST --seed 42 --batch-size 2048 --accumulation-steps 4 --workers 0 --max-epochs 50 --patience 5 --static-layout-policy current --run-purpose PRIMARY_GRID --augmentation-seed-policy match_model_seed --energy-sampling-interval-seconds 1.0
test -s "$TARGET/run_manifest.json"
test -s "$TARGET/metadata_contract.json"
for P in P1 P2 P3 P4; do test -s "$TARGET/predictions/validation_$P.parquet"; test -s "$TARGET/predictions/test_$P.parquet"; done
echo "TRAIN_COMPLETE W3 V7 $(date -Is)"
mkdir -p "$STATE/selected/LO"
for W in W1 W2 W3; do
  mkdir -p "$STATE/selected/LO/$W/V7"
  ln -s "$RUNS/LO/$W/V7/PATCHTST" "$STATE/selected/LO/$W/V7/PATCHTST"
done
python -u tools/vastai_audit_shared.py --task LO --data-root "$DATA" --run-root "$STATE/selected" --audit-root "$STATE/audit" --model-name PATCHTST --seed 42 --bootstrap-repetitions 2000 --allow-partial
python -c 'import json,sys; m=json.load(open(sys.argv[1])); assert m["runs"]==3 and m["bootstrap_repetitions"]==2000' "$STATE/audit/LO/PATCHTST/seed=42/audit_manifest.json"
mkdir -p "$STATE/artifacts/LO"
for W in W1 W2 W3; do mkdir -p "$STATE/artifacts/LO/$W"; cp -a "$RUNS/LO/$W/V7" "$STATE/artifacts/LO/$W/"; done
tar -czf "$BASE/runs/lo_patch_V7_resume_20261107.tar.gz.partial" -C "$STATE" artifacts audit preflight_W1_W2.json
mv "$BASE/runs/lo_patch_V7_resume_20261107.tar.gz.partial" "$BASE/runs/lo_patch_V7_resume_20261107.tar.gz"
sha256sum "$BASE/runs/lo_patch_V7_resume_20261107.tar.gz" > "$STATE/bundle.sha256"
touch "$STATE/BUNDLE_READY"
echo "BUNDLE_READY $(date -Is)"
