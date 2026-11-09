"""Assemble F0 CQ_PARTIAL_TRIAD (24 rows) from partial COELO/AFELO/ACELO exported by the Databricks job.

Usage: python -I tools/assemble_f0_cq_partial_triad_20261108.py <databricks_output_dir_downloaded_locally>
The directory must contain f0_manifest_*.json (one with final_check_pass == true) and P1..P4/f0_components/*.parquet.

Convention (also written to the README): an enrollment absent from a partial artifact had no video, problem
or comment event before its cutoff (the production population keeps only active proxy-timeline enrollments),
so its components are set to 0 and its proximity is 0 (class warning). The label rule is the production rule:
proximity = 1 - sqrt((C-1)^2 + (A-1)^2 + (L-1)^2) / sqrt(3); warning < 0.10, average < 0.30, else good.
"""
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from metrics_core.evaluation import classification_metrics

SRC = Path(sys.argv[1])
OUT = Path('CQ/resuilt/f0_cq_partial_triad_20261108')
OUT.mkdir(parents=True, exist_ok=True)
DATA = Path('downloads/vastai/CQ_V2_2_clean_grain_seed42')
CLASS = {'warning': 0, 'average': 1, 'good': 2}
manifests = [json.loads(p.read_text(encoding='utf8')) for p in sorted(SRC.glob('f0_manifest_*.json'))]
final = [m for m in manifests if m.get('final_check_pass')]
if not final:
    raise SystemExit('No manifest with a passing FINAL self-check; partial components are not trustworthy')
manifest = {'final_check': final[0]['final_check'], 'manifests': manifests}

def predict(frame):
    c, a, l = (frame[k].fillna(0.0).clip(0, 1) for k in ('COELO_personal', 'AFELO_personal', 'ACELO_personal'))
    prox = 1 - np.sqrt((c - 1) ** 2 + (a - 1) ** 2 + (l - 1) ** 2) / np.sqrt(3)
    return np.where(prox < 0.10, 0, np.where(prox < 0.30, 1, 2)), prox

rows = []
for k in range(1, 5):
    comp = pd.read_parquet(SRC / f'P{k}' / 'f0_components', columns=['enrollment_id', 'COELO_personal', 'AFELO_personal', 'ACELO_personal'])
    if comp.enrollment_id.duplicated().any():
        raise ValueError(f'Duplicate enrollment_id in P{k} components')
    comp = comp.set_index('enrollment_id')
    for window in ('W1', 'W2', 'W3'):
        for split, rel in (('VALIDATION', f'evaluation/{window}/V0/validation.parquet'), ('TEST', f'evaluation/{window}/V0/test_P{k}.parquet')):
            cohort = pd.read_parquet(DATA / rel, columns=['enrollment_id', 'CQ_label_final'])
            if cohort.enrollment_id.duplicated().any():
                raise ValueError('cohort ids not unique')
            joined = cohort.join(comp, on='enrollment_id')
            n_absent = int(joined.COELO_personal.isna().sum())
            y_pred, prox = predict(joined)
            y_true = joined.CQ_label_final.map(CLASS).to_numpy()
            if np.isnan(y_true.astype(float)).any():
                raise ValueError('unknown label in cohort')
            probs = np.eye(3)[y_pred]
            m = classification_metrics(y_true.astype(int), probs)
            rows.append({'task': 'CQ', 'window_id': f'{window}', 'phase_id': f'P{k}', 'eval_split': split,
                         'subgroup_axis': 'ALL', 'subgroup_value': 'ALL', 'model_tier': 'F0_REFERENCE', 'model_name': 'CQ_PARTIAL_TRIAD',
                         'n_eval_samples': m['n_eval_samples'], 'n_absent_from_partial_artifact': n_absent,
                         'macro_f1': m['macro_f1'], 'balanced_acc': m['balanced_acc'], 'mcc': m['mcc'], 'kappa': m['kappa'],
                         'gmean': m['gmean'], 's_perf': m['s_perf'], 'acctempo_m3': None, 'acctempo_m3_status': 'NOT_APPLICABLE',
                         'mean_proximity': float(prox.mean()), 'confusion_matrix': json.dumps(m['confusion_matrix'])})
frame = pd.DataFrame(rows)
if len(frame) != 24 or frame.duplicated(['window_id', 'phase_id', 'eval_split']).any():
    raise ValueError('F0 must have 24 unique rows')
frame.to_csv(OUT / 'f0_cq_partial_triad.csv', index=False)
frame.to_parquet(OUT / 'f0_cq_partial_triad.parquet', index=False)
(OUT / 'f0_manifest_databricks.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf8')
(OUT / 'README.md').write_text(
    '# F0 CQ_PARTIAL_TRIAD (M-13c)\n\nDeterministic baseline: COELO/AFELO/ACELO recomputed with the unchanged production component builder on events '
    'available before enroll + q*(offering_end - enroll), q = 0.25/0.5/0.75/0.9 for P1-P4, then the production proximity rule. '
    'Self-check: the same job at q = 1.0 reproduced the production component artifact (see f0_manifest_databricks.json). '
    'Enrollments missing from a partial artifact had no observed event before cutoff and are scored with zero components (warning). '
    'No seed, pipeline or probabilities; metrics use one-hot hard predictions. acctempo_m3 is NULL (NOT_APPLICABLE) as required.\n', encoding='utf8')
with (OUT / 'sha256sums.txt').open('w') as f:
    for n in ('f0_cq_partial_triad.csv', 'f0_cq_partial_triad.parquet', 'f0_manifest_databricks.json', 'README.md'):
        f.write(f"{hashlib.sha256((OUT / n).read_bytes()).hexdigest()}  {n}\n")
print(frame[['window_id', 'phase_id', 'eval_split', 'macro_f1', 'balanced_acc', 'n_absent_from_partial_artifact']].round(4).to_string())
