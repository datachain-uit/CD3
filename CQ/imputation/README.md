# CQ imputation V2.2

Independent CQ imputation project, parallel to `Feature_extraction`.

It consumes the frozen CQ `phase_views_v2_2`; it never rewrites labels or
features. Read [PLAN.md](PLAN.md) before implementing a variant.

Core contract: for window `Wk`, fit encoder/scaler/imputer only on the union
of training samples in `P1`–`P4` (`TRAIN_POOLED_P1_P4`). Transform validation
and test with that frozen state. Labels, IDs, label provenance (`COELO_final`,
`AFELO_final`, `ACELO_final`, vector/proximity) and future-unavailable values
are never imputed or exposed to the model.

Before a CQ run, execute `Feature_extraction/validation/audit_cq_label_proxy.py`
on TRAIN/P4. It writes `feature_dictionary_v1`, a Spearman/NMI audit, the
approved `CQ_RAW_EARLY` imputer predictors, and a QA23 summary. Catalog/score
ratios and TRIAD-derived columns are excluded from the CQ raw imputer path;
an owner must explicitly review any remaining feature with `|rho| >= 0.50`.
