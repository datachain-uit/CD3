# CQ V1

Canonical CQ pipeline: vector label `[COELO, AFELO, ACELO]`, Euclidean
proximity to `[1, 1, 1]`, and classes `warning < 0.10`,
`average < 0.30`, `good >= 0.30`.

Run in order:

1. `python -m labels.build_cq_labels`
2. `python -m features.build_scenario_phase_features`
3. `python -m views.materialize_label_stratified_views`
4. `python -m validation.audit_cq_labels`

The split fixes A as the earliest 60% of whole offerings. B--G are allocated
deterministically by label counts while preserving whole offerings. Each split
has P1, P2, P3 and P4; labels are fixed across phases.
