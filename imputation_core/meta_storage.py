"""L1/L2/L3 storage and data-quality facts for imputation-only runs.

This module intentionally does not compute classification scores: an imputer
has no predictions.  It emits the reproducible data-quality and resource facts
that later model runs join to their prediction-derived metrics.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .wide_imputation import COUNT_RE, PHASES, PHASE_SUFFIX_RE, _structural_mask

DQ_DEF_VERSION = "1.0.0"
METRIC_DEF_VERSION = "1.0.0"
META_SCHEMA_VERSION = "1.0.0"
FEATURE_REGIME = {"CQ": "CQ_RAW_EARLY", "LO": "LO_FULL_EARLY"}
COHORT = {"CQ": "FIXED", "LO": "RISK_SET"}
PIPELINE_ID = {"v0": "V0", "median": "V1", "mean": "V5", "extra_trees": "V9", "mice": "V13"}
SCALING_CONTRACT = {
    "version": "numeric_robust_scale_v2",
    "numeric_log_transform": "log1p_on_nonnegative_count_duration_features_only",
    "scaler": "RobustScaler",
    "fit_scope": "TRAIN_ONLY__dynamic_pooled_P1_P4__static_train_rows",
    "imputation_space": "RAW_LOG_NUMERIC",
    "scale_order": "IMPUTE_THEN_SCALE__SCALER_FIT_ON_OBSERVED_TRAIN_VALUES_ONLY",
    "validation_test": "TRANSFORM_ONLY",
    "id_columns": "PREFIX_STRIPPED_TRAIN_ONLY_CATEGORICAL_CODES__NOT_SCALED__NOT_IMPUTED",
    "binary_masks": "NOT_SCALED__NOT_IMPUTED",
}
IMPUTER_PARAMS = {
    "v0": {"fill": 0.0, "imputer": "NONE"},
    "median": {"strategy": "median", "fit_rows": "ALL_TRAIN"}, "mean": {"strategy": "mean", "fit_rows": "ALL_TRAIN"},
    "extra_trees": {
        "estimator": "ExtraTreesRegressor",
        "n_estimators": 1,
        "max_depth": 5,
        "max_iter": 1,
        "source": "TEMPO_extra_trees_baseline", "fit_sample_rows_default": "ALL_TRAIN",
    },
    "mice": {
        "estimator": "NaNSafeBayesianRidge",
        "max_iter": 3,
        "initial_strategy": "constant_0_for_finite_chained_predictors",
        "internal_model_space": "TRAIN_FITTED_ROBUST_SCALE__INVERSE_TRANSFORM_BEFORE_OUTPUT_SCALE",
        "imputed_value_bounds": "OBSERVED_TRAIN_FEATURE_MIN_MAX__INTERNAL_MODEL_SPACE",
        "sparse_predictor_fallback": "TRAIN_MEDIAN__ZERO_IF_ALL_MISSING",
        "sample_posterior": False,
        "fit_sample_rows_default": 1000000,
        "fit_scope": "TRAIN_POOLED_P1_P4__DETERMINISTIC_BOUNDED_SAMPLE",
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_hash(value: dict[str, Any]) -> str:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    temp.replace(path)


def atomic_parquet(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    frame.to_parquet(temp, index=False, compression="zstd")
    temp.replace(path)


def phase_index(phase: str) -> int:
    return PHASES.index(phase) + 1


def feature_family(name: str) -> str:
    stem = PHASE_SUFFIX_RE.sub(r"\1", name)
    if stem.startswith(("segment_", "video_", "watch_", "avg_playback", "fast_forward", "unique_video", "most_common_hour")):
        return "video"
    if stem.startswith(("problem_", "exercise_", "score_", "correct_", "incorrect_", "attempts_", "submit_")):
        return "problem"
    if stem.startswith(("comment_", "positive_", "negative_", "neutral_", "avg_comment", "min_comment", "max_comment")):
        return "comment"
    return "static" if not PHASE_SUFFIX_RE.search(name) else "other_dynamic"


@dataclass
class Telemetry:
    """Process telemetry available on CPU Modal workers without GPU access."""

    started_wall: float = field(default_factory=time.perf_counter)
    started_cpu: float = field(default_factory=time.process_time)
    marks: dict[str, float] = field(default_factory=dict)

    def mark(self, name: str) -> None:
        self.marks[name] = time.perf_counter()

    def row(self, *, run_id: str, task: str, window: str, pipeline_id: str, seed: int, cpu_allocated: int) -> pd.DataFrame:
        elapsed = time.perf_counter() - self.started_wall
        cpu_seconds = time.process_time() - self.started_cpu
        peak_ram_mb: float | None = None
        try:
            import resource  # Linux: ru_maxrss is KiB.
            peak_ram_mb = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) / 1024.0
        except (ImportError, AttributeError):
            pass
        values: dict[str, Any] = {
            "run_id": run_id, "task": task, "window_id": window, "pipeline_id": pipeline_id,
            "seed": seed, "time_run_total_s": elapsed, "cpu_process_s": cpu_seconds,
            "cpu_core_seconds_allocated": elapsed * cpu_allocated, "cpu_cores_allocated": cpu_allocated,
            "peak_ram_mb": peak_ram_mb, "gpu_used": False, "gpu_count": 0,
            "peak_gpu_mem_mb": 0.0, "energy_gpu_run_kwh": None, "energy_it_run_kwh": None,
            "co2e_gpu_run_g": None, "co2e_it_run_g": None, "cost_usd_run": None,
            "energy_measurement_type": "TELEMETRY_UNAVAILABLE_CPU_MODAL",
            "cost_measurement_type": "TELEMETRY_UNAVAILABLE_MODAL_BILLING",
            "telemetry_missing_rate": 0.0 if peak_ram_mb is not None else 1.0,
            "created_at_utc": utc_now(),
        }
        previous = self.started_wall
        for stage, mark in self.marks.items():
            values[f"time_{stage.lower()}_s"] = mark - previous
            previous = mark
        return pd.DataFrame([values])


def _safe_rate(numerator: int, denominator: int) -> float | None:
    return float(numerator / denominator) if denominator else None


def _empty_counts() -> dict[str, int]:
    return {key: 0 for key in (
        "n_cells_total", "n_cells_unavailable", "n_cells_structural_absence",
        "n_cells_observed_eligible", "n_cells_observed_value", "n_cells_observed_missing",
        "n_cells_observed_zero", "n_cells_imputed", "n_cells_residual_nan",
        "n_cells_imputed_in_unavailable", "n_cells_imputed_in_structural",
    )}


def dq_profile(
    raw: pd.DataFrame,
    transformed: pd.DataFrame,
    pipeline: Any,
    *, task: str,
    window: str,
    split: str,
    phase: str,
    run_id: str,
    stage: str = "S1_IMPUTED",
) -> pd.DataFrame:
    """Return lossless numerator/denominator DQ facts for one prefix snapshot."""
    # Train and validation physically contain the complete P1–P4 trajectory.
    # Only test is a prefix view, so only test_Pj must mark P(j+1)…P4 as
    # protocol-unavailable.  Treating full train/validation as Pj prefixes
    # created false future-leakage QA failures in S0/S1 facts.
    visible = set(PHASES if split.lower() != "test" else PHASES[:phase_index(phase)])
    groups = {"all": _empty_counts(), "video": _empty_counts(), "problem": _empty_counts(),
              "comment": _empty_counts(), "static": _empty_counts(), "other_dynamic": _empty_counts()}
    source_columns = list(pipeline.dynamic_source) + list(pipeline.static_columns)
    structural = _structural_mask(raw, list(pipeline.dynamic_source))
    rows = len(raw)
    for column in source_columns:
        match = PHASE_SUFFIX_RE.match(column)
        is_future = bool(match and f"P{match.group(2)}" not in visible)
        family = feature_family(column)
        destinations = (groups["all"], groups[family])
        if is_future:
            # A future phase is unavailable by protocol.  A value in the
            # transformed view would be leakage, irrespective of how it was
            # produced.  Count it explicitly rather than leaving the QA
            # counter at zero by construction.
            post = (pd.to_numeric(transformed[column], errors="coerce")
                    if column in transformed else pd.Series(np.nan, index=raw.index))
            for count in destinations:
                count["n_cells_total"] += rows
                count["n_cells_unavailable"] += rows
                count["n_cells_imputed_in_unavailable"] += int(post.notna().sum())
            continue
        values = pd.to_numeric(raw[column], errors="coerce")
        is_structural = structural[column] if column in structural else pd.Series(False, index=raw.index)
        eligible = ~is_structural
        missing = values.isna() & eligible
        observed = ~values.isna() & eligible
        post = pd.to_numeric(transformed[column], errors="coerce") if column in transformed else pd.Series(np.nan, index=raw.index)
        imputed = missing & post.notna()
        residual = missing & post.isna()
        structural_filled = is_structural & post.notna()
        for count in destinations:
            count["n_cells_total"] += rows
            count["n_cells_structural_absence"] += int(is_structural.sum())
            count["n_cells_observed_eligible"] += int(eligible.sum())
            count["n_cells_observed_missing"] += int(missing.sum())
            count["n_cells_observed_value"] += int(observed.sum())
            count["n_cells_observed_zero"] += int((observed & values.eq(0)).sum())
            count["n_cells_imputed"] += int(imputed.sum())
            count["n_cells_residual_nan"] += int(residual.sum())
            count["n_cells_imputed_in_structural"] += int(structural_filled.sum())
    records = []
    for family, count in groups.items():
        if not count["n_cells_total"]:
            continue
        record: dict[str, Any] = {
            "run_id": run_id, "task": task, "feature_regime": FEATURE_REGIME[task], "window_id": window,
            "split": split.upper(), "phase_id": phase, "feature_family": family,
            "stage": stage, "dq_def_version": DQ_DEF_VERSION, **count,
        }
        record.update({
            "missing_rate": _safe_rate(count["n_cells_observed_missing"], count["n_cells_observed_eligible"]),
            "completeness_observed": _safe_rate(count["n_cells_observed_value"], count["n_cells_observed_eligible"]),
            "unavailable_rate": _safe_rate(count["n_cells_unavailable"], count["n_cells_total"]),
            "structural_absence_rate": _safe_rate(count["n_cells_structural_absence"], count["n_cells_total"]),
            "observed_zero_rate": _safe_rate(count["n_cells_observed_zero"], count["n_cells_observed_eligible"]),
            "imputed_rate": _safe_rate(count["n_cells_imputed"], count["n_cells_observed_missing"]),
            "residual_nan_rate": _safe_rate(count["n_cells_residual_nan"], count["n_cells_observed_missing"]),
            "qa_no_unavailable_imputation_ok": count["n_cells_imputed_in_unavailable"] == 0,
            "qa_no_structural_imputation_ok": count["n_cells_imputed_in_structural"] == 0,
            "created_at_utc": utc_now(),
        })
        records.append(record)
    return pd.DataFrame(records)


def dataset_quality_summary(
    raw: pd.DataFrame,
    transformed: pd.DataFrame | None,
    pipeline: Any,
    *, task: str, window: str, split: str, phase: str, run_id: str, stage: str,
) -> pd.DataFrame:
    """Dataset-level DQ gates complementing the family-level missingness facts.

    Counts are emitted (rather than only rates) so downstream reports can use
    an appropriate denominator.  The function is intentionally sample-safe for
    S0 and release-safe for S1: it never modifies input values.
    """
    # See dq_profile: phase-prefix availability applies to test only.
    visible = set(PHASES if split.lower() != "test" else PHASES[:phase_index(phase)])
    source_columns = list(pipeline.dynamic_source) + list(pipeline.static_columns)
    structural = _structural_mask(raw, list(pipeline.dynamic_source))
    n_eligible = n_value = n_nonfinite = n_negative_count_duration = 0
    n_all_missing_columns = 0
    for column in source_columns:
        match = PHASE_SUFFIX_RE.match(column)
        if match and f"P{match.group(2)}" not in visible:
            continue
        values = pd.to_numeric(raw[column], errors="coerce")
        is_structural = structural[column] if column in structural else pd.Series(False, index=raw.index)
        eligible = ~is_structural
        observed = values.notna() & eligible
        finite = pd.Series(np.isfinite(values.to_numpy(dtype="float64", na_value=np.nan)), index=raw.index)
        n_eligible += int(eligible.sum())
        n_value += int(observed.sum())
        n_nonfinite += int((observed & ~finite).sum())
        if COUNT_RE.search(column):
            n_negative_count_duration += int((observed & finite & values.lt(0)).sum())
        if not (observed & finite).any():
            n_all_missing_columns += 1

    mask_columns = [c for c in pipeline.mask_columns if c in raw]
    n_mask_values = n_mask_domain_violation = 0
    for column in mask_columns:
        values = pd.to_numeric(raw[column], errors="coerce")
        present = values.notna()
        n_mask_values += int(present.sum())
        n_mask_domain_violation += int((present & ~values.isin([0, 1])).sum())

    enrollment = raw.get("enrollment_id", pd.Series(dtype="object"))
    enrollment_present = enrollment.notna()
    n_duplicate_enrollment_rows = int(enrollment.loc[enrollment_present].duplicated(keep=False).sum())
    label = "CQ_label_final" if task == "CQ" else "LO_performance_label_3"
    label_missing = int(raw[label].isna().sum()) if label in raw else len(raw)
    output_numeric_null = output_numeric_nonfinite = 0
    if transformed is not None:
        numeric = transformed.select_dtypes(include=[np.number])
        output_numeric_null = int(numeric.isna().sum().sum())
        output_numeric_nonfinite = int((~np.isfinite(numeric.to_numpy(dtype="float64"))).sum())
    record = {
        "run_id": run_id, "task": task, "feature_regime": FEATURE_REGIME[task],
        "window_id": window, "split": split.upper(), "phase_id": phase, "stage": stage,
        "dq_def_version": DQ_DEF_VERSION, "n_rows_profiled": len(raw),
        "n_numeric_eligible_cells": n_eligible, "n_numeric_observed_cells": n_value,
        "n_numeric_nonfinite_cells": n_nonfinite,
        "n_negative_count_duration_cells": n_negative_count_duration,
        "n_all_missing_numeric_columns": n_all_missing_columns,
        "n_mask_values": n_mask_values, "n_mask_domain_violations": n_mask_domain_violation,
        "n_enrollment_id_missing": int((~enrollment_present).sum()) if len(enrollment) else len(raw),
        "n_duplicate_enrollment_rows": n_duplicate_enrollment_rows,
        "n_label_missing": label_missing,
        "n_output_numeric_null_cells": output_numeric_null,
        "n_output_numeric_nonfinite_cells": output_numeric_nonfinite,
        "qa_label_complete": label_missing == 0,
        "qa_enrollment_id_unique": n_duplicate_enrollment_rows == 0,
        "qa_numeric_finite": n_nonfinite == 0,
        "qa_binary_masks_valid": n_mask_domain_violation == 0,
        "created_at_utc": utc_now(),
    }
    return pd.DataFrame([record])


def distribution_sketch(
    raw: pd.DataFrame,
    transformed: pd.DataFrame,
    pipeline: Any,
    *, task: str, window: str, split: str, phase: str, run_id: str,
    max_values: int = 20_000,
) -> pd.DataFrame:
    """Compact observed-vs-imputed distribution sketches in model-input space."""
    visible = set(PHASES[:phase_index(phase)])
    rng = np.random.default_rng(20260922)
    samples: dict[str, dict[str, list[np.ndarray]]] = {}
    for column in list(pipeline.dynamic_source) + list(pipeline.static_columns):
        match = PHASE_SUFFIX_RE.match(column)
        if match and f"P{match.group(2)}" not in visible:
            continue
        if column not in transformed:
            continue
        family = feature_family(column)
        samples.setdefault(family, {"observed": [], "imputed": []})
        raw_values = pd.to_numeric(raw[column], errors="coerce")
        output_values = pd.to_numeric(transformed[column], errors="coerce")
        structural = _structural_mask(raw, [column])[column] if match else pd.Series(False, index=raw.index)
        for status, mask in (("observed", raw_values.notna() & ~structural), ("imputed", raw_values.isna() & ~structural)):
            values = output_values[mask & output_values.notna()].to_numpy(dtype="float64")
            if len(values) > 256:
                take = min(512, len(values))
                values = values[rng.choice(len(values), take, replace=False)]
            samples[family][status].append(values)
    records = []
    for family, statuses in samples.items():
        pooled = {status: np.concatenate(values)[:max_values] if values else np.array([]) for status, values in statuses.items()}
        both = np.concatenate([pooled["observed"], pooled["imputed"]])
        if not len(both):
            continue
        low, high = np.nanquantile(both, [0.01, 0.99])
        if not np.isfinite(low) or not np.isfinite(high) or low == high:
            high = low + 1.0
        edges = np.linspace(low, high, 11)
        counts_by_status = {}
        for status, values in pooled.items():
            counts = np.histogram(np.clip(values, low, high), bins=edges)[0]
            counts_by_status[status] = counts
            records.append({
                "run_id": run_id, "task": task, "feature_regime": FEATURE_REGIME[task], "window_id": window,
                "split": split.upper(), "phase_id": phase, "feature_family": family, "stage": "S1_IMPUTED",
                "value_status": status, "n_values": int(len(values)), "mean": float(np.mean(values)) if len(values) else None,
                "std": float(np.std(values)) if len(values) else None,
                "p05": float(np.quantile(values, .05)) if len(values) else None,
                "p50": float(np.quantile(values, .50)) if len(values) else None,
                "p95": float(np.quantile(values, .95)) if len(values) else None,
                "bin_edges_json": json.dumps(edges.tolist()), "bin_counts_json": json.dumps(counts.tolist()),
                "created_at_utc": utc_now(),
            })
        observed, imputed = counts_by_status["observed"].astype(float), counts_by_status["imputed"].astype(float)
        if observed.sum() and imputed.sum():
            p, q = observed / observed.sum(), imputed / imputed.sum()
            midpoint = (p + q) / 2
            jsd = .5 * np.sum(np.where(p > 0, p * np.log2(p / np.maximum(midpoint, 1e-12)), 0)) + .5 * np.sum(np.where(q > 0, q * np.log2(q / np.maximum(midpoint, 1e-12)), 0))
            for record in records[-2:]:
                record["observed_imputed_jsd"] = float(jsd)
    return pd.DataFrame(records)


def fidelity_probe(pipeline: Any, validation: pd.DataFrame, baseline: pd.DataFrame, *, task: str, window: str, run_id: str, seed: int) -> pd.DataFrame:
    """Masked-observed validation check; bounded to keep it a diagnostic, not a run."""
    prepared, _ = pipeline._prepare(validation, fitting=False)
    sample = prepared.sample(min(len(prepared), 20_000), random_state=seed).copy()
    baseline = baseline.loc[sample.index]
    rng = np.random.default_rng(seed)
    held: list[tuple[str, np.ndarray]] = []
    candidates = list(pipeline.dynamic_source) + list(pipeline.static_columns)
    # Spread the bounded probe across feature families rather than favouring video columns.
    selected: list[str] = []
    for family in ("video", "problem", "comment", "static", "other_dynamic"):
        selected.extend([c for c in candidates if feature_family(c) == family][:8])
    for column in selected:
        values = pd.to_numeric(sample[column], errors="coerce")
        structural = _structural_mask(sample, [column])[column] if PHASE_SUFFIX_RE.match(column) else pd.Series(False, index=sample.index)
        positions = np.flatnonzero((values.notna() & ~structural).to_numpy())
        if not len(positions):
            continue
        chosen = rng.choice(positions, min(500, max(1, int(.05 * len(positions)))), replace=False)
        sample.iloc[chosen, sample.columns.get_loc(column)] = np.nan
        held.append((column, chosen))
    masked, _ = pipeline.transform(sample)
    records = []
    for family in ("video", "problem", "comment", "static", "other_dynamic"):
        errors = []
        for column, positions in held:
            if feature_family(column) != family or column not in masked or column not in baseline:
                continue
            errors.extend((masked.iloc[positions][column].to_numpy(dtype=float) - baseline.iloc[positions][column].to_numpy(dtype=float)).tolist())
        if errors:
            error = np.asarray(errors)
            records.append({"run_id": run_id, "task": task, "window_id": window, "split": "VALIDATION", "phase_id": "P4", "feature_family": family, "n_masked_cells": len(error), "mae": float(np.mean(np.abs(error))), "rmse": float(np.sqrt(np.mean(error ** 2))), "medae": float(np.median(np.abs(error))), "created_at_utc": utc_now()})
    return pd.DataFrame(records)


def l3_rows(profile: pd.DataFrame, resource: pd.DataFrame, *, task: str, window: str, run_id: str, pipeline_id: str, seed: int) -> pd.DataFrame:
    """Provisional L3 rows.  Prediction metrics remain explicitly unavailable."""
    overall = profile.loc[profile["feature_family"].eq("all") & profile["stage"].eq("S1_IMPUTED")]
    resource_row = resource.iloc[0].to_dict()
    rows = []
    for _, source in overall.iterrows():
        if source["split"] == "TRAIN":
            continue
        key = {"task": task, "label_rule_version": "cq_vector_proximity_v1" if task == "CQ" else "lo_performance_proxy_v1", "label_threshold_set": "PRIMARY", "feature_regime": FEATURE_REGIME[task], "window_id": window, "seed": seed, "phase_id": source["phase_id"], "cohort": COHORT[task], "eval_split": source["split"], "subgroup_axis": "ALL", "subgroup_value": "ALL", "model_name": "IMPUTATION_ONLY", "pipeline_id": pipeline_id}
        rows.append({**key, "meta_obs_id": canonical_hash(key), "run_id": run_id, "row_status": "PARTIAL", "performance_null_reason": "NO_PREDICTION", "metric_def_version": METRIC_DEF_VERSION, "dq_def_version": DQ_DEF_VERSION, "n_cells_observed_missing_after": source["n_cells_observed_missing"], "n_cells_imputed_after": source["n_cells_imputed"], "imputed_rate_after": source["imputed_rate"], "residual_nan_rate_after": source["residual_nan_rate"], "unavailable_rate_after": source["unavailable_rate"], "structural_absence_rate_after": source["structural_absence_rate"], "qa_no_unavailable_imputation_ok": source["qa_no_unavailable_imputation_ok"], "time_run_total_s_after": resource_row["time_run_total_s"], "cpu_process_s_after": resource_row["cpu_process_s"], "peak_ram_mb_after": resource_row["peak_ram_mb"], "gpu_used_after": resource_row["gpu_used"], "energy_gpu_run_kwh_after": resource_row["energy_gpu_run_kwh"], "cost_usd_run_after": resource_row["cost_usd_run"], "created_at_utc": utc_now()})
    return pd.DataFrame(rows)


def environment_record() -> dict[str, Any]:
    versions = {}
    for name in ("numpy", "pandas", "pyarrow", "sklearn", "joblib"):
        try:
            module = __import__(name)
            versions[name] = getattr(module, "__version__", "UNKNOWN")
        except ImportError:
            versions[name] = "NOT_INSTALLED"
    return {"python_version": platform.python_version(), "platform": platform.platform(), "pid": os.getpid(), "library_versions": versions, "created_at_utc": utc_now()}


def implementation_version() -> str:
    root = Path(__file__).parent
    digest = hashlib.sha256()
    for name in ("wide_imputation.py", "meta_storage.py", "variants/v0.py", "variants/median.py", "variants/mean.py", "variants/extra_trees.py", "variants/mice.py"):
        path = root / name
        digest.update(name.encode("utf-8"))
        digest.update(path.read_bytes())
    return f"sha256:{digest.hexdigest()}"


def feature_key(column: str) -> str:
    """Pool P1--P4 columns of the same dynamic feature under one key."""
    match = PHASE_SUFFIX_RE.match(column)
    return match.group(1) if match else column


def release_inventory(input_root: Path, *, task: str) -> dict[str, Any]:
    """A stable, inexpensive file inventory used as the frozen input identity."""
    entries = []
    for path in sorted(input_root.rglob("*")):
        if path.is_file() and not path.name.startswith("."):
            status = path.stat()
            entries.append({"path": str(path.relative_to(input_root)), "bytes": status.st_size})
    payload = {"task": task, "root": str(input_root), "files": entries}
    # A sidecar preserves the immutable upstream release identity when the
    # Modal input layout uses compatibility aliases such as phase_views_v1.
    # Legacy uploads remain readable with the historical defaults.
    sidecar_path = input_root / "release_manifest.json"
    sidecar: dict[str, Any] = {}
    if sidecar_path.is_file():
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        if sidecar.get("task") != task:
            raise ValueError(f"Input release sidecar task mismatch: expected {task}, got {sidecar.get('task')}")
    defaults = {
        "split_version": "label_stratified_v1",
        "phase_version": "wide_prefix_v1",
        "feature_dictionary_version": "schema_from_phase_views_v1",
        "label_rule_version": "cq_vector_proximity_v1" if task == "CQ" else "lo_performance_proxy_v1",
    }
    release = {key: sidecar.get(key, value) for key, value in defaults.items()}
    release["data_release_id"] = f"sha256:{canonical_hash({'inventory': payload, 'sidecar': sidecar})}"
    release["inventory"] = payload
    if sidecar:
        release["input_release_manifest"] = sidecar
    return release


def _eligible_feature_values(raw: pd.DataFrame, values: pd.DataFrame, pipeline: Any, *, phase: str | None) -> dict[str, dict[str, list[np.ndarray]]]:
    """Observed/imputed values grouped by pooled base feature, in one stage's scale."""
    visible = set(PHASES if phase is None else PHASES[:phase_index(phase)])
    result: dict[str, dict[str, list[np.ndarray]]] = {}
    dynamic_structural = _structural_mask(raw, list(pipeline.dynamic_source))
    for column in list(pipeline.dynamic_source) + list(pipeline.static_columns):
        match = PHASE_SUFFIX_RE.match(column)
        if match and f"P{match.group(2)}" not in visible:
            continue
        if column not in values:
            continue
        key = feature_key(column)
        family = feature_family(column)
        bucket = result.setdefault(key, {"family": family, "observed": [], "imputed": []})
        raw_value = pd.to_numeric(raw[column], errors="coerce")
        transformed = pd.to_numeric(values[column], errors="coerce")
        structural = dynamic_structural[column] if column in dynamic_structural else pd.Series(False, index=raw.index)
        observed = transformed[raw_value.notna() & ~structural & transformed.notna()].to_numpy(dtype="float64")
        imputed = transformed[raw_value.isna() & ~structural & transformed.notna()].to_numpy(dtype="float64")
        if len(observed):
            bucket["observed"].append(observed)
        if len(imputed):
            bucket["imputed"].append(imputed)
    return result


