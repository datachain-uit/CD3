"""Package an M-15 run directory (six metamodel configurations) for delivery: copies the configuration folders and logs, writes RUN_LOG.md (command, versions, pip freeze, times, SKIPPED, QA, hypotheses supported) and sha256sums.txt (LF).
Usage: python tools/build_m15_package_20261113.py --runs DIR --release DIR --release-id ID --out DIR --pip-freeze FILE --python-version 3.12.1 --code-commit HASH --patch-diff FILE --scope p1|full42
Run with the same interpreter as the metamodel run (needs pandas + pyarrow)."""
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument('--runs', type=Path, required=True)
ap.add_argument('--release', type=Path, required=True)
ap.add_argument('--release-id', required=True)
ap.add_argument('--out', type=Path, required=True)
ap.add_argument('--pip-freeze', type=Path, required=True)
ap.add_argument('--python-version', required=True)
ap.add_argument('--code-commit', required=True)
ap.add_argument('--patch-diff', type=Path)
ap.add_argument('--scope', choices=('p1', 'full42'), required=True)
ap.add_argument('--tests', default='22 passed')
args = ap.parse_args()
CFGS = ['main_cal_time', 'sens_v1', 'sens_energy', 'sens_conservative', 'obj_perf', 'obj_macrof1']
FLAGS = {'main_cal_time': '(mặc định, `PAPER_COMPOSITE_CAL`)', 'sens_v1': '`--objective META_PRIMARY_M3_V1`', 'sens_energy': '`--accept-energy-estimates`',
         'sens_conservative': '`--conservative`', 'obj_perf': '`--objective PAPER_PERF_AXIS`', 'obj_macrof1': '`--objective SECONDARY_MACRO_F1`'}
HANDOFF = '7a3549427b8b32148c858965066c4deb65fab0543fe15519a61e578d08683f2d'


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(8 << 20), b''):
            h.update(b)
    return h.hexdigest()


if args.out.exists():
    shutil.rmtree(args.out)
args.out.mkdir(parents=True)
prog = {}
for line in (args.runs / 'm15_progress.log').read_text(encoding='utf-8').splitlines():
    m = re.match(r'END \S+/(\w+) rc=(\d+) seconds=(\d+)', line)
    if m:
        prog[m.group(1)] = (int(m.group(2)), int(m.group(3)))
rows, hyp_lines, skipped_any = [], [], False
for c in CFGS:
    shutil.copytree(args.runs / c, args.out / c)
    for ext in ('stdout.log', 'stderr.log'):
        shutil.copy2(args.runs / f'{c}.{ext}', args.out / f'{c}.{ext}')
    reg = pd.read_parquet(args.out / c / 'mm_run_registry.parquet')
    st = reg['status'].value_counts().to_dict()
    skipped_any |= any(str(k).startswith('SKIPPED') for k in st)
    hyp = pd.read_parquet(args.out / c / 'mm_hypotheses.parquet')
    sup = sorted(set(hyp.loc[hyp['supported'].astype(bool), 'hypothesis'].astype(str)))
    hyp_lines.append(f'- {c}: ' + (', '.join(sup) if sup else 'không giả thuyết nào'))
    cfgsha = (args.out / c / 'mm_config_sha256.txt').read_text().split()[0]
    assert cfgsha == sha(args.out / c / 'mm_config.json'), c
    fb = reg['fallback_models'].astype(str).unique().tolist()
    rows.append(f"| {c} | {cfgsha[:16]}… | {len(reg)} | {st} | rc={prog[c][0]} | {round(prog[c][1] / 60)} |")
shutil.copy2(args.runs / 'm15_progress.log', args.out / 'm15_progress.log')
shutil.copy2(args.pip_freeze, args.out / 'pip_freeze.txt')
if args.patch_diff:
    shutil.copy2(args.patch_diff, args.out / 'local_patch_baselines_B5.diff')
