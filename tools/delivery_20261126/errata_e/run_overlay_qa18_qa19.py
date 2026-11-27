# -*- coding: utf-8 -*-
"""Re-run QA18 and QA19 of release r2 with the two errata files as an overlay (item E.3).
The QA18 vectorised block and qa19_roles are copied from run_qa_release_r2.py (request B.2) (unchanged there).
Env: RELEASE_DIR, OUT_DIR (trailing slash). Writes qa18_qa19_with_errata.csv. The release is only read."""
import json, fnmatch, os, hashlib, runpy, tempfile, filecmp
from typing import Tuple
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__)).replace('\\', '/') + '/'
R = os.environ['RELEASE_DIR']
OUT = os.environ.get('OUT_DIR', HERE)
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()

df = pd.read_parquet(R + 'meta_dataset_seed_level.parquet')
dic = pd.read_csv(R + 'meta_column_dictionary.csv')
roles_err = pd.read_csv(OUT + 'release_r2_errata_column_roles.csv')
nulls_err = pd.read_csv(OUT + 'release_r2_errata_null_reasons.csv')
dic_sha = sha(R + 'meta_column_dictionary.csv')
N = len(df)

# ===== verbatim from run_qa_release_r2.py (repo qa19) =====
def qa19_roles(df: pd.DataFrame, dictionary: pd.DataFrame) -> Tuple[bool, pd.DataFrame]:
    roles = dict(zip(dictionary['column_name'], dictionary['role']))
    missing = [c for c in df.columns if c not in roles or not roles[c]]
    return len(missing) == 0, pd.DataFrame({'column_without_role': missing})

# ===== QA18 baseline (same vectorised block as run_qa_release_r2.py) =====
body = df.drop(columns=['null_reason_map'])
nullm = body.isna(); cols = list(nullm.columns); arr = nullm.to_numpy()
nrm = df.null_reason_map.fillna('{}').to_numpy()
miss_w = np.zeros(len(cols), dtype=np.int64)
for s_ in pd.unique(nrm):
    mp = json.loads(s_) if s_ else {}
    cw = np.array([(c in mp) or any(fnmatch.fnmatchcase(c, k) for k in mp if '*' in k) for c in cols])
    ii = np.where(nrm == s_)[0]
    miss_w += (arr[ii] & ~cw).sum(axis=0)
d18 = pd.DataFrame({'column': cols, 'n_null': arr.sum(axis=0), 'n_wo_reason': miss_w})
d18['is_reason_column'] = d18.column.str.endswith('_reason')
dd = d18[(d18.n_null > 0) & ~d18.is_reason_column]
nnull = int(dd.n_null.sum()); base_bad = int(dd.n_wo_reason.sum()); base_cols = int((dd.n_wo_reason > 0).sum())

# ===== reproducibility: rebuild both errata files into a temp dir and compare bytes =====
tmp = tempfile.mkdtemp(prefix='errata_chk_', dir=os.environ.get('TMP_DIR', HERE)) + '/'
os.environ['OUT_DIR'] = tmp
runpy.run_path(HERE + 'build_null_errata.py', run_name='__rebuild__')
runpy.run_path(HERE + 'build_roles_errata.py', run_name='__rebuild__')
same_null = filecmp.cmp(tmp + 'release_r2_errata_null_reasons.csv', OUT + 'release_r2_errata_null_reasons.csv', shallow=False)
same_roles = filecmp.cmp(tmp + 'release_r2_errata_column_roles.csv', OUT + 'release_r2_errata_column_roles.csv', shallow=False)

