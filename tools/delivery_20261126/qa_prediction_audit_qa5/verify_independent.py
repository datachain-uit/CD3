"""Independent re-computation of QA07 and QA12 (population part) for ONE run, written without reusing qa_pred_audit.py code paths:
sha256 by the OS tool, probabilities read with pandas and processed in a pure-python loop (math.fsum, max()), population by the FULL 64-hex salted hash string (no 60-bit key).
usage: python verify_independent.py RUN_DIR_WITH_predictions OUT_JSON   (the salt is read into memory only)"""
import hashlib, json, math, os, sys
from pathlib import Path
import pandas as pd
run = Path(sys.argv[1]); out = Path(sys.argv[2])
REPO = os.environ['TEMPO_REPO_ROOT']; WORK = os.environ['TEMPO_WORK_ROOT']
salts = [Path(p).read_bytes().decode().rstrip('\n') for p in [f'{REPO}/downloads/private/lo_grid_prediction_salt', f'{REPO}/CQ/resuilt/private/.vastai_cq_prediction_salt', f'{REPO}/downloads/private/lo_replay_protocol27_prediction_salt'] if Path(p).exists()]
fl = pd.read_parquet(f'{WORK}/phaseB/seen_flags_LO.parquet', columns=['window_id', 'split_name', 'phase_id', 'enrollment_id'])
res = []
for f in sorted((run / 'predictions').glob('*.parquet')):
    sp, ph = f.stem.split('_'); split = sp.upper()
    d = pd.read_parquet(f)
    n = len(d); sum_viol = 0; worst = 0.0; arg_viol = 0; tie = 0
    for a, b, c, yp in zip(d.prob_c0.tolist(), d.prob_c1.tolist(), d.prob_c2.tolist(), d.y_pred.tolist()):
        e = abs(math.fsum((a, b, c)) - 1.0); worst = max(worst, e); sum_viol += e > 1e-4
        pr = (a, b, c); m = max(pr)
        if pr[int(yp[1:])] < m: arg_viol += 1
        elif pr.index(m) != int(yp[1:]): tie += 1
    w = d.window_id.iloc[0]
    ids = fl[(fl.window_id == w) & (fl.split_name == split) & (fl.phase_id == ph)].enrollment_id.astype(str).tolist()
    h = set(d.enrollment_id_hash.tolist()); notin = None
    for s in salts:
        pop = {hashlib.sha256(f'{s}|{i}'.encode()).hexdigest() for i in ids}
        if len(pop & h) > 0.9 * len(h):
            notin = len(h - pop); break
    res.append({'file': f.name, 'sha256': hashlib.sha256(f.read_bytes()).hexdigest(), 'n_rows': n, 'max_abs_sum_err': worst, 'n_sum_viol': int(sum_viol), 'n_pred_below_max': arg_viol, 'n_ties': tie, 'n_unique_hash': len(h), 'n_hash_not_in_population': notin})
out.write_text(json.dumps(res, indent=1)); print(json.dumps(res, indent=1))
