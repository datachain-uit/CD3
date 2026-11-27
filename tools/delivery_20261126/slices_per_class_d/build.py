import os as _os
# Machine roots come from environment variables (no machine paths in the repository).
REPO = _os.environ.get('TEMPO_REPO_ROOT', '.')
WORK = _os.environ.get('TEMPO_WORK_ROOT', '.')
AUDIT44 = _os.environ.get('TEMPO_AUDIT44_ROOT', '.')
WORKD = _os.environ.get('TEMPO_DELIVERY_WORK_ROOT', '.')
import sys, json, hashlib, datetime, re
sys.path.insert(0, f'{WORKD}/code')
from pathlib import Path
import pyarrow as pa, pyarrow.parquet as pq, pyarrow.compute as pc
import pandas as pd
import registry

BS = chr(92)
OUT = Path(f'{WORKD}/l2_slices_and_per_class_3seeds_20261126')
OUT.mkdir(parents=True, exist_ok=True)
MODELS = ['RNN', 'LSTM', 'GRU', 'BILSTM', 'PATCHTST', 'MANTIS_V2']
TASKS = ['CQ', 'LO']; SEEDS = [42, 43, 44]
TABLES = registry.TABLES
OUTNAME = {'evaluation_slices': 'evaluation_slices', 'metrics_per_class': 'metrics_per_class',
           'bootstrap_metrics_per_class': 'bootstrap_metrics_per_class', 'cohort_slice_status': 'cohort_slice_status'}
EXPECT = {'evaluation_slices': 1224, 'metrics_per_class': 1224, 'bootstrap_metrics_per_class': 3672, 'cohort_slice_status': 1632}

def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(8 << 20), b''):
            h.update(b)
    return h.hexdigest()
def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(8 << 20), b''):
            h.update(b)
    return h.hexdigest()

inv = pd.read_parquet(f'{WORK}/tree/inventory_all.parquet')
inv_md5 = {}
for r in inv.itertuples():
    inv_md5.setdefault(str(r.md5), []).append(r.path)
drive_list = {}
for line in open(f'{WORKD}/drive_full_list.txt', encoding='utf-8'):
    line = line.rstrip('\n')
    if ';' in line:
        p, s = line.rsplit(';', 1)
        drive_list[p] = int(s)

rel = json.load(open(f'{REPO}/CQ/resuilt/meta_release_CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2/meta_release_manifest.json'))['inputs_sha256']
acc = {v['path'].replace(BS, '/'): v['sha256'] for v in rel.values()}

def drive_check(local, drive_rel_path):
    """size check against current Drive listing and md5 against the 21/11 inventory (any location)."""
    r = {}
    if drive_rel_path in drive_list:
        r['drive_listing_size_match'] = (drive_list[drive_rel_path] == Path(local).stat().st_size)
    else:
        r['drive_listing_size_match'] = None
    m = md5(local)
    hits = inv_md5.get(m, [])
    r['md5_in_inventory_20261121'] = bool(hits)
    r['md5_inventory_paths'] = hits[:2]
    return r

def pkg_sha_lines(d):
    p = Path(d) / 'sha256sums.txt'
    out = {}
    if p.exists():
        for ln in p.read_text(encoding='utf-8', errors='replace').splitlines():
            m = re.match(r'^([0-9a-f]{64})\s+\*?(.+)$', ln.strip())
            if m: out[m.group(2).strip().replace(BS, '/')] = m.group(1)
    return out

CQ_RC = f'{REPO}/CQ/resuilt/'
R4S = Path(CQ_RC + 'cq_r4_slices_reconciled_20261103/cq_evaluation_slices.parquet')
R4D = Path(f'{WORKD}/src/CQ/seed42/F1_recurrent/cq_recurrent_allfamilies_grid_r4_20261023')
R4_SLICE_PKG = 'CQ/L2_facts/model_facts/seed=42/other_exports/cq_r4_slices_reconciled_20261103'
R4_PC_PKG = 'CQ/L2_facts/model_facts/seed=42/F1_recurrent/cq_recurrent_allfamilies_grid_r4_20261023'
LOA = Path(f'{REPO}/CQ/resuilt/input/results/R21_evidence_20261031/LO/audit_seed42')
LO_P = 'LO/L1_runs/S3_model/seed=42/primary/release=LO_STATIC_V2/lo_static_v2_seed42_20261026/'

def lo_src(m):
    if m == 'BILSTM':
        return LOA / 'audits_seed42/LO/BILSTM/seed=42', LO_P + 'audits/closure_seed42/audits_seed42/LO/BILSTM/seed=42'
    return LOA / f'{m}/LO/{m}/seed=42', LO_P + f'models/{m}/audits/LO/{m}/seed=42'

