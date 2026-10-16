# Modal execution: locked CQ V2.2 and LO V3.1 releases

The Modal Volume `tempo-data-v1` is mounted at `/data`. Upload the downloaded
release once; every remote run then reads and writes inside that Volume.

Required remote layout:

```text
/data/input/CQ_v2_2/release_manifest.json
/data/input/CQ_v2_2/phase_views_v2_2/
/data/input/CQ_v2_2/test_prefix_views_v2_2/P1/ ... /P4/
/data/input/LO_v3_1/release_manifest.json
/data/input/LO_v3_1/phase_views_v3_1_scored_signal_excluded/
/data/input/LO_v3_1/test_prefix_views_v3_1_scored_signal_excluded/P1/ ... /P4/
/data/input/CQ_v2_2/materialization_lineage_v2_2/
/data/input/LO_v3_1/materialization_lineage_v3_1_scored_signal_excluded/
```

Use the checked PowerShell uploader after extracting the downloaded artifacts.
It uploads only the immutable `/input/...` release and does not delete or
modify prior L1/L2 artifacts:

```powershell
# Validate paths/markers only first.
.\modal_jobs\upload_release.ps1 -Task CQ `
  -PhaseViewsPath .\CQ\resuilt\phase_views_v2_2 `
  -TestPrefixesPath .\CQ\resuilt\test_prefix_views_v2_2 `
  -LineagePath .\CQ\resuilt\materialization_lineage_v2_2 `
  -AllowMissingSuccessMarker `
  -VerifyOnly

# Upload CQ V2.2 after validation.
.\modal_jobs\upload_release.ps1 -Task CQ `
  -PhaseViewsPath .\CQ\resuilt\phase_views_v2_2 `
  -TestPrefixesPath .\CQ\resuilt\test_prefix_views_v2_2 `
  -LineagePath .\CQ\resuilt\materialization_lineage_v2_2 `
  -AllowMissingSuccessMarker `
  -ReplaceExisting

# Upload LO V3.1 after validation.
.\modal_jobs\upload_release.ps1 -Task LO `
  -PhaseViewsPath .\LO\resuilt\phase_views_v3_1_scored_signal_excluded `
  -TestPrefixesPath .\LO\resuilt\test_prefix_views_v3_1_scored_signal_excluded `
  -LineagePath .\LO\resuilt\materialization_lineage_v3_1_scored_signal_excluded `
  -AllowMissingSuccessMarker `
  -ReplaceExisting
```

The paths may point either directly to the extracted release directory or to
its parent directory. The runner requires at least one Parquet file for phase
views and for each P1--P4 test-prefix directory before invoking Modal.
When replacing an already uploaded release, `-ReplaceExisting` is mandatory:
it removes only that release's phase views, test prefixes, and input manifest
before uploading. This prevents stale Parquet files being read alongside the
new release; it never removes L1/L2/L3 experiment outputs.

Each `release_manifest.json` must declare `task`, `release_id`,
`split_registry_id`, `split_version`, `phase_version`,
`feature_dictionary_version`, `label_rule_version`, and `label_threshold_set`. The active
values are `CQ_V2_2` / `cq_vector_proximity_v1_zero_activity_policy` and
`LO_V3_1` / `lo_final_score_catalog_normalized_v3_1`; old L1 artifacts are
intentionally not eligible as parents for these releases.

The App writes one frozen meta release to:

```text
/data/meta_release=imputation-v1/
  L0_registry/                         # data inventory, version IDs, feature dictionary, definitions
  L1_runs/task=.../feature_regime=.../window_id=.../pipeline_id=V*/model_name=IMPUTATION_ONLY/seed=.../
    run_id=.../attempt_id=0001/
      model_inputs/{train,validation,test_P1,...,test_P4}.parquet
      fitted_preprocessors/fitted_pipeline.joblib + sha256.json
      run_manifest.json
  L2_facts/{bin_scheme,dq_feature_profile,dataset_quality_summary,distribution_sketch,imputation_fidelity,resource_usage}/...
  L3_meta/imputation_diagnostic_seed_level/... # never merged into final model L3
