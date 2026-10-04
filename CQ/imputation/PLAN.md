# CQ imputation V2.2 — execution plan

This project is independent of `Feature_extraction`. Input is the downloaded,
immutable `CQ/phase_views_v2_2` release; output is local Python artifacts.

## 1. Freeze and validate input

Read the release inventory, schema and DQ baseline before any model fit. The
grain is one enrollment/window/split/prediction-phase record. Required scope:
`W1..W3 × train/validation/test × P1..P4`. Keep `enrollment_id` and
`offering_id` only as provenance/split keys, never as predictors.

## 2. Declare feature roles

Build `contracts/feature_roles_v1.yaml` from the downloaded schema.

- Exclude: labels, enrollment/offering IDs, split/phase/provenance columns, CQ vector-label
  components (`COELO_final`, `AFELO_final`, `ACELO_final`), proximity and
  distance.
- Exclude V1: `age_at_enroll`, because the DQ baseline found impossible
  values; do not impute it.
- Categorical: only explicitly approved low-cardinality fields; fit encoder
  on training data only.
- `user_id` and `course_id`: strip `U_`/`C_`, parse the suffix as an integer
  categorical code, and fit a training-only vocabulary with `UNK` for unseen
  validation/test IDs. They are never numerically scaled or imputed.
- Numeric observable: eligible for imputation only when genuinely
  observed-missing.
- Structural absence: activity/comment-dependent NULL with its modality mask
  false. Preserve it and its mask; never turn it into an imputed observation.
- Future unavailable: never imputed. It is represented only in the derived
  wide snapshot, with an explicit availability mask.

## 3. Build cumulative wide snapshots

The immutable feature release remains long. Before the task split is assigned,
the feature pipeline pivots it into one legacy-compatible wide row per
enrollment. The split materializer then assigns windows to these already-wide
rows. A time-varying feature keeps one column per observed phase:
`watch_count_P1`, `watch_count_P2`, and so on.

- Train and validation retain the complete P1--P4 row. Only each window's
  test partition is emitted as four prefix files: P1 masks P2--P4, P2 masks
  P3--P4, P3 masks P4, and P4 is complete.
- New phases extend the schema additively (`*_P5`, `*_P6`, ...); old columns
  never change meaning.
- Masked test blocks have `phase_available_Pk=0`; they are never imputed,
  fitted, or interpreted as observed zero activity.
- Static features occur once, without a phase suffix.

## 4. Fit/transform boundary (after the split)

For each `Wk`, concatenate `train × P1..P4` and fit one feature contract,
encoder, scaler and imputer state: `TRAIN_POOLED_P1_P4`. Apply that frozen
state to each of train/validation/test at each P separately. No validation or
test statistic may affect fitting, feature selection, clipping or category
vocabulary.

## 5. Imputation variants

Run in this order: V0 raw-with-neutral-fill-and-masks, median/mode baseline,
mean baseline, iterative ExtraTrees, then MICE. A GPU deep imputer is optional
and may be introduced only after these baselines pass masked-value evaluation.
CPU methods are expected for median/MICE/ExtraTrees; renting GPU is most useful
for downstream sequence models unless a deep imputer demonstrably improves
validation metrics.

## 6. Evaluation before augmentation/modeling

Mask a fixed sample of values that were originally observed in the *training*
partition. Compare recovered values with truth using MAE, median AE and NRMSE
per feature family and phase. Also report: imputation rate, remaining NULLs,
mask preservation, invalid-range rate and train→validation/test distribution
drift (PSI/JSD). Do not score structural or future-unavailable cells as
imputation errors.

## 7. Outputs per window

`artifacts/Wk/<variant>/` contains: feature-role contract hash, fitted state,
feature order/hash and imputed cumulative wide snapshots,
imputation audit, masked-value evaluation, run manifest and seed. Augmentation
is a later train-only consumer of these artifacts; it never changes validation
or test.