def sources(task, model, seed, table):
    """-> list of dict(path, package, schema_version, filter_model(bool), drive_path)"""
    u = UNITS.get((task, model, seed), {})
    if seed == 42 and model in ('RNN', 'LSTM', 'GRU', 'BILSTM'):
        if task == 'CQ':
            if table == 'evaluation_slices':
                return [dict(path=R4S, package=R4_SLICE_PKG, sv='cq_r4_reconciled_slices_v1', fm=True, dp=R4_SLICE_PKG + '/cq_evaluation_slices.parquet')]
            if table == 'metrics_per_class':
                return [dict(path=R4D / 'cq_metrics_per_class_long.parquet', package=R4_PC_PKG, sv='cq_r4_grid_per_class_long_v1', fm=True, dp=R4_PC_PKG + '/cq_metrics_per_class_long.parquet')]
            if table == 'bootstrap_metrics_per_class':
                return [dict(path=R4D / 'cq_bootstrap_metrics_per_class_long.parquet', package=R4_PC_PKG, sv='cq_r4_grid_bootstrap_long_v1', fm=True, dp=R4_PC_PKG + '/cq_bootstrap_metrics_per_class_long.parquet')]
            return None
        d, dp = lo_src(model)
        if table == 'cohort_slice_status':
            return None
        sv = {'evaluation_slices': 'lo_static_v2_audit_slices_v1', 'metrics_per_class': 'lo_static_v2_audit_per_class_v1', 'bootstrap_metrics_per_class': 'lo_static_v2_audit_bootstrap_v1'}[table]
        return [dict(path=d / f'{table}.parquet', package=LO_P.rstrip('/'), sv=sv, fm=False, dp=f'{dp}/{table}.parquet')]
    out = []
    for d, pkg in u.get('dirs', []):
        out.append(dict(path=Path(d) / f'{table}.parquet', package=pkg, sv='l2_facts_full_package_v1', fm=False, dp=f'{pkg}/{table}.parquet', pkgdir=Path(d)))
    return out

UNITS = registry.units()
not_avail_reason = {}
manifest_units = []
per_table_tables = {t: [] for t in TABLES}
col_types = {t: {} for t in TABLES}   # col -> {type str: [units]}
sig_registry = {t: {} for t in TABLES}
problems = []

