"""Deterministic categorical codes for prefixed MOOC identifiers.

The numeric suffix is an identifier code, not an ordinal/continuous feature.
Callers must keep it out of numeric scaling and fit any vocabulary only on the
selected training partition; unseen validation/test values map to ``UNK``.
"""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd


PREFIXES = {
    "user_id": "U_",
    "course_id": "C_",
    "teacher_id": "T_",
    "school_id": "S_",
}


def prefixed_id_to_code(values: Iterable[object], prefix: str) -> pd.Series:
    """Strip a two-character prefix and return nullable integer ID codes.

    Invalid/null values remain ``<NA>`` rather than becoming a made-up numeric
    value.  This is intentionally a categorical code, never a scaled feature.
    """
    series = pd.Series(values, dtype="string")
    suffix = series.str.extract(rf"^{prefix}(\d+)$", expand=False)
    return pd.to_numeric(suffix, errors="coerce").astype("Int64")


def add_id_code_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Add ``*_code`` for scalar prefixed IDs present in a dataframe."""
    result = frame.copy()
    for column, prefix in PREFIXES.items():
        if column in result.columns:
            result[f"{column}_code"] = prefixed_id_to_code(result[column], prefix)
    return result
