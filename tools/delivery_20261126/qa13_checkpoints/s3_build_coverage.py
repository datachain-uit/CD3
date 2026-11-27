"""Step 3: build qa13_checkpoint_coverage_by_run.csv and qa13_coverage_summary_by_unit.csv from
 (1) work_pred_sources_by_run.csv   accepted package of each run (step 1)
 (2) work_list_{CQ,LO}.json         Drive listing of the files of S3_model (names, sizes)
 (3) ckpt_{CQ,LO}.json, work_hash_probe_CQ.json   Drive listings with hashes (sha256) of loose model.pt / probe_head.pt / channel adapters
 (4) tar_scan/*.json                streamed archive members with sha256 (step 2)
 (5) qa5 first-pass runs csv        12-hex prefixes of model.pt taken while streaming the archive that holds the predictions; S1 preprocessor sha256"""
import os, json, re, glob
from pathlib import Path
import pandas as pd
OUT = Path(os.environ.get('QA13_DIR', '.')); W5 = Path(os.environ['QA5_FULL_DIR'])
CK = re.compile(r'(\.(pt|pth|ckpt|safetensors)$)|(^checkpoint(?!_selection))')
AD = re.compile(r'^channel_adapter\.(json|npz)$')
d = pd.read_csv(OUT / 'work_pred_sources_by_run.csv', keep_default_na=False)
SM = '/L1_runs/S3_model/'

# ---- loose files: key 'CQ/seed=42/...' (task + path inside S3_model)
loose_names, loose_sha = {}, {}
for T in ('CQ', 'LO'):
    for x in json.load(open(OUT / f'work_list_{T}.json')):
        loose_names[f'{T}/{x["Path"]}'] = x['Size']
    for fn in (OUT / f'drive_hash_listing_loose_model_pt_{T}.json', OUT / 'work_hash_probe_CQ.json'):
        if T == 'LO' and fn.name.startswith('work_hash'):
            continue
        for x in json.load(open(fn)):
            loose_sha[f'{T}/{x["Path"]}'] = (x['Hashes'].get('sha256'), x['Hashes'].get('md5'), x['Size'])


def short(p):          # 'CQ/L1_runs/S3_model/seed=42/...' -> 'CQ/seed=42/...'
    return p.replace(SM, '/', 1)


def rel(p):            # Drive-relative path used in the deliverable
    return p.replace(SM, '/', 1)


_cache = {}


def loose_files(rundir):
    pre = rundir + '/'
    if pre not in _cache:
        _cache[pre] = [p for p in loose_names if p.startswith(pre)]
    return _cache[pre]


# ---- scanned archives
tars = {}
for f in glob.glob(str(OUT / 'tar_scan' / '*.json')):
    j = json.load(open(f))
    if j['status'] == 'OK':
        tars[j['tar']] = j


def tar_run_members(j, w, v, model, seed):
    out, ads = [], []
    for name, size, sha in j['members']:
        b = name.rsplit('/', 1)[-1]
        m = re.search(r'(?:^|/)(W\d)/(V\d+)/(?:([A-Z][A-Z0-9_]*)/seed=(\d+)/)?', name)
        if m:
            if (m.group(1), m.group(2)) != (w, v):
                continue
            if m.group(3) and (m.group(3) != model or int(m.group(4)) != seed):
                continue
        else:
            m2 = re.search(r'(?:^|/)adapters/(W\d)/', name)
            if m2 and m2.group(1) == w and AD.match(b):
                ads.append((name, size, sha))
            continue
        if CK.search(b):
            out.append((name, size, sha))
        elif AD.match(b):
            ads.append((name, size, sha))
    return out, ads


# ---- first QA pass
qa = {}
for f in glob.glob(str(W5 / '*_qa_runs.csv')):
    q = pd.read_csv(f, dtype=str, keep_default_na=False)
    for r in q.itertuples():
        qa[(r.unit, r.window_id, r.pipeline_id)] = (r.qa13_aux_member_hashes, r.qa13_s1_preprocessor_sha256, r.qa13_n_manifests_for_run)


def srcinfo(kind, pkg, w, v, model, seed):
    """-> (checkpoint files [(name,size,sha,md5,hash_kind)], adapters [(name,size,sha)], scanned)"""
    if kind == 'loose':
        rd = short(pkg)
        fs = loose_files(rd)
        ck = []
        for p in fs:
            b = p.rsplit('/', 1)[-1]
            if CK.search(b):
                s, m5, sz = loose_sha.get(p, (None, None, loose_names[p]))
                ck.append((p[len(rd) + 1:], sz, s, m5, 'sha256_drive_listing' if s else ('md5_drive_listing' if m5 else 'none')))
        ad = [(p[len(rd) + 1:], loose_names[p], loose_sha.get(p, (None,))[0]) for p in fs if AD.match(p.rsplit('/', 1)[-1])]
        return ck, ad, True
    j = tars.get(pkg)
    if j is None:
        return [], [], False
    ck, ad = tar_run_members(j, w, v, model, seed)
    return [(n, s, h, None, 'sha256_tar_stream' if h else 'none') for n, s, h in ck], ad, True


