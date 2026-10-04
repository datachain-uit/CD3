# LO imputation V3.1

Independent LO imputation project, parallel to `Feature_extraction_LO`.

It consumes the frozen LO `phase_views_v3_1_scored_signal_excluded`; it never rewrites labels or
features. Read [PLAN.md](PLAN.md) before implementing a variant.

Core contract: for window `Wk`, fit encoder/scaler/imputer only on the union
of training samples in `P1`–`P4` (`TRAIN_POOLED_P1_P4`). Transform validation
and test with that frozen state. Labels, IDs, label provenance
(`performance_score`, proxy decision/reason) and future-unavailable values
are never imputed or exposed to the model.
