"""Stage one LO temporal split for train-only imputation."""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_FEATURE_ROOT = next(
    (PROJECT_ROOT / name for name in ("Feature_extraction_LO", "Feature_extraction")
     if (PROJECT_ROOT / name).is_dir()),
    None,
)
if PROJECT_FEATURE_ROOT is None:
    raise ModuleNotFoundError(
        "Cannot find LO feature pipeline folder (expected Feature_extraction_LO or Feature_extraction)."
    )
if str(PROJECT_FEATURE_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_FEATURE_ROOT))

from common.imputation_preparation import main


if __name__ == "__main__":
    main("LO")
