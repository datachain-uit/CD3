"""Materialize auditable synthetic TRAIN rows without interpolating identities or masks."""
from __future__ import annotations

import hashlib
import json
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from .contracts import SyntheticBatch, synthetic_available_mask, synthetic_missing_mask


IDENTITY_CODES = {"user_id_code", "course_id_code", "teacher_id_code", "school_id_code"}
PROVENANCE = {"enrollment_id", "offering_id", "window", "split", "task", "scenario"}


def augmentable_model_columns(source: pd.DataFrame, *, label_column: str, phase_id: str) -> list[str]:
    """Return the complete numeric model input eligible for interpolation.

    At prefix ``Pk`` a synthetic row contains every dynamic value from
    P1..Pk *and* every numeric static feature.  IDs, labels, categorical codes
    and all masks are inherited or regenerated separately, never interpolated.
    """
    if phase_id not in {"P1", "P2", "P3", "P4"}:
        raise ValueError("phase_id must be P1-P4")
    allowed_phases = {f"P{index}" for index in range(1, int(phase_id[1:]) + 1)}
    result: list[str] = []
    for column in source.columns:
        if column in IDENTITY_CODES | PROVENANCE | {label_column} or column.startswith("context__"):
            continue
        if column.startswith(("missing__", "phase_available_", "video_observed_mask_",
                              "problem_observed_mask_", "comment_observed_mask_")):
            continue
        if not pd.api.types.is_numeric_dtype(source[column]):
            continue
        suffix = column.rsplit("_", 1)
        if len(suffix) == 2 and suffix[1] in {"P1", "P2", "P3", "P4"}:
            if suffix[1] not in allowed_phases:
                continue
        result.append(column)
    if not result:
        raise ValueError("no numeric dynamic/static model feature available for augmentation")
    return result


def materialize_synthetic_rows(
    source: pd.DataFrame,
    batch: SyntheticBatch,
    *,
    numeric_columns: Sequence[str],
    label_column: str,
    available_mask_columns: Sequence[str],
    missing_mask_columns: Sequence[str],
    context: Mapping[str, str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create TRAIN-only synthetic rows and the mandatory parent ledger.

    ``numeric_columns`` must be finite post-imputation model features and must
    exclude IDs/categorical codes. Categorical context and code columns are
    inherited from parent A; available masks are the intersection, and missing
    flags are the union, of both parents.
    """
    if any(column in IDENTITY_CODES for column in numeric_columns):
        raise ValueError("identity codes must be inherited from parent_a, never interpolated")
    if len(batch.labels) == 0:
        return source.iloc[0:0].copy(), pd.DataFrame()
    if len(numeric_columns) != batch.values.shape[1]:
        raise ValueError("numeric_columns does not match synthetic feature width")

    synthetic = source.iloc[batch.parent_a].copy().reset_index(drop=True)
    # SMOTE interpolation is continuous, including for source count columns
    # that arrived as int32/int64.  Convert only augmentable features before
    # assignment; IDs, labels and binary availability/missing masks retain
    # their original dtypes and are never interpolated.
    synthetic = synthetic.astype({column: np.float32 for column in numeric_columns}, copy=False)
    synthetic.loc[:, list(numeric_columns)] = batch.values
    synthetic[label_column] = batch.labels
    for column in available_mask_columns:
        if column in source:
            synthetic[column] = synthetic_available_mask(source[column].to_numpy(), batch.parent_a, batch.parent_b)
    for column in missing_mask_columns:
        if column in source:
            synthetic[column] = synthetic_missing_mask(source[column].to_numpy(), batch.parent_a, batch.parent_b)

    parent_key = source["enrollment_id"].astype("string") if "enrollment_id" in source else pd.Series(source.index.astype(str), index=source.index)
    records = []
    for ordinal, (left, right, alpha, label) in enumerate(zip(batch.parent_a, batch.parent_b, batch.alpha, batch.labels)):
        payload = {**context, "method": batch.method, "parent_a": str(parent_key.iloc[left]),
                   "parent_b": str(parent_key.iloc[right]), "ordinal": ordinal}
        synthetic_id = "synthetic:" + hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        records.append({"synthetic_id": synthetic_id, "synthetic_ordinal": ordinal,
                        "synthetic_method": batch.method, "parent_a_enrollment_id": str(parent_key.iloc[left]),
                        "parent_b_enrollment_id": str(parent_key.iloc[right]), "interpolation_alpha": float(alpha),
                        "label": str(label), **context})
    ledger = pd.DataFrame(records)
    synthetic.insert(0, "synthetic_id", ledger["synthetic_id"].to_numpy())
    # enrollment_id is provenance only, not a model feature. Do not duplicate a
    # real enrollment identifier for an artificial row.
    if "enrollment_id" in synthetic:
        synthetic["enrollment_id"] = ledger["synthetic_id"].to_numpy()
    return synthetic, ledger
