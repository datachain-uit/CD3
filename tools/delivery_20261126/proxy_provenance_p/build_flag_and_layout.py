# -*- coding: utf-8 -*-
"""P.2 lo_proxy_flag_check.csv and P.3 lo_feature_layout_by_family.csv.
Run: python -I build_flag_and_layout.py   (env TEMPO_REPO_ROOT, P_OUT, B34, HANDOFF)"""
import os, sys, json, hashlib, re, importlib.util, tarfile
import pandas as pd

REPO = os.environ['TEMPO_REPO_ROOT']; OUT = os.environ['P_OUT']; B34 = os.environ['B34']; HAND = os.environ['HANDOFF']
FAMS = ['video_catalog_coverage', 'problem_catalog_coverage', 'problem_score_catalog_coverage']
SUF = ['', '_P1', '_P2', '_P3', '_P4']


def load(path, name):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s); sys.modules[name] = m; s.loader.exec_module(m)
    return m


fd = load(f'{HAND}/tempo_fix/feature_dictionary.py', 'feature_dictionary')
# LO_LABEL_PROXY_COLUMNS: the set literal is parsed from the source text (importing the module pulls heavy dependencies)
src = open(f'{REPO}/imputation_core/wide_imputation.py', encoding='utf-8').read()
blk = re.search(r'LO_LABEL_PROXY_COLUMNS = \{(.*?)\n\}', src, re.S).group(1)
LO_SET = set(re.findall(r'"([A-Za-z0-9_]+)"', blk))
release_dict = pd.read_csv(f'{REPO}/CQ/resuilt/meta_release_CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2/meta_column_dictionary.csv')
drive_dict = pd.read_parquet(f'{OUT}/src/drive_lo_feature_dictionary_W1.parquet')
cdir = f'{REPO}/LO/resuilt/final_score_contract_audit_v3_1_scored_signal_excluded/proxy_feature_contract'
contract = pd.read_parquet([os.path.join(cdir, f) for f in os.listdir(cdir) if f.endswith('.parquet')][0])
lay = json.load(open(f'{B34}/src/lo42prim/release=LO_STATIC_V2/lo_static_v2_seed42_20261026/models/RNN/runs/W1/V0/seed=42/feature_layout.json'))
dyn = set(lay['dynamic_bases'])


def base(n):
    return re.sub(r'_P[1-4]$', '', n)


rows = []
for fam in FAMS:
    for s in SUF:
        n = fam + s
        cr = fd.classify_feature(n)
        dd = drive_dict[drive_dict.feature_name == n]
        cc = contract[contract.canonical_column == n]
        rows.append(dict(
            family=fam, column_name=n, suffix=s or 'none',
            release_meta_column_dictionary_has_column=bool((release_dict.column_name == n).any()),
            release_meta_column_dictionary_has_is_label_proxy_field='is_label_proxy' in release_dict.columns,
            drive_historical_LO_feature_dictionary_row='present' if len(dd) else 'absent',
            drive_historical_LO_feature_dictionary_feature_role=(dd.feature_role.iloc[0] if len(dd) else ''),
            drive_historical_LO_feature_dictionary_has_is_label_proxy_field='is_label_proxy' in drive_dict.columns,
            registries_lo_proxy_contract_v3_declared_is_label_proxy=1,
            registries_declared_how=('canonical field listed' if not s else 'phase_variants_rule text (not enforced by code)'),
            audit_proxy_feature_contract_is_label_proxy_required=(int(cc.is_label_proxy_required.iloc[0]) if len(cc) else 'no row (base row carries suffix_policy=apply_to_unsuffixed_and_all_phase_suffix_variants)'),
            tempo_fix_feature_dictionary_classify_feature_is_label_proxy=int(cr.is_label_proxy),
            tempo_fix_classify_rule=cr.proxy_rule,
            repo_audit_lo_label_proxy_qa23_classify_is_label_proxy=1,   # base_name() strips _Pk, then tests CURRENT_GRADE_BASES
            qa4_qa23_py_dict_for_is_label_proxy_assumed=1,              # re.sub(_P[1-4]$) then LO_CANON
            wide_imputation_LO_LABEL_PROXY_COLUMNS_exact_match=(n in LO_SET),
            model_data_fit_layout_has_label_proxy_exclusion=False,
            in_RNN_feature_layout_dynamic_bases=(base(n) in dyn) if s else '',
            note=('exact-name list matches the unsuffixed name only; columns seen by the imputer and the model are always suffixed' if not s
                  else 'suffixed name: NOT matched by the exact-name list'),
        ))
pd.DataFrame(rows).to_csv(f'{OUT}/lo_proxy_flag_check.csv', index=False)