```

Run `--mode s0` once for each task before any imputer. It materializes the
pipeline-independent, all-row S0_RAW census and locks ten quantile histogram bins from
TRAIN_POOLED_P1_P4.  An imputer run writes only S1_IMPUTED and must use its own
S1 train-fitted bins. Thus neither S0 facts nor histogram edges are duplicated
or re-fit on validation/test.

For every `(task, window)` imputer run, raw numeric predictors are log-adjusted
where appropriate, then imputed. `RobustScaler` is **fit only on observed
numeric values from that window's train split** and applied after imputation;
validation and test are transform-only. This keeps V0, Median and Mean
meaningfully distinct while preserving one scaling rule for every pipeline.
`user_id`, `course_id`, `teacher_id`, and `school_id`
are prefix-stripped identity codes, fitted as train-only categorical mappings
(unknown code `0`) and are never scaled or numerically imputed.

The L2 DQ facts use canonical partition keys `task`, `feature_regime`,
`window_id`, `phase_id`, `stage`, `run_id`, and `attempt_id`. `phase_id` is
always P1–P4; pooled fit artefacts use `fit_scope=TRAIN_POOLED_P1_P4`, never a
pseudo-phase such as `ALL`. Facts contain numerator/denominator counts,
missing/imputed/residual rates, structural/future guards, locked-bin
distribution sketches, and a bounded masked-validation MAE/RMSE/MedAE probe. Resource facts record
wall/process CPU time and peak RAM. These CPU imputers deliberately report no
GPU energy or billing value when Modal exposes no such telemetry.

Execution order:

```powershell
python -m modal run .\modal_jobs\imputation_app.py --mode s0 --task CQ
python -m modal run .\modal_jobs\imputation_app.py --mode s0 --task LO
python -m modal run .\modal_jobs\imputation_app.py --mode impute --task CQ --window W1 --test-phase ALL --variant v0
```

`extra_trees` and `mice` use CPU/RAM, not a GPU. Reserve GPUs for the later
LSTM/RNN/GRU stage; using one for sklearn imputation increases cost without
accelerating these estimators. S0 and imputation workers use 192 GiB RAM
because the all-row census and full-train learned imputers retain large
working matrices.

Available imputation variants are independent runs: `v0` (raw-zero fill before
the common scaler), `median`, `mean`, `extra_trees`, and `mice`. Median and
Mean fit exact univariate statistics on all training values. `extra_trees` preserves
the lightweight TEMPO baseline: `IterativeImputer(ExtraTreesRegressor)` with
one shallow tree (`max_depth=5`) and one iteration, fitted on all training
values for the current full-train experiment. `mice` uses full-train Bayesian
Ridge conditional models for up to three iterations, fitted on the locked
1,000,000-row sample. Run V0 first as the baseline,
then run each learned variant on the same frozen window; never reuse an
imputer fitted in another window.

Each active release must include `release_manifest.json`; the applications
reject missing provenance, a V1 directory, a split/phase mismatch, duplicate
`enrollment_id`, or a model input without the non-predictive audit context
(offering, timeline, course, duration/long-offering and P1--P4 STRICT flags).

## Seed-aligned augmentation and model grid

### Audit execution cadence

Avoid recomputing an audit merely because a report is regenerated.  The
following cadence is part of the execution contract:

| Artifact or audit | Re-run trigger |
| --- | --- |
| `materialization_lineage_*` | A new phase-view / label / feature release only. |
| QA23 label-proxy audit | A changed feature dictionary, label contract, or phase-view release only. |
| S0, S1 imputation, S2 augmentation | A changed input release or an explicitly changed augmentation-seed policy. |
| Per-class metrics, calibration, checkpoint selection | Written automatically by every S3 model run. |
| STRICT/OVERLAP prediction-slice audit | Once per distinct prediction grid (model family × seed × pipeline scope). |
| Report export | Reads existing immutable L2 facts; never retrains or recomputes model predictions. |

The registered F1 design is the full grid (17 pipelines x 4 recurrent models
x 3 windows x 3 seeds per task, `GRID_POLICY`); VALIDATION facts are reported
and used for the selection-margin check, not to shortlist pipelines. F2 is
also full-grid after its deterministic pilot. F3 MOMENT_SMALL is deferred until
F2 completes; its registered exploratory subset then requires a frozen-embedding
cache.
MOMENT_BASE is deferred from GĐ1. Do not use a TEST report refresh as a reason
to rerun S0--S3.

The registered stability policy is `MATCH_MASTER_SEED` (decision of
2026-10-05, `LO/registries.py` `EXPERIMENT_SEEDS`): one balanced S2 TRAIN
artifact per master seed `42`, `43`, `44`, and every S3 cell with master seed
`s` consumes the S2 artifact created with the same `s`.  The seed-42 pilot
needs only the seed-42 artifacts; the stability runs need all three.

```powershell
# One task: 3 windows × 4 imputer parents × 3 balancers × 3 master seeds.
.\modal_jobs\run_augmentation_grid.ps1 -Task CQ -Seeds 42          # pilot
.\modal_jobs\run_augmentation_grid.ps1 -Task CQ -Seeds 42,43,44    # stability

