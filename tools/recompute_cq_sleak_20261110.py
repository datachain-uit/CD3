"""Q-31 (a) (writing-side recommendation, applied 2026-11-10, ratification pending): copy s_leak from the registered reference table into a facts package and
recompute the leak-dependent columns (generalised from the LO r2 tool of 2026-11-09).

s_leak is a property of (task, window, split, phase): the F1 export holds ONE value per (window, split, phase) for all 68
pipeline/model rows (spread 0). The LO PatchTST audits carried three slightly different probe fits, so the package is rebuilt:
  s_leak, s_leak_probe_auc            <- canonical F1 values
  s_san_plus, s_san_plus_v2           <- geometric mean (floor 1e-3) of the six components with the canonical s_leak
  acctempo_m3 (v1), acctempo_m4 (v2)  <- clip(S_perf,1e-3)^0.6 * clip(S_san+,1e-3)^0.4
  n_at_floor columns (if present)     <- recounted
Before replacing anything the formulas must reproduce the existing columns from the existing components (<= 1e-9),
otherwise the script stops. Output: a copy of the package with suffix _r2, README_r2.md, r2_changes.csv, new sha256sums.
No GPU, no prediction files needed.
Usage: python tools/recompute_lo_patchtst_sleak_r2_20261109.py
"""
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import argparse
ap = argparse.ArgumentParser()
ap.add_argument('--src', type=Path, required=True)
ap.add_argument('--out', type=Path, required=True)
ap.add_argument('--reference', type=Path, required=True, help='s_leak_reference_<TASK>.csv (columns window_id, eval_split, phase_id, s_leak)')
ap.add_argument('--revision', default='r2')
ARGS = ap.parse_args()
SRC, OUT, CANON = ARGS.src, ARGS.out, ARGS.reference
K = ['window_id', 'eval_split', 'phase_id']
FLOOR = 1e-3
V1 = ['s_nan', 's_maj_jsd', 's_ent', 's_drift', 's_eff', 's_leak']
V2 = ['s_nan', 's_maj_jsd', 's_cal', 's_drift', 's_eff', 's_leak']


def gmean(frame, cols):
    v = frame[cols].to_numpy(float)
    return np.exp(np.log(np.maximum(v, FLOOR)).mean(axis=1)), (v < FLOOR).sum(axis=1)


def derived(frame):
    out = frame.copy()
    out['s_san_plus'], n1 = gmean(out, V1)
    out['s_san_plus_v2'], n2 = gmean(out, V2)
    sp = np.maximum(out['s_perf'].to_numpy(float), FLOOR)
    out['acctempo_m3'] = sp ** 0.6 * np.maximum(out['s_san_plus'].to_numpy(float), FLOOR) ** 0.4
    out['acctempo_m4'] = sp ** 0.6 * np.maximum(out['s_san_plus_v2'].to_numpy(float), FLOOR) ** 0.4
    return out, n1, n2


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(4 << 20), b''):
            h.update(b)
    return h.hexdigest()


