#!/usr/bin/env python
"""qa_pred_audit.py - per-unit audit of QA07 / QA11 / QA12 / QA13 / QA21 on sample-level predictions and run manifests (READ-ONLY on Drive).

One unit = (task, model, seed) = 51 runs (3 windows x 17 pipelines) x 2 splits x 4 phases = 408 prediction files.
The prediction files are never written to disk when they come from a tar (rclone cat | tarfile stream mode, each member is checked in memory).
Loose files are copied to --tmp, checked and deleted. Salts are only read into memory (to test that every prediction hash is a real enrollment), never printed or stored.

usage:  python qa_pred_audit.py LO PATCHTST 43 --out OUT_DIR [--tmp TMP_DIR] [--only-tar NAME] [--no-population]
env:    TEMPO_REPO_ROOT, TEMPO_WORK_ROOT  (as the phase-B tools)
output: OUT_DIR/<UNIT>_qa_files.csv   one row per prediction file (QA07, QA12 and QA21-part1 columns)
        OUT_DIR/<UNIT>_qa_runs.csv    one row per run (QA13, QA11, QA21 parts, links to S1/S2 manifests)
        OUT_DIR/<UNIT>_qa_evidence.json   counts, verdict per check, timing, bytes downloaded
"""
import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

REPO = Path(os.environ['TEMPO_REPO_ROOT']).as_posix()      # required (no machine-specific default)
WORK = Path(os.environ['TEMPO_WORK_ROOT']).as_posix()
ROOT_ID = '1GWiedVROrxp8jvGbd0xmvVmWriZUkpOn'
RC = ['rclone', '--drive-root-folder-id', ROOT_ID]
TOL = 1e-4
CLASSES = ['c0', 'c1', 'c2']
SALTS = [f'{REPO}/CQ/resuilt/private/.vastai_cq_prediction_salt', f'{REPO}/CQ/resuilt/private/.cq_matched_replay_prediction_salt', f'{REPO}/downloads/private/cq_patchtst_prediction_salt',
         f'{REPO}/downloads/private/lo_grid_prediction_salt', f'{REPO}/downloads/private/lo_replay_protocol27_prediction_salt', f'{REPO}/LO/resuilt/lo_static_ablation_20261019/.ablation_prediction_salt']
# source ranking copied from tools/subgroups_phaseB/run_unit.py (official packages first, pilots/replays/ablations last)
PREFER = ['primary/release=LO_STATIC_V2', 'primary/family=PATCHTST', 'cq_recurrent_batch2048_seed42', 'cq_lstm_batch2048_full', 'cq_rnn_historical_layout_batch2048', 'mantis_v2_seed', 'staging_incoming']
DENY = ['pilot', 'determinism', 'replay', 'ablation', '/vastai/', 'vastai_runs', 'matched_historical', 'baseline_drive', 'nvml_historical', 'cohort_audit', 'host_backups']
TRUNCATED_TARS = {'lo_patchtst_seed44_V2_host40077.tar', 'LO_static_v2_BILSTM.tar'}
# 19 canonical LO label-proxy fields of LO/registries.py::LO_PROXY_CONTRACT (every _P1.._P4 variant is also a proxy); CQ has no flat list (feature dictionary needed) -> part 5 not evaluated for CQ
LO_PROXY = {'performance_score', 'video_weight', 'assignment_weight', 'exam_weight', 'course_weight_total', 'watched_videos', 'video_counts', 'watch_percent', 'video_catalog_coverage',
            'assignment_problem_catalog_count', 'exam_problem_catalog_count', 'assignment_best_correct_sum', 'exam_best_correct_sum', 'assignment_ratio_catalog', 'exam_ratio_catalog',
            'problem_catalog_coverage', 'problem_score_catalog_coverage', 'tempo_legacy_unclipped_score', 'tempo_legacy_score_clipped'}
SYN_NAME = re.compile(r'synth|smote|augment|generated|is_syn|ledger', re.I)

