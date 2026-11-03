from pathlib import Path

from tools.audit_prediction_course_cohort import read_shell_salt, train_path


def test_shell_salt_preserves_cr_and_other_whitespace(monkeypatch):
    monkeypatch.setattr(Path, "read_bytes", lambda _: b" leading secret \r\n\n")
    assert read_shell_salt(Path("salt")) == " leading secret \r"


def test_balanced_pipeline_uses_real_parent_train():
    root = Path("inputs")
    assert train_path(root, "W3", "V4", 42) == root / "train/W3/V1/train.parquet"
    assert train_path(root, "W1", "V6", 42) == root / "train/W1/V5/train.parquet"
    assert train_path(root, "W2", "V0", 42) == root / "train/W2/V0/train.parquet"