# The default policy of run_model_grid.ps1 is match_model_seed; no flag is needed.
.\modal_jobs\run_model_grid.ps1 `
  -Task CQ -Mode grid -Seeds 42,43,44
```

Use `-AugmentationSeedPolicy fixed -AugmentationSeed 42` only for a separately
registered fixed-augmentation sensitivity design; it is not the stability
protocol.

### Ordered temporal-family extension

`PATCHTST`, `MOMENT_SMALL`, and `MOMENT_BASE` use the same fitted numeric
prefix tensor, static branch, class order, validation selection, predictions,
and L2 fact schema as the recurrent models. PatchTST first runs the required
deterministic pilot twice on CQ/W1/V0/seed42 and then the F2 full grid.
MOMENT_SMALL is deferred until F2 is complete; its registered 13-pipeline F3
exploratory subset then requires frozen embedding caching.

```powershell
# Determinism acceptance: run this command twice and compare prediction/probability
# checksums, metrics, best_epoch, and manifest identity.
.\modal_jobs\run_model_grid.ps1 `
  -Task CQ -Mode pilot -Windows W1 -Pipelines V0 -Models PATCHTST -Seeds 42 `
  -AccumulationSteps 4

# F2 primary: full grid, after PatchTST determinism acceptance.  The registered
# configuration is 2,048 = 4 x 512; a single 2,048-row PatchTST pass does not
# fit a 24 GB L4.
.\modal_jobs\run_model_grid.ps1 `
  -Task CQ -Mode grid -Models PATCHTST -Seeds 42,43,44 `
  -AccumulationSteps 4

# F3 exploratory core, only after F2 is complete: five imputers, CDSMOTE and
# SASMOTE (13 pipelines). RadiusSMOTE is a separately-labelled sensitivity
# analysis because its registered fallback rate exceeds the warning threshold.
# Requires frozen embedding cache.
.\modal_jobs\run_model_grid.ps1 `
  -Task CQ -Mode grid `
  -Pipelines V0,V1,V5,V9,V13,V2,V6,V10,V14,V3,V7,V11,V15 `
  -Models MOMENT_SMALL -Seeds 42,43,44
