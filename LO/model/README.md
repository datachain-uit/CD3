# LO model stage

Use the shared implementation in [`../../model`](../../model). LO has label
`LO_performance_label_3` and feature regime `LO_FULL_EARLY`.

For phase `Pk`, train from the matching augmented `balanced_train.parquet`
when a V2/V3/V4/V6/V7/V8/V10/V11/V12/V14/V15/V16 pipeline is selected.
Validation and `test_Pk` always come from the unchanged parent-imputer run.
Use `V0_mask` with the V0 parent input and explicit masks; do not augment it.
## LO model contracts

Task-specific contracts live here; reusable PyTorch implementations remain in
the repository-root `model/` package so CQ and LO use the same audited
architecture. Each subdirectory pins LO's release, class vocabulary, output
tree, and execution identity.

- `patchtst/`: F2 task-trained causal PatchTST.
- `moment_small/`: F3 frozen MOMENT-Small encoder with a trainable task head.

Run a single cell through its task wrapper, for example:

```powershell
python .\LO\model\patchtst\run_vastai.py --data-root <release-root> --output-root <runs-root> --window W1 --pipeline-id V0 --seed 42
```
