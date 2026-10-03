# LO V1

Canonical LO pipeline uses the operational performance label: `I/D < 60`,
`G = 60--84`, `E >= 85`. This remains a behavioural-performance proxy, not
an observed completion or dropout outcome.

Run in order:

1. `python -m labels.build_lo_labels`
2. `python -m features.build_scenario_phase_features`
3. `python -m views.materialize_label_stratified_views`

The split fixes A as the earliest 60% of whole offerings. B--G are allocated
deterministically by label counts while preserving whole offerings. Each split
has P1, P2, P3 and P4; labels are fixed across phases.