def main():
    canon = pd.read_csv(CANON)
    g = canon.groupby(K).agg(s_leak=('s_leak', 'first'), spread=('s_leak', lambda x: x.max() - x.min())).reset_index()
    if len(g) != 24 or g.spread.max() > 1e-12:
        raise SystemExit('reference s_leak table is not unique per window x split x phase')
    # s_leak = clip(2 - 2*auc, 0, 1)  ->  auc = 1 - s_leak/2 (exact where s_leak < 1; the formula was verified on the package below)
    g['auc'] = 1.0 - g['s_leak'] / 2.0
    if (g['s_leak'] >= 1.0).any():
        print('WARNING: s_leak == 1 in', int((g['s_leak'] >= 1.0).sum()), 'reference cells; s_leak_probe_auc is not recoverable there')
        g.loc[g['s_leak'] >= 1.0, 'auc'] = np.nan
    can = g.set_index(K)
    san = pd.read_parquet(SRC / 'sanity_components.parquet')
    # 1) formula reproduces the existing columns
    ref, _, _ = derived(san)
    errs = {c: float(np.abs(ref[c] - san[c]).max()) for c in ('s_san_plus', 's_san_plus_v2', 'acctempo_m3', 'acctempo_m4') if c in san}
    print('formula check (max abs diff vs existing columns):', errs)
    if max(errs.values()) > 1e-9:
        raise SystemExit('formula does not reproduce the existing columns; stop')
    # 2) replace s_leak and recompute
    new = san.copy()
    idx = pd.MultiIndex.from_frame(new[K])
    new['s_leak'] = can.loc[idx, 's_leak'].to_numpy()
    if 's_leak_probe_auc' in new:
        chk = np.abs(np.clip(2 - 2 * san['s_leak_probe_auc'].to_numpy(float), 0, 1) - san['s_leak'].to_numpy(float)).max()
        if chk > 1e-9:
            raise SystemExit(f's_leak != clip(2-2*auc) in the source package ({chk}); stop')
        new['s_leak_probe_auc'] = can.loc[idx, 'auc'].to_numpy()
    new, n1, n2 = derived(new)
    for col, vals in (('n_at_floor_v1', n1), ('n_at_floor_v2', n2)):
        if col in new:
            new[col] = vals
    changed = [c for c in ['s_leak', 's_leak_probe_auc', 's_san_plus', 's_san_plus_v2', 'acctempo_m3', 'acctempo_m4'] if c in san]
    keys = ['pipeline_id', 'window_id', 'eval_split', 'phase_id']
    delta = san[keys].copy()
    for c in changed:
        delta[c + '_old'] = san[c].to_numpy()
        delta[c + '_new'] = new[c].to_numpy()
        delta[c + '_diff'] = new[c].to_numpy() - san[c].to_numpy()
    print({c: round(float(np.abs(delta[c + '_diff']).max()), 6) for c in changed})
    if (new.groupby(K).s_leak.nunique() != 1).any():
        raise SystemExit('s_leak still not unique per window x split x phase')

    # evaluation_slices: same canonical s_leak for every slice of the same (window, split, phase)
    sl = pd.read_parquet(SRC / 'evaluation_slices.parquet')
    sl_new = sl.copy()
    if 's_leak' in sl_new:
        idx2 = pd.MultiIndex.from_frame(sl_new[K])
        sl_new['s_leak'] = can.loc[idx2, 's_leak'].to_numpy()
        comp = [c for c in set(V1 + V2) if c not in sl_new]
        if not comp and 's_san_plus' in sl_new:
            ref_sl, _, _ = derived(sl)
            e = max(float(np.abs(ref_sl[c] - sl[c]).max()) for c in ('s_san_plus', 'acctempo_m3') if c in sl)
            print('slice formula check', e)
            if e <= 1e-9:
                sl_new, _, _ = derived(sl_new)
        else:
            print('slice components missing:', comp, '-> only s_leak replaced in evaluation_slices')

    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(SRC, OUT)
    (OUT / 'sha256sums.txt').unlink()
    for name, frame in (('sanity_components', new), ('evaluation_slices', sl_new)):
        frame.to_parquet(OUT / (name + '.parquet'), index=False)
        frame.to_csv(OUT / (name + '.csv'), index=False)
    delta.to_csv(OUT / 'r2_changes.csv', index=False)
    summary = json.loads((OUT / 'summary.json').read_text(encoding='utf-8'))
    summary.update({'revision': ARGS.revision, 'r2_created_utc': datetime.now(timezone.utc).isoformat(),
                    's_leak_source': 'registered reference table s_leak_reference_<task>_20261109 (one value per window x split x phase), copied per Q-31 (a)',
                    'r2_max_abs_change': {c: float(np.abs(delta[c + '_diff']).max()) for c in changed}})
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    readme = (OUT / 'README.md').read_text(encoding='utf-8')
    (OUT / 'README.md').write_text(
        readme + '\n## Revision r2 (09/11/2026)\n\n`s_leak` and `s_leak_probe_auc` are now the canonical values of the LO F1 static-v2 grid '
        '(one value per window × split × phase for every pipeline). `s_san_plus`, `s_san_plus_v2`, `acctempo_m3` and `acctempo_m4` were recomputed from '
        'the unchanged components with the same formulas (geometric mean with floor 1e-3; AccTEMPO = S_perf^0.6 × S_san+^0.4); the formulas reproduce '
        'the previous columns to 1e-9 before the replacement. Metrics that do not depend on the leak probe (macro-F1, S_perf, S_ent, S_cal, …), the '
        'cohort slices and the resources are unchanged. `r2_changes.csv` lists old, new and difference for every cell.\n', encoding='utf-8')
    files = sorted(p for p in OUT.rglob('*') if p.is_file() and p.name != 'sha256sums.txt')
    (OUT / 'sha256sums.txt').write_text(''.join(sha(p) + '  ' + p.relative_to(OUT).as_posix() + '\n' for p in files), encoding='utf-8')
    print('written', OUT, 'files', len(files))


if __name__ == '__main__':
    main()
