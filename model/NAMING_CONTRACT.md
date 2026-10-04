# Naming contract — recurrent V0 runs

This contract is derived from `AGENT_READY_EXPERIMENT_REEXECUTION_GUIDE.md`
and `Mo_ta_meta-dataset.docx`. All persisted field names are ASCII
`snake_case`; identifiers are deterministic SHA-256 hashes of canonical JSON
(`sort_keys=True`, compact separators). Python's built-in `hash()` is forbidden.

## Controlled values

```text
task:              CQ | LO
feature_regime:    CQ_RAW_EARLY | LO_FULL_EARLY
window_id:         W1 | W2 | W3
phase_id:          P1 | P2 | P3 | P4
pipeline_id:       V0 .. V16
pipeline_name:     RAW_CONSTANT_FILL_WITH_MASKS | IMPUTE_ONLY | IMPUTE_AND_BALANCE
model_family:      F1_RECURRENT
model_name:        RNN
model_revision:    recurrent_shared_phase_v2_3_epoch50
input_mode:        v0_mask
adaptation_mode:   from_scratch
cohort_type:       FIXED
eval_split:        VALIDATION | TEST
sample_type:       real
stage:             S3_MODEL
```

`V0` is a model-input baseline, not a NaN-to-network baseline: its constant
fill rule and explicit masks must be referenced from `pipeline_registry`.

## Identity and paired-seed fields

```text
master_seed
seed_index
seed_model       = stable_hash(master_seed, "model", task, window_id, model_name)
seed_dataloader  = stable_hash(master_seed, "loader", task, window_id, model_name)
seed_sampler     = stable_hash(master_seed, "sampler", task, window_id, pipeline_id)
```

The paired `seed_index` is identical across competing pipelines for the same
task/window/model. Seeds never define split membership.

```text
run_id = sha256(canonical_json({
  task, feature_regime, label_rule_version, label_threshold_set,
  window_id, master_seed, model_name, pipeline_id,
  hparam_config_id, data_release_id, split_version
}))

attempt_id = <run_id>-<attempt_number:04d>
```

The initial RNN-V0 baseline uses `master_seed=42`, `gpu_type=L4`, and
`precision_policy=bf16_amp`.  A model run may proceed only when its parent
imputation manifest explicitly has `split_version=v2_2`,
`phase_version=wide_prefix_v2_2`, a feature-dictionary version, and a label
rule version.  The resolver never uses an unqualified “latest” artifact.

For V2--V4, V6--V8, V10--V12, and V14--V16, only the full P1--P4 TRAIN
sequence is read from `BALANCED_TRAIN_ONLY`; VALIDATION and all four TEST
prefixes are always read from the matching parent imputation run.  An
augmentation manifest must state `validation_test_touched=false`.

`run_group_id = run_id`; it groups the four phase predictions from the one
shared checkpoint. `rec_group_id` is created later by the L3 builder from the
meta-observation key with `pipeline_id` omitted.

## Paths

```text
meta_release=imputation-v1/
|- L0_registry/
|  |- model_registry/model_name=RNN/model_revision=recurrent_shared_phase_v2_3_epoch50.json
|  |- run_registry/run_id=<run_id>.json
|  `- environments/attempt_id=<attempt_id>.json
|- L1_runs/
|  `- task=<task>/feature_regime=<feature_regime>/window_id=<window_id>/
|     pipeline_id=<V0..V16>/model_name=<RNN|LSTM|GRU|BILSTM>/seed=<master_seed>/
|     run_id=<run_id>/attempt_id=<attempt_id>/
|     |- run_manifest.json
|     |- checkpoint/model.pt
|     |- train_history.parquet
|     |- predictions/eval_split=<VALIDATION|TEST>/phase_id=<P1|P2|P3|P4>/part-00000.parquet
|     |- probability_matrices/eval_split=<VALIDATION|TEST>/phase_id=<P1|P2|P3|P4>/part-00000.parquet
|     |- timing.parquet
|     |- resource_timeseries.parquet
|     `- SUCCESS | FAILED.json
`- L2_facts/
   `- <fact_name>/task=<task>/feature_regime=<feature_regime>/window_id=<window_id>/
      phase_id=<phase_id>/stage=S3_MODEL_INPUT/pipeline_id=V0/model_name=RNN/
      run_id=<run_id>/attempt_id=<attempt_id>/part-00000.parquet
```

`fact_name` is one of `metrics_overall`, `metrics_per_class`,
`bootstrap_metrics_per_class`, `checkpoint_selection`, `confusion_matrix`,
`calibration`, `sanity_components`, or `resource_usage`.
Training cost is written once at run level with
`cost_shared_across_phases=true`; it must not be added four times in L3.

## Small-support contract

Every phase and evaluation split writes `metrics_per_class` with
`n_support` and `small_support_flag = (n_support < 400)`. For LO W2/W3 only,
flagged classes additionally write `bootstrap_metrics_per_class` using 2,000
stratified bootstrap draws and a 95% interval. Checkpoint selection remains
validation-only (`mean_validation_macro_f1_p1_p4`) and writes
`checkpoint_selection.selection_margin` (best minus second-best epoch score).

Comparing two completed LO W2/W3 pipelines is a separate post-hoc L3 action:
align their TEST predictions by `enrollment_id_hash`, verify identical
`y_true`, then use the registered paired 2,000-draw bootstrap. It never
chooses a checkpoint or changes a split.

## Class order and prediction columns

```text
CQ: c0=warning, c1=average, c2=good
LO: c0=I/D,     c1=G,       c2=E
```

The class mapping is fitted from real TRAIN only and frozen in both checkpoint
and manifest. Prediction columns are always:

```text
run_id, attempt_id, task, feature_regime, window_id, seed_index,
model_family, model_name, model_revision, pipeline_id, phase_id,
cohort_type, eval_split, enrollment_id_hash, y_true, y_pred,
prob_c0, prob_c1, prob_c2, observed_length, sample_type,
inference_latency_ms
```

Raw entity identifiers never leave L1 prediction input: stored prediction IDs
are salted hashes, while `sample_type` for validation/test is always `real`.
Each probability matrix is row-aligned to its prediction table and contains
only `enrollment_id_hash`, `prob_c0`, `prob_c1`, and `prob_c2`.
