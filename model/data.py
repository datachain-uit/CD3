"""Leakage-safe conversion of wide imputed rows into P1-P4 model tensors."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset


PHASES = ("P1", "P2", "P3", "P4")
# These are the locked cumulative-prefix cut points.  They are channels, not
# learned from a split, so every architecture receives an explicit notion of
# time even when the same feature value appears at different prefixes.
PHASE_FRACTIONS = (0.25, 0.50, 0.75, 0.90)
PHASE_RE = re.compile(r"^(.*)_P([1-4])$")
IDENTITY_OR_PROVENANCE = {
    "enrollment_id", "offering_id", "window", "split", "synthetic_id",
    "course_id", "user_id", "teacher_id", "school_id",
    "user_id_code", "course_id_code", "teacher_id_code", "school_id_code",
}


def label_column(task: str) -> str:
    return "CQ_label_final" if task == "CQ" else "LO_performance_label_3"


def read_parquet(path: str | Path) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    if frame.empty:
        raise ValueError(f"empty model input: {path}")
    return frame


@dataclass(frozen=True)
class FeatureLayout:
    task: str
    phase_id: str
    dynamic_bases: tuple[str, ...]
    static_columns: tuple[str, ...]
    mask_dynamic_columns: tuple[str, ...]
    mask_static_columns: tuple[str, ...]

    @property
    def phases(self) -> tuple[str, ...]:
        return PHASES[:PHASES.index(self.phase_id) + 1]

    def as_dict(self) -> dict:
        return {
            "task": self.task, "phase_id": self.phase_id,
            "dynamic_bases": list(self.dynamic_bases),
            "static_columns": list(self.static_columns),
            "mask_dynamic_columns": list(self.mask_dynamic_columns),
            "mask_static_columns": list(self.mask_static_columns),
        }


def _is_numeric(frame: pd.DataFrame, column: str) -> bool:
    return column in frame and pd.api.types.is_numeric_dtype(frame[column])


def fit_layout(train: pd.DataFrame, *, task: str, phase_id: str, use_masks: bool) -> FeatureLayout:
    """Learn feature schema from TRAIN only; identities cannot enter tensors."""
    label = label_column(task)
    if label not in train:
        raise ValueError(f"missing model label {label}")
    phase_columns: dict[str, set[str]] = {phase: set() for phase in PHASES}
    for column in train.columns:
        match = PHASE_RE.match(column)
        if not match or column.startswith(("missing__", "phase_available_")):
            continue
        base, phase_number = match.groups()
        phase = f"P{phase_number}"
        if base.endswith("observed_mask") or not _is_numeric(train, column):
            continue
        phase_columns[phase].add(base)
    available_phases = PHASES[:PHASES.index(phase_id) + 1]
    dynamic_bases = tuple(sorted(set.intersection(*(phase_columns[p] for p in available_phases))))
    if not dynamic_bases:
        raise ValueError("no common numeric P1-Pk dynamic features found")

    dynamic_names = {f"{base}_{phase}" for base in dynamic_bases for phase in available_phases}
    excluded = IDENTITY_OR_PROVENANCE | {label} | dynamic_names
    static = []
    for column in train.columns:
        if (column in excluded or column.startswith(("missing__", "phase_available_", "context__"))):
            continue
        if PHASE_RE.match(column) or column.endswith("_observed_mask"):
            continue
        if _is_numeric(train, column):
            static.append(column)
    if not static:
        raise ValueError("no numeric static features found after identity exclusion")

    # V0_mask receives missingness provenance and modality/phase availability.
    mask_dynamic, mask_static = [], []
    if use_masks:
        mask_dynamic = [f"missing__{base}_{phase}" for phase in available_phases for base in dynamic_bases
                        if f"missing__{base}_{phase}" in train]
        mask_static = [c for c in train.columns if c.startswith("missing__") and not PHASE_RE.match(c.removeprefix("missing__"))]
        mask_static += [c for c in train.columns if c.startswith(("phase_available_", "video_observed_mask_", "problem_observed_mask_", "comment_observed_mask_"))]
        mask_static = sorted(set(c for c in mask_static if _is_numeric(train, c)))
    return FeatureLayout(task, phase_id, dynamic_bases, tuple(sorted(static)),
                         tuple(mask_dynamic), tuple(mask_static))


def _numeric(frame: pd.DataFrame, columns: list[str]) -> np.ndarray:
    # Input is already train-fitted scaled output.  A null here signals a
    # broken upstream imputer, so fail rather than silently refit or fill.
    values = frame.loc[:, columns].apply(pd.to_numeric, errors="coerce").to_numpy(dtype="float32")
    if not np.isfinite(values).all():
        raise ValueError("model input contains non-finite numeric values; repair upstream imputation")
    return values


def _phase_lengths(frame: pd.DataFrame, phases: tuple[str, ...]) -> np.ndarray:
    flags = []
    for phase in phases:
        named = f"phase_available_{phase}"
        if named in frame:
            flags.append(pd.to_numeric(frame[named], errors="coerce").fillna(0).to_numpy() > 0)
        else:
            # Train/validation schemas from the canonical release always have
            # the selected prefix. This fallback is only for legacy input.
            flags.append(np.ones(len(frame), dtype=bool))
    lengths = np.asarray(flags, dtype=np.int64).T.sum(axis=1)
    return np.maximum(lengths, 1)


def transform_frame(frame: pd.DataFrame, layout: FeatureLayout, *, classes: tuple[str, ...],
                    use_masks: bool) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    label = label_column(layout.task)
    if label not in frame:
        raise ValueError(f"missing model label {label}")
    phases = layout.phases
    blocks = [_numeric(frame, [f"{base}_{phase}" for base in layout.dynamic_bases]) for phase in phases]
    dynamic = np.stack(blocks, axis=1)
    if use_masks:
        per_phase_masks = []
        for phase in phases:
            columns = [f"missing__{base}_{phase}" for base in layout.dynamic_bases]
            columns = [c for c in columns if c in frame]
            per_phase_masks.append(_numeric(frame, columns) if columns else np.empty((len(frame), 0), dtype="float32"))
        dynamic = np.concatenate((dynamic, np.stack(per_phase_masks, axis=1)), axis=2)
    # Mandatory recurrent-input channels from the V1.6 contract.  ``phase_id``
    # is encoded as its fixed fraction and ``delta_t`` is the elapsed fraction
    # since the previous prefix.  Neither is fit on validation/test data.
    fractions = np.asarray([PHASE_FRACTIONS[PHASES.index(p)] for p in phases], dtype="float32")
    deltas = np.diff(np.concatenate(([0.0], fractions))).astype("float32")
    timing = np.broadcast_to(
        np.stack((fractions, deltas), axis=1)[None, :, :],
        (len(frame), len(phases), 2),
    ).copy()
    dynamic = np.concatenate((dynamic, timing), axis=2)
    static = _numeric(frame, list(layout.static_columns))
    if use_masks and layout.mask_static_columns:
        static = np.concatenate((static, _numeric(frame, list(layout.mask_static_columns))), axis=1)
    labels = frame[label].astype("string")
    mapping = {name: index for index, name in enumerate(classes)}
    unknown = sorted(set(labels.unique()) - set(mapping))
    if unknown:
        raise ValueError(f"labels unseen in TRAIN: {unknown}")
    y = labels.map(mapping).to_numpy(dtype="int64")
    return dynamic, static, _phase_lengths(frame, phases), y


class PhaseDataset(Dataset):
    def __init__(self, dynamic: np.ndarray, static: np.ndarray, lengths: np.ndarray, labels: np.ndarray) -> None:
        self.dynamic = torch.from_numpy(dynamic)
        self.static = torch.from_numpy(static)
        self.lengths = torch.from_numpy(lengths)
        self.labels = torch.from_numpy(labels)

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(self, index: int):
        return self.dynamic[index], self.static[index], self.lengths[index], self.labels[index]
