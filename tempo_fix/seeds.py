# -*- coding: utf-8 -*-
"""Deterministic seeds and identifiers (PLAN v1.6 §3.1, §3.2), aligned on 2026-10-05 with the
implementation that actually runs (CD3 ``modal_jobs/model_app.py`` @ dff9a3f, ``LO/seeds.py``).

Rules (implemented scheme, replaces the PLAN v1.6 §3.1 text from this revision on)
-----------------------------------------------------------------------------------
* master seeds: ``MASTER_SEEDS = (42, 43, 44)`` (S = 3); policy ``MATCH_MASTER_SEED``.
* role seeds for the trainer (model init, dataloader order) are derived PER CELL so that every
  (task, window, pipeline, model) cell gets independent RNG streams::

      derive_seed(master, role, task, window, pipeline_id, model_name)
        = int(sha256(f"{master}|{role}|{task}|{window}|{pipeline_id}|{model_name}").hexdigest()[:8], 16) % (2**31 - 1)

  The PLAN v1.6 formula H(seed, role) = sha256(f"{seed}:{role}")[:4 bytes] is NOT what the code does;
  it is kept only as ``derive_seed_plan_v1_6`` for provenance of the older registry exports.
* augmentation / sampler seed: the master seed itself (``seed_sampler = seed_augmentation = master``).
  One S2 balanced TRAIN artifact is materialised per master seed and the S3 model cell with master seed
  ``s`` consumes the S2 artifact with the same ``s`` (DECISION_RESPONSE_2026-10-05b, Decision 1).
* preprocessing / imputation seed shared by all master seeds: ``SEED_PREPROCESS = 20260922`` (literal in
  ``LO/seeds.py`` and in the S1 artifact path ``seed=20260922``). The PLAN v1.6 value H(0, "preprocess")
  = 4072383768 was never used by a materialised artifact.
* run_id / meta_obs_id: sha256 of canonical JSON (sorted keys, no whitespace, UTF-8).
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Mapping, Optional

MASTER_SEEDS = (42, 43, 44)
AUGMENTATION_SEED_POLICY = 'MATCH_MASTER_SEED'
SEED_ROLES = ('model', 'dataloader')          # derived per cell
SEED_PREPROCESS = 20260922                     # S1 imputation / S0 profile seed, shared by every master seed
SEED_PREPROCESS_PLAN_V1_6 = None               # filled below; documentation only


def derive_seed_plan_v1_6(master_seed: int, role: str) -> int:
    """PLAN v1.6 §3.1 formula (superseded): first 4 bytes of sha256(f"{seed}:{role}") as unsigned int."""
    digest = hashlib.sha256(f'{int(master_seed)}:{role}'.encode('utf-8')).digest()
    return int.from_bytes(digest[:4], 'big', signed=False)


SEED_PREPROCESS_PLAN_V1_6 = derive_seed_plan_v1_6(0, 'preprocess')


def derive_seed(master_seed: int, role: str, task: str, window: str, pipeline_id: str, model_name: str) -> int:
    """Implemented per-cell role seed (model_app._role_seed): sha256 of "master|role|task|window|pipeline|model",
    first 8 hex digits, modulo 2**31 - 1 (fits torch / numpy seed ranges)."""
    payload = f'{int(master_seed)}|{role}|{task}|{window}|{pipeline_id}|{model_name}'.encode('utf-8')
    return int(hashlib.sha256(payload).hexdigest()[:8], 16) % (2 ** 31 - 1)


def seed_bundle(master_seed: int, task: str, window: str, pipeline_id: str, model_name: str,
                augmentation_seed: Optional[int] = None, has_balancer: bool = True) -> Dict[str, Optional[int]]:
    """All seeds stored in run_manifest for one S3 cell (field names as written by model_app.py).

    ``augmentation_seed`` defaults to the master seed (MATCH_MASTER_SEED). For a pipeline without a balancer
    (V0, V1, V5, V9, V13) ``seed_sampler`` / ``seed_augmentation`` are None, as in the implementation."""
    if augmentation_seed is None:
        augmentation_seed = int(master_seed)
    aug: Optional[int] = int(augmentation_seed) if has_balancer else None
    return {'master_seed': int(master_seed),
            'seed_model': derive_seed(master_seed, 'model', task, window, pipeline_id, model_name),
            'seed_sampler': aug, 'seed_augmentation': aug,
            'seed_dataloader': derive_seed(master_seed, 'dataloader', task, window, pipeline_id, model_name),
            'seed_preprocess': SEED_PREPROCESS}


def canonical_json(obj: Any) -> str:
    """Canonical JSON: sorted keys, no whitespace, non-ASCII preserved (PLAN §3.1)."""
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False, default=str)


def sha256_of(obj: Any) -> str:
    return hashlib.sha256(canonical_json(obj).encode('utf-8')).hexdigest()


RUN_ID_FIELDS = (
    'task', 'feature_regime', 'label_rule_version', 'label_threshold_set', 'window_id', 'seed',
    'augmentation_seed',                       # added 2026-10-05: distinguishes fixed-seed from matched-seed runs
    'model_name', 'pipeline_id', 'hparam_config_id', 'data_release_id', 'split_version',
    'feature_dictionary_version',
)


def run_id(config: Mapping[str, Any]) -> str:
    """run_id = sha256 of the logical configuration (PLAN Table 13, extended in v1.6 with
    feature_dictionary_version and on 2026-10-05 with augmentation_seed). Missing fields raise, so nothing
    is silently defaulted. The CD3 implementation hashes its full config dict (a superset of these fields)."""
    missing = [k for k in RUN_ID_FIELDS if k not in config]
    if missing:
        raise KeyError(f'run_id config is missing fields: {missing}')
    return sha256_of({k: config[k] for k in RUN_ID_FIELDS})


def attempt_id(run_id_value: str, attempt_no: int) -> str:
    return f'{run_id_value}-{int(attempt_no):04d}'


if __name__ == '__main__':  # pragma: no cover
    for s in MASTER_SEEDS:
        print(seed_bundle(s, 'CQ', 'W1', 'V14', 'LSTM'))
