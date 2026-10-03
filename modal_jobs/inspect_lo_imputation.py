"""Compact, read-only inspection for LO imputation runs on Modal."""
from __future__ import annotations

import json
from pathlib import Path

import modal


APP_NAME, VOLUME_NAME, MOUNT = "tempo-lo-imputation-inspect", "tempo-data-v1", "/data"
META_RELEASE, REGIME, SEED = "imputation-v1", "LO_FULL_EARLY", 20260922
PIPELINES = {"v0": "V0", "median": "V1", "mean": "V5", "extra_trees": "V9", "mice": "V13"}

app = modal.App(APP_NAME)
volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)
image = modal.Image.debian_slim(python_version="3.12").pip_install("pyarrow>=16")


def _parquet_rows(path: Path) -> int | None:
    try:
        import pyarrow.parquet as pq

        return int(pq.ParquetFile(path).metadata.num_rows)
    except Exception:
        return None


def _latest_manifest(window: str, pipeline_id: str) -> tuple[Path | None, dict | None]:
    root = (
        Path(MOUNT) / f"meta_release={META_RELEASE}" / "L1_runs" / "task=LO" /
        f"feature_regime={REGIME}" / f"window_id={window}" / f"pipeline_id={pipeline_id}" /
        "model_name=IMPUTATION_ONLY" / f"seed={SEED}"
    )
    candidates = sorted(
        root.glob("run_id=*/attempt_id=*/run_manifest.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        return None, None
    path = candidates[0]
    return path, json.loads(path.read_text(encoding="utf-8"))


@app.function(image=image, volumes={MOUNT: volume}, cpu=2, memory=4096, timeout=60 * 10)
def inspect_lo_imputation(variants_csv: str = "v0") -> list[dict]:
    """Return concise manifests and Parquet metadata without loading input data."""
    requested = [value.strip() for value in variants_csv.split(",") if value.strip()]
    if requested == ["all"]:
        requested = list(PIPELINES)
    invalid = sorted(set(requested).difference(PIPELINES))
    if invalid:
        raise ValueError(f"Unknown variants: {invalid}; use one of {sorted(PIPELINES)} or all")
    volume.reload()
    records: list[dict] = []
    for variant in requested:
        for window in ("W1", "W2", "W3"):
            manifest_path, manifest = _latest_manifest(window, PIPELINES[variant])
            if manifest is None or manifest_path is None:
                records.append({"variant": variant, "pipeline_id": PIPELINES[variant], "window": window, "status": "NOT_STARTED"})
                continue
            inputs = manifest_path.parent / "model_inputs"
            rows = {
                name: _parquet_rows(inputs / filename)
                for name, filename in {
                    "train": "train.parquet", "validation": "validation.parquet",
                    "test_p1": "test_P1.parquet", "test_p2": "test_P2.parquet",
                    "test_p3": "test_P3.parquet", "test_p4": "test_P4.parquet",
                }.items()
                if (inputs / filename).is_file()
            }
            records.append({
                "variant": variant,
                "pipeline_id": PIPELINES[variant],
                "window": window,
                "status": manifest.get("run_status"),
                "stage": manifest.get("progress_stage"),
                "run_id": manifest.get("run_id"),
                "attempt_id": manifest.get("attempt_id"),
                "fit_rows": manifest.get("fit_rows"),
                "fit_sample_rows": manifest.get("fit_sample_rows"),
                "split_version": manifest.get("split_version"),
                "phase_version": manifest.get("phase_version"),
                "model_input_rows": rows,
                "preprocessor_sha256": manifest.get("preprocessor_sha256"),
            })
    return records


@app.local_entrypoint()
def cli(variants: str = "v0") -> None:
    print(json.dumps(inspect_lo_imputation.remote(variants), ensure_ascii=False, indent=2))
