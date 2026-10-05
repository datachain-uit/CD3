"""Modal jobs for natural-state profiling and phase-safe imputation."""
from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

import modal

APP_NAME = "tempo-imputation-v1"
VOLUME_NAME = "tempo-data-v1"
MOUNT = "/data"
META_RELEASE = "imputation-v1"
# S0 and S1 are official release-quality measurements. Both scan every row.
# Sampling is deliberately not an S0 CLI option: a sampled profile must never
# be mistaken for the release-quality baseline used to compare imputers.
S0_PROFILE_ROWS = 0  # Internal sentinel: 0 means an all-row census.
S1_PROFILE_ROWS = 0  # 0 means all rows after each imputation.

app = modal.App(APP_NAME)
volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)
image = (modal.Image.debian_slim(python_version="3.12")
         .pip_install("numpy>=1.26", "pandas>=2.2", "pyarrow>=16", "scikit-learn>=1.5", "joblib>=1.4")
         .add_local_python_source("imputation_core")
         .add_local_python_source("release_core"))


def _partition(task: str, regime: str, window: str, phase: str) -> Path:
    return Path(f"task={task}") / f"feature_regime={regime}" / f"window_id={window}" / f"phase_id={phase}"


def _fact_partition(task: str, regime: str, window: str, phase: str, stage: str,
                    *, run_id: str | None = None, attempt_id: str | None = None,
                    state_id: str | None = None) -> Path:
    """Canonical L2 partition; phase is always P1–P4, never a pseudo-ALL phase."""
    path = _partition(task, regime, window, phase) / f"stage={stage}"
    if state_id is not None:
        path /= f"state_id={state_id}"
    if run_id is not None:
        path /= f"run_id={run_id}"
    if attempt_id is not None:
        path /= f"attempt_id={attempt_id}"
    return path


def _next_attempt(run_root: Path) -> tuple[str, Path]:
    """Allocate a new immutable attempt directory for one logical run."""
    attempts = []
    if run_root.exists():
        for child in run_root.iterdir():
            if child.is_dir() and child.name.startswith("attempt_id="):
                try:
                    attempts.append(int(child.name.removeprefix("attempt_id=")))
                except ValueError:
                    continue
    number = max(attempts, default=0) + 1
    return f"{number:04d}", run_root / f"attempt_id={number:04d}"


def _profile_rows(frame, limit: int, seed: int):
    """Return every row for an official census, otherwise a deterministic sample."""
    return frame if limit <= 0 else frame.sample(min(len(frame), limit), random_state=seed)


def _require_enrollment_grain(frame, *, source: str) -> None:
    """Fail before profiling/imputing if the analytical unit is duplicated."""
    if "enrollment_id" not in frame:
        raise ValueError(f"{source} is missing enrollment_id")
    if frame["enrollment_id"].isna().any():
        raise ValueError(f"{source} has null enrollment_id")
    duplicate_count = int(frame["enrollment_id"].duplicated(keep=False).sum())
    if duplicate_count:
        raise ValueError(
            f"{source} violates one-row-per-enrollment grain: rows={len(frame)}, "
            f"distinct_enrollment_id={frame['enrollment_id'].nunique()}, duplicate_rows={duplicate_count}. "
            "Re-materialize and upload the release; do not impute this input."
        )


def _release_view_roots(input_root: Path, spec: dict[str, str]) -> tuple[Path, Path]:
    """Resolve the exact uploaded view directory for a locked input release.

    LO's registered phase version is ``wide_prefix_v3_1`` while the
    materialized artifact carries the fuller immutable release suffix
    ``v3_1_scored_signal_excluded``. Keep both names explicit so the loader
    neither falls back to V1 nor requires a misleading rename during upload.
    """
    phase_root = input_root / spec["phase_views_dir"]
    test_root = input_root / spec["test_prefix_views_dir"]
    if not phase_root.exists() or not test_root.exists():
        raise FileNotFoundError(
            f"Missing views for release_id={spec['release_id']}; expected "
            f"{phase_root} and {test_root}"
        )
    return phase_root, test_root


