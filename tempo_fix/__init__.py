"""tempo_fix — reference implementations for the v1.6 fixes of the
Natural + Temporal Meta-dataset plan (Journal_CD3).

Modules
-------
split_v2            time-ordered block re-cut (A + three slices), temporal-overlap audit, QA22
feature_dictionary  feature dictionary with is_label_proxy / regimes_included, label-proxy audit, QA23
registries          pipeline / model / metric / s_san / acctempo / rec-rule registries with sha256
seeds               deterministic seed derivation and run_id
sanity              six sanity components (v1 and v2), S_san+, S_perf, AccTEMPO_M3, log decomposition
metrics_extra       pr_auc_macro, roc_auc_macro_ovr, per-class specificity/gmean/AP, paired bootstrap
energy_nvml         in-process GPU energy meter (NVML counter or power integration) with NULL fallback
seen_flags          seen_learner / seen_course / seen_offering flags per prediction row
qa_checks           QA03, QA04, QA08, QA09, QA10, QA15, QA18, QA19, QA20, QA22, QA24
l3_pilot            meta_obs_id / rec_group_id keys, V0 pilot rows, column dictionary

Every module is standalone (numpy / pandas / scikit-learn only; pynvml optional) and is exercised by
tests/ on synthetic data. Column names follow the plan (Mo_ta_meta-dataset v1.6) and are configurable
through the Schema dataclasses where the user's tables may differ.
"""
__version__ = '1.6.0'
