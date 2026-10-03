# TEMPO CQ/LO experiment pipeline

Repository này chứa phần đặc thù CQ/LO và các Modal entry point để tạo dữ liệu
theo pha P1--P4, chạy điền khuyết, cân bằng lớp và huấn luyện mô hình tuần tự.

## Phạm vi repository

Commit hiện tại cố ý chỉ gồm `CQ/`, `LO/` và `modal_jobs/`; dữ liệu, report
Word và TEMPO shared source không được đưa vào repository này. Trước khi chạy
Modal, đặt/cài các package dùng chung từ repository đồng hành ở Python path:

```text
imputation_core/
augmentation_core/
metrics_core/
model/
tempo_core/
```

Các package trên là dependency runtime của `modal_jobs/`, không phải artifact
thực nghiệm. Hai task được giữ tách biệt trong `CQ/` và `LO/`.

## 1. Cấu trúc mã nguồn

```text
CQ/Feature_extraction/          # CQ: label, feature, split, view, audit
LO/Feature_extraction_LO/       # LO: label, feature, split, view, audit
modal_jobs/                     # Modal entry points
README.md                        # this run guide
```

`CQ/` and `LO/` are not sufficient on their own for the Modal stages: their
views are inputs for `modal_jobs/`, which imports the shared packages above.

## 2. Prerequisites

Use Python 3.12+, install the companion shared packages, then authenticate the
desired Modal account:

```powershell
python -m modal setup
python -m modal profile current
```

The repository never stores a personal Databricks path. In the Databricks job
or notebook, set the Volume roots before running CQ/LO Spark code:

```python
import os

os.environ["TEMPO_OUTPUT_BASE"] = "/Volumes/<catalog>/<schema>/<volume>/preprocessed"
os.environ["TEMPO_RAW_BASE"] = "/Volumes/<catalog>/<schema>/<volume>/raw"
```

`PROJECT_ROOT` is optional when executing an uploaded `.py` file. For copied
notebook cells, set it to the repository subproject that contains `common/`:

```python
os.environ["PROJECT_ROOT"] = "/Workspace/.../CQ/Feature_extraction"
# or
os.environ["PROJECT_ROOT"] = "/Workspace/.../LO/Feature_extraction_LO"
```

Do not commit a filled runtime-path file; keep it in the job/notebook
environment.

## 3. Stage S0 -- label, split, and phase views (Databricks/Spark)

Run this stage separately for CQ and LO. Upload the relevant
`CQ/Feature_extraction/` or `LO/Feature_extraction_LO/` folder with its
`common/`, `config/`, `labels/`, `features/`, and `views/` children intact.

Recommended order:

1. Build the task label from `labels/build_cq_labels.py` or
   `labels/build_lo_labels.py`.
2. Build or select the frozen split registry in `views/`.
3. Materialize the matching phase views and P1--P4 TEST prefixes.
4. Run the release-specific label/split audits before treating a registry as
   locked.

The version folders under `views/` and `labels/` are navigation maps. The
executable entry points remain at the parent directory until a release is
frozen and all Databricks commands have been migrated together.

Current release contracts:

| Task | Split / phase release | Input feature regime |
|---|---|---|
| CQ | `v2_2` / `wide_prefix_v2_2` | `CQ_RAW_EARLY` |
| LO | `v3_1` / `wide_prefix_v3_1` | `LO_FULL_EARLY` |

## 4. Stage S0 profile and S1 imputation (Modal)

Materialize the input profile once per task after its views are frozen:

```powershell
python -X utf8 -m modal run .\modal_jobs\imputation_app.py --mode s0 --task CQ --seed 20260922
python -X utf8 -m modal run .\modal_jobs\imputation_app.py --mode s0 --task LO --seed 20260922
```

Then run each input pipeline for each required window. `--test-phase ALL`
creates P1--P4 TEST prefixes. `fit-sample-rows 0` means all TRAIN rows;
MICE is normally sampled because it is iterative and expensive.

```powershell
# V0: deterministic constant fill plus missingness masks
python -X utf8 -m modal run .\modal_jobs\imputation_app.py --task CQ --window W1 --test-phase ALL --variant v0 --fit-sample-rows 0 --seed 20260922

# V1, V5, V9: full-TRAIN estimators
python -X utf8 -m modal run .\modal_jobs\imputation_app.py --task CQ --window W1 --test-phase ALL --variant median      --fit-sample-rows 0 --seed 20260922
python -X utf8 -m modal run .\modal_jobs\imputation_app.py --task CQ --window W1 --test-phase ALL --variant mean        --fit-sample-rows 0 --seed 20260922
python -X utf8 -m modal run .\modal_jobs\imputation_app.py --task CQ --window W1 --test-phase ALL --variant extra_trees --fit-sample-rows 0 --seed 20260922

# V13: MICE; transform applies to all rows, fit is sampled.
python -X utf8 -m modal run .\modal_jobs\imputation_app.py --task CQ --window W1 --test-phase ALL --variant mice --fit-sample-rows 1000000 --seed 20260922
```

