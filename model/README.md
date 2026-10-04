# Model stage: CQ and LO

This folder is the model stage after imputation and optional augmentation. It
implements the four recurrent architectures present in the TEMPO baselines:
`RNN`, `LSTM`, `GRU`, and `BiLSTM`. Their recurrent/static fusion follows the
LO `V0_mask_DL` baseline; their four real P1--P4 time steps correct the older
CQ baseline, which fed all features as a single time step.

## Input contract

One logical model run has exactly **one shared checkpoint**. It is trained on
real TRAIN enrollment sequences P1--P4, validates each epoch on all four
validation prefixes, selects by mean validation Macro-F1 over P1--P4 (then
mean loss), and subsequently predicts each untouched test prefix P1--P4 once.
It never retrains, fine-tunes, refits preprocessing, or changes its head by
test phase.

This is phase-safe: V0 uses no synthetic rows; future-unavailable positions are
not read; raw IDs and high-cardinality codes are excluded; and V0 constant-fill
values are accompanied by explicit missingness and availability channels.

`rnn_v0_shared_phase_v1.json` is the locked initial configuration. The current
single-prefix CLI is retained only as a local smoke-test utility and must not be
used for protocol runs because it selects a distinct checkpoint per phase.

```text
augmentation L1                                      model input
--------------------------------------------------------------------------
.../model_inputs/split=TRAIN/phase_id=P2/             --train
    balanced_train.parquet

parent-imputer L1/model_inputs/validation.parquet     --validation
parent-imputer L1/model_inputs/test_P2.parquet        --test
```

Raw IDs and high-cardinality ID codes (`user/course/teacher/school`) are
excluded. Numeric inputs are already transformed with the imputer's
train-fitted RobustScaler; this stage never refits a scaler on validation or
test.

## V0_mask baseline

`V0_mask` is an input baseline: take V0-imputed features and concatenate the
explicit `missing__*`, `phase_available_*`, and modality-availability masks.
It does **not** infer a missing phase from an all-zero feature row. Run it with
`--input-mode v0_mask`; this forces `--use-masks`.

## First commands

```powershell
# Example: CQ, W1, P2, V2 augmented TRAIN, GRU.
python -m model.run --task CQ --window W1 --phase P2 --architecture gru `
  --train <balanced_train.parquet> `
  --validation <imputed_validation.parquet> `
  --test <imputed_test_P2.parquet> `
  --output-dir outputs/CQ/W1/P2/V2/gru

# V0_mask counterpart, using V0 artifacts and no augmentation.
python -m model.run --task CQ --window W1 --phase P2 --architecture lstm `
  --input-mode v0_mask `
  --train <v0_train.parquet> --validation <v0_validation.parquet> `
  --test <v0_test_P2.parquet> `
  --output-dir outputs/CQ/W1/P2/V0_mask/lstm
```

Each run writes `model.pt`, a run manifest, training history, validation/test
predictions and confusion matrices. Metrics include accuracy, balanced
accuracy, macro/weighted F1, per-class precision/recall/F1, G-mean, MCC and
Cohen's kappa.
# Official shared-checkpoint runner

The official RNN V0 execution is `modal_jobs/model_app.py`, not the older
single-prefix local smoke-test CLI. It uses one full P1--P4 real-TRAIN input,
selects one checkpoint by mean validation Macro-F1 across P1--P4, then
evaluates the frozen checkpoint on the four unmodified TEST prefix files.

```powershell
python -X utf8 -m modal run .\modal_jobs\model_app.py --task CQ --window W1 --seed 42
```

Artifacts and controlled names are specified in
[`NAMING_CONTRACT.md`](NAMING_CONTRACT.md). The current runner accepts the
registered `V0`–`V16` pipeline grid with `model_name=RNN` and stamps every new
run as `model_revision=recurrent_shared_phase_v2_3_epoch50`.  This revision
uses `max_epochs=50` with validation-only early stopping (`patience=5`), so it
does not force every cell to train for 50 epochs.