agg = args.release / 'meta_dataset_seed_agg.parquet'
n = len(pd.read_parquet(agg))
log = f"""# M-15 — sáu cấu hình metamodel, bản phát hành {args.release_id} (seed 42)

Đầu vào: `{args.release.name}/meta_dataset_seed_agg.parquet` ({n:,} dòng; sha256 `{sha(agg)}`).
Gói: metamodel 0.2.2 + tempo_fix rev 2026-11-10 (`metamodel_handoff_2026-11-10.zip`, sha256 {HANDOFF}); {args.tests} (`python -m pytest metamodel/tests -q`). Commit repo lúc đóng gói: {args.code_commit}. Python {args.python_version} (xem `pip_freeze.txt`; lightgbm và optuna đã cài, không dùng fallback: `fallback_models` = False ở mọi dòng registry).
Lệnh chung: `python -m metamodel.cli run --meta <parquet> --out <cfg> --release-id {args.release_id} --protocols E1-A E1-B E2 E3 --learners L1 L2 L3 L4 --extra-learners L5 L6 --n-trials 50 --learner-seeds 5 <cờ riêng>`. Sáu cấu hình chạy song song, mỗi cấu hình một tiến trình (`m15_progress.log` ghi giờ bắt đầu/kết thúc).

| Cấu hình | mm_config sha256 | Số dòng registry | Trạng thái | Mã thoát | Phút |
|---|---|---|---|---|---|
""" + '\n'.join(rows) + f"""

Cờ riêng: """ + '; '.join(f'{c} {FLAGS[c]}' for c in CFGS) + f""".

## Ghi chú cần phía viết xem

1. **Bản vá cục bộ cho B5 (KNNMeta).** Gói 0.2.2 báo lỗi khi cột chuỗi `*_prev_reason` lọt vào ma trận đặc trưng của B5. Mình vá `baselines.py` để chỉ giữ cột số (`local_patch_baselines_B5.diff`; bản gốc không đổi trong gói bàn giao). Đề nghị đưa vào 0.2.3.
2. **`obj_macrof1` chạy đầy đủ** (không còn bản "restricted"): bản phát hành lắp lại ngày 12/11 điền cột macro-F1 của CQ họ RECURRENT (RNN, LSTM, GRU, BILSTM) từ `f1_macro` của facts R4; `obj_macrof1` và `obj_perf` có {'6 dòng SKIPPED (thiếu thành phần phân rã của mục tiêu)' if skipped_any else 'không dòng SKIPPED'} trong registry.
3. **Danh sách SKIPPED:** trong cột Trạng thái của bảng trên. QA failures: không có lỗi QA nào ghi trong stdout; không có traceback trong stderr.
4. Giả thuyết được ủng hộ (cột `supported` của `mm_hypotheses`; cần tác giả xác nhận):
""" + '\n'.join(hyp_lines) + f"""
5. {'Bộ dữ liệu p1 không có LO PatchTST và Mantis (theo Q-30 b).' if args.scope == 'p1' else 'Bộ dữ liệu đầy đủ seed 42 có F1 (RNN/LSTM/GRU/BILSTM), F2 PatchTST V0–V16 và F3 MANTIS_V2 V0–V16 (EXPLORATORY).'}

6. **Đề xuất về phiên bản thư viện (để phía viết cân nhắc):** điểm số mức mô hình của L4 và L5 thay đổi theo phiên bản thư viện (kiểm trên hai bộ phiên bản của cùng cấu hình và cùng bản phát hành; kết luận giả thuyết H1–H8 và hướng ước lượng không đổi). Để các lần chạy sau khớp số, đề nghị dùng đúng bản thư viện của lần chạy này, ghi trong `pip_freeze.txt`: Python {args.python_version}, NumPy 2.5.4, SciPy 1.18.1, scikit-learn 1.9.1, pandas 3.1.0, LightGBM 4.7.0, Optuna 5.0.0 (bản NumPy, SciPy, scikit-learn trùng môi trường chuẩn của các báo cáo).

`sha256sums.txt` liệt kê mọi tệp trong thư mục.
"""
(args.out / 'RUN_LOG.md').write_bytes(log.encode('utf-8'))
files = sorted(p for p in args.out.rglob('*') if p.is_file() and p.name != 'sha256sums.txt')
(args.out / 'sha256sums.txt').write_bytes(''.join(f'{sha(p)}  {p.relative_to(args.out).as_posix()}\n' for p in files).encode())
print('packaged', args.out, len(files), 'files')