for task in TASKS:
    for model in MODELS:
        for seed in SEEDS:
            key = (task, model, seed)
            entry = dict(task=task, model_name=model, seed=seed, tables={})
            u = UNITS.get(key) or dict(dirs=[], accepted_sanity=None, sanity_in=None)
            # accepted-package verification
            ver = {}
            if seed == 42 and model in ('PATCHTST', 'MANTIS_V2'):
                chk = []
                for d, pkg in u.get('dirs', []):
                    sp = Path(d) / 'sanity_components.csv'
                    exp = acc.get(str(sp).replace(BS, '/'))
                    got = sha(sp)
                    chk.append(dict(package=pkg, sanity_components_sha256=got, release_inputs_sha256=exp, match=(exp == got)))
                ver['sanity_components_vs_release_inputs_sha256'] = chk
            elif seed in (43, 44):
                sp = u['sanity_in']; exp = acc.get(str(u['accepted_sanity']).replace(BS, '/')); got = sha(sp)
                ver['sanity_components_vs_release_inputs_sha256'] = [dict(package=u['dirs'][0][1], sanity_components_sha256=got, release_inputs_sha256=exp, match=(exp == got))]
            else:
                ver['note'] = ('seed 42 F1 release input is a derived export (%s); verified by ALL-row comparison, see check_all_rows' %
                               ('cq_r4_with_regime_macro.parquet' if task == 'CQ' else 'lo_static_v2_facts_no_confusion.parquet'))
            entry['accepted_check'] = ver
            for ch in ver.get('sanity_components_vs_release_inputs_sha256', []):
                if not ch['match']: problems.append(f'{key}: sanity sha mismatch {ch}')
            for table in TABLES:
                srcs = sources(task, model, seed, table)
                if not srcs:
                    if table == 'cohort_slice_status':
                        reason = ('No cohort_slice_status table was produced for the seed-42 F1 %s package (%s); the SEEN/UNSEEN x STRICT/OVERLAP cohort tables exist only for the F2/F3 seed-42 packages and the seed 43/44 packages. Not synthesized.' %
                                  ('CQ R4 grid / cq_r4_slices_reconciled' if task == 'CQ' else 'LO static v2 audits', 'seed 42'))
                    else:
                        reason = 'source table missing'
                    entry['tables'][table] = dict(status='NOT_AVAILABLE', reason=reason, rows=0)
                    continue
                parts = []; sfiles = []; total = 0
                for s in srcs:
                    p = Path(s['path'])
                    if not p.exists():
                        entry['tables'][table] = dict(status='NOT_AVAILABLE', reason=f'file missing: {s["dp"]}', rows=0)
                        problems.append(f'{key} {table}: missing {s["dp"]}')
                        parts = None; break
                    t = pq.read_table(p)
                    total_src = t.num_rows
                    if s['fm']:
                        t = t.filter(pc.equal(t['model_name'], model))
                    # integrity vs package sha256sums.txt
                    d = s.get('pkgdir') or p.parent
                    sums = pkg_sha_lines(d)
                    fsha = sha(p)
                    exp = sums.get(p.name)
                    dc = drive_check(p, s['dp'])
                    sfiles.append(dict(source_package=s['package'], file=s['dp'], sha256=fsha, bytes=p.stat().st_size,
                                       rows_in_file=total_src, rows_used=t.num_rows, row_filter=('model_name == %s' % model) if s['fm'] else None,
                                       package_sha256sums_check=('OK' if exp == fsha else ('MISMATCH' if exp else 'no sha256sums entry')), **dc))
                    if exp and exp != fsha: problems.append(f'{key} {table}: sha mismatch vs package sha256sums {p}')
                    # added columns
                    n = t.num_rows
                    for col, val in (('task', task), ('model_name', model), ('seed', seed)):
                        if col in t.column_names:
                            vals = set(pc.unique(t[col]).to_pylist())
                            if vals != {val}:
                                problems.append(f'{key} {table}: column {col} has values {vals} != {val}')
                        else:
                            t = t.append_column(col, pa.array([val] * n, pa.int64() if col == 'seed' else pa.string()))
                    t = t.append_column('source_package', pa.array([s['package']] * n, pa.string()))
                    t = t.append_column('schema_version', pa.array([s['sv']] * n, pa.string()))
                    parts.append(t); total += n
                if parts is None: continue
                ut = pa.concat_tables(parts, promote_options='permissive') if len(parts) > 1 else parts[0]
                sig = hashlib.sha256(json.dumps([(f.name, str(f.type)) for f in ut.schema if f.name not in ('source_package', 'schema_version')]).encode()).hexdigest()[:10]
                svfull = parts[0]['schema_version'][0].as_py() + ';ncols=%d;sig=%s' % (len(ut.schema) - 2, sig)
                ut = ut.set_column(ut.schema.get_field_index('schema_version'), 'schema_version', pa.array([svfull] * ut.num_rows, pa.string()))
                sig_registry[table].setdefault(sig, dict(columns=[(f.name, str(f.type)) for f in ut.schema if f.name not in ('source_package', 'schema_version')], units=[], schema_versions=set()))
                sig_registry[table][sig]['units'].append(f'{task}/{model}/seed{seed}')
                sig_registry[table][sig]['schema_versions'].add(svfull)
                for f in ut.schema:
                    col_types[table].setdefault(f.name, {}).setdefault(str(f.type), []).append(f'{task}/{model}/seed{seed}')
                if ut.num_rows != total:
                    problems.append(f'{key} {table}: concat rows {ut.num_rows} != {total}')
                if sum(x['rows_used'] for x in sfiles) != ut.num_rows:
                    problems.append(f'{key} {table}: rows_used sum mismatch')
                per_table_tables[table].append(ut)
                entry['tables'][table] = dict(status='OK', rows=ut.num_rows, expected_rows_for_51_run_grid=EXPECT[table],
                                              rows_equal_expected=(ut.num_rows == EXPECT[table]),
                                              n_columns_source=len(ut.schema) - 2, schema_signature=sig, source_files=sfiles)
                if ut.num_rows != EXPECT[table]:
                    problems.append(f'{key} {table}: rows {ut.num_rows} != expected {EXPECT[table]}')
            manifest_units.append(entry)
            print(key, {t: v['rows'] for t, v in entry['tables'].items()}, flush=True)

