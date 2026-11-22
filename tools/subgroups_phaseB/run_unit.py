"""Run one unit (task, model, seed) of phase B end to end: fetch the stored sample-level predictions of its 51 runs from Drive into a temporary folder (loose files when the run has them,
otherwise by streaming the tar), detect the prediction salt, build the subgroup facts with build_subgroup_facts.py, write the unit README, upload the unit folder, delete the temporary folder.
usage: run_unit.py CQ RNN 42 [--tmp DIR] [--out DIR] [--no-upload]"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path

import pandas as pd

import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1] / 'seed43_44_pipeline'))
from tempo_paths import A44, M14C, REPO, WORK

ROOT_ID = '1GWiedVROrxp8jvGbd0xmvVmWriZUkpOn'
RC = ['rclone', '--drive-root-folder-id', ROOT_ID]
HERE = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument('task'); ap.add_argument('model'); ap.add_argument('seed', type=int)
ap.add_argument('--tmp', default='D:/phaseB_tmp')
ap.add_argument('--out', default=f'{WORK}/phaseB/units')
ap.add_argument('--no-upload', action='store_true')
args = ap.parse_args()
TASK, MODEL, SEED = args.task, args.model, args.seed
UNIT = f'{TASK}_{MODEL}_seed{SEED}'
tmp = Path(args.tmp) / UNIT
out = Path(args.out) / f'{UNIT}_subgroups_20261121'
LOG = Path(args.out) / 'run_units.log'
Path(args.out).mkdir(parents=True, exist_ok=True)


def log(m):
    with LOG.open('a', encoding='utf-8') as h:
        h.write(time.strftime('%F %T ') + f'[{UNIT}] ' + m + '\n')
    print(f'[{UNIT}] {m}', flush=True)


SALTS = [f'{REPO}/CQ/resuilt/private/.vastai_cq_prediction_salt', f'{REPO}/CQ/resuilt/private/.cq_matched_replay_prediction_salt', f'{REPO}/downloads/private/cq_patchtst_prediction_salt',
         f'{REPO}/downloads/private/lo_grid_prediction_salt', f'{REPO}/downloads/private/lo_replay_protocol27_prediction_salt', f'{REPO}/LO/resuilt/lo_static_ablation_20261019/.ablation_prediction_salt']
CQR, LOR = f'{REPO}/CQ/resuilt', f'{REPO}/LO/resuilt'
AS = f'{A44}/asm_inputs/seed43'
F44 = f'{A44}/facts44'


def facts_files():
    t, m, s = TASK, MODEL, SEED
    if s == 42:
        if t == 'CQ':
            if m in ('RNN', 'LSTM', 'GRU', 'BILSTM'):
                return [f'{M14C}/cq_r4_with_regime_macro.parquet']
            if m == 'PATCHTST':
                return [f'{CQR}/cq_patchtst_v0_v6_full_facts_20261103_r2/sanity_components.csv', f'{CQR}/cq_patchtst_v7_v16_full_facts_20261109_r2/sanity_components.csv']
            return [f'{CQR}/cq_mantis_v2_v0_v16_full_facts_20261109_r3/sanity_components.csv']
        if m in ('RNN', 'LSTM', 'GRU', 'BILSTM'):
            return [f'{M14C}/lo_static_v2_facts_no_confusion.parquet']
        if m == 'PATCHTST':
            return [f'{LOR}/lo_patchtst_v0_v16_full_facts_20261109_r2/sanity_components.csv']
        return [f'{LOR}/lo_mantis_v2_v0_v16_full_facts_20261110/sanity_components.csv']
    base = AS if s == 43 else F44
    suf = '' if s == 43 else '_v0_v16_seed44'
    if m in ('RNN', 'LSTM', 'GRU', 'BILSTM'):
        return [f'{base}/{t}_f1_recurrent{suf}/{m}/sanity_components.csv']
    if m == 'PATCHTST':
        return [f'{base}/{t}_patchtst{suf}/sanity_components.csv']
    return [f'{base}/{t}_mantis_v2{suf}/sanity_components.csv']


# ---- locate the predictions
cat = pd.read_parquet(f'{WORK}/phaseB/pred_files_unified.parquet')
cat = cat[(cat.task == TASK) & (cat.model_name == MODEL) & (cat.seed == SEED)]
mp = pd.read_csv(f'{WORK}/tree/s3_seed_mapping.csv', usecols=['old_path', 'new_path']).set_index('old_path').new_path.to_dict()
TRUNCATED_TARS = {'lo_patchtst_seed44_V2_host40077.tar', 'LO_static_v2_BILSTM.tar'}
PREFER = ['primary/release=LO_STATIC_V2', 'primary/family=PATCHTST', 'cq_recurrent_batch2048_seed42', 'cq_lstm_batch2048_full', 'cq_rnn_historical_layout_batch2048', 'mantis_v2_seed', 'staging_incoming']
DENY = ['pilot', 'determinism', 'replay', 'ablation', '/vastai/', 'vastai_runs', 'matched_historical', 'baseline_drive', 'nvml_historical', 'cohort_audit', 'host_backups']


def rank(path):
    """official packages first (the ones the accepted facts were built from), pilots/replays/ablations last"""
    if any(d in path for d in DENY):
        return 2
    return 0 if any(p_ in path for p_ in PREFER) else 1
need = {}   # (W, V, split, phase) -> list of sources
for r in cat.itertuples():
    old = r.path if r.kind == 'tar' else f'{TASK}/L1_runs/S3_model/{r.path}'
    new = mp.get(old)
    if new is None:
        continue
    need.setdefault((r.window_id, r.pipeline_id, r.split.lower(), r.phase_id), []).append((r.kind, new, r.member if 'member' in cat.columns else None))
if len(need) != 51 * 8:
    log(f'ABORT: catalog gives {len(need)} (run, split, phase) files instead of 408'); sys.exit(2)

tmp.mkdir(parents=True, exist_ok=True)
local = lambda W, V, sp, P: tmp / W / V / f'{sp}_{P}.parquet'


def parse(name, tar_new):
    m = re.search(r'(?:(CQ|LO)/)?(W\d)/(V\d+)/([A-Z][A-Z0-9_]*)/seed=(\d+)/predictions/(validation|test)_(P\d)\.parquet$', name)
    if m:
        return m.group(2), m.group(3), m.group(4), int(m.group(5)), m.group(6), m.group(7)
    m = re.search(r'runs/(W\d)/(V\d+)/predictions/(validation|test)_(P\d)\.parquet$', name)
    if m:
        sd = re.search(r'seed[_=]?(\d+)', tar_new.split('S3_model/')[-1])
        return m.group(1), m.group(2), 'MANTIS_V2', int(sd.group(1)) if sd else None, m.group(3), m.group(4)
    return None


want = {k for k in need}
got = set()
# 1) loose files (prefer: no streaming)
loose = {}
for k, srcs in need.items():
    cands = sorted((x for x in srcs if x[0] == 'loose'), key=lambda x: rank(x[1]))
    if cands and rank(cands[0][1]) < 2:      # a loose copy of a denied (pilot/replay/ablation) package is never used when a tar of an official package exists
        loose[k] = cands[0][1]
    elif cands and not any(x[0] == 'tar' and rank(x[1]) < 2 for x in srcs):
        loose[k] = cands[0][1]
if loose:
    listing = tmp / '_files_from.txt'
    rel = {k: v.split('L1_runs/S3_model/')[-1] for k, v in loose.items()}
    listing.write_text('\n'.join(rel.values()) + '\n', encoding='utf-8')
    dst = tmp / '_loose'
    subprocess.run(RC + ['copy', f'gdrive:{TASK}/L1_runs/S3_model', str(dst), '--files-from', str(listing), '--transfers', '8', '-q'], capture_output=True)
    for k, r_ in rel.items():
        f = dst / r_
        if f.exists() and f.stat().st_size > 0:
            L = local(*k); L.parent.mkdir(parents=True, exist_ok=True); shutil.move(str(f), str(L)); got.add(k)
# 2) tars for the rest
rest = want - got
tars = {}
for k in rest:
    best = sorted((x for x in need[k] if x[0] == 'tar' and Path(x[1]).name not in TRUNCATED_TARS), key=lambda x: rank(x[1]))
    if not best:      # last resort: a truncated archive still holds the runs written before its cut (e.g. LO PatchTST seed 44 W1 V2 is complete in lo_patchtst_seed44_V2_host40077.tar)
        best = sorted((x for x in need[k] if x[0] == 'tar'), key=lambda x: rank(x[1]))
    if best:
        tars.setdefault(best[0][1], set()).add(k)
for new, keys in sorted(tars.items(), key=lambda x: -len(x[1])):
    if not (keys - got):
        continue
    p = subprocess.Popen(RC + ['cat', f'gdrive:{new}'], stdout=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=p.stdout, mode='r|*') as a:
            for mem in a:
                if not mem.isfile() or mem.size == 0:
                    continue
                pr = parse(mem.name, new)
                if not pr:
                    continue
                W, V, mdl, sd, sp, P = pr
                k = (W, V, sp, P)
                if mdl == MODEL and sd == SEED and k in keys and k not in got:
                    L = local(*k); L.parent.mkdir(parents=True, exist_ok=True)
                    with L.open('wb') as h:
                        shutil.copyfileobj(a.extractfile(mem), h)
                    got.add(k)
    except Exception as e:
        log(f'tar {new}: {e}')
    while p.stdout.read(1 << 20):
        pass
    p.wait()
missing = want - got
log(f'fetched {len(got)}/{len(want)} prediction files')
if missing:
    log(f'ABORT: missing {sorted(missing)[:5]}'); sys.exit(3)

# ---- salts are detected per prediction file inside the builder
salt_files = [sf for sf in SALTS if Path(sf).exists()]

# ---- build
cmd = [sys.executable, str(HERE / 'build_subgroup_facts.py'), '--task', TASK, '--model', MODEL, '--seed', str(SEED), '--pred-glob', f'{tmp.as_posix()}/{{W}}/{{V}}/{{split}}_{{P}}.parquet',
       '--facts', *facts_files(), '--salt-files', *salt_files, '--out', str(out)]
res = subprocess.run(cmd, capture_output=True, text=True)
if res.returncode != 0:
    log('ABORT: builder failed: ' + res.stderr[-400:]); sys.exit(5)
qa = json.loads((out / 'summary.json').read_text(encoding='utf-8'))
log(f'builder status {qa["status"]}, rows {qa["rows"]}, slice_status {qa["slice_status"]}, all_row_mismatch {len(qa["all_row_mismatch"])}, reported-only diffs {qa.get("reported_only_max_abs_diff")}')

# ---- README
df = pd.read_parquet(out / 'subgroup_components.parquet')
two = qa['two_class_cells']
small = int(df.drop_duplicates(['window_id', 'eval_split', 'phase_id', 'subgroup_axis', 'subgroup_value']).small_subgroup_flag.sum()) if 'small_subgroup_flag' in df else None
(out / 'README.md').write_text(f"""# Facts of the four seen/unseen subgroups, {TASK} {MODEL} seed {SEED} (appendix; the accepted fact package is not modified)