Repeat the commands with `--task LO` and `--window W1`, `W2`, or `W3`. The
pipeline mapping is fixed:

| Pipeline | Meaning |
|---|---|
| `V0` | constant fill + masks |
| `V1` | median |
| `V5` | mean |
| `V9` | ExtraTrees |
| `V13` | MICE |

## 5. Stage S2 augmentation (TRAIN only)

Augmentation reads the full P1--P4 TRAIN sequence from its parent imputation
run. Validation and all TEST prefixes remain real, unmodified data.

```powershell
# Example: CQ/W1, median parent V1, CDSMOTE -> V2
python -X utf8 -m modal run .\modal_jobs\augmentation_app.py `
  --task CQ --window W1 --phase P4 --parent-pipeline V1 --method CDSMOTE --seed 42

# Status check without writing any data
python -X utf8 -m modal run .\modal_jobs\augmentation_app.py `
  --mode status_all_windows --task CQ --balance-pipelines V2,V6,V10,V14 --seed 42
```

| Parent input | CDSMOTE | SASMOTE | RadiusSMOTE |
|---|---:|---:|---:|
| median `V1` | `V2` | `V3` | `V4` |
| mean `V5` | `V6` | `V7` | `V8` |
| ExtraTrees `V9` | `V10` | `V11` | `V12` |
| MICE `V13` | `V14` | `V15` | `V16` |

Valid methods are `CDSMOTE`, `SASMOTE`, and `RADIUS_SMOTE`.

## 6. Stage S3 models and sanity facts

Run a single reproducible cell directly:

```powershell
python -X utf8 -m modal run .\modal_jobs\model_app.py `
  --task CQ --window W1 --pipeline-id V0 --model-name RNN --seed 42 `
  --split-version v2_2 --phase-version wide_prefix_v2_2

python -X utf8 -m modal run .\modal_jobs\model_sanity_app.py `
  --task CQ --window W1 --pipeline-id V0 --model-name RNN --seed 42 `
  --split-version v2_2 --phase-version wide_prefix_v2_2
```

For LO, use `--split-version v3_1 --phase-version wide_prefix_v3_1`.

The recommended launcher runs model then sanity for every planned cell and
records local logs. Start small; `grid` can be expensive.

```powershell
# Official one-cell pilot
.\modal_jobs\run_model_grid.ps1 -Task CQ -Mode pilot -Seeds 42

# Explicit one-window grid, one model, one seed
.\modal_jobs\run_model_grid.ps1 `
  -Task CQ -Mode grid -Windows W1 -Pipelines V0,V1,V5,V9,V13 `
  -Models RNN -Seeds 42
```

Default recurrent configuration uses L4 GPU, bf16 AMP, maximum 50 epochs,
early stopping, and seed 42. Valid model names are `RNN`, `LSTM`, `GRU`, and
`BILSTM`.

## 7. Outputs and verification

Artifacts are organized by immutable release:

```text
meta_release=imputation-v1/
├── L0_registry/  # input/split/schema/environment/run registries
├── L1_runs/      # immutable imputation, augmentation, model artifacts
├── L2_facts/     # metrics, sanity, calibration, drift, resource facts
└── L3_meta/      # later aggregated meta-dataset
```

Before comparing pipelines, verify all of the following from each manifest:

- matching task, `split_version`, `phase_version`, and label rule;
- `run_status: SUCCESS` and no remaining numeric nulls after imputation;
- augmentation has `validation_test_touched: false`;
- model predictions, probability matrices, confusion matrices, metrics and
  sanity facts exist for VALIDATION and TEST/P1--P4;
- compare predictive quality primarily with AccTEMPO, then Macro-F1 and
  calibration/resource facts.

Use the dedicated export jobs only after a complete experiment slice:

```powershell
python -X utf8 -m modal run .\modal_jobs\export_cq_rnn_facts.py
python -X utf8 -m modal run .\modal_jobs\export_lo_rnn_facts.py
```

## 8. Safe Git workflow

Commit source, contracts, version maps, and Markdown documentation. Do not
commit Modal downloads, parquet artifacts, logs, credentials, or runtime
paths.

```powershell
git add README.md CQ LO modal_jobs
git status
```

Review `git status` before every commit, especially after downloads or report
exports.
