"""Canonical L1/L2 storage contract for phase-safe augmentation."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


BALANCE_PIPELINES = {
    "V2": ("V1", "CDSMOTE"), "V3": ("V1", "SASMOTE"), "V4": ("V1", "RADIUS_SMOTE"),
    "V6": ("V5", "CDSMOTE"), "V7": ("V5", "SASMOTE"), "V8": ("V5", "RADIUS_SMOTE"),
    "V10": ("V9", "CDSMOTE"), "V11": ("V9", "SASMOTE"), "V12": ("V9", "RADIUS_SMOTE"),
    "V14": ("V13", "CDSMOTE"), "V15": ("V13", "SASMOTE"), "V16": ("V13", "RADIUS_SMOTE"),
}


@dataclass(frozen=True)
class BalanceContext:
    """One immutable, single-phase TRAIN-only augmentation attempt."""

    task: str
    feature_regime: str
    window_id: str
    phase_id: str
    pipeline_id: str
    model_name: str
    seed: int
    run_id: str
    attempt_id: str
    cohort: str
    split: str = "TRAIN"
    stage: str = "S2_BALANCED"

    def validate(self) -> None:
        if self.task not in {"CQ", "LO"}:
            raise ValueError("task must be CQ or LO")
        if self.window_id not in {"W1", "W2", "W3"}:
            raise ValueError("window_id must be W1, W2 or W3")
        if self.phase_id not in {"P1", "P2", "P3", "P4"}:
            raise ValueError("augmentation must use one real phase_id P1-P4, never ALL")
        if self.pipeline_id not in BALANCE_PIPELINES:
            raise ValueError(f"{self.pipeline_id} is not an augmentation pipeline")
        if self.split != "TRAIN":
            raise ValueError("augmentation is TRAIN-only")
        if self.stage != "S2_BALANCED":
            raise ValueError("augmentation facts must use stage S2_BALANCED")
        if not self.run_id or not self.attempt_id:
            raise ValueError("run_id and attempt_id are mandatory for immutable storage")

    @property
    def parent_pipeline_id(self) -> str:
        self.validate()
        return BALANCE_PIPELINES[self.pipeline_id][0]

    @property
    def balancer(self) -> str:
        self.validate()
        return BALANCE_PIPELINES[self.pipeline_id][1]


def _run_identity(context: BalanceContext) -> Path:
    context.validate()
    return (Path(f"task={context.task}") /
            f"feature_regime={context.feature_regime}" /
            f"window_id={context.window_id}" /
            f"pipeline_id={context.pipeline_id}" /
            f"model_name={context.model_name}" /
            f"seed={context.seed}" /
            f"run_id={context.run_id}" /
            f"attempt_id={context.attempt_id}")


def l1_attempt_root(meta_root: str | Path, context: BalanceContext) -> Path:
    """Root for immutable artifacts of one balancing attempt."""
    return Path(meta_root) / "L1_runs" / _run_identity(context)


def l1_synthetic_ledger_path(meta_root: str | Path, context: BalanceContext) -> Path:
    """Ledger grain is run_id x synthetic_id; phase is an explicit key."""
    return l1_attempt_root(meta_root, context) / "synthetic_ledger" / f"phase_id={context.phase_id}" / "part-00000.parquet"


def l1_balanced_input_path(meta_root: str | Path, context: BalanceContext) -> Path:
    """Materialized TRAIN input for the downstream model, scoped to one phase."""
    return l1_attempt_root(meta_root, context) / "model_inputs" / "split=TRAIN" / f"phase_id={context.phase_id}" / "balanced_train.parquet"


def l2_fact_path(meta_root: str | Path, fact_name: str, context: BalanceContext) -> Path:
    """Path for a long-format L2 fact partition after balancing."""
    context.validate()
    if not fact_name or "/" in fact_name or "\\" in fact_name:
        raise ValueError("fact_name must be a simple table name")
    partition = (Path(f"task={context.task}") /
                 f"feature_regime={context.feature_regime}" /
                 f"window_id={context.window_id}" /
                 f"pipeline_id={context.pipeline_id}" /
                 f"model_name={context.model_name}" /
                 f"seed={context.seed}" /
                 f"split={context.split}" /
                 f"phase_id={context.phase_id}" /
                 f"cohort={context.cohort}" /
                 f"stage={context.stage}" /
                 f"run_id={context.run_id}" /
                 f"attempt_id={context.attempt_id}")
    return Path(meta_root) / "L2_facts" / fact_name / partition / "part-00000.parquet"
