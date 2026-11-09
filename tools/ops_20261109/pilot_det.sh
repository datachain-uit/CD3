#!/usr/bin/env bash
# Determinism pilot (check 37 (d)): one fresh Mantis cell {TASK}/W1/V0/seed 42 in its own work dir with its own empty cache,
# then sha256 of every artefact that must repeat: channel adapter, level-A embeddings (frames/index/row_ids), probabilities,
# predictions, probe head. Two runs with different TAG are compared with tools/compare_pilot_det_20261109.py.
# usage: pilot_det.sh TASK(CQ|LO) TAG      env: ENVROOT, LDD (optional)
set -Eeuo pipefail
TASK=$1; TAG=$2
BASE=/workspace/CD3
WORK="$BASE/pilot_det_${TASK}_V0_W1_${TAG}"
if test "$TASK" = LO; then DATA="$BASE/lo_mantis_data"; SALTF="$BASE/lo_static_v2_prediction_salt"; else DATA="$BASE/cq_pilot_data"; SALTF="$BASE/mantis_cq_prediction_salt"; fi
test ! -e "$WORK" || { echo "WORK_EXISTS $WORK"; exit 2; }
mkdir -p "$WORK/state"
if test -n "${LDD:-}"; then export LD_LIBRARY_PATH="$LDD/usr/local/cuda-13.0/compat:${LD_LIBRARY_PATH:-}"; fi
tar -xf "$BASE/mantis_lo_code_20261109.tar" -C "$WORK"
ENVROOT="${ENVROOT:-/venv/main}"
source "$ENVROOT/bin/activate"
export PYTHONPATH="$WORK/deps:$WORK:$WORK/tools"
export CUBLAS_WORKSPACE_CONFIG=:4096:8 MALLOC_ARENA_MAX=2 ARROW_NUM_THREADS=2
export TEMPO_PREDICTION_SALT="$(cat "$SALTF")"
if test -n "${DEPS_FROM:-}"; then
  # reuse the dependency directory of an earlier run on this host (same pinned versions) instead of downloading again
  mkdir -p "$WORK/deps"; cp -a "$DEPS_FROM"/. "$WORK/deps"/
else
  uv pip install --python "$ENVROOT/bin/python" --target "$WORK/deps" 'einops>=0.8,<0.9' 'huggingface-hub>=0.23' 'safetensors>=0.4' 'zstandard>=0.23' numpy pandas pyarrow scikit-learn >/dev/null
  uv pip install --python "$ENVROOT/bin/python" --no-deps --target "$WORK/deps" 'mantis-tsfm==1.1.0' >/dev/null
fi
cd "$WORK"
python -c 'import torch,numpy,pandas,sklearn,scipy;print("ENV",torch.__version__,numpy.__version__,pandas.__version__,sklearn.__version__,scipy.__version__)' | tee "$WORK/state/env_versions.txt"
python -m f3_mantis.cli pin --out "$WORK/backbone_pin.json"
echo "PILOT_TRAIN_STARTED $TASK $TAG $(date -Is)"
python -u tools/run_mantis_grid_zstd_20261109.py --task "$TASK" --window W1 --pipeline V0 --data-root "$DATA" --work-root "$WORK"
test -s "$WORK/runs/W1/V0/COMPLETE"
python - <<'PY'
import hashlib, json, os
from pathlib import Path
work = Path(os.environ.get("PWD"))
def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(8 << 20), b""):
            h.update(b)
    return h.hexdigest()
out = {}
for root in ("cache", "runs/W1/V0"):
    for p in sorted((work / root).rglob("*")):
        if p.is_file():
            out[p.relative_to(work).as_posix()] = {"sha256": sha(p), "bytes": p.stat().st_size}
(work / "pilot_hashes.json").write_text(json.dumps(out, indent=1))
print("HASHED", len(out))
PY
cp -p "$WORK/runs/W1/V0/result/f3_cell_record.json" "$WORK/pilot_cell_record.json"
echo "PILOT_DONE $TASK $TAG $(date -Is)"