def build_bin_scheme(raw_train: pd.DataFrame, values_train: pd.DataFrame, pipeline: Any, *, task: str, window: str, stage: str, run_id: str | None) -> pd.DataFrame:
    """Lock ten quantile bins on TRAIN_POOLED_P1_P4 for a single data stage."""
    grouped = _eligible_feature_values(raw_train, values_train, pipeline, phase=None)
    records = []
    for key, values in grouped.items():
        observed = np.concatenate(values["observed"]) if values["observed"] else np.array([])
        if not len(observed):
            continue
        if len(observed) > 50_000:
            observed = observed[np.random.default_rng(20260922).choice(len(observed), 50_000, replace=False)]
        edges = np.quantile(observed, np.linspace(0, 1, 11))
        # Histograms require strict edges; retain deterministic tiny widening.
        edges = np.maximum.accumulate(edges)
        for idx in range(1, len(edges)):
            if edges[idx] <= edges[idx - 1]:
                edges[idx] = edges[idx - 1] + 1e-7
        records.append({"run_id": run_id, "task": task, "feature_regime": FEATURE_REGIME[task], "window_id": window,
                        "stage": stage, "fit_scope": "TRAIN_POOLED_P1_P4", "feature_key": key,
                        "feature_family": values["family"], "n_fit_values": int(len(observed)),
                        "bin_edges_json": json.dumps(edges.tolist()), "created_at_utc": utc_now()})
    return pd.DataFrame(records)