@app.function(image=image, volumes={MOUNT: volume}, cpu=8, memory=196608, timeout=60 * 60 * 24)
def materialize_s0(task: str, profile_sample_rows: int = S0_PROFILE_ROWS, seed: int = 20260922,
                   release_id: str = "") -> dict:
    """G1: write the pipeline-independent S0_RAW state and locked raw bins once."""
    import pandas as pd
    from imputation_core.meta_storage import (
        FEATURE_REGIME, IMPUTER_PARAMS, PIPELINE_ID, SCALING_CONTRACT, atomic_json, atomic_parquet, build_bin_scheme, canonical_hash,
        class_distribution, dataset_quality_summary, distribution_sketch_locked, dq_profile, drift_measures_from_sketch,
        environment_record, implementation_version, release_inventory,
    )
    from imputation_core.wide_imputation import PHASES, WideImputer, _read
    from release_core import resolve_release, validate_release_manifest

    if task not in {"CQ", "LO"}:
        raise ValueError("task must be CQ or LO")
    if profile_sample_rows > 0:
        raise ValueError("S0_RAW is an official all-row census; profile_sample_rows must be 0")
    spec = resolve_release(task, release_id)
    input_root = Path(MOUNT) / "input" / spec["input_dir"]
    release = release_inventory(input_root, task=task)
    validate_release_manifest(release.get("input_release_manifest", {}), spec, source=str(input_root / "release_manifest.json"))
    release.update({"release_id": spec["release_id"], "split_registry_id": spec["split_registry_id"]})
    root = Path(MOUNT) / f"meta_release={META_RELEASE}"
    l0, l2 = root / "L0_registry", root / "L2_facts"
    atomic_json(l0 / f"data_release_{task}.json", release)
    atomic_json(l0 / "split_registry.json", {"split_version": release["split_version"], "windows": {"W1": ["A", "B", "C"], "W2": ["A+B+C", "D", "E"], "W3": ["A+B+C+D+E", "F", "G"]}, "split_policy": "label_stratified_offering_blocks"})
    atomic_json(l0 / "pipeline_registry.json", {"pipeline_registry_version": "1.0.0", "fit_scope": "TRAIN_POOLED_P1_P4", "impute_scope": "OBSERVED_MISSING_ONLY", "future_unavailable": "NEVER_IMPUTE", "scaling_contract": SCALING_CONTRACT, "pipelines": [{"pipeline_id": PIPELINE_ID[v], "variant": v, "scaling_contract_version": SCALING_CONTRACT["version"], "imputer_params": IMPUTER_PARAMS[v], "balancer": "NONE"} for v in PIPELINE_ID]})
    atomic_json(l0 / "metric_definitions.json", {"metric_def_version": "1.0.0", "dq_def_version": "1.0.0", "bin_rule": "10_quantile_bins_fit_on_train_pooled_p1_p4"})
    atomic_json(l0 / "environments" / f"s0_{task}.json", environment_record())

    all_facts: list[pd.DataFrame] = []
    all_sketches: list[pd.DataFrame] = []
    all_classes: list[pd.DataFrame] = []
    all_quality: list[pd.DataFrame] = []
    state_ids = []
    views, test_views = _release_view_roots(input_root, spec)
    for window in ("W1", "W2", "W3"):
        train = _read(views, [("window", "=", window), ("split", "=", "train")])
        validation = _read(views, [("window", "=", window), ("split", "=", "validation")])
        _require_enrollment_grain(train, source=f"{task}/{window}/train")
        _require_enrollment_grain(validation, source=f"{task}/{window}/validation")
        # Discover role/schema without fitting any transform or using a label.
        probe = WideImputer(task, "v0", 1, seed)
        prepared_train, _ = probe._prepare(train, fitting=True)
        state_key = {
            "task": task,
            "window_id": window,
            "stage": "S0_RAW",
            "profile_scope": "ALL_ROWS",
            # Makes the regenerated full-census facts distinct from the
            # historical 100k-row S0 artifacts.
            "measurement_version": "s0_all_rows_v2",
            "code_version": implementation_version(),
            **{k: release[k] for k in ("data_release_id", "release_id", "split_registry_id", "split_version", "phase_version", "feature_dictionary_version", "label_rule_version", "label_threshold_set")},
        }
        state_id = canonical_hash(state_key)
        state_ids.append(state_id)
        raw_train = prepared_train if profile_sample_rows <= 0 else prepared_train.sample(min(len(prepared_train), profile_sample_rows), random_state=seed)
        bins = build_bin_scheme(raw_train, raw_train, probe, task=task, window=window, stage="S0_RAW", run_id=state_id)
        bin_root = (Path(f"task={task}") / f"feature_regime={FEATURE_REGIME[task]}" /
                    f"window_id={window}" / "fit_scope=TRAIN_POOLED_P1_P4" /
                    "stage=S0_RAW" / f"state_id={state_id}")
        atomic_parquet(bins, l2 / "bin_scheme" / bin_root / "part-00000.parquet")
        for split_name, frame in (("train", train), ("validation", validation)):
            prepared, _ = probe._prepare(frame, fitting=False)
            sample = prepared if profile_sample_rows <= 0 else prepared.sample(min(len(prepared), profile_sample_rows), random_state=seed)
            quality_sample = sample.copy()
            for key in ("enrollment_id", "CQ_label_final" if task == "CQ" else "LO_performance_label_3"):
                if key in frame:
                    quality_sample[key] = frame.loc[sample.index, key]
            for phase in PHASES:
                all_facts.append(dq_profile(sample, sample, probe, task=task, window=window, split=split_name, phase=phase, run_id=state_id, stage="S0_RAW"))
                all_quality.append(dataset_quality_summary(quality_sample, None, probe, task=task, window=window, split=split_name, phase=phase, run_id=state_id, stage="S0_RAW"))
                all_sketches.append(distribution_sketch_locked(sample, sample, probe, bins, task=task, window=window, split=split_name, phase=phase, stage="S0_RAW", run_id=state_id))
                all_classes.append(class_distribution(sample, task=task, window=window, split=split_name, phase=phase, state_id=state_id, stage="S0_RAW"))
        for phase in PHASES:
            test = _read(test_views / phase, [("window", "=", window), ("split", "=", "test")])
            _require_enrollment_grain(test, source=f"{task}/{window}/test_{phase}")
            prepared, _ = probe._prepare(test, fitting=False)
            sample = prepared if profile_sample_rows <= 0 else prepared.sample(min(len(prepared), profile_sample_rows), random_state=seed)
            quality_sample = sample.copy()
            for key in ("enrollment_id", "CQ_label_final" if task == "CQ" else "LO_performance_label_3"):
                if key in test:
                    quality_sample[key] = test.loc[sample.index, key]
            all_facts.append(dq_profile(sample, sample, probe, task=task, window=window, split="test", phase=phase, run_id=state_id, stage="S0_RAW"))
            all_quality.append(dataset_quality_summary(quality_sample, None, probe, task=task, window=window, split="test", phase=phase, run_id=state_id, stage="S0_RAW"))
            all_sketches.append(distribution_sketch_locked(sample, sample, probe, bins, task=task, window=window, split="test", phase=phase, stage="S0_RAW", run_id=state_id))
            all_classes.append(class_distribution(sample, task=task, window=window, split="test", phase=phase, state_id=state_id, stage="S0_RAW"))
        dictionary = pd.DataFrame({"feature_name": prepared_train.columns, "physical_dtype": [str(v) for v in prepared_train.dtypes]})
        dictionary["feature_role"] = dictionary.feature_name.map(lambda c: "dynamic" if c in probe.dynamic_source else "static" if c in probe.static_columns else "categorical" if c in probe.categorical else "excluded_or_mask")
        atomic_parquet(dictionary, l0 / "feature_dictionary" / f"task={task}" / f"window_id={window}" / "feature_dictionary.parquet")

    facts, sketches, classes, quality = pd.concat(all_facts, ignore_index=True), pd.concat(all_sketches, ignore_index=True), pd.concat(all_classes, ignore_index=True), pd.concat(all_quality, ignore_index=True)
    drift = drift_measures_from_sketch(sketches, task=task, window="ALL", stage="S0_RAW", run_id=None)
    for (window, phase), subset in facts.groupby(["window_id", "phase_id"]):
        partition = _fact_partition(task, FEATURE_REGIME[task], window, phase, "S0_RAW", state_id=state_ids[("W1", "W2", "W3").index(window)])
        atomic_parquet(subset.assign(state_id=state_ids[("W1", "W2", "W3").index(window)]), l2 / "dq_feature_profile" / partition / "part-00000.parquet")
        atomic_parquet(quality.loc[(quality.window_id == window) & (quality.phase_id == phase)].assign(state_id=state_ids[("W1", "W2", "W3").index(window)]), l2 / "dataset_quality_summary" / partition / "part-00000.parquet")
        atomic_parquet(sketches.loc[(sketches.window_id == window) & (sketches.phase_id == phase)].assign(state_id=state_ids[("W1", "W2", "W3").index(window)]), l2 / "distribution_sketch" / partition / "part-00000.parquet")
        atomic_parquet(classes.loc[(classes.window_id == window) & (classes.phase_id == phase)].assign(state_id=state_ids[("W1", "W2", "W3").index(window)]), l2 / "class_distribution" / partition / "part-00000.parquet")
        atomic_parquet(drift.loc[(drift.window_id == window) & (drift.phase_id == phase)].assign(state_id=state_ids[("W1", "W2", "W3").index(window)]), l2 / "drift_measures" / partition / "part-00000.parquet")
    manifest = {"task": task, "stage": "S0_RAW", "profile_scope": "ALL_ROWS" if profile_sample_rows <= 0 else "SAMPLED_ROWS", "profile_sample_rows_max": "ALL_ROWS" if profile_sample_rows <= 0 else profile_sample_rows, "state_ids": state_ids, "release": release}
    atomic_json(root / "L0_registry" / "state_manifests" / f"s0_{task}.json", manifest)
    volume.commit()
    return manifest


