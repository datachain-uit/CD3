# Data-quality baseline

Run this before fitting any imputer, augmentation method, or model.  It reads
the frozen `phase_views_v1` release only and writes reports; it never changes
the source Parquet files.

It produces one directory per task under `artifacts/dq_baseline_v1/`:

- `release_inventory.json`: absolute input path, file names/sizes, SHA-256,
  Parquet row counts, schema and run time;
- `scope_counts.csv`: sample, unique enrollment and unique offering counts for
  every window / split / prediction phase / label;
- `feature_quality.csv`: null rate, non-finite rate, zero rate, negative rate,
  min, max, mean and standard deviation for numeric input fields;
- `mask_quality.csv`: prevalence of `video_observed_mask`,
  `problem_observed_mask`, and `comment_observed_mask` by scope;
- `key_quality.csv`: null rates of identifiers and a streaming estimate of
  duplicate `(enrollment_id, window, split_id, phase)` records.  It is a
  screening signal; an exact duplicate audit can be run later on a database.
- `summary.json`: machine-readable headline results and failed/pass checks.

The scan is streaming (`--batch-size` rows at a time), so it does not load the
whole release into memory.  `--hash-files` is intentionally optional because
hashing each approximately 1 GB release is a separate full disk read.

Example on the current local downloads:

```powershell
$env:PYTHONPATH = "$PWD\.audit_parquet_reader;$PWD"
python -m tempo_core.dq.compute_baseline --task CQ
python -m tempo_core.dq.compute_baseline --task LO
python -m tempo_core.dq.review_baseline --task CQ
python -m tempo_core.dq.review_baseline --task LO
```

On a machine with about 2 GB free RAM, use `--batch-size 16384`.

`review_baseline` writes `quality_review.json`: a release gate plus explicit
feature-exclusion recommendations.  It distinguishes a blocking loss of split
keys from sparse behavioural fields, which must be handled by masks rather
than indiscriminate imputation.

The reports are a data baseline, not model-performance metrics.  Model metrics
(macro-F1, balanced accuracy, per-class recall, PR-AUC, calibration and so on)
belong after the first train-only preprocessing/model run.