# check ALL rows of R4 against release derived export (macro_f1, per-class recall)
check_all = {}
try:
    rel_cq = pd.read_parquet(f'{WORK}/m14c/cq_r4_with_regime_macro.parquet')
    k = ['window_id', 'pipeline_id', 'phase_id', 'eval_split', 'model_name']
    es = pd.read_parquet(R4S); a = es[es.slice == 'ALL']
    mm = a.merge(rel_cq, on=k, suffixes=('_s', '_r'))
    check_all['CQ_F1_seed42'] = dict(rows_slices_ALL=len(a), rows_release=len(rel_cq), matched=len(mm),
        max_abs_diff_macro_f1=float((mm.macro_f1_s - mm.macro_f1_r).abs().max()),
        max_abs_diff_c0_recall=float((mm.c0_recall_s - mm.c0_recall_r).abs().max()),
        release_file_sha256=sha(f'{WORK}/m14c/cq_r4_with_regime_macro.parquet'), release_inputs_sha256=acc.get(f'{WORK}/m14c/cq_r4_with_regime_macro.parquet'))
    fa = pd.read_parquet(f'{WORK}/m14c/lo_static_v2_facts_no_confusion.parquet')
    res = {}
    for m in registry.REC:
        d, _ = lo_src(m)
        e = pd.read_parquet(d / 'evaluation_slices.parquet'); a = e[e.slice == 'ALL']
        mm = a.merge(fa[fa.model_name == m], on=['window_id', 'pipeline_id', 'phase_id', 'eval_split'], suffixes=('_s', '_r'))
        res[m] = dict(matched=len(mm), max_abs_diff_macro_f1=float((mm.macro_f1_s - mm.macro_f1_r).abs().max()), max_abs_diff_s_leak=float((mm.s_leak_s - mm.s_leak_r).abs().max()))
    check_all['LO_F1_seed42'] = dict(per_model=res, release_file_sha256=sha(f'{WORK}/m14c/lo_static_v2_facts_no_confusion.parquet'),
                                    release_inputs_sha256=acc.get(f'{WORK}/m14c/lo_static_v2_facts_no_confusion.parquet'))
except Exception as ex:
    problems.append('check_all failed: %r' % ex)

# write tables
out_info = {}
for table in TABLES:
    tabs = per_table_tables[table]
    ut = pa.concat_tables(tabs, promote_options='permissive')
    # column order: original columns first (union in order of appearance), then added source_package, schema_version
    names = [n for n in ut.column_names if n not in ('source_package', 'schema_version')] + ['source_package', 'schema_version']
    ut = ut.select(names)
    pq.write_table(ut, OUT / f'{table}.parquet', compression='zstd', row_group_size=20000)
    out_info[table] = dict(rows=ut.num_rows, columns=len(names), bytes=(OUT / f'{table}.parquet').stat().st_size, sha256=sha(OUT / f'{table}.parquet'),
                           units_present=len(tabs))
    cc = {}
    for c, tp in col_types[table].items():
        if len(tp) > 1: cc[c] = {k2: len(v) for k2, v in tp.items()}
    out_info[table]['columns_with_mixed_source_types'] = cc
    out_info[table]['output_types_of_mixed_columns'] = {c: str(ut.schema.field(c).type) for c in cc}
    out_info[table]['schema_variants'] = {sg: dict(n_columns=len(v['columns']), units=len(v['units']), schema_versions=sorted(v['schema_versions'])) for sg, v in sig_registry[table].items()}
    print(table, out_info[table]['rows'], out_info[table]['bytes'], flush=True)

# column diff report between schema variants (relative to the largest variant group)
schema_diff = {}
for table in TABLES:
    vs = sig_registry[table]
    if len(vs) <= 1:
        schema_diff[table] = 'single schema across all units'; continue
    base_sig = max(vs, key=lambda s: len(vs[s]['units']))
    base = dict(vs[base_sig]['columns']); d = {}
    for sg, v in vs.items():
        if sg == base_sig: continue
        cols = dict(v['columns'])
        d[sg] = dict(vs_base_signature=base_sig, only_in_variant=[c for c in cols if c not in base], only_in_base=[c for c in base if c not in cols],
                     type_differences={c: [base[c], cols[c]] for c in cols if c in base and base[c] != cols[c]},
                     units=v['units'] if len(v['units']) <= 12 else v['units'][:12] + ['...'], schema_versions=sorted(v['schema_versions']))
    schema_diff[table] = dict(base_signature=base_sig, base_units=len(vs[base_sig]['units']), variants=d)

man = dict(
    package='l2_slices_and_per_class_3seeds_20261126', created_utc=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    description='Concatenation of ACCEPTED fact tables (no recomputation) for 2 tasks x 6 models x 3 seeds = 36 units. Rows are copied unchanged; added columns: source_package, schema_version (task, model_name, seed already present in every source and were verified equal to the unit key).',
    release_reference='CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2 (meta_release_manifest.json, inputs_sha256)',
    source_package_convention='Drive-relative package folder (relative to the shared Drive root); file column of source_files gives the Drive-relative file path.',
    outputs=out_info, schema_differences=schema_diff, check_all_rows_vs_release_inputs=check_all,
    column_handling='No column was renamed. Columns are the union of the sources (first-appearance order); rows from sources lacking a column hold null. Mixed source dtypes are listed in outputs.<table>.columns_with_mixed_source_types with the resulting output dtype.',
    problems=problems, units=manifest_units)
(OUT / 'manifest.json').write_text(json.dumps(man, indent=1, default=str) + '\n', encoding='utf-8')
print('PROBLEMS', len(problems))
for p in problems[:40]: print(' -', p)
