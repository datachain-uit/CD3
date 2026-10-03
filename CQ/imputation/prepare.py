"""Stage one CQ temporal split for train-only imputation."""
import sys
from pathlib import Path

PROJECT_FEATURE_ROOT = Path(__file__).resolve().parents[1] / "Feature_extraction"
if str(PROJECT_FEATURE_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_FEATURE_ROOT))

from common.imputation_preparation import main


if __name__ == "__main__":
    main("CQ")
