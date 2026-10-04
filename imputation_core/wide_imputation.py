"""Phase-safe, train-only preprocessing for the wide CQ/LO release.

Dynamic features are fitted as one long matrix pooled from P1--P4 in the
selected window's training partition.  A test Pj is transformed only through
blocks P1..Pj; future blocks never reach an imputer or scaler.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import joblib
import numpy as np
import pandas as pd
import pyarrow.dataset as ds
from sklearn.preprocessing import RobustScaler
from release_core.runtime_config import MICE

from .id_codes import add_id_code_columns
from .variants import BUILDERS

Variant = Literal["v0", "median", "mean", "extra_trees", "mice"]
PHASES = ("P1", "P2", "P3", "P4")
ID_COLUMNS = {"enrollment_id", "offering_id", "user_id", "course_id", "teacher_id", "school_id"}
AUDIT_CONTEXT_COLUMNS = {
    "duration_days", "long_offering_flag", "label_threshold_set",
    "temporal_strict_P1", "temporal_strict_P2", "temporal_strict_P3", "temporal_strict_P4",
}
BASE_EXCLUDED = {"task", "window", "split", "split_id", "scenario", "temporal_block", "label_availability_time", "label_availability_source", "label_rule_version", "decision", "proxy_reason", "cq_exclusion_reason", "proxy_exclusion_reason", "performance_score", "CQ_label_vector", "COELO_final", "AFELO_final", "ACELO_final", "CQ_distance_euclidean_final", "CQ_proximity_final", "TRIAD_distance_final", "observed_dimension_mask", "year_of_birth", "age_at_enroll", "most_common_day"}
# These LO fields are direct ingredients of the activity-derived target, or a
# deterministic denominator/ratio for one.  They must never be imputers' or
# models' predictors, even when a materialized view carries the label audit
# columns through a join.
LO_LABEL_PROXY_COLUMNS = {
    "label_threshold_set", "video_weight", "assignment_weight", "exam_weight",
    "course_weight_total", "watched_videos", "video_counts", "watch_percent",
    "assignment_problem_catalog_count", "exam_problem_catalog_count",
    "assignment_best_correct_sum", "exam_best_correct_sum",
    "assignment_problem_attempted_count", "exam_problem_attempted_count",
    "assignment_ratio_catalog", "exam_ratio_catalog",
    "tempo_legacy_unclipped_score", "tempo_legacy_score_clipped",
    "assignment_ratio_used", "total_correct_ratio_assignment",
    "total_correct_ratio_exam", "average_correct_ratio_assignment",
    "average_correct_ratio_exam", "exam_attempt_count", "assignment_attempt_count",
    "video_catalog_coverage", "problem_catalog_coverage",
    "problem_score_catalog_coverage",
}
# CQ's final W/A/G label is derived from the TRIAD score.  Ratios normalised
# against the catalog/full score and TRIAD components (or monotone derivatives
# of them) are label proxies.  They belong only to CQ_REDUCED_DIRECT or
# CQ_EARLY_COMPONENT, never to the RAW_EARLY imputer/model input.
CQ_LABEL_PROXY_RE = re.compile(
    r"(?:^cq_label_|^(?:coelo|afelo|acelo|triad_distance)_|^cq_(?:distance|proximity|score_g)|"
    r"(?:catalog_)?coverage$|_coverage$|score_fraction|correct_ratio|watch_ratio|"
    r"video_ratio|problem_ratio|scaled_watch|watch_count_scaled|scaled_attempts)",
    re.I,
)
COUNT_RE = re.compile(r"(count|counts|sum|seconds|duration|length|attempts)", re.I)
HOUR_RE = re.compile(r"^most_common_hour(?:_(P[1-4]))?$")
PHASE_SUFFIX_RE = re.compile(r"^(.*)_P([1-4])$")


def fit_sample_rows_for_variant(variant: Variant, requested_rows: int) -> int:
    """Return the declared estimator-fit budget for a variant.

    Simple statistics and ExtraTrees fit on all training values.  MICE is the
    intentionally bounded chained-equation experiment: fitting it on the
    pooled P1--P4 matrix at full scale is prohibitively expensive, while its
    fitted chain can still transform every row in every split.
    """
    if variant in {"median", "mean", "extra_trees"}:
        return 0  # 0 denotes exact full-train statistic fit.
    if variant == "mice":
        # MICE is a fixed 1M-row estimator-fit experiment.  Accepting a CLI
        # override would make the immutable registry claim false.
        if requested_rows not in {0, MICE["fit_sample_rows"]}:
            raise ValueError(f"MICE fit_sample_rows is locked to {MICE['fit_sample_rows']} for the active release")
        return MICE["fit_sample_rows"]
    return requested_rows


def _read(path: Path, filters: list[tuple[str, str, object]]) -> pd.DataFrame:
    expression = None
    for column, op, value in filters:
        term = ds.field(column) == value if op == "=" else ds.field(column).isin(value)
        expression = term if expression is None else expression & term
    return ds.dataset(path, format="parquet").to_table(filter=expression).to_pandas()


def _label_column(task: str) -> str:
    return "CQ_label_final" if task == "CQ" else "LO_performance_label_3"


def _structural_mask(frame: pd.DataFrame, source_columns: list[str]) -> pd.DataFrame:
    """True where a modality is unavailable, hence zero is not imputation."""
    result = pd.DataFrame(False, index=frame.index, columns=source_columns)
    for column in source_columns:
        match = PHASE_SUFFIX_RE.match(column)
        if not match:
            continue
        stem, phase = match.groups()
        if stem.startswith(("segment_", "video_", "watch_", "avg_playback", "fast_forward", "unique_video", "most_common_hour")):
            modality = "video"
        elif stem.startswith(("problem_", "exercise_", "score_", "correct_", "incorrect_", "attempts_", "submit_")):
            modality = "problem"
        elif stem.startswith(("comment_", "positive_", "negative_", "neutral_", "avg_comment", "min_comment", "max_comment")):
            modality = "comment"
        else:
            continue
        mask = f"{modality}_observed_mask_P{phase}"
        if mask in frame:
            result[column] = frame[mask].fillna(0).eq(0)
    return result


@dataclass
class WideImputer:
    task: str
    variant: Variant
    fit_sample_rows: int
    seed: int

    def _prepare(self, source: pd.DataFrame, *, fitting: bool) -> tuple[pd.DataFrame, pd.DataFrame]:
        original = source.copy()
        frame = add_id_code_columns(source)
        frame = frame.drop(columns=[c for c in ID_COLUMNS if c in frame], errors="ignore")
        for name in list(frame.columns):
            match = HOUR_RE.match(name)
            if match:
                hour = pd.to_numeric(frame[name], errors="coerce")
                suffix = f"_{match.group(1)}" if match.group(1) else ""
                frame[f"most_common_hour_sin{suffix}"] = np.sin(2 * np.pi * hour / 24)
                frame[f"most_common_hour_cos{suffix}"] = np.cos(2 * np.pi * hour / 24)
                frame = frame.drop(columns=name)
        label = _label_column(self.task)
        excluded = set(BASE_EXCLUDED) | LO_LABEL_PROXY_COLUMNS | AUDIT_CONTEXT_COLUMNS | {label}
        if self.task == "CQ":
            excluded |= {c for c in frame if CQ_LABEL_PROXY_RE.search(c)}
        excluded |= {c for c in frame if c.startswith(("CQ_label_", "LO_performance_label_", "label_available_by_", "primary_risk_set_", "outcome_", "cutoff_time_"))}
        excluded |= {c for c in frame if pd.api.types.is_datetime64_any_dtype(frame[c])}
        if fitting:
            self.categorical = [c for c in frame if c not in excluded and (c in {"gender", "timeline_source", "user_id_code", "course_id_code", "teacher_id_code", "school_id_code"} or pd.api.types.is_object_dtype(frame[c]) or pd.api.types.is_string_dtype(frame[c]))]
            numeric = [c for c in frame if c not in excluded and c not in self.categorical and pd.api.types.is_numeric_dtype(frame[c])]
            self.mask_columns = [c for c in numeric if c.startswith(("video_observed_mask_", "problem_observed_mask_", "comment_observed_mask_", "phase_available_"))]
            value_columns = [c for c in numeric if c not in self.mask_columns]
            self.dynamic_source = [c for c in value_columns if PHASE_SUFFIX_RE.match(c)]
            self.static_columns = [c for c in value_columns if c not in self.dynamic_source]
            self.dynamic_bases = sorted({PHASE_SUFFIX_RE.match(c).group(1) for c in self.dynamic_source})
            self.static_log_columns = [c for c in self.static_columns if COUNT_RE.search(c)]
            self.dynamic_log_columns = [c for c in self.dynamic_bases if COUNT_RE.search(c)]
        required = set(self.categorical + self.mask_columns + self.dynamic_source + self.static_columns)
        missing = required.difference(frame.columns)
        if missing:
            raise ValueError(f"Transform schema is missing fitted features: {sorted(missing)}")
        return frame, original

    def _fit_categories(self, frame: pd.DataFrame) -> None:
        self.category_maps = {}
        for column in self.categorical:
            values = frame[column].astype("string").fillna("<MISSING>")
            self.category_maps[column] = {v: i for i, v in enumerate(pd.unique(values), start=1)}

    def _encode_categories(self, frame: pd.DataFrame) -> pd.DataFrame:
        result = pd.DataFrame(index=frame.index)
        for column in self.categorical:
            values = frame[column].astype("string").fillna("<MISSING>")
            result[column] = values.map(self.category_maps[column]).fillna(0).astype("int32")
        return result

    @staticmethod
    def _log(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
        result = frame.copy()
        for column in columns:
            value = result[column]
            # np.where eagerly evaluates both branches, which previously emitted
            # warnings for legitimate negative sentinel/derived values.  Log only
            # non-negative values and preserve negative values for the audit.
            eligible = value.ge(0)
            logged = value.copy()
            logged.loc[eligible] = np.log1p(value.loc[eligible])
            result[column] = logged
        return result

    def _dynamic_long(self, frame: pd.DataFrame, phases: tuple[str, ...]) -> tuple[pd.DataFrame, pd.DataFrame]:
        values, structural = [], []
        for phase in phases:
            source_cols = [f"{base}_{phase}" for base in self.dynamic_bases if f"{base}_{phase}" in frame]
            block = pd.DataFrame(np.nan, index=frame.index, columns=self.dynamic_bases, dtype="float32")
            block_mask = pd.DataFrame(False, index=frame.index, columns=self.dynamic_bases)
            for source in source_cols:
                base = PHASE_SUFFIX_RE.match(source).group(1)
                block[base] = pd.to_numeric(frame[source], errors="coerce").astype("float32")
            source_mask = _structural_mask(frame, source_cols)
            for source in source_cols:
                base = PHASE_SUFFIX_RE.match(source).group(1)
                block_mask[base] = source_mask[source]
            values.append(block)
            structural.append(block_mask)
        return pd.concat(values, ignore_index=True), pd.concat(structural, ignore_index=True)

    @staticmethod
    def _fit_estimator(variant: Variant, matrix: pd.DataFrame, active_columns: list[str], sample_rows: int, seed: int,
                       model_scaler: RobustScaler | None = None):
        estimator = BUILDERS[variant](seed=seed)
        if estimator is None:
            return None
        sample = matrix[active_columns]
        # Learned estimators may use a bounded, deterministic fit sample.
        # This applies to MICE to control the quadratic-like cost of chained
        # regressions over the pooled P1--P4 matrix.
        if variant not in {"median", "mean"} and sample_rows > 0 and len(sample) > sample_rows:
            sample = sample.sample(sample_rows, random_state=seed)
            # A purely random bounded sample can miss a very sparse, otherwise
            # valid column.  Keep one observed anchor for every fitted column so
            # sklearn never silently drops it from the estimator schema.
            anchors = [matrix[column].first_valid_index() for column in active_columns]
            sample = pd.concat([sample, matrix.loc[list(dict.fromkeys(anchors)), active_columns]])
            sample = sample.loc[~sample.index.duplicated(keep="first")]
        if active_columns:
            # BayesianRidge is numerically sensitive to the raw heterogeneous
            # feature units (for example, a duration alongside a proportion).
            # MICE therefore uses the train-fitted RobustScaler only inside its
            # chained equations. Values are inverse-transformed after MICE, so
            # the externally documented contract remains impute -> scale.
            model_sample = sample
            if variant == "mice" and model_scaler is not None:
                model_sample = pd.DataFrame(
                    model_scaler.transform(sample), index=sample.index, columns=active_columns,
                )
                # Chained Bayesian-Ridge predictions can otherwise explode on
                # the very sparse wide modality matrix and then contaminate
                # the next round.  Bounds are learned exclusively from the
                # observed train support in this internal scaled space. They
                # constrain imputed values only; observed values are never
                # clipped or changed.
                lower = model_sample.min(axis=0, skipna=True).to_numpy(dtype="float64")
                upper = model_sample.max(axis=0, skipna=True).to_numpy(dtype="float64")
                finite = np.isfinite(lower) & np.isfinite(upper)
                # IterativeImputer requires a strict interval. Constant
                # train features are legitimate (for example a course-level
                # indicator), so give them a numerically negligible interval
                # around their observed value rather than dropping them.
                constant = finite & (upper <= lower)
                lower = np.where(finite, lower, -np.inf)
                upper = np.where(finite, upper, np.inf)
                lower = np.where(constant, lower - 1e-6, lower)
                upper = np.where(constant, upper + 1e-6, upper)
                estimator.min_value = lower
                estimator.max_value = upper
            estimator.fit(model_sample)
        return estimator

    @staticmethod
    def _apply_estimator(matrix: pd.DataFrame, structural: pd.DataFrame, estimator, columns: list[str], active_columns: list[str],
                         model_scaler: RobustScaler | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Impute only train-observed columns, retaining the full fitted schema.

        sklearn's SimpleImputer/IterativeImputer can drop a column with no
        observed training value.  Such a column cannot be statistically fitted;
        it remains in the release as neutral scaled-zero with a missing flag.
        """
        missing = matrix.isna() & ~structural
        output = pd.DataFrame(0.0, index=matrix.index, columns=columns, dtype="float32")
        if active_columns:
            active = matrix[active_columns]
            if estimator is None:
                values = active.fillna(0.0).to_numpy(dtype="float32")
            else:
                model_active = active
                if model_scaler is not None:
                    model_active = pd.DataFrame(
                        model_scaler.transform(active), index=active.index, columns=active_columns,
                    )
                values = estimator.transform(model_active)
                if model_scaler is not None:
                    values = model_scaler.inverse_transform(values)
                values = values.astype("float32")
            output.loc[:, active_columns] = values
        output = output.mask(structural, 0.0)
        missing.columns = [f"missing__{c}" for c in columns]
        return output, missing.astype("int8")

    @staticmethod
    def _fit_scaler(matrix: pd.DataFrame) -> tuple[RobustScaler | None, list[str]]:
        active_columns = [column for column in matrix if matrix[column].notna().any()]
        return (RobustScaler().fit(matrix[active_columns]) if active_columns else None), active_columns

    @staticmethod
    def _scale(matrix: pd.DataFrame, scaler: RobustScaler | None, columns: list[str], active_columns: list[str], structural: pd.DataFrame | None = None) -> pd.DataFrame:
        """Apply a train-fitted scaler while preserving missingness and structural absence."""
        # Keep an already-imputed fallback value in any unfittable column. For
        # raw input these are naturally NaN; for post-imputation output they are
        # the documented neutral zero.
        output = matrix.loc[:, columns].copy().astype("float32")
        if active_columns:
            output.loc[:, active_columns] = scaler.transform(matrix[active_columns]).astype("float32")
        return output if structural is None else output.mask(structural, 0.0)

    def fit(self, train: pd.DataFrame) -> "WideImputer":
        prepared, _ = self._prepare(train, fitting=True)
        self._fit_categories(prepared)
        dynamic, dynamic_structural = self._dynamic_long(prepared, PHASES)
        dynamic = self._log(dynamic, self.dynamic_log_columns).mask(dynamic_structural)
        static = self._log(prepared[self.static_columns].apply(pd.to_numeric, errors="coerce").astype("float32"), self.static_log_columns)
        # Fit imputers on raw/log train values, matching the TEMPO convention.
        # The scaler is then fit only on observed raw/log TRAIN values and
        # applied uniformly after every imputation variant. This preserves the
        # distinction between raw-zero V0, median and mean while preventing any
        # validation/test contribution to scaling.
        self.dynamic_scaler, self.dynamic_active_columns = self._fit_scaler(dynamic)
        self.static_scaler, self.static_active_columns = self._fit_scaler(static)
        dynamic_model_scaler = self.dynamic_scaler if self.variant == "mice" else None
        static_model_scaler = self.static_scaler if self.variant == "mice" else None
        self.dynamic_imputer = self._fit_estimator(self.variant, dynamic, self.dynamic_active_columns, self.fit_sample_rows, self.seed, dynamic_model_scaler)
        self.static_imputer = self._fit_estimator(self.variant, static, self.static_active_columns, self.fit_sample_rows, self.seed, static_model_scaler)
        return self

    def transform(self, source: pd.DataFrame, *, max_test_phase: str | None = None) -> tuple[pd.DataFrame, dict[str, object]]:
        prepared, original = self._prepare(source, fitting=False)
        observed = PHASES if max_test_phase is None else PHASES[:PHASES.index(max_test_phase) + 1]
        dynamic, structural = self._dynamic_long(prepared, observed)
        dynamic = self._log(dynamic, self.dynamic_log_columns).mask(structural)
        dynamic_output, dynamic_missing = self._apply_estimator(
            dynamic, structural, self.dynamic_imputer, self.dynamic_bases, self.dynamic_active_columns,
            self.dynamic_scaler if self.variant == "mice" else None,
        )
        dynamic_output = self._scale(dynamic_output, self.dynamic_scaler, self.dynamic_bases, self.dynamic_active_columns, structural)
        n = len(prepared)
        dynamic_columns: dict[str, np.ndarray] = {}
        for index, phase in enumerate(PHASES):
            for base in self.dynamic_bases:
                target = f"{base}_{phase}"
                if target not in self.dynamic_source:
                    continue
                if phase in observed:
                    rows = slice(index * n, (index + 1) * n)
                    dynamic_columns[target] = dynamic_output.iloc[rows][base].to_numpy()
                    dynamic_columns[f"missing__{target}"] = dynamic_missing.iloc[rows][f"missing__{base}"].to_numpy()
                else:
                    dynamic_columns[target] = np.zeros(n, dtype="float32")
                    dynamic_columns[f"missing__{target}"] = np.zeros(n, dtype="int8")
        output = pd.DataFrame(dynamic_columns, index=prepared.index)
        static = self._log(prepared[self.static_columns].apply(pd.to_numeric, errors="coerce").astype("float32"), self.static_log_columns)
        static_output, static_missing = self._apply_estimator(
            static, pd.DataFrame(False, index=static.index, columns=self.static_columns), self.static_imputer,
            self.static_columns, self.static_active_columns, self.static_scaler if self.variant == "mice" else None,
        )
        static_output = self._scale(static_output, self.static_scaler, self.static_columns, self.static_active_columns)
        output = pd.concat([output, static_output, static_missing, prepared[self.mask_columns].fillna(0).astype("int8"), self._encode_categories(prepared)], axis=1)
        label = _label_column(self.task)
        provenance = pd.DataFrame(index=prepared.index)
        for key in ("enrollment_id", "window", "split"):
            if key in original:
                provenance[key] = original[key].values
        # These columns are retained solely for post-model audit/subgroup
        # joins.  Their namespace prevents them from entering model tensors.
        for key in ("offering_id", "timeline_source", "course_id", "duration_days", "long_offering_flag", "label_threshold_set",
                    "temporal_strict_P1", "temporal_strict_P2", "temporal_strict_P3", "temporal_strict_P4"):
            if key in original:
                provenance[f"context__{key}"] = original[key].values
        output = pd.concat([pd.DataFrame({label: original[label].values}, index=prepared.index), output, provenance], axis=1)
        audit = {"rows": float(n), "observed_phases": list(observed), "eligible_missing_cells": float((dynamic.isna() & ~structural).sum().sum() + static.isna().sum().sum()), "structural_cells": float(structural.sum().sum()), "unfittable_dynamic_columns": sorted(set(self.dynamic_bases) - set(self.dynamic_active_columns)), "unfittable_static_columns": sorted(set(self.static_columns) - set(self.static_active_columns)), "remaining_numeric_nulls": float(output.select_dtypes(include=[np.number]).isna().sum().sum()), "future_imputed_cells": 0.0}
        return output, audit


