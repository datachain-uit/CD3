"""Aggregate the three-seed release (seeds 42, 43, 44; CQ and LO; RNN, LSTM, GRU, BILSTM, PATCHTST, MANTIS_V2; W1-W3; V0-V16) into tidy tables for the summary report.
Single source: meta_release_CQ_LO_full_F1F2F3_seeds42_43_44_20261119/meta_dataset_seed_level.parquet (the *_after columns). Split = TEST; mean over phases P1-P4 per cell unless stated.
Output: <OUT>/*.csv and sources.json   (no number of the report is typed by hand)."""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1] / 'seed43_44_pipeline'))
from tempo_paths import A44, REPO
import json
import os
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

REL = Path(os.environ.get('TEMPO_RELEASE', f'{REPO}/CQ/resuilt/meta_release_CQ_LO_full_F1F2F3_seeds42_43_44_20261119'))
OUT = Path(os.environ.get('TEMPO_REPORT_TABLES', f'{A44}/report_s42_43_44'))
OUT.mkdir(parents=True, exist_ok=True)
M = ['macro_f1', 'balanced_acc', 'mcc', 'kappa', 'gmean', 'log_loss', 'brier', 'ece', 's_perf', 's_san_plus_v2', 's_leak', 'acctempo_m3_cal']
CELL = ['task', 'model_name', 'seed', 'window_id', 'pipeline_id']
SEEDS = [42, 43, 44]
cols = CELL + ['eval_split', 'phase_id'] + [f'{m}_after' for m in M] + ['time_run_total_s_after', 'time_train_s_after', 'energy_gpu_run_kwh_after', 'energy_measurement_type', 's_leak_source']
sl = pd.read_parquet(REL / 'meta_dataset_seed_level.parquet', columns=cols)
sl.columns = [c[:-6] if c.endswith('_after') else c for c in sl.columns]
sl['seed'] = sl['seed'].astype(int)
src = {'release': str(REL.name), 'table': 'meta_dataset_seed_level.parquet', 'rows': int(len(sl))}
test = sl[sl.eval_split == 'TEST']
cell = test.groupby(CELL)[M].mean().reset_index()                      # one row per run (task, model, seed, window, pipeline): TEST, mean over P1-P4
cell.to_csv(OUT / 'perf_per_cell_test_mean_P1P4.csv', index=False, lineterminator='\n')

cov = sl.groupby(['task', 'model_name', 'seed']).apply(lambda g: pd.Series({'cells': g[['window_id', 'pipeline_id']].drop_duplicates().shape[0], 'rows': len(g)}), include_groups=False).reset_index()
cov.to_csv(OUT / 'coverage_cells.csv', index=False, lineterminator='\n')

summ = cell.groupby(['task', 'model_name', 'seed'])[M].mean().reset_index()
summ.to_csv(OUT / 'summary_task_model_seed.csv', index=False, lineterminator='\n')
across = cell.groupby(['task', 'model_name', 'seed'])[M].mean().groupby(['task', 'model_name'])[M].agg(['mean', 'std'])
across.columns = [f'{a}_{b}' for a, b in across.columns]
across.reset_index().to_csv(OUT / 'summary_task_model_across_seeds.csv', index=False, lineterminator='\n')

bw = cell.groupby(['task', 'model_name', 'seed', 'window_id'])[['macro_f1', 'acctempo_m3_cal']].mean().reset_index()
bw.to_csv(OUT / 'summary_task_model_seed_window.csv', index=False, lineterminator='\n')

# pipeline groups: V0 = no intervention; imputation only (balancer NONE): V1, V5, V9, V13; imputation + balancing: the other twelve (child of the imputation-only pipeline with the same imputer)
IMP_ONLY = ['V1', 'V5', 'V9', 'V13']
PARENT = {'V2': 'V1', 'V3': 'V1', 'V4': 'V1', 'V6': 'V5', 'V7': 'V5', 'V8': 'V5', 'V10': 'V9', 'V11': 'V9', 'V12': 'V9', 'V14': 'V13', 'V15': 'V13', 'V16': 'V13'}
cell['group'] = np.where(cell.pipeline_id == 'V0', 'V0', np.where(cell.pipeline_id.isin(IMP_ONLY), 'IMP_ONLY', 'IMP_BAL'))
G = ['task', 'model_name', 'seed']
grp = cell.groupby(G + ['group'])[['macro_f1', 'acctempo_m3_cal']].mean().unstack('group')
grp.columns = [f'{a}_{b}' for a, b in grp.columns]
grp = grp.reset_index()
for m in ('macro_f1', 'acctempo_m3_cal'):
    grp[f'{m}_imp_only_minus_V0'] = grp[f'{m}_IMP_ONLY'] - grp[f'{m}_V0']
    grp[f'{m}_imp_bal_minus_V0'] = grp[f'{m}_IMP_BAL'] - grp[f'{m}_V0']
