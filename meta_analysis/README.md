# Reproducing the meta-level analysis

This document and the packages `metamodel/` and `tempo_fix/` hold the code of the meta-level analysis (release `CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2`).
`metamodel/` is version 0.3.1 (26/11/2026) and `tempo_fix/` is registry revision 2026-11-26b; both are committed unchanged from the delivered package
(`handoff_2026-11-26_tree_sha256.txt` of that package lists the sha256 of each file; `.gitattributes` keeps the bytes as delivered, so check the blob, not a checkout that may convert line endings).

## Environment

Python 3.12.1 (CPython, Windows 11, AMD64), packages as in `requirements-meta.txt` (the `pip freeze` of the environment of record: phase C of 23-24/11/2026 and the control re-run of 26/11/2026 used the same set).
Every process ran with one thread: `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`, `NUMEXPR_NUM_THREADS` and `LOKY_MAX_CPU_COUNT` set to 1 and `PYTHONNOUSERSITE=1`;
`tools/subgroups_phaseB/run_metamodel_single_core.py` pins one process to one logical CPU. Learners with `n_jobs=-1` resolve to one thread under `LOKY_MAX_CPU_COUNT=1`.

## Inputs

- Meta-dataset release `CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2`: `meta_dataset_seed_agg.parquet`, `meta_dataset_seed_level.parquet`, `meta_column_dictionary.csv`, `meta_release_manifest.json`, `sha256sums.txt` (download: see the release assets; not stored in the repository because the tables exceed the file limits).
- Frozen configurations: `phaseC_frozen_configurations_r2.json` (repository root) (ten configurations with the sha256 of their `MMConfig`).

## The ten runs of phase C

Run from the root of this repository (the package `metamodel/` must be importable). `--expect-digest` stops the run (exit code 3) if the configuration differs from the frozen one;
`--digest-only` instead of `--expect-digest ... --progress` prints the digest without reading any table.

