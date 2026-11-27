# -*- coding: utf-8 -*-
"""P.5 cost table: sum over the 51 cells (3 windows x 17 pipelines) of resource_per_run of the accepted LO facts, seeds 43 and 44.
Estimate only; nothing is run. Env: P_OUT, AUDIT44."""
import os, glob
import pandas as pd

OUT = os.environ['P_OUT']; A = os.environ['AUDIT44']
paths = {}
for fam in ('RNN', 'LSTM', 'GRU', 'BILSTM'):
    paths[(fam, 43)] = f'{A}/asm_inputs/seed43/LO_f1_recurrent/{fam}/resource_per_run.csv'
    g = glob.glob(f'{A}/facts44/LO_f1_recurrent_v0_v16_seed44/{fam}/resource_per_run.csv')
    paths[(fam, 44)] = g[0] if g else None
paths[('PATCHTST', 43)] = f'{A}/asm_inputs/seed43/LO_patchtst/resource_per_run.csv'
paths[('PATCHTST', 44)] = f'{A}/facts44/LO_patchtst_v0_v16_seed44/resource_per_run.csv'
paths[('MANTIS_V2', 43)] = f'{A}/asm_inputs/seed43/LO_mantis_v2/resource_per_run.csv'
paths[('MANTIS_V2', 44)] = f'{A}/facts44/LO_mantis_v2_v0_v16_seed44/resource_per_run.csv'
rows = []
for (fam, seed), p in paths.items():
    if p is None or not os.path.exists(p):
        rows.append(dict(model_family=fam, seed=seed, source='NOT_FOUND')); continue
    d = pd.read_csv(p)
    assert len(d) == 51 and d[['window_id', 'pipeline_id']].drop_duplicates().shape[0] == 51
    e = d.groupby('window_id').elapsed_seconds.sum()
    rows.append(dict(model_family=fam, seed=seed, n_cells=len(d), gpu=';'.join(sorted(d.gpu.dropna().unique())),
                     sum_train_seconds=d.train_seconds.sum(), sum_elapsed_seconds=d.elapsed_seconds.sum(),
                     sum_train_hours=d.train_seconds.sum() / 3600, sum_elapsed_hours=d.elapsed_seconds.sum() / 3600,
                     elapsed_hours_W1=e.get('W1', 0) / 3600, elapsed_hours_W2=e.get('W2', 0) / 3600, elapsed_hours_W3=e.get('W3', 0) / 3600,
                     max_cell_elapsed_hours=d.elapsed_seconds.max() / 3600, median_cell_elapsed_hours=d.elapsed_seconds.median() / 3600,
                     energy_gpu_estimated_kwh_sum=d.energy_gpu_estimated_kwh.sum(),
                     energy_measurement_types=';'.join(sorted(d.energy_measurement_type.dropna().astype(str).unique())),
                     batch_sizes=';'.join(str(x) for x in sorted(d.batch_size.dropna().unique())),
                     source=p.replace(A, 'AUDIT44')))
t = pd.DataFrame(rows)
t.to_csv(f'{OUT}/ablation_cost_table.csv', index=False)
pd.set_option('display.width', 250, 'display.max_columns', 30)
print(t.drop(columns=['source', 'energy_measurement_types']).round(2).to_string())
