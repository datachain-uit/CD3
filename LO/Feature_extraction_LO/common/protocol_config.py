"""Single source of truth for the data/temporal protocol.

``experiment_protocol_config.yaml`` intentionally contains JSON, which is a
valid YAML subset.  Reading it with the standard library keeps the PySpark
jobs runnable on Databricks Serverless without an extra PyYAML dependency.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any


CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "experiment_protocol_config.yaml"


@lru_cache(maxsize=1)
def load_protocol_config() -> dict[str, Any]:
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        config = json.load(handle)

    required = ("version", "output_base", "raw_base", "phases", "paths", "labels")
    missing = [key for key in required if key not in config]
    if missing:
        raise ValueError(f"Protocol config is missing required keys: {', '.join(missing)}")

    # The tracked config intentionally uses portable, relative defaults.  A
    # deployment supplies its storage roots without committing a user/workspace
    # path to Git.
    for key, environment_key in (
        ("output_base", "TEMPO_OUTPUT_BASE"),
        ("raw_base", "TEMPO_RAW_BASE"),
    ):
        config[key] = os.environ.get(environment_key, str(config[key])).rstrip("/")
    return config


def path_from_config(config: dict[str, Any], path_key: str) -> str:
    """Return an absolute Volume path for a configured relative artifact path."""
    try:
        relative_path = config["paths"][path_key]
    except KeyError as error:
        raise KeyError(f"Unknown protocol path key: {path_key}") from error
    if str(relative_path).startswith("/"):
        return str(relative_path).rstrip("/")
    return f"{str(config['output_base']).rstrip('/')}/{str(relative_path).strip('/')}"


def phase_pairs(config: dict[str, Any]) -> tuple[tuple[str, float], ...]:
    return tuple((str(item["phase"]), float(item["ratio"])) for item in config["phases"])