```

PatchTST uses registered two-phase/stride-one prefix patches independently for
each dynamic channel with shared projection/Transformer weights; only its task
head combines post-encoder channel embeddings with static features. MOMENT uses the
official `momentfm` embedding model at its pinned repository revision with the
phase-as-patch encoding: each observed phase fills one pretrained patch
(`patch_len` repeats) and future phases are masked, because momentfm counts a
patch as observed only when every position is observed; the per-channel RevIN
statistics of the prefix are fused into the task head. A channel that is
constant over the observed prefix (every channel at P1, any cumulative feature
without later activity) is fed to the encoder as exact zeros
(`constant_channel_guard`, revision `moment_frozen_linear_probe_v2_1_phase_patch`):
momentfm's RevIN divides by `std + 1e-5`, so float32 rounding of the mean would
otherwise enter the pretrained encoder as pseudo-signal of order 1e-2; the
channel level still reaches the head through the RevIN statistics. The encoder is frozen (`FROZEN_LINEAR_PROBE`), its
resolved snapshot is recorded in the run manifest, and only the shared task
head is checkpointed. The initial snapshot download is cached under
`/data/model_cache/huggingface`; do not treat a first-download wall time as
measured model training time.

### Portable VastAI runner (tools/vastai_train_shared.py)

The portable runner trains one cell with the same `model.shared_phase`
implementation, seeds and salted prediction ids as S3, but it is a second
execution backend. Its outputs are comparable with Modal cells only under the
same conditions, which the runner now enforces or records:

- The registered S3 hardware is NVIDIA L4 (bf16 AMP). The runner refuses any
  other GPU unless `--allow-gpu-mismatch` is passed, and records
  `execution_backend`, `gpu`, `cuda_capability`, `torch_version`,
  `cuda_version`, `cudnn_version` and `cublas_workspace_config` in
  `run_manifest.json` and `metadata_contract.json`.
- `CUBLAS_WORKSPACE_CONFIG=:4096:8` is set by the runner before CUDA starts;
  strict determinism fails otherwise.
- The portable runner attempts 1-second NVML power sampling when `pynvml` is
  available.  Its output is explicitly an estimate
  (`NVML_POWER_SAMPLING_ESTIMATE`), not a hardware total-energy counter.  If
  telemetry is unavailable, it persists `NOT_MEASURED`; neither kWh nor CO2e
  is inferred from wall-clock, RAM, or VRAM.  Do not pool estimated VastAI
  energy with counter-measured Modal energy in a single ranking.
- The bundle must ship `release_core/` next to `model/`: the release
  vocabulary is imported from `release_core.contracts.RELEASE_SPECS`, not
  copied (a copy drifted on 2026-10-12 for the LO `label_threshold_set`).
- Audited VastAI facts can be ingested without copying model tensors into the
  Modal Volume.  `ingest_lo_vastai_facts_app.py` validates 204 metadata
  contracts, model metrics, resource rows, and the six post-hoc fact families into L2 under
  `execution_backend=vastai_portable_runner`, with an immutable L0 receipt.
  They use the explicit compact external layout (family × window partitions;
  run, phase, and split remain columns) and therefore cannot collide with
  Modal-native `S3_MODEL` partitions.  The audit bundle must be complete
  before this command is run:

  ```powershell
  python -X utf8 -m modal run .\modal_jobs\ingest_lo_vastai_facts_app.py --mode ingest
  python -X utf8 -m modal run .\modal_jobs\ingest_lo_vastai_facts_app.py --mode status
  python -X utf8 -m modal run .\modal_jobs\export_lo_vastai_facts.py
  ```
  The exporter reads only those immutable L2 partitions and writes the normal
  report bundle under `L2_facts/report_exports/task=LO/`; it does not retrain,
  recompute predictions, or read a local VastAI output tree.
- The registered optimisation batch is 2048 rows for every family. The
  channel-independent PatchTST does not fit that batch with the 274 CQ
  channels on a 24 GB L4, so it is run with gradient accumulation
  (`--accumulation-steps 4`: four 512-row micro-batches, one optimiser step
  per 2048 rows; `run_model_grid.ps1 -AccumulationSteps 4` on Modal). The
  update equals the full-batch update; `batch_size`, `micro_batch_size` and
  `accumulation_steps` are recorded in the manifest. A plain `--batch-size 512`
  changes the registered protocol and must not be used for grid cells.
- Balanced TRAIN follows MATCH_MASTER_SEED: the tree holds one S2 artifact per
  master seed (`train/<W>/<V>/seed=<s>/balanced_train.parquet`, or the flat
  path for a single-seed tree), and the runner refuses a cell whose artifact
  comes from another S2 seed unless `--augmentation-seed-policy fixed` is
  passed for a registered sensitivity design.

## LO V3.1: model-ready execution path

LO uses the same immutable Modal applications as CQ; it is not a separate
model implementation. The LO lock is deliberately stricter:

```text
/data/input/LO_v3_1/
  release_manifest.json                     # split=v3_1, phase=wide_prefix_v3_1
  phase_views_v3_1_scored_signal_excluded/    # TRAIN + VALIDATION P1--P4
  test_prefix_views_v3_1_scored_signal_excluded/P1/ ... /P4/ # immutable TEST prefixes
