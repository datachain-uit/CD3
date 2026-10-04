"""V5: training-only mean imputation."""

from sklearn.impute import SimpleImputer


def build(*, seed: int):
    del seed
    return SimpleImputer(strategy="mean")
