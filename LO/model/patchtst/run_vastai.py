"""Run LO PatchTST through the shared portable trainer."""
from pathlib import Path
import runpy
import sys

contract = runpy.run_path(str(Path(__file__).with_name("config.py")))["MODEL_CONTRACT"]
root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / "tools"))
sys.argv = [str(root / "tools" / "vastai_train_shared.py"), "--task", contract["task"],
            "--model-name", contract["model_name"], *sys.argv[1:]]
runpy.run_path(str(root / "tools" / "vastai_train_shared.py"), run_name="__main__")
