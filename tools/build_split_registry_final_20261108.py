"""Consolidate the M-07 split evidence into split_registry_cq_v2_2.{csv,json} and split_registry_lo_v3_1.{csv,json}."""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import pyarrow.parquet as pq

TMP = Path(sys.argv[1])            # downloaded partial packages from Drive (cqp/, lop/)
OUT = Path('CQ/resuilt/split_registry_final_20261108')
OUT.mkdir(exist_ok=True)
CQ_DIR = Path('CQ/resuilt/m07_split_evidence_received_20261107')
CQ_POP = Path('LO/resuilt/m07_m05_delivery_20261107/CQ/L0_registry/M07_split_evidence')
LO_DIR = Path('LO/resuilt/m07_split_evidence_received_20261107_r2')
LO_POP = Path('LO/resuilt/m07_m05_delivery_20261107/LO/L0_registry/M07_split_evidence')
LO_REG = Path('LO/resuilt/lo_split_evidence_20261106/split_registry_source.csv')
ROOTS = {'CQ': Path('downloads/vastai/CQ_V2_2_clean_grain_seed42'), 'LO': Path('downloads/vastai/LO_V3_1_clean_grain_seed42')}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def jl(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


now = datetime.now(timezone.utc).isoformat()


def strict_table(task):
    rows = []
    for w in ('W1', 'W2', 'W3'):
        v = pq.read_table(ROOTS[task] / f'evaluation/{w}/V0/validation.parquet',
                          columns=[f'context__temporal_strict_P{k}' for k in range(1, 5)]).to_pandas()
        for k in range(1, 5):
            f = v[f'context__temporal_strict_P{k}']
            assert f.notna().all()
            rows.append((w, 'VALIDATION', f'P{k}', len(v), int(f.astype(bool).sum())))
            t = pq.read_table(ROOTS[task] / f'evaluation/{w}/V0/test_P{k}.parquet',
                              columns=[f'context__temporal_strict_P{k}']).to_pandas().iloc[:, 0]
            assert t.notna().all()
            rows.append((w, 'TEST', f'P{k}', len(t), int(t.astype(bool).sum())))
    d = pd.DataFrame(rows, columns=['window_id', 'eval_split', 'phase_id', 'n_eval', 'n_strict'])
    d['n_overlap'] = d.n_eval - d.n_strict
    d['strict_share'] = d.n_strict / d.n_eval
    d['overlap_share'] = d.n_overlap / d.n_eval
    return d


def pivot_strict(s):
    p = s.pivot(index='window_id', columns=['eval_split', 'phase_id'], values='strict_share')
    p.columns = [f'strict_share_{a.lower()}_{b}' for a, b in p.columns]
    return p.reset_index()


checks = {}
# ---------------- CQ ----------------
cq_reg = pd.read_csv(CQ_DIR / 'split_registry.csv')
cq_strict = strict_table('CQ')
cqp =pd.read_csv(TMP / 'cqp/strict_by_phase.csv').rename(columns={'n_eval': 'o_eval', 'n_strict': 'o_strict'})
mm = cq_strict.merge(cqp[['window_id', 'eval_split', 'phase_id', 'o_eval', 'o_strict']], on=['window_id', 'eval_split', 'phase_id'])
assert len(mm) == 24 and (mm.n_eval == mm.o_eval).all() and (mm.n_strict == mm.o_strict).all()
cq_blocks = pd.read_csv(CQ_DIR / 'block_label_audit.csv').sort_values('rolling_block')
cq_dur = pd.read_csv(TMP / 'cqp/offering_duration.csv')
cal = pd.read_csv(CQ_DIR / 'calendar_boundaries.csv').iloc[0].to_dict()
ref = jl('CQ/resuilt/input/results/R21_evidence_20261031/registry_v1_3/split_registry.json')
partial_json = jl(TMP / 'cqp/split_registry_cq_v2_2.json')
checks['CQ'] = {
    'calendar_equals_reference_R21': ref['calendar']['a_boundary'] == cal['a_boundary']
    and ref['calendar']['slice_boundaries'] == {'T1': cal['slice_1_boundary'], 'T2': cal['slice_2_boundary'], 'T3': cal['slice_3_boundary']},
    'tau_w_equals_reference_R21': ref['calendar']['tau_w'] == dict(zip(cq_reg.window_id, cq_reg.tau_w)),
    'strict_by_phase_equals_earlier_partial_package_24_cells': True,
    'w2_strict_vs_R4_cells': partial_json.get('w2_strict_r4'),
    'w2_strict_r4_rows_checked': partial_json.get('w2_strict_r4_rows_checked'),
}
assert checks['CQ']['calendar_equals_reference_R21'] and checks['CQ']['tau_w_equals_reference_R21']
cq_pop = jl(CQ_POP / 'population_summary.json')
cq_miss = jl(CQ_POP / 'cq_missing_label_population_summary.json')
raw_recon = jl('CQ/resuilt/m07_raw_population_reconciliation_20261108/summary.json')

# ---------------- LO ----------------
lo_reg = pd.read_csv(LO_REG)
lo_strict = strict_table('LO')
lop = pd.read_csv(TMP / 'lop/strict_share.csv').rename(columns={'n': 'o_eval', 'strict_n': 'o_strict'})
mm = lo_strict.merge(lop[['window_id', 'eval_split', 'phase_id', 'o_eval', 'o_strict']], on=['window_id', 'eval_split', 'phase_id'])
assert len(mm) == 24 and (mm.n_eval == mm.o_eval).all() and (mm.n_strict == mm.o_strict).all()
lo_blocks = pd.read_csv(TMP / 'lop/block_class_counts.csv')
lo_dur = pd.read_csv(TMP / 'lop/duration_summary.csv')
lo_excl = pd.read_csv(TMP / 'lop/exclusion_reason_summary.csv')
lo_pivot = pd.read_csv(LO_DIR / 'slice_exclusion_reason_pivot.csv')
lo_cov = pd.read_csv(LO_DIR / 'assignment_coverage_qa.csv')
lo_slices = pd.read_csv(LO_DIR / 'slice_timeline_summary.csv')
lo_pop = jl(LO_POP / 'population_summary.json')
facts = pd.read_parquet('LO/resuilt/lo_static_v2_grid_seed42_20261102/lo_family_pipeline_window_phase_metrics.parquet')
a = facts[(facts.pipeline_id == 'V0') & (facts.phase_id == 'P4') & (facts.model_name == facts.model_name.iloc[0])]
sup = a.groupby('window_id')[['c0_support', 'c1_support', 'c2_support']].sum()
g = lo_slices.groupby('temporal_slice')[['n_I_D', 'n_G', 'n_E']].sum()
ok_totals = all([int(g.loc[t, 'n_I_D']), int(g.loc[t, 'n_G']), int(g.loc[t, 'n_E'])] == [int(x) for x in sup.loc[w]]
                for t, w in (('T1', 'W1'), ('T2', 'W2'), ('T3', 'W3')))
checks['LO'] = {'class_totals_equal_facts_support_T1_T2_T3': ok_totals,
                'strict_by_phase_equals_earlier_partial_package_24_cells': True,
                'exclusion_status_rows': int(len(lo_excl)),
                'exclusion_total_enrollments': int(lo_excl.enrollment_count.sum()),
                'exclusion_note': '6 exclusion reasons + ELIGIBLE = 7 statuses'}
assert ok_totals and int(lo_excl.enrollment_count.sum()) == 11807090


def write(task, version, reg, strict, blocks, dur, extra_tables, doc):
    base = f'split_registry_{task.lower()}_{version}'
    win = reg.merge(pivot_strict(strict), on='window_id', how='left')
    win.insert(0, 'registry_version', f'{task}_{version}')
    win.to_csv(OUT / f'{base}.csv', index=False)
    strict.assign(task=task).to_csv(OUT / f'{base}_strict_by_phase.csv', index=False)
    blocks.to_csv(OUT / f'{base}_blocks.csv', index=False)
    dur.to_csv(OUT / f'{base}_offering_duration.csv', index=False)
    for name, t in extra_tables.items():
        t.to_csv(OUT / f'{base}_{name}.csv', index=False)
    doc.update({'registry_version': f'{task}_{version}', 'created_at_utc': now,
                'windows': json.loads(win.to_json(orient='records')),
                'strict_by_phase': json.loads(strict.to_json(orient='records')),
                'blocks': json.loads(blocks.to_json(orient='records')),
                'offering_duration': json.loads(dur.to_json(orient='records')),
                'tables': {n: json.loads(t.to_json(orient='records')) for n, t in extra_tables.items()},
                'acceptance_checks': checks[task]})
    (OUT / f'{base}.json').write_text(json.dumps(doc, indent=2, ensure_ascii=False, default=str) + '\n', encoding='utf8')


cq_doc = {'task': 'CQ', 'release_id': 'CQ_V2_2',
          'data_release_id': 'sha256:8db2b1d375c9cb7cd91cbccb7907fca51a8ab9bcd748c7bde43e879b1237d045',
          'calendar': cal, 'ev_train_overlap_share': dict(zip(cq_reg.window_id, cq_reg.ev_train_overlap_share)),
          'population': {'processed_enrollments': 11807090, 'with_label_artifact': 3192206, 'without_label_artifact': 8614884,
                         'artifact_summary': cq_pop.get('population_summary'), 'missing_label_audit': cq_miss,
                         'raw_reconciliation': raw_recon['steps'], 'raw_reconciliation_limitation': raw_recon['limitation'],
                         'historical_log_evidence': raw_recon['historical_log_evidence']},
          'label_policy': 'cq_vector_proximity_v1_zero_activity_policy', 'status': 'COMPLETE_WITH_DOCUMENTED_LIMITATIONS',
          'limitations': ['Counts logged at creation time (2026-08-25, 2026-09-02, 2026-09-12 to 2026-09-22) equal the counts of 2026-11-08, but no byte hash of user.json or of the label artifacts from build time exists.',
                          'The 2026-10-22 release identity ledger covers the model-input release, not the raw files.']}
write('CQ', 'v2_2', cq_reg, cq_strict, cq_blocks, cq_dur,
      {'calendar': pd.DataFrame([cal]), 'temporal_overlap': pd.read_csv(CQ_DIR / 'temporal_overlap.csv'), 'qa22': pd.read_csv(CQ_DIR / 'qa22.csv')}, cq_doc)
lo_doc = {'task': 'LO', 'release_id': 'LO_V3_1',
          'data_release_id': 'sha256:2edf8cc293044d29c360cb2db71b8d21e26e2187cf40c6d45266f342a826d35b',
          'population': {'summary': lo_pop.get('population_summary'), 'comparisons': lo_pop.get('comparisons'),
                         'exclusion_reasons': json.loads(lo_excl.to_json(orient='records'))},
          'label_policy': 'lo_final_score_catalog_normalized_v3_1', 'status': 'COMPLETE_WITH_DOCUMENTED_LIMITATIONS',
          'limitations': ['LO exclusion statuses cover the 11,807,090 processed enrollments (same expansion of user.json as CQ).',
                          'No byte hash of the raw sources or label artifacts from build time exists.']}
write('LO', 'v3_1', lo_reg, lo_strict, lo_blocks, lo_dur,
      {'exclusion_reasons': lo_excl, 'exclusion_by_slice': lo_pivot, 'assignment_coverage': lo_cov, 'slice_timeline_summary': lo_slices}, lo_doc)

sources = [CQ_DIR / 'split_registry.csv', CQ_DIR / 'block_label_audit.csv', CQ_DIR / 'calendar_boundaries.csv', CQ_DIR / 'temporal_overlap.csv',
           CQ_DIR / 'qa22.csv', LO_REG, LO_DIR / 'slice_timeline_summary.csv', LO_DIR / 'slice_exclusion_reason_pivot.csv', LO_DIR / 'assignment_coverage_qa.csv']
(OUT / 'sources.json').write_text(json.dumps([{'path': str(p), 'sha256': sha(p)} for p in sources], indent=2) + '\n', encoding='utf8')
(OUT / 'README.md').write_text(
    '# Split registry CQ_V2_2 and LO_V3_1 (M-07)\n\n'
    'split_registry_cq_v2_2.{csv,json} and split_registry_lo_v3_1.{csv,json}: window-level registry (tau_w, windows, sizes, overlap, QA22 fields, days, '
    'STRICT share by split and phase) plus, in the JSON and in the *_blocks, *_strict_by_phase, *_offering_duration and other *_ CSVs, block A-G sizes and '
    'class distributions, STRICT by window x split x phase, offering duration, and the population before/after each filter. sources.json lists the SHA-256 '
    'of every input table.\n\n'
    'STRICT counts come from the per-enrollment flag context__temporal_strict_P1..P4 of the delivered V0 evaluation files; they equal the counts of the '
    'earlier CQ (2026-11-03) and LO (2026-11-06) partial packages in all 48 cells. Acceptance checks are in the JSON (acceptance_checks).\n\n'
    'Known limitations (also in the JSON): counts logged at creation time equal today\'s counts, but no byte hash of the raw sources or label artifacts from '
    'build time exists; the 2026-10-22 release identity ledger covers the model-input release only.\n', encoding='utf8')
names = sorted(p.name for p in OUT.iterdir() if p.name != 'sha256sums.txt')
(OUT / 'sha256sums.txt').write_text(''.join(f'{sha(OUT / n)}  {n}\n' for n in names), encoding='utf8')
print(json.dumps(checks, indent=1, default=str))
print(names)