# ===== QA18 with overlay =====
chk = []
e = nulls_err.set_index('column_name')
chk.append(('errata sha256 == release dictionary sha256', bool((nulls_err.column_dictionary_sha256 == dic_sha).all() and (roles_err.column_dictionary_sha256 == dic_sha).all())))
chk.append(('errata columns == columns with NULL w/o reason (excl *_reason)', set(e.index) == set(dd[dd.n_wo_reason > 0].column)))
chk.append(('n_null_without_reason per column equals recomputed', bool((e.n_null_without_reason == dd.set_index('column').n_wo_reason.reindex(e.index)).all())))
chk.append(('no reason code empty', bool(e.proposed_reason_code.notna().all())))
unexpl = int(e.n_cells_not_explained.sum()); expl = int(e.n_cells_explained_by_rule.sum())
chk.append(('errata files reproduce byte-identical from scripts', bool(same_null and same_roles)))
qa18_fail = base_bad - expl if all(ok for _, ok in chk) else base_bad   # if any consistency check fails the overlay is not accepted
qa18_fail = max(qa18_fail, 0) if all(ok for _, ok in chk) else base_bad
qa18_status = 'PASS' if qa18_fail == 0 else 'FAIL'

# ===== QA19 with overlay =====
un0 = dic[dic.role == 'UNASSIGNED']
valid_roles = set(dic.role.unique()) - {'UNASSIGNED'}
r = roles_err.set_index('column_name')
ov = dic.copy()
ov['role'] = [r.proposed_role[c] if (role == 'UNASSIGNED' and c in r.index) else role for c, role in zip(ov.column_name, ov.role)]
ok19, _ = qa19_roles(df.drop(columns=[]), ov)
still_un = int((ov.role == 'UNASSIGNED').sum())
bad_role = int((~roles_err.proposed_role.isin(valid_roles)).sum())
chk19 = [('errata columns == UNASSIGNED columns of dictionary', set(r.index) == set(un0.column_name)), ('one row per column', bool(roles_err.column_name.is_unique)), ('proposed roles all exist in dictionary', bad_role == 0)]
qa19_fail = still_un + bad_role if all(ok for _, ok in chk19) else len(un0)
qa19_status = 'PASS' if qa19_fail == 0 and ok19 else 'FAIL'
nc = len(dic)

rows = [
    dict(check_id='QA18', status=qa18_status, n_units_checked=nnull, n_pass=nnull - qa18_fail, n_fail=qa18_fail,
         note=(f'Overlay release_r2_errata_null_reasons.csv. Trước overlay: {base_bad} ô NULL không có lý do thuộc {base_cols} cột (bảng QA gốc không đổi: FAIL). Sau overlay: {expl} ô được quy tắc cấu trúc giải thích '
               f'(kiểm trên bảng seed-level), {unexpl} ô không được giải thích. Kiểm nhất quán: ' + '; '.join(f'{k}={"OK" if ok else "LỖI"}' for k, ok in chk) +
               '. Mã lý do đề xuất, chưa có trong null_reason_map của release; release giữ nguyên, cần tác giả xác nhận mã mới. Ô NULL của cột *_reason không tính (như QA gốc).')),
    dict(check_id='QA19', status=qa19_status, n_units_checked=nc, n_pass=nc - qa19_fail, n_fail=qa19_fail,
         note=(f'Overlay release_r2_errata_column_roles.csv. Trước overlay: {len(un0)} cột role = UNASSIGNED (FAIL, bảng QA gốc không đổi). Sau overlay: {still_un} cột còn UNASSIGNED, {bad_role} role đề xuất không có trong từ điển; '
               'Kiểm nhất quán: ' + '; '.join(f'{k}={"OK" if ok else "LỖI"}' for k, ok in chk19) +
               '. Role là ĐỀ XUẤT chưa được tác giả chấp nhận; cột ambiguity MEDIUM/HIGH cần xác nhận (đặc biệt nếu role là X_STATE/X_CONTEXT, tức thành input meta-model).')),
]
out = pd.DataFrame(rows)
out.to_csv(OUT + 'qa18_qa19_with_errata.csv', index=False, encoding='utf-8-sig', lineterminator='\n')
print(out.drop(columns='note').to_string()); print(chk, chk19)