def distribution_sketch_locked(raw: pd.DataFrame, values: pd.DataFrame, pipeline: Any, bin_scheme: pd.DataFrame, *, task: str, window: str, split: str, phase: str, stage: str, run_id: str | None) -> pd.DataFrame:
    """Histogram facts using bins locked from the corresponding training stage."""
    grouped = _eligible_feature_values(raw, values, pipeline, phase=phase)
    bins = {row.feature_key: np.asarray(json.loads(row.bin_edges_json), dtype=float) for row in bin_scheme.itertuples()}
    records = []
    for key, values_by_status in grouped.items():
        if key not in bins:
            continue
        edges = bins[key]
        status_records = []
        for status in ("observed", "imputed"):
            data = np.concatenate(values_by_status[status]) if values_by_status[status] else np.array([])
            counts = np.histogram(np.clip(data, edges[0], edges[-1]), bins=edges)[0] if len(data) else np.zeros(len(edges) - 1, dtype=int)
            quantiles = np.quantile(data, [0.05, 0.50, 0.95]) if len(data) else (np.nan, np.nan, np.nan)
            record = {"run_id": run_id, "task": task, "feature_regime": FEATURE_REGIME[task], "window_id": window,
                      "split": split.upper(), "phase_id": phase, "stage": stage, "feature_key": key,
                      "feature_family": values_by_status["family"], "value_status": status, "n_values": int(len(data)),
                      "value_min": float(np.min(data)) if len(data) else None,
                      "value_max": float(np.max(data)) if len(data) else None,
                      "value_mean": float(np.mean(data)) if len(data) else None,
                      "value_std": float(np.std(data)) if len(data) else None,
                      "value_p05": float(quantiles[0]) if len(data) else None,
                      "value_p50": float(quantiles[1]) if len(data) else None,
                      "value_p95": float(quantiles[2]) if len(data) else None,
                      "bin_edges_json": json.dumps(edges.tolist()), "bin_counts_json": json.dumps(counts.tolist()),
                      "created_at_utc": utc_now()}
            status_records.append((record, counts))
            records.append(record)
        observed, imputed = status_records[0][1].astype(float), status_records[1][1].astype(float)
        if observed.sum() and imputed.sum():
            p, q = observed / observed.sum(), imputed / imputed.sum()
            mid = (p + q) / 2
            jsd = .5 * np.sum(np.where(p > 0, p * np.log2(p / np.maximum(mid, 1e-12)), 0)) + .5 * np.sum(np.where(q > 0, q * np.log2(q / np.maximum(mid, 1e-12)), 0))
            for record, _ in status_records:
                record["observed_imputed_jsd"] = float(jsd)
    return pd.DataFrame(records)