# effect of balancing alone: each balanced pipeline minus its imputation-only parent (same window, task, model, seed)
ch = cell[cell.pipeline_id.isin(PARENT)].copy()
par = cell[cell.pipeline_id.isin(IMP_ONLY)][G + ['window_id', 'pipeline_id', 'macro_f1', 'acctempo_m3_cal']].rename(columns={'pipeline_id': 'parent', 'macro_f1': 'macro_f1_parent', 'acctempo_m3_cal': 'acctempo_m3_cal_parent'})
ch['parent'] = ch.pipeline_id.map(PARENT)
ch = ch.merge(par, on=G + ['window_id', 'parent'])
ch['bal_effect_macro_f1'] = ch.macro_f1 - ch.macro_f1_parent
ch['bal_effect_acctempo'] = ch.acctempo_m3_cal - ch.acctempo_m3_cal_parent
be = ch.groupby(G).agg(bal_cells=('bal_effect_macro_f1', 'size'), bal_effect_macro_f1=('bal_effect_macro_f1', 'mean'), bal_share_better=('bal_effect_macro_f1', lambda x: float((x > 0).mean())), bal_effect_acctempo=('bal_effect_acctempo', 'mean')).reset_index()
grp.merge(be, on=G).to_csv(OUT / 'summary_pipeline_groups.csv', index=False, lineterminator='\n')
pc = cell[cell.pipeline_id != 'V0'].merge(cell[cell.pipeline_id == 'V0'][G + ['window_id', 'macro_f1']].rename(columns={'macro_f1': 'macro_f1_V0'}), on=G + ['window_id'])
pc['delta'] = pc['macro_f1'] - pc['macro_f1_V0']
pc.groupby(G).agg(cells=('delta', 'size'), share_better=('delta', lambda x: float((x > 0).mean())), mean_delta=('delta', 'mean')).reset_index().to_csv(OUT / 'delta_V0_vs_V1V16_macro_f1.csv', index=False, lineterminator='\n')

# agreement between seeds on the same cell
rows = []
for (t, m), g in cell.groupby(['task', 'model_name']):
    wide = {s: g[g.seed == s].set_index(['window_id', 'pipeline_id']) for s in SEEDS}
    for a, b in combinations(SEEDS, 2):
        j = wide[a].join(wide[b], lsuffix='_a', rsuffix='_b', how='inner')
        for met in ('macro_f1', 'acctempo_m3_cal'):
            x, y = j[f'{met}_a'], j[f'{met}_b']
            pm = g.groupby(['seed', 'pipeline_id'])[met].mean().unstack(0)            # 17 pipelines x seeds: average ranking
            rows.append({'task': t, 'model_name': m, 'seed_a': a, 'seed_b': b, 'metric': met, 'cells': len(j), 'mean_abs_diff': float((x - y).abs().mean()), 'pearson_cells': float(x.corr(y)),
                         'spearman_pipeline_means': float(pm[a].corr(pm[b], method='spearman')), 'best_pipeline_a': pm[a].idxmax(), 'best_pipeline_b': pm[b].idxmax()})
pd.DataFrame(rows).to_csv(OUT / 'seed_pair_agreement.csv', index=False, lineterminator='\n')

# s_leak: copied from the registered reference table for every seed; identity across seeds
sk = sl[sl.pipeline_id.isin(sl.pipeline_id.unique())].groupby(['task', 'window_id', 'eval_split', 'phase_id', 'seed']).s_leak.mean().unstack('seed')
sk['max_abs_diff_between_seeds'] = sk[SEEDS].max(axis=1) - sk[SEEDS].min(axis=1)
sk = sk.reset_index()
sk.to_csv(OUT / 'summary_s_leak.csv', index=False, lineterminator='\n')
src['s_leak_source_values'] = sorted(sl.s_leak_source.dropna().unique().tolist())

# run time and energy availability
rn = sl.groupby(CELL).agg(time_run_total_s=('time_run_total_s', 'first'), time_train_s=('time_train_s', 'first'), energy_kwh=('energy_gpu_run_kwh', 'first'), energy_type=('energy_measurement_type', 'first')).reset_index()
rn.to_csv(OUT / 'resource_per_run.csv', index=False, lineterminator='\n')
tm = rn.groupby(['task', 'model_name', 'seed']).agg(runs=('time_run_total_s', 'size'), n_time_run=('time_run_total_s', lambda x: int(x.notna().sum())), total_run_hours=('time_run_total_s', lambda x: x.sum() / 3600),
                                                     mean_run_minutes=('time_run_total_s', lambda x: x.mean() / 60), n_time_train=('time_train_s', lambda x: int(x.notna().sum())),
                                                     total_train_hours=('time_train_s', lambda x: x.sum() / 3600), mean_train_minutes=('time_train_s', lambda x: x.mean() / 60),
                                                     energy_runs=('energy_kwh', lambda x: int(x.notna().sum())), energy_kwh_measured=('energy_kwh', 'sum')).reset_index()
tm.to_csv(OUT / 'summary_time_energy_seed.csv', index=False, lineterminator='\n')
(OUT / 'sources.json').write_text(json.dumps(src, indent=1), encoding='utf-8')
print('tables:', sorted(p.name for p in OUT.glob('*.csv')))
print('cells per task/model/seed unique:', sorted(cov.cells.unique()), '| rows per task/model/seed unique:', sorted(cov.rows.unique()))