LOC = f'{B34}/src/lo42prim'
D42 = 'LO/L1_runs/S3_model/seed=42/primary/'
ITEMS = [
    ('RNN', 'release=LO_STATIC_V2/lo_static_v2_seed42_20261026/models/RNN/runs/W1/V0/seed=42/feature_layout.json'),
    ('LSTM', 'release=LO_STATIC_V2/lo_static_v2_seed42_20261026/models/LSTM/runs/W1/V0/seed=42/feature_layout.json'),
    ('GRU', 'release=LO_STATIC_V2/lo_static_v2_seed42_20261026/models/GRU/runs/W1/V0/seed=42/feature_layout.json'),
    ('BILSTM', 'release=LO_STATIC_V2/lo_static_v2_seed42_20261026/models/BILSTM/metadata/W1/V0/seed=42/feature_layout.json'),
    ('PATCHTST', 'family=PATCHTST/lo_patchtst_v0_seed42_20261107/W1/V0/PATCHTST/seed=42/feature_layout.json'),
]
out = []
for fam, rel in ITEMS:
    b = open(f'{LOC}/{rel}', 'rb').read(); j = json.loads(b)
    dynb = set(j['dynamic_bases']); md = set(j['mask_dynamic_columns'])
    r = dict(model_family=fam, seed=42, window='W1', pipeline='V0', drive_relative_path=D42 + rel,
             layout_sha256='sha256:' + hashlib.sha256(b).hexdigest(), layout_bytes=len(b), n_dynamic_bases=len(dynb),
             n_static_columns=len(j['static_columns']), n_mask_dynamic_columns=len(md),
             input_path='feature_layout.json -> model.data.transform_frame (dynamic block [rows,4,C])')
    for f in FAMS:
        r[f'{f}_in_dynamic_bases'] = f in dynb
        r[f'{f}_P1_P4_in_model_input'] = ';'.join(f'{f}_P{k}' for k in range(1, 5)) if f in dynb else ''
        r[f'missing__{f}_Pk_mask_channels'] = sum(1 for k in range(1, 5) if f'missing__{f}_P{k}' in md)
        r[f'{f}_in_static_columns'] = f in j['static_columns']
    r['commented_resource_catalog_coverage_in_dynamic_bases'] = 'commented_resource_catalog_coverage' in dynb
    r['course_problem_count_in_dynamic_bases'] = 'course_problem_count' in dynb
    r['course_problem_full_score_sum_in_dynamic_bases'] = 'course_problem_full_score_sum' in dynb
    out.append(r)

t = tarfile.open(f'{OUT}/src/mantis_lo_V0_W1_s42.tar.gz'); name = 'adapters/W1/channel_adapter.json'
b = t.extractfile(name).read(); j = json.loads(b); cn = j['channel_names']
r = dict(model_family='MANTIS_V2', seed=42, window='W1', pipeline='V0',
         drive_relative_path='LO/L1_runs/S3_model/seed=42/staging_incoming/mantis_v2_seed42_exploratory_20261109/V0/mantis_lo_V0_W1_20261109_results.tar.gz :: ' + name,
         layout_sha256='NO feature_layout.json in the Mantis result tar; sha256 of channel_adapter.json = ' + hashlib.sha256(b).hexdigest()
                       + '; resource_per_run layout hash of the release = sha256:847617755f0d0190efdc52ecada53772f24117e7034885e3432f609b604e17d1 (all 51 runs)',
         layout_bytes=len(b), n_dynamic_bases=len([c for c in cn if not c.startswith('missing__')]),
         n_static_columns='NOT_IN_ADAPTER (adapter covers the dynamic tensor only)', n_mask_dynamic_columns=sum(1 for c in cn if c.startswith('missing__')),
         input_path='f3_mantis/cell.py: arrays from model.data.transform_frame -> ChannelPCAAdapter (PCA %d components over %d channels, fitted on real TRAIN rows) -> frozen Mantis encoder -> linear probe' % (j['n_components'], j['n_channels']))
for f in FAMS:
    r[f'{f}_in_dynamic_bases'] = f in cn
    r[f'{f}_P1_P4_in_model_input'] = 'channel (the four prefixes share the channel; PCA mixes it with the other channels)' if f in cn else ''
    r[f'missing__{f}_Pk_mask_channels'] = 1 if f'missing__{f}' in cn else 0
    r[f'{f}_in_static_columns'] = ''
r['commented_resource_catalog_coverage_in_dynamic_bases'] = 'commented_resource_catalog_coverage' in cn
r['course_problem_count_in_dynamic_bases'] = 'course_problem_count' in cn
r['course_problem_full_score_sum_in_dynamic_bases'] = 'course_problem_full_score_sum' in cn
out.append(r)
df = pd.DataFrame(out)
df.to_csv(f'{OUT}/lo_feature_layout_by_family.csv', index=False)
pd.set_option('display.width', 250, 'display.max_colwidth', 120)
print(df.T.to_string())
print(pd.DataFrame(rows).drop(columns=['note', 'drive_relative_path'], errors='ignore').to_string())
