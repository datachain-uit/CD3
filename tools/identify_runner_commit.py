#!/usr/bin/env python3
"""Attribute a run to the commits whose runner script has the recorded ``runner_sha256``.

Manifests written before the launcher recorded ``runner_git_commit`` carry only ``lineage.runner_sha256``,
the sha256 of ``tools/vastai_train_shared.py`` as it was when the run started.  Git keeps every version of
that file, so the hash identifies the interval of commits during which the runner had that content, and the
interval tells on which side of the training-loop change (044d6c7, model/shared_phase.py) the run was trained.
This replaces "timestamp before 044d6c7" by a reproducible attribution.

    python tools/identify_runner_commit.py --sha256 <hex or sha256:hex>
    python tools/identify_runner_commit.py --manifest <run_manifest.json | metadata_contract.json>

The output names the commit that introduced the runner content, the first later commit that changed it (if
any), the dates of both, and ``side_of_loop_change`` (before / after / unknown).  A hash that matches no
version of the runner (a local, uncommitted edit) is reported as ``unmatched``: such a run has no reproducible
code identity and must not be ingested as a primary cell.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = "tools/vastai_train_shared.py"
TRAINING_LOOP_CHANGE_COMMIT = "044d6c7"


def _git(*args: str, root: Path = ROOT) -> str:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True, timeout=60).stdout


def runner_hash_history(*, root: Path = ROOT, path: str = RUNNER_PATH, ref: str = "HEAD") -> list[dict]:
    """Every commit of ``ref`` that changed the runner, newest first, with the sha256 of the runner at that commit."""
    lines = _git("log", "--format=%H %cI", ref, "--", path, root=root).splitlines()
    history = []
    for line in lines:
        commit, date = line.split(" ", 1)
        blob = subprocess.run(["git", "-C", str(root), "show", f"{commit}:{path}"], capture_output=True, check=True, timeout=60).stdout
        history.append({"commit": commit, "short": commit[:7], "date": date, "sha256": hashlib.sha256(blob).hexdigest()})
    return history


def _side(commit: str, *, root: Path = ROOT, loop_change: str = TRAINING_LOOP_CHANGE_COMMIT) -> str:
    probe = subprocess.run(["git", "-C", str(root), "merge-base", "--is-ancestor", loop_change, commit], capture_output=True, timeout=60)
    if probe.returncode == 0:
        return "after"
    if probe.returncode == 1:
        return "before"
    return "unknown"


def identify(runner_sha256: str, *, history: list[dict] | None = None, root: Path = ROOT) -> dict:
    """Interval of commits whose runner content hashes to ``runner_sha256``."""
    digest = runner_sha256.strip().lower().removeprefix("sha256:")
    history = runner_hash_history(root=root) if history is None else history
    matches = [index for index, item in enumerate(history) if item["sha256"] == digest]
    if not matches:
        return {"runner_sha256": digest, "status": "unmatched", "introduced_in": None, "superseded_by": None,
                "side_of_loop_change": "unknown"}
    oldest = max(matches)                      # history is newest first; the content was introduced by the oldest match
    newest = min(matches)
    superseded = history[newest - 1] if newest > 0 else None
    introduced = history[oldest]
    side = _side(introduced["commit"], root=root)
    # A runner file can stay unchanged while the shared training loop changes.
    # Its hash alone cannot establish which side of that change ran in that case.
    if side == "before" and (superseded is None or _side(superseded["commit"], root=root) != "before"):
        side = "unknown"
    return {"runner_sha256": digest, "status": "matched",
            "introduced_in": introduced["short"], "introduced_on": introduced["date"],
            "superseded_by": superseded["short"] if superseded else None,
            "superseded_on": superseded["date"] if superseded else None,
            "side_of_loop_change": side,
            "loop_change_commit": TRAINING_LOOP_CHANGE_COMMIT}


def runner_sha256_of(manifest_path: Path) -> str:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    for candidate in (payload.get("lineage", {}).get("runner_sha256"), payload.get("runner_sha256")):
        if candidate:
            return str(candidate)
    raise ValueError(f"{manifest_path} records no runner_sha256")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--sha256", help="runner_sha256 of the run (with or without the sha256: prefix)")
    group.add_argument("--manifest", type=Path, help="run_manifest.json or metadata_contract.json of the run")
    group.add_argument("--table", action="store_true", help="print the sha256 of every committed runner version")
    args = parser.parse_args(argv)
    if args.table:
        print(json.dumps(runner_hash_history(), indent=2))
        return 0
    digest = args.sha256 if args.sha256 else runner_sha256_of(args.manifest)
    result = identify(digest)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "matched" else 1


if __name__ == "__main__":
    raise SystemExit(main())