```
python -m metamodel.cli run --meta <release>/meta_dataset_seed_agg.parquet \
    --out <out>/full_main_cal_time --release-id CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2 \
    --protocols E1-A E1-B E2 E3 --learners L1 L2 L3 L4 --extra-learners L5 L6 --n-trials 50 --learner-seeds 5 --design full --progress \
    --expect-digest 7c17b34f6cdd17e73f664b4d710768a956967d8dc47f20081f4d2c21d1d74b2f
python -m metamodel.cli run --meta <release>/meta_dataset_seed_agg.parquet \
    --out <out>/full_sens_v1 --release-id CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2 \
    --protocols E1-A E1-B E2 E3 --learners L1 L2 L3 L4 --extra-learners L5 L6 --n-trials 50 --learner-seeds 5 --design full --objective META_PRIMARY_M3_V1 --progress \
    --expect-digest 65f7c9022ee2a9e5ba4dc7d98d61a449b0d81183b651d5fdd23484cd8ec87177
python -m metamodel.cli run --meta <release>/meta_dataset_seed_agg.parquet \
    --out <out>/full_sens_energy --release-id CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2 \
    --protocols E1-A E1-B E2 E3 --learners L1 L2 L3 L4 --extra-learners L5 L6 --n-trials 50 --learner-seeds 5 --design full --accept-energy-estimates --progress \
    --expect-digest a048bb3bd423b23080d8d6d470cba46c57b487c3cff8c76b5d81df46922bca42
python -m metamodel.cli run --meta <release>/meta_dataset_seed_agg.parquet \
    --out <out>/full_sens_conservative --release-id CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2 \
    --protocols E1-A E1-B E2 E3 --learners L1 L2 L3 L4 --extra-learners L5 L6 --n-trials 50 --learner-seeds 5 --design full --conservative --progress \
    --expect-digest a4be8b576bd25c4e89147275484dc95ca657c864d1f660daa39dab3265996dac
python -m metamodel.cli run --meta <release>/meta_dataset_seed_agg.parquet \
    --out <out>/full_obj_perf --release-id CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2 \
    --protocols E1-A E1-B E2 E3 --learners L1 L2 L3 L4 --extra-learners L5 L6 --n-trials 50 --learner-seeds 5 --design full --objective PAPER_PERF_AXIS --progress \
    --expect-digest aa76a61aacefaff21b379b72b1d0c2a75f1a52ad82a392378fc052a310e13a12
python -m metamodel.cli run --meta <release>/meta_dataset_seed_agg.parquet \
    --out <out>/full_obj_macrof1 --release-id CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2 \
    --protocols E1-A E1-B E2 E3 --learners L1 L2 L3 L4 --extra-learners L5 L6 --n-trials 50 --learner-seeds 5 --design full --objective SECONDARY_MACRO_F1 --progress \
    --expect-digest 25408bf302e7780144739258c82884d6e1042330d99e58688ffb1021998b7e10
python -m metamodel.cli run --meta <release>/meta_dataset_seed_agg.parquet \
    --out <out>/var_all_only_main --release-id CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2 \
    --protocols E1-A E1-B E2 E3 --learners L1 L2 L3 L4 --extra-learners L5 L6 --n-trials 50 --learner-seeds 5 --design full --training-subgroups all-only --progress \
    --expect-digest f3c2e88f8505156163390232626d90fec3714b8533ab2281058054cc531a4186
python -m metamodel.cli run --meta <release>/meta_dataset_seed_agg.parquet \
    --out <out>/var_task_pooled_main --release-id CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2 \
    --protocols E1-A E1-B E2 E3 --learners L1 L2 L3 L4 --extra-learners L5 L6 --n-trials 50 --learner-seeds 5 --design full --e1-scope pooled --progress \
    --expect-digest 6c1382b873d1de689892f8a94c33c88858b230c06cd15df316f6dc6bad30f733
python -m metamodel.cli run --meta <release>/meta_dataset_seed_agg.parquet \
    --out <out>/var_all_rows_baselines_main --release-id CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2 \
    --protocols E1-A E1-B E2 E3 --learners L1 L2 L3 L4 --extra-learners L5 L6 --n-trials 50 --learner-seeds 5 --design full --baseline-scope all-rows --progress \
    --expect-digest eeb15fd612f28a07326f872ea4c1167aec45ae57e8a5699182b4e99d9b1ac3b7
python -m metamodel.cli run --meta <release>/meta_dataset_seed_agg.parquet \
    --out <out>/var_drop_small_main --release-id CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2 \
    --protocols E1-A E1-B E2 E3 --learners L1 L2 L3 L4 --extra-learners L5 L6 --n-trials 50 --learner-seeds 5 --design full --small-subgroups drop-from-training --progress \
    --expect-digest 2f81db5fea1e5b186240cf0315504a5f48b0dbbd9923696eefea62eac0db0ca4
```

Recorded durations of the original runs: see `progress.log` in the results of phase C (six `full_*` runs in parallel, then four `var_*` runs, one CPU each).

## Negative control (MQ08) and bootstrap check

`run_negative_control_r2.py` (repository root, next to `metamodel/` and `tempo_fix/`, as in the delivered package) re-runs only the negative control of the ten configurations with metamodel 0.3.1 (dtype-preserving permutation), checks the bootstrap rows (`verify-bootstrap`) and recomputes the two labelled post hoc tables (`checks/post_hoc_h7_cost_r34b.py`; `checks/post_hoc_reference_writing_side/` holds the four reference tables of the writing side):

```
python run_negative_control_r2.py all   --runs <results of phase C> --release <release folder> --out <out>
python run_negative_control_r2.py tests --out <out>
python run_negative_control_r2.py report --runs <results of phase C> --out <out>
```

Run from the repository root: the driver locates the packages, the frozen configurations, `handoff_2026-11-26_tree_sha256.txt` and `checks/` relative to its own folder.
Scripts of the earlier dtype investigation of 24/11/2026 are in `tools/mq08_dtype_finding/`.

## Where the other steps live

Subgroup facts, S0 profile v5 and the release assembly: `tools/subgroups_phaseB/`. Phase C driver and packaging: `tools/subgroups_phaseB/run_phasec_r2_controller_20261123.py`, `finalize_phasec_r2_20261124.py`, `verify_phasec_parts_20261124.py`.
