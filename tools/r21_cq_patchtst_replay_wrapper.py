"""Label a one-epoch replay without changing the committed runner or its math."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vastai_train_shared as runner

original_parse = runner.parse

def parse_replay():
    args = original_parse()
    if (args.task, args.window, args.pipeline_id, args.model_name, args.seed, args.max_epochs) != (
        "CQ", "W1", "V0", "PATCHTST", 42, 1
    ):
        raise ValueError("This wrapper is restricted to CQ/W1/V0/PATCHTST seed 42, one epoch")
    args.run_purpose = "REPLAY_EQUIVALENCE_1_EPOCH"
    return args

runner.parse = parse_replay
runner.main()
