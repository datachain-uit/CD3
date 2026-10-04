"""Immutable model-run configuration shared by CQ and LO."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


Architecture = Literal["rnn", "lstm", "gru", "bilstm"]


@dataclass(frozen=True)
class ModelConfig:
    """Training settings for one task/window/prefix/architecture run.

    ``input_mode=v0_mask`` means V0-imputed features plus the explicit
    availability/missingness masks.  It is an input baseline, not an extra
    label or an augmentation method.
    """

    task: str
    window_id: str
    phase_id: str
    architecture: Architecture
    input_mode: Literal["imputed", "v0_mask"] = "imputed"
    use_masks: bool = False
    train_is_augmented: bool = False
    hidden_size: int = 128
    num_layers: int = 1
    dropout: float = 0.30
    batch_size: int = 2048
    max_epochs: int = 50
    patience: int = 5
    learning_rate: float = 1e-3
    weight_decay: float = 1e-5
    seed: int = 42
    num_workers: int = 4

    def validate(self) -> None:
        if self.task not in {"CQ", "LO"}:
            raise ValueError("task must be CQ or LO")
        if self.window_id not in {"W1", "W2", "W3"}:
            raise ValueError("window_id must be W1, W2 or W3")
        if self.phase_id not in {"P1", "P2", "P3", "P4"}:
            raise ValueError("phase_id must be P1-P4")
        if self.architecture not in {"rnn", "lstm", "gru", "bilstm"}:
            raise ValueError("architecture must be rnn/lstm/gru/bilstm")
        if self.input_mode == "v0_mask" and not self.use_masks:
            raise ValueError("V0_mask must retain availability and missingness masks")

    def as_dict(self) -> dict:
        self.validate()
        return asdict(self)
