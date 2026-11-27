# -*- coding: utf-8 -*-
"""Doc fitted_pipeline.joblib KHONG thuc thi ma cua file: Unpickler thay moi lop/ham bang lop gia (stub) ghi lai
duong dan va trang thai; chi cho phep dung that: joblib.numpy_pickle.NumpyArrayWrapper, numpy ndarray/dtype/_reconstruct
(de doc mang). Moi 'GLOBAL' khac (sklearn, pandas, imputation_core, ...) -> stub. Khong goi __reduce__ cua doi tuong la.
Dung: python -I qa21_c_safe_inspect_joblib.py <file.joblib> <out.json>
(chay trong tien trinh con; file la san pham cua chinh chuoi S1 cua du an, tai ve thu muc rieng)"""
import sys, json, pickle, io
import numpy as np
from joblib.numpy_pickle import NumpyUnpickler

ALLOW = {('numpy', 'ndarray'), ('numpy', 'dtype'), ('numpy.core.multiarray', '_reconstruct'), ('numpy._core.multiarray', '_reconstruct'),
         ('numpy.core.multiarray', 'scalar'), ('numpy._core.multiarray', 'scalar'),
         ('joblib.numpy_pickle', 'NumpyArrayWrapper'), ('numpy', 'float64'), ('numpy', 'int64'), ('numpy', 'bool_')}
SEEN = {}


class Stub:
    _path = None

    def __new__(cls, *a, **k):
        o = object.__new__(cls)
        o._args = a
        return o

    def __setstate__(self, st):
        self._state = st

    def __call__(self, *a, **k):  # ham gia (vi du mot ham duoc goi qua REDUCE)
        return Stub()


def make_stub(mod, name):
    key = f'{mod}.{name}'
    if key not in SEEN:
        SEEN[key] = type(name, (Stub,), {'_path': key})
    return SEEN[key]


class SafeUnpickler(NumpyUnpickler):
    def find_class(self, module, name):
        if (module, name) in ALLOW:
            return super().find_class(module, name)
        return make_stub(module, name)


def describe(o, depth=0, path='root', out=None, seen=None):
    out = out if out is not None else []
    seen = seen if seen is not None else set()
    if id(o) in seen or depth > 6 or len(out) > 4000:
        return out
    seen.add(id(o))
    if isinstance(o, Stub):
        st = getattr(o, '_state', None)
        out.append({'path': path, 'kind': 'stub', 'class': o._path})
        if isinstance(st, dict):
            for k, v in st.items():
                describe(v, depth + 1, f'{path}.{k}', out, seen)
        elif st is not None:
            describe(st, depth + 1, f'{path}.__state__', out, seen)
        for i, a in enumerate(getattr(o, '_args', ())):
            describe(a, depth + 1, f'{path}.__args__[{i}]', out, seen)
    elif isinstance(o, dict):
        if 'category_maps' in path:   # khoa la ma dinh danh nguoi hoc/khoa hoc: chi ghi so luong, khong ghi gia tri
            out.append({'path': path, 'kind': 'dict', 'n': len(o), 'keys': 'omitted (identifiers)'})
            return out
        out.append({'path': path, 'kind': 'dict', 'keys': [str(k) for k in list(o)[:60]], 'n': len(o)})
        for k, v in list(o.items())[:80]:
            describe(v, depth + 1, f'{path}[{k!r}]', out, seen)
    elif isinstance(o, (list, tuple)):
        if o and all(isinstance(x, str) for x in o):
            out.append({'path': path, 'kind': 'list_str', 'n': len(o), 'values': list(o)})
        else:
            out.append({'path': path, 'kind': type(o).__name__, 'n': len(o)})
            for i, v in enumerate(o[:12]):
                describe(v, depth + 1, f'{path}[{i}]', out, seen)
    elif isinstance(o, np.ndarray):
        e = {'path': path, 'kind': 'ndarray', 'shape': list(o.shape), 'dtype': str(o.dtype)}
        if o.dtype.kind in 'OUS' and o.ndim == 1 and o.size <= 5000:
            e['values'] = [str(x) for x in o.tolist()]
        out.append(e)
    elif isinstance(o, (str, int, float, bool, type(None))):
        out.append({'path': path, 'kind': 'scalar', 'value': o})
    else:
        out.append({'path': path, 'kind': type(o).__name__})
    return out


if __name__ == '__main__':
    src, dst = sys.argv[1], sys.argv[2]
    from joblib.numpy_pickle import _validate_fileobject_and_memmap
    with open(src, 'rb') as f:
        with _validate_fileobject_and_memmap(f, src, None) as (fobj, _):   # mo tep (khong giai pickle)
            obj = SafeUnpickler(src, fobj, True).load()
    items = describe(obj)
    # tom tat chuoi hoi quy cua IterativeImputer: moi bo ba = (feat_idx, neighbor_feat_idx, estimator)
    for side in ('dynamic_imputer', 'static_imputer'):
        imp = (getattr(obj, '_state', None) or {}).get(side)
        st = getattr(imp, '_state', None) if imp is not None else None
        if not isinstance(st, dict):
            items.append({'path': side, 'kind': 'summary', 'note': 'khong co imputer (hoac khong phai IterativeImputer)'})
            continue
        seq = st.get('imputation_sequence_') or []
        feats, nlens, nsets = [], [], []
        for tr in seq:
            a = getattr(tr, '_args', None) or ()
            if len(a) >= 2:
                feats.append(int(a[0])); nb = np.asarray(a[1]).astype(int).tolist(); nlens.append(len(nb)); nsets.append(nb)
        items.append({'path': side, 'kind': 'summary', 'n_sequence': len(seq), 'n_distinct_target_idx': len(set(feats)),
                      'target_idx_sorted': sorted(set(feats)), 'neighbor_len_min': min(nlens) if nlens else None, 'neighbor_len_max': max(nlens) if nlens else None,
                      'n_features_in_': (int(st['n_features_in_']) if 'n_features_in_' in st else None),
                      'feature_names_in_': ([str(x) for x in np.asarray(st['feature_names_in_']).tolist()] if 'feature_names_in_' in st else None),
                      'neighbor_idx_first_triplet': (nsets[0] if nsets else None)})
    json.dump({'source_file': src.replace('\\', '/').split('/')[-2] + '/' + src.replace('\\', '/').split('/')[-1], 'stub_classes_seen': sorted(SEEN), 'items': items}, open(dst, 'w', encoding='utf-8'), ensure_ascii=False)
    print('ok', len(items), 'stub classes', len(SEEN))
