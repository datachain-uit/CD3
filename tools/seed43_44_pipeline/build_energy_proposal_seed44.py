"""Energy proposal for the 8 CQ seed-44 cells without an energy measurement (report only; nothing is written into the fact packages).

Method (README of `energy_proposal_seed44_20261119`): power of every measured cell = energy_gpu_estimated_kwh * 3.6e6 / elapsed_seconds;
proposal = median power of the measured cells of the same family (PatchTST: cells on the same GPU model as the missing cells; Mantis: all measured Mantis CQ cells)
x elapsed_seconds / 3.6e6; the range uses the 5th and 95th percentile of the power.
usage: build_energy_proposal_seed44.py [--out DIR]   (reads <audit44>/facts44/CQ_patchtst_v0_v16_seed44 and CQ_mantis_v2_v0_v16_seed44 resource_per_run.csv)
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))
from tempo_paths import A44

ap = argparse.ArgumentParser()
ap.add_argument('--out', default=f'{A44}/energy_note_seed44_rebuilt')
args = ap.parse_args()
out = Path(args.out); out.mkdir(parents=True, exist_ok=True)

rows = []
for family, folder in (('PATCHTST', 'CQ_patchtst_v0_v16_seed44'), ('MANTIS_V2', 'CQ_mantis_v2_v0_v16_seed44')):
    r = pd.read_csv(f'{A44}/facts44/{folder}/resource_per_run.csv')
    r['power_w'] = r.energy_gpu_estimated_kwh * 3.6e6 / r.elapsed_seconds
    measured = r[r.energy_gpu_estimated_kwh.notna() & r.elapsed_seconds.notna()]
    missing = r[r.energy_gpu_estimated_kwh.isna()]
    for m in missing.itertuples():
        pool = measured[measured.gpu == m.gpu] if family == 'PATCHTST' and isinstance(m.gpu, str) else measured
        p50, p5, p95 = (round(float(x), 1) for x in (pool.power_w.median(), pool.power_w.quantile(0.05), pool.power_w.quantile(0.95)))   # power rounded to 0.1 W as in the delivered note
        rows.append({'task': 'CQ', 'model': family, 'window_id': m.window_id, 'pipeline_id': m.pipeline_id, 'gpu': m.gpu, 'elapsed_seconds': round(float(m.elapsed_seconds), 1),
                     'basis_power_w': round(float(p50), 1), 'proposed_kwh': round(float(p50 * m.elapsed_seconds / 3.6e6), 3),
                     'low_kwh_p5_power': round(float(p5 * m.elapsed_seconds / 3.6e6), 3), 'high_kwh_p95_power': round(float(p95 * m.elapsed_seconds / 3.6e6), 3)})
df = pd.DataFrame(rows)
df.to_csv(out / 'energy_proposal_seed44.csv', index=False, lineterminator='\n')
print(len(df), 'cells;', df[['model', 'window_id', 'pipeline_id', 'proposed_kwh']].to_string(index=False))
