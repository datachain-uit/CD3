"""Build the M-18 seed-43 package (training histories) from the collection pass: one long table (one row per epoch), one per-cell summary, README, scripts, sha256sums.
Same layout as m18_training_history_seed42_20261111. Also writes the runner-commit check (every cell's run_manifest runner_git_commit).
usage: m43_build_m18.py   (inputs D:/audit43/m43_collect/*.pkl, outputs D:/audit43/m18_43/ and D:/audit43/m43_collect/runner_commit_check_seed43.*)"""
import hashlib
import json
import shutil
from pathlib import Path

import pandas as pd

C = Path('D:/audit43/m43_collect')
OUT = Path('D:/audit43/m18_43/m18_training_history_seed43_20261116')
OUT.mkdir(parents=True, exist_ok=True)
hist = pd.read_pickle(C / 'all_histories.pkl')
man = pd.read_pickle(C / 'all_manifests.pkl')
KEY = ['task', 'window_id', 'pipeline_id', 'model_name']
fcol = 'validation_macro_f1_mean_p1_p4'
rows, long_rows = [], []
for key, g in hist.groupby(KEY, sort=True):
    # one cell can come from more than one archive (e.g. a supplementary bundle): keep the first, report identity
    parts = [x for _, x in g.groupby((g['epoch'].diff() < 0).cumsum())] if 'epoch' in g else [g]
    first = parts[0].reset_index(drop=True)
    same = all(first.drop(columns=[c for c in first.columns if c.endswith('_seconds')], errors='ignore').equals(p.reset_index(drop=True).drop(columns=[c for c in p.columns if c.endswith('_seconds')], errors='ignore')) for p in parts[1:]) if len(parts) > 1 else True
    long_rows.append(first)
    m = man[(man.task == key[0]) & (man.window_id == key[1]) & (man.pipeline_id == key[2]) & (man.model_name == key[3])]
    best_m = m.best_epoch.dropna().iloc[0] if len(m) and m.best_epoch.notna().any() else None
    vce = next((c for c in first.columns if c.startswith('validation_cross_entropy')), None)
    be = int(first.loc[first[fcol].idxmax(), 'epoch']) if fcol in first else None
    rows.append({'task': key[0], 'window_id': key[1], 'pipeline_id': key[2], 'model_name': key[3], 'seed': 43, 'epochs_logged': len(first), 'best_epoch_manifest': best_m,
                 'best_epoch_by_val_macro_f1': be, 'best_epoch_equals_manifest': (int(best_m) == be) if best_m is not None and be is not None else None,
                 'best_validation_macro_f1': float(first[fcol].max()) if fcol in first else None, 'min_validation_ce': float(first[vce].min()) if vce else None,
                 'total_train_seconds': float(first['epoch_seconds'].sum()) if 'epoch_seconds' in first else None, 'n_sources': len(parts), 'sources_identical': same})
allh = pd.concat(long_rows, ignore_index=True)
summ = pd.DataFrame(rows)
allh.to_parquet(OUT / 'm18_training_history_seed43.parquet', index=False)
allh.to_csv(OUT / 'm18_training_history_seed43.csv', index=False, lineterminator='\n')
summ.to_parquet(OUT / 'm18_training_history_cell_summary_seed43.parquet', index=False)
summ.to_csv(OUT / 'm18_training_history_cell_summary_seed43.csv', index=False, lineterminator='\n')
cells = summ.groupby(['task', 'model_name']).size().to_dict()
print('cells per task/model', cells)
print('total cells', len(summ), 'epoch rows', len(allh))
bad = {k: v for k, v in cells.items() if v != 51}
(OUT / 'README.md').write_text(
    f"# M-18 — lịch sử huấn luyện seed 43 (F1, F2, F3; CQ và LO)\n\nPhạm vi: 12 họ × 51 ô (3 cửa sổ × 17 pipeline V0–V16) = {len(summ)} ô, {len(allh):,} dòng epoch.\n"
    "Họ mô hình: RNN, LSTM, GRU, BILSTM (F1), PATCHTST (F2), MANTIS_V2 (F3), cho hai tác vụ CQ và LO. Seed 43.\n\nTệp:\n"
    "- `m18_training_history_seed43.parquet|csv`: một dòng mỗi epoch (task, window_id, pipeline_id, model_name, seed, epoch và các cột loss, F1 validation, thời gian).\n"
    "- `m18_training_history_cell_summary_seed43.parquet|csv`: một dòng mỗi ô (số epoch, epoch tốt nhất theo manifest và theo F1 validation, F1 validation tốt nhất, tổng giây train).\n"
    "- `m43_stream.py`, `m43_build_m18.py`: script tạo gói (đọc `train_history.parquet` nguyên bản trong từng tệp kết quả trên Drive, và `history` của `f3_cell_record.json` với Mantis; không tính lại).\n"
    "- `sha256sums.txt`.\n\n"
    "Ghi chú nguồn: F1 từ `f1_recurrent_seed43_20261110`; PatchTST từ `patchtst_seed43_cells_20261112` (CQ) và `patchtst_seed43_cells_20261114` (LO); Mantis từ `mantis_v2_seed43_exploratory_20261111` (CQ) và `..._20261113` (LO). "
    "Cột `n_sources` và `sources_identical` cho biết ô nào có hơn một nguồn trên Drive và các nguồn đó có trùng nhau không. Seed 44 sẽ bổ sung khi chạy xong.\n"
    + (f"\nLưu ý phạm vi: các tổ hợp không đủ 51 ô: {bad}\n" if bad else ''), encoding='utf-8', newline='\n')
for f in ('m43_stream.py', 'm43_build_m18.py'):
    shutil.copy2(Path('C:/tmp_aud/m43') / f, OUT / f)
lines = []
for p in sorted(x for x in OUT.iterdir() if x.name != 'sha256sums.txt'):
    lines.append(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n')
(OUT / 'sha256sums.txt').write_text(''.join(lines), encoding='utf-8', newline='\n')
# runner commit check (item 4)
chk = man.copy()
chk['runner_git_commit'] = chk['runner_git_commit'].fillna('NULL')
cnt = chk.groupby(['task', 'model_name', 'runner_git_commit']).size().rename('cells').reset_index()
cnt.to_csv(C / 'runner_commit_check_seed43.csv', index=False, lineterminator='\n')
chk.drop(columns=['archive']).to_csv(C / 'runner_commit_check_seed43_cells.csv', index=False, lineterminator='\n')
print(cnt.to_string())
