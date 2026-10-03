"""Compact, read-only status inspection for LO V0 imputation runs on Modal."""
from __future__ import annotations

import json
from pathlib import Path

import modal


APP_NAME, VOLUME_NAME, MOUNT = "tempo-lo-v0-inspect", "tempo-data-v1", "/data"
META_RELEASE, REGIME, SEED = "imputation-v1", "LO_FULL_EARLY", 20260922

app = modal.App(APP_NAME)
volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)
image = modal.Image.debian_slim(python_version="3.12").pip_install("pyarrow>=16")


def _parquet_rows(path: Path) -> int | None:
    try:
        import pyarrow.parquet as pq

        return int(pq.ParquetFile(path).metadata.num_rows)
    except Exception:
        return None


def _latest_manifest(window: str) -> tuple[Path | None, dict | None]:
    root = (
        Path(MOUNT) / f"meta_release={META_RELEASE}" / "L1_runs" / "task=LO" /
        f"feature_regime={REGIME}" / f"window_id={window}" / "pipeline_id=V0" /
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
def inspect_lo_v0() -> list[dict]:
    """Return one concise status record per LO window without loading data."""
    volume.reload()
    records: list[dict] = []
    for window in ("W1", "W2", "W3"):
        manifest_path, manifest = _latest_manifest(window)
        if manifest is None or manifest_path is None:
            records.append({"window": window, "status": "NOT_STARTED"})
            continue
        root = manifest_path.parent
        inputs = root / "model_inputs"
        input_rows = {
            name: _parquet_rows(inputs / filename)
            for name, filename in {
                "train": "train.parquet",
                "validation": "validation.parquet",
                "test_p1": "test_P1.parquet",
                "test_p2": "test_P2.parquet",
                "test_p3": "test_P3.parquet",
                "test_p4": "test_P4.parquet",
            }.items()
            if (inputs / filename).is_file()
        }
        records.append({
            "window": window,
            "status": manifest.get("run_status"),
            "stage": manifest.get("progress_stage"),
            "run_id": manifest.get("run_id"),
            "attempt_id": manifest.get("attempt_id"),
            "fit_rows": manifest.get("fit_rows"),
            "fit_sample_rows": manifest.get("fit_sample_rows"),
            "split_version": manifest.get("split_version"),
            "phase_version": manifest.get("phase_version"),
            "label_rule_version": manifest.get("label_rule_version"),
            "model_input_rows": input_rows,
            "preprocessor_sha256": manifest.get("preprocessor_sha256"),
            "profile_scope": manifest.get("profile_scope"),
        })
    return records


@app.local_entrypoint()
def cli() -> None:
    print(json.dumps(inspect_lo_v0.remote(), ensure_ascii=False, indent=2))