```

The release manifest must declare the catalog-normalised source-faithful LO
label release; the worker rejects a V1/V2 split or label artifact rather than
silently using it.

Run order after this input release is uploaded:

```powershell
# S0 once, then one imputation run per window/pipeline.
python -X utf8 -m modal run .\modal_jobs\imputation_app.py --mode s0 --task LO --seed 20260922

foreach ($w in "W1","W2","W3") {
  python -X utf8 -m modal run .\modal_jobs\imputation_app.py `
    --mode impute --task LO --window $w --test-phase ALL `
    --variant v0 --fit-sample-rows 0 --seed 20260922
}

# First GPU pilot: model plus 8 validation/test sanity records.
.\modal_jobs\run_model_grid.ps1 `
  -Task LO -Mode pilot -Windows W1 -Pipelines V0 -Models RNN -Seeds 42
```

The generic runner accepts `-Task LO` for all four recurrent architectures
(`RNN`, `LSTM`, `GRU`, `BILSTM`) and all V0--V16 pipelines. For LO W2/W3 it
also materializes the registered small-support facts; paired bootstrap is a
separate post-hoc comparison after paired prediction rows exist. It also writes
the registered offering-cluster sensitivity when a class appears in no more
than two offerings:

```powershell
python -X utf8 -m modal run .\modal_jobs\model_bootstrap_app.py `
  --task LO --window W2 --pipeline-id V1 --reference-pipeline-id V0 `
  --model-name RNN --seed 42 --repetitions 2000
```

## Ingesting audited VastAI F1 facts

Portable VastAI output is not a substitute for an L2 fact export.  Before it
can appear in a CQ or LO report, retain the compact artifact bundle locally:
every `run_manifest.json`, `metadata_contract.json`, `train_history.parquet`,
`metrics_overall.parquet`, and the post-hoc `audits/` tree.  Do not upload
model checkpoints or model inputs for this step.

The same importer serves one task per invocation.  It verifies all 204
contracts (four recurrent families x three windows x 17 pipelines), preserves
the portable run ID, checks that each `run_manifest.json` matches the SHA-256
recorded in its contract, requires one runner revision and NVIDIA L4 across
the grid, then writes immutable backend-partitioned L2 facts and an L0 receipt.

```powershell
# CQ: set the local bundle roots after downloading the VastAI outputs.
$env:VASTAI_TASK = "CQ"
$env:VASTAI_INGEST_ID = "vastai_f1_seed42_clean_20261016_r1"
$env:CQ_VASTAI_ARTIFACT_ROOT = ".\CQ\resuilt\vastai_f1_batch2048_seed42"
$env:CQ_VASTAI_AUDIT_ROOT = ".\CQ\resuilt\vastai_f1_batch2048_seed42\audits"
python -X utf8 -m modal run .\modal_jobs\ingest_lo_vastai_facts_app.py --mode ingest
python -X utf8 -m modal run .\modal_jobs\ingest_lo_vastai_facts_app.py --mode status
python -X utf8 -m modal run .\modal_jobs\export_lo_vastai_facts.py

# LO uses the same application; its existing r2 bundle is the default.
$env:VASTAI_TASK = "LO"
$env:VASTAI_INGEST_ID = "vastai_f2_seed42_clean_20261015_r2"
python -X utf8 -m modal run .\modal_jobs\ingest_lo_vastai_facts_app.py --mode status
```

The importer imports facts only: it neither reruns training nor rewrites L1
artifacts. Historical runs with `energy_measurement=NOT_MEASURED` retain that
status. Only runs that actually contain NVML sampling metadata are exported as
`NVML_POWER_SAMPLING_ESTIMATE`.

For a completed CQ recurrent grid on VastAI, create the required audit bundle
before downloading it. The command is post-hoc and CPU-only relative to the
saved predictions; it needs all 51 completed cells for each family:

```bash
cd /workspace/CD3
bash code/vastai_run_cq_f1_audit.sh
```

It creates, for each of RNN/LSTM/GRU/BiLSTM, canonical parent-real-row
`S_leak`, sanity components, per-class support/recall, bootstrap CI
(`B=2000`), STRICT/OVERLAP metrics, and checkpoint-selection facts. Download
those `runs/audits_seed42/CQ/` files together with the compact run metadata
before invoking the Modal importer.