def make_parser(task: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window", choices=("W1", "W2", "W3"), required=True)
    parser.add_argument("--test-phase", choices=("ALL", *PHASES), default="ALL")
    parser.add_argument("--variant", choices=("v0", "median", "mean", "extra_trees", "mice"), required=True)
    parser.add_argument("--train-validation", type=Path, required=True)
    parser.add_argument("--test-prefix-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--fit-sample-rows", type=int, default=200_000)
    parser.add_argument("--seed", type=int, default=20260922)
    parser.set_defaults(task=task)
    return parser


def main(task: str) -> None:
    args = make_parser(task).parse_args()
    train = _read(args.train_validation, [("window", "=", args.window), ("split", "=", "train")])
    validation = _read(args.train_validation, [("window", "=", args.window), ("split", "=", "validation")])
    phases = PHASES if args.test_phase == "ALL" else (args.test_phase,)
    tests = {p: _read(args.test_prefix_root / p, [("window", "=", args.window), ("split", "=", "test")]) for p in phases}
    pipeline = WideImputer(task, args.variant, args.fit_sample_rows, args.seed).fit(train)
    root = args.output_root / task / args.window / args.variant
    root.mkdir(parents=True, exist_ok=True)
    audit = {"task": task, "window": args.window, "variant": args.variant, "splits": {}}
    for name, frame in (("train", train), ("validation", validation)):
        result, stats = pipeline.transform(frame)
        result.to_parquet(root / f"{name}.parquet", index=False)
        audit["splits"][name] = stats
    for phase, frame in tests.items():
        result, stats = pipeline.transform(frame, max_test_phase=phase)
        result.to_parquet(root / f"test_{phase}.parquet", index=False)
        audit["splits"][f"test_{phase}"] = stats
    joblib.dump(pipeline, root / "fitted_pipeline.joblib")
    (root / "audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