- Rows: {qa['rows']} (51 runs x 2 splits x 4 phases x 4 subgroups); slice_status: {qa['slice_status']}.
- Rule `seen_v1_train_partition_only`; join by `enrollment_id_hash` = sha256(salt|enrollment_id) with the salt detected per prediction file (families used: {qa.get('salt_families_used')}; values not exported); files without a matching salt: {len(qa.get('no_salt_match', []))}; QA15 violations: {qa['qa15_violations']}; hash unmatched: {qa['hash_unmatched']}.
- Columns: slice-level columns recomputed on the slice; run- and cell-level columns (s_eff, s_leak, s_leak_probe_auc, probe_*, model_tier, variant_role, run_purpose ...) copied from the accepted ALL row of the unit. Columns of the accepted ALL row missing here: {qa['columns_of_accepted_ALL_row_missing_in_subgroup_rows']}.
- Self-check: ALL row recomputed from the predictions equals the accepted facts on every common numeric column within 1e-12 except log_loss (reported only): mismatches beyond 1e-12 = {len(qa['all_row_mismatch'])}; largest differences on the report-only metrics {qa.get('reported_only_max_abs_diff')} (log_loss: the accepted facts clip probabilities at 1e-7, the current function at 1e-12; pr_auc_macro: older implementation). Status: {qa['status']}. SEEN + UNSEEN = ALL confusion matrices: {len(qa['partition_failures'])} failures.
- Slices with only two classes present (values kept as the function returns them): {len(two)} (window/split/phase/subgroup cells) {two[:40]}.
- Subgroup cells flagged `small_subgroup_flag` (n < 30 or any class support < 5): {small}.
- Builder commit {qa['builder']['repo_commit']}, builder sha256 {qa['builder']['sha256']}.
""", encoding='utf-8')
files = [p for p in sorted(out.iterdir()) if p.name != 'sha256sums.txt']
(out / 'sha256sums.txt').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in files), encoding='utf-8')
if not args.no_upload and qa['status'].startswith('PASS'):
    dest = f'gdrive:cross_task_meta/work_in_progress/subgroups_phaseB_20261121/{out.name}'
    subprocess.run(RC + ['copy', str(out), dest, '-q'], capture_output=True)
    chk = subprocess.run(RC + ['check', str(out), dest, '--one-way'], capture_output=True, text=True)
    log('upload ' + ('OK' if chk.returncode == 0 else 'CHECK FAILED ' + chk.stderr[-200:]))
if not qa['status'].startswith('PASS'):
    log('NOT UPLOADED: status ' + qa['status'] + f" no_salt_match={len(qa.get('no_salt_match', []))} hash_unmatched={qa['hash_unmatched']} all_row_mismatch={len(qa['all_row_mismatch'])} files_missing={len(qa['files_missing'])}")
shutil.rmtree(tmp, ignore_errors=True)
log('done, temp folder removed')
