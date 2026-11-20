"""Paths and host settings of the seed 43/44 pipeline scripts, taken from environment variables so that no machine-specific path is committed.

TEMPO_REPO_ROOT   repository root (default: two levels above this file)
TEMPO_WORK_ROOT   working area for downloads, audits, packages and logs (default: <repo>/work)
TEMPO_AUDIT43_ROOT / TEMPO_AUDIT44_ROOT   per-seed audit areas (default: <work>/audit43, <work>/audit44)
TEMPO_SSH_KEY     private key for the rented Vast hosts (default: ~/.ssh/id_vastai)
TEMPO_HOSTS_JSON  JSON file {"<port>": "<ip>", ...} of the rented hosts (default: <work>/hosts.json; keep it out of git)
All values are POSIX-style strings ('/' separators) so that they can be used in f-strings, rclone and ssh commands.
"""
import json
import os
from pathlib import Path

REPO = Path(os.environ.get('TEMPO_REPO_ROOT') or Path(__file__).resolve().parents[2]).as_posix()
WORK = Path(os.environ.get('TEMPO_WORK_ROOT') or (Path(REPO) / 'work')).as_posix()
A43 = Path(os.environ.get('TEMPO_AUDIT43_ROOT') or (Path(WORK) / 'audit43')).as_posix()
A44 = Path(os.environ.get('TEMPO_AUDIT44_ROOT') or (Path(WORK) / 'audit44')).as_posix()
S2 = (Path(WORK) / 's2').as_posix()          # scheduler/orchestrator scripts and logs of the seed 44 run
M43 = (Path(WORK) / 'm43').as_posix()        # seed 43 M-18 / facts scripts and collections
M14C = (Path(WORK) / 'm14c').as_posix()      # inputs of the meta-release assembly
LOM = (Path(WORK) / 'lom').as_posix()        # Mantis code tar and related files
SSH_KEY = Path(os.environ.get('TEMPO_SSH_KEY') or (Path.home() / '.ssh' / 'id_vastai')).as_posix()


def hosts() -> dict:
    p = Path(os.environ.get('TEMPO_HOSTS_JSON') or (Path(WORK) / 'hosts.json'))
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
