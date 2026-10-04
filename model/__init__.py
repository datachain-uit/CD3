"""Phase-safe neural baselines for the CQ and LO meta-datasets."""

from .architectures import HybridRecurrentClassifier
from .config import ModelConfig

__all__ = ("HybridRecurrentClassifier", "ModelConfig")