def class_distribution(frame: pd.DataFrame, *, task: str, window: str, split: str, phase: str, state_id: str, stage: str) -> pd.DataFrame:
    label = "CQ_label_final" if task == "CQ" else "LO_performance_label_3"
    counts = frame[label].astype("string").value_counts(dropna=False)
    total = int(counts.sum())
    probabilities = counts.to_numpy(dtype=float) / total if total else np.array([])
    entropy = float(-np.sum(np.where(probabilities > 0, probabilities * np.log(probabilities), 0)) / np.log(3)) if len(probabilities) else None
    minority = int(counts.min()) if len(counts) else 0
    majority = int(counts.max()) if len(counts) else 0
    return pd.DataFrame([{"state_id": state_id, "task": task, "feature_regime": FEATURE_REGIME[task], "window_id": window,
                          "split": split.upper(), "phase_id": phase, "stage": stage, "class_code": str(code), "class_count": int(count),
                          "n_rows": total, "class_share": float(count / total) if total else None, "class_entropy_norm": entropy,
                          "imbalance_ratio": float(majority / minority) if minority else None, "created_at_utc": utc_now()}
                         for code, count in counts.items()])


def drift_measures_from_sketch(sketches: pd.DataFrame, *, task: str, window: str, stage: str, run_id: str | None) -> pd.DataFrame:
    """JSD from locked observed-value histograms; values remain recomputable."""
    observed = sketches.loc[sketches.value_status.eq("observed")].copy()
    if observed.empty:
        return pd.DataFrame()
    records = []
    def compare(left: pd.DataFrame, right: pd.DataFrame, kind: str, phase: str, split: str, actual_window: str) -> None:
        merged = left.merge(right, on="feature_key", suffixes=("_left", "_right"))
        for row in merged.itertuples():
            a = np.asarray(json.loads(row.bin_counts_json_left), dtype=float)
            b = np.asarray(json.loads(row.bin_counts_json_right), dtype=float)
            if not a.sum() or not b.sum():
                continue
            p, q = a / a.sum(), b / b.sum()
            midpoint = (p + q) / 2
            jsd = .5 * np.sum(np.where(p > 0, p * np.log2(p / np.maximum(midpoint, 1e-12)), 0)) + .5 * np.sum(np.where(q > 0, q * np.log2(q / np.maximum(midpoint, 1e-12)), 0))
            records.append({"run_id": run_id, "task": task, "feature_regime": FEATURE_REGIME[task], "window_id": actual_window,
                            "stage": stage, "comparison": kind, "split": split, "phase_id": phase,
                            "feature_key": row.feature_key, "feature_family": row.feature_family_left,
                            "jsd_base2": float(jsd), "created_at_utc": utc_now()})
    for actual_window in observed.window_id.unique():
        current_window = observed.loc[observed.window_id.eq(actual_window)]
        for phase in sorted(current_window.phase_id.unique()):
            train = current_window.loc[(current_window.split == "TRAIN") & (current_window.phase_id == phase)]
            for split in ("VALIDATION", "TEST"):
                compare(train, current_window.loc[(current_window.split == split) & (current_window.phase_id == phase)], "TRAIN_VS_EVAL", phase, split, actual_window)
        for split in current_window.split.unique():
            for previous, current in zip(PHASES, PHASES[1:]):
                compare(current_window.loc[(current_window.split == split) & (current_window.phase_id == previous)], current_window.loc[(current_window.split == split) & (current_window.phase_id == current)], "PHASE_VS_PREV", current, split, actual_window)
    return pd.DataFrame(records)