@app.function(image=image, volumes={MOUNT: volume}, cpu=1, memory=2048, timeout=60 * 30)
def export_s0_facts() -> dict:
    """Package only the current all-row S0 facts into one portable archive.

    The archive deliberately uses a short, human-readable local tree and
    selects facts by the state IDs in the current S0 manifests.  It therefore
    cannot accidentally include older sampled S0 states or S1 imputation facts.
    """
    root = Path(MOUNT) / f"meta_release={META_RELEASE}"
    l0, l2 = root / "L0_registry", root / "L2_facts"
    archive_path = root / "exports" / "s0_all_rows_v2.zip"
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = Path("/tmp/s0_all_rows_v2.zip")
    if temp_path.exists():
        temp_path.unlink()

    regimes = {"CQ": "CQ_RAW_EARLY", "LO": "LO_FULL_EARLY"}
    fact_kinds = (
        "dq_feature_profile", "dataset_quality_summary", "distribution_sketch",
        "class_distribution", "drift_measures",
    )
    windows, phases = ("W1", "W2", "W3"), ("P1", "P2", "P3", "P4")
    included: list[str] = []
    missing: list[str] = []
    with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for task, regime in regimes.items():
            manifest_path = l0 / "state_manifests" / f"s0_{task}.json"
            if not manifest_path.exists():
                raise FileNotFoundError(f"Missing current S0 manifest: {manifest_path}")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("profile_scope") != "ALL_ROWS":
                raise RuntimeError(f"Refusing to export sampled S0 state for {task}")
            archive.write(manifest_path, f"manifests/s0_{task}.json")
            included.append(f"manifests/s0_{task}.json")
            for index, window in enumerate(windows):
                state_id = manifest["state_ids"][index]
                for phase in phases:
                    for kind in fact_kinds:
                        source = (l2 / kind / f"task={task}" / f"feature_regime={regime}" /
                                  f"window_id={window}" / f"phase_id={phase}" /
                                  "stage=S0_RAW" / f"state_id={state_id}" / "part-00000.parquet")
                        target = f"L2_facts/task={task}/window_id={window}/phase_id={phase}/{kind}.parquet"
                        if source.exists():
                            archive.write(source, target)
                            included.append(target)
                        else:
                            missing.append(str(source))
                bin_source = (l2 / "bin_scheme" / f"task={task}" / f"feature_regime={regime}" /
                              f"window_id={window}" / "fit_scope=TRAIN_POOLED_P1_P4" /
                              "stage=S0_RAW" / f"state_id={state_id}" / "part-00000.parquet")
                bin_target = f"L2_facts/task={task}/window_id={window}/bin_scheme.parquet"
                if bin_source.exists():
                    archive.write(bin_source, bin_target)
                    included.append(bin_target)
                else:
                    missing.append(str(bin_source))
        archive.writestr("EXPORT_MANIFEST.json", json.dumps({
            "artifact": "s0_all_rows_v2",
            "included_files": included,
            "missing_files": missing,
        }, indent=2, sort_keys=True))
    shutil.copy2(temp_path, archive_path)
    volume.commit()
    return {"archive": str(archive_path), "included_files": len(included), "missing_files": missing}