ap = argparse.ArgumentParser()
ap.add_argument('task'); ap.add_argument('model'); ap.add_argument('seed', type=int)
ap.add_argument('--out', required=True)
ap.add_argument('--tmp', default=None)
ap.add_argument('--only-tar', default=None, help='process only the tar whose basename equals this (smoke test / partial run)')
ap.add_argument('--no-population', action='store_true', help='skip the salted hash check against the real enrollment population (QA12 part c)')
ap.add_argument('--seed-folder-layout', default='seed={seed}', help='folder under S3_model holding the unit (Drive layout of 2026-11-26)')
args = ap.parse_args()
TASK, MODEL, SEED = args.task, args.model, args.seed
UNIT = f'{TASK}_{MODEL}_seed{SEED}'
OUT = Path(args.out); OUT.mkdir(parents=True, exist_ok=True)
TMP = Path(args.tmp) if args.tmp else OUT / 'tmp'
TMP.mkdir(parents=True, exist_ok=True)
T0 = time.time()
BYTES = {'tar_stream': 0, 'loose': 0, 'small_json': 0}


def log(m):
    print(time.strftime('%T'), f'[{UNIT}]', m, flush=True)


def rclone(*a, check=True):
    r = subprocess.run(RC + list(a), capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError('rclone ' + ' '.join(a[:2]) + ': ' + r.stderr[-300:])
    return r.stdout


def rank(path):
    if any(d in path for d in DENY):
        return 2
    return 0 if any(p_ in path for p_ in PREFER) else 1


# ---------------------------------------------------------------- locate sources (catalog of phase B + new Drive layout seed=NN)
cat = pd.read_parquet(f'{WORK}/phaseB/pred_files_unified.parquet')
cat = cat[(cat.task == TASK) & (cat.model_name == MODEL) & (cat.seed == SEED)]
S3 = f'{TASK}/L1_runs/S3_model'
SEEDDIR = f'{S3}/' + args.seed_folder_layout.format(seed=SEED)
listing = set(l for l in rclone('lsf', f'gdrive:{SEEDDIR}', '-R', '--files-only').splitlines() if l)
by_base = {}
for l in listing:
    by_base.setdefault(l.rsplit('/', 1)[-1], []).append(l)
log(f'Drive listing of {SEEDDIR}: {len(listing)} files')


def to_new(old_rel):
    """old S3_model-relative path -> path in the seed=NN layout (insertion rule; fallback unique basename)"""
    if old_rel in listing:
        return f'{SEEDDIR}/{old_rel}'
    c = by_base.get(old_rel.rsplit('/', 1)[-1], [])
    return f'{SEEDDIR}/{c[0]}' if len(c) == 1 else None


need = {}
unresolved = set()
for r in cat.itertuples():
    old_rel = r.path[len(S3) + 1:] if r.kind == 'tar' and r.path.startswith(S3 + '/') else r.path
    new = to_new(old_rel)
    if new is None:
        unresolved.add(old_rel); continue
    need.setdefault((r.window_id, r.pipeline_id, r.split.lower(), r.phase_id), []).append((r.kind, new))
if len(need) != 408:
    log(f'WARNING: {len(need)} (run, split, phase) keys resolved instead of 408; unresolved sources: {len(unresolved)}')
WANT = set(need)
RUNS = sorted({(w, v) for (w, v, _, _) in WANT})

# choose one source per key (loose first, then best-ranked tar; same policy as run_unit.py)
tar_keys, loose_keys, got = {}, {}, set()
for k, srcs in need.items():
    loose = sorted((x for x in srcs if x[0] == 'loose'), key=lambda x: rank(x[1]))
    tars = sorted((x for x in srcs if x[0] == 'tar' and Path(x[1]).name not in TRUNCATED_TARS), key=lambda x: rank(x[1])) or sorted((x for x in srcs if x[0] == 'tar'), key=lambda x: rank(x[1]))
    if loose and rank(loose[0][1]) < 2:
        loose_keys[k] = loose[0][1]
    elif tars:
        tar_keys.setdefault(tars[0][1], set()).add(k)
    elif loose:
        loose_keys[k] = loose[0][1]
if args.only_tar:
    tar_keys = {t: ks for t, ks in tar_keys.items() if Path(t).name == args.only_tar}
    loose_keys = {}
    WANT = set().union(*tar_keys.values()) if tar_keys else set()
    RUNS = sorted({(w, v) for (w, v, _, _) in WANT})
log(f'plan: {len(WANT)} files wanted, {len(tar_keys)} tars, {len(loose_keys)} loose files')

# ---------------------------------------------------------------- population of real enrollments (salted hashes, in memory only)
SALT_VALUES = []
POP = {}
flags = None
if not args.no_population:
    SALT_VALUES = [Path(f).read_bytes().decode('utf-8').rstrip('\n') for f in SALTS if Path(f).exists()]
    flags = pd.read_parquet(f'{WORK}/phaseB/seen_flags_{TASK}.parquet', columns=['window_id', 'split_name', 'phase_id', 'enrollment_id'])


def hkey(h):
    return int(h[:15], 16)


def population(si, w, split, phase):
    k = (si, w, split, phase)
    if k not in POP:
        ids = flags[(flags.window_id == w) & (flags.split_name == split) & (flags.phase_id == phase)].enrollment_id.astype(str)
        keys = np.fromiter((hkey(hashlib.sha256(f'{SALT_VALUES[si]}|{v}'.encode()).hexdigest()) for v in ids), dtype=np.int64, count=len(ids))
        if len(np.unique(keys)) != len(keys):
            raise RuntimeError(f'60-bit key collision in population {w} {split} {phase}')
        POP[k] = np.sort(keys)
    return POP[k]


def detect_salt(hashes, w, split, phase):
    ids = flags[(flags.window_id == w) & (flags.split_name == split) & (flags.phase_id == phase)].enrollment_id.astype(str).head(300).tolist()
    hs = set(hashes)
    for si, s in enumerate(SALT_VALUES):
        if all(hashlib.sha256(f'{s}|{v}'.encode()).hexdigest() in hs for v in ids):
            return si
    return None


# ---------------------------------------------------------------- per-file checks
FILES = []          # per-file evidence rows
KEYS = {}           # (w, v, phase, split) -> int64 key array (for the VALIDATION/TEST disjointness check; dropped after use)
MANIFESTS = {}      # (w, v) -> dict
LAYOUT = {}         # (w, v) -> parsed feature_layout.json (model input features of the run)
EXTRA = {}          # (w, v) -> {member name: sha256} for model.pt / feature_layout.json / metadata_contract.json when present
COLS_SEEN = {}


def check_file(w, v, split, phase, data, source):
    t = pq.read_table(io.BytesIO(data))
    cols = t.schema.names
    COLS_SEEN.setdefault(tuple(cols), 0); COLS_SEEN[tuple(cols)] += 1
    n = t.num_rows
    P = np.column_stack([t.column(f'prob_{c}').to_numpy(zero_copy_only=False).astype(np.float64) for c in CLASSES])
    yp = t.column('y_pred').to_pandas().astype(str)
    yt = t.column('y_true').to_pandas().astype(str)
    pidx = yp.map({c: i for i, c in enumerate(CLASSES)})
    bad_label = int(pidx.isna().sum()) + int((~yt.isin(CLASSES)).sum())
    pi = pidx.fillna(-1).astype(int).to_numpy()
    finite = np.isfinite(P).all(axis=1)
    sum_err = np.abs(np.where(finite, P.sum(axis=1), np.nan) - 1.0)
    mx = np.nanmax(sum_err) if finite.any() else np.nan
    am = P.argmax(axis=1)
    valid = pi >= 0
    ptrue_pred = np.where(valid, P[np.arange(n), np.where(valid, pi, 0)], np.nan)
    viol_strict = int(((ptrue_pred < P.max(axis=1)) & valid).sum())      # y_pred has a probability strictly below the maximum
    mism = int(((am != pi) & valid).sum())                               # argmax index differs (includes exact ties)
    h = t.column('enrollment_id_hash').to_pandas()
    row = {'unit': UNIT, 'window_id': w, 'pipeline_id': v, 'eval_split': split.upper(), 'phase_id': phase, 'source': Path(source).name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
           'n_rows': n, 'columns': ';'.join(cols),
           'qa07_n_nonfinite_prob': int((~finite).sum()), 'qa07_n_prob_out_of_0_1': int(((P < 0) | (P > 1)).any(axis=1).sum()), 'qa07_max_abs_sum_err': float(mx), 'qa07_n_sum_viol': int((sum_err > TOL).sum()),
           'qa07_n_bad_label': bad_label, 'qa07_n_argmax_mismatch': mism, 'qa07_n_pred_below_max': viol_strict, 'qa07_n_ties': mism - viol_strict,
           'qa12_split_col_ok': bool((t.column('eval_split').to_pandas().astype(str) == split.upper()).all()) if 'eval_split' in cols else None,
           'qa12_synthetic_like_columns': ';'.join(c for c in cols if SYN_NAME.search(c)),
           'qa12_n_hash_null': int(h.isna().sum()), 'qa12_n_hash_duplicate': int(h.duplicated().sum())}
    # real-enrollment test (part c): every hash must be the salted hash of a real enrollment of this (window, split, phase)
    row.update({'qa12_pop_checked': False, 'qa12_pop_size': None, 'qa12_n_not_in_population': None, 'qa12_pop_coverage': None})
    keys = np.fromiter((hkey(x) for x in h), dtype=np.int64, count=n)
    if SALT_VALUES:
        si = detect_salt(h.tolist(), w, split.upper(), phase)
        if si is None:
            row['qa12_pop_checked'] = 'NO_SALT_MATCH'
        else:
            pop = population(si, w, split.upper(), phase)
            pos = np.searchsorted(pop, keys); pos[pos >= len(pop)] = 0
            inpop = pop[pos] == keys
            row.update({'qa12_pop_checked': True, 'qa12_pop_size': int(len(pop)), 'qa12_n_not_in_population': int((~inpop).sum()), 'qa12_pop_coverage': float(len(np.unique(keys[inpop])) / len(pop))})
    # VALIDATION vs TEST disjointness of the keys within (run, phase) (QA21 part 1, prediction level)
    other = KEYS.pop((w, v, phase, 'test' if split == 'validation' else 'validation'), None)
    if other is None:
        KEYS[(w, v, phase, split)] = keys
        row['qa21p1_val_test_overlap'] = None
    else:
        row['qa21p1_val_test_overlap'] = int(np.intersect1d(keys, other).size)
    row['_k'] = (w, v, split, phase)
    FILES.append(row)
    return row


def parse_pred(name, tar_name):
    m = re.search(r'(?:(CQ|LO)/)?(W\d)/(V\d+)/([A-Z][A-Z0-9_]*)/seed=(\d+)/predictions/(validation|test)_(P\d)\.parquet$', name)
    if m:
        return m.group(2), m.group(3), m.group(4), int(m.group(5)), m.group(6), m.group(7)
    m = re.search(r'runs/(W\d)/(V\d+)/predictions/(validation|test)_(P\d)\.parquet$', name)
    if m:
        sd = re.search(r'seed[_=]?(\d+)', tar_name)
        return m.group(1), m.group(2), 'MANTIS_V2', int(sd.group(1)) if sd else None, m.group(3), m.group(4)
    return None


AUX = re.compile(r'(W\d)/(V\d+)/(?:[A-Z][A-Z0-9_]*/seed=(\d+)/)?(run_manifest\.json|model\.pt|feature_layout\.json|metadata_contract\.json)$')


def take_aux(name, data):
    m = AUX.search(name)
    if not m:
        return
    w, v, _, fn = m.groups()
    if (w, v) not in set(RUNS):
        return
    if fn == 'run_manifest.json':
        MANIFESTS.setdefault((w, v), json.loads(data.decode('utf-8')))
    EXTRA.setdefault((w, v), {})[fn] = hashlib.sha256(data).hexdigest()
    if fn == 'feature_layout.json':
        LAYOUT.setdefault((w, v), json.loads(data.decode('utf-8')))


class Counting(io.RawIOBase):
    def __init__(self, f, key):
        self.f, self.key = f, key
    def readable(self):
        return True
    def readinto(self, b):
        d = self.f.read(len(b))
        b[:len(d)] = d
        BYTES[self.key] += len(d)
        return len(d)


# ---------------------------------------------------------------- 1) tars (streamed, nothing written to disk)
for tar_new, keys in sorted(tar_keys.items(), key=lambda x: -len(x[1])):
    todo = keys - got
    if not todo:
        continue
    t1 = time.time(); n0 = len(got)
    p = subprocess.Popen(RC + ['cat', f'gdrive:{tar_new}'], stdout=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=io.BufferedReader(Counting(p.stdout, 'tar_stream'), 1 << 20), mode='r|*') as a:
            for mem in a:
                if not mem.isfile() or mem.size == 0:
                    continue
                pr = parse_pred(mem.name, tar_new)
                if pr:
                    w, v, mdl, sd, sp, ph = pr
                    k = (w, v, sp, ph)
                    if mdl == MODEL and sd == SEED and k in todo and k not in got:
                        check_file(w, v, sp, ph, a.extractfile(mem).read(), tar_new); got.add(k)
                else:
                    take_aux(mem.name, a.extractfile(mem).read() if mem.size < (1 << 24) else b'')
    except Exception as e:
        log(f'tar {tar_new}: {type(e).__name__}: {e}')
    while p.stdout.read(1 << 20):
        BYTES['tar_stream'] += 0
    p.wait()
    log(f'{Path(tar_new).name}: {len(got) - n0}/{len(todo)} files in {time.time() - t1:.0f}s (cum. {BYTES["tar_stream"] / 1e6:.0f} MB)')

# ---------------------------------------------------------------- 2) loose files (copied to --tmp, checked, deleted)
if loose_keys:
    lst = TMP / '_files_from.txt'
    rel = {k: v[len(SEEDDIR) + 1:] for k, v in loose_keys.items()}
    for k, r_ in rel.items():
        pass
    batch = list(rel.items())
    for i in range(0, len(batch), 40):
        part = dict(batch[i:i + 40])
        files = list(part.values()) + [x.rsplit('/predictions/', 1)[0] + '/run_manifest.json' for x in part.values() if '/predictions/' in x]
        lst.write_text('\n'.join(sorted(set(files))) + '\n', encoding='utf-8')
        dst = TMP / '_loose'
        subprocess.run(RC + ['copy', f'gdrive:{SEEDDIR}', str(dst), '--files-from', str(lst), '--transfers', '2', '--retries', '5'], capture_output=True, text=True)
        for k, r_ in part.items():
            f = dst / r_
            if f.exists() and f.stat().st_size:
                d = f.read_bytes(); BYTES['loose'] += len(d)
                check_file(k[0], k[1], k[2], k[3], d, r_); got.add(k)
            mf = dst / (r_.rsplit('/predictions/', 1)[0] + '/run_manifest.json')
            if mf.exists():
                MANIFESTS.setdefault((k[0], k[1]), json.loads(mf.read_text(encoding='utf-8')))
        shutil.rmtree(dst, ignore_errors=True)

missing = sorted(WANT - got)
log(f'checked {len(got)}/{len(WANT)} prediction files; manifests {len(MANIFESTS)}/{len(RUNS)}; {len(missing)} missing')

# ---------------------------------------------------------------- 3) manifest-level joins (QA12 row counts, QA13)
for r in FILES:
    w, v, sp, ph = r.pop('_k')
    m = MANIFESTS.get((w, v))
    exp = None
    if m:
        exp = m.get('validation_rows') if sp == 'validation' else (m.get('test_rows') or {}).get(ph)
    r['qa12_manifest_rows'] = exp
    r['qa12_rows_equal_manifest'] = (r['n_rows'] == exp) if exp is not None else None
fdf = pd.DataFrame(FILES)

# ---------------------------------------------------------------- 4) upstream manifests: S1 imputation (QA11, QA21 parts 3-5) and S2 augmentation (QA12, QA21)
def fetch_json(rel_dir, inc):
    d = TMP / '_json' / hashlib.md5(rel_dir.encode()).hexdigest()[:8]
    shutil.rmtree(d, ignore_errors=True)
    rclone('copy', f'gdrive:{rel_dir}', str(d), '--include', inc, check=False)
    out = {}
    for f in d.rglob('*'):
        if f.is_file():
            b = f.read_bytes(); BYTES['small_json'] += len(b)
            out[f.relative_to(d).as_posix()] = b
    shutil.rmtree(d, ignore_errors=True)
    return out


def canon_sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


S1, S2 = {}, {}
s1root = f'{TASK}/L1_runs/S1_imputation/complete_seed20260922'
for rel, b in fetch_json(s1root, 'run_manifest.json').items():
    m = re.match(r'(W\d)/(V\d+)/', rel)
    if m:
        d = json.loads(b.decode('utf-8'))
        S1[(m.group(1), m.group(2))] = {'manifest_file_sha256': hashlib.sha256(b).hexdigest(), 'canon_sha256': canon_sha(d), 'd': d}
s2dirs = [x.strip('/') for x in rclone('lsf', f'gdrive:{TASK}/L1_runs/S2_augmentation', '--dirs-only', check=False).splitlines() if x.strip('/') == f'provenance_seed{SEED}']
for sd in s2dirs:
    for rel, b in fetch_json(f'{TASK}/L1_runs/S2_augmentation/{sd}', 'run_manifest.json').items():
        m = re.match(r'(W\d)/(V\d+)/', rel)
        if m:
            S2[(m.group(1), m.group(2))] = json.loads(b.decode('utf-8'))
log(f'upstream manifests: S1 {len(S1)}, S2 {len(S2)} (provenance folders {s2dirs})')

parent = {k: (m.get('parent_pipeline') or None) for k, m in MANIFESTS.items()}
run_rows = []
for (w, v) in RUNS:
    m = MANIFESTS.get((w, v)) or {}
    f = fdf[(fdf.window_id == w) & (fdf.pipeline_id == v)] if len(fdf) else fdf
    r = {'unit': UNIT, 'window_id': w, 'pipeline_id': v, 'n_pred_files': int(len(f)), 'manifest_found': bool(m)}
    # QA13: fields the spec names, and what exists instead
    r['qa13_checkpoint_sha256_in_manifest'] = 'checkpoint_sha256' in m
    r['qa13_preprocessor_sha256_in_manifest'] = 'preprocessor_sha256' in m
    r['qa13_protocol'] = m.get('protocol')
    r['qa13_feature_layout_sha256'] = m.get('feature_layout_sha256')
    r['qa13_aux_member_hashes'] = ';'.join(f'{k}={x[:12]}' for k, x in sorted(EXTRA.get((w, v), {}).items()) if k != 'run_manifest.json')
    r['qa13_n_manifests_for_run'] = 1 if m else 0
    inp = m.get('input_paths') or {}
    r['qa12_eval_inputs_not_train'] = (all('train' not in Path(inp[k]).parts[-3:-1] and 'balanced' not in inp[k] for k in inp if k != 'train') if inp else None)
    r['qa12_train_input_is_balanced'] = ('balanced' in str(inp.get('train'))) if inp else None
    r['model_parent_pipeline'] = m.get('parent_pipeline')
    fl_ = LAYOUT.get((w, v))
    if fl_ is not None and TASK == 'LO':
        names = set(fl_.get('dynamic_bases', [])) | set(fl_.get('static_columns', [])) | set(fl_.get('mask_dynamic_columns', [])) | set(fl_.get('mask_static_columns', [])) | set(fl_.get('mask_phase_bases', []))
        hits = sorted(n for n in names if re.sub(r'_P[1-4]$', '', n) in LO_PROXY)
        r['qa21p5_model_input_names'] = len(names); r['qa21p5_proxy_in_model_input'] = len(hits); r['qa21p5_proxy_names'] = ';'.join(hits)
    # S1 parent: first pipeline of the parent chain that has an S1 imputation manifest
    chain, cur = [], v
    for _ in range(6):
        if (w, cur) in S1:
            break
        nxt = parent.get((w, cur)) if (w, cur) in parent else (S2.get((w, cur)) or {}).get('parent_pipeline')
        if not nxt or nxt == cur:
            cur = None; break
        chain.append(cur); cur = nxt
    else:
        cur = None
    r['s1_pipeline'] = cur if (cur and (w, cur) in S1) else None
    if r['s1_pipeline']:
        d = S1[(w, r['s1_pipeline'])]['d']
        sp = d.get('splits') or {}
        r['qa11_future_imputed_cells_total'] = float(sum(x.get('future_imputed_cells', np.nan) for x in sp.values()))
        r['qa11_s1_splits'] = len(sp)
        r['qa21p3_fit_scope'] = d.get('fit_scope')
        r['qa21p3_fit_rows'] = d.get('fit_rows')
        r['qa21p3_train_rows'] = (sp.get('train') or {}).get('rows')
        r['qa21p3_validation_test_mode'] = (d.get('scaling_contract') or {}).get('validation_test')
        r['qa21p3_scaler_fit_scope'] = (d.get('scaling_contract') or {}).get('fit_scope')
        r['qa13_s1_preprocessor_sha256'] = d.get('preprocessor_sha256')
        r['s1_imputer'] = (d.get('imputer_params') or {}).get('imputer')
        r['s1_manifest_canonical_sha256'] = S1[(w, r['s1_pipeline'])]['canon_sha256']
    s2 = S2.get((w, v))
    if s2:
        r['qa12_s2_validation_test_touched'] = s2.get('validation_test_touched')
        r['qa12_s2_test_prefixes_untouched'] = s2.get('test_prefixes_untouched')
        r['qa12_s2_rows_synthetic'] = s2.get('rows_synthetic')
        r['qa12_s2_algorithm'] = (s2.get('algorithm_config') or {}).get('algorithm')
        p1 = (w, s2.get('parent_pipeline'))
        r['s2_parent_hash_matches_s1'] = (S1[p1]['canon_sha256'] == s2.get('parent_imputation_manifest_sha256')) if p1 in S1 else None
    run_rows.append(r)
rdf = pd.DataFrame(run_rows)

# ---------------------------------------------------------------- 5) verdicts (counts only; PASS/FAIL words only for what was actually run)
def vc(df, col):
    return int(df[col].fillna(0).astype(float).sum()) if len(df) and col in df else None

n_files = len(fdf)
ev = {'unit': UNIT, 'task': TASK, 'model': MODEL, 'seed': SEED, 'wall_seconds': round(time.time() - T0, 1), 'bytes_downloaded': dict(BYTES), 'bytes_downloaded_total': int(sum(BYTES.values())),
      'files_expected': len(WANT), 'files_checked': n_files, 'files_missing': [list(k) for k in missing], 'runs_expected': len(RUNS), 'manifests_found': len(MANIFESTS),
      'prediction_column_sets': [{'columns': list(k), 'n_files': n} for k, n in COLS_SEEN.items()]}
ev['QA07'] = {'rows_checked': int(fdf.n_rows.sum()) if n_files else 0, 'max_abs_sum_err': float(fdf.qa07_max_abs_sum_err.max()) if n_files else None, 'n_sum_viol': vc(fdf, 'qa07_n_sum_viol'),
              'n_nonfinite': vc(fdf, 'qa07_n_nonfinite_prob'), 'n_bad_label': vc(fdf, 'qa07_n_bad_label'), 'n_argmax_mismatch': vc(fdf, 'qa07_n_argmax_mismatch'), 'n_pred_below_max': vc(fdf, 'qa07_n_pred_below_max'), 'n_ties': vc(fdf, 'qa07_n_ties')}
ev['QA12'] = {'files_val_test': n_files, 'synthetic_like_columns_files': int((fdf.qa12_synthetic_like_columns != '').sum()) if n_files else None, 'split_col_not_ok': int((fdf.qa12_split_col_ok == False).sum()) if n_files else None,
              'hash_null_rows': vc(fdf, 'qa12_n_hash_null'), 'hash_duplicate_rows': vc(fdf, 'qa12_n_hash_duplicate'),
              'population_checked_files': int((fdf.qa12_pop_checked == True).sum()) if n_files else None, 'no_salt_match_files': int((fdf.qa12_pop_checked == 'NO_SALT_MATCH').sum()) if n_files else None,
              'rows_not_in_real_population': vc(fdf, 'qa12_n_not_in_population'), 'files_rows_ne_manifest': int((fdf.qa12_rows_equal_manifest == False).sum()) if n_files else None,
              'runs_with_s2_manifest': int(rdf.qa12_s2_validation_test_touched.notna().sum()) if len(rdf) and 'qa12_s2_validation_test_touched' in rdf else 0,
              'runs_s2_validation_test_touched_true': int((rdf['qa12_s2_validation_test_touched'] == True).sum()) if len(rdf) and 'qa12_s2_validation_test_touched' in rdf else 0,
              'runs_train_input_balanced': int((rdf['qa12_train_input_is_balanced'] == True).sum()) if len(rdf) and 'qa12_train_input_is_balanced' in rdf else 0, 'runs_eval_inputs_not_train_false': int((rdf['qa12_eval_inputs_not_train'] == False).sum()) if len(rdf) and 'qa12_eval_inputs_not_train' in rdf else 0}
ev['QA13'] = {'runs': len(rdf), 'runs_with_checkpoint_sha256_field': int(rdf.qa13_checkpoint_sha256_in_manifest.sum()) if len(rdf) else 0, 'runs_with_preprocessor_sha256_field': int(rdf.qa13_preprocessor_sha256_in_manifest.sum()) if len(rdf) else 0,
              'runs_with_s1_preprocessor_sha256': int(rdf.qa13_s1_preprocessor_sha256.notna().sum()) if len(rdf) and 'qa13_s1_preprocessor_sha256' in rdf else 0, 'protocols': sorted(rdf.qa13_protocol.dropna().unique().tolist()) if len(rdf) else []}
ev['QA11'] = {'runs': len(rdf), 'runs_linked_to_s1': int(rdf.s1_pipeline.notna().sum()) if len(rdf) else 0, 'sum_future_imputed_cells_over_linked_runs': float(rdf.qa11_future_imputed_cells_total.sum()) if 'qa11_future_imputed_cells_total' in rdf else None,
              'runs_with_nonzero': int((rdf.qa11_future_imputed_cells_total > 0).sum()) if 'qa11_future_imputed_cells_total' in rdf else None}
ev['QA21'] = {'p1_val_test_overlap_total_keys': vc(fdf, 'qa21p1_val_test_overlap'), 'p1_pairs_checked': int(fdf.qa21p1_val_test_overlap.notna().sum()) if n_files else 0,
              'p3_runs_fit_scope_train': int(rdf.qa21p3_fit_scope.astype(str).str.startswith('TRAIN').sum()) if 'qa21p3_fit_scope' in rdf else 0, 'p3_runs_fit_rows_le_train_rows': int((rdf.qa21p3_fit_rows <= rdf.qa21p3_train_rows).sum()) if 'qa21p3_fit_rows' in rdf else 0,
              'p3_runs_transform_only': int((rdf.qa21p3_validation_test_mode == 'TRANSFORM_ONLY').sum()) if 'qa21p3_validation_test_mode' in rdf else 0,
              'p5_model_input_runs_checked_LO_contract': int(rdf.qa21p5_proxy_in_model_input.notna().sum()) if 'qa21p5_proxy_in_model_input' in rdf else 0, 'p5_runs_with_proxy_in_model_input': int((rdf.qa21p5_proxy_in_model_input > 0).sum()) if 'qa21p5_proxy_in_model_input' in rdf else 0,
              'p2_p4_p5_imputer': 'no artefact of the run holds train-label timestamps / imputer_predictors / is_label_proxy (see README)'}
try:
    import psutil
    ev['peak_rss_mb'] = round(getattr(psutil.Process().memory_info(), 'peak_wset', psutil.Process().memory_info().rss) / 1e6)
except Exception:
    ev['peak_rss_mb'] = None
(OUT / f'{UNIT}_qa_files.csv').write_text(fdf.drop(columns=[c for c in ('columns',) if False]).to_csv(index=False), encoding='utf-8')
(OUT / f'{UNIT}_qa_runs.csv').write_text(rdf.to_csv(index=False), encoding='utf-8')
(OUT / f'{UNIT}_qa_evidence.json').write_text(json.dumps(ev, indent=1, default=str), encoding='utf-8')
shutil.rmtree(TMP / '_json', ignore_errors=True); shutil.rmtree(TMP / '_loose', ignore_errors=True)
try:
    (TMP / '_files_from.txt').unlink()
except OSError:
    pass
log(f'done in {ev["wall_seconds"]}s, downloaded {ev["bytes_downloaded_total"] / 1e6:.0f} MB; evidence: {OUT / (UNIT + "_qa_evidence.json")}')
sys.exit(0 if not missing else 3)
