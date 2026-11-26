# -*- coding: utf-8 -*-
"""metamodel — L3 assembly and L4 meta-model experiments for the CD3 Natural + Temporal Meta-dataset.

Scope (Meta-Dataset-Report v1.9 of 2026-10-24, §3–§5, §9–§10 and Appendix E (input contract and code mapping);
tempo_fix/registries.py rev 2026-10-24):

* ``assemble``   : long L2 facts (family x pipeline x window x phase x split, resources, S0 profiles) ->
                   meta_dataset_seed_level -> meta_dataset_seed_agg, with references, paired effects,
                   decompositions, the recommendation block R and the row-level QA flags.
* ``features``   : column roles (X_STATE / X_CONTEXT / X_VAL / TARGET / ...), nested feature sets FS0–FS5,
                   information scenarios Cold / Warm / Full, train-only preprocessing, checks MQ01/MQ06/MQ10.
* ``baselines``  : B0 oracle, B1 always-V0, B2 global best, B3 best per (model, phase), B4 DQ heuristic,
                   B5 kNN meta-learning, B6 validation selection, B7 TEMPO-DQ diagnosis policy (in contract since 2026-10-24).
* ``learners``   : L1 elastic net, L2 ExtraTrees, L3 LightGBM regression (primary), L4 LambdaRank,
                   L5 3-class classifier, L6 decomposed two-part regression; inner objective = mean regret.
* ``protocols``  : E1-A, E1-B (primary), E2 (cross-task), E3 (cross-tier), W0_LOCKED fallback; MQ02/MQ03/MQ05.
* ``metrics``    : regret, harm, top-1, NDCG@3, gain, gap closure, Kendall agreement, utility regret, Pareto share,
                   cluster bootstrap, Holm.
* ``experiment`` : frozen configuration (sha256), run registry, predictions, recommendations, metric tables.
* ``synthetic``  : SYNTHETIC fixture for tests and dry runs only. Never a source of reported numbers.
* ``verify``     : 0.3.1 — reproduction checks on a delivered run directory (paired bootstrap rows of H1-H4 from stored outcomes).

Nothing in this package produces a number for the paper by itself: every table it writes is traceable to the
input facts through the run registry and the configuration digest.
"""
__version__ = "0.3.1 (2026-11-26)"