# Full-train learned imputers and the all-row S0 quality census can retain
# large working matrices. Allocate 192 GB to each isolated Modal invocation.
@app.function(image=image, volumes={MOUNT: volume}, cpu=8, memory=196608, timeout=60 * 60 * 24)
def run_imputation(task: str, window: str, test_phase: str, variant: str,
                   fit_sample_rows: int = 1_000_000, seed: int = 20260922,
                   release_id: str = "") -> dict:
    """G2a: fit one imputer and write L1, S1/L2, resource and diagnostic L3."""
    import joblib
    import pandas as pd
    from imputation_core.meta_storage import (
        FEATURE_REGIME, IMPUTER_PARAMS, PIPELINE_ID, SCALING_CONTRACT, Telemetry, atomic_json, atomic_parquet,
        build_bin_scheme, canonical_hash, dataset_quality_summary, distribution_sketch_locked, dq_profile,
        drift_measures_from_sketch, environment_record, fidelity_probe, file_sha256, implementation_version, l3_rows, release_inventory,
    )
    from imputation_core.wide_imputation import PHASES, WideImputer, _label_column, _read, fit_sample_rows_for_variant
    from release_core import resolve_release, validate_release_manifest

    if task not in {"CQ", "LO"} or window not in {"W1", "W2", "W3"}:
        raise ValueError("task must be CQ/LO and window must be W1/W2/W3")
    if test_phase not in {"ALL", *PHASES} or variant not in PIPELINE_ID:
        raise ValueError("invalid test_phase or variant")
    telemetry = Telemetry()
    print(json.dumps({"event": "run_started", "task": task, "window_id": window,
                      "variant": variant, "test_phase": test_phase}, sort_keys=True), flush=True)
    spec = resolve_release(task, release_id)
    input_root = Path(MOUNT) / "input" / spec["input_dir"]
    root = Path(MOUNT) / f"meta_release={META_RELEASE}"
    release = release_inventory(input_root, task=task)
    validate_release_manifest(release.get("input_release_manifest", {}), spec, source=str(input_root / "release_manifest.json"))
    release.update({"release_id": spec["release_id"], "split_registry_id": spec["split_registry_id"]})
    s0_manifest = root / "L0_registry" / "state_manifests" / f"s0_{task}.json"
    if not s0_manifest.exists():
        raise RuntimeError(f"Run materialize_s0 for {task} before imputation.")
    views, test_views = _release_view_roots(input_root, spec)
    train = _read(views, [("window", "=", window), ("split", "=", "train")])
    validation = _read(views, [("window", "=", window), ("split", "=", "validation")])
    phases = PHASES if test_phase == "ALL" else (test_phase,)
    tests = {phase: _read(test_views / phase, [("window", "=", window), ("split", "=", "test")]) for phase in phases}
    _require_enrollment_grain(train, source=f"{task}/{window}/train")
    _require_enrollment_grain(validation, source=f"{task}/{window}/validation")
    for phase, frame in tests.items():
        _require_enrollment_grain(frame, source=f"{task}/{window}/test_{phase}")
    # CQ labels do not carry a per-row threshold-set field, whereas LO labels
    # do.  Both releases nevertheless have a locked threshold-set identity.
    # Stamp it before preprocessing so WideImputer preserves it as the required
    # non-predictive ``context__label_threshold_set`` audit field.
    for frame in (train, validation, *tests.values()):
        if "label_threshold_set" not in frame.columns:
            frame["label_threshold_set"] = spec["label_threshold_set"]
    telemetry.mark("read")
    print(json.dumps({"event": "input_read_complete", "train_rows": len(train),
                      "validation_rows": len(validation),
                      "test_rows": {phase: len(frame) for phase, frame in tests.items()}}, sort_keys=True), flush=True)
    label = _label_column(task)
    for name, frame in (("train", train), ("validation", validation), *((f"test_{p}", x) for p, x in tests.items())):
        if label not in frame or frame[label].isna().any():
            raise ValueError(f"{name} has incomplete {label}")

    effective_fit_sample_rows = fit_sample_rows_for_variant(variant, fit_sample_rows)
    pipeline_id = PIPELINE_ID[variant]
    # run_id identifies a scientific/logical configuration. Source code and
    # environment remain provenance on each attempt, not inputs to this hash.
    run_key = {"task": task, "feature_regime": FEATURE_REGIME[task], "window_id": window, "pipeline_id": pipeline_id,
               "model_name": "IMPUTATION_ONLY", "pipeline_version": "1.0.0",
               "variant": variant, "imputer_params": IMPUTER_PARAMS[variant], "fit_sample_rows": ("ALL_TRAIN" if effective_fit_sample_rows == 0 else effective_fit_sample_rows), "scaling_contract": SCALING_CONTRACT, "seed": seed, "fit_scope": "TRAIN_POOLED_P1_P4", "impute_scope": "OBSERVED_MISSING_ONLY",
               **{k: release[k] for k in ("data_release_id", "release_id", "split_registry_id", "split_version", "phase_version", "feature_dictionary_version", "label_rule_version", "label_threshold_set")}}
    run_id = canonical_hash(run_key)
    run_root = (root / "L1_runs" / f"task={task}" / f"feature_regime={FEATURE_REGIME[task]}" /
                f"window_id={window}" / f"pipeline_id={pipeline_id}" /
                "model_name=IMPUTATION_ONLY" / f"seed={seed}" / f"run_id={run_id}")
    attempt_number, l1 = _next_attempt(run_root)
    attempt_id = f"{run_id}-{attempt_number}"
    model_inputs, preprocessors = l1 / "model_inputs", l1 / "fitted_preprocessors"
    manifest = {**run_key, "run_id": run_id, "attempt_id": attempt_id, "attempt_number": attempt_number,
                "implementation_version": implementation_version(), "run_status": "RUNNING", "fit_rows": len(train), "fit_sample_rows": ("ALL_TRAIN" if effective_fit_sample_rows == 0 else min(len(train), effective_fit_sample_rows)), "splits": {}}
    atomic_json(l1 / "run_manifest.json", manifest)
    atomic_json(root / "L0_registry" / "environments" / f"attempt_id={attempt_id}.json", environment_record())

    def checkpoint(stage: str, **details) -> None:
        manifest["progress_stage"] = stage
        manifest["progress_details"] = details
        atomic_json(l1 / "run_manifest.json", manifest)
        print(json.dumps({"event": stage, "run_id": run_id, "attempt_id": attempt_id,
                          **details}, sort_keys=True, default=str), flush=True)

    checkpoint("preprocess_fit_started", fit_rows=len(train),
               fit_sample_rows=("ALL_TRAIN" if effective_fit_sample_rows == 0 else effective_fit_sample_rows))
    pipeline = WideImputer(task, variant, effective_fit_sample_rows, seed).fit(train)
    # Preserve the exact categorical schema for downstream augmentation: these
    # integer encodings are nominal and must be inherited, never interpolated.
    manifest["categorical_columns"] = list(pipeline.categorical)
    atomic_json(l1 / "run_manifest.json", manifest)
    telemetry.mark("preprocess_fit")
    checkpoint("preprocess_fit_complete")
    raw_train_sample = _profile_rows(train, S1_PROFILE_ROWS, seed)
    prepared_train_sample, _ = pipeline._prepare(raw_train_sample, fitting=False)
    transformed_frames: dict[str, pd.DataFrame] = {}
    facts: list[pd.DataFrame] = []
    quality_facts: list[pd.DataFrame] = []
    sketches_input: list[tuple[pd.DataFrame, pd.DataFrame, str, str]] = []
    for split_name, frame in (("train", train), ("validation", validation)):
        checkpoint("transform_started", split=split_name, rows=len(frame), observed_phases="P1_P2_P3_P4")
        transformed, split_audit = pipeline.transform(frame)
        atomic_parquet(transformed, model_inputs / f"{split_name}.parquet")
        manifest["splits"][split_name] = split_audit
        transformed_frames[split_name] = transformed
        raw_sample = _profile_rows(frame, S1_PROFILE_ROWS, seed)
        prepared_sample, _ = pipeline._prepare(raw_sample, fitting=False)
        out_sample = transformed.loc[prepared_sample.index]
        quality_sample = prepared_sample.copy()
        for key in ("enrollment_id", label):
            if key in raw_sample:
                quality_sample[key] = raw_sample.loc[prepared_sample.index, key]
        for phase in PHASES:
            facts.append(dq_profile(prepared_sample, out_sample, pipeline, task=task, window=window, split=split_name, phase=phase, run_id=run_id, stage="S1_IMPUTED"))
            quality_facts.append(dataset_quality_summary(quality_sample, out_sample, pipeline, task=task, window=window, split=split_name, phase=phase, run_id=run_id, stage="S1_IMPUTED"))
            sketches_input.append((prepared_sample, out_sample, split_name, phase))
        checkpoint("transform_complete", split=split_name, rows=len(frame))
    for phase, frame in tests.items():
        checkpoint("transform_started", split="test", phase_id=phase, rows=len(frame), observed_phases="P1_TO_" + phase)
        transformed, split_audit = pipeline.transform(frame, max_test_phase=phase)
        atomic_parquet(transformed, model_inputs / f"test_{phase}.parquet")
        manifest["splits"][f"test_{phase}"] = split_audit
        raw_sample = _profile_rows(frame, S1_PROFILE_ROWS, seed)
        prepared_sample, _ = pipeline._prepare(raw_sample, fitting=False)
        out_sample = transformed.loc[prepared_sample.index]
        quality_sample = prepared_sample.copy()
        for key in ("enrollment_id", label):
            if key in raw_sample:
                quality_sample[key] = raw_sample.loc[prepared_sample.index, key]
        facts.append(dq_profile(prepared_sample, out_sample, pipeline, task=task, window=window, split="test", phase=phase, run_id=run_id, stage="S1_IMPUTED"))
        quality_facts.append(dataset_quality_summary(quality_sample, out_sample, pipeline, task=task, window=window, split="test", phase=phase, run_id=run_id, stage="S1_IMPUTED"))
        sketches_input.append((prepared_sample, out_sample, "test", phase))
        checkpoint("transform_complete", split="test", phase_id=phase, rows=len(frame))
    telemetry.mark("transform_write")

    checkpoint("s1_quality_facts_started", profile_scope="ALL_ROWS" if S1_PROFILE_ROWS <= 0 else "SAMPLED_ROWS")
    transformed_train_sample = transformed_frames["train"].loc[prepared_train_sample.index]
    s1_bins = build_bin_scheme(prepared_train_sample, transformed_train_sample, pipeline, task=task, window=window, stage="S1_IMPUTED", run_id=run_id)
    sketches = [distribution_sketch_locked(raw, out, pipeline, s1_bins, task=task, window=window, split=split_name, phase=phase, stage="S1_IMPUTED", run_id=run_id) for raw, out, split_name, phase in sketches_input]
    preprocessors.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, preprocessors / "fitted_pipeline.joblib")
    pipeline_hash = file_sha256(preprocessors / "fitted_pipeline.joblib")
    atomic_json(preprocessors / "sha256.json", {"fitted_pipeline.joblib": f"sha256:{pipeline_hash}"})
    fidelity = fidelity_probe(pipeline, validation, transformed_frames["validation"], task=task, window=window, run_id=run_id, seed=seed)
    telemetry.mark("fidelity")
    checkpoint("s1_quality_facts_complete", fact_rows=len(facts), quality_rows=len(quality_facts))
    resource = telemetry.row(run_id=run_id, task=task, window=window, pipeline_id=pipeline_id, seed=seed, cpu_allocated=8)
    resource["cost_shared_across_phases"] = True

    l2 = root / "L2_facts"
    all_facts, all_sketches, all_quality = pd.concat(facts, ignore_index=True), pd.concat(sketches, ignore_index=True), pd.concat(quality_facts, ignore_index=True)
    drift = drift_measures_from_sketch(all_sketches, task=task, window=window, stage="S1_IMPUTED", run_id=run_id)
    bin_root = (Path(f"task={task}") / f"feature_regime={FEATURE_REGIME[task]}" /
                f"window_id={window}" / "fit_scope=TRAIN_POOLED_P1_P4" /
                "stage=S1_IMPUTED" / f"run_id={run_id}" / f"attempt_id={attempt_id}")
    checkpoint("artifact_write_started")
    atomic_parquet(s1_bins.assign(attempt_id=attempt_id), l2 / "bin_scheme" / bin_root / "part-00000.parquet")
    for phase, phase_facts in all_facts.groupby("phase_id"):
        partition = _fact_partition(task, FEATURE_REGIME[task], window, phase, "S1_IMPUTED", run_id=run_id, attempt_id=attempt_id)
        atomic_parquet(phase_facts.assign(attempt_id=attempt_id, pipeline_id=pipeline_id), l2 / "dq_feature_profile" / partition / "part-00000.parquet")
        atomic_parquet(all_quality.loc[all_quality.phase_id.eq(phase)].assign(attempt_id=attempt_id, pipeline_id=pipeline_id), l2 / "dataset_quality_summary" / partition / "part-00000.parquet")
        atomic_parquet(all_sketches.loc[all_sketches.phase_id.eq(phase)].assign(attempt_id=attempt_id, pipeline_id=pipeline_id), l2 / "distribution_sketch" / partition / "part-00000.parquet")
        atomic_parquet(drift.loc[drift.phase_id.eq(phase)].assign(attempt_id=attempt_id, pipeline_id=pipeline_id), l2 / "drift_measures" / partition / "part-00000.parquet")
        atomic_parquet(resource.assign(phase_id=phase, attempt_id=attempt_id), l2 / "resource_usage" / partition / "part-00000.parquet")
    if not fidelity.empty:
        fidelity_partition = _fact_partition(task, FEATURE_REGIME[task], window, "P4", "S1_IMPUTED", run_id=run_id, attempt_id=attempt_id)
        atomic_parquet(fidelity.assign(attempt_id=attempt_id, pipeline_id=pipeline_id), l2 / "imputation_fidelity" / fidelity_partition / "part-00000.parquet")
    diagnostic = l3_rows(
        all_facts, resource, task=task, window=window, run_id=run_id,
        pipeline_id=pipeline_id, seed=seed,
        label_rule_version=release["label_rule_version"],
        label_threshold_set=release["label_threshold_set"],
    )
    diagnostic_partition = (Path(f"task={task}") / f"feature_regime={FEATURE_REGIME[task]}" /
                            f"window_id={window}" / f"pipeline_id={pipeline_id}" /
                            "model_name=IMPUTATION_ONLY" / f"seed={seed}" /
                            f"run_id={run_id}" / f"attempt_id={attempt_id}")
    atomic_parquet(diagnostic.assign(attempt_id=attempt_id), root / "L3_meta" / "imputation_diagnostic_seed_level" / diagnostic_partition / "part-00000.parquet")
    manifest.update({"run_status": "SUCCESS", "progress_stage": "complete", "profile_scope": "ALL_ROWS" if S1_PROFILE_ROWS <= 0 else "SAMPLED_ROWS", "profile_sample_rows_max": "ALL_ROWS" if S1_PROFILE_ROWS <= 0 else S1_PROFILE_ROWS, "preprocessor_sha256": f"sha256:{pipeline_hash}", "cost_shared_across_phases": True})
    atomic_json(l1 / "run_manifest.json", manifest)
    volume.commit()
    print(json.dumps({"event": "run_complete", "run_id": run_id, "attempt_id": attempt_id}, sort_keys=True), flush=True)
    return manifest


@app.local_entrypoint()
def cli(mode: str = "impute", task: str = "CQ", window: str = "W1", test_phase: str = "ALL", variant: str = "median", fit_sample_rows: int = 1_000_000, seed: int = 20260922, release_id: str = ""):
    if mode == "s0":
        result = materialize_s0.remote(task, S0_PROFILE_ROWS, seed, release_id)
    elif mode == "export_s0":
        result = export_s0_facts.remote()
    elif mode == "impute":
        result = run_imputation.remote(task, window, test_phase, variant, fit_sample_rows, seed, release_id)
    else:
        raise ValueError("mode must be s0, export_s0, or impute")
    print(json.dumps(result, indent=2))
