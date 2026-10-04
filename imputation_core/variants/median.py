"""V1: training-only median imputation."""

from sklearn.impute import SimpleImputer


def build(*, seed: int):
    del seed
    return SimpleImputer(strategy="median")
