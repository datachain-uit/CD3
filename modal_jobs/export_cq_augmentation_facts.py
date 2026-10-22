"""Export the immutable CQ S2 sampling plans and Radius-SMOTE fallback audits.

The exporter follows the augmentation run IDs declared by the selected S3
manifests.  It therefore cannot accidentally report a superseded S2 attempt.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import modal


APP_NAME, VOLUME_NAME, MOUNT = "tempo-cq-augmentation-export-v1", "tempo-data-v1", "/data"
META_RELEASE, TASK, REGIME = "imputation-v1", "CQ", "CQ_RAW_EARLY"
DEFAULT_REPORT_ID = "RNN_seed42_v2_2_clean_20261007_r1"
PIPELINES = tuple(f"V{number}" for number in range(17))
RADIUS_PIPELINES = {"V4", "V8", "V12", "V16"}
METHOD_BY_PIPELINE = {
    **{pipeline: "CDSMOTE" for pipeline in ("V2", "V6", "V10", "V14")},
    **{pipeline: "SASMOTE" for pipeline in ("V3", "V7", "V11", "V15")},
    **{pipeline: "RADIUS_SMOTE" for pipeline in RADIUS_PIPELINES},
}

app = modal.App(APP_NAME)
volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=False)
image = (modal.Image.debian_slim(python_version="3.12")
         .pip_install("numpy>=1.26", "pandas>=2.2", "pyarrow>=16", "scikit-learn>=1.5", "joblib>=1.3")
         .add_local_python_source("imputation_core")
         .add_local_python_source("release_core"))


def _selected_models(base: Path, *, seed: int, spec: dict[str, str],
                     accepted_identities: dict[str, str]) -> list[dict]:
    selected: dict[tuple[str, str], tuple[int, float, dict]] = {}
    pattern = (f"task=CQ/feature_regime={REGIME}/window_id=*/pipeline_id=*/"
               f"model_name=RNN/seed={seed}/run_id=*/attempt_id=*/run_manifest.json")
    for path in base.glob(pattern):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if (manifest.get("run_status") != "SUCCESS" or
                any(manifest.get(field) != spec[field] for field in
                    ("release_id", "split_registry_id", "split_version", "phase_version"))):
            continue
        identity = str(manifest.get("data_release_id") or "")
        if identity not in accepted_identities:
            raise ValueError(
                "CQ RNN manifest matches the active release contract but has unknown "
                f"data_release_id={identity or '<absent>'}"
            )
        manifest = {**manifest, "data_release_identity_class": accepted_identities[identity]}
        key = str(manifest.get("pipeline_id")), str(manifest.get("window_id"))
        if key[0] not in PIPELINES or key[1] not in {"W1", "W2", "W3"}:
            continue
        suffix = str(manifest.get("attempt_id", "")).rsplit("-", 1)[-1]
        candidate = (int(suffix) if suffix.isdigit() else 0, path.stat().st_mtime, manifest)
        if key not in selected or candidate[:2] > selected[key][:2]:
            selected[key] = candidate
    if len(selected) != 51:
        raise RuntimeError(f"Expected 51 current RNN runs, found {len(selected)}")
    return [candidate[2] for candidate in selected.values()]


@app.function(image=image, volumes={MOUNT: volume}, cpu=1, memory=2048, timeout=30 * 60)
def export_cq_augmentation_facts(seed: int = 42, report_id: str = "") -> dict:
    import pandas as pd
    from imputation_core.meta_storage import release_identity_aliases
    from release_core import resolve_release

    spec = resolve_release(TASK, "CQ_V2_2")
    base = Path(MOUNT) / f"meta_release={META_RELEASE}"
    release, accepted_identities = release_identity_aliases(
        Path(MOUNT) / "input" / spec["input_dir"], task=TASK
    )
    data_release_id = release["data_release_id"]
    models = _selected_models(base / "L1_runs", seed=seed, spec=spec,
                              accepted_identities=accepted_identities)
    references = {
        str(manifest["parent_augmentation_run_id"]): manifest
        for manifest in models if manifest.get("parent_augmentation_run_id")
    }
    if len(references) != 36:
        raise RuntimeError(f"Expected 36 S2 parents for the 12 balanced pipelines, found {len(references)}")

    manifests: dict[str, tuple[Path, dict]] = {}
    for path in (base / "L1_runs").glob(
        f"task=CQ/feature_regime={REGIME}/window_id=*/phase_id=P4/pipeline_id=*/"
        f"model_name=BALANCED_TRAIN_ONLY/seed={seed}/run_id=*/attempt_id=*/run_manifest.json"
    ):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        run_id = str(manifest.get("run_id"))
        if run_id not in references or manifest.get("run_status") != "SUCCESS":
            continue
        if any(manifest.get(field) != spec[field] for field in
               ("release_id", "split_registry_id", "split_version", "phase_version")):
            continue
        previous = manifests.get(run_id)
        if previous is None or path.stat().st_mtime > previous[0].stat().st_mtime:
            manifests[run_id] = (path, manifest)
    if set(manifests) != set(references):
        missing = sorted(set(references).difference(manifests))
        raise RuntimeError(f"Selected RNN manifests reference missing/incompatible S2 parents: {missing}")

    sampling_rows, radius_rows = [], []
    for run_id, (path, manifest) in manifests.items():
        audit = manifest.get("algorithm_audit") or {}
        config = manifest.get("algorithm_config") or {}
        parent = references[run_id]
        balance_pipeline = str(manifest.get("balance_pipeline"))
        # The pipeline identifier is the release contract.  Some early S2
        # manifests retained the placeholder ``UNSPECIFIED_LEGACY_METHOD``;
        # do not let that stale, truthy value leak into a current report.
        locked_method = METHOD_BY_PIPELINE.get(balance_pipeline)
        manifest_method = manifest.get("method")
        if locked_method is not None:
            if manifest_method not in (None, "", "UNSPECIFIED_LEGACY_METHOD", locked_method):
                raise ValueError(
                    "S2 method conflicts with the locked pipeline contract: "
                    f"pipeline={balance_pipeline}, manifest_method={manifest_method!r}, "
                    f"locked_method={locked_method!r}"
                )
            method = locked_method
        else:
            method = manifest_method or "NONE"
        common = {
            "task": TASK, "release_id": spec["release_id"], "data_release_id": data_release_id,
            "data_release_identity_class": parent.get("data_release_identity_class"),
            "window_id": manifest.get("window_id"), "phase_id": manifest.get("phase_id"),
            "pipeline_id": balance_pipeline, "parent_pipeline": manifest.get("parent_pipeline"),
            "method": method, "manifest_method": manifest_method,
            "seed_augmentation": manifest.get("seed_augmentation"),
            "augmentation_run_id": run_id, "augmentation_attempt_id": manifest.get("attempt_id"),
            "consumer_model_run_id": parent.get("run_id"), "rows_original": manifest.get("rows_original"),
            "rows_synthetic": manifest.get("rows_synthetic"), "rows_balanced": manifest.get("rows_balanced"),
            "sampling_plan_json": json.dumps(config.get("sampling_plan", {}), sort_keys=True),
            "algorithm_config_json": json.dumps(config, sort_keys=True),
            "manifest_mtime_utc": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
        }
        sampling_rows.append(common)
        if balance_pipeline not in RADIUS_PIPELINES:
            continue
        by_class = audit.get("fallback_by_class") or {}
        if by_class:
            for label, values in by_class.items():
                radius_rows.append({**common, "class_code": str(label), "fallback_grain": "class",
                                    **values, "radius": audit.get("radius"),
                                    "radius_space": audit.get("radius_space")})
        else:
            # Older immutable S2 manifests did not retain per-class fallback;
            # retain their aggregate result but make the insufficiency explicit.
            radius_rows.append({**common, "class_code": None, "fallback_grain": "aggregate_legacy",
                                "generated_rows": manifest.get("rows_synthetic"),
                                "fallback_nearest_neighbour_rows": audit.get("fallback_nearest_neighbour_rows"),
                                "fallback_nearest_neighbour_rate": audit.get("fallback_nearest_neighbour_rate"),
                                "radius": audit.get("radius"), "radius_space": audit.get("radius_space")})

    export_id = report_id or DEFAULT_REPORT_ID
    output = base / "L2_facts" / "report_exports" / "task=CQ" / f"report_id={export_id}"
    output.mkdir(parents=True, exist_ok=True)
    sampling = pd.DataFrame(sampling_rows).sort_values(["window_id", "pipeline_id"])
    radius = pd.DataFrame(radius_rows)
    if radius.empty:
        discovered = sorted({str(item[1].get("balance_pipeline")) for item in manifests.values()})
        raise RuntimeError(
            "No Radius-SMOTE parent manifest was found among the selected S3 runs; "
            f"discovered balance pipelines={discovered}"
        )
    radius = radius.sort_values(["window_id", "pipeline_id", "class_code"], na_position="last")
    sampling.to_parquet(output / "augmentation_sampling_plan_long.parquet", index=False)
    radius.to_parquet(output / "radius_fallback_long.parquet", index=False)
    metadata = {
        "task": TASK, "report_id": export_id, "seed": seed, "release_id": spec["release_id"],
        "data_release_id": data_release_id, "accepted_data_release_identities": accepted_identities,
        "sampling_plan_rows": len(sampling),
        "radius_fallback_rows": len(radius),
        "radius_class_grain_complete": bool(not radius.empty and (radius["fallback_grain"] == "class").all()),
        "paths": {"augmentation_sampling_plan_long": str(output / "augmentation_sampling_plan_long.parquet"),
                  "radius_fallback_long": str(output / "radius_fallback_long.parquet")},
    }
    (output / "augmentation_export_manifest.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    volume.commit()
    return metadata


@app.local_entrypoint()
def cli(seed: int = 42, report_id: str = "") -> None:
    print(json.dumps(export_cq_augmentation_facts.remote(seed, report_id), indent=2))