def pred_sizes(kind, pkg, w, v, model, seed):
    out = {}
    if kind == 'loose':
        rd = short(pkg)
        for p in loose_files(rd):
            m = re.search(r'/predictions/(validation|test)_(P\d)\.parquet$', p)
            if m: out[m.group(1) + m.group(2)] = loose_names[p]
        return out
    j = tars.get(pkg)
    if j is None: return out
    for name, size, _ in j['members']:
        m = re.search(r'(?:^|/)(W\d)/(V\d+)/(?:([A-Z][A-Z0-9_]*)/seed=(\d+)/)?(?:.*/)?predictions/(validation|test)_(P\d)\.parquet$', name)
        if m and (m.group(1), m.group(2)) == (w, v) and (not m.group(3) or (m.group(3) == model and int(m.group(4)) == seed)):
            out[m.group(5) + m.group(6)] = size
    return out


rows = []
for r in d.itertuples():
    unit = f'{r.task}_{r.model}_seed{r.seed}'
    pk = r.packages.split('|')
    kind, pkg = r.kinds.split('|')[0], pk[0]
    ck, ad, scanned = srcinfo(kind, pkg, r.window, r.pipeline, r.model, r.seed) if len(pk) == 1 else ([], [], False)
    aux, s1pp, nman = qa.get((unit, r.window, r.pipeline), ('', '', ''))
    mm = re.search(r'model\.pt=([0-9a-f]{12})', aux)
    prefix = mm.group(1) if mm else ''
    alts = []
    if r.other_sources:
        for s in r.other_sources.split('|'):
            rk, k2, p2 = s.split(':', 2)
            alts.append((int(rk), k2, p2))
    tied = [(k2, p2) for rk, k2, p2 in alts if rk <= r.pick_rank]
    lower_loose = [(k2, p2) for rk, k2, p2 in alts if rk > r.pick_rank and k2 == 'loose']
    tied_h, tied_unknown, tied_ck = [], 0, []
    for k2, p2 in tied:
        c2, _, sc2 = srcinfo(k2, p2, r.window, r.pipeline, r.model, r.seed)
        if not sc2:
            tied_unknown += 1
            continue
        tied_h.append(tuple(sorted(str(h) for _, _, h, _, _ in c2)) if c2 else ('NOCKPT',))
        if c2:
            tied_ck.append((k2, p2, c2))
    low_h = []
    for k2, p2 in lower_loose:
        c2, _, _ = srcinfo(k2, p2, r.window, r.pipeline, r.model, r.seed)
        low_h.append(tuple(sorted(str(h) for _, _, h, _, _ in c2)) if c2 else ('NOCKPT',))
    own = tuple(sorted(str(h) for _, _, h, _, _ in ck)) if ck else ('NOCKPT',)
    own_ck = bool(ck)
    amb = ''
    ckpkg = rel(pkg)
    if not ck and tied_ck and len(pk) == 1:       # the package holding the predictions has no checkpoint file: use the same-rank package that has one
        hs = {tuple(sorted(str(h) for _, _, h, _, _ in c2)) for _, _, c2 in tied_ck}
        if len(hs) == 1:
            k2, p2, c2 = tied_ck[0]
            ck = c2
            ckpkg = rel(p2)
            ps_own, ps_alt = pred_sizes(kind, pkg, r.window, r.pipeline, r.model, r.seed), pred_sizes(k2, p2, r.window, r.pipeline, r.model, r.seed)
            same = 'sizes of the 8 prediction files equal' if ps_own and ps_own == ps_alt else ('prediction files not comparable' if not ps_alt else 'prediction file sizes DIFFER')
            amb = f'SIBLING_PACKAGE: no checkpoint beside the predictions; identical checkpoint in {len(tied_ck)} same-rank package(s) ({same})'
            tied_h = []
        else:
            amb = f'AMBIGUOUS: same-rank packages hold {len(hs)} different checkpoints'
            tied_h = []
    if amb:
        pass
    elif len(pk) > 1:
        amb = 'AMBIGUOUS: predictions of the run come from several packages'
    elif tied:
        if ck and any(h != own and h != ('NOCKPT',) for h in tied_h):
            amb = f'AMBIGUOUS: {len(tied)} further package(s) of the same rank hold the run with a different checkpoint hash'
        elif tied_unknown:
            amb = f'UNRESOLVED: {tied_unknown} further package(s) of the same rank not scanned'
        elif not ck:
            amb = 'NO_CHECKPOINT_FOUND: neither the package of the predictions nor the same-rank packages hold a checkpoint file'
        else:
            amb = f'DUPLICATE_IDENTICAL: {len(tied)} further package(s) of the same rank hold the run with the same checkpoint hash'
    low_note = ''
    if low_h:
        low_note = 'lower-ranked loose copies: ' + ('same hash' if all(h == own for h in low_h) else 'differing hash') + f' ({len(lower_loose)})'
    n = len(ck)
    first = ck[0] if ck else ('', '', '', '', 'none')
    hk, hv = first[4], (first[2] or first[3] or '')
    src = {'sha256_drive_listing': 'Drive listing of the loose file (rclone lsjson --hash)', 'sha256_tar_stream': 'archive streamed once, member hashed (sha256)',
           'md5_drive_listing': 'Drive listing (md5 only)', 'none': ''}[hk]
    nfiles, cname = n, first[0]
    if not scanned and kind == 'tar' and prefix:       # archive not scanned: only the 12-hex prefix taken during the first QA pass
        nfiles, cname, hk, hv = '', 'model.pt', 'sha256_prefix12_qa_first_pass', prefix
        src = 'first QA pass (12 hex of the sha256 of the member while streaming the archive; member count not verified)'
    qa_agree = ''
    if prefix and len(hv) == 64:
        qa_agree = 'yes' if hv.startswith(prefix) else 'NO'
    rows.append(dict(task=r.task, model=r.model, seed=r.seed, window=r.window, pipeline=r.pipeline,
                     n_checkpoint_files=nfiles, checkpoint_name=cname, hash_kind=hk, hash_value=hv,
                     checkpoint_package=ckpkg, package=rel(pkg) if len(pk) == 1 else '|'.join(rel(p) for p in pk), package_kind=kind, source_of_hash=src, ambiguity=amb,
                     other_packages_note=low_note, adapter_files=';'.join(f'{a[0]}={a[2]}' if a[2] else a[0] for a in ad),
                     all_checkpoint_like_files=';'.join(c[0] for c in ck), qa_prefix12=prefix, qa_prefix_agrees_with_full=qa_agree,
                     n_manifests_for_run=nman, s1_preprocessor_sha256=s1pp.replace('sha256:', '')))
