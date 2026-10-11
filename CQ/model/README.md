# CQ model stage

Use the shared implementation in [`../../model`](../../model). CQ has label
`CQ_label_final` and feature regime `CQ_RAW_EARLY`.

For phase `Pk`, train from the matching augmented `balanced_train.parquet`
when a V2/V3/V4/V6/V7/V8/V10/V11/V12/V14/V15/V16 pipeline is selected.
Validation and `test_Pk` always come from the unchanged parent-imputer run.
Use `V0_mask` with the V0 parent input and explicit masks; do not augment it.
## CQ model contracts

Task-specific contracts live here; reusable PyTorch implementations remain in
the repository-root `model/` package so CQ and LO use the same audited
architecture. Each subdirectory pins CQ's release, class vocabulary, output
tree, and execution identity.

- `patchtst/`: F2 task-trained causal PatchTST.
- `moment_small/`: F3 frozen MOMENT-Small encoder with a trainable task head.
