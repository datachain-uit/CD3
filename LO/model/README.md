# LO model stage

Use the shared implementation in [`../../model`](../../model). LO has label
`LO_performance_label_3` and feature regime `LO_FULL_EARLY`.

For phase `Pk`, train from the matching augmented `balanced_train.parquet`
when a V2/V3/V4/V6/V7/V8/V10/V11/V12/V14/V15/V16 pipeline is selected.
Validation and `test_Pk` always come from the unchanged parent-imputer run.
Use `V0_mask` with the V0 parent input and explicit masks; do not augment it.