o = pd.DataFrame(rows)
# S1 preprocessor sha256 is a function of (task, window, pipeline) only (checked: one value per triple across all models and seeds); fill the runs whose first-pass csv has none
tri = o[o.s1_preprocessor_sha256 != ''].groupby(['task', 'window', 'pipeline']).s1_preprocessor_sha256.agg(['nunique', 'first'])
assert (tri['nunique'] == 1).all()
o['s1_preprocessor_source'] = 'first QA pass (per run)'
miss = o.s1_preprocessor_sha256 == ''
o.loc[miss, 's1_preprocessor_sha256'] = [tri['first'].get((t, w, p), '') for t, w, p in zip(o.task[miss], o.window[miss], o.pipeline[miss])]
o.loc[miss, 's1_preprocessor_source'] = 'same (task, window, pipeline) in the other units (single value)'
first_cols = ['task', 'model', 'seed', 'window', 'pipeline', 'n_checkpoint_files', 'checkpoint_name', 'hash_kind', 'hash_value', 'package', 'source_of_hash', 'ambiguity', 's1_preprocessor_sha256']
o = o[first_cols + [c for c in o.columns if c not in first_cols]]
o.to_csv(OUT / 'qa13_checkpoint_coverage_by_run.csv', index=False, lineterminator='\n')


def cat(r):
    if r.ambiguity.startswith(('AMBIGUOUS', 'UNRESOLVED')):
        return 'ambiguous'
    if r.hash_kind == 'sha256_prefix12_qa_first_pass':
        return 'prefix_only'
    if r.n_checkpoint_files != 1:
        return 'zero_or_multiple'
    return {'sha256_drive_listing': 'sha256', 'sha256_tar_stream': 'sha256', 'md5_drive_listing': 'md5_only'}.get(r.hash_kind, 'none')


o['cat'] = o.apply(cat, axis=1)
o['unit'] = o.task + '_' + o.model + '_seed' + o.seed.astype(str)
s = o.pivot_table(index='unit', columns='cat', values='window', aggfunc='size', fill_value=0)
cols = ['sha256', 'md5_only', 'prefix_only', 'none', 'ambiguous', 'zero_or_multiple']
for c in cols:
    if c not in s:
        s[c] = 0
s['runs'] = s[cols].sum(axis=1)
s['sib'] = o[o.ambiguity.str.startswith('SIBLING_PACKAGE')].groupby('unit').size().reindex(s.index).fillna(0).astype(int)
s = s[['runs'] + cols + ['sib']].reset_index()
s.columns = ['unit', 'runs', 'runs_one_checkpoint_sha256', 'runs_one_checkpoint_md5_only', 'runs_prefix12_only', 'runs_no_checkpoint_hash', 'runs_ambiguous', 'runs_zero_or_several_checkpoint_files', 'of_which_sha256_checkpoint_taken_from_sibling_package']
s.to_csv(OUT / 'qa13_coverage_summary_by_unit.csv', index=False, lineterminator='\n')
print(s.to_string())
print(s.iloc[:, 1:].sum())
