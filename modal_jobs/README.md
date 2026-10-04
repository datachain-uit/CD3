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
```

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
Ridge conditional models for up to five iterations. Run V0 first as the baseline,
then run each learned variant on the same frozen window; never reuse an
imputer fitted in another window.

Each active release must include `release_manifest.json`; the applications
reject missing provenance, a V1 directory, a split/phase mismatch, duplicate
`enrollment_id`, or a model input without the non-predictive audit context
(offering, timeline, course, duration/long-offering and P1--P4 STRICT flags).

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
separate post-hoc comparison after paired prediction rows exist.
