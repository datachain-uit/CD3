# MDS metric core

`evaluation.py` implements the locked three-class performance contract from
`Mo_ta_meta-dataset.docx`: per-class metrics, Macro-F1, balanced accuracy,
MCC, kappa, PR-AUC, G-mean, log-loss, Brier, ECE, the six `S_san+` components,
`AccTEMPO_M3`, and paired bootstrap confidence intervals.

Every model runner must persist sample-level predictions with:
`enrollment_id`, `window`, `prediction_phase`, `y_true`, `y_pred`, and
`prob_c0`, `prob_c1`, `prob_c2`.  Aggregate metrics must be recomputed from
that artifact, never only from training logs.
