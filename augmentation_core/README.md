# Augmentation core — CQ and LO

This package implements the three balancing methods registered by the MDS
protocol: `CDSMOTE`, `SASMOTE`, and `RADIUS_SMOTE`. `SASMOTE` means
**Self-Inspected Adaptive SMOTE** (Kosolwattana et al., 2023,
doi:10.1186/s13040-023-00330-4): visible-minority-neighbour interpolation plus
random-forest self-inspection. It is not the legacy TEMPO notebook called
``sasmote.ipynb``: that notebook implements ordinary minority-neighbour SMOTE
and uses an inaccurate name.

The older LO notebooks are not copied directly: they use legacy five-class
labels, differ from CQ in the CDSMOTE/Radius construction, and one SASMOTE
notebook fabricates fractional `user_id` values. That violates the current
train-only identity-code contract.

The paper defines a binary procedure. Our registered SASMOTE applies its
visible-neighbour and inspection rules separately to each minority class versus
all other labels. The literal paper construction would fit one balanced random
forest inspector for every majority partition, which is impractical on CQ/LO.
The implementation uses a bounded number of balanced inspectors; its cap,
observed majority coverage, candidate acceptance, and every algorithm parameter
are persisted in the L1 manifest as `algorithm_audit`. It must therefore be
reported as `SASMOTE_self_inspected_adaptive_v1`, not as an unqualified exact
reproduction of the paper.

## Non-negotiable execution contract

1. Balance **TRAIN only**, after the selected imputer has produced finite
   model features. Validation and test are never augmented.
2. Invoke one balancer per `task × window_id` on the complete training
   sequence (`phase_id=P4`, meaning P1–P4 are all present). This matches the
   TEMPO RNN/LSTM/GRU/BiLSTM protocol: train once on complete sequences and
   evaluate untouched P1–P4 test-prefix views with timestep masks.
3. Pass the complete numeric, scaled model vector: dynamic `P1..P4` **and**
   all numeric static features. Do not interpolate labels,
   raw identities, offering IDs, `user_id_code`, `course_id_code`, teacher or
   school codes. Categorical context is inherited from `parent_a` and stored
   in the synthetic ledger.
4. Build availability masks by `INTERSECTION_OF_PARENTS`; build missingness
   flags by union of the two parents. The helpers in `contracts.py` implement
   these rules.
5. Persist every synthetic row in an L1 synthetic ledger with `synthetic_id`,
   `parent_a`, `parent_b`, `alpha`, `method`, task/window/phase/pipeline/run,
   and the label. This makes synthetic data auditable and excludes it from
   validation/test metrics.

`ledger.materialize_synthetic_rows()` is the only supported assembly helper:
it rejects interpolated identity codes, gives each generated row a synthetic
identifier, retains parent IDs only in the ledger, inherits categorical context
from parent A, and applies the two mask rules above.

Use `ledger.augmentable_model_columns(source, label_column, "P4")` to form
the interpolation matrix. It includes the complete model input `P1..P4 +
static` and rejects IDs, categorical codes, labels, missing flags and
availability masks. Each synthetic sequence has coherent P1–P4 values from
the same two parents.

## Registered pipeline mapping

`V2/V6/V10/V14` use CDSMOTE; `V3/V7/V11/V15` use SASMOTE; and
`V4/V8/V12/V16` use RadiusSMOTE. The imputer-only parents are respectively
`V1`, `V5`, `V9`, and `V13`.

## Storage and partitioning contract

`storage.py` is the only supported path builder. A balancing attempt requires
the complete key:

```text
task, feature_regime, window_id, pipeline_id, model_name, seed,
run_id, attempt_id, split=TRAIN, phase_id, cohort, stage=S2_BALANCED
```

The baseline augmentation artifact uses `phase_id=P4` as the explicit marker
for a complete P1–P4 training sequence. It is created once per task/window/
parent-imputer/balancer. Test prefix artifacts are never augmented.

```text
meta_release=imputation-v1/
|- L0_registry/
|  |- pipeline_registry.json        # V2-V16: parent imputer, balancer, rules
|  |- run_registry/                 # immutable scientific run metadata
|  `- environments/                 # software / CPU-GPU provenance per attempt
|- L1_runs/
|  `- task=.../feature_regime=.../window_id=.../pipeline_id=.../
|     model_name=.../seed=.../run_id=.../attempt_id=.../
|     |- run_manifest.json
|     |- synthetic_ledger/phase_id=P*/part-00000.parquet
|     `- model_inputs/split=TRAIN/phase_id=P*/balanced_train.parquet
|- L2_facts/
|  |- class_distribution/.../split=TRAIN/phase_id=P*/cohort=.../stage=S2_BALANCED/...
|  |- balance_audit/...              # train-only, phase-only, lineage/mask QA
|  |- dq_feature_profile/...         # data quality after balance
|  |- dataset_quality_summary/...
|  |- distribution_sketch/... and drift_measures/...
|  `- resource_usage/...             # wall/CPU/RAM/GPU for balancing
`- L3_meta/                          # model-level diagnostics only, later
```

L1 is row-level provenance: its ledger has grain `run_id x synthetic_id`, and
is written once per immutable `attempt_id`. L2 is long-form measurement only;
it stores no full synthetic feature matrix. The balanced input in L1 is needed
by the next model-training step; it is never used to change validation or test.

Required S2 audit fields include real/synthetic/total row counts per class,
post-balance share and imbalance ratio, parent lineage completeness,
`SAME_PHASE_ONLY`, `TRAIN_ONLY`, finite numeric values, no interpolated
identity code, availability-mask intersection and missing-flag union. Parquet
artifacts use Zstandard compression and are atomically renamed only after a
successful write.
