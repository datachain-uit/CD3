# -*- coding: utf-8 -*-
"""L0 registries required by PLAN v1.6 G0 (§2.3, §2.4, §5.5, §5.6, §6.10, §6.11, §12.3).

Each registry is a plain dict serialisable to YAML/JSON; ``write_registries`` writes them together
with a sha256 manifest so that run_manifest can reference exact versions. Values below are the
v1.6 decisions plus the operational decisions locked between 28/09 and 30/09/2026
(SPLIT_V2_2_OVERALL_CLOSURE, REPORT_LO_V3). Change them here, never inside experiment code.

Revision 2026-11-10 (registries_rev_2026-11-10), on top of 2026-11-09; CD3 @ 193b584 (six commits of 10/11), the team response
PHAN_HOI_REVIEW_YEU_CAU_09-11_2026-11-10 and the Drive deliveries of 09-10/11 (round 27; Ra_soat_tien_do_2026-11-10.md):
  * CODE_REFERENCE          -> 193b584: deterministic leak probe (lbfgs, C 1, tol 1e-4, max_iter 500, one BLAS thread, environment recorded)
                              with the audit assertion --s-leak-reference (default 1e-9); LO r2 recomputation tool; meta-release combiner and
                              acceptance checker; runner-commit inventory, source inventories and byte-level delivery receipts; 34 f3_mantis
                              tests + 6 DedupZstdStore tests + 4 probe tests in tests/; team registry: D-18 objective mapping in METRIC_DEF,
                              MANTIS_V2 row without the PatchTST keys (+ licence, pretraining_data, references); ACELO provenance note.
  * GRID_POLICY             -> execution_status_2026-11-10: M-14 assembled (meta_release_CQ_LO_p1_F2V0V16_20261109, 3,672 seed-level rows,
                              QA six rates 1.0 except the 0.2.1 run-level check); M-15 not run; LO Mantis grid running (no package); phase 2
                              (seeds 43/44) not started.
  * S_SAN_FORMULA v1        -> component_behaviour_2026-11-10: LO r2 copies the LO F1 reference (spread 0, |diff| 0); the three accepted CQ
                              F2/F3 packages keep their own probe fit (|diff| vs the CQ reference up to 4.98e-5 for V0-V6, 1.24e-5 for V7-V16
                              and Mantis); the deterministic probe reproduces the reference to 2.09e-6 across environments -> decision 42.
  * PENDING_DECISIONS       -> 38 (a), 39 (c), 40 (a), 41 (b) EXECUTED by the team before the author's answer (status_2026-11-10; the manifests
                              call them "author decision" - they are recommendations until ratified); 42 (cross-environment s_leak tolerance
                              and reference-copy contract, Q-31) and 43 (retroactive runner-commit mapping and the three NULL Mantis V0 cells,
                              Q-32) new and OPEN; OPEN_AUTHOR_QUESTIONS_2026_11_10 lists Q-27 .. Q-32.
  * POST_MATERIALIZE_CHECKS -> 36 (release half MET), 37 ((b), (h), (i) met; (c)/(d) reported, W1/V0 evidence files not on the Drive), 38
                              (LO r2 PASS at 0; CQ packages at 1.24e-5 / 4.98e-5), 39 (items 1, 2, 5, 6 now met except the V0 Mantis commit),
                              40 (PASS with S0 v4 and Z_M v2) status; 41 (leak-probe reproduction diagnostic per environment) new.
Revision 2026-11-09 (registries_rev_2026-11-09), on top of 2026-11-06; CD3 @ 421dbcd (three commits of 09/11), BAO_CAO_DOI_CHIEU_M01_M18_2026-11-08,
BAO_CAO_PATCHTST_MANTIS_CQ_LO_2026-11-09 and the Drive facts packages of 09/11 (round 26; Ra_soat_tien_do_2026-11-09.md):
  * CODE_REFERENCE          -> 421dbcd: team registry registries_rev_2026-11-08_d32_mantis_local restores MATCH_MASTER_SEED (decision 9 now
                              "CLOSED updated 2026-11-04 D-32"), probability clip 1e-12 float64 (METRIC_DEF v1.3, M-16), mantis_v2 architecture
                              row and RETIRED MOMENT rows; f3_mantis/ byte-identical to the writing-side package 0.1.0 (10 files) but its 34
                              tests are not in the repository; team runner wraps run_cell with a zstd dedup cache store (DedupZstdStore).
  * GRID_POLICY             -> execution_status_2026-11-09: every seed-42 cell of F1 and F2 now exists for both tasks (510 of 1,530 planned
                              primary runs); CQ PatchTST V7-V16 (30 cells, runner 29da3b2) and LO PatchTST V0-V16 (51 cells) complete; CQ
                              MANTIS_V2 V0-V16 (51 cells) as EXPLORATORY; Mantis LO running; seeds 43/44 not started.
  * S_SAN_FORMULA v1        -> component_behaviour_2026-11-09: CQ F2 V7-V16 and F3 Mantis carry the R4 leak probe (max |diff| 1.2e-5); the LO
                              F2 export mixes three probe fits (V14 = LO F1 exactly; eight bundle audits <= 1.1e-3; the 09/11 re-audit of
                              V0-V4, V7, V11, V12 up to 0.0234 at W3) -> decision 38, check 38.
  * PENDING_DECISIONS       -> 32 CLOSED on the code side (check 35 PASS); 36/37 status; 38 (LO F2 leak-probe harmonisation, Q-27), 39 (S0
                              profile conventions of M-13a, Q-28), 40 (meta-tier hand-off and the 14/11 gate, Q-29), 41 (phase-1 use of the
                              complete CQ PatchTST V7-V16 facts, Q-30) new and OPEN.
  * POST_MATERIALIZE_CHECKS -> 31, 35 (PASS), 36, 37 status; 38 (leak-probe reference identity), 39 (F2/F3 facts package completeness), 40
                              (M-13 input acceptance) new.
Revision 2026-11-06 (registries_rev_2026-11-06), on top of 2026-11-04; author instruction of 06/11 (replace MOMENT_SMALL and
MOMENT_BASE by MantisV2 if the model meets the conditions of tier F3 as EXPLORATORY, then update the resources; suitability check
in Huong_dan_doi_code_F3_MantisV2_2026-11-06.docx section 2 and Ra_soat_tien_do_2026-11-06.md); CODE_REFERENCE unchanged at 5872cac:
  * MODEL_REGISTRY          -> MOMENT_SMALL and MOMENT_BASE leave the registry (kept verbatim in RETIRED_MODEL_ROWS, never run into L2);
                              MANTIS_V2 is the single F3 row (EXPLORATORY): paris-noah/MantisV2 @ 8f6ca35, mantis-tsfm 1.1.0, frozen,
                              truncated after transformer layer index 2, output token 'combined', PCA across channels (8 components,
                              standardised, real TRAIN rows), every prefix resized to 512 points, constant-series guard, shared-phase
                              linear probe on cached features (writing-side package f3_mantis 0.1.0, to be integrated by the team).
  * PENDING_DECISIONS       -> 37 new and CLOSED 2026-11-06 (replacement approved under the author instruction after the check; the
                              adapter defaults wait for the author confirmation Q-26); 11 gains update_2026-11-06 (D-11 scope unchanged).
  * POST_MATERIALIZE_CHECKS -> 37 new (F3 MANTIS_V2 acceptance: pin, guard and prefix safety, cost pilot, determinism pilot, adapter,
                              export label, freeze rule); 11 keeps its PatchTST items, its MOMENT items are superseded by 37.
  * AUTHOR_RATIFICATIONS_2026_11_06 (new) -> decision 37.
Revision 2026-11-04 (registries_rev_2026-11-04), on top of 2026-11-03; author replies in the 04/11 writing session
(Ra_soat_tien_do_2026-11-04.md §1; checklist questions Q-01, Q-02, Q-03, Q-05, Q-16 .. Q-19 and the phase-1 scope); CODE_REFERENCE
unchanged at 5872cac:
  * AUTHOR_RATIFICATIONS_2026_11_04 (new) -> decisions 32 (a), 33 (a), 34 (a) signed on 04/11; 35 (a) (energy label of the LO static-v2
                              grid: D-15 unchanged, NVML_POWER_SAMPLING_ESTIMATE 204/204 runs, ENERGY as labelled sensitivity for LO too);
                              36 (phase-1 scope, amends D-N3 (A): seed 42 only, F1 of both tasks and F2 PatchTST CQ V0-V6, meta layer
                              with planned_seeds = [42], M-13/M-14 by 2026-11-09, M-15 by 2026-11-12); D-S1-5, D-S1-8 (b), D-S1-6, Q-05.
  * PENDING_DECISIONS       -> 32-34 closed by ratification (a) (status_2026-11-04); 35 (energy label LO static-v2) and 36 (phase-1 scope)
                              new and CLOSED 2026-11-04; 23 (D-N3 option (c)) points to decision 36.
  * POST_MATERIALIZE_CHECKS -> 35 updated (the four places must read MATCH_MASTER_SEED); 36 new (phase-1 meta layer on seed 42:
                              meta_release manifest, mm_runs, cluster bootstrap B = 2000, Holm).
  * framework name          -> TEMPO-MDS (Temporal Meta-Dataset for intervention Selection), successor of TEMPO-DQ (D-S1-5, Q-01).
Revision 2026-11-03 (registries_rev_2026-11-03), on top of 2026-10-31; CD3 @ 5872cac, BAO_CAO_CQ_PATCHTST_V0_V6_2026-11-02 and the
Drive deliveries of 02-03/11 (round 23); revisions 2026-10-17 .. 2026-10-31 are documented in README.md:
  * AUTHOR_RATIFICATIONS_2026_11_01 / _2026_11_02 (new) -> decisions 17 (a), 20 (a-v2), 23 (a), 24 (b), 26 (a), 27 (a) signed on 01/11;
                              decisions 28-31 (Drive as delivery channel, LO M3^(cal) derived column, static-v2 ablation, Drive sync)
                              signed on 02/11 (Ra_soat_tien_do_2026-11-01.md section 9, Ra_soat_tien_do_2026-11-02.md section 8).
  * CODE_REFERENCE          -> 5872cac: review patch 2026-10-31 adopted (df2a867); 23 new export/audit tools; 68 tests. df2a867 also
                              rewrote EXPERIMENT_SEEDS (FIXED_SEED_42) and closed decision 9 anew without the author -> decision 32;
                              S_SAN_FORMULA s_eff/s_leak text converged on the real-row contract of this file (check 35 (a)).
  * PENDING_DECISIONS       -> 23: V0-V6 executed under (a) (21 cells, one runner 29da3b2) and (a) ratified 01/11; 32 (seed policy),
                              33 (Radius-SMOTE fallback > 0.50 in all 24 class rows), 34 (W1 TEST class good = one offering, 98.85 %).
  * POST_MATERIALIZE_CHECKS -> 31 partly closed from the Drive (hash-verified small files); 32 (calibration convention 1e-7 / 1e-12),
                              33 (report integrity of the 02/11 report), 34 (R4 RNN receipt / T1-EX-07), 35 (seed policy in four places).
Revision 2026-10-15b (registries_rev_2026-10-15b), on top of 2026-10-15; CD3 @ 294a17d and REPORT_LO_V2_EXECUTION_L2_INGESTED (round 13):
  * CODE_REFERENCE          -> ce0486e/23ea1f5/294a17d: VastAI launcher, download/upload scripts, NVML power sampler (ESTIMATE, never
                              pooled with counters), portable audit mirroring the Modal definitions, L2 ingest of 204 LO cells, exporter.
                              Review patch 2026-10-15: resources read from the hash-verified run_manifest (the contract has no
                              resources section), uniform runner/GPU assertion, per-seed grid trees, grain verifier.
  * PENDING_DECISIONS       -> 13: Modal-vs-VastAI equivalence delivered for LO/W1/V0/RNN/seed 42 (probabilities bit-identical);
                              ratification pending. 15: estimates allowed descriptively, never as cost basis mixed with counters.
  * POST_MATERIALIZE_CHECKS -> 15 added (top priority): LO W1/P1 TEST at chance (balanced accuracy 0.334-0.372) while VALIDATION P1
                              is 0.39-0.53; must be explained before any LO W1/P1 claim and before further grids on this protocol.
Revision 2026-10-15 (registries_rev_2026-10-15), on top of 2026-10-14; consolidated execution reports CQ/LO of 2026-10-15 (round 12):
  * CODE_REFERENCE          -> no new commit (origin/main still be110a4 on 2026-10-15); review patch 2026-10-14 not adopted; the repo
                              has no tooling that produces the six audit-fact families from portable (VastAI) outputs although the LO
                              report cites them for 204 cells.
  * PENDING_DECISIONS       -> 13 urgent: LO F1 seed 42 (204 cells) and the F2 pilot ran on VastAI; a Modal-vs-VastAI equivalence test
                              on CQ/W1/V0/RNN/seed 42 is proposed as the gate. 14: pilot A/B repeated at 2048 = 4 x 512 (PASS per
                              report, evidence bundle pending). 15 added: energy/time basis for cells without NVML and W1-primary tables.
  * POST_MATERIALIZE_CHECKS -> 11 updated (PatchTST pilot at the registered configuration); 14 added (promotion conditions for the LO
                              F1 seed-42 VastAI grid); 7 note: CQ LSTM/GRU/BiLSTM absent from the team plan.
Revision 2026-10-14 (registries_rev_2026-10-14), on top of 2026-10-13b; CD3 @ be110a4 reviewed (round 11):
  * CODE_REFERENCE          -> 265415d adopts review patch 2026-10-13b (gradient accumulation, per-seed balanced TRAIN with the
                              MATCH_MASTER_SEED check, epoch timings); be110a4 defers MOMENT_SMALL until the F2 grid completes
                              (TEMPORAL_FAMILY_POLICY: pilot families [PATCHTST], F3 role DEFERRED / AFTER_F2_COMPLETE).
  * PENDING_DECISIONS       -> 14: option (a) implemented in code and README (await ratification; the team registry row lacked the
                              accumulation fields -> review patch 2026-10-14); 11: team text now says F3 after F2; 13 unchanged.
  * POST_MATERIALIZE_CHECKS -> 13: runner-side enforcement adopted; launcher, S2 seeds 43/44 and grid status still to be shown.
Revision 2026-10-13b (registries_rev_2026-10-13b), on top of 2026-10-13; CD3 @ b5f55fe and BAO_CAO_PATCHTST_2026-10-13 (round 10):
  * CODE_REFERENCE          -> b5f55fe adopts review patch 2026-10-13 (scoped math-SDP, VastAI provenance and vocabulary) and adds
                              release_contract_sha256 to the sidecar.
  * PENDING_DECISIONS       -> 14 added: the PatchTST determinism pilot A/B ran with batch 512 (registered batch 2048) on the
                              portable (VastAI) runner; options: gradient accumulation 4 x 512 (review patch 2026-10-13b) or a
                              registered F2-only batch. 13 updated: the F2 grid is being launched on the portable backend before
                              the author decided; the portable tree has no seed dimension for balanced TRAIN (MATCH_MASTER_SEED).
  * POST_MATERIALIZE_CHECKS -> 11 split: PatchTST pilot evidence (checksums equal, batch 512, VastAI) recorded as PARTIAL; 13 added
                              (one S2 artifact per master seed in the portable tree, enforced by the runner after the patch).
Revision 2026-10-13 (registries_rev_2026-10-13), on top of 2026-10-12b; CD3 @ 813e7ea reviewed (round 9):
  * MODEL_REGISTRY          -> team adopted the constant-channel guard (MOMENT revision v2_1, input_encoding v1_1) and the
                              contract/registry alignment; PATCHTST revision patchtst_channel_independent_v2_1_math_sdp (math SDP
                              backend because fused kernels reject B x C sequences; CQ has 274 dynamic channels per the team).
  * PENDING_DECISIONS       -> 11: the F3 subset is now self-consistent (core = five imputers + CDSMOTE + SASMOTE, Radius-SMOTE
                              V4/V8/V12/V16 as labelled sensitivity); still awaiting author ratification. 13 (VastAI backend):
                              README @ 813e7ea describes runner guarantees that tools/ does not implement (patch 2026-10-13).
  * POST_MATERIALIZE_CHECKS -> 11 updated (guard adopted; channel count and F3 cost to be confirmed from feature_layout.json).
  * CODE_REFERENCE          -> commit 813e7ea (2026-10-13); team registry registries_rev_2026-10-12_r5.
Revision 2026-10-12b (registries_rev_2026-10-12b), on top of 2026-10-12; CD3 @ 640be01 reviewed (round 8):
  * MODEL_REGISTRY          -> PATCHTST is now channel-independent (c2856d2 implements decision 12 option (a):
                              shared projection/encoder per channel, post-encoder channel concat in the head;
                              revision patchtst_channel_independent_v2_prefixsafe, verified prefix-safe and channel-independent).
                              MOMENT rows: phase-as-patch encoding adopted verbatim (v2); review patch 2026-10-12b proposes v2_1
                              with a constant-channel guard (RevIN std + 1e-5 amplifies float32 rounding of constant channels).
  * TEMPORAL_FAMILY_POLICY  -> team proposal (640be01) recorded: F2 full grid PRIMARY, F3 MOMENT_SMALL exploratory 13-pipeline
                              subset, MOMENT_BASE deferred, determinism pilot CQ/W1/V0/seed 42 x 2. Awaiting author ratification;
                              the subset lists the four Radius-SMOTE pipelines while declaring Radius sensitivity-only (SASMOTE absent).
  * EXECUTION_BACKENDS (new)-> Modal L4 (registered) and the new portable VastAI runner (tools/vastai_train_shared.py @ c2856d2):
                              second backend without hardware gate, energy measurement or L2 ingestion; LO release vocabulary drifted.
  * PENDING_DECISIONS       -> 12 CLOSED (implemented as (a)); 11 stays OPEN (ratification + subset); 13 added (VastAI backend policy).
  * POST_MATERIALIZE_CHECKS -> 11 updated (determinism pilot as registered by the team, guard, cache still missing); 12 added
                              (Modal-vs-VastAI equivalence before any VastAI cell is used).
  * CODE_REFERENCE          -> commit 640be01 (2026-10-12); team registry registries_rev_2026-10-12_r4 (+ review patch 2026-10-12b -> r5).
Revision 2026-10-12 (registries_rev_2026-10-12), on top of 2026-10-06; F2/F3 backbones reviewed (CD3 @ 548d4d4):
  * MODEL_REGISTRY          -> PATCHTST and MOMENT rows carry the implemented parameters (channel-mixing patch tokens,
                              patch_len 2 / stride 1 / 2 layers / 4 heads; MOMENT-1 pinned revisions, frozen linear probe,
                              phase-as-patch encoding with RevIN-statistics fusion after review patch 2026-10-12).
  * PENDING_DECISIONS       -> 11 (F2/F3 evaluation scope) and 12 (PatchTST channel independence vs naming) OPEN for the authors.
  * POST_MATERIALIZE_CHECKS -> 11 added: F2/F3 acceptance (finite MOMENT embeddings, prefix safety, CUDA determinism of the
                              transformer encoder, cached frozen embeddings before any grid).
  * CODE_REFERENCE          -> commit 548d4d4 (2026-10-11); team registry registries_rev_2026-10-05_r1 (+ review patch 2026-10-12).
Revision 2026-10-06 (registries_rev_2026-10-06), on top of 2026-10-05; no locked parameter changed:
  * CODE_REFERENCE          -> commit c07e02c (06/10/2026); team registry LO/registries.py registries_rev_2026-10-05_r1 (799cf9e)
                              adopted review patch 2026-10-05c: identifiers = RELEASE_SPECS, validate_release_alignment(),
                              PENDING 10 closed, regression tests.
  * METRIC_DEF              -> small_subgroup_flag implementation note closed: metrics_core.classification_metrics now applies the
                              registered rule (n < 30 or any class support < 5) with a regression test.
  * POST_MATERIALIZE_CHECKS -> 9 closed; 10 added: release upload with the materialization_lineage sidecar on the Volume
                              (upload_release.ps1 @ c07e02c plus review patch 2026-10-06: lineage/manifest/_SUCCESS checks,
                              immutable namespace guard, self-describing sidecar).
Revision 2026-10-05 (registries_rev_2026-10-05), on top of 2026-10-01.2; aligned with the CD3 repository at commit
dff9a3f ("Align augmentation seeds with master-seed grid") and with DECISION_RESPONSE_2026-10-05b:
  * MICE_PARAMS / EXTRATREES_PARAMS / BALANCER_PARAMS / COMMON_HPARAMS -> the values of release_core/runtime_config.py
                              (MICE max_iter 3, fit sample 1,000,000 rows; ExtraTrees 1 tree depth 5; CDSMOTE 5 clusters;
                              SASMOTE inspector parameters; Radius-SMOTE fixed radius 0.092 in scaled space; batch 2048,
                              hidden 128, dropout 0.3, weight decay 1e-5, bf16 AMP on L4). PLAN v1.6 starting values superseded.
  * EXPERIMENT_SEEDS (new)  -> master seeds 42/43/44, augmentation policy MATCH_MASTER_SEED (216 S2 runs), per-cell role
                              seeds as implemented in model_app._role_seed, seed_preprocess 20260922 [DEC §1], [SEEDS].
  * GRID_POLICY (new)       -> full F1 grid after the L4 V0/W1 acceptance pilot, no post-pilot shortlist; promotion of results
                              only after Volume-level S0/S1 and grain audits; the 51 legacy LO cells are quarantined [DEC §3].
  * ACCTEMPO_DEF            -> LOCKED 2026-10-05: S_san+ v1 primary, v2/s_cal auxiliary calibration sensitivity only [DEC §2].
  * MODEL_REGISTRY          -> model_revision recurrent_shared_phase_v2_4_prefixsafe_epoch50; per-timestep mask bases
                              (phase_available, *_observed_mask) as dynamic channels; BiLSTM prefix rule; strict determinism.
  * LABEL_ARTIFACTS / SPLIT_REGISTRY -> identifiers exactly as in release_core/contracts.RELEASE_SPECS (CQ_V2_2, LO_V3_1):
                              label_threshold_set CQ_VECTOR_PROXIMITY_PRIMARY_V1 and
                              CATALOG_NORMALIZED_PRIMARY_V3_1__EXCLUDE_NO_SCORED_SIGNAL, split_version v2_2 / v3_1,
                              phase_version wide_prefix_v2_2 / wide_prefix_v3_1; former strings kept as aliases.
  * FEATURE_SOURCE (new)    -> cumulative_phase_features_v2 (wide: one row per enrollment, cumulative columns per phase); v1 had two exact copies
                              (23,614,180 -> 11,807,090 rows) and is forbidden as materializer input [R1_C9].
  * PENDING_DECISIONS       -> 4 closed (2026-10-04), 5 closed (2026-10-05), 9 added and closed (2026-10-05); nothing open.
  * POST_MATERIALIZE_CHECKS -> 5 rewritten for the implemented balancer parameters (Radius fallback-rate warning > 0.50);
                              6-8 added (feature-source grain stop, L4 pilot acceptance, R4 scheduled jobs).
  Sources: [DEC §k] = DECISION_RESPONSE_2026-10-05b.md, [R1_C9] = R1_C9_RUNTIME_EVIDENCE_2026-10-04.md,
  [RESP] = RESPONSE_TO_CODE_REVIEW_2026-10-05.md, [SEEDS] = modal_jobs/model_app.py + LO/seeds.py @ dff9a3f,
  [RT] = release_core/runtime_config.py @ dff9a3f, [REL] = release_core/contracts.py @ dff9a3f.
Revision 2026-10-01.2 (registries_rev_2026-10-01.2), on top of 2026-10-01 (REPORT_LO_V3_1_2 §14-§15):
  * LABEL_ARTIFACTS['LO']  -> catalog-denominator audit recorded (active-catalog hypothesis rejected, V3.1 kept as FINAL),
                              course-ceiling coverage per slice; four problem proxy fields confirmed by physical name.
  * METRIC_DEF v1.2        -> probability metrics for exploratory windows (LO W2), offering-cluster bootstrap for cells with
                              n_offerings_with_class <= 2, course_score_ceiling_observed as report-only context (label-derived).
  * PENDING_DECISIONS      -> 6, 7, 8 closed; POST_MATERIALIZE_CHECKS lists the remaining pipeline checks (not decisions).
Revision 2026-10-01 (registries_rev_2026-10-01), on top of 2026-09-30:
  * LABEL_ARTIFACTS['LO']  -> V3.1: courses without any observed attempt in a weighted assignment/exam component
                              excluded (no_scored_signal_in_course: 102 courses, 172,003 enrollments) [V3.1 §4];
                              cohort 2,605,423 / 711 courses; course score-ceiling table [V3.1 §5]; current-grade group [V3.1 §6].
  * SPLIT_REGISTRY['tasks']['LO'] -> split_version v3_1_scored_signal_excluded, blocks re-paired on the same calendar [V3.1 §8].
  * SAMPLING_STRATEGY      -> LO reference train pools under V3.1 (c0 only changes) [V3.1 §6.1].
  * PENDING_DECISIONS      -> 0, 1, 2, 3 closed (1 and 3 with a remainder); new items 6-8 opened.
Revision 2026-09-30 (registries_rev_2026-09-30):
  * LABEL_ARTIFACTS['LO']  -> catalog-normalised final_score contract V3 (REPORT_LO_V3 §1-§4, §7),
                              sensitivity set TEMPO_LEGACY_CLIP, 19-field label-proxy contract, cohort.
  * SPLIT_REGISTRY         -> shared CQ calendar, per-task split_version (CQ v2.2, LO v3_catalog_normalized),
                              QA22 as locked (label-end order + non-empty arms), two overlap metrics,
                              long-offering decision (keep units, context flags).
  * METRIC_DEF v1.1        -> cell-level small_support_flag (< 400), small_subgroup_flag kept, CLASS_ABSENT,
                              bootstrap / paired-bootstrap policy, checkpoint rule, prediction-level context columns.
  * SAMPLING_STRATEGY      -> unchanged IR10_K10; reference train-pool counts under LO V3 added (cap binds).
  * PENDING_DECISIONS      -> items still open on 2026-09-30; nothing in them is to be treated as locked.
Sources are tagged [CL §k] = REPORT_SPLIT_V2_2_OVERALL_CLOSURE_2026-09-30, [V3 §k] = REPORT_LO_V3 (30/09/2026),
[LO §k] = REPORT_LO_V2.2 (30/09/2026), [V3.1 §k] = REPORT_LO_V3_1 (01/10/2026), [V3.1.2 §k] = REPORT_LO_V3_1_2 (01/10/2026, adds §14-§15),
[PLAN §k] = Mo_ta_meta-dataset_v1.6.
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

from .seeds import (sha256_of, SEED_PREPROCESS, SEED_PREPROCESS_PLAN_V1_6, MASTER_SEEDS, AUGMENTATION_SEED_POLICY)

REGISTRY_REVISION = 'registries_rev_2026-11-26b'
CODE_REFERENCE = {'repository': 'https://github.com/datachain-uit/CD3', 'commit': 'acd11c1',
                  'review_2026-11-26b': {'checked_on': '2026-11-26 (second pass)', 'origin': 'origin/main at acd11c1, unchanged since the first pass of 26/11 (110 commits, 858 files)', 'public_release_state': ['the repository page is served without sign-in; no licence, no release, no description (read on the page, 26/11)', 'the analysis package is not in the repository: no metamodel/ and no tempo_fix/ directory (only the driver tools/subgroups_phaseB/run_metamodel_single_core.py, which runs the package from the hand-off folder); the meta-dataset release and the ten run directories of phase C are on the Drive of the team, not in the repository', 'no LICENSE and no CITATION file; largest tracked file 454,589 bytes', 'docs/ holds 8 files of internal reports and replies of the team in a public repository; whether they stay public is a decision of the author', 'release tables: meta_dataset_seed_agg.parquet 164,712,412 bytes (157.1 MiB), meta_dataset_seed_level.parquet 88,784,875 bytes (84.7 MiB); warning above 50 MiB, files above 100 MiB blocked in a regular repository (GitHub Docs, About large files on GitHub, read 26/11)'], 'asked_of_the_team': 'request of 26/11 (second pass), part C: commit of metamodel 0.3.1 and tempo_fix, release assets, review before publication; licence, tag and the fate of docs/ wait for the author'},
                  'review_2026-11-26': {'checked_on': '2026-11-26', 'origin': 'origin/main at acd11c1ec6671105675e33720cfbddf5dc3e7a14 (commit of 2026-11-24T18:36:53+07:00); 1 commit since ecad59d: 3 files changed, 123 insertions(+)', 'verdict': 'the commit adds the three scripts of phase C asked for on 24/11 under tools/subgroups_phaseB/ (run_phasec_r2_controller_20261123.py, finalize_phasec_r2_20261124.py, verify_phasec_parts_20261124.py); nothing else changes; static reading, nothing of the repository was run', 'notes': ["driver (tools/subgroups_phaseB/run_phasec_r2_controller_20261123.py, sha256 of the repository version 2386e986380b...): it checks the hand-off tree and the ten digests before the first run and writes the line 'PREFLIGHT PASS' found in progress.log of the delivery, sets the thread variables of the numerical libraries to 1 and launches each configuration through run_metamodel_single_core.py; this closes the item 'driver of phase C not in the repository' of 24/11", 'the reply of the team of 24/11 states that the versions of the three scripts that were run are not byte-identical to the committed ones and gives their sha256; the configurations run are identified by their digests, as before, and not by the driver', 'the script of the dtype-preserved negative control (code/mq08_dtype_preserved_12fold_20261124.py of the evidence folder) is not in the repository']},
                  'commits_reviewed_2026-11-26': ['acd11c1 (2026-11-24 18:36) Add phase C execution and delivery tooling'],
                  'resolved_since_2026-11-24': ['the driver of phase C, the QA and packaging script and the verification script of the split files are in origin/main at acd11c1'],
                  'not_in_repository_2026-11-26': ['the script of the dtype-preserved negative control and the table of its 115 folds over the ten configurations (evidence of the MQ08 finding of 24/11)'],
                  'review_2026-11-24': {'checked_on': '2026-11-24', 'origin': 'origin/main at ecad59d7ea81bf2f21fb8ad00954409ac93b5f92 (commit of 2026-11-23 17:30:33 +0700); 6 commits since fc361b6: 24 files changed, 1831 insertions(+), 51 deletions(-)', 'verdict': 'the commits add tools and one reply document: 24 files (docs/ 2, tools/ 22); no file under model/, metrics_core/, f3_mantis/, imputation_core/, augmentation_core/, tempo_core/, release_core/, tests/, CQ/, LO/ or modal_jobs/; the 22 Python files changed compile; static reading, nothing of the repository was run; no test was added', 'notes': ['builder of the 36 unit packages of phase B (tools/subgroups_phaseB/build_subgroup_facts.py): the sha256 recorded in 27 summary.json (249132bbd023...) is the file at commits e0da303 and e182a6f; these summaries name repo_commit d19fb122b795, at which the file still has the sha256 of fc361b6 (a8d0e7f2c853...): the 27 units were produced by a working copy that was committed afterwards, so they are traced by the sha256 of the file and not by the commit they name; the sha256 recorded in the 9 summaries of seed 42 (c3da76a6973f...) is the file at b13e1b9 and ecad59d', "difference between the two builder versions (e182a6f -> b13e1b9; 1 file changed, 38 insertions(+), 2 deletions(-)): legacy_cols() added and used only when the accepted facts carry the older column names (LEGACY = 'f1_macro' in the fact columns); REPORT_ONLY widened from two to six metrics; COPY_COLS extended by the probe_* / s_leak* / calibration_bins columns present in the facts; the ALL-row check extended to array columns; metric_row() unchanged; the computed values of the 27 units do not depend on it, so the fifth builder amendment asked on 21/11 (one builder commit for the 36 units) is closed without regenerating a unit", 'the three copies delivered in code_provenance/ on 23/11 against the repository: infer_s0_hour_histogram_bins.py identical; assemble_release_5subgroups_20261122.py (3 lines replaced by 3) and compute_s0_v5_eval_jsd.py (1 by 2) differ only in lines where a machine path is replaced by an environment variable', 'S0 profile v5 and its dtype-fixed re-issue: tools/subgroups_phaseB/assemble_s0_v5.py (the dtype of every column is set to that of the v4 reference before writing; output folder taken from the first argument); the six compute_s0_v5_eval_*.py, infer_s0_hour_histogram_bins.py, preflight_s0_v5.py, check_s0_jsd_hour_parity.py and verify_s0_v5_subgroup_packages.py are present', 'B.5: tools/subgroups_phaseB/run_b5_then_phasec.py (release id from TEMPO_5SUBGROUP_RELEASE_ID, TEMPO_B5_ONLY=1 stops after B.5; its phase C branch reads the r1 file phaseC_frozen_configurations.json and writes other log lines than the delivered progress.log); run_metamodel_single_core.py and prepare_b5_dtype_diagnostic.py are present; A.9: tools/m15_3seed/verify_m18_vs_facts_seed44.py is present', 'mm_run_registry.code_commit of the ten runs of phase C is ecad59d7ea81bf2f21fb8ad00954409ac93b5f92, the head of origin/main', 'two commits of 21/11 (f4e6de5, d19fb12) change the reply document of 21/11 (docs/21112026/PHAN_HOI_YEU_CAU_20-11_BAN2_2026-11-21.docx; docs/21112026/PHAN_HOI_YEU_CAU_20-11_BAN2_2026-11-21.md); by their subjects section 11 describes the exploratory per-task run without its regret or hypothesis results and A.3 copies tables of the three-seed report; the writing side did not open that document in this round']},
                  'commits_reviewed_2026-11-24': ['f4e6de5 (2026-11-21 08:38) Reply 20/11 (version 2): section 11 now describes the exploratory per-task E1 run (method, completion table, location) without its regret or hypothesis results', 'd19fb12 (2026-11-21 08:40) Reply 20/11 (version 2), A.3: results of the re-run (regret tables and H1-H8) copied from the three-seed report', 'e0da303 (2026-11-22 08:34) Phase B: builder with per-file salt detection and all-column ALL check, unit runner with source ranking, finish_unit, driver; extras (end-date spread, 48-row cr', 'e182a6f (2026-11-22 08:34) Phase B: temp folder of the unit runner taken from the work root (no machine-specific path)', 'b13e1b9 (2026-11-22 08:40) Phase B builder: columns of the older fact schema (accuracy, f1_weighted, per_class_*, roc_auc_macro_ovr, strict shares) recomputed on each slice for the R4 and', 'ecad59d (2026-11-23 17:30) Add phase B subgroup release and verification tools'],
                  'not_in_repository_2026-11-24': ["the driver that launched the ten runs of phase C on release r2: progress.log carries the lines 'PREFLIGHT PASS: ten approved digests and metamodel tree verified', 'BATCH START PRIMARY', 'BATCH PASS VARIANTS' and 'PHASE_C_ALL_COMPLETE; packaging and QA required', which neither run_phaseC_r2.sh of the hand-off of 23/11 nor tools/subgroups_phaseB/run_b5_then_phasec.py writes; the configurations run are identified by their digests (--expect-digest values equal to the frozen ones), not by the driver", 'the script that wrote qa_phaseC_20261124.json (status PASS_STRUCTURAL)', 'the script that split the 28 CSV files above 10 MB into 74 parts (large_file_parts/parts_manifest.json)'],
                  'resolved_since_2026-11-23': ['the local history is pushed: d19fb122b795 and b13e1b963092 exist in origin and both builder versions are found by their sha256', 'the scripts of the S0 profile v5, of its dtype fix and of the 240-row assembly', 'assemble_release_5subgroups_20261122.py and the driver of B.5 with the two diagnostic runs', 'tools/m15_3seed/verify_m18_vs_facts_seed44.py'],
                  'review_2026-11-23': {'checked_on': '2026-11-23', 'origin': 'git ls-remote origin lists HEAD and refs/heads/main only, both at fc361b651208102796c6d4b80a9fd7170d2c1632 (commit of 2026-11-21 08:35:30 +0700); no commit, branch or tag has been pushed since the review of 21/11, although the request of 23/11 states that the code changes are on GitHub', 'not_in_repository': ['the two versions of tools/subgroups_phaseB/build_subgroup_facts.py that produced the 36 unit packages of phase B: sha256 249132bbd023... (27 units, local commit d19fb122b795) and c3da76a6973f... (9 units of seed 42, local commit b13e1b963092); the file at origin/main has sha256 a8d0e7f2c853...; neither local commit exists in origin', 'build_seen_flags.py and build_support_table.py at origin/main carry the sha256 recorded in the 36 summary.json files (unchanged since 21/11)', 'the builder of the S0 profile v5 and its dtype-fixed re-issue (evaluation-slice tables eval_time, eval_masks, eval_zero, eval_overlap, eval_psi, eval_jsd and the 240-row table) is not delivered; three scripts are delivered as copies in the Drive folder code_provenance/ only: assemble_release_5subgroups_20261122.py, compute_s0_v5_eval_jsd.py, infer_s0_hour_histogram_bins.py', 'the driver of the six ALL-only runs of step B.5 and of the two diagnostic runs is not delivered; mm_run_registry.code_commit of B.5 r2 is b13e1b963092be5d0ca68118f178632473e2f31c, a commit that is not in origin'], 'delivered_copies_read_by_the_writing_side': ['assemble_release_5subgroups_20261122.py: runs `metamodel.cli assemble` of the hand-off of 21/11 once per task (accepted fact packages plus the 18 unit tables of the task, resources, S0 profile, model context, F0 for CQ) with --require-subgroups and --compare-all-with, stops on a non-zero exit code or on subgroup_report.ok false, concatenates the two child tables, writes list-valued object columns as JSON text, splits the seed-level table into 30 parts (task x subgroup x seed) and checks that the parts rebuild it exactly; the release id is restricted to ..._5subgroups_r1 and ..._5subgroups_r2', 'compute_s0_v5_eval_jsd.py: TRAIN-versus-evaluation Jensen-Shannon divergence per feature on the histogram bins stored in the S0 distribution sketch, by subgroup, mean over features; refuses to write unless the ALL slice reproduces v4 within 1e-10', 'infer_s0_hour_histogram_bins.py: mapping hour -> bin of most_common_hour_sin found by integer programming from the eight stored ALL histograms of a task and window (4 phases x VALIDATION / TEST), candidates restricted to the bins of the sine value and of its three floating-point neighbours on each side; an hour that is observed and admits a second exact solution makes the script stop; the mapping is a function of the hour only, and a subgroup is a subset of the ALL population, so the subgroup histograms follow from it'], 'asked_2026-11-23': 'push the local history (at least the commits d19fb122b795 and b13e1b963092 and the scripts listed above) to origin/main; the writing side then compares the two builder versions and the three delivered copies with the repository'},
                  'commits_reviewed_2026-11-21': ['8494886 (21/11 08:26) review of 20/11, version 2: the scripts missing from the repository (phaseB_orch.py, the two Mantis CQ seed-44 launchers, the M-18 repair scripts, the three-seed M-15 scripts run_local_all_1t.sh / m15_run_logged.py / run_six_mm026.sh / run_e1_per_task.sh, scan_release_ids.py, verify_err_tars.py, the assemble energy-fix patch of release 20261120, the n_jobs=1 patch of the other session, the report builders, combine_meta_release_3seed_mm026.py), the phase B builders (tools/subgroups_phaseB: build_seen_flags.py, build_support_table.py, build_subgroup_facts.py, build_pred_catalog.py, scan_predictions.py) and the reply of 21/11 (docs/21112026); machine paths replaced by environment variables', 'f6cefe7 (21/11 08:30) build_energy_proposal_seed44.py rebuilt from the method description of the delivered folder (the original script is lost); reproduces the delivered CSV to within 0.001 kWh', '35e806e (21/11 08:32) reply of 21/11, item A.7.7 rewritten', 'fc361b6 (21/11 08:35) three-seed report of 20/11: M-15 and meta-dataset sections updated to the metamodel 0.2.6 release and re-run (docs/20112026 with 13 tables)'],
                  'review_2026-11-21': {'verdict': 'the four commits add scripts, builders and documents only: 42 files, all under tools/ and docs/; model/, metrics_core/, f3_mantis/, imputation_core/, augmentation_core/ and tests/ are unchanged since 6274591; every new Python file compiles; no test was added', 'notes': ['the eight items listed as not in the repository on 20/11 are present; item 7 (energy proposal of seed 44) is a rebuilt script that reproduces the delivered values to within 0.001 kWh, the original being lost', 'tools/m15_3seed/m15_run_logged.py wraps metamodel.experiment._learner_cell and _negative_control to print progress and returns their results unchanged; the five configurations that do not use energy reproduce the earlier pc_one_thread set exactly, which is the evidence that the wrapper changes nothing; metamodel 0.3.0 has `run --progress`, so the wrapper is not needed any more', 'tools/subgroups_phaseB/build_seen_flags.py implements seen_v1_train_partition_only on the TRAIN partition of the window with the cutoff of the phase view; offering_end_date is derived per enrollment as enroll_time + (cutoff_time_P4 - enroll_time) / 0.90, and the phases P1-P3 give the same date to within 3 s; one CQ offering of 3,309 and one LO offering of 2,169 have an end-date spread above 60 s', 'tools/subgroups_phaseB/build_subgroup_facts.py recomputes the ALL row of every (run, split, phase) and compares it with the accepted facts on eight columns (macro_f1, s_perf, s_san_plus_v2, s_drift, s_nan, s_maj_jsd, s_cal, acctempo_m3); log_loss, brier and the per-class columns are outside that self-check', 'the copies of the three builders in the pilot folder on Drive differ from the committed files only in the paths (absolute machine paths against environment variables)', "tools/m15_3seed/run_e1_per_task.sh is the script of the exploratory per-task run declared by the team (GRID_POLICY['execution_status_2026-11-21']['exploratory_run'])"], 'open': ['scan output of the M-08 ledger (per manifest: path, data_release_id, class) is not in the repository or on Drive; the confirmation of item A.8 is a statement of the reply', 'output of verify_err_tars.py (two truncated archives) is not delivered as a file', 'cell-by-cell reconciliation of the six seed-44 fact packages with the archives used to build M-18: not done (stated by the team)', 'pip freeze of the Linux host 17429 is lost (machine deleted); only the Python version survives in m15_progress_17429.log']},
                  'subgroup_tooling_2026-11-20b': {'reviewed_for': 'what the repository at 6274591 holds for the five mandatory subgroups (decision 51 (b)); static reading, nothing was run', 'findings': ['tools/vastai_audit_shared.py _slice_rows computes the slices ALL, STRICT and OVERLAP of every run, split and phase from predictions/{validation|test}_{phase}.parquet (y_true, prob_c0, prob_c1, prob_c2, temporal_strict_{phase}) with metrics_core.evaluation.classification_metrics; s_eff is the value of the run and s_leak the canonical value of the (window, parent pipeline, split, phase) cell, passed in unchanged for every slice; STRICT + OVERLAP = ALL is asserted on the confusion matrices', 'tools/audit_prediction_course_cohort.py joins the predictions to course_id through the private prediction salt and writes the joint slices SEEN_COURSE / UNSEEN_COURSE x STRICT / OVERLAP with n_eval, macro_f1, balanced_accuracy and the class supports (96 rows per pipeline); SEEN_COURSE = the course_id occurs in the real parent TRAIN of the window, without the cutoff condition of Table 10', "no LEARNER slice, no marginal COURSE slice with the full metric set, no S0 profile row and no F0 row by subgroup, and no job for the five mandatory subgroups (Appendix D of the Meta-Dataset-Report lists 'subgroup with STRICT/OVERLAP' among the five R4 jobs due before the result tables)"], 'consequence': 'the subgroup facts are an extension of _slice_rows with four masks built from seen flags; the flags need user_id and course_id of every evaluated enrollment, its cutoff at each phase and the TRAIN partition of the window; nothing is trained and no inference is run'},
                  'commits_reviewed_2026-11-20': ['7c24981 (19/11) seed 43/44 facts pipeline: build_facts_package_mantis_lo_20261109.py gains --seed, --kind patchtst, --task, --model and writes the seed into the README title; vastai_audit_shared.py gains --skip-probe-refit (canonical_s_leak built straight from the reference table, probe_seed = 42 = seed of the reference fit, s_leak_source = REFERENCE_TABLE_COPY_NO_REFIT); build_sleak_reference_seed_20261115.py; Mantis runner-evidence builders for seed 43 (--task, --inventory) and seed 44; build_seed43_receipts_20261116.py; tools/seed43_44_pipeline/ (24 scripts: audit, facts, finalize, M-18, orchestration)', '11941f1 (19/11) build_seed44_receipts_20261119.py (delivery + L2 ingest), fix44_packages_v2.py (README title, single r2 section, probe_seed = 42, builder commit recorded; the verified originals kept in fact_exports_superseded_20261119), m44_build_m18.py, resync_staging44.sh', '6274591 (20/11) machine-specific absolute paths replaced by environment variables (tools/seed43_44_pipeline/tempo_paths.py, hosts.example.json); combine_meta_release_3seed_20261119.py and _20261120.py (row-wise concatenation of the CQ and LO child releases, merged column dictionary, manifest with the sha256 of every input, RUN_LOG, sha256sums)'],
                  'review_2026-11-20': {'verdict': 'the three commits (19-20/11) carry the tooling asked for on 16/11 (item 1): the six seed-43 and the six seed-44 facts packages can now be rebuilt from the repository apart from the files listed in not_in_repository_2026-11-20; every change is under tools/ (36 files, +3,275 lines); model/, metrics_core/, imputation_core/, augmentation_core/, tempo_core/, release_core/, f3_mantis/, tests/, CQ/, LO/, modal_jobs/ and config/ have the same tree hash as at cb575df, so the training core is untouched; static review, no test of the repository was run; no test was added', 'notes': ['the seed-44 cells were trained with the runner at 5ba9829 (F1 and PatchTST, commit written at run time) and audited with --s-leak-source copy-reference --skip-probe-refit: s_leak equals the registered reference exactly (check 44)', 'the builder commit recorded in the seed-44 packages (7c24981) was made after the packages were built (created 18-19/11, commit 19/11 08:56 UTC) and written in afterwards by fix44_packages_v2.py', 'the M-18 scripts shipped inside m18_training_history_seed44_20261119 on the Drive are the _repair variants (absolute Windows paths, an expected-cell assertion, a different rule for truncated archives); they differ from tools/seed43_44_pipeline/m44_stream.py and m44_build_m18.py', 'LO/registries.py still says REGISTRY_REVISION = registries_rev_2026-11-10_d18_mantis_clean; the meta-release manifest records the reference export registries_rev_2026-11-16 (sha256 96b5c1e4...) as asked']},
                  'not_in_repository_2026-11-20': ['phaseB_orch.py (imported by tools/seed43_44_pipeline/cq_workers44.py and lo_workers44.py, which therefore cannot be imported from origin/main)', 'cq44_mantis_parent.sh and cq44_mantis_child.sh (host-side scripts called by cq_workers44.py)', 'report_aggregate_3seed.py (named in the 20/11 report as the source of every table of its sections 2 and 3.2)', 'run_assemble_3seed.sh (named in the RUN_LOG of the three-seed release)', "the locally patched metamodel/assemble.py used for the LO half of release 20261120 (the RUN_LOG says 'copy in this package'; the Drive folder holds no copy; builder_version still reads metamodel 0.2.4)", 'the launch scripts of the three-seed M-15 runs (one process per configuration, thread caps by environment variables) and the n_jobs=1 patch of the other session named in PROVENANCE.txt', 'the script behind energy_proposal_seed44_20261119', 'm44_stream_repair.py and m44_build_m18_repair.py (shipped in the M-18 seed-44 package only)'],
                  'resolved_since_2026-11-16': ['the five uncommitted tools of 16/11 (--skip-probe-refit, build_sleak_reference_seed_20261115.py, --seed/--kind patchtst/--model, --task/--inventory, m43_stream.py and m43_build_m18.py) are in 7c24981',
                                                'README title and probe_seed corrected from the seed-44 packages on (seed 43 documented in seed43_package_notes_20261120, no re-export)'],
                  'commits_reviewed_2026-11-16': [
                      '2152d49 request 2026-11-13 items 1.1/1.2: vastai_audit_shared.py --s-leak-source copy-reference (default) copies the registered s_leak into canonical_s_leak (s_leak_probe_auc = 1 - s_leak/2), keeps the refit as s_leak_refit* diagnostics, records probe_mode and probe_threads in the audit manifest; probe_environment() lists the thread pools again; vastai_run_f1_grid_20261110.sh exits 2 without S_LEAK_REFERENCE; Q-32 labels in the L2 ingest receipts; test tests/test_audit_s_leak_copy_reference_20261113.py',
                      '3eb7bc0 M-15 full42 packaging tool; receipts include the full42 and p1 packages',
                      '293c43a Q-28 wording: ratified by the author on 2026-11-13 in the builders; receipts rebuilt',
                      'f9dd908 probe reproduction check: tolerance 1e-3 (check 41, Q-31 a) and the probe mode of each run in the report',
                      'cb575df reply to the 13/11 request (batch 28): docs/13112026/PHAN_HOI_YEU_CAU_13-11_2026-11-13.md + .docx'],
                  'review_2026-11-16': {
                      'verdict': 'the five commits (all of 13/11) implement items 1.1 and 1.2 of the 13/11 request and the Q-28/Q-31/Q-32 wording; no commit touches the training core; static review, no test of the repository was run; the seed-43 runs were trained with the runner at 5ba9829 (10/11) and audited afterwards with the 2152d49 audit in COPY_REFERENCE mode',
                      'notes': [
                          'apply_reference_s_leak() recomputes S_san+ v1/v2, M3 and M4 from the copied s_leak (verified on the exported facts: formulas reproduce to 1.2e-15)',
                          'the facts of the seed-43 packages carry probe_seed = 43 although the probe was not refit (probe_fit_rows_source = REFERENCE_PROBE_FIT_SEED42_SAME_REAL_DATA): documentation inconsistency, no numeric effect',
                          'the 15-16/11 tooling (build_sleak_reference_seed_20261115.py, --skip-probe-refit, --seed/--kind patchtst/--model of build_facts_package_mantis_lo_20261109.py, --task/--inventory of build_mantis_seed43_runner_evidence_20261112.py, m43_stream.py, m43_build_m18.py) is not committed: the six seed-43 packages cannot be rebuilt from origin/main']},
                  'uncommitted_tools_2026-11-16': ['tools/vastai_audit_shared.py --skip-probe-refit', 'tools/build_sleak_reference_seed_20261115.py',
                                                   'tools/build_facts_package_mantis_lo_20261109.py --seed/--kind patchtst/--model', 'tools/build_mantis_seed43_runner_evidence_20261112.py --task/--inventory',
                                                   'm43_stream.py and m43_build_m18.py (shipped inside m18_training_history_seed43_20261116 on the Drive)'],
                  'commits_reviewed_2026-11-13': [
                      '18d00fe tools/vastai_run_s2_augmentation.py: one S2 cell outside Modal; run_augmentation taken from modal_jobs/augmentation_app.py by AST (not re-implemented); environment sidecar; resource_summary keeps the values hard-coded in the Modal runner',
                      '5ba9829 tools/recompute_cq_sleak_20261110.py: decision 42 option (a) applied to the three CQ packages (s_leak copied from the reference, four columns recomputed, r2_changes.csv); wording of pending author decisions',
                      '238c7d4 tools/build_s2_sampling_artefacts_20261110.py: plan, run summary, ledger inventory, kappa_reached and Radius fallback of one master seed from the 72 run manifests',
                      'd735cea tools/vastai_run_f1_grid_20261110.sh: F1 grid of one task and seed; vastai_train_shared.py writes runner_git_commit at run time; the family audit passes --s-leak-reference only when S_LEAK_REFERENCE is set and never --s-leak-tolerance (default 1e-9) while the audit probe is single-threaded',
                      'fcabc19 LO Mantis: mantis_standardize_runs_20261110.py, run_lo_mantis_audit_pipeline_20261110.py (--s-leak-tolerance default 1e-3), build_facts_package --kind lo_mantis',
                      '78b4100 metrics_core/evaluation.py probe_environment(): thread-pool listing dropped, library versions and platform kept; test updated',
                      'af59411 tools/compare_pilot_det_20261109.py: cache manifest.json (created_at_utc) excluded from the determinism claim, exclusions listed',
                      '2b17334 request 2026-11-10 items 4.1-4.3: ratification wording in builders and evidence, C3 script writes the v0_cells dict and counts hosts from data, REGISTRY_REVISION = registries_rev_2026-11-10_d18_mantis_clean',
                      '46a04ef tools/build_delivery_receipts_20261112.py and the reply of 12/11',
                      '8eada42 reply 12/11: default (multi-thread) probe mode and the deterministic-mode differences',
                      'f4310ca tools/build_mantis_seed43_runner_evidence_20261112.py (Mantis CQ seed-43 cells carry no runner commit: retroactive mapping again) and verify_mantis_zstd_cache_fixed_20261108.py',
                      '3b09db3 tools/build_m15_package_20261113.py (RUN_LOG, pip freeze, sha256sums, supported lists)',
                      'e2583c5 reply 12/11: M-15 p1 delivered; proposal on library versions',
                      'a777ee1 tools/build_l2_ingest_receipts_20261113.py: placement, byte identity and checkable ingest conditions of nine packages',
                      '7cad8b1 reply to the 10/11 request as .docx (status 13/11), sha256 da42b927...5f01'],
                  'review_2026-11-13': {
                      'verdict': 'the fifteen commits are tooling and records; no commit changes the training core; items 4.1-4.3 of the 10/11 request are closed (static review, no test of the repository was run)',
                      'notes': [
                          'F1 grid audit: single-thread probe + default tolerance 1e-9 against a reference produced in the default multi-thread mode (team report: single-thread differs by 2.1e-5 at CQ W1 and up to 9.6e-4 at LO W2) -> assert_s_leak_matches_reference stops the audit before the facts are written; the LO Mantis pipeline already had to use 1e-3',
                          'probe_environment() no longer records the thread pools although the thread mode is what moves the probe',
                          'Mantis CQ seed-43 cells were run from a code tar without a run-time commit, against the phase-2 gate stated on 2026-11-10',
                          'S2 outside Modal keeps the Modal hard-coded resource fields: S2 cost of seeds 43/44 is not comparable with seed 42 until the real host is recorded',
                          'the reply of 10/11 (2.09e-6, thread independent) and the probe README of 12/11 (2.1e-5 single thread, 0.0 multi-thread) disagree']},
                  'team_registry_revision_2026-11-13': 'registries_rev_2026-11-10_d18_mantis_clean in LO/registries.py @ 7cad8b1 (2b17334); export registry_export_repo_20261110 on the Drive, not compared',
                  'not_copied_2026-11-13': 'the Drive is not reachable from the writing-side machines in this session; only six mm_hypotheses.csv were rebuilt and hash-matched; see input/results/_pending_drive_packages_2026-11-13.json',
                  'commit_subject': 'Add phase C execution and delivery tooling', 'commit_full': 'acd11c1ec6671105675e33720cfbddf5dc3e7a14', 'checked_on': '2026-11-26',
                  'previous_reference': 'ecad59d (checked 2026-11-24)', 'previous_reference_2026-11-24': 'fc361b6 (checked 2026-11-21, unchanged on 2026-11-23)', 'previous_reference_2026-11-21': '6274591 (checked 2026-11-20)', 'previous_reference_2026-11-20': 'cb575df (checked 2026-11-16)', 'previous_reference_2026-11-16': '7cad8b1 (checked 2026-11-13)', 'previous_reference_2026-11-13': '193b584 (checked 2026-11-10)', 'previous_reference_2026-11-10': '421dbcd (checked 2026-11-09)', 'previous_reference_2026-11-09': '5872cac (checked 2026-11-03)',
                  'previous_reference_2026-11-03': '3bdb8b6 (checked 2026-10-31)',
                  'team_registry_revision_2026-11-10': 'registries_rev_2026-11-08_d32_mantis_local (string unchanged) in LO/registries.py @ 193b584 '
                                                       '(8cf8b9b): METRIC_DEF v1_3_change_2026-10-24 now carries the D-18 objective mapping '
                                                       '(PAPER_COMPOSITE_CAL = acctempo_m4 primary, v1 sensitivity) with acctempo_m4_export_note_2026-10-23; '
                                                       'MANTIS_V2 row without max_seq_len / patch_len / patch_stride, with licence (Apache-2.0), '
                                                       'pretraining_data (synthetic CauKer, 2 million series) and references; '
                                                       'tests/test_registry_release_alignment.py asserts the mapping (test_metric_def_maps_the_paper_objectives_d18)',
                  'commits_reviewed_2026-11-10': ['8cf8b9b (10/11, D2/D4/E1/E3): tests/test_adapter_store.py, test_encoder.py, test_probe_cell.py, test_spec.py '
                                                  '(the 34 f3_mantis package tests) + conftest.py; tests/test_dedup_zstd_store.py (6 tests: per-entry '
                                                  'identity fields, lossless round-trip, hash check on open, ensure/reusable unchanged); LO/registries.py '
                                                  'as above; CQ/Feature_extraction/labels/README.md ACELO provenance note (production rule with_comment; '
                                                  'the builder in the repository drops comments and does not reproduce 30,231 rows, 0.95 %; the artefact '
                                                  'is the source of truth)',
                                                  '8c3fd80 (10/11, B/C1/D1): tools/combine_meta_release_p1_20261109.py (row-wise concatenation of the CQ and '
                                                  'LO child releases, union of columns, merged column dictionary, manifest with the sha256 of every '
                                                  'input, f2_scope and s0_profile strings, known_qa_note), tools/check_meta_release_acceptance_20261109.py '
                                                  '(seeds, partial rows, row counts vs input fact rows, QA rates, imputer-only ref N10, F0 columns, '
                                                  'FS1-FS3 leakage checks MQ01/MQ06/MQ10, required S0 columns non-null, feature_regime non-null, row '
                                                  'status), tools/recompute_lo_patchtst_sleak_r2_20261109.py (s_leak and s_leak_probe_auc copied from the '
                                                  'canonical 24-value table of the LO F1 static-v2 export; s_san_plus, s_san_plus_v2, acctempo_m3, '
                                                  'acctempo_m4 recomputed; formula reproduction <= 1e-9 asserted before the replacement; r2_changes.csv '
                                                  'with old/new/diff per cell; new sha256sums), tools/compare_pilot_det_20261109.py and '
                                                  'tools/ops_20261109/pilot_det.sh (determinism pilot: two fresh cache roots, per-class sha256 '
                                                  'comparison, cell record and library versions), tools/compare_repro_runs_20261109.py, '
                                                  'tools/build_m13_s0_v4_20261109.py (S0 v4), tools/build_d3_mantis_facts_zm_20261109.py (Z_M v2), '
                                                  'tools/verify_facts_of_record_20261109.py (rclone copy of the 198 listed files, sha256 and bytes '
                                                  'compared), tools/ops_20261109/lo_mantis_child.sh',
                                                  'ea19afa (10/11, C2): metrics_core/evaluation.py PROBE_CONFIG (lbfgs, C 1.0, tol 1e-4, max_iter 500), '
                                                  'fit_missingness_probe(..., deterministic=True) under threadpool_limits(1), probe_environment() '
                                                  '(python, numpy, scipy, scikit-learn, threadpools); tools/vastai_audit_shared.py --s-leak-reference, '
                                                  '--s-leak-tolerance (default 1e-9), --no-s-leak-reference, assert_s_leak_matches_reference (RuntimeError '
                                                  '"not reproducible" / "lacks cells"), manifest blocks probe_config, probe_environment, s_leak_check; '
                                                  'tests/test_leak_probe_determinism.py (4 tests: bitwise repeatability under 1/2/4 ambient threads, '
                                                  'registered parameters, environment record, reference assertion accepts/rejects)',
                                                  'ba5c1c6 (10/11, C3): tools/build_c3_runner_commit_inventory_20261109.py (LO: host code directory '
                                                  'lo_patchtst_seed42_code, 38 files compared with the repository history after CRLF/LF normalisation, '
                                                  '37 equal to the tree, check_gpu.py not in the repository, earliest matching commit recorded; '
                                                  'Mantis: runner blob sha256 2cc8e3f8... found in the history; V0 cells NULL; source_inventory.json '
                                                  'per package; README revision r2b; sha256sums rewritten), '
                                                  'tools/build_delivery_receipts_20261109.py (per file: bytes, sha256 re-checked against sha256sums.txt, '
                                                  'local MD5 and Drive MD5; status DELIVERED_AND_BYTE_VERIFIED_NOT_L2_INGESTED), '
                                                  '(verify_facts_of_record_20261109.py is in 8c3fd80)',
                                                  'f478b23 (10/11, C2 on real data): tools/check_leak_probe_reproduction_20261109.py (two deterministic runs '
                                                  'and one default multi-thread run of the canonical s_leak computation of one window/parent, compared '
                                                  'with the reference table; environment and platform recorded in the report)',
                                                  '193b584 (10/11): tools/ops_20261109/lo_mantis_child.sh skips a child assigned to another host '
                                                  '(skip_<V>_<W> marker); operational only'],
                  'review_2026-11-10': {'verdict': 'the six commits implement C1, C2, C3, D2, D3, D4, E1, E3 of the 09/11 request as specified; static '
                                                   'review only (the environment does not run the team repository)',
                                        'notes': ['build_c3_runner_commit_inventory writes v0_cells as a string, but the delivered '
                                                  'runner_commit_evidence.json of the Mantis r2 package carries a v0_cells dict with "author decision '
                                                  '2026-11-10" and indirect evidence: the delivered file is not byte-reproducible from the committed '
                                                  'script, and the author has not decided (decision 43)',
                                                  'build_m13_s0_v4 and combine_meta_release_p1 label Q-28 and Q-30 as "author decision 2026-11-09": '
                                                  'the writing-side recommendations were applied before the author answered (decisions 39, 41)',
                                                  'check_leak_probe_reproduction: the CQ W1/V0 report cited in the response (6,437,104 probe rows, 43 '
                                                  'iterations, bitwise repeatable, thread-independent, max |diff| vs the F1 reference 2.09e-6) is not '
                                                  'on the Drive; LO not run (RAM)',
                                                  'hosts_with_identical_37_file_set: 12 is a literal in the inventory script, not a computed value',
                                                  'the W1/V0 determinism-pilot reports (CQ and LO) and the bench output of check 37 (c)/(d) cited in '
                                                  'the response are not on the Drive; only repro_V2_W2_seed42_20261109 (CQ V2 W2, bit-identical) is']},
                  'team_registry_revision_2026-11-09': 'registries_rev_2026-11-08_d32_mantis_local (LO/registries.py @ 421dbcd)',
                  'commits_reviewed_2026-11-09': ['cfcfd40 (09/11: LO/registries.py: EXPERIMENT_SEEDS augmentation_policy FIXED_SEED_42 -> MATCH_MASTER_SEED '
                                                  '("use the S2 balanced TRAIN artifact whose augmentation seed matches the model master seed"), decision 9 '
                                                  'rewritten "CLOSED updated 2026-11-04 D-32", status "LOCKED D-32 2026-11-04"; MODEL_REGISTRY: MOMENT rows '
                                                  'moved to RETIRED_MODEL_ROWS, MANTIS_V2 row (pinned revision, library, PCA8 adapter, guard, cache levels, '
                                                  'strict weight loading; carries max_seq_len 4 / patch_len 16 / patch_stride 16 copied from the PatchTST '
                                                  'update loop); TEMPORAL_FAMILY_POLICY F3_MANTIS_V2 (13 core + 4 sensitivity pipelines, master seeds '
                                                  '42/43/44, requires cache, determinism pilot and cost pilot of check 37); model/metrics.py '
                                                  'calibration_metrics clips at 1e-12 in float64 and renormalises (METRIC_DEF v1.3, M-16; historical facts '
                                                  'keep their provenance); model/architectures.py and model/config.py register mantis_v2; '
                                                  'modal_jobs/model_app.py and model_preflight_app.py: augmentation_seed default -1 = follow the run seed, '
                                                  'negative values rejected; tools/vastai_audit_shared.py --include-static-ablation; tests: '
                                                  'test_probability_clip_contract.py, test_registry_release_alignment.py asserts MATCH_MASTER_SEED and '
                                                  'that the MANTIS_V2 row equals f3_mantis/spec.py)',
                                                  '6a69b7f (09/11: f3_mantis/ package (adapter, cell, cli, determinism, encoder, metrics, probe, spec, store) '
                                                  'byte-identical to the writing-side f3_mantis_v0.1.0_2026-11-06 (sha256 of all 10 files equal); the 34 '
                                                  'package tests (tests/test_adapter_store.py, test_encoder.py, test_probe_cell.py, test_spec.py) are NOT in '
                                                  'the repository; CQ/LO mantis_v2 configs; tools/run_mantis_grid_zstd_20261109.py (task CQ|LO) and '
                                                  'run_mantis_cq_grid_zstd_20261108.py call f3_mantis.cell.run_cell with backbone_pin.json and '
                                                  'MANTIS_V2_SPEC but replace cell.EmbeddingStore by tools/mantis_zstd_dedup_store_20261107.DedupZstdStore '
                                                  '(subclass: write/open overridden, lossless zstd frames with per-row dedup and a round-trip check, '
                                                  'encoder-identity check on write, sha256 of frames/index/row_ids verified on open; ensure/reusable '
                                                  'inherited); run_purpose EXPLORATORY_CACHE_VALIDATION, microbatch 4,096, precision bf16; '
                                                  'tools/mantis_standardize_runs_20261108.py rebuilds the standard run layout ("nothing is invented", '
                                                  'provenance_notes.json per key; runner_git_commit null because the runner ships as a tar); '
                                                  'tools/rebuild_mantis_v0_predictions_20261109.py; refit/prepare adapter tools; '
                                                  'tools/build_report_patchtst_mantis_audit_20261109.py (report tables computed from the audit tables)',
                                                  '421dbcd (09/11: 267 files, 11,052 lines: MOMENT pilots of 04-06/11 (modal_jobs/moment_*), Mantis cache '
                                                  'probes, PatchTST V7-V16 and LO PatchTST queues/supervisors/resume scripts, M-09/M-10 receipt and '
                                                  'facts-of-record builders, M-13 S0/F0 builders, split registry and offering ledger tools, cohort and '
                                                  'facts-package builders (build_cq_patchtst_v7_v16_full_facts_20261109.py, '
                                                  'build_facts_package_mantis_lo_20261109.py, run_lo_patchtst_cohort_20261109.py), tempo_core.dq '
                                                  'baseline tools, Drive organisation PowerShell scripts; scripts with rented-host addresses excluded)'],
                  'registry_drift_2026-11-09': {'augmentation_policy': 'CONVERGED: MATCH_MASTER_SEED in LO/registries.py EXPERIMENT_SEEDS and decision 9 '
                                                                       '(cfcfd40), modal_jobs/README.md (lines 157, 168, 277), modal_jobs/run_model_grid.ps1 '
                                                                       'default match_model_seed, tools/vastai_train_shared.py default match_model_seed with '
                                                                       'the runtime check, modal_jobs/model_app.py and model_preflight_app.py default -1 = run '
                                                                       'seed; test_registry_release_alignment asserts it (check 35 PASS on the code side)',
                                                'metric_def_v1_3': 'clip 1e-12 float64 now in model/metrics.py (M-16 code contract); the D-18 objective mapping '
                                                                   'is still not written into LO/registries.py METRIC_DEF (open item of check 35)',
                                                'mantis_v2_row': 'team row agrees with MODEL_REGISTRY here on revision, library, adapter, guard, cache levels, '
                                                                 'strict loading and parameter counts; it adds max_seq_len 4, patch_len 16, patch_stride 16 '
                                                                 'from the shared update loop (meaningless for Mantis; harmless) and does not carry the '
                                                                 'references, licence and pretraining_data keys',
                                                'f3_mantis_tests': 'the repository has no tests for f3_mantis/ (the package tests were not copied); only '
                                                                   'test_registry_release_alignment reads f3_mantis/spec.py',
                                                'cache_store': 'DedupZstdStore (team, 07/11) is a subclass of the reviewed EmbeddingStore and is not covered '
                                                               'by the writing-side review or tests; its write path keeps the identity fields '
                                                               '(input_sha256, adapter_digest, encoder_digest, encoder_fingerprint, backbone_pin) and its '
                                                               'open path verifies file hashes; check 37 (h)'},
                  'seed_policy_consistency_2026-11-09': 'CONSISTENT: the four places of check 35 and the two Modal entry points read MATCH_MASTER_SEED / '
                                                        'match_model_seed; every LO PatchTST launch script of 07/11 passes '
                                                        '--augmentation-seed-policy match_model_seed; seeds 43/44 still need the 144 S2 runs',
                  'drive_layout_2026-11-09': 'move-only migration on 09/11 (DRIVE_LAYOUT_MIGRATION_20261109.md, MODEL_LAYOUT_MIGRATION_20261109.md, '
                                             'README.md at the Results root): Results/{CQ,LO}/{L0_registry,L1_runs,L2_facts,L3_meta}, '
                                             'Results/cross_task_meta/{accepted,work_in_progress,retroactive_receipts}; the former Jobs/ tree is kept '
                                             'for hash reconciliation; Drive file ids are unchanged by the move (the 03/11 ids still resolve); '
                                             'FACTS_OF_RECORD.md (198 files, 16 folders, with FACTS_OF_RECORD_sha256.txt) names the paper facts of '
                                             'phase 1 and lists the 09/11 full-grid packages as phase-2 facts',
                  'results_package_2026-11-09': 'input/results gains four packages built from hash-verified Drive files: '
                                                'GD2_CQ_PATCHTST_F2_V7_V16_facts_20261109 (sanity 240, cohort 960, checkpoint 30, resource 30, summary, '
                                                'source inventory, README, sha256sums), GD2_LO_PATCHTST_F2_V0_V16_facts_20261109 (sanity 408, cohort '
                                                '1,632, checkpoint 51, resource 51; status MIXED_LEAK_PROBE, decision 38), '
                                                'GD3_CQ_MANTIS_V2_F3_exploratory_facts_20261109 (sanity 408, cohort 1,632, checkpoint 51, resource 51; '
                                                'EXPLORATORY) and GD4_meta_inputs_M13_phase1_20261108 (S0 profile 48 rows, Z_M 5 rows, F0 CQ 24 rows); '
                                                'the large per-class, bootstrap and slice files are listed with their Drive ids for the author sync',
                  'not_in_repository_or_drive_2026-11-10': ['determinism-pilot reports of CQ/W1/V0 and LO/W1/V0 (check 37 (d)) and the bench / estimate output '
                                                            'of check 37 (c): reported in the 10/11 response, no file on the Drive', 'leak-probe reproduction '
                                                            'report of CQ W1/V0 (f478b23 tool): reported, no file on the Drive; LO not run', 'LO Mantis facts '
                                                            'package (grid running on 09-10/11)', 'official L2 ingest receipts (the 10/11 receipts are '
                                                            'byte-level code-team receipts)', 'M-15 (mm_runs: lightgbm / optuna not installed on the team side)',
                                                            'S2 seeds 43/44 (144 runs) and every phase-2 cell'],
                  'resolved_since_2026-11-09': ['f3_mantis tests (34) now in tests/ (8cf8b9b)', 'deterministic probe and reference assertion (ea19afa)',
                                                'runner commit of the LO PatchTST runs (51/51, retroactive) and of 48/51 Mantis runs (ba5c1c6)', 'metamodel package and registry received by the team (M-14 assembled)', 'MANTIS_V2 row of '
                                                'Z_M (v2)', 'S0 profile v4', 'LO r2 with one probe table (decision 38 (a))'],
                  'not_in_repository_2026-11-09': ['f3_mantis tests (34) and requirements-f3.txt', 'backbone_pin.json of the pilots (only the pin block inside '
                                                   'the run manifests)', 'cost pilot (f3_mantis.cli bench / estimate) and determinism pilot outputs of '
                                                   'check 37 (c)/(d)', 'the standard-audit code that fits the s_leak probe with a deterministic solver '
                                                   '(the 09/11 LO re-audit produced a third probe fit)', 'runner commit for the LO PatchTST runs '
                                                   '(runner_git_commit null in all 51 resource rows) and for Mantis', 'official L2 ingest receipts of the '
                                                   '09/11 facts packages', 'metamodel package and registry revision 2026-11-04/06/09 on the team side '
                                                   '(M-14 blocked: the team reports that it never received them)', 'MANTIS_V2 row of Z_M (M-13b has five rows)',
                                                   'S2 seeds 43/44 (144 runs)'],
                  'commits_reviewed_2026-11-03': ['df2a867 (31/10: review patch 2026-10-31 adopted: identify_runner_commit hashes the LF and CRLF '
                                                  'renditions of every committed runner version, content_note softened ("matching runner content '
                                                  'alone does not identify the full working tree"); tools/compare_paired_replay.py (generic matched '
                                                  'replay with two salts); tools/package_r21_evidence_20261031.py; LO/registries.py: '
                                                  'REGISTRY_REVISION registries_rev_2026-10-31_r22, METRIC_DEF metric_def_v1.3 (version string), '
                                                  'S_SAN_FORMULA s_eff/s_leak rewritten to the real-row contract, EXPERIMENT_SEEDS augmentation_policy '
                                                  'MATCH_MASTER_SEED -> FIXED_SEED_42 and decision 9 rewritten "CLOSED updated 2026-10-31" (see '
                                                  'PENDING_DECISIONS[32]); test_registry_release_alignment asserts FIXED_SEED_42; 66 tests)',
                                                  '834ad30 (03/11: export_lo_static_v2_r4_20261102.py = M-01 (1,632 LO cells with acctempo_m4, 204 '
                                                  'resource runs, train-time summary, means, summary.json, sha256sums); export_cq_slices_r4_20261102.py; '
                                                  'prepare_cq_patchtst_v0_drive_20261102.py = M-04; build_cq_patchtst_v0_v6_full_facts_20261103.py and '
                                                  'append/finalize/check/correct_cq_* tools (facts package V0-V6: 168 sanity cells, 504 slice rows, '
                                                  '504 per-class rows, 1,512 bootstrap rows, 21 resource rows, 672 cohort slices, salt join); '
                                                  'report_cq_patchtst_v0_v6_20261102.py (cost rate 0.368 USD/h hard-coded) and add_cq_cost_vnd '
                                                  '(25,990 VND/USD); audit_prediction_course_cohort.py salt-based join with train_path = real parent '
                                                  'TRAIN; test_prediction_course_cohort_contract.py)',
                                                  '5872cac (03/11: check_cq_r4_probability_metric_definitions_20261103.py (model clip 1e-7 vs audit '
                                                  '1e-12 -> ALL export blocked), reconcile_cq_r4_slices_from_predictions_20261103.py (ALL copied from '
                                                  'immutable R4, STRICT/OVERLAP recomputed with the model convention within 1e-6), '
                                                  'prepare_cq_r4_provenance_20261102.py (DRAFT inventory), export_cq_s2_sampling_partial_20261103.py '
                                                  '(M-06 partial), export_cq_split_evidence_partial_20261103.py (M-07 partial), '
                                                  'export_cq_release_identity_partial_20261103.py (M-08 partial), export_cq_class_offering_support_20261103.py '
                                                  '(M-05 CQ), preflight_cq_meta_r4_20261103.py (M-14 trial), package_cq_qa23_evidence_20261103.py (M-10); '
                                                  '68 tests pass at 5872cac; no change to tools/vastai_train_shared.py, model/ or modal_jobs/)'],
                  'review_patch_2026-10-31_status': 'adopted in df2a867',
                  'registry_drift_2026-11-03': {'s_eff_s_leak': 'CONVERGED: LO/registries.py @ df2a867 now states s_eff = mean(mask) on the unaugmented '
                                                                'parent-imputation real TRAIN pooled P1-P4, inherited by augmented variants, and s_leak = '
                                                                'probe fit once on that real TRAIN and evaluated per (eval_split, phase); this is the '
                                                                'real-row contract registered here since rev 2026-10-05 [DEC §2]; confirmed numerically '
                                                                'by the PatchTST V0-V6 sanity tables (s_eff and s_leak identical for V2/V3/V4 = V1, V6 = V5 '
                                                                'and across V0/V1/V5 per window x split x phase)',
                                                'augmentation_policy': 'DIVERGED: FIXED_SEED_42 in the team registry against MATCH_MASTER_SEED LOCKED '
                                                                       '2026-10-05 [DEC §1] here; a closed decision was rewritten without the author; the '
                                                                       'request list of 02/11 (M-12) asks for MATCH_MASTER_SEED; decision 32 and check 35',
                                                'metric_def_v1_3': 'the team bumped the version string only; the D-18 objective mapping (H1-H6 on '
                                                                   'AccTEMPO_M3^(cal), H7 on macro-F1, S_perf as the performance axis, v1 as sensitivity) '
                                                                   'is not yet written into LO/registries.py METRIC_DEF'},
                  'seed_policy_consistency_2026-11-03': 'INCONSISTENT inside the repository: LO/registries.py says FIXED_SEED_42; modal_jobs/README.md '
                                                        '(lines 157 and 277) still names MATCH_MASTER_SEED as the registered policy; '
                                                        'modal_jobs/run_model_grid.ps1 defaults to match_model_seed; tools/vastai_train_shared.py raises '
                                                        '"MATCH_MASTER_SEED violated" under match_model_seed; the portable tree therefore still needs one '
                                                        'S2 artifact per master seed unless every seed-43/44 launch passes the fixed policy explicitly',
                  'drive_access_2026-11-03': 'the author shared the team Drive (Results folder 1GWiedVROrxp8jvGbd0xmvVmWriZUkpOn); the writing side '
                                             'reads it through the Google Drive connector file by file (base64, sha256 checked against each '
                                             'package sha256sums.txt); files above about 40 KB are not transferred this way (decision 31: the author '
                                             'syncs the subfolders to input/results/_drive_mirror_20261029/); 47 small files of 12 packages were '
                                             'verified on 03/11 (analysis_r23_2026-11-03.json, drive_fetch_2026-11-03)',
                  'results_package_2026-11-03': 'input/results gains the hash-verified small files of the 03/11 Drive packages: '
                                                'GD2_CQ_PATCHTST_F2_V0_V6_facts_20261103 (facts package V0-V6: resource_per_run, checkpoint_selection, '
                                                'runtime_cost_estimates_vnd, salt diagnostics, summary, source inventory; plus the V0-current '
                                                'report_facts training_history / run_contracts / checkpoint_selection), '
                                                'GD1_LO_V3_1_clean_r1_export_static_v2 (lo_family_window_phase_mean with acctempo_m4, '
                                                'lo_train_time_family_pipeline, summary, README, sha256sums), GD1_CQ_V2_2_clean_r1/_export_2026-11-03 '
                                                '(R4 means, train-time/energy, summary, provenance DRAFT inventory, reconciled-slices summary), and '
                                                'GD1_CQ_V2_2_clean_r1_audits_20261103 (Radius fallback 24 rows, S2 sampling summary 108 rows, class '
                                                'offering support 27 rows, split evidence partial, release identity partial, meta-join trial summary); '
                                                'the large per-cell files are listed by Drive id and size in each package README and wait for the '
                                                'author\'s sync (decision 31)',
                  'not_in_repository_2026-11-03': ['the V1-V6 run bundles (verified tar.gz on the team disk, sha256 in source_inventory.json) and the '
                                                   'V7 partial run', 'LO S2 sampling summary and LO Radius audit (M-06 LO)', 'LO class-offering flags '
                                                   '(M-05 LO)', 'the static-v2 ablation (M-03)', 'FACTS_OF_RECORD.md at the Jobs/ root (M-09)', 'the '
                                                   'release identity ledger app output (M-08)', 'S2 input trees for seeds 43/44', 'the D-18 objective '
                                                   'mapping in LO/registries.py METRIC_DEF v1.3', 'a builder fix for the appendix encoding defect of the '
                                                   '02/11 report (check 33)'],
                  'commits_reviewed_2026-10-31': ['93dcf1e (28/10: review patch 2026-10-28 adopted: runner_git_commit per ingest, excluded_runner_commits, '
                                                  'replay_provenance; tools/append_complete_cq_lo_evidence_20261028.py = the DAY_DU appendix builder '
                                                  '(check 28 closed for the appendix); report titles *_R20)',
                                                  'e06665f (31/10: review patch 2026-10-29 adopted: receipt-backed runner exceptions, '
                                                  'tools/identify_runner_commit.py with the team refinement "unknown" when a runner version spans '
                                                  'the loop change; new tools: audit_cq_patchtst_v0_current_epoch1_replay.py (one-epoch replay of the '
                                                  'current V0 run, bit-exact float64 on three epoch-1 metrics, layout and 16 contract fields), '
                                                  'audit_cq_primary_risk_set_v1.py (constant column primary_risk_set: source 1, input 0, mask 0 in the '
                                                  '18 V0 inputs), audit_cq_label_view_consistency_20261031.py (labels of the release views equal the '
                                                  'label artifact per window x split; TEST phases share one cohort), '
                                                  'build_cq_patchtst_v0_current_r21_report.py (three NEW PatchTST V0 runs, current layout = 11 static '
                                                  'fields without timeline_source, audits B = 2,000, comparison with the 12-field pilot and with '
                                                  'recurrent V0), build_cq_v0_performance_replay_report.py, update_cq_static_provenance_20261031.py '
                                                  '(static availability caveats; baseline runner hash 4077c6c9... = CRLF rendition of eb80516))',
                                                  '9bc2c21 / e9b488f / 3bdb8b6 (31/10: tools/stage_r21_evidence_20261031.py copies 151 selected files '
                                                  'from Drive into CQ/resuilt/input/results/R21_evidence_20261031 with a sha256 manifest, status '
                                                  'PARTIAL_NOT_RELEASED; audit_r21_s2_ledger_inventory_20261031.py: 36/36 S2 seed-42 ledgers on Drive); '
                                                  '65 tests pass at 3bdb8b6'],
                  'review_patch_2026-10-28_status': 'adopted in 93dcf1e', 'review_patch_2026-10-29_status': 'adopted in e06665f',
                  'review_patch_2026-10-31': 'on 3bdb8b6: tools/identify_runner_commit.py hashes every committed runner version in its blob, LF '
                                             'and CRLF renditions, names the rendition and explains that a run dated before the commit used that '
                                             'content from the working copy; the 20/10 CQ baseline hash resolves to eb80516 (CRLF), before '
                                             '044d6c7, superseded by 75eae0c; one test; 66 pass',
                  'baseline_runner_attribution_2026-10-31': 'independently reproduced by the writing side: sha256 of the CRLF rendition of '
                                                            'tools/vastai_train_shared.py @ eb80516 = 4077c6c91de8f16053653ae315317fb11746a5fa8924873b66be6cbaad14c78e, '
                                                            'the value the team reports from the baseline metadata_contract; eb80516 was committed '
                                                            '2026-10-21 17:26 (+07), one day after the run, five days before 044d6c7; the baseline ran '
                                                            'the working copy that became eb80516, so its training loop predates 044d6c7',
                  'results_package_2026-10-31': 'input/results now holds three report-derived packages built by the writing side '
                                                '(GD1_CQ_V2_2_clean_r1_report_derived: 12 CSV from the 28/10 CQ report and the 23/10 R4 tables; '
                                                'GD1_LO_V3_1_clean_r1_report_derived: 13 CSV from the LO R20 report; GD2_CQ_PATCHTST_F2_evidence_report_derived: '
                                                '14 CSV from the 23/10, 27/10, 29/10 and 31/10 reports), each with the source docx, README and sha256 '
                                                'manifest, plus a placeholder for the team package R21_evidence_20261031 (151 files, not yet received: the '
                                                'Drive connector of the writing side sees only the folders the author has opened)',
                  'remote_status_2026-10-29': 'origin/main still e0ae433 (git ls-remote, 29/10): the changes behind the 29/10 CQ report '
                                              '(matched historical replay tool cq_rnn_matched_historical_20261029, section 14) and the R20 LO '
                                              'report (ONE_CLASS / SLICE_EMPTY statuses, classes min-max, UNSEEN share table, the replay '
                                              'sentence of review patch 2026-10-28 reproduced verbatim) exist only in the team\'s local '
                                              'checkout; nothing new to review on GitHub',
                  'review_patch_2026-10-29': 'series on e0ae433 (includes 2026-10-28): modal_jobs/ingest_lo_vastai_facts_app.'
                                             'assert_uniform_execution(runner_exceptions=...) admits a cell trained from another runner only '
                                             'through an explicit entry {runner_sha256, runner_git_commit, equivalence_receipt_sha256, '
                                             'registered_by} matching the contract lineage (unused or mismatched entries are errors; the '
                                             'receipt lists the exceptions; VASTAI_RUNNER_EXCEPTIONS names the file); '
                                             'tools/identify_runner_commit.py maps lineage.runner_sha256 to the interval of commits whose '
                                             'tools/vastai_train_shared.py has that content and to the side of 044d6c7 (the 20/10 baseline '
                                             'hash resolves to 83c5056..eb80516 = before); replay_provenance attributes a side without a '
                                             'commit through its runner hash; 65 tests',
                  'drive_storage_tree_2026-10-29': 'README_STORAGE_TREE_CQ_LO_20261029.md: gdrive:Jobs/{CQ,LO}/organized_moved_20261029/ with '
                                                   'L0_registry (release manifest, lineage, Modal L0 copy), L1_runs (S1: 15 attempts per task = 5 '
                                                   'imputers x 3 windows, 9 files each, rclone check 0 differences; S2: 12 balanced pipelines x 3 '
                                                   'windows, seed 42, balanced_train + ledger + manifest; S3: run bundles and preserved packages), '
                                                   'L2_facts (fact_exports, audits_and_evidence, s2 quality/resource facts), input_archives, '
                                                   'evidence_packages (CQ only), transfer receipts; no L3. The Drive connector sees the shared '
                                                   'root folder but none of its children, so receipts could not be verified from here (check 30)',
                  'commits_reviewed_2026-10-28': ['651b458 (review patch 2026-10-27 adopted verbatim; the test helper loads '
                                                  'tests/test_vastai_ingest_and_verify.py by file path)',
                                                  '29da3b2 (LO/registries.py rev 2026-10-27_r1: MODEL_REGISTRY PatchTST gains '
                                                  'optimisation_protocol {HP_PATCHTST_CHANNEL_INDEPENDENT_v2, lr 1e-3, warm-up 0, clip None, '
                                                  'PRIMARY_GRID, status LOCKED 2026-10-27} and TEMPORAL_FAMILY_POLICY.F2 gains '
                                                  'seed42_optimisation_protocol with the decision text "D23 v3 remains sensitivity evidence '
                                                  'after W3 failed the registered curve criterion": the team locked decision 23 as (a) '
                                                  'before the author ratified it)',
                                                  'e0ae433 (tools/build_cq_lo_consolidated_reports_20261028.py: CQ R4 + D23 + CQ RNN replay '
                                                  'receipt, LO static-v2 grid from four family audits + closure archive sha256 + prefix '
                                                  'audit + cohort audit + LO RNN replay receipt; tools/audit_lo_paired_replay_20261028.py '
                                                  '(source-id hash join of LO W1/V0/RNN baseline vs replay with each run salt, exact '
                                                  'probability equality asserted); tools/run_lo_static_v2_cohort_audit.ps1 (V0-V16 per '
                                                  'family); 60 tests pass at e0ae433)'],
                  'review_patch_2026-10-27_status': 'adopted in 651b458 (all five tests kept)',
                  'review_patch_2026-10-28': 'on e0ae433: modal_jobs/ingest_lo_vastai_facts_app.assert_uniform_execution also requires '
                                             'one runner_git_commit per ingest (runner_sha256 hashes the runner script only; the training '
                                             'loop lives in model/shared_phase.py since 044d6c7) and records it in the receipt; '
                                             'tools/f2_shard_plan.py records excluded_runner_commits of reused pilot cells and warns when '
                                             'they cannot share an ingest with the shards; '
                                             'tools/build_cq_lo_consolidated_reports_20261028.replay_provenance() prints the runner '
                                             'commits of both sides of a paired replay and states whether a delta of 0 closes check 27 '
                                             '(reference before 044d6c7, current after) or only proves determinism; LO replay sentence '
                                             'read from the receipt; 3 tests; 63 pass',
                  'report_builder_provenance_2026-10-28': 'the delivered REPORT_*_2026-10-28_DAY_DU.docx files were not produced by the '
                                                          'builder committed in e0ae433: sections 1, 7 and 8 differ in wording and the '
                                                          'appendix sections 10-13 (816-cell tables, label distribution, support and '
                                                          'bootstrap CI, STRICT/OVERLAP and SEEN/UNSEEN slice means) are generated by no '
                                                          'script in the repository; no tool in the repository writes '
                                                          'cq_rnn_equivalence_20261028/canonical_facts_comparison.json either (check 28)',
                  'pilot_runner_mismatch_2026-10-28': 'the three PatchTST V0 pilot cells (runner 7886a856, 2026-10-23) and the 48 F2 '
                                                      'shards (runner e0ae433 or later) carry different runner_sha256 values, so '
                                                      'assert_uniform_execution refuses one ingest that mixes them; the shard plan '
                                                      '(--exclude-completed pilot root) silently assumes the mix (decision 25)',
                  'not_in_repository_2026-10-31': ['the R21_evidence_20261031 package itself (151 files; on the team disk and Drive, not in the repository, '
                                                   'not yet in input/results/)',
                                                   'the three NEW PatchTST V0 run bundles (cq_patchtst_v0_current_seed42_r21), their audits and the reports '
                                                   'REPORT_CQ_PATCHTST_V0_CURRENT_2026-10-31 (+ _STATIC_PROVENANCE) and BAO_CAO_CQ_PATCHTST_V0_HIEU_SUAT_REPLAY_2026-10-31 '
                                                   'with run_contracts.csv, training_history.csv, metrics_and_sanity.csv, per_class_recall_ci.csv (not delivered '
                                                   'to the author)',
                                                   'the D23 train_history files (packaged in R21_evidence, not delivered)',
                                                   'an LO static-v2 fact export (the package stages the r2 historical export under LO/facts/ and the v2 audits '
                                                   'under LO/audit_seed42/)',
                                                   'S2 input trees for seeds 43/44', 'release identity ledger.json', 'METRIC_DEF v1.3 in LO/registries.py'],
                  'not_in_repository_2026-10-29': ['everything of 2026-10-28 (origin/main unchanged)',
                                                   'tools behind the 29/10 CQ report: the matched historical replay of CQ/W1/V0/RNN '
                                                   '(cq_rnn_matched_historical_20261029/paired_replay_equivalence.json, baseline '
                                                   'cq_rnn_baseline_drive_20261029) and the DAY_DU builder with sections 10-14',
                                                   'the LO R20 builder changes (ONE_CLASS / SLICE_EMPTY / classes / UNSEEN share)',
                                                   'the baseline run_manifest of the matched replay with its runner_sha256 (needed to close check 27 by attribution)',
                                                   'the D23 train_history (still not delivered; the 29/10 CQ report prints no epoch curve)'],
                  'not_in_repository_2026-10-28': ['the R4 CQ package, the PatchTST pilot package, the D23 pilot package (train_history '
                                                   'still not delivered to the author; the regenerated D23 report with section 4b of '
                                                   'review patch 2026-10-27 was not sent)',
                                                   'the LO static-v2 package (lo_static_v2_seed42_20261026: four family audits, '
                                                   'LO_static_v2_closure_20261028.tar.gz sha256 9108...40d3, cohort audit 68 x 96 cells, '
                                                   'prefix audit summary_static13_full_scan.json, paired_replay_equivalence.json)',
                                                   'the CQ replay receipt canonical_facts_comparison.json and the tool that wrote it',
                                                   'the exact builder of the DAY_DU reports (appendix sections 10-13)',
                                                   'the LO r3 package and the historical r2 package (now archived evidence)',
                                                   'ablation_comparison.csv and the 128 ablation cohort slices',
                                                   'release identity ledger.json (CQ, LO)', 'QA23 per-base linkage table',
                                                   'METRIC_DEF v1.3 (repository LO/registries.py still metric_def_v1.2)',
                                                   'S2 input trees for seeds 43 and 44'],
                  'commits_reviewed_2026-10-27': ['8d105db (static_feature_contract_id in every manifest and Modal run record; N10 '
                                                  'mirrored into LO/registries.py)',
                                                  '0851aed (tools/vastai_run_lo_static_v2_grid.sh: full LO F1 seed-42 replay under the '
                                                  'v2 13-field contract, one family per instance, new output root; salt still read from '
                                                  'reference/ablation_salt)',
                                                  '044d6c7 (model.shared_phase.train_shared_checkpoint: per-update linear warm-up and '
                                                  'gradient-norm clipping through one optimizer_step helper used by every family; '
                                                  'history records learning_rate_end and optimizer_updates; vastai_train_shared gains '
                                                  '--learning-rate, --warmup-epochs, --gradient-clip-norm, --run-purpose '
                                                  '{PRIMARY_GRID, STABILITY_PILOT_D23, EXPLORATORY_STATIC_ABLATION}; manifests record '
                                                  'warmup_epochs and gradient_clip_norm; tools/vastai_run_cq_patchtst_stability_pilot.sh '
                                                  'runs W2/V0 and W3/V0 at lr 3e-4, warm-up 1, clip 1.0)',
                                                  'b0e5ae1 (launcher accepts code/ and tools/ layouts)',
                                                  'bc20089 (PIPELINE_LABELS aligned with the registry: N1 closed; '
                                                  'tools/build_cq_d23_configuration_report.py)',
                                                  'af079d8 (review patch 2026-10-25 shard plan, launcher and tests adopted verbatim); '
                                                  '55 tests pass at af079d8'],
                  'review_patch_2026-10-25_status': 'adopted: shard plan + sharded launcher + tests (af079d8), pipeline labels (bc20089), '
                                                    'N10 mirror (8d105db)',
                  'review_patch_2026-10-27': 'on af079d8: training-protocol provenance after 044d6c7 (contract records learning rate, '
                                             'warm-up, clipping and run purpose and adds them to the immutable identity when they '
                                             'deviate from the registered protocol; ingest asserts one training protocol, one layout '
                                             'policy and one revision per receipt and refuses non-primary runs; shard verify compares '
                                             'the same fields and the static contract id; the F2 report gate includes the registered '
                                             'optimisation protocol); tools/build_cq_d23_configuration_report.py evaluates the '
                                             'registered D-23 (b) criterion from train_history (unimodal spike-free VALIDATION curve or '
                                             'selection away from epoch 1), prints old and D23 histories side by side and makes its '
                                             'conclusion conditional; tests/test_training_protocol_provenance.py; 60 pass',
                  'pipeline_label_defect_N1_status_2026-10-27': 'closed in bc20089 (PIPELINE_LABELS follow the registry; the D23 report '
                                                                 'of 2026-10-27 prints the correct mapping); reports of 2026-10-16..25 '
                                                                 'keep the swapped words and must not be quoted for pipeline names',
                  'not_in_repository_2026-10-27': ['the R4 CQ package and the PatchTST pilot package (unchanged since 2026-10-23)',
                                                   'the D23 pilot package (cq_patchtst_d23_stability_pilot_20261026: two run manifests, '
                                                   'train_history.parquet, audits): the report prints neither history nor the '
                                                   'per-epoch learning rate, so the registered acceptance criterion cannot be checked '
                                                   'from the report',
                                                   'the LO r3 package and the historical r2 package',
                                                   'ablation_comparison.csv and the 128 ablation cohort slices',
                                                   'the LO cohort audit numbers (6,528 cells)',
                                                   'release identity ledger.json (CQ, LO)',
                                                   'QA23 per-base linkage table',
                                                   'an equivalence replay of one recurrent cell with the 044d6c7 training loop '
                                                   '(check 27)'],
                  'commits_reviewed_2026-10-25': ['75eae0c (review patch 2026-10-23 adopted and extended: the PatchTST report builder '
                                                  'requires run_manifest / train_history / feature_layout per window, checks revision, '
                                                  '2048 = 4 x 512, static_ablation, run_purpose, required provenance fields and one layout '
                                                  'policy / layout hash / runner / seed across the three runs, writes a POSTHOC identity '
                                                  'receipt (the pilot manifests predate the release-identity fields), and prints lineage, '
                                                  'prefix audit, per-pipeline means with M4, time/energy, sanity detail, per-class and '
                                                  'bootstrap CI, provenance, epoch history, the V0-vs-V0 comparison and SEEN/UNSEEN x '
                                                  'STRICT/OVERLAP cohorts; tools/audit_prediction_course_cohort.py (salted-hash join of '
                                                  'predictions with evaluation inputs, STRICT flag equality enforced); '
                                                  'vastai_train_shared writes feature_layout_sha256 and the release identity fields '
                                                  '(release_id, data_release_id, split/phase versions, ...) into every new run manifest)',
                                                  'c225961 (LO static feature contract v2: contract_id static_feature_contract_lo_v2_point_in_time, '
                                                  '13 IN_TENSOR fields, timeline_source CONTEXT_ONLY, split_rule_version EXCLUDE, '
                                                  'model.data.fit_layout enforces an LO allowlist (LO_STATIC_TENSOR_COLUMNS) and raises on an '
                                                  'unregistered numeric static; LO/registries.py PENDING 19 closed by the team; '
                                                  'tools/stage_lo_l2_ingest_closure.py (NVML campaign bundles of the four families, RNN W1/V0 '
                                                  'replaced by the runner-7886a856 repair cell, ingest vastai_lo_f2_seed42_clean_20261025_r3); '
                                                  'tools/build_lo_closure_evidence_report.py; 52 tests pass at c225961)'],
                  'review_patch_2026-10-23_status': 'adopted in 75eae0c (both tests kept, builder extended far beyond the patch)',
                  'review_patch_2026-10-25': 'on c225961: tools/f2_shard_plan.py (deterministic shard plan of the remaining PatchTST cells '
                                             'for N parallel instances, --verify against run manifests: completeness, no duplicates, one '
                                             'runner commit / layout policy / revision per ingest) + tools/vastai_run_cq_patchtst_shard.sh '
                                             '(one shard per instance, explicit --static-layout-policy current, skip completed, refuses an '
                                             'instance without the per-seed input tree); LO/registries.py and CQ/registries.py mirror N10 '
                                             '(imputer_only_ref = the pipeline itself when balancer = NONE; validate_pipeline_registry '
                                             'updated); tools/generate_e2e_reports.py PIPELINE_LABELS corrected to the registry mapping '
                                             '(V1 MEDIAN, V5 MEAN, V3 SASMOTE, V4 RADIUS_SMOTE, ...); tests',
                  'pipeline_label_defect_N1_status_2026-10-25': 'still open in the repository at c225961: tools/generate_e2e_reports.py '
                                                                 'PIPELINE_LABELS swaps mean/median and SASMOTE/Radius-SMOTE, and the LO '
                                                                 'report of 2026-10-25 (its pipeline table and every pipeline name in it) '
                                                                 'inherits the swapped labels; artefacts and facts follow the registry '
                                                                 '(imputation_core.meta_storage.PIPELINE_ID, augmentation_core.storage), so '
                                                                 'numbers by V-id are right and only the words are wrong; fixed in review '
                                                                 'patch 2026-10-25',
                  'not_in_repository_2026-10-25': ['the R4 CQ package (cq_recurrent_allfamilies_grid_r4_20261023: CSV/parquet, per-class, '
                                                   'bootstrap, QA23 linkage, time/energy) and the PatchTST pilot package (manifests, '
                                                   'train_history, feature_layout, audits, cohort audit, posthoc receipt): read by the '
                                                   'builders from the working tree; none delivered to input/results/',
                                                   'the LO r3 package (lo_l2_ingest_closure_seed42_20261025, 204 NVML cells, receipt '
                                                   'vastai_lo_f2_seed42_clean_20261025_r3) and the historical LO r2 package '
                                                   '(lo_recurrent_allfamilies_grid_r2_20261021)',
                                                   'ablation_comparison.csv and the 128 ablation cohort slices (the P1 table is printed in '
                                                   'the 25/10 report; P2-P4 and the CSV are not)',
                                                   'the LO cohort audit at 68 configurations (6,528 cells computed, counts printed, no '
                                                   'numbers)',
                                                   'release identity ledger.json (CQ, LO) with scan counts',
                                                   'QA23 per-base linkage table (cq_qa23_reviewed_behavioural_linkage.csv)',
                                                   'runner commit per family of the LO NVML campaign (only the RNN W1/V0 repair cell names '
                                                   '7886a856)'],
                  'commits_reviewed_2026-10-23': ['585343e (tools/vastai_run_lo_nvml_historical_grid.sh: full LO matched replay '
                                                  'launcher, 204 cells, batch 2048, historical static layout, NVML 1 s; salt read from '
                                                  'reference/ablation_salt)',
                                                  '7886a85 (review patch 2026-10-21 adopted and extended: '
                                                  'imputation_core.meta_storage.release_identity_aliases returns the CURRENT and the '
                                                  'LEGACY_WITH_LINEAGE identity; every CQ Modal exporter (RNN facts, augmentation facts, '
                                                  'canonical S_leak, slice audit) classifies a manifest instead of comparing one id and '
                                                  'raises on an unknown identity of the active release; '
                                                  'modal_jobs/release_identity_ledger_app.py writes the ledger on the Volume and fails on '
                                                  'UNMATCHED / ABSENT / UNREADABLE; tools/release_identity_ledger.py rewritten on the shared '
                                                  'helper with OTHER_RELEASE and UNVERSIONED_S2_PARENT labels; canonical S_leak overlay reads '
                                                  'both identity partitions and refuses inconsistent duplicates)',
                                                  '5b14052 (CQ/registries.CQ_METRIC_AND_QA23_POLICY: M3 primary in the meta-dataset, paper '
                                                  'phase trends on S_perf / macro-F1 / balanced accuracy, M4 as sensitivity composite, QA23 '
                                                  'eight bases APPROVED_PREFIX_OBSERVED_BEHAVIOUR; '
                                                  'tools/export_cq_qa23_reviewed_behavioural_linkage.py (per-phase |rho| / NMI of the eight '
                                                  'bases); export_cq_recurrent_grid_report.py keeps the full sanity contract, M4, per-class and '
                                                  'bootstrap facts (4,896 / 14,688); tools/build_cq_current_recurrent_patchtst_report.py; '
                                                  '37 tests pass at 5b14052)'],
                  'review_patch_2026-10-21_status': 'adopted in 7886a85 (ledger tool rewritten on meta_storage.release_identity_aliases; '
                                                    'README section not taken)',
                  'review_patch_2026-10-23': 'on 5b14052: tools/build_cq_current_recurrent_patchtst_report.py reads the F2 protocol from '
                                             'the three PatchTST run manifests and fails on a deviation (revision, 2048 = 4 x 512, '
                                             'static_ablation, run_purpose, mixed layout policy or runner commit); checkpoint table reads '
                                             'best_score (selection_score does not exist, Score VAL was blank); new sections 8b provenance '
                                             '(elapsed, NVML energy, GPU) and 8c per-epoch VALIDATION history; '
                                             'tests/test_patchtst_pilot_report_gate.py, tests/test_release_identity_acceptance.py; 52 pass',
                  'not_in_repository_2026-10-23': ['the LO ablation report and ablation_comparison.csv (since 2026-10-21)',
                                                   'the R4 evidence package CQ/resuilt/cq_recurrent_allfamilies_grid_r4_20261023 '
                                                   '(1,632-cell parquet/CSV, per-class, bootstrap, QA23 linkage) and the PatchTST pilot '
                                                   'package cq_patchtst_v0_seed42_20261023 (three run manifests, train_history, audit): '
                                                   'the report builder reads them from the working tree, the commit carries only the tools',
                                                   'PatchTST pilot provenance: model_revision, static_layout_policy, runner commit, '
                                                   'elapsed time and NVML energy of the three runs are not in the 23/10 report',
                                                   'the release identity ledger output (ledger.json per task) and the scan counts'],
                  'commits_reviewed_2026-10-21': ['83c5056 (slice flags must be binary and ids unique; LO static ablation modes '
                                                  '--static-ablation no_static|gender_duration and --static-layout-policy '
                                                  'historical_reference in the runner; refuse to overwrite a run; portable_run_id '
                                                  'carries the layout policy; review patch 2026-10-19 adopted with stricter null '
                                                  'handling and a task/seed scope check in export_window_phase_tables)',
                                                  'eb80516 (report generators, closure and audit scripts committed: 116 files; '
                                                  'tools/audit_strict_overlap_partition.py; CQ RNN rerun launcher with the historical '
                                                  'static layout; per-class Radius-SMOTE fallback rates; release_inventory excludes '
                                                  'materialization_lineage_* from data_release_id; QA23 reviewed behavioural prefix '
                                                  'list in audit_cq_label_proxy; 35 tests pass)'],
                  'review_patch_2026-10-19_status': 'adopted in 83c5056 (null strict flags refused instead of counted as OVERLAP)',
                  'review_patch_2026-10-21': 'on eb80516: tools/release_identity_ledger.py (both data_release_id values of a release, '
                                             'manifest scan CURRENT / LEGACY_WITH_LINEAGE / UNMATCHED) with tests; 37 pass',
                  'commits_reviewed_2026-10-19': ['6fd6315 (review patch 2026-10-17b adopted and extended: alignment audit with --task CQ, '
                                                  'salted-hash cohort join, provisional CQ/registries.py STATIC_FEATURE_CONTRACT; '
                                                  'slice facts recomputed with the parent contract (s_eff/s_leak/train counts) and '
                                                  'checked ALL == sanity at ingest; runner_git_commit in the contract; '
                                                  'tools/vastai_audit_w1.py committed; CQ batch-2048 closure scripts '
                                                  '(audit_cq_batch2048_closure, rematerialize_cq_slices_2048, stage_cq_recurrent_2048_ingest, '
                                                  'audit_cq_static_compact); 30 tests pass)'],
                  'review_patch_2026-10-17b_status': 'adopted in 6fd6315 (registry note softened by the team; tools extended)',
                  'review_patch_2026-10-19': 'on 6fd6315: STRICT + OVERLAP confusion matrices must add up to ALL (slice partition '
                                             'invariant in vastai_audit_shared._slice_rows); tools/export_window_phase_tables.py '
                                             '(per family x split x metric tables at window x phase grain with labelled GROUP_/TREND_ '
                                             'aggregates); tests; 34 pass',
                  'commits_reviewed_2026-10-17': ['20de6db (review patch 2026-10-15 adopted: hash-verified resources, uniform execution, '
                                                  'family summaries, per-seed PatchTST launcher, grain verifier, energy window)',
                                                  'e8ada48 (train_history kept for train_seconds/epochs_run)',
                                                  'f989540 (canonical S_leak overlay suffix fix in the exporter)',
                                                  'd8e9670 (tools/audit_prefix_validation_alignment.py: static list with dispositions, '
                                                  'prefix mask sample, static parity, cohorts by row order, W1 P1-P4 table)',
                                                  'e17ae6e (export_w1_phase_validation_test_table.py; split_rule_version excluded in '
                                                  'model.data + test)',
                                                  '46f55d3, c519737, 04a0db8, d449831 (ingest/export generalised to CQ via VASTAI_TASK, '
                                                  'VASTAI_FAMILIES, VASTAI_INGEST_ID; ingest_id partition; CQ post-hoc audit launcher)'],
                  'test_status_d449831': '2 of 21 tests fail (tests/test_vastai_ingest_and_verify.py: the modal stub lacks Image.env() '
                                         'added in c519737); fixed in review patch 2026-10-17b (26 pass)',
                  'access_note_2026-10-17': 'the repository was unreadable from the review session earlier on 2026-10-17 (private); '
                                            'public again at 13:30 UTC+7 and reviewed to d449831',
                  'review_patches_pending': ['review_patches_2026-10-17b.patch (on d449831; supersedes 2026-10-17): '
                                             'LO/registries.py STATIC_FEATURE_CONTRACT (15 fields: definition, availability, grain, '
                                             'disposition, course_fingerprint_fields) exported with the registries; '
                                             'audit_prefix_validation_alignment.py reads it, reports macro-F1 under the fixed-K and the '
                                             'present-class convention side by side and gains --full-scan; tools/probe_static_only.py '
                                             '(static-only logistic probe ALL_STATIC / COURSE_FINGERPRINT / NON_COURSE on TRAIN -> '
                                             'VALIDATION, TEST with the majority reference); tools/audit_static_columns.py with '
                                             '--allowlist-from-registry; modal stub fix; registry note fix; 26 tests pass'],
                  'review_patch_2026-10-15_status': 'adopted in 20de6db (four files verbatim; ingest and exporter extended by the team)',
                  'not_in_repository_2026-10-21': ['the LO ablation report (LO/docs/REPORT_LO_..._ABLATION.docx) and its '
                                                   'ablation_comparison.csv (results exist locally, not delivered to the author)'],
                  'resolved_since_2026-10-19': ['report generators and maintenance scripts committed (tools/generate_*, build_*, '
                                                'update_*, report_maintenance/)', 'runner sha of the batch-2048 CQ grid reported '
                                                '(sha256:10cd38a2...)', 'tools/audit_lo_split_rule_history.py committed',
                                                'two-ingest merge replaced by two receipts (RNN historical layout; three families r2)'],
                  'resolved_since_2026-10-17': ['tools/vastai_audit_w1.py committed', 'CQ full-scan prefix audit reproducible with '
                                                'audit_prefix_validation_alignment.py --task CQ --full-scan', 'two-ingest merge no longer '
                                                'needed: the batch-2048 CQ grid is one ingest (vastai_cq_f1_batch2048_seed42_slice_r2_20261019)'],
                  'previous_commits_reviewed': ['dff9a3f (2026-10-05)', '799cf9e (registry identity + subgroup rule)',
                                                'c07e02c (release uploader, 2026-10-06)', '67e248c..548d4d4 (PatchTST, MOMENT, 2026-10-11)',
                                                'c2856d2, 640be01 (channel-independent PatchTST, phase-as-patch MOMENT, '
                                                'TEMPORAL_FAMILY_POLICY, VastAI runner, 2026-10-12)',
                                                '813e7ea (guard adopted, F3 subset fixed, math SDP, 2026-10-13)',
                                                'b5f55fe (scoped SDP, VastAI provenance + vocabulary, 2026-10-13)',
                                                '265415d, be110a4 (accumulation, seed check, MOMENT deferred, 2026-10-13)',
                                                'ce0486e, 23ea1f5, 294a17d (VastAI tooling, power sampler, L2 ingest/export, 2026-10-15)'],
                  'team_registry_revision': 'registries_rev_2026-10-14_r1 (LO/registries.py @ 294a17d; PATCHTST accumulation fields adopted)',
                  'relation': 'this file is the tested reference copy; LO/registries.py is the registry the workers import'}

# ---------------------------------------------------------------------------------------------
# Release identities (release_core/contracts.RELEASE_SPECS @ dff9a3f). Every worker validates the uploaded
# release_manifest.json against these strings; the registry must use the same strings, not paraphrases.
# ---------------------------------------------------------------------------------------------
RELEASE_SPECS = {
    'CQ_V2_2': {'task': 'CQ', 'input_dir': 'CQ_v2_2', 'split_version': 'v2_2', 'phase_version': 'wide_prefix_v2_2',
                'phase_views_dir': 'phase_views_v2_2', 'test_prefix_views_dir': 'test_prefix_views_v2_2',
                'split_registry_id': 'split_registry_v2_2_overlap_audit_v1_r2',
                'label_rule_version': 'cq_vector_proximity_v1_zero_activity_policy',
                'label_threshold_set': 'CQ_VECTOR_PROXIMITY_PRIMARY_V1'},
    'LO_V3_1': {'task': 'LO', 'input_dir': 'LO_v3_1', 'split_version': 'v3_1', 'phase_version': 'wide_prefix_v3_1',
                'phase_views_dir': 'phase_views_v3_1_scored_signal_excluded',
                'test_prefix_views_dir': 'test_prefix_views_v3_1_scored_signal_excluded',
                'split_registry_id': 'split_registry_v3_1_scored_signal_excluded_overlap_audit_v1',
                'label_rule_version': 'lo_final_score_catalog_normalized_v3_1',
                'label_threshold_set': 'CATALOG_NORMALIZED_PRIMARY_V3_1__EXCLUDE_NO_SCORED_SIGNAL'},
}
FEATURE_SOURCE = {
    'active': 'cumulative_phase_features_v2',
    'grain': 'wide_prefix: exactly one row per enrollment_id with cumulative P1-P4 column blocks (analytical_unit = enrollment_id, '
             '11,807,090 rows); materializers raise if exact duplicates are collapsed on this source',
    'forbidden': {'cumulative_phase_features_v1': 'two exact copies of every row (23,614,180 -> 11,807,090 after dedupe) '
                                                  'produced the 2x grain of the GD1 views [R1_C9]'},
    'consequence_for_gd1': 'every GD1 (seed 42 RNN) number was computed on doubled rows: point estimates ~unchanged, '
                           'n_support and bootstrap CI wrong by ~sqrt(2); GD1 results are superseded by the re-run on v2',
}

# ---------------------------------------------------------------------------------------------
# Pipeline registry V0–V16 (PLAN Table 7 / Table 14)
# ---------------------------------------------------------------------------------------------
IMPUTERS = [('NONE', 'V0'), ('MEDIAN', 'V1'), ('MEAN', 'V5'), ('EXTRATREES', 'V9'), ('MICE', 'V13')]
BALANCERS = ['NONE', 'CDSMOTE', 'SASMOTE', 'RADIUS_SMOTE']
IMPUTER_FAMILY = {'NONE': 'NONE', 'MEDIAN': 'UNIVARIATE', 'MEAN': 'UNIVARIATE',
                  'EXTRATREES': 'MULTIVARIATE_MODEL', 'MICE': 'MULTIVARIATE_MODEL'}

V0_FILL_RULE = {
    'rule_id': 'ZERO_RAW_PRE_TRANSFORM',
    'fill_value': 0.0,
    'fill_space': 'RAW',                      # RAW | POST_LOG | POST_SCALE
    'applies_to': 'OBSERVED_MISSING_ONLY',
    'future_unavailable': {'fill_value': 0.0, 'mask': 'M_available=0'},
    'note': 'Filled before log transform and RobustScaler; carries "no activity" semantics for counts; '
            'M_missing=1 keeps the cell distinguishable from a real zero.',
}
SAMPLING_STRATEGY = {
    # Decided 2026-09-27 (Phuong_an_sampling_strategy.docx): IR target with a per-class expansion cap.
    'primary': {'sampling_strategy_id': 'IR10_K10', 'type': 'IR_TARGET_WITH_CAP', 'ir_target': 10, 'max_expansion_per_class': 10,
                'rule': 'n_target_c = min(max(n_c, ceil(n_max / ir_target)), max_expansion_per_class * n_c); majority never undersampled',
                'decided_on': '2026-09-27', 'basis': 'Phuong_an_sampling_strategy.docx; tempo_fix.sampling.plan_targets'},
    'sensitivity': [
        {'sampling_strategy_id': 'IR5_K20', 'type': 'IR_TARGET_WITH_CAP', 'ir_target': 5, 'max_expansion_per_class': 20},
        {'sampling_strategy_id': 'IR20_K5', 'type': 'IR_TARGET_WITH_CAP', 'ir_target': 20, 'max_expansion_per_class': 5},
    ],
    # Targets are always recomputed from the real TRAIN pool of the window (sampling.targets_from_registry);
    # the counts below are the reference values used in the plan text and in the sampling note.
    'reference_train_pools': {
        'CQ': {'W1': {'c0': 1576716, 'c1': 19394, 'c2': 13166}, 'source': '[CL §7.5] CQ W1 train (block A), release V1 population 2,684,090'},
        'LO': {'W1': {'c0': 1782182, 'c1': 4720, 'c2': 655}, 'W2': {'c0': 1936554, 'c1': 5777, 'c2': 1907},
               'W3': {'c0': 2338176, 'c1': 5823, 'c2': 1925},
               'source': '[V3.1 §6.1] LO train pools under lo_final_score_catalog_normalized_v3_1 (c1, c2 identical to V3; '
                         'c0 smaller by the excluded courses); replaces the June 2026 counts (c0 2,947,015 / c1 8,886 / '
                         'c2 31,441) used in Phuong_an_sampling_strategy.docx'},
    },
    'v3_consequence': 'Under LO V3.1 the max_expansion_per_class = 10 cap binds for c1 and c2 in every window: post-sampling IR '
                      'is 37.8/272.1 (W1), 33.5/101.5 (W2), 40.2/121.5 (W3) for c1/c2 instead of approaching ir_target '
                      '[V3.1 §6.1]. The reason for the cap (synthetic share <= 90% of a class) is unchanged, so the primary '
                      'scheme is kept; the consequence table in PLAN §2.3 and the sampling note must be rewritten with these numbers.',
    'status': 'PRIMARY_CONFIRMED 2026-10-01 [V3.1 §6]',
}
# Values below are the executable contract of release_core/runtime_config.py @ dff9a3f [RT]; they supersede the
# PLAN v1.6 starting values (MICE max_iter 10; ExtraTrees 100 trees; k_neighbors 5; radius_quantile 0.5).
MICE_PARAMS = {'max_iter': 3, 'tol': 1e-3, 'fit_sample_rows': 1000000, 'initial_strategy': 'constant', 'fill_value': 0.0,
               'sample_posterior': False,
               'internal_scaler': 'RobustScaler(train_only, inverse_transform_before_output)',
               'sparse_predictor_fallback': 'train_median (0 if all missing)',
               'report': 'trpool_post_fallback_rate',
               'fit_sample_rule': 'IterativeImputer fitted on a seeded sample of at most 1,000,000 TRAIN rows (seed_preprocess), '
                                  'then transform applied to every row; locked for the whole grid [RESP]',
               'source': '[RT] MICE; supersedes PLAN v1.6 max_iter 10 / constant_zero_first_round_only'}
EXTRATREES_PARAMS = {'n_estimators': 1, 'max_depth': 5, 'max_iter': 1, 'n_jobs': -1, 'initial_strategy': 'median',
                     'source': '[RT] EXTRA_TREES = TEMPO extra-trees light baseline; supersedes PLAN v1.6 100 trees / depth None'}
BALANCER_PARAMS = {
    'CDSMOTE': {'n_clusters': 5, 'within_cluster_interpolation': True,
                'source': '[RT] BALANCERS.CDSMOTE; k-means clusters of the minority class, interpolation inside a cluster'},
    'SASMOTE': {'visible_k': 16, 'max_inspectors': 4, 'inspector_trees': 16, 'inspector_n_jobs': 8, 'uncertainty_threshold': 0.5,
                'candidate_batch_size': 262144, 'max_candidate_rounds': 32,
                'neighbour_rule': 'n_neighbors = min(visible_k, n_minority - 1)',
                'source': '[RT] BALANCERS.SASMOTE'},
    'RADIUS_SMOTE': {'radius': 0.092, 'radius_space': 'scaled_numeric_model_input',
                     'fallback_audit': 'fallback_nearest_neighbour_rate recorded per run; > 0.50 raises a warning in the ledger '
                                       '(radius too small for that class), see POST_MATERIALIZE_CHECKS[5]',
                     'source': '[RT] BALANCERS.RADIUS_SMOTE; supersedes PLAN v1.6 radius_quantile 0.5'},
}


def build_pipeline_registry(sampling: Dict = SAMPLING_STRATEGY['primary']) -> List[Dict]:
    rows = []
    vid = 0
    for imp, imp_only in IMPUTERS:
        for bal in BALANCERS:
            if imp == 'NONE' and bal != 'NONE':
                continue                       # SMOTE needs NaN-free data (PLAN §2.3)
            pid = f'V{vid}'
            name = 'V0-Raw' if pid == 'V0' else f'{pid}-' + '-'.join(
                x for x in (imp.title().replace('Extratrees', 'ExtraTrees').replace('Mice', 'MICE'),
                            {'NONE': '', 'CDSMOTE': 'CDSMOTE', 'SASMOTE': 'SASMOTE', 'RADIUS_SMOTE': 'RadiusSMOTE'}[bal]) if x)
            imputer_params = {'NONE': V0_FILL_RULE, 'MEDIAN': {'strategy': 'median'}, 'MEAN': {'strategy': 'mean'},
                              'EXTRATREES': EXTRATREES_PARAMS, 'MICE': MICE_PARAMS}[imp]
            balancer_params = None if bal == 'NONE' else {**BALANCER_PARAMS[bal], **sampling}
            row = {
                'pipeline_id': pid, 'pipeline_name': name, 'imputer': imp, 'balancer': bal,
                'imputer_family': IMPUTER_FAMILY[imp], 'balancer_family': 'NONE' if bal == 'NONE' else 'SMOTE_VARIANT',
                'is_no_intervention': int(pid == 'V0'), 'has_imputation': int(imp != 'NONE'), 'has_balancing': int(bal != 'NONE'),
                # N10 (author decision 2026-10-24): a pipeline without balancer is its own imputer-only reference, so that
                # delta_imp = delta and delta_bal = 0 for V1/V5/V9/V13 (Meta-Dataset-Report Table 14 to be corrected accordingly)
                'before_ref': 'V0', 'imputer_only_ref': pid if bal == 'NONE' else imp_only,
                'fit_scope': 'TRAIN_POOLED_P1_P4', 'impute_scope': 'OBSERVED_MISSING_ONLY',
                'v0_fill_rule': V0_FILL_RULE['rule_id'], 'seed_preprocess': SEED_PREPROCESS,
                'synthetic_phase_rule': 'SAME_PHASE_ONLY', 'synthetic_mask_rule': 'INTERSECTION_OF_PARENTS',
                'sampling_strategy_id': None if bal == 'NONE' else sampling['sampling_strategy_id'],
                'imputer_params': imputer_params, 'balancer_params': balancer_params,
            }
            row['imputer_params_hash'] = sha256_of(imputer_params)
            row['balancer_params_hash'] = sha256_of(balancer_params) if balancer_params else None
            rows.append(row)
            vid += 1
    assert vid == 17, vid
    return rows


def validate_pipeline_registry(rows: List[Dict]) -> None:
    ids = [r['pipeline_id'] for r in rows]
    assert ids == [f'V{i}' for i in range(17)], ids
    by = {r['pipeline_id']: r for r in rows}
    # PLAN Table 14 mapping with the N10 correction of 2026-10-24 (imp(a) = a for imputation-only pipelines)
    expect = {'V2': 'V1', 'V3': 'V1', 'V4': 'V1', 'V6': 'V5', 'V7': 'V5', 'V8': 'V5', 'V10': 'V9', 'V11': 'V9',
              'V12': 'V9', 'V14': 'V13', 'V15': 'V13', 'V16': 'V13', 'V1': 'V1', 'V5': 'V5', 'V9': 'V9', 'V13': 'V13', 'V0': 'V0'}
    for k, v in expect.items():
        assert by[k]['imputer_only_ref'] == v, (k, by[k]['imputer_only_ref'], v)


# ---------------------------------------------------------------------------------------------
# Model registry (PLAN Table 8, §2.4; v1.6: selection metric, mandatory channels)
# ---------------------------------------------------------------------------------------------
INPUT_CHANNELS = ['X', 'M_missing', 'M_available', 'delta_t', 'phase_id', 'observed_length']
PHASE_MASK_BASES = ('phase_available', 'video_observed_mask', 'problem_observed_mask', 'comment_observed_mask')
MODEL_REVISION = 'recurrent_shared_phase_v2_4_prefixsafe_epoch50'
COMMON_HPARAMS = {'hparam_config_id': 'HP_RNN_FAMILY_v1', 'loss_name': 'cross_entropy', 'class_weighting': 'NONE',
                  # values of release_core/runtime_config.MODEL @ dff9a3f [RT]; PLAN v1.6 batch_size 256 superseded
                  'lr': 1e-3, 'weight_decay': 1e-5, 'batch_size': 2048, 'max_epochs': 50, 'early_stopping_patience': 5,
                  'hidden_size': 128, 'num_layers': 1, 'dropout': 0.3, 'dataloader_workers': 4,
                  'precision_policy': 'bf16_amp', 'amp_dtype': 'bfloat16', 'logits_loss_dtype': 'float32', 'gpu_type': 'L4',
                  'selection_metric': 'MEAN_PHASE_MACRO_F1', 'selection_tiebreak': 'MEAN_PHASE_CROSS_ENTROPY_MIN',
                  'selection_log': ['selection_margin', 'selected_epoch', 'n_checkpoints_within_margin'],
                  'training_sequence': 'P1_P2_P3_P4 (one model per cell, checkpoint shared by the four phases)',
                  'determinism': 'torch.use_deterministic_algorithms(True) with CUBLAS_WORKSPACE_CONFIG=:4096:8 set before the '
                                 'first CUDA call; acceptance = two runs of the V0 W1 L4 pilot with identical metrics [RESP]',
                  'model_revision': MODEL_REVISION,
                  'phase_mask_bases': list(PHASE_MASK_BASES),
                  'phase_mask_rule': 'phase_available and the *_observed_mask columns enter as per-timestep dynamic channels, '
                                     'never as static features, so a prefix P_k carries no information about phases > k',
                  'bidirectional_prefix_rule': 'BiLSTM output at step k is recomputed from the prefix 1..k only (one backward pass '
                                               'per prefix); the plain forward LSTM/GRU/RNN need no recomputation'}
MODEL_REGISTRY = [
    {'model_name': 'CQ_PARTIAL_TRIAD', 'model_tier': 'F0_REFERENCE', 'model_family': 'DETERMINISTIC', 'variant_role': 'REFERENCE', 'task': 'CQ'},
    {'model_name': 'LO_HEURISTIC_PROGRESS_GRADE', 'model_tier': 'F0_REFERENCE', 'model_family': 'DETERMINISTIC', 'variant_role': 'REFERENCE', 'task': 'LO'},
    {'model_name': 'RNN', 'model_tier': 'F1_RECURRENT', 'model_family': 'RNN', 'variant_role': 'PRIMARY'},
    {'model_name': 'LSTM', 'model_tier': 'F1_RECURRENT', 'model_family': 'LSTM', 'variant_role': 'PRIMARY'},
    {'model_name': 'GRU', 'model_tier': 'F1_RECURRENT', 'model_family': 'GRU', 'variant_role': 'ROBUSTNESS'},
    {'model_name': 'BILSTM', 'model_tier': 'F1_RECURRENT', 'model_family': 'LSTM', 'variant_role': 'ROBUSTNESS'},
    {'model_name': 'PATCHTST', 'model_tier': 'F2_TS_TRANSFORMER', 'model_family': 'PATCHTST', 'variant_role': 'PRIMARY',
     'max_seq_len': 4, 'patch_len': 2, 'patch_stride': 1, 'transformer_layers': 2, 'attention_heads': 4, 'd_model': 128, 'dim_feedforward': 512,
     'channel_mixing': False, 'channel_aggregation': 'flatten_after_shared_encoder', 'hparam_config_id': 'HP_PATCHTST_CHANNEL_INDEPENDENT_v2',
     'hparam_candidate_2026-10-26': {'candidate_id': 'HP_PATCHTST_CHANNEL_INDEPENDENT_v3_D23_CANDIDATE',
                                     'learning_rate': 3e-4, 'warmup_epochs': 1, 'gradient_clip_norm': 1.0,
                                     'batch': '2048 = 4 x 512', 'static_layout_policy': 'current',
                                     'run_purpose': 'STABILITY_PILOT_D23',
                                     'status': 'NOT REGISTERED: two pilot runs (CQ W2/V0, W3/V0, seed 42, 26/10) exist; the registered '
                                               'protocol of every primary grid remains lr 1e-3 without warm-up or clipping until the '
                                               'author decides PENDING_DECISIONS[23]; a run under the candidate carries '
                                               'run_purpose STABILITY_PILOT_D23 and never enters L2',
                                     'status_2026-10-28': 'SENSITIVITY PILOT ONLY: the team reports that the W3 VALIDATION history under '
                                                          'the candidate is not unimodal and the selected epoch stays at 1, so the '
                                                          'registered D-23 (b) criterion fails; the history itself was not delivered'},
     'optimisation_protocol_lock_2026-10-27': {'protocol_id': 'HP_PATCHTST_CHANNEL_INDEPENDENT_v2', 'learning_rate': 1e-3,
                                               'warmup_epochs': 0, 'gradient_clip_norm': None, 'run_purpose': 'PRIMARY_GRID',
                                               'locked_by': 'team, LO/registries.py @ 29da3b2 (MODEL_REGISTRY.optimisation_protocol and '
                                                            'TEMPORAL_FAMILY_POLICY.F2.seed42_optimisation_protocol)',
                                               'status': 'TEAM-LOCKED; equals option (a) of PENDING_DECISIONS[23] and the protocol the F2 '
                                                         'gate, the shard verifier and the ingest already enforce; author ratification '
                                                         'pending; the repository key names seed 42 only although the protocol applies to '
                                                         'the three master seeds'},
     'model_revision': 'patchtst_channel_independent_v2_1_math_sdp',
     'attention_backend': 'math SDP scoped to the encoder call with torch.nn.attention.sdpa_kernel (b5f55fe); fused flash/mem-efficient '
                          'kernels reject B x C sequences (CQ: 274 channels)',
     'memory_note': 'B x C = 2048 x 274 sequences with four prefix passes do not fit a 24 GB L4 for training; the team piloted with '
                    'batch 512; gradient accumulation 4 x 512 (review patch 2026-10-13b, adopted in 265415d) keeps the registered '
                    '2048-row optimiser step (PENDING_DECISIONS[14])',
     'optimisation_batch_size': 2048, 'micro_batch_size': 512, 'accumulation_steps': 4,
     'implementation_note': 'CD3 @ c2856d2 (decision 12, option (a)): every dynamic channel is patched as [values, validity] with a '
                            'projection and Transformer shared across channels (B x C sequences of 1..3 patch tokens), learned position '
                            'embedding, mean over tokens, then the C post-encoder embeddings are concatenated with the static branch '
                            'in a linear head (C x 128 + static inputs; CQ: 274 x 128 = 35,072). Verified 2026-10-12/13: prefix logits '
                            'identical from truncated and full inputs, P3/P4 perturbation leaves P1/P2 unchanged, encodings of channels '
                            '1..C-1 unchanged when channel 0 changes, training converges; the channel-mixing v1 token is superseded'},
    {'model_name': 'MANTIS_V2', 'model_tier': 'F3_TS_FOUNDATION', 'model_family': 'MANTIS', 'variant_role': 'EXPLORATORY', 'is_pretrained': 1,
     'finetune_mode': 'LINEAR_PROBE', 'encoder_frozen': 1, 'pretrained_repo': 'paris-noah/MantisV2',
     'pretrained_revision': '8f6ca35cb54ab14b120618943c6fca5ddf5a76a6',
     'pretrained_revision_note': 'Hugging Face API read on 2026-11-06 (lastModified 2026-08-21T09:56:46Z, card licence apache-2.0, safetensors '
                                 '4,188,690 values); the pilot re-reads the sha and records the snapshot file sha256 (check 37 (a))',
     'library': 'mantis-tsfm==1.1.0', 'library_revision': 'mantis-tsfm 1.1.0, wheel sha256 accdaf2e44d263b23913fc914e00d5d0d37d41d70590ba34d70883f21b40a55f',
     'licence': 'Apache-2.0 (PyPI package; model-card metadata at the pinned revision)',
     'pretraining_data': 'synthetic only (CauKer, 2 million series), so no overlap with MOOCCubeX is possible',
     'references': ['Feofanov et al., Mantis: Lightweight Foundation Model for Time Series Classification, ICML 2026, PMLR 306:30692-30719',
                    'Feofanov et al., MantisV2, arXiv:2602.17868 (2026)'],
     'param_count_backbone_total': 4188672, 'param_count_backbone_used': 2214144, 'return_transf_layer': 2, 'output_token': 'combined',
     'embedding_dim_per_series': 512, 'num_patches': 32, 'interp_len': 512, 'interp_mode': 'linear', 'interp_align_corners': False,
     'interp_constant_rows': 'a component whose k values are all equal is replicated exactly instead of interpolated (keeps the '
                             'constant-series guard exact on kernels that compute w0 x0 + w1 x1, such as CUDA)',
     'input_encoding': 'PCA8_PER_PHASE_THEN_LINEAR_RESIZE_512_v1',
     'channel_adapter': {'method': 'PCA_ACROSS_CHANNELS', 'n_components': 8, 'standardize': True, 'fit_rows': 'REAL_TRAIN_ROWS_ONLY',
                         'fit_vectors': 'every phase step of the selected rows (P1..P4 pooled)', 'sample_rows_max': 1000000,
                         'sample_seed': 20260922, 'solver': 'eigh of the float64 covariance of standardised channels',
                         'sign_rule': 'largest absolute loading of every component is positive (ties: lowest channel index)',
                         'fit_order': 'rows sorted by row id before sampling and accumulation (independent of the frame order); '
                                      'sha256 of the fitted rows stored with the adapter and checked by later imputer-only cells'},
     'constant_series_rtol': 1e-6,
     'constant_series_guard': 'instance normalisation returns exact zeros when std <= 1e-6 * (|mean| + 1e-6) over the resized series (rule '
                              'of MOMENT revision v2_1); bit-identical to the official expression otherwise; measured without the guard on '
                              'CPU: pseudo-signal 0.0015 for a constant 0.1 and 0.046 for a constant 3.3',
     'embedding_reduction': 'concatenate the 8 component embeddings (8 x 512 = 4096 values per row and prefix)',
     'head_inputs': ['standardised MantisV2 embeddings (4096)', 'standardised static block', 'phase one-hot (4)'],
     'head': 'Dropout(0.3) + Linear(4096 + static_dim + 4 -> 3); one head for P1..P4',
     'embedding_cache': {'level_A': 'per (task, window, imputer pipeline, adapter digest): REAL_TRAIN, VALIDATION, TEST',
                         'level_B': 'per (task, window, balanced pipeline, master seed): synthetic TRAIN rows only',
                         'fallback': 'CELL_TRAIN when the real rows of a balanced cell differ from the imputer-only TRAIN (ids or input sha256)',
                         'dtype': 'float16',
                         'key': 'adapter digest + encoder fingerprint (sha256 of the truncated backbone weights, encoding settings, '
                                'precision, microbatch, device)',
                         'reuse_rule': 'every entry (level A, level B, CELL_TRAIN) is reused only when ids and the sha256 of its input '
                                       'tensor match; an existing entry built from other rows stops the run'},
     'weight_loading': 'strict key-by-key load of the pinned snapshot (state dict 4,188,690 values); run_cell refuses a '
                       'random-weight backbone',
     'microbatch_sequences': 4096, 'attention_backend': 'MATH (scoped torch.nn.attention.sdpa_kernel)',
     'backbone_precision': 'bf16 autocast on CUDA; embeddings stored as float16; head in fp32',
     'model_revision': 'mantisv2_frozen_linear_probe_v1_pca8_interp512', 'hparam_config_id': 'HP_MANTISV2_FROZEN_LINEAR_PROBE_v1_pca8',
     'max_seq_len': 4, 'patch_len': 16, 'patch_stride': 16,
     'cost_note_2026-11-06': 'one backbone series costs 160.7 MFLOPs (torch.utils.flop_counter, truncated network, 512 points), the same '
                             'order as MOMENT-1-small under phase-as-patch (40-80 MFLOPs per token x 4 tokens); the saving comes from the '
                             '8-component adapter (CQ: 274 channels -> 8, 34x fewer series) and from the cache, not from the backbone; CQ '
                             'W1 REAL_TRAIN = 1,609,276 rows x 8 x 4 = 51.5 million series per pass; cache 52.7 GB float16',
     'implementation': 'writing-side package f3_mantis 0.1.0 (working/Data and Code/f3_mantis_v0.1.0_2026-11-06, 33 tests + 1 registry test; '
                       'independent code review on 2026-11-06 before delivery: every cache entry verified by ids and input sha256 and '
                       'keyed by the encoder fingerprint, strict weight loading, random-weight backbone refused, adapter keyed by '
                       'task/window/imputer and fitted in row-id order, channel layout checked, equal phase values replicated before '
                       'resizing); '
                       'the team integrates it (model/architectures.py, model/config.py, CQ|LO/model/mantis_v2/config.py, LO/registries.py, '
                       'tools/vastai_train_f3_mantis.py)',
     'replaces': 'MOMENT_SMALL (exploratory) and MOMENT_BASE (deferred), decision 37 of 2026-11-06'},
]
for _m in MODEL_REGISTRY:
    if _m['model_tier'] != 'F0_REFERENCE':
        # Shared training contract for every learned model; a row's own values (model_revision, patch/encoder
        # parameters of F2/F3) take precedence over the F1 defaults in COMMON_HPARAMS. The six-channel loader of
        # PLAN v1.6 §2.4 is realised by the common tensor of model/data.py (numeric channels, four per-step mask
        # bases, missing__ indicators under V0, phase_id fraction and delta_t), shared by F1, F2 and F3.
        defaults = {'input_channels': INPUT_CHANNELS, 'uses_mask_channels': 1, 'uses_delta_t': 1, 'uses_phase_id': 1,
                    'uses_observed_length': 1, 'identifier_embeddings': 0, **COMMON_HPARAMS}
        _m.update({k: v for k, v in defaults.items() if k not in _m})

# F3 rows retired on 2026-11-06 (decision 37). Kept verbatim for provenance: no F3 cell was run into L2 or read; the
# family_smoke / family_screen runs of CD3 @ 548d4d4 never entered L2. Not exported as part of model_registry.
RETIRED_MODEL_ROWS = [
    {'model_name': 'MOMENT_SMALL', 'model_tier': 'F3_TS_FOUNDATION', 'model_family': 'MOMENT', 'variant_role': 'PRIMARY', 'is_pretrained': 1,
     'finetune_mode': 'LINEAR_PROBE', 'pretrained_repo': 'AutonLab/MOMENT-1-small', 'pretrained_revision': '43ee05b',
     'library_revision': 'momentfm @ 38f7310', 'pretrained_patch_len': 8,
     'input_encoding': 'PHASE_AS_PATCH_REPEAT_v1_1 (phase-as-patch adopted in c2856d2, constant-channel guard adopted in 813e7ea; '
                       'v1 right-padding produced NaN embeddings)',
     'revin_statistics_fusion': True, 'embedding_reduction': 'mean_over_channels_then_mean_over_observed_patches',
     'constant_channel_guard': 'zero_input_when_prefix_std_below_1e-6_relative (RevIN divides by std + 1e-5; float32 rounding of a '
                               'constant channel would otherwise enter the encoder as pseudo-signal of order 1e-2)',
     'model_revision': 'moment_frozen_linear_probe_v2_1_phase_patch', 'hparam_config_id': 'HP_MOMENT_FROZEN_LINEAR_PROBE_v2_1_phase_patch',
     'variant_role_proposed_by_team': 'EXPLORATORY (640be01; Appendix D2 says PRIMARY; awaiting author ratification)'},
    {'model_name': 'MOMENT_BASE', 'model_tier': 'F3_TS_FOUNDATION', 'model_family': 'MOMENT', 'variant_role': 'PRIMARY', 'is_pretrained': 1,
     'finetune_mode': 'LINEAR_PROBE', 'pretrained_repo': 'AutonLab/MOMENT-1-base', 'pretrained_revision': 'b0ae575',
     'library_revision': 'momentfm @ 38f7310', 'pretrained_patch_len': 8,
     'input_encoding': 'PHASE_AS_PATCH_REPEAT_v1_1 (adopted in c2856d2 / 813e7ea)', 'revin_statistics_fusion': True,
     'embedding_reduction': 'mean_over_channels_then_mean_over_observed_patches',
     'constant_channel_guard': 'zero_input_when_prefix_std_below_1e-6_relative',
     'model_revision': 'moment_frozen_linear_probe_v2_1_phase_patch', 'hparam_config_id': 'HP_MOMENT_FROZEN_LINEAR_PROBE_v2_1_phase_patch',
     'variant_role_proposed_by_team': 'DEFERRED from GD1 (640be01; awaiting author ratification)'},
]
for _m in RETIRED_MODEL_ROWS:
    _m.update({'retired_on': '2026-11-06', 'retired_by': 'PENDING_DECISIONS[37]', 'replaced_by': 'MANTIS_V2'})

# ---------------------------------------------------------------------------------------------
# Metric, sanity, AccTEMPO and recommendation definitions
# ---------------------------------------------------------------------------------------------
METRIC_DEF = {
    'metric_def_version': 'metric_def_v1.3',
    'v1_3_change_2026-10-24': {
        'authority': 'author ratification D-18 of 2026-10-24 (AUTHOR_RATIFICATIONS_2026_10_24); registered here on 2026-10-25',
        'names': {'acctempo_m3': 'AccTEMPO_M3 (S_san+ v1): pre-registered primary of the meta-dataset, kept as the sensitivity '
                                 'objective of every paper test',
                  'acctempo_m3_cal': 'AccTEMPO_M3^(cal) = clip(S_perf, 1e-3)^0.6 x clip(S_san+ v2, 1e-3)^0.4 (S_san+ v2: s_cal '
                                     'replaces s_ent); exporter column acctempo_m4 (5b14052); the composite objective of the paper'},
        'objectives': {'PAPER_COMPOSITE_CAL': 'acctempo_m3_cal', 'PAPER_PERF_AXIS': 's_perf',
                       'META_PRIMARY_M3_V1': 'acctempo_m3', 'SECONDARY_MACRO_F1': 'macro_f1'},
        'default_objective': 'PAPER_COMPOSITE_CAL',
        'hypothesis_objectives': {'H1': 'PAPER_COMPOSITE_CAL', 'H2': 'PAPER_COMPOSITE_CAL', 'H3': 'PAPER_COMPOSITE_CAL',
                                  'H4': 'PAPER_COMPOSITE_CAL', 'H5': 'PAPER_COMPOSITE_CAL', 'H6': 'PAPER_COMPOSITE_CAL',
                                  'H7': 'PAPER_COMPOSITE_CAL vs SECONDARY_MACRO_F1', 'H8': 'PAPER_COMPOSITE_CAL'},
        'sensitivity_objective': 'META_PRIMARY_M3_V1',
        'trend_and_ranking_rule': 'phase trends (P1 -> P4) and family or pipeline rankings in the paper are read on S_perf, macro-F1 '
                                  'and balanced accuracy; both composites are printed next to them; neither composite carries a W2 '
                                  'trend (s_leak of the V0 parent falls 0.232 -> 0.019 on CQ TEST W2)',
        'disclosure': 'the Method section states that the composite objective was changed after the seed-42 F1 results were read '
                      '(hedging reward of s_ent); the meta-dataset keeps v1 as pre-registered',
        'code_mirror': 'metamodel.contracts.OBJECTIVES / HYPOTHESIS_OBJECTIVES / SENSITIVITY_OBJECTIVE (v0.2.0) use the same names; '
                       'CQ/registries.CQ_METRIC_AND_QA23_POLICY (5b14052) records the same rule for the team; metrics_core still computes '
                       'acctempo_m3 only (M3^(cal) is derived in the exporters)',
        'evidence_2026-10-25': 'per-pipeline means over 12 window x phase cells (CQ TEST, R4): M3 spans 0.63-0.70 within every family '
                               'while M3^(cal) spans 0.737-0.747 and macro-F1 0.704-0.726; balanced minus imputation-only pipelines: '
                               'M3 +0.055 to +0.060, M3^(cal) +0.002 to +0.003, macro-F1 +0.001 to +0.003; Spearman(M3^(cal), S_perf) '
                               '0.94-0.98, Spearman(M3^(cal), macro-F1) 0.79-0.87, Spearman(M3, M3^(cal)) 0.54-0.66',
    },
    'class_index': {'CQ': {'c0': 'W', 'c1': 'A', 'c2': 'G'}, 'LO': {'c0': 'ID', 'c1': 'G', 'c2': 'E'}},
    'risk_class': 'c0',
    'majority_class': {'CQ': 'c0', 'LO': 'c0'},   # both tasks: the risk class is the majority class ([CL §7.5], [V3 §6])
    'macro_policy': 'FIXED_K_CLASSES',       # macro averages over all K classes (absent class -> NULL/CLASS_ABSENT)
    'zero_division': 'NULL',
    'macro_policy_code_status_2026-10-17': 'metrics_core/evaluation.py @ 294a17d computes macro_f1 with labels=CLASS_IDS and '
                                           'zero_division=0: an absent class contributes F1 = 0 instead of NULL, so a 3-class macro-F1 '
                                           'on a slice without one class is capped at 0.667; per-class metrics do return None for an '
                                           'absent class. Main TEST cells have every class present; slices (UNSEEN_COURSE in LO W1, '
                                           'STRICT/OVERLAP x phase) may not. Which convention the slice audit uses is unknown '
                                           '(POST_MATERIALIZE_CHECKS[17])',
    'acctempo_structure_note_2026-10-17': 's_ent = 1 - |median(normalised predictive entropy) - 0.5| / 0.5 rewards hedged '
                                          'predictions; on the 2026-10-16 seed-42 tables 92-98% (CQ) and 65-70% (LO) of the '
                                          'log-range of AccTEMPO across the 17 pipelines comes from S_san+, almost entirely via '
                                          's_ent, while macro-F1 is flat (CQ -0.002, LO +0.009 balanced vs imputer-only) and PR-AUC '
                                          'falls (-0.026 / -0.022). AccTEMPO_M3 v1 stays the preregistered primary; every table must '
                                          'show S_perf, S_san+ and s_ent next to it and v2 (s_cal) as the sensitivity '
                                          '(PENDING_DECISIONS[18])',
    'acctempo_m4_export_note_2026-10-23': 'acctempo_m4 = clip(S_perf, 1e-3)^0.6 x clip(S_san+_v2, 1e-3)^0.4 with S_san+_v2 = '
                                          'geometric mean of (s_nan, s_maj_jsd, s_cal, s_drift, s_eff, s_leak), computed read-only in '
                                          'tools/export_cq_recurrent_grid_report.py and build_cq_current_recurrent_patchtst_report.py '
                                          '(5b14052), not in metrics_core; it is the sensitivity composite of CQ_METRIC_AND_QA23_POLICY. '
                                          'M4 removes the hedging term but keeps s_leak, which for the V0 parent at W2 falls 0.232 (P1) '
                                          '-> 0.019 (P4) on TEST (identical for PatchTST and the recurrent V0 cells), so M4 also falls '
                                          'P1 -> P4 on W2 while macro-F1 rises; phase trends are read from S_perf / macro-F1 / balanced '
                                          'accuracy only, composites are reported next to them',
    'core_metrics': ['acctempo_m3', 's_perf', 'macro_f1', 'balanced_acc', 'mcc', 'kappa', 'pr_auc_macro', 'gmean'],
    'extended_metrics': ['accuracy', 'weighted_f1', 'roc_auc_macro_ovr', 'log_loss', 'brier', 'ece'],
    'ece_bins': 15, 'ece_type': 'top_label', 'probability_clip': 1e-12, 'prob_sum_tolerance': 1e-4,
    'per_class': ['precision', 'recall', 'specificity', 'f1', 'gmean', 'ap', 'support', 'predicted_count'],
    'bootstrap': {'B': 2000, 'unit': 'ENROLLMENT', 'ci': 0.95},
    # --- support and uncertainty policy locked 30/09/2026 ([CL §6], [V3 §6]; thresholds from Danh_gia_Split_V2.2_closure) ---
    'support_flags': {
        'small_support_flag': {'rule': 'n_support < 400', 'granularity': 'cell = (task, window, phase, eval_split, subgroup, class); '
                               'applies to the TEMPORAL STRICT/OVERLAP slice and to every mandatory subgroup',
                               'rationale': '95% CI of a proportion near 0.5 wider than +/-5 points',
                               'effect': 'per-class metrics kept, always reported with bootstrap CI; never used alone as pipeline evidence'},
        'small_subgroup_flag': {'rule': 'n_g < 30 or any class support < 5', 'source': '[PLAN §2.5]', 'kept_separately': True},
        'class_absent': {'rule': 'per-class metrics NULL with null_reason = CLASS_ABSENT; never 0 or interpolated'},
    },
    'pipeline_comparison': {'rule': 'paired_bootstrap_delta, B = 2000, unit ENROLLMENT; mandatory for every LO W2/W3 cell and '
                                    'for every cell with small_support_flag = 1'},
    # --- v1.2 additions locked 01/10/2026 [V3.1.2 §15.2] ---
    'probability_metrics_for_exploratory_windows': {
        'rule': 'log_loss and pr_auc_macro reported next to macro_f1 in every window whose minority cells all carry '
                'small_support_flag = 1 (currently LO W2); pr_auc_macro is NULL with null_reason = CLASS_ABSENT when a class is absent',
        'applies_to': {'LO': ['W2']}},
    'cluster_bootstrap': {
        'rule': 'when n_offerings_with_class <= 2 for a (cell, class), add an offering-cluster bootstrap CI: resample whole offerings '
                '(offering_id x timeline_source units) with replacement, B = 2000, ci = 0.95; the enrollment bootstrap is still reported',
        'known_cells': {'LO_W1_TEST_c2': '1,000 of 1,000 E from one offering', 'LO_W3_TEST_c1': '1,074 of 1,079 G from one offering'},
        'reason': 'positives from a single offering share one context; enrollment resampling understates the uncertainty'},
    'course_score_ceiling_observed': {
        'definition': 'highest PRIMARY final_score observed in the course over all its enrollments [V3.1.2 §14.1]',
        'role': 'CONTEXT_REPORT_ONLY', 'derived_from_labels': True, 'model_input': 'FORBIDDEN (uses labels of every enrollment, '
        'including evaluation ones)', 'use': 'post-hoc stratification: ceiling bands < 60, 60-85, >= 85; reported per slice and per cell'},
    'checkpoint_selection': {'metric': 'MEAN_PHASE_MACRO_F1', 'split': 'VALIDATION', 'tiebreak': 'MEAN_PHASE_CROSS_ENTROPY_MIN',
                             'log': ['selection_margin', 'selected_epoch', 'n_checkpoints_within_margin'],
                             'note': 'LO W1 VALIDATION minority classes come from a single offering (E 1,000 of 1,000; G 525) '
                                     '[V3 §6, §8]; read selection_margin before interpreting LO W1'},
    'prediction_level_context_columns': ['timeline_source', 'duration_days', 'long_offering_flag', 'label_threshold_set',
                                         'n_offerings_with_class', 'course_score_ceiling_observed'],
    'long_offering_flag': {'rule': 'offering duration > 270 days', 'source': '[CL §8], [V3 §8]',
                           'use': 'report-only stratification; not a filter; not a new mandatory subgroup'},
    'sanity_reporting': {'rule': 'S_san+ v1 (primary) and s_cal-based v2 (auxiliary) reported side by side in every cell with all '
                                 'components; the v1 s_ent component sits at the eps floor on 99.8-99.9%-majority slices (LO W2/W3), '
                                 'which is discussed with the v2 column but never used to re-rank pipelines [DEC §2]'},
    'small_subgroup_flag_implementation_note': 'CLOSED 2026-10-06: metrics_core.evaluation.classification_metrics @ 799cf9e applies the '
                                               'registered rule (n < 30 or any class support < 5); regression test '
                                               'tests/test_registry_release_alignment.py::test_small_subgroup_flag_follows_registered_rule; '
                                               'small_support_flag (< 400) lives in model/metrics.py',
}
S_SAN_FORMULA = {
    'v1': {'s_san_formula_version': 's_san_v1_jsd_base2_six_components',
           'components': ['s_nan', 's_maj_jsd', 's_ent', 's_drift', 's_eff', 's_leak'], 'aggregation': 'geometric_mean',
           's_eps_floor': 1e-3, 'jsd_base': 2,
           's_ent': '1 - min(|median(h_i) - 0.5| / 0.5, 1), h_i normalised entropy',
           's_eff': 'run-level: mean of the dynamic mask channels over the REAL TRAIN tensor of the parent imputation input '
                    '(model_inputs/train.parquet, pooled P1-P4); synthetic rows of a balanced artifact are excluded '
                    '(real-row contract, s_eff_definition_version model_input_mask_mean_v1) [DEC §2]',
           's_leak': '1 - 2*max(AUC_probe - 0.5, 0); probe = multinomial logistic regression on the per-phase mask matrix only; '
                     'fit once on the REAL TRAIN rows pooled over P1-P4 (probe_rows_per_phase 0 = all rows) and reused for every '
                     '(eval_split, phase) slice; record n_fit, n_eval, eval_split (real-row contract) [DEC §2]',
           's_drift_reference': 'TRAIN real class distribution before balancing (trpool_class_count)',
           's_maj_jsd_reference': 'true class distribution of the evaluated slice',
           'team_alignment_2026-10-31': 'LO/registries.py @ df2a867 rewrote its s_eff and s_leak sentences to this real-row contract '
                                        '(s_eff "mean(mask) on unaugmented parent-imputation real TRAIN, pooled P1-P4; inherited by augmented '
                                        'variants"; s_leak "fit once on unaugmented parent-imputation real TRAIN pooled P1-P4; evaluate on real '
                                        'parent evaluation prefix per (eval_split, phase)"); the two registries now agree on both components',
           'component_behaviour_2026-11-03': 'because the mask channels do not depend on the imputer or the balancer, s_nan (= 1), s_eff '
                                             '(0.6635 / 0.6646 / 0.6650 for W1 / W2 / W3) and s_leak (0.019-0.556 by window x split x phase) '
                                             'are identical across V0-V16 for a given cell; s_drift and s_maj_jsd move at the third decimal; '
                                             'across pipelines S_san+ v1 therefore moves through s_ent alone (PatchTST V0-V6 TEST means of '
                                             's_ent 0.072-0.326, of S_san+ v1 0.460-0.586) [BAO_CAO_CQ_PATCHTST_V0_V6_2026-11-02, sections 5]',
           'component_behaviour_2026-11-09': 'verified on the exports of 09/11: s_nan, s_eff, s_leak and s_leak_probe_auc take one value per '
                                             '(window, split, phase) across the 68 family x pipeline rows of the CQ R4 export and of the LO static-v2 '
                                             'export (phase-1 facts), across the 10 pipelines of CQ PatchTST V7-V16 and across the 17 pipelines of '
                                             'CQ MANTIS_V2; CQ F2 and F3 equal the R4 probe within 1.2e-5. The LO PatchTST V0-V16 export does NOT: '
                                             'three probe fits coexist (V14 = LO F1 export exactly; V5, V6, V8, V9, V10, V13, V15, V16 from the '
                                             'bundle audits, |diff| <= 1.13e-3; V0-V4, V7, V11, V12 from the re-audit of 09/11, |diff| up to 0.0234 at '
                                             'W3, probe AUC 0.8401 vs 0.8400 vs 0.8402 at W1 TEST P4 with identical probe_fit_rows 7,150,228, n_eval '
                                             'and probe_seed 42), which moves acctempo_m3 by up to 0.0139 and acctempo_m4 by up to 0.0163 per cell and '
                                             'changes the LO M4 ordering of the mid-ranked pipelines (decision 38, check 38); the formula itself is '
                                             'reproduced from the exported components to 2.6e-15 (v1), 4.4e-16 (v2), M3 1.7e-16, M4 2.2e-16',
           'component_behaviour_2026-11-10': 'LO r2 (lo_patchtst_v0_v16_full_facts_20261109_r2): s_leak and s_leak_probe_auc equal the LO F1 static-v2 '
                                             'reference in all 408 cells (|diff| 0.0, spread across the 17 pipelines 0.0); exactly six columns changed '
                                             'against the 09/11 package (s_leak 384 cells, max 0.02342; s_leak_probe_auc 384, 0.01171; s_san_plus 392, '
                                             '0.02673; s_san_plus_v2 389, 0.03551; acctempo_m3 390, 0.01425; acctempo_m4 387, 0.01658), every other '
                                             'column identical; v1 / v2 / M3 / M4 reproduce from the components to 2.7e-15 / 3.3e-16 / 2.2e-16 / 2.2e-16; '
                                             'the TEST M4 order (mean over phases and windows) keeps V7 first and V16 last but moves V6 from 7th to 2nd. '
                                             'The three accepted CQ packages keep their own probe fit: |s_leak - CQ R4 reference| up to 4.98e-5 for '
                                             'PatchTST V0-V6 (126 of 168 rows above 1e-5), 1.24e-5 for PatchTST V7-V16 (30 of 240) and 1.24e-5 for '
                                             'MANTIS_V2 (51 of 408); the deterministic probe of ea19afa reproduces the CQ W1/V0 reference to 2.09e-6 '
                                             '(team report, environment unrecorded for the F1 fit) -> decision 42 (tolerance and reference-copy contract)'},
    'v2': {'s_san_formula_version': 's_san_v2_calibration', 'components': ['s_nan', 's_maj_jsd', 's_cal', 's_drift', 's_eff', 's_leak'],
           'aggregation': 'geometric_mean', 's_eps_floor': 1e-3, 's_cal': '1 - ECE_15 (top-label, 15 equal-width bins)',
           'calibration_convention_note_2026-11-03': 'the audit computes s_cal (and NLL / Brier / ECE) with probabilities clipped at 1e-12, the model '
                                                     'metrics with 1e-7; the two conventions differ beyond 1e-6 on some ALL cells, so the 03/11 '
                                                     'reconciled slice export copies ALL from R4 and recomputes STRICT/OVERLAP with the model '
                                                     'convention while the sanity composites keep the audit convention (check 32)'},
}
ACCTEMPO_DEF = {'acctempo_def_version': 'acctempo_m3_v1.1', 'alpha': 0.6, 'beta': 0.4, 'acctempo_eps_floor': 1e-3,
                'formula': 'AccTEMPO_M3 = S_perf^0.6 * S_san+_v1^0.4; S_perf = (macroF1 * BA * (MCC+1)/2 * (kappa+1)/2)^(1/4); '
                           'every factor clipped to [1e-3, 1] before the product',
                'primary_s_san_version': 'v1', 'also_compute': ['v2'],
                'report_rule': 'v1 is the preregistered primary comparison; v2 (s_cal = 1 - ECE_15 in place of s_ent) is reported '
                               'only as a calibration sensitivity analysis and never changes the primary ranking [DEC §2]',
                'mandatory_columns': ['acctempo_m3', 's_perf', 's_san_plus', 's_nan', 's_maj_jsd', 's_ent', 's_drift', 's_eff', 's_leak',
                                      's_cal', 's_san_plus_v2'],
                'interpretation_rule': 'S_san+ is a data/pipeline quality score, not a predictive score; an AccTEMPO difference is '
                                       'reported together with the S_perf difference and the component that drives it. The GD1 '
                                       'decomposition (92-94% of the CQ V13 -> V14 AccTEMPO gain attributable to s_ent) is explanatory '
                                       'only and does not redefine the primary metric after results are observed [DEC §2]',
                'bootstrap_rule': 'S_perf, s_nan, s_maj_jsd, s_ent/s_cal, s_drift recomputed per resample; s_eff, s_leak fixed (run-level)',
                'decision_status': 'LOCKED 2026-10-05; primary v1, v2 auxiliary sensitivity [DEC §2]',
                'author_mapping_2026-11-01': 'D-18 confirmed and Q-06/Q-09 signed: in the paper AccTEMPO_M3^(cal) = acctempo_m4 is the composite '
                                             'objective, S_perf / macro-F1 / balanced accuracy carry trends and rankings, M3 v1 is the sensitivity '
                                             'and the pre-registered primary of the meta-dataset (AUTHOR_RATIFICATIONS_2026_10_24[18], _2026_11_01)',
                'decomposition_patchtst_2026-11-03': 'report-derived (decision 27 (a) tag), seed 42, TEST means over 12 cells: M3 gains of the balanced '
                                                     'variants over their parent are V2 +0.036, V3 +0.056, V4 +0.060, V6 +0.074 while S_perf moves '
                                                     '+0.017 to +0.023 and s_ent +0.09 to +0.23; under M3^(cal) (s_cal 0.966-0.984 for every pipeline) '
                                                     'the same gains are +0.010, +0.008, +0.011, +0.013; imputation without balancing (V1, V5) is '
                                                     'below V0 on M3 (-0.004, -0.010), M3^(cal) (-0.007, -0.003) and macro-F1 (-0.019, -0.014). '
                                                     'The interpretation_rule applies: every F2 AccTEMPO difference is reported with the S_perf '
                                                     'difference and with s_ent named as the driver [BAO_CAO_CQ_PATCHTST_V0_V6_2026-11-02, tables 3-10]'}
EXPERIMENT_SEEDS = {
    'master_seeds': list(MASTER_SEEDS),
    'augmentation_policy': AUGMENTATION_SEED_POLICY,
    'rule': 'materialise one S2 balanced TRAIN artifact per master seed; the S3 model cell with master seed s consumes the S2 '
            'artifact created with the same s; no balanced artifact with a hidden fixed seed is reused across model seeds [DEC §1]',
    's2_plan': {'cells': '2 tasks x 3 windows x 4 imputer parents (V1, V5, V9, V13) x 3 balancers x 3 seeds', 'n_runs': 216,
                'runner': 'modal_jobs/run_augmentation_grid.ps1 -Task CQ|LO -Seeds 42,43,44 (sequential; plan.json + run_summary.csv)',
                'artifact_path': 'meta_release=imputation-v1/L1_runs/task=*/feature_regime=*/window_id=*/phase_id=P4/'
                                 'pipeline_id=V*/model_name=BALANCED_TRAIN_ONLY/seed=<master seed>/run_id=*/attempt_id=*',
                'scope': 'the full P1-P4 TRAIN sequence of the window is balanced once (phase_id=P4); prefixes are never balanced separately'},
    's3_rule': {'runner': 'modal_jobs/run_model_grid.ps1 -AugmentationSeedPolicy match_model_seed (default)',
                'fixed_policy': 'opt-in only: -AugmentationSeedPolicy fixed -AugmentationSeed <s>; mixing the two flags is rejected',
                'parent_resolution': 'model_app._latest_balanced_train requires manifest.seed == augmentation_seed, the registered parent '
                                     'imputation run/attempt, the parent-manifest sha256 and the full release identity',
                'run_id_fields': 'seed, augmentation_seed and parent_augmentation_run_id are part of the hashed run config'},
    'role_seeds': {'seed_model / seed_dataloader': 'int(sha256("{master}|{role}|{task}|{window}|{pipeline_id}|{model_name}")[:8], 16) '
                                                    'mod (2^31 - 1); independent per cell [SEEDS]',
                   'seed_sampler = seed_augmentation': 'the master seed itself (None for pipelines without a balancer)',
                   'seed_preprocess': SEED_PREPROCESS,
                   'superseded_plan_v1_6_rule': f'H(seed, role) = sha256("{{seed}}:{{role}}")[:4 bytes]; H(0, "preprocess") = '
                                                f'{SEED_PREPROCESS_PLAN_V1_6}; never used by a materialised artifact'},
    'manifest_fields': ['seed', 'augmentation_seed', 'augmentation_seed_policy', 'master_seed', 'seed_model', 'seed_sampler',
                        'seed_augmentation', 'seed_dataloader', 'seed_preprocess', 'parent_augmentation_run_id'],
    'status': 'LOCKED 2026-10-05 [DEC §1]',
    'team_change_2026-10-31': 'LO/registries.py @ df2a867: augmentation_policy FIXED_SEED_42, rule "reuse the seed-42 S2 balanced TRAIN artifact '
                              'across model master seeds 42, 43 and 44", seed_sampler = seed_augmentation = 42 for balanced pipelines; decision 9 '
                              'rewritten "CLOSED updated 2026-10-31: model seeds measure training variability"; the runner, the launcher default '
                              'and modal_jobs/README.md were not changed (CODE_REFERENCE.seed_policy_consistency_2026-11-03)',
    'status_2026-11-03': 'this registry keeps MATCH_MASTER_SEED until the author decides PENDING_DECISIONS[32]; no seed-43/44 S2 or S3 cell is '
                         'accepted under either policy before that decision (check 35)',
    'status_2026-11-09': 'CONVERGED: LO/registries.py @ 421dbcd (cfcfd40) reads MATCH_MASTER_SEED with the rule "use the S2 balanced TRAIN artifact whose '
                         'augmentation seed matches the model master seed; seed-42 artifacts remain valid for seed-42 runs" and decision 9 "CLOSED updated '
                         '2026-11-04 D-32"; the Modal entry points default augmentation_seed = -1 (follow the run seed); seeds 43/44 may start with the 144 S2 '
                         'runs (phase 2, decision 36)',
}
GRID_POLICY = {
    'f1_grid': '17 pipelines x 4 F1 models x 3 windows x 3 seeds per task (612 S3 runs per task); executed in full after the L4 '
               'V0/W1 acceptance pilot; the pilot is an acceptance gate, not a shortlist [DEC §3]',
    'pilot': {'cell': 'one V0/W1 RNN run per task on an L4 [RESP step 4]', 'gpu': 'L4',
              'acceptance': ['no strict-deterministic CUDA error (P2); recommended: a second identical run to show bitwise-equal metrics',
                             f'model_revision == {MODEL_REVISION}',
                             'feature_layout.json lists the four availability-mask bases as dynamic channels',
                             'model input carries every context__* audit field incl. context__label_threshold_set',
                             'one sanity run completes (s_leak probe on real rows)',
                             'inspect_view_grain.py on the Modal Volume: one row per enrollment in every model_inputs split and TEST prefix view']},
    'promotion_rule': 'a cell enters the result tables only after the Volume-level S0/S1 audits and the grain audit of its inputs '
                      'pass; GD1 numbers (seed 42 RNN on the 2x views) are superseded, not merged',
    'legacy_quarantine': {'what': '51 LO cells materialised before the V3.1 release identity and the v2 feature source',
                          'rule': 'kept on the Volume for provenance, excluded from every export and every table'},
    'scheduled_after_core_s0_s3': ['F0 reference models (CQ_PARTIAL_TRIAD, LO_HEURISTIC_PROGRESS_GRADE)',
                                   'subgroup job incl. TEMPORAL STRICT/OVERLAP slices', 'QA23 on the current-grade group',
                                   'VALIDATION AccTEMPO and per-class export', 'energy fallback when NVML is unavailable'],
    'status': 'LOCKED 2026-10-05 [DEC §3]',
    'execution_status_2026-10-15': {'CQ': 'RNN seed 42 complete (51 Modal L4 cells, 2026-10-08); LSTM/GRU/BiLSTM seed 42 not scheduled in '
                                          'the team plan; S2 seeds 43/44 missing',
                                    'LO': 'RNN/LSTM/GRU/BiLSTM seed 42 complete as 204 VastAI cells (promotion pending, '
                                          'POST_MATERIALIZE_CHECKS[14]); S2 seeds 43/44 missing'},
    'execution_status_2026-10-17': {'CQ': 'F1 seed 42: RNN 51 Modal L4 cells (2026-10-08, revision recurrent_shared_phase_v2_4_prefixsafe_'
                                          'epoch50) + LSTM/GRU/BiLSTM 153 VastAI L4 cells (REPORT_CQ_FULL_E2E_SEED42_2026-10-16: '
                                          'resource table batch_size 512, two runner sha256 (LSTM/GRU vs BiLSTM) ingested under two '
                                          'ingest_ids with VASTAI_FAMILIES scoping (c519737), energy_records 0); '
                                          'F2 PatchTST determinism pilot only; F3 deferred; S2 seeds 43/44 missing '
                                          '(PENDING_DECISIONS[16], POST_MATERIALIZE_CHECKS[16])',
                                    'LO': 'F1 seed 42: 204 VastAI L4 cells, batch 2048, bf16, resources ingested (204 rows, wall_s and '
                                          'ram_peak_mb per family; REPORT_LO_FULL_E2E_SEED42_2026-10-16); W1 VALIDATION-TEST discrepancy '
                                          'partly diagnosed (POST_MATERIALIZE_CHECKS[15]); S2 seeds 43/44 missing',
                                    'numbers': 'all report figures are descriptive until the parquet exports reach input/results/; '
                                               'nothing from the 2026-10-16 reports enters 03_claims'},
    'execution_status_2026-10-19': {'CQ': 'F1 seed 42: LSTM/GRU/BiLSTM rerun at the registered batch 2048 (153 VastAI L4 cells, one runner '
                                          'sha, NVML GPU-only estimates in 153/153 manifests, selected epochs = history argmax 153/153, '
                                          'W1/V0 CPU replay prefix-safe < 1e-6); ingest vastai_cq_f1_batch2048_seed42_slice_r2_20261019 '
                                          '(66 partitions, slices recomputed with the parent contract, ALL == sanity 408/408 per family); '
                                          'the batch-512 set is archived as history; RNN still the 51 Modal cells of 2026-10-08; F2 pilot '
                                          'only; F3 deferred; S2 seeds 43/44 missing',
                                    'LO': 'unchanged 204 VastAI cells (batch 2048); full-scan TEST prefix clean (409,508 rows per phase); '
                                          'static audit and static-only probe W1/V0 delivered; split_rule_version constant 1 inside the '
                                          '204 historical layouts; ablation and hash-matched cohorts still pending',
                                    'numbers': 'descriptive until the parquet exports reach input/results/; CQ numbers now come from one '
                                               'ingest at the registered batch, so the export is the remaining step for CQ F1'},
    'execution_status_2026-10-21': {'CQ': 'F1 seed 42 complete on one backend: RNN rerun on VastAI L4 at batch 2048 with the historical '
                                          'static layout of the LSTM batch (51 cells, receipt vastai_cq_rnn_historical_layout_seed42_20261020) '
                                          '+ LSTM/GRU/BiLSTM 153 cells (receipt vastai_cq_f1_batch2048_oldfamilies_r2_20261021); 204/204 '
                                          'manifests with NVML estimates; slice partition invariant 0 violations; R3 export at family x '
                                          'pipeline x window x phase x split grain (1,632 cells, CSV/Parquet in '
                                          'CQ/resuilt/cq_recurrent_allfamilies_grid_r3_20261021/) not yet copied to input/results/; '
                                          'RNN Modal (2026-10-08) and RNN VastAI agree to 1e-4 on all 51 window-level AccTEMPO means',
                                    'LO': 'unchanged 204 cells; static ablation pilot run (W1 V0 and V8, LSTM, no_static and '
                                          'gender_duration; exploratory, no contract); results only in the undelivered LO ablation report; '
                                          'prediction-grain scan of 1,632 LO files done',
                                    'numbers': 'descriptive until the exports reach input/results/GD1_CQ_V2_2_clean_r1/ (now feasible for '
                                               'CQ F1 seed 42) and GD1_LO_V3_1_clean_r1/'},
    'execution_status_2026-10-23': {'CQ': 'F1 seed 42 unchanged (R4 export of 2026-10-23 equals R3 to 1e-4 on every family mean and RNN '
                                          'window x phase mean; R4 adds the full sanity contract, AccTEMPO_M4, 4,896 per-class and 14,688 '
                                          'bootstrap facts); F2 pilot: PatchTST V0 x W1-W3 x seed 42 on VastAI L4 (3 runs, post-hoc audit '
                                          '24 sanity / 72 slice / 72 per-class / 216 bootstrap rows, B = 2,000; selected epochs 8 / 7 / 1 '
                                          'of 13 / 12 / 6); the pilot numbers are V0-only and seed-42-only, so no F2 ranking exists; '
                                          'neither package is in the repository or in input/results/',
                                    'LO': 'unchanged 204 cells; a full matched-replay launcher with NVML (585343e) exists but no LO rerun '
                                          'or ablation numbers were delivered; LO F2 not started',
                                    'numbers': 'descriptive; the R4 CQ package is the first export that carries every column the paper '
                                               'tables need (M3, M4, S_perf, S_san+ v1/v2, components, per-class, bootstrap), so check 23 '
                                               'can close as soon as it is copied to input/results/ with its README'},
    'execution_status_2026-10-25': {'CQ': 'F1 seed 42 unchanged (R4). F2 pilot provenance delivered in the regenerated 23/10 report: '
                                          'revision patchtst_channel_independent_v2_1_math_sdp, runner 7886a856, static_layout_policy '
                                          'current (the recurrent grid used the historical layout with the constant split_rule_version), '
                                          'NVML L4; elapsed 22,789 / 25,521 / 15,156 s (W1/W2/W3), 0.453 / 0.507 / 0.301 kWh, epoch time '
                                          '1,738 / 2,109 / 2,490 s, 13 / 12 / 6 epochs; per-epoch VALIDATION macro-F1 oscillates '
                                          '(mean absolute step 0.037-0.069, max 0.11-0.15; train CE spikes x9.5 at W1 epoch 3 and x2.1 '
                                          'at W3 epoch 2); SEEN/UNSEEN x STRICT/OVERLAP cohorts of the pilot printed (96 cells)',
                                    'LO': 'historical-layout grid: full 1,632-cell appendix delivered (consistent with the 68-configuration '
                                          'tables to 7e-5 and with the 19/10 W1 table to 7e-5); NVML matched replay (batch 2048, '
                                          'historical layout, runner 7886a856 for the RNN W1/V0 repair cell) complete for the four '
                                          'families and ingested as vastai_lo_f2_seed42_clean_20261025_r3 (204 contracts, 1,632 metric '
                                          'rows, 87 partitions); BiLSTM NVML facts equal the historical BiLSTM facts to 1e-4 on every '
                                          'pipeline mean; cohort audit 6,528 cells (counts only); ablation P1 table printed; static '
                                          'contract v2 locked for new layouts (13 fields)',
                                    'F2_cost': 'pilot: 17.6 L4-hours and 1.26 kWh for 3 runs (5.9 h and 0.42 kWh per run, about 125x a '
                                               'recurrent run; the 3-run pilot used 1.8x the energy of the whole 204-run CQ recurrent '
                                               'grid). Remaining CQ seed-42 grid (48 cells): about 282 L4-hours and 20 kWh at the pilot '
                                               'epoch counts; D-N3 (A) with F2 on two tasks and three seeds: about 306 runs, of the order '
                                               'of 1,800 L4-hours and 130 kWh if LO behaves like CQ (LO channel count not yet quoted)',
                                    'numbers': 'descriptive; no package in input/results/ yet (CQ R4, LO r2/r3, pilot, ablation)'},
    'execution_status_2026-10-27': {'CQ': 'F1 seed 42 unchanged (family means of the 27/10 report equal R4 exactly). D-23 (b) pilot run '
                                          'on 26/10 at lr 3e-4, warm-up 1 epoch, clip 1.0 (run_purpose STABILITY_PILOT_D23): W2/V0 '
                                          'selected epoch 4 of 9 (old 7 of 12), 5.44 h, 0.389 kWh; W3/V0 selected epoch 1 of 6 (old 1 '
                                          'of 6), 4.28 h, 0.306 kWh; epoch time unchanged (0.60 / 0.71 h). Means over P1-P4: W2 TEST '
                                          'macro-F1 0.644 vs 0.653 (old), VALIDATION 0.712 vs 0.707; W3 TEST 0.770 vs 0.795, VALIDATION '
                                          '0.804 vs 0.763 (descriptive, one seed, never a selection criterion). The per-epoch curves of '
                                          'the two pilot runs are not in the report. The 48 F2 cells are not run; the team proposes to '
                                          'lock D23 for F2',
                                    'LO': 'unchanged; the v2-contract replay launcher exists (0851aed) but no v2 cell was reported',
                                    'numbers': 'descriptive; no package in input/results/'},
    'execution_status_2026-11-26b': {'decisions': '59 (b), 60 (a), 61 (a) ratified on 26/11 (second pass); Method v0.5 and Online Resource 1 v0.1 approved; no pre-submission inquiry to TOIS; opened: 62 (Q-51); open: Q-20, Q-22, Q-23, Q-24, Q-51', 'base_tier': 'unchanged: 1,836 runs on the three registered seeds', 'meta_phase_C': 'accepted (check 47), tables unchanged; the negative control is re-run alone by the team with metamodel 0.3.1 (check 48, PENDING)', 'exploratory_run': 'still not opened by the writing side; not used anywhere', 'package': 'metamodel 0.3.1 written and tested (metamodel_0.3.1_pandas_3.0.5: 55 passed; metamodel_0.3.1_pandas_3.1.0: 55 passed); writing-side run on the ten delivered run directories: 115/115 folds OK, replays equal to the delivered tables; MMConfig and the frozen digests unchanged', 'post_hoc': 'H7 as registered and the utility rule with a decision-time cost estimate computed by the writing side from delivered files (labelled; outside the Holm family of the delivered tables)', 'repository': 'origin/main at acd11c1, public; the analysis package, the release and the phase C runs are not in it yet (request of 26/11, part C)', 'manuscript': 'Method v0.5.1 (EN) and Online Resource 1 v0.2: the three decisions applied to the approved texts; no experimental number added (03_claims section B unchanged)', 'numbers': 'every figure of this revision comes from input/results/GD6_delivery_receipts_and_checks_20261126b/checks/r34b_facts.json'},
    'execution_status_2026-11-26': {'decisions': '57 (a) and 58 (a) of 24/11 recorded; 58 superseded by 59; the twelve answers of 26/11 recorded (AUTHOR_RATIFICATIONS_2026_11_26); opened: 59 (Q-48), 60 (Q-49), 61 (Q-50); open: Q-20, Q-22, Q-23, Q-24, Q-48, Q-49, Q-50', 'base_tier': 'unchanged: 1,836 runs on the three registered seeds', 'meta_phase_A': 'accepted on 21/11 (check 45)', 'meta_phase_B': 'CLOSED 2026-11-26: the four questions left open on 24/11 are answered in the reply of the team (PHAN_HOI_REVIEW_PHA_C_2026-11-24.md, accepted/); the acceptance of 23/11 and 24/11 stands unchanged', 'meta_phase_C': 'PASSED 2026-11-24, items (a) to (e), unchanged; on 2026-11-26 the delivery items are closed (driver in the repository at acd11c1; package copied to cross_task_meta/accepted/, 387 lines in its checksum list, equal to the list of the work_in_progress package; reply of the team filed) and the finding negative_control_MQ08 of 24/11 is corrected (correction_2026-11-26); two further deviations between the design document and the package are recorded (deviations_2026-11-26)', 'exploratory_run': 'still not opened by the writing side; not used anywhere', 'package': 'metamodel 0.3.0 unchanged; known defects recorded for 0.3.1: cluster order of the bootstrap (24/11) and dtype of the permuted state block in the negative control (26/11); neither changes H1 to H8', 'repository': 'origin/main at acd11c1 (the three phase C scripts pushed); the meta-dataset and the code are to be published there (author, 26/11)', 'manuscript': 'Method v0.5 (EN) and Online Resource 1 v0.1 (S1 to S4) written, Figures 1 and 2 redrawn, Figure S1 redrawn; waiting for the approval of the author; no experimental number added (03_claims section B unchanged)', 'numbers': 'every figure of this revision comes from input/results/GD6_delivery_receipts_and_checks_20261126/checks/r34_facts.json'},
    'execution_status_2026-11-24': {'decisions': 'no new author decision; opened: 57 (Q-46) and 58 (Q-47); open: Q-20 to Q-24, Q-26, Q-46, Q-47', 'base_tier': 'unchanged: 1,836 runs on the three registered seeds', 'meta_phase_A': 'accepted on 21/11 (check 45)', 'meta_phase_B': 'PASSED 2026-11-24, items (a) to (f): item (f) is closed by the push of the code of phase B (origin/main at ecad59d); the two tables of release r2 above 10 MB are verified by sha256 against sha256sums.txt of the team and compared with the parts and with the table rebuilt by the writing side (largest differences 0.0 and 1.4e-17); the acceptance of 23/11 on the data stands unchanged', 'meta_phase_C': 'PASSED 2026-11-24, items (a) to (e): the ten runs carry the digests frozen on 23/11, use the seed-aggregated table of release r2 and the hand-off of 21/11 unchanged, ended with exit code 0 in one environment at commit ecad59d, and every delivered table is re-derived by the writing side from the release and the delivered scores (430 hypothesis rows and 28,706 metric rows within 1.1e-16); result on the row that carries the verdict (PRIMARY): H1 is supported in none of the ten configurations and H6 in all; findings and results in acceptance_2026-11-24; open: decisions 57 and 58, push of the phase C driver, move of the package to accepted/', 'exploratory_run': 'cross_task_meta/exploratory_not_for_conclusions/e1_per_task_all_only_mm024_20261120: not opened by the writing side; the seal condition (acceptance of check 47) is met on 24/11; opened only if the author asks', 'package': 'metamodel 0.3.0 and the hand-off zip of 21/11 unchanged; known defect recorded on 24/11: cluster order of the bootstrap (to be fixed in the next version, used for later runs only)', 'repository': "origin/main at ecad59d; the code of phase B is pushed; the driver, the QA script and the splitting script of phase C are not (CODE_REFERENCE['not_in_repository_2026-11-24'])", 'numbers': 'no number of phase C is in the manuscript; the conclusion on C2 is written on the tables of this run when section 5.3 is written (decision 48 (a)), each number through 03_claims.md section B'},
    'execution_status_2026-11-23': {'decisions': 'Q-44 (a) and Q-45 (a) of the second pass of 21/11 written into the registry (AUTHOR_RATIFICATIONS_2026_11_21B; PENDING_DECISIONS 55 and 56); Q-45 (a) restated on 23/11; open: Q-20 to Q-24, Q-26', 'base_tier': 'unchanged: 1,836 runs on the three registered seeds', 'meta_phase_A': 'accepted on 21/11 (check 45); folder moved to cross_task_meta/accepted/ by the team', 'meta_phase_B': 'PASSED 2026-11-23 on the data, items (a) to (e): 36 of 36 unit packages (58,752 rows), S0 profile v5 (240 rows, ALL rows equal to v4), release CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2 (73,440 seed-level rows, ALL rows equal to the accepted release on 557 columns apart from the release id and the builder version, subgroup_report ok), B.5 r2 equal to the accepted set (54 tables, 0 different); the three gates set on 21/11 for the start of check 47 are met; item (f) stays OPEN: the code that produced the packages is not in the repository (origin/main unchanged at fc361b6); details in acceptance_2026-11-23', 'meta_phase_C': "not started by the team, which waited for digests of the r2 release id; the ten digests are issued on 23/11 (POST_MATERIALIZE_CHECKS[47]['frozen_configurations_r2']); go-ahead given in the request of 23/11", 'exploratory_run': 'moved by the team to cross_task_meta/exploratory_not_for_conclusions/e1_per_task_all_only_mm024_20261120; not opened by the writing side; sealed until check 47 is accepted (author, 21/11)', 'package': 'metamodel 0.3.0 and the hand-off zip of 21/11 unchanged; addendum of 23/11: run_phaseC_r2.sh and phaseC_frozen_configurations_r2.json', 'repository': "origin/main unchanged at fc361b6; the code of phase B is not pushed (CODE_REFERENCE['review_2026-11-23'])", 'numbers': 'no number of phase B enters the manuscript: the five-subgroup release is an input of check 47; no outcome of H1 is stated before the full-design run (decisions 48 (a) and 51 (b))'},
    'execution_status_2026-11-21': {'decisions': 'author decisions of 21/11 recorded in AUTHOR_RATIFICATIONS_2026_11_21: 52 (a), 53 (a), 54 (b); the three conventions of the facts contract (check 46) and the reading of decisions 48 and 51 are agreed', 'base_tier': 'unchanged: 1,836 runs on the three registered seeds; the base-tier tables of the paper are three-seed means with the across-seed SD (decision 46 (b)); T05/T17/T18/F07 are regenerated after the author approves the table plan', 'meta_phase_A': 'check 45 PASSED on 21/11: release meta_release_CQ_LO_full_F1F2F3_seeds42_43_44_20261120_mm026 (metamodel 0.2.6, registry rev 2026-11-20b, the 70 inputs of release 20261120) and the six configurations of mm_runs_CQ_LO_full_F1F2F3_seeds42_43_44_20261120_mm026 on that one release in the PC environment of record; five configurations equal the earlier pc_one_thread set and sens_energy is now a real sensitivity analysis (energy cost basis in 56 LO groups); this set is the robustness variant of Table 42 (training and scoring on (ALL, ALL)) with the task-pooled E1 of Appendix E.4 and is cited under that label only', 'meta_phase_B': 'check 46 PARTIAL: seen flags and the 240-row support table delivered; the pilot unit CQ RNN seed 42 (1,632 rows) passes the contract of metamodel 0.2.6 (subgroup_report ok on the delivered rows together with the ALL rows of the accepted release); 35 units, the S0 profile v5, the five-subgroup release and the ALL-only regression are to come', 'meta_phase_C': "check 47 OPEN: decisions 52-54 are answered, the reference package metamodel 0.3.0 implements the registered primary set and its variants, and the configuration digests of the ten runs are frozen in POST_MATERIALIZE_CHECKS[47]['frozen_configurations'] for the release id CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r1; the runs start when the automated gates of check 46 pass (assemble exit code 0, ALL-only regression different: 0)", 'exploratory_run': 'declared by the code team in the reply of 21/11 (section 11): on 20/11, 17:22-18:12 (+07), before either version of the 20/11 request existed, E1-A and E1-B were run separately for CQ and LO with metamodel 0.2.4 on the seed-aggregated table of release 20261120 filtered to one task, (ALL, ALL) rows only, six configurations (12 runs, 254 files, Drive folder mm_runs_CQ_LO_full_F1F2F3_seeds42_43_44_20261119/e1_per_task_20261120); the team read its regret and hypothesis tables; the writing side downloaded README.txt and progress.log only and has not opened any outcome table of that folder; the set is exploratory, is not copied to input/results, is not a source of any statement, and is to be moved to a folder whose name says so; its design equals the per-task ALL-only variant (run V1 of check 47), which is recomputed with metamodel 0.3.0 on the accepted five-subgroup release', 'package': 'metamodel 0.3.0: `run --design full` = training on the five mandatory subgroups (Table 42), one model per task and fold for E1-A, E1-B and E3 (section 10.10), baselines and inner selection on the matched slice (decision 53 (a)), registered hypothesis rows with their analysis_role and one Holm family (decision 54 (b)); new tables mm_metrics_joint, mm_metrics_secondary, mm_recommendations_secondary, mm_fold_composition; `run --expect-digest` refuses a configuration whose digest is not the frozen one; with the default options run computes exactly what 0.2.6 computes, with the 0.2.x digest', 'numbers': 'no number of the meta tier is cited in the manuscript as the registered test before check 47 closes; the numbers of the phase A set are cited only as the robustness variant of Table 42 with task-pooled E1; no outcome of H1 is stated before the full-design run (decisions 48 (a) and 51 (b), reading agreed by the author on 21/11)'},
    'execution_status_2026-11-20b': {'decisions': 'six author decisions of 20/11 recorded in AUTHOR_RATIFICATIONS_2026_11_20: 46 (b), 47 (a), 48 (a), 49 (a), 50 (a), 51 (b)', 'base_tier': 'unchanged since the first pass of 20/11: 1,836 runs on the three registered seeds; from now on the base-tier tables of the paper are three-seed means with the across-seed SD (decision 46 (b)); the 8 seed-44 CQ cells without an energy measurement stay empty (decision 49 (a))', 'meta': 'the three-seed M-15 of 20/11 is the robustness variant of Table 42 of the Meta-Dataset-Report (training and evaluation on the (ALL, ALL) subgroup only) with task-pooled E1 folds (Appendix E.4); it is re-issued on one release with metamodel 0.2.6 in the PC environment of record (check 45, decision 50 (a)); the registered primary design (five training subgroups, per-task E1, replication and pooled rows) is prepared in two steps: five-subgroup facts and release by the code team (check 46), full-design run after decisions 52-54 and the next release of the reference package (check 47)', 'package': 'metamodel 0.2.6: assemble accepts and checks a five-subgroup input (subgroup_report, compare_main_slice, --require-subgroups, --compare-all-with), marks a row whose objective is undefined on its slice as INFEASIBLE and keeps the slice-size columns on the seed-aggregated table; run is unchanged and evaluates one subgroup', 'numbers': 'no three-seed M-15 number is cited in the manuscript until check 45 closes, and every such number is labelled as the ALL-only, task-pooled analysis; the conclusion on C2 (H1) is written on the run of check 47 only (decision 48 (a) together with decision 51 (b)); three-seed base-tier numbers are citable from the facts packages as means with SD once entered in 03_claims'},
    'execution_status_2026-11-20': {'CQ': 'seed 44 COMPLETE: cq_f1_recurrent (RNN, LSTM, GRU, BILSTM) v0_v16_full_facts_seed44_20261118, cq_patchtst and cq_mantis_v2 v0_v16_full_facts_seed44_20261119 on the Drive (fact_exports), 408 sanity rows / 51 cells / 51 runs each, s_leak equal to the reference (max |diff| 0.0), probe_seed = 42, runner commit 5ba9829 written at run time for F1 and PatchTST (255/255 cells), Mantis retroactive 6a69b7f (label); energy missing in 7 PatchTST cells (W1/V5, W1/V16, W2/V7, W2/V12, W2/V16, W3/V0, W3/V12) and 1 Mantis cell (W2/V0), measured in all 204 F1 runs; the three registered seeds are complete (918 runs)', 'LO': 'seed 44 COMPLETE: the same six families, 408/51/51 each, identity 0.0, runner commit 5ba9829 (255/255) and Mantis retroactive 6a69b7f; energy 306/306 runs; the three registered seeds are complete (918 runs)', 'runs': 'base tier complete for the three registered seeds: 1,836 runs = 2 tasks x 6 models x 51 cells x 3 seeds (1,530 primary-grid F1/F2 runs + 306 exploratory Mantis runs), 14,688 sanity rows; 2,499 GPU train hours and 2,909 run hours in total; an energy value on 1,605 of 1,836 runs (CQ 697/918, LO 908/918; CQ seed 43: 99/306), every value an NVML power-sampling estimate; 8 seed-44 cells without energy carry a team proposal (median power of the measured cells of the model x elapsed time: 71.6 W PatchTST, 44.6 W Mantis) that is not applied to the packages (decision 49)', 'meta': 'three-seed release meta_release_CQ_LO_full_F1F2F3_seeds42_43_44_20261120 in cross_task_meta/work_in_progress: manifest 14,688 seed-level rows x 557 columns and 4,896 seed-aggregated rows, n_seeds 3/3, seven QA flags 1.0 in both children, 70 hashed inputs of which 61 equal files held by the writing side (all 24 seed-44 and all 24 seed-43 files); the two extracts published with the report equal the facts (1,836 cells <= 1.2e-16; 1,836 runs <= 1.1e-13 s; LO energy 908 runs equal); the two parquet tables (18.6 MB, 35.2 MB) exceed the 10 MB limit of the Drive connector and are not yet in input/results; release 20261120 differs from 20261119 only in the LO half (energy columns filled by a locally patched assemble.py, builder_version unchanged). M-15 on three seeds (work_in_progress/mm_runs_CQ_LO_full_F1F2F3_seeds42_43_44_20261119): six configurations x 238 registry rows, run twice: pc_one_thread (Windows, Python 3.12.1, the set used in the report; five configurations on release 20261119, sens_energy on 20261120) and host17429_one_thread (Linux, Python 3.12.15, all six on 20261119). Primary objective PAPER_COMPOSITE_CAL, E1-B W1W2->W3, 48 clusters: H1 not supported (L3-FS3 - B3 = +0.0029 [0.0006, 0.0057], p_holm 0.036, the learner is worse), H2 +0.0010 [-0.0015, 0.0041], H3 +0.0625 [-0.0417, 0.1875], H4 +0.0087 [0.0019, 0.0165], H5 supported CQ->LO only (-0.0070 [-0.0112, -0.0031]), H6 supported (log2 cost ratio -0.333 [-0.416, -0.253], objective difference +0.0030 with lower bound -0.0007), H7 not (-0.0011), H8 not (-0.286 [-0.670, 0.132], 25 clusters). Across the six configurations H6 is supported in 6, H7 in 3 (sens_v1, obj_perf, obj_macrof1), H3 in 1 (sens_v1), H1/H2/H4/H8 in none. Mean regret over the 7 folds (main): B2 0.0113, L1-FS3 0.0123, B6 0.0126, L3-FS3 0.0146, B3 0.0161, B1 0.0326. sens_energy is identical to main_cal_time (238/238 metric rows, 6,528/6,528 recommendations) because the run flag --accept-energy-estimates had no effect in metamodel 0.2.4 (the cost basis was fixed at assembly): defect of the reference package, fixed in 0.2.5. Baselines are bit-identical between the two machines; learner rows differ on 11-18 of 182 per configuration (mostly L4, L5, L6, L3-FS4; |diff mean regret| up to 0.0271), 63-124 of 6,528 recommendations differ; every hypothesis verdict is the same on both machines. The analysis run so far is a reduced form of the registered design (decision 51): the releases hold only the (ALL, ALL) subgroup, so E1-B has 48 recommendation situations (one per cluster), and the E1 folds pool the two tasks; mm_hypotheses writes the E1-B rows only. Computed by the writing side from the recommendation rows (descriptive): on the replication fold E1-A the H1 comparison is -0.0021 [-0.0042, -0.0002], on the two folds pooled (96 clusters) +0.0004 [-0.0013, 0.0021], within E1-B by task CQ +0.0006 [-0.0001, 0.0014] and LO +0.0052 [0.0008, 0.0106]', 'repository': "CD3 @ 6274591 (three commits of 19-20/11, tools only); see CODE_REFERENCE['not_in_repository_2026-11-20']", 'archive': 'seed-44 evidence copied on 20/11: delivery receipts (16 packages, byte level), L2 ingest receipts (6 packages + 16 detail; Mantis CONDITIONS_MET_WITH_LABEL), runner_commit_check (510/510 = 5ba9829, Mantis NULL in the manifests), M-18 seed 44 (612 cells, 6,027 epoch rows, best epoch equal to the manifest in 612/612, 7 cells with two identical sources), energy proposal, seed-43 package notes, team report and its 13 tables; the M-15 three-seed folders carry no sha256sums.txt, RUN_LOG or pip freeze and are not in accepted/; the M-08 ledger confirmation asked on 16/11 is still pending', 'numbers': 'three-seed base-tier numbers are citable from the facts packages of seeds 42, 43 and 44 in input/results once entered in 03_claims (every table of sections 1-3 of the 20/11 report reproduces from them, check 44); the three-seed M-15 numbers are recorded as descriptive (03_claims D.4) and are not cited in the manuscript until the release and the six runs are re-issued on one release with metamodel 0.2.5 and accepted (check 45) and until decision 48 (Q-37) and decision 51 (Q-40) are answered'},
    'execution_status_2026-11-16': {
        'meta': 'M-15 three seeds not started (waits for seed 44; metamodel 0.2.4 per decisions 44/45); the team acceptance of 0.2.4 (metamodel_024_acceptance_20261113, copied 16/11) re-assembles the p1 release from the raw inputs: common columns equal to 2.9e-11, 58 columns empty in release 20261112 on the CQ F1 rows are filled (the writing side confirms six alias metrics empty on those rows: balanced_acc, kappa, gmean, log_loss, brier, ece), eight original-name columns dropped, six seed_agg sign/positive-seed columns change on F1 rows; M-15 p1 of 13/11 stands as run on release 20261112',
        'CQ': 'seed 43 COMPLETE: cq_f1_recurrent (RNN, LSTM, GRU, BILSTM), cq_patchtst and cq_mantis_v2 v0_v16_full_facts_seed43_20261116 on the Drive (fact_exports), 408 sanity rows / 51 cells / 51 runs each, s_leak copied from the reference (identity <= 1.1e-16), runner commit 5ba9829 at run time for F1/PatchTST (255/255 cells), Mantis retroactive 6a69b7f (label); energy NOT measured in the 204 CQ F1 runs and in 3 PatchTST runs',
        'LO': 'seed 43 COMPLETE: the same six families, 408/51/51 each, identity <= 9.7e-17, runner commit 5ba9829 (255/255) and Mantis retroactive 6a69b7f (11 hosts); energy missing in 5 PatchTST runs; LO cohort_status OK 1343 / ONE_CLASS 238 / SLICE_EMPTY 51 per package',
        'runs': 'seed 44 (team report of 16/11 and Drive folders): S2 72/72 (seed44_17429_20261114); F1 CQ and LO trained and audited, partly backed up (f1_recurrent_seed44_20261115); PatchTST CQ about 38/51 (patchtst_seed44_cells_20261116); Mantis CQ 2 parents of 15 done; LO PatchTST and LO Mantis not started',
        'repository': 'CD3 @ cb575df (five commits of 13/11); the 15-16/11 tooling of the seed-43 packages is uncommitted',
        'archive': 'seed-43 evidence on the Drive (copied 16/11): delivery receipts (15), L2 ingest receipts (6 + 15 detail) with seed43_fact_source_manifest.json (1,044 files checked, 0 differences), evidence receipts (12, variant_role overlay), runner_commit_check (510/510 = 5ba9829, Mantis NULL), vast identity scan (537 archives, 612 manifests, CQ/CURRENT 306 + LO/CURRENT 306), M-18 seed 43 (612 cells, 5,857 epoch rows), M-08 ledgers (CQ 301 manifests, LO 256)',
        'numbers': 'seed-43 numbers are citable as descriptive seed-robustness evidence (README_results rule 27) from the GD2/GD3 _seed43 packages in input/results once entered in 03_claims; the phase-1 primary tables stay on seed 42 (decision 36) until decision 46 (Q-35) is answered; the team report of 16/11 reproduces from the facts at 4 dp (check 43)'},
    'execution_status_2026-11-13': {
        'meta': 'M-15 phase 1 delivered on 13/11 (mm_runs_CQ_LO_p1_20261113): six configurations x 204 registry rows on meta_release_CQ_LO_p1_F2V0V16_20261112 (3,672 rows, seed_agg sha256 0494d1a5...fb32); E1-B hypotheses: main_cal_time none of H1-H8 supported, sens_v1 H1 H3 H7, sens_energy byte-identical to main, sens_conservative H8 (4 clusters), obj_perf H3, obj_macrof1 H1 H6 H7; release re-assembled on 12/11 with metamodel 0.2.2 (seven QA flags 1.0 per the team receipt) using two R4 copies because of two assembler defects fixed in metamodel 0.2.3',
        'CQ': 'seed 42: PatchTST V0-V6 r2, V7-V16 r2 and MANTIS_V2 r3 carry the reference s_leak (max change 1.24e-5 per the team summaries); seed 43 (team reply, not verified): S2 done, F1 203/204 (BILSTM W3 V16 missing), PatchTST 51/51, Mantis 50/51',
        'LO': 'seed 42: MANTIS_V2 facts package of 51 cells (exploratory; s_leak copied, audit probe within 7.7e-4); seed 43 (team reply, not verified): S2 done, F1 204/204, PatchTST running, Mantis not started',
        'runs': 'seed 44: S2 72/72 finished and being backed up, F1/F2/F3 not started (team reply)',
        'repository': 'CD3 @ 7cad8b1 (fifteen tooling commits 10-13/11)',
        'archive': 'delivery receipts 20261112 (eight packages) and L2 ingest receipts 20261113 (nine packages: six met, three with the retroactive-commit exception) issued by the team',
        'numbers': 'no number of the 10-13/11 packages is citable: the packages are not in input/results (check 42) and decisions 44, 45 are open',
        'numbers_after_ratification': 'same day, later: the 13 packages are in input/results (GD*), check 42 PASSED, decisions 38, 39, 41-45 ratified; numbers are citable under the rules of README_results.md once entered in 03_claims section B'},
    'execution_status_2026-11-10': {'meta': 'M-14 assembled by the team on 09/11 17:04 UTC with metamodel 0.2.1 and registries_v1.6 (manifest sha256 '
                                            'e1fdb8e3... = writing side): meta_release_CQ_LO_p1_F2V0V16_20261109 in cross_task_meta/accepted: 3,672 seed-level '
                                            'rows (CQ 2,040 = F1 1,632 + F2 PatchTST V0-V16 408; LO 1,632), 545 columns, cohort FIXED, feature_regime '
                                            'filled, row_status COMPLETE 3,672, planned_seeds [42], synthetic false, F0 CQ on 2,040/2,040 rows (LO '
                                            'NOT_AVAILABLE_PHASE1), S0 v4 joined on every row (98 X_STATE columns, only *_reason columns all NULL), '
                                            'QA rates: metric_recompute, pairing, delta_identity, decomposition, v0_zero_delta 1.0; run_level_invariant 0.0 '
                                            '(metamodel 0.2.1 counted s_leak as run-level; s_eff is constant in all 459 runs of the release, writing-side count, '
                                            'the RUN_LOG still quoting 225 + 204 runs and 3,432 rows from the first assembly in two lines; fixed in 0.2.2); the first '
                                            'release meta_release_CQ_LO_p1_20261109 (F2 V0-V6, 3,432 rows, X_STATE all NULL) is marked SUPERSEDED; M-15 '
                                            '(mm_runs) not run (lightgbm / optuna); the 14/11 gate of decision 36 stands',
                                    'CQ': 'unchanged since 09/11 except provenance: cq_mantis_v2_v0_v16_full_facts_20261109_r2 (labels on 51/51 '
                                          'checkpoint rows, resource_null_reason on 6 rows, runner_git_commit 6a69b7f on 48/51 rows retroactive, V0 NULL) '
                                          'replaces the 09/11 package (SUPERSEDED marker 10/11); CQ PatchTST V7-V16 package unchanged, receipt added',
                                    'LO': 'lo_patchtst_v0_v16_full_facts_20261109_r2 replaces the MIXED_LEAK_PROBE package (SUPERSEDED marker 10/11): one '
                                          'probe table (LO F1 reference), runner_git_commit df2a867 on 51/51 rows retroactive, source inventory; LO '
                                          'MANTIS_V2 grid running on 09-10/11 (result tars mantis_lo_<V>_<W>_20261109_results.tar.gz of at least V2, V3, V4, '
                                          'V6, V7, V8, V13, V14, V15, V16 at W1-W3 uploaded under LO/L1_runs up to 10/11 03:13 UTC per the Drive listing of '
                                          '50 recent files), facts package not delivered',
                                    'runs': 'primary seed-42 cells unchanged (510 of 1,530); exploratory CQ Mantis 51; LO Mantis in progress; seeds 43/44: '
                                            'nothing (phase 2 not started, as requested in the 09/11 order F)',
                                    'repository': 'origin/main 193b584 (six commits of 10/11): deterministic probe + reference assertion, LO r2 tool, '
                                                  'meta-release combiner and acceptance checker, runner-commit inventory, receipts, 44 new tests',
                                    'archive': 'Drive: s_leak_reference_20261109 (CQ and LO tables, 24 cells each, identical copies in both L0_registry '
                                               'folders, sha256sums), delivery_receipts_20261109 (three byte-level receipts, 88 + 87 + 58 files, 0 '
                                               'problems, Drive MD5 = local MD5 for every file), facts_of_record_hash_check_20261109.json (198/198 ok), '
                                               'repro_V2_W2_seed42_20261109 (CQ Mantis V2 W2 re-run bit-identical: probabilities, predictions, metrics, '
                                               'adapter digest 36ee17d9...); 34 small files of the new packages hash-verified by the writing side',
                                    'numbers': 'export-sourced for CQ F1, LO F1, CQ F2 V0-V16, CQ F3 Mantis (exploratory) and now LO F2 r2 (all columns); '
                                               'the meta-release row counts and QA rates verified from the seed-level parquet (sha256 60968928...)'},
    'execution_status_2026-11-09': {'CQ': 'F2 PatchTST seed 42 complete: V0-V16 = 51 cells; V7-V16 (30 cells) with the same runner 29da3b2 and layout '
                                          'sha256:367bf42b..., protocol v2, audits B = 2,000, 960 cohort slices OK, partition PASS; 251.52 L4-hours elapsed '
                                          '(244.13 train), 17.36 kWh GPU estimate (NVML 30/30), 92.56 USD at the 0.368 USD/h rate of the 02/11 report '
                                          '(descriptive); best epochs 1-18 (6 cells at <= 2); n_checkpoints_within_margin = 2 in all 30 cells (tautological '
                                          'margin, check 33). F3 MANTIS_V2 seed 42: V0-V16 = 51 cells EXPLORATORY (run_purpose EXPLORATORY_CACHE_VALIDATION), '
                                          'pin satisfied in every standardised manifest (resolved sha 8f6ca35..., strict_load true, weights sha256 48f1066f..., '
                                          'param_count_total 2,226,510 = 2,214,144 backbone + 12,366 probe), 101.23 L4-hours elapsed of which 29.81 '
                                          'train, 5.48 kWh in 45 runs (3 UNAVAILABLE, 3 V0 cells without elapsed or energy), runner_git_commit null, '
                                          'cohort 1,632 OK; the cost and determinism pilots of check 37 (c)/(d) are not documented before this grid. '
                                          'CQ F1 R4 unchanged',
                                    'LO': 'F2 PatchTST seed 42 complete: V0-V16 = 51 cells, release LO_V3_1, layout sha256:84761775..., protocol v2 '
                                          '(launch scripts pass --augmentation-seed-policy match_model_seed), 352.17 L4-hours elapsed (343.14 train), 24.17 kWh '
                                          '(NVML 51/51), runner_git_commit NOT RECORDED in all 51 resource rows; audits B = 2,000; cohort 1,632 slices = '
                                          '1,343 OK, 238 ONE_CLASS, 51 SLICE_EMPTY (UNSEEN groups); best epochs 1-15 (13 cells at <= 2, 10 at epoch 1); '
                                          'the audit tables mix three s_leak probe fits (decision 38); Mantis LO V0/V1/V5/V9/V13 training; LO F1 static-v2 '
                                          'unchanged',
                                    'runs': 'primary seed-42 cells: CQ F1 204 + LO F1 v2 204 + CQ F2 PatchTST 51 + LO F2 PatchTST 51 = 510 of 1,530 '
                                            '(every seed-42 cell of the plan); exploratory: CQ MANTIS_V2 51; seeds 43/44: nothing (S2 144 runs not started); '
                                            'archived as before',
                                    'repository': 'origin/main 421dbcd (three commits of 09/11): seed policy converged (check 35 PASS), clip 1e-12, '
                                                  'mantis_v2 rows, f3_mantis package integrated without its tests, 267 orchestration/audit/facts tools',
                                    'archive': 'Drive re-organised on 09/11 (move only; ids unchanged); three full-grid facts packages read through the '
                                               'connector (sanity, cohort, checkpoint, resource, summary, README, source inventory, sha256sums all '
                                               'hash-verified: 29 files); FACTS_OF_RECORD.md at the Results root; the author has not yet synced the '
                                               '_drive_mirror folder (decision 31) and the team has not received the metamodel package (decision 40)',
                                    'numbers': 'export-sourced for CQ F1 (R4), LO F1 (static-v2), CQ F2 V0-V16, CQ F3 Mantis (exploratory) and the LO F2 '
                                               'metrics other than S_san+/M3/M4 (decision 38); the 09/11 report tables equal the facts at three decimals '
                                               '(440 values compared, 0 mismatches)'},
    'execution_status_2026-11-03': {'CQ': 'F2 PatchTST seed 42: V0-V6 complete = 21 cells (W1-W3), one runner 29da3b2, one layout '
                                          'sha256:367bf42b..., protocol v2 (lr 1e-3, warm-up 0, no clipping, batch 2048 = 4 x 512, bf16, L4), '
                                          'audits B = 2,000, 672 cohort slices OK, salt join COMPLETE_FULL_JOIN; selected epochs V0 20/4/1, V1 '
                                          '6/4/24, V2 19/4/28, V3 4/1/3, V4 8/3/6, V5 5/7/7, V6 3/9/7 (evaluated = best + 5 everywhere, '
                                          'patience 5); 181.81 L4-hours, 66.91 USD at 0.368 USD/h, 13.03 kWh GPU estimate; V4/W3 rerun with '
                                          'workers = 0 after an OOM; V7 stopped before completion; V8-V16 (30 cells) not run; CQ F1 R4 unchanged '
                                          '(now with per-cell slices reconciled, class-offering flags, partial split / release / S2 evidence)',
                                    'LO': 'F1 static-v2 grid unchanged and now exported in the R4 grain (M-01: 1,632 cells with acctempo_m4, 204 '
                                          'resource runs with train_seconds and elapsed_seconds, energy NOT_MEASURED preserved as recorded); LO F2, '
                                          'LO S2 summary, LO class-offering flags and the static-v2 ablation not started',
                                    'runs': 'primary seed-42 cells: CQ F1 204 + LO F1 v2 204 + CQ F2 PatchTST 21 = 429 of 1,530; archived: LO '
                                            'historical 204, LO NVML r3 204, PatchTST pilot 3, D23 2, ablation 4, replays 5 (CQ RNN x2, LO RNN, '
                                            'PatchTST one epoch x2)',
                                    'repository': 'origin/main 5872cac: review patch 2026-10-31 adopted; 23 export/audit tools added; 68 tests; '
                                                  'registry drift on the seed policy (decision 32)',
                                    'archive': 'Drive shared with the author; 12 packages of 02-03/11 read through the connector (small files '
                                               'hash-verified); the official R4 and LO static-v2 audits already in input/results since 02/11',
                                    'numbers': 'export-sourced for CQ F1 (R4), LO F1 (static-v2 audits and the M-01 means), PatchTST resources and '
                                               'checkpoints; report-derived (decision 27 (a) tag) for the PatchTST V0-V6 metric cells until the '
                                               'per-cell facts files are synced (decision 31)'},
    'execution_status_2026-10-31': {'CQ': 'three NEW PatchTST V0 runs (W1-W3, seed 42, current layout 11 static fields, registered protocol, one '
                                          'runner, audits B = 2,000; selected epochs 20 / 4 / 1 per the builder text) replace the 23/10 pilot; '
                                          'one-epoch replay of W1/V0 bit-exact; F2 remaining 48 cells still not run (the team waits for the '
                                          'author\'s ratification of protocol v2 and of the three new V0 as the base); CQ F1 R4 unchanged',
                                    'LO': 'unchanged (v2 grid complete); the team package stages the four v2 audits and the r2 historical export',
                                    'runs': 'primary seed-42 cells: CQ F1 204 + LO F1 v2 204 + PatchTST V0 (new) 3 = 411 of 1,530; archived: '
                                            'LO historical 204, LO NVML r3 204, PatchTST pilot 3, D23 2, ablation 4, replays 4 (CQ RNN x2, LO RNN, '
                                            'PatchTST one epoch)',
                                    'repository': 'origin/main 3bdb8b6: review patches 2026-10-28 and 2026-10-29 adopted; 65 tests',
                                    'archive': 'R21_evidence_20261031 staged on the team disk (151 files, manifest); input/results holds the '
                                               'report-derived packages of the writing side (49 files) and a placeholder for the team package',
                                    'numbers': 'report-derived numbers may enter the draft only under decision 27'},
    'execution_status_2026-10-29': {'CQ': 'no new primary run; one matched historical replay of CQ/W1/V0/RNN (29da3b2) against the 20/10 '
                                          'baseline: bit-exact (check 27); F2 0 of 48; the three PatchTST V0 pilot cells await decision 25',
                                    'LO': 'unchanged (v2 grid complete); R20 report fixes the slice tables (check 29 closed)',
                                    'repository': 'origin/main unchanged at e0ae433; local tools behind the two reports not pushed',
                                    'archive': 'Drive tree README of 29/10 (check 30); nothing in input/results/'},
    'execution_status_2026-10-28': {'CQ': 'F1 seed 42 unchanged: the 28/10 consolidated report reprints R4 (68 family x pipeline means, '
                                          'RNN mean-17 window x phase and the recurrent V0 means equal the 23/10 values to 1e-4; 1,632 '
                                          'cells, 204 runs, 14.65 train-hours, 0.685 kWh). D23 pilot classified by the team as a '
                                          'sensitivity pilot (W3 history not unimodal, epoch 1 kept); F2 protocol locked by the team '
                                          'as (a) in 29da3b2; 48 F2 cells still not run. Paired replay CQ/W1/V0/RNN/seed 42: 8 '
                                          'canonical facts per side, maximum delta 0; the report names neither runner commit '
                                          '(check 27)',
                                    'LO': 'F1 seed-42 grid under the v2 13-field contract COMPLETE (lo_static_v2_seed42_20261026: 204 '
                                          'runs at runner b0e5ae1, 1,632 evaluation facts, four family audits with 408 sanity / 120 '
                                          'S_leak / 1,224 slice / 1,224 per-class / 3,672 bootstrap / 51 checkpoint rows each; BiLSTM '
                                          'in LO_static_v2_closure_20261028.tar.gz, sha256 9108...40d3; cohort audit 68/68 family x '
                                          'pipeline, 96 cells each, 0 duplicate hashes; prefix audit 409,508 rows per phase, 189,192,696 '
                                          'future cells null, 39/39 static parity checks). Decision 20 (a-v2) and decision 24 (b) were '
                                          'executed by the team before ratification. Versus r3 (15-field historical layout, NVML): family '
                                          'TEST means move by at most 0.007 in macro-F1 / balanced accuracy / M3 and 0.029 in recall E; '
                                          'the W1 VALIDATION - TEST macro-F1 gap stays +0.140 / +0.192 / +0.219 / +0.236 (P1-P4), W2 '
                                          '+0.004..+0.011, W3 -0.061..-0.073; recall E on W1 TEST is 0 in 96% of the 272 cells (max '
                                          '0.002); s_leak TEST 0.1615, VALIDATION 0.1425. Paired replay LO/W1/V0/RNN/seed 42: baseline '
                                          'b0e5ae1 vs replay 29da3b2 (both after 044d6c7), epoch 4 both, exact probability equality on '
                                          '8 split x phase files: determinism shown, loop equivalence not',
                                    'runs': 'primary seed-42 cells: CQ F1 204 + LO F1 v2 204 + PatchTST V0 pilot 3 (reusable only under '
                                            'decision 25) = 411 of 1,530 (D-N3 (A)); archived evidence: LO historical 204, LO NVML r3 '
                                            '204, D23 2, ablation 4, replays 2',
                                    'numbers': 'descriptive; the 28/10 report pair is reproducible only from an uncommitted builder '
                                               '(check 28); no package in input/results/'},
}
REC_RULE = {'rec_rule_version': 'rec_v1.1', 'rec_objective': 'TEST_ACCTEMPO_M3_DELTA', 'rec_eps': 0.005,
            'secondary_objective': 'TEST_MACRO_F1_DELTA', 'utility_lambda_grid': [0, 0.01, 0.02, 0.05],
            'cost_basis': 'ENERGY_IF_MEASURED_ELSE_TIME',
            'cost_basis_rule': 'energy_gpu_run_kwh_ratio when every candidate in the rec_group has a MEASURED value; '
                               'otherwise time_run_total_s_ratio; never mixed inside a rec_group'}

# ---------------------------------------------------------------------------------------------
# Label artifacts (PLAN Table 4; LO replaced by the V3 catalog-normalised contract on 30/09/2026)
# ---------------------------------------------------------------------------------------------
LO_PROXY_CONTRACT = {
    # 19 canonical fields [V3 §4]; every canonical field and every _P1.._P4 variant has is_label_proxy = 1 and is
    # excluded from imputer predictors and from model input in every LO regime. The four problem fields were confirmed
    # by physical name in [V3.1.2 §15.1]; the audit artifact still has to be refreshed so that it records all 19 fields.
    'contract_id': 'lo_proxy_contract_v3',
    'canonical_fields': {
        'score_weights': ['performance_score', 'video_weight', 'assignment_weight', 'exam_weight', 'course_weight_total'],
        'video': ['watched_videos', 'video_counts', 'watch_percent', 'video_catalog_coverage'],
        'problem': ['assignment_problem_catalog_count', 'exam_problem_catalog_count',
                    'assignment_best_correct_sum', 'exam_best_correct_sum',
                    'assignment_ratio_catalog', 'exam_ratio_catalog',
                    'problem_catalog_coverage', 'problem_score_catalog_coverage'],
        'sensitivity': ['tempo_legacy_unclipped_score', 'tempo_legacy_score_clipped'],
    },
    'n_canonical_fields': 19,
    'names_to_confirm': [],
    'names_confirmed_on': '2026-10-01 [V3.1.2 §15.1]: assignment_problem_catalog_count, exam_problem_catalog_count, '
                          'assignment_best_correct_sum, exam_best_correct_sum (denominators and numerators of the two ratios)',
    'phase_variants_rule': 'any canonical field with suffix _P1, _P2, _P3, _P4 (or the pipeline equivalent) inherits is_label_proxy = 1',
    'exclusion_scope': ['imputer_predictors (QA21)', 'model input of LO_FULL_EARLY, LO_NO_CURRENT_GRADE, LO_NO_PROGRESS'],
    'audit_artifact': 'final_score_contract_audit_v3_catalog_normalized/{label_semantics_contract, proxy_feature_contract, '
                      'exclusion_reason_summary, score_range_by_profile}',
    'audit_status': 'refresh pending: current snapshot must record all 19 fields incl. the three coverage fields [V3 §4, §9]; '
                    'all 19 names are now confirmed (POST_MATERIALIZE_CHECKS[3])',
    'current_grade_group': {'status': 'LOCKED 2026-10-01 [V3.1 §6]',
                            'columns': ['score_sum', 'score_mean', 'score_std', 'score_fraction_mean', 'score_fraction_std',
                                        'correct_problem_count', 'incorrect_problem_count', 'correct_ratio', 'correct_ratio_std'],
                            'regimes': {'LO_FULL_EARLY': 'included', 'LO_NO_CURRENT_GRADE': 'removed', 'LO_NO_PROGRESS': 'per PLAN §2.6'},
                            'note': 'attempt-level, not catalog-normalised; problem_score_catalog_coverage stays a label proxy in every '
                                    'regime; QA23 (Spearman |rho|, NMI vs final_score) is run per phase on this group and reported'},
}
LABEL_ARTIFACTS = {
    'CQ': {'label_rule_version': RELEASE_SPECS['CQ_V2_2']['label_rule_version'],
           'label_threshold_set': RELEASE_SPECS['CQ_V2_2']['label_threshold_set'],
           'aliases': {'label_rule_version': ['CQ_TRIAD_PROXIMITY_v1 (PLAN v1.6 name)'], 'label_threshold_set': ['PRIMARY (PLAN v1.6 name)']},
           'zero_activity_policy': {'rule': '200,000 enrollments with cq_active_event_any = 0 and CQ_label_final = warning are removed '
                                            'from the labelled population by a deterministic hash sample (sha256 of "20260917:" + '
                                            'enrollment_id, lowest 200,000 ranks); their label is set to NULL with cq_exclusion_reason = '
                                            'v3_sampled_zero_activity_warning_removal; every other zero-activity enrollment keeps its label',
                                    'source': 'CQ/Feature_extraction/labels/build_cq_labels.py @ dff9a3f (LABEL_VERSION, zero_activity_warning)',
                                    'to_confirm': 'that the split population 2,684,090 is counted after this removal; the report v1.8 '
                                                  'population reconciliation must state the pre-removal count and this rule'},
           'score': 'cq_score_g_final = 1 - TRIAD_distance_final/sqrt(3) (alias CQ_proximity_final)',
           'thresholds': {'W': '< 0.10', 'A': '[0.10, 0.30)', 'G': '>= 0.30'},
           'invalid_component_policy': 'NULL with exclusion_reason; never coerced to W',
           'population': {'n_enrollments': 2684090, 'source': 'release V1 (REPORT_CQ_V1); [CL §8.3] distinct enrollment 2,684,090',
                          'class_counts': {'c0': 2582414, 'c1': 56129, 'c2': 45547}}},
    'LO': {
        'label_rule_version': RELEASE_SPECS['LO_V3_1']['label_rule_version'],
        'label_threshold_set': RELEASE_SPECS['LO_V3_1']['label_threshold_set'],
        'aliases': {'label_threshold_set': ['CATALOG_NORMALIZED_PRIMARY_V3 (registry name until 2026-10-04)']},
        'v3_1_change': 'same formula and bands as V3; courses without any observed attempt in every weighted assignment/exam '
                       'component are excluded with reason no_scored_signal_in_course (102 courses, 172,003 enrollments) [V3.1 §4]',
        'label_field': 'LO_performance_label_3', 'score_field': 'performance_score',
        'score_semantics': 'activity_derived_weighted_score',
        'final_grade_claim': 'not_an_independently_observed_final_grade',
        'formula': 'performance_score = video_weight*watch_percent + assignment_weight*assignment_ratio_catalog '
                   '+ exam_weight*exam_ratio_catalog',
        'components': {
            'watch_percent': 'min(1, watched_videos / video_counts)',
            'assignment_ratio_catalog': 'sum over catalog assignment problems of best automatic correct ratio '
                                        '(best score / full score over attempts) / catalog assignment problem count; unattempted = 0',
            'exam_ratio_catalog': 'same rule over catalog exam problems; unattempted = 0',
            'exam_problem_rule': 'exam problems = problems of the last hierarchical chapter when the course has exam_weight; '
                                 'every other problem is an assignment problem [LO §5]',
            'weights': 'course_limit.csv (video, assignment, exam); weight total must equal 100',
        },
        'structural_bound': [0.0, 100.0],
        'thresholds': {'ID': '[0, 60)', 'G': '[60, 85)', 'E': '[85, 100]'},
        'monotone_in_performance': True,
        'sensitivity_sets': {
            'TEMPO_LEGACY_CLIP': {'rule': 'legacy attempt-level score (exam component = sum of correct ratios over attempted exam '
                                          'problems, not normalised) clipped at 100; same bands', 'role': 'SENSITIVITY_ONLY',
                                  'note': 'reproduces the CD2/TEMPO prevalence regime; identical to the 2026-09-30 morning label '
                                          'except for the clip'},
        },
        'superseded_versions': [
            {'label_rule_version': 'lo_operational_performance_v1', 'reason': 'exam component unbounded (sum of correct ratios), '
             'score > 100 kept as E; 21,141 enrollments > 100 [LO §8]'},
            {'label_rule_version': 'lo_final_score_sourcefaithful_v2', 'reason': 'score > 100 mapped to I/D: non-monotone in '
             'performance (Danh_gia_LO_V2.2_nhan.docx §2); replaced by V3 [V3 §2]'},
            {'label_rule_version': 'lo_final_score_catalog_normalized_v3', 'reason': 'kept courses with no scored signal at all '
             '(profile EXAM max 0.000); replaced by V3.1 after the course-ceiling audit [V3.1 §4, §5]'},
        ],
        'cohort': {
            'raw_enrollments': 11807090, 'eligible_enrollments': 2605423, 'eligible_share_of_raw': 0.22067, 'eligible_courses': 711,
            'class_counts': {'c0': 2596424, 'c1': 6996, 'c2': 2003},
            'exclusion_reasons': {'missing_course_limit_weights': {'enrollments': 8615401, 'courses': 3610},
                                  'missing_assignment_problem_catalog': {'enrollments': 200140, 'courses': 159},
                                  'no_scored_signal_in_course': {'enrollments': 172003, 'courses': 102,
                                                                 'rule': 'no observed attempt in every weighted assignment/exam component'},
                                  'nonpositive_course_weight_total': {'enrollments': 134618, 'courses': 102},
                                  'course_weight_total_not_100': {'enrollments': 69729, 'courses': 16},
                                  'missing_exam_problem_catalog': {'enrollments': 9776, 'courses': 1}},
            'source': '[V3.1 §4]',
            'technical_exclusions_inside_assigned_slices': {
                # label rows that carry a rolling block but are not label-eligible; outside the split population [V3.1 §9]
                'by_slice_and_reason': {'A': {'missing_assignment_problem_catalog': 37, 'course_weight_total_not_100': 154,
                                              'missing_exam_problem_catalog': 943, 'nonpositive_course_weight_total': 1},
                                        'T1': {'missing_assignment_problem_catalog': 1},
                                        'T2': {'missing_assignment_problem_catalog': 2453, 'course_weight_total_not_100': 361,
                                               'missing_exam_problem_catalog': 55, 'nonpositive_course_weight_total': 6},
                                        'T3': {'missing_assignment_problem_catalog': 8946, 'course_weight_total_not_100': 4980,
                                               'missing_exam_problem_catalog': 61, 'nonpositive_course_weight_total': 10}},
                'total': 18008},
        },
        'label_status': 'FINAL 2026-10-01 [V3.1.2 §14.4]: no V3.2; label, split and materialize are not rebuilt for the ceiling finding',
        'course_score_ceiling': {
            # course_score_ceiling_observed = highest PRIMARY score observed in the course [V3.1 §5], [V3.1.2 §14.1]
            'ceiling_below_60': {'courses': 493, 'enrollments': 1668604, 'share_of_cohort': 0.64044},
            'ceiling_below_85': {'courses': 675, 'enrollments': 2372394, 'share_of_cohort': 0.91056},
            'ceiling_ge_60': {'courses': 218, 'enrollments': 936819, 'share_of_cohort': 0.35956},
            'ceiling_ge_85': {'courses': 36, 'enrollments': 233029, 'share_of_cohort': 0.08944},
            'remaining_no_scored_signal_candidates': 0,
            'decision': 'no automatic drop of low-ceiling courses; ceiling is a report-only context field [V3.1 §5], [V3.1.2 §14.1]',
            'implication': 'class G can only occur in 218 courses, class E in 36 courses; must appear in the dataset description and in '
                           'the interpretation of COURSE SEEN/UNSEEN subgroups',
            'by_slice': {  # [V3.1.2 §14.3]; sums to the cohort, no UNASSIGNED
                'A': {'enrollments': 1787557, 'ceiling_ge_60': 659474, 'ceiling_ge_85': 166159},
                'T1': {'enrollments': 156681, 'ceiling_ge_60': 59054, 'ceiling_ge_85': 10237},
                'T2': {'enrollments': 401686, 'ceiling_ge_60': 120925, 'ceiling_ge_85': 24864},
                'T3': {'enrollments': 259499, 'ceiling_ge_60': 97366, 'ceiling_ge_85': 31769}},
            'prevalence_within_reachable_courses': {  # derived from [V3.1.2 §4.1, §8, §14.3]: class count / reachable enrollments
                'G_given_ceiling_ge_60': {'A': 0.00716, 'T1': 0.01790, 'T2': 0.00038, 'T3': 0.01205},
                'E_given_ceiling_ge_85': {'A': 0.00394, 'T1': 0.12230, 'T2': 0.00072, 'T3': 0.00246},
                'reading': 'reachable-course shares are similar across slices (30-38% for >= 60), yet G within reachable courses is 47x '
                           'lower in T2 than in T1: the T1 vs T2/T3 contrast is within-course temporal variation, not course composition; '
                           'log coverage per slice (S0) remains the last alternative explanation to check'},
        },
        'catalog_denominator_audit': {  # [V3.1.2 §14.2]; artifact catalog_denominator_audit_v3_1_r2
            'active_problem_rule': 'catalog problem with >= 1 automatic-score event from any enrollment of the course; only components '
                                   'with positive weight enter the denominator',
            'active_ratio_by_ceiling_band': {'<60': {'courses': 493, 'enrollments': 1668604, 'p50': 0.900, 'p90': 1.000, 'mean': 0.740},
                                             '60-<85': {'courses': 182, 'enrollments': 703790, 'p50': 1.000, 'p90': 1.000, 'mean': 0.986},
                                             '>=85': {'courses': 36, 'enrollments': 233029, 'p50': 1.000, 'p90': 1.000, 'mean': 0.993}},
            'conclusion': 'inflated catalogs do not explain the low ceilings for the bulk of courses (median active ratio 0.90 in the '
                          '< 60 band); the mean of 0.74 shows a tail of courses with inactive catalog items, to be described, not corrected',
            'decision': 'keep catalog-normalised V3.1 as PRIMARY; active-catalog denominator not adopted; no V3.2',
        },
        'score_range_by_profile': {
            # [V3.1 §7] after the no_scored_signal exclusion; profile EXAM no longer exists
            'VIDEO': {'eligible': 7377, 'min': 0.0, 'max': 25.806, 'E': 0, 'G': 0},
            'ASSIGNMENT+EXAM': {'eligible': 76661, 'min': 0.0, 'max': 100.0, 'E': 220, 'G': 150},
            'ASSIGNMENT': {'eligible': 15069, 'min': 0.0, 'max': 100.0, 'E': 28, 'G': 25},
            'VIDEO+ASSIGNMENT': {'eligible': 887408, 'min': 0.0, 'max': 90.0, 'E': 4, 'G': 623},
            'VIDEO+ASSIGNMENT+EXAM': {'eligible': 1618809, 'min': 0.0, 'max': 97.198, 'E': 1751, 'G': 6198},
            'VIDEO+EXAM': {'eligible': 99, 'min': 0.0, 'max': 5.0, 'E': 0, 'G': 0},
            'removed_by_no_scored_signal': {'EXAM': 31334, 'VIDEO+ASSIGNMENT+EXAM': 117389, 'VIDEO+ASSIGNMENT': 22097,
                                            'VIDEO+EXAM': 922, 'ASSIGNMENT': 200, 'ASSIGNMENT+EXAM': 61, 'total': 172003},
        },
        'proxy_contract': LO_PROXY_CONTRACT,
        'invalid_component_policy': 'enrollment not label-eligible -> excluded with proxy_exclusion_reason; never coerced to ID',
    },
}

# ---------------------------------------------------------------------------------------------
# Split registry: shared CQ calendar, per-task split_version (locked 29-30/09/2026)
# ---------------------------------------------------------------------------------------------
SPLIT_REGISTRY = {
    'scheme_version': 'v2_family_shared_calendar',
    'scenario': 'hybrid',
    'scheme': 'A = offerings ending on or before a_boundary (CQ anchor: earliest 60% CQ enrollments by offering_end_date); '
              'future pool cut at explicit calendar boundaries into T1, T2, T3; inside each slice whole units are paired '
              'into VALIDATION/TEST blocks (T1->B,C; T2->D,E; T3->F,G) with tempo_fix.split_v2._greedy_pair_split',
    'unit': 'offering_id x timeline_source; a unit is never split across blocks; an enrollment belongs to exactly one block',
    'windows': {'W1': ['A', 'B', 'C'], 'W2': ['A+B+C', 'D', 'E'], 'W3': ['A+B+C+D+E', 'F', 'G']},
    'calendar': {
        'anchor_task': 'CQ',
        'a_boundary': '2020-07-31', 'slice_boundaries': {'T1': '2020-09-13', 'T2': '2020-12-31', 'T3': '2022-01-18'},
        'tau_w': {'W1': '2020-07-31', 'W2': '2020-09-13', 'W3': '2020-12-31'},
        'slice_calendar_days': {'T1': 44, 'T2': 109, 'T3': 383},
        'source': '[CL §2 boundaries], [V3 §5 tau_w]; both tasks use the same four dates',
    },
    'temporal_rule': 'LABEL_TIME_ORDERING: tau_w = latest TRAIN offering_end_date <= earliest VALIDATION/TEST offering_end_date '
                     'in every window',
    'qa22': {'hard': ['end_order_ok', 'eval_size_ok'], 'min_eval_enrollments': 1,
             'reported_only': ['ev_train_overlap_share', 'p1_cutoff_overlap_share', 'days_train_end_to_test_start',
                               'temporal_strict_share_P1_P4'],
             'revised_on': '2026-09-28', 'locked_on': '2026-09-30',
             'reason': 'SPLIT_V2_QA_INCIDENT_REPORT: concurrent offerings make any start-date purge remove 90-100% of the '
                       'evaluation sets; overlap is inherent to MOOC data and is analysed as a slice'},
    'overlap_metrics': {
        'ev_train_overlap_share': 'share of evaluation enrollments whose offering_start_date < tau_w (offering-start based) [CL §3]',
        'p1_cutoff_overlap_share': '1 - temporal_strict_share(P1, split): share whose P1 cutoff < tau_w [CL §3]',
        'rule': 'both columns are kept; neither replaces the other',
    },
    'purge_mode': 'NONE',
    'sensitivity_exclusions': ['TEST_SIDE_PURGE', 'TRAIN_EMBARGO'],
    'embargo_gap_days': 0,
    'temporal_slice': {'subgroup_axis': 'TEMPORAL', 'values': ['STRICT', 'OVERLAP'],
                       'rule': 'STRICT when cutoff_k(e) = enroll_time + q_k*(offering_end_date - enroll_time) >= tau_w; computed per '
                               '(enrollment, phase) from stored predictions; reported for every run and every phase P1-P4; '
                               'not part of the five mandatory meta-model subgroups; empty slice -> NULL with SLICE_EMPTY'},
    'long_offering': {'decision': 'KEEP_UNITS', 'decided_on': '2026-09-30', 'source': '[V3 §8]',
                      'threshold_days': 270,
                      'context_columns': ['timeline_source', 'duration_days', 'long_offering_flag'],
                      'no_new_mandatory_subgroup': True,
                      'evidence': {'course_specific_timeline': {'p50': 121, 'p90': 345, 'max': 506, 'enrollment_share_gt_270d': 0.01457},
                                   'global_template_fallback': {'p50': 127, 'p90': 426, 'max': 481, 'enrollment_share_gt_270d': 0.55124},
                                   'enrollment_anchored_proxy': {'p50': 152, 'p90': 212, 'max': 212, 'enrollment_share_gt_270d': 0.0}}},
    'tasks': {
        'CQ': {'split_version': RELEASE_SPECS['CQ_V2_2']['split_version'], 'split_version_alias': 'v2.2 (report name)',
               'release_id': 'CQ_V2_2', 'phase_version': RELEASE_SPECS['CQ_V2_2']['phase_version'],
               'registry_id': RELEASE_SPECS['CQ_V2_2']['split_registry_id'], 'pairing': 'balanced',
               'population': 2684090, 'label_rule_version': RELEASE_SPECS['CQ_V2_2']['label_rule_version'],
               'label_threshold_set': RELEASE_SPECS['CQ_V2_2']['label_threshold_set'],
               'blocks': {'A': 1609276, 'B': 175689, 'C': 178095, 'D': 180485, 'E': 180482, 'F': 180032, 'G': 180031},
               'qa22': {'W1': 'PASS', 'W2': 'PASS', 'W3': 'PASS'},
               'assignment_qa': {'multi_block_enrollments': 0, 'multi_split_per_window': 0, 'multi_block_units': 0, 'unmapped': 0},
               'status': 'LOCKED', 'source': '[CL §2, §7.5, §8.3]'},
        'LO': {'split_version': RELEASE_SPECS['LO_V3_1']['split_version'],
               'split_version_alias': 'v3_1_scored_signal_excluded (report name; the view directories keep this suffix)',
               'release_id': 'LO_V3_1', 'phase_version': RELEASE_SPECS['LO_V3_1']['phase_version'],
               'registry_id': RELEASE_SPECS['LO_V3_1']['split_registry_id'],
               'pairing': 'rarest_first', 'population': 2605423, 'label_rule_version': RELEASE_SPECS['LO_V3_1']['label_rule_version'],
               'label_threshold_set': RELEASE_SPECS['LO_V3_1']['label_threshold_set'],
               'blocks': {'A': 1787557, 'B': 78090, 'C': 78591, 'D': 200842, 'E': 200844, 'F': 129426, 'G': 130073},
               'block_classes': {'A': {'c0': 1782182, 'c1': 4720, 'c2': 655}, 'B': {'c0': 77306, 'c1': 532, 'c2': 252},
                                 'C': {'c0': 77066, 'c1': 525, 'c2': 1000}, 'D': {'c0': 200812, 'c1': 23, 'c2': 7},
                                 'E': {'c0': 200810, 'c1': 23, 'c2': 11}, 'F': {'c0': 129283, 'c1': 94, 'c2': 49},
                                 'G': {'c0': 128965, 'c1': 1079, 'c2': 29}},
               'qa22': {'W1': 'PASS', 'W2': 'PASS', 'W3': 'PASS'},
               'assignment_qa': {'multi_block_enrollments': 0, 'multi_split_per_window': 0, 'multi_block_units': 0, 'unmapped': 0,
                                 'note': 'source audits available; refresh against the V3.1 release after materialize [V3.1 §13]'},
               'superseded': ['v2_2_reference (label lo_operational_performance_v1)',
                              'v2.2.sourcefaithful (label lo_final_score_sourcefaithful_v2)',
                              'v3_catalog_normalized (label lo_final_score_catalog_normalized_v3)'],
               'relation_to_cq': 'same calendar, same unit rule, different population and label; distinct split_version by design',
               'single_offering_cells': {'W1_TEST_c2': '1,000 of 1,000 E from the top-E offering of T1 (79.87% of 1,252)',
                                         'W3_TEST_c1': '1,074 of 1,079 G from the top-G offering of T3'},
               # derived from block_classes above (shares in percent of the block); read before any LO W1 VALIDATION-vs-TEST comparison
               'derived_minority_shares_pct': {'A': {'c1_G': 0.264, 'c2_E': 0.037}, 'B': {'c1_G': 0.681, 'c2_E': 0.323},
                                               'C': {'c1_G': 0.668, 'c2_E': 1.272}, 'D': {'c1_G': 0.011, 'c2_E': 0.003},
                                               'E': {'c1_G': 0.011, 'c2_E': 0.005}, 'F': {'c1_G': 0.073, 'c2_E': 0.038},
                                               'G': {'c1_G': 0.830, 'c2_E': 0.022},
                                               'note': 'W1: the E prior in TEST (C) is 3.9x VALIDATION (B) and 34x TRAIN (A), and all '
                                                       'TEST E rows belong to one offering; a majority predictor scores macro-F1 0.330 '
                                                       'and balanced accuracy 0.333 on C (POST_MATERIALIZE_CHECKS[15])'},
               'status': 'LOCKED 2026-10-01 [V3.1 §12]; catalog-denominator audit closed without a V3.2, so no further re-pair is '
                         'foreseen [V3.1.2 §14.4]',
               'source': '[V3.1 §6.1, §8]'},
    },
    'evaluation_windows': {'CQ': {'primary': ['W1', 'W2', 'W3']},
                           'LO': {'primary': ['W1'], 'exploratory': ['W2', 'W3'],
                                  'reason': 'LO W2 minority support 7-23 per split, LO W3 E 29-49 and TEST G 99.5% from one '
                                            'offering [V3 §6, §8]; all windows are still run so the meta-dataset is complete',
                                  'status': 'CONFIRMED 2026-10-01 [V3.1 §6]'}},
    'run_manifest_required': ['scenario', 'release_id', 'split_version', 'phase_version', 'split_registry_id', 'parent_manifest_id',
                              'parent_audit_ids', 'code_hash', 'config_hash', 'seed', 'augmentation_seed', 'augmentation_seed_policy',
                              'parent_imputation_run_id', 'parent_augmentation_run_id', 'label_rule_version', 'label_threshold_set',
                              'feature_source', 'model_revision'],
    'release_manifest_required': ['task', 'release_id', 'split_registry_id', 'split_version', 'phase_version',
                                  'feature_dictionary_version', 'label_rule_version', 'label_threshold_set'],
}

# ---------------------------------------------------------------------------------------------
# Decision log (opened 2026-09-30). Since 2026-10-05 every item is closed; ids stay unique and are referenced above.
# ---------------------------------------------------------------------------------------------
# Author ratifications of 2026-10-24 (round 2). They close the registry decisions listed below; the entries of
# PENDING_DECISIONS keep their history, this block records the closing decision and is exported next to them.
AUTHOR_RATIFICATIONS_2026_10_24 = {
    'date': '2026-10-24', 'source': 'author reply to Ra_soat_tien_do_2026-10-24.md §3 and §7',
    'decisions': {
        '11': 'RATIFIED: F2 PATCHTST PRIMARY full grid; F3 MOMENT_SMALL exploratory on the 13-pipeline core after F2; MOMENT_BASE deferred',
        '13': 'RATIFIED (b): VastAI L4 pinned image for the grids, Modal L4 reference backend, equivalence checked on common cells',
        '14': 'RATIFIED (a): PatchTST batch 2048 = 4 x 512 micro-batches; manifests print batch / micro_batch / accumulation',
        '15': 'RATIFIED: NVML power-sampling estimates are descriptive numbers; REC_RULE treats them as not MEASURED, so the primary cost basis is TIME and ENERGY is a flagged sensitivity analysis',
        '16': 'RATIFIED: the CQ batch-512 wave is historical and enters no table',
        '18': 'RATIFIED (2026-10-24, round 1 and 2): AccTEMPO_M3 with S_san+ v1 stays the pre-registered primary of the meta-dataset; the paper reads trends and rankings on S_perf / macro-F1 / balanced accuracy and uses AccTEMPO_M3^(cal) (exporter acctempo_m4) as the composite objective; H1-H6 on AccTEMPO_M3^(cal), H7 against macro-F1, v1 as sensitivity; disclosed in the Method section as a change made after observing seed-42 results (METRIC_DEF v1.3 to be registered)',
        '19': 'RATIFIED (b): timeline_source CONTEXT_ONLY, window_duration_seconds IN_TENSOR for every new grid',
        '21': 'RATIFIED (b): QA23 exemption of the eight behavioural prefix bases for CQ, on condition that a per-base linkage table and the G-label construction note accompany every CQ P3/P4 number',
        '22': 'RATIFIED (b): the 48-cell CQ F2 grid opens after the pilot manifests, epoch history and SEEN/UNSEEN x STRICT/OVERLAP slices are delivered',
        'N3': 'RATIFIED (A): minimum meta-dataset scope for the paper = 2 tasks x 3 master seeds x (F1 + F2)',
        'N10': 'RATIFIED: imp(a) = a for imputation-only pipelines (build_pipeline_registry corrected in this revision; Meta-Dataset-Report Table 14 to follow)',
        'B7': 'RATIFIED: TEMPO-DQ Table 4 policy (x = S_san+, y = S_perf of V0 on VALIDATION; x0 = 0.75, y0 = 0.70; Q1/Q2 -> V0; Q3/Q4 -> V2 default) is baseline B7 of the meta-model plan (warm-start scenario)',
        'RQ8_H8': 'RATIFIED: RQ8/H8 on the mechanism decomposition (share delta_imp / delta rises with tr_missing_rate and falls from P1 to P4 among beneficial non-V0 recommendations; cluster Spearman with cluster-bootstrap CI)',
    },
    'still_open': {'17': 'LO W1 presentation, waits for the LO ablation CSV', '20': 'static-branch policy for future grids, waits for the LO ablation CSV',
                   'F0_LO': 'LO_HEURISTIC_PROGRESS_GRADE definition', 'framework_name': 'not decided', 'SASMOTE_paper': 'code docstring cites Kosolwattana et al. (2023); author confirmation pending'},
}

AUTHOR_RATIFICATIONS_2026_11_01 = {
    'date': '2026-11-01', 'source': 'author reply to Ra_soat_tien_do_2026-11-01.md §5 (recorded in §9); checklist questions Q-04, Q-06, Q-07, Q-09, Q-10',
    'decisions': {
        '17': 'RATIFIED (a) [Q-04]: the LO W1 TEST class E single-offering support is presented as a finding; contract unchanged; facts carry the single-offering flag',
        '20': 'RATIFIED (a-v2) [Q-04]: the 13-field static contract v2 applies to every new grid (F1 reruns, F2, seeds 43/44)',
        '23': 'RATIFIED (a) [Q-06]: protocol v2 (lr 1e-3, warm-up 0, no clipping, batch 2048 = 4 x 512) is the single F2 protocol; the three NEW V0 runs of 31/10 are the base of the grid; D23 stays a sensitivity; the 48 CQ and 51 LO cells may open (shard plan from the V0 run root, one runner, no --exclude-completed against the old pilot)',
        '24': 'RATIFIED (b) [Q-07]: the LO static-v2 seed-42 grid (13 fields, runner b0e5ae1) is the LO F1 grid of the paper; r3 and the historical grid are archived evidence',
        '26': 'RATIFIED (a) [Q-10]: the 11-field CQ / 13-field LO contracts stay; the two availability assumptions are declared in Method §4.1.2 and in the threats section; SEEN/UNSEEN slices are the empirical check; primary_risk_set dropped at the next contract revision',
        '27': 'RATIFIED (a) [Q-09]: report-derived numbers may enter the draft with the tag [source: results/<package>/<file>, row ...; report-derived] and a mandatory re-check against the L2 export before submission',
    },
    'applied_in': ['Content/4 Method.tex v0.3 (§4.1.2 static branch and availability assumptions, §4.8 one protocol, D23 as sensitivity)',
                   '00_contributions.md v0.6, 02_baselines.md v0.6, 03_claims.md v0.6, input/results/README_results.md (01/11)'],
    'still_open': {'Q-01': 'framework name (D-S1-5)', 'Q-02': 'SASMOTE reference (Kosolwattana et al. 2023?)', 'Q-03': 'F0 LO definition (D-S1-8)',
                   'Q-05': 'phase set P2/P4/P8 wording', 'outline': 'Experiments outline §6 of Ra_soat_tien_do_2026-11-01 and the writing-order exception for W-EN-02'},
}

AUTHOR_RATIFICATIONS_2026_11_02 = {
    'date': '2026-11-02', 'source': 'author reply in the 02/11 session (Ra_soat_tien_do_2026-11-02.md §6 and §8); checklist questions Q-11 to Q-14',
    'decisions': {
        '28': 'RATIFIED (a) [Q-11]: the shared Drive tree is the official delivery channel of the team; the R21_evidence placeholder is closed',
        '29': 'RATIFIED (c) [Q-12]: LO AccTEMPO_M3^(cal) from the derived column acctempo_m3_cal_DERIVED (tag "derived") in the draft; the team exports acctempo_m4 and the tag is replaced before submission',
        '30': 'RATIFIED (c) [Q-13]: the 19/10 ablation is descriptive evidence (layout, family, window named); the team runs the static-v2 no_static ablation before submission; §4.1.2 unchanged',
        '31': 'RATIFIED (a) [Q-14]: the author syncs the remaining Drive subfolders to input/results/_drive_mirror_20261029/Jobs/...; the writing side verifies on the computer',
    },
    'applied_in': ['input/results: GD1_CQ_V2_2_clean_r1 (R4 export, 14 files) and GD1_LO_V3_1_clean_r1 (four static-v2 family audits, 28 files, ablation, cohort sample, replay, derived) with _drive_manifest.json; R21 placeholder moved to _superseded/',
                   '03_claims.md v0.7 (section A: export sources; D.2 s_leak correction), 00_contributions.md v0.7, 02_baselines.md v0.7, README_results.md (02/11)',
                   'Yeu_cau_bo_sung_doi_code_2026-11-02.docx (M-01 .. M-15) sent to the team through the author'],
    'still_open': {'Q-15': 'three V0 runs on the Drive: DELIVERED 02/11 (cq_patchtst_v0_current_20261102, M-04)', 'outline': 'Experiments outline §6 still to be approved'},
}

AUTHOR_RATIFICATIONS_2026_11_04 = {
    'date': '2026-11-04', 'source': 'author replies in the 04/11 writing session (Ra_soat_tien_do_2026-11-04.md §1); checklist questions Q-01, Q-02, Q-03, Q-05, Q-16 .. Q-19 and the phase-1 scope',
    'decisions': {
        '32': 'RATIFIED (a) [Q-16]: MATCH_MASTER_SEED stays the registered augmentation seed policy; the team restores LO/registries.py and the tests; S2 for seeds 43/44 are 144 runs without GPU; no seed-43/44 cell before the four places agree (check 35)',
        '33': 'RATIFIED (a) [Q-17]: keep the artefacts; the method is named "Radius-SMOTE with nearest-neighbour fallback"; the fallback rate is printed per window x class in the paper; the sensitivity label of D-11 stays; no rerun',
        '34': 'RATIFIED (a) [Q-18]: a flag single_offering_dominant (top_offering_share >= 0.5) is added to cell_flags for CQ and LO; clustered (offering-unit) bootstrap CIs are produced for flagged cells; flagged cells are presented as findings like D-17 (LO W1 class E)',
        '35': 'RATIFIED (a) [Q-19]: D-15 unchanged (TIME is the primary cost basis for both tasks); the LO static-v2 grid carries NVML_POWER_SAMPLING_ESTIMATE for 204/204 runs (lo_resource_per_run.csv, 0.4967 kWh), so ENERGY may be used as a labelled sensitivity for LO too; the sentence "LO NOT_MEASURED" in 00_contributions C3 and 02_baselines is corrected',
        '36': 'RATIFIED [scope (c) of 04/11, amends D-N3 (A)]: the phase-1 submission (TOIS, deadline 2026-11-20) uses seed 42 only, F1 of both tasks (CQ R4 1632 cells; LO static-v2 1632 cells) and F2 PatchTST CQ V0-V6 (168 cells); the meta layer (assemble + MM0-MM6) is run by the team on these facts with planned_seeds = [42] (M-13 F0 CQ / S0 profile / Z_M by 2026-11-09 together with M-14 assemble; M-15 run by 2026-11-12); if M-15 is later than 2026-11-14 the paper falls back to reporting C1, C4, C5 only; seeds 43/44, V7-V16 and LO F2 move to the full release (phase 2); every hypothesis test in phase 1 uses cluster bootstrap over cells/offering units and no across-seed variance decomposition',
        'D-S1-5': 'RATIFIED [Q-01]: framework name TEMPO-MDS (Temporal Meta-Dataset for intervention Selection), successor of TEMPO-DQ',
        'D-S1-8': 'RATIFIED (b) [Q-03]: LO_HEURISTIC_PROGRESS_GRADE is NOT_AVAILABLE in phase 1; F0 reference features exist for CQ only (CQ_PARTIAL_TRIAD); LO rows keep the V0 and imputer-only references; stated in threats and future work',
        'D-S1-6': 'CONFIRMED [Q-02]: SASMOTE = Kosolwattana et al. (2023), bib key kosolwattana2023selfinspected',
        'Q-05': 'P2, P4, P8 are outside phase 1; P8 (controlled calibration-error injection to validate s_cal) is listed as future work',
    },
    'applied_in': ['Ra_soat_tien_do_2026-11-04.md §1',
                   '00_contributions.md v0.8, 02_baselines.md v0.8, 03_claims.md v1.0 (04/11)',
                   'Content/4 Method.tex v0.4 (TEMPO-MDS; §4.1.2 Radius-SMOTE with nearest-neighbour fallback; single_offering_dominant flag; phase-1 scope; energy label)',
                   'Yeu_cau_tang_meta_doi_code_2026-11-04.docx (M-13/M-14/M-15 with the two milestones)'],
    'still_open': {'M-15': 'meta-layer results awaited (milestone 2026-11-12)',
                   'outline': 'Experiments outline §6 of Ra_soat_tien_do_2026-11-01 approved implicitly on 04/11 by the instruction to start writing; adjusted for decision 36'},
}

AUTHOR_RATIFICATIONS_2026_11_06 = {
    'date': '2026-11-06', 'source': 'author instruction in the 06/11 session: check whether MantisV2 can replace MOMENT_SMALL / MOMENT_BASE in '
                                    'F3_TS_FOUNDATION with the role EXPLORATORY and, if so, update the resources, the code and the guide '
                                    'of the code team',
    'decisions': {
        '37': 'APPROVED (b) [instruction of 06/11, conditional on the suitability check, which passed with four conditions: channel '
              'adapter, constant-series guard, cache with the pilots of check 37, validity-domain limitation in the paper]: MANTIS_V2 '
              'replaces MOMENT_SMALL and MOMENT_BASE as the single F3 member, EXPLORATORY, full release only; D-11 scope unchanged',
    },
    'applied_in': ['tempo_fix/registries.py rev 2026-11-06 (MODEL_REGISTRY, RETIRED_MODEL_ROWS, PENDING 37, check 37)',
                   'f3_mantis 0.1.0 and Huong_dan_doi_code_F3_MantisV2_2026-11-06.docx (Progress/Ver 3/2026-11-06_F3_MantisV2)',
                   '00_contributions.md v0.9, 02_baselines.md v0.9, 01_notation.md v0.6; Content/4 Method.tex v0.4.1; Figure 1; '
                   'Meta-Dataset-Report v1.9.1; checklist v1.9'],
    'still_open': {'Q-26': 'author confirmation of the adapter defaults (8 PCA components on real TRAIN rows, layer index 2, combined '
                           'token, linear resize to 512) and of the two bib entries staged in input/references/references_additions_2026-11-06.bib',
                   'pilot': 'check 37 (pin, cost, determinism) by the code team before any F3 cell'},
}

AUTHOR_RATIFICATIONS_2026_11_13 = {
    'date': '2026-11-13', 'source': 'author answers in the 13/11 session, after the round-28 review and after check 42 on the packages copied by the author',
    'decisions': {'38': 'RATIFIED (a) [Q-27]: the LO PatchTST r2 package (one probe, reference copied) is the citable LO F2 source', '39': 'RATIFIED (c) [Q-28]: S0 profile v4 without tr_inactive_learner_ratio is the registered state profile', '41': 'RATIFIED (b) [Q-30]: F2 of phase 1 = CQ PatchTST V0-V16; the meta release has 3,672 seed-level rows; tables T05/T17/T18/F07 are regenerated from the r2 packages', '42': 'RATIFIED (a) [Q-31]: reference-copy contract: every F2/F3 export carries the registered s_leak; check 38 is an identity <= 1e-9 (metamodel 0.2.4 TOL_LEAK_IDENTITY = 1e-9); probe reproduction is the diagnostic check 41 with tolerance 1e-3 and the thread mode recorded', '43': 'RATIFIED (a) [Q-32]: the retroactive runner-commit basis (*_RETROACTIVE) is accepted with its label for CQ MANTIS_V2 r3, LO MANTIS_V2 and LO PatchTST r2, and the three NULL Mantis V0 cells stay NULL with their reason; new F1/F2 runs record the commit at run time', '44': 'RATIFIED (a) [Q-33]: the primary objective stays PAPER_COMPOSITE_CAL (D-18); phase-1 results are reported as measured (full H1-H8 table of the six configurations, single-seed limitation stated); M-15 is re-run on the three-seed seed_agg before the conclusions of 5.3/5.4', '45': 'RATIFIED (a) [Q-34]: H8: the phase part is the test, the tr_missing_rate part is descriptive, a verdict needs at least 10 clusters; implemented in metamodel 0.2.4 before any three-seed run; the phase-1 run of 13/11 keeps its tables under the earlier definition'},
    'other': {'Q-14': 'executed by the author: 13 phase-1 packages copied from the Drive; check 42 PASSED; packages placed under input/results/GD* in round 28c',
              'check_42_d': 'reading accepted: release 20261112 differs from 20261109 only through the r2 facts (CQ PATCHTST rows, <= 1.74e-5), the filled macro_f1 columns and the QA flag',
              'correction': 'the 4.98e-5 deviation attributed on 2026-11-10 to the CQ PatchTST V0-V6 facts was measured by the writing side on a report-derived file with rounded s_leak; the facts deviate by 1.24e-5 as the team states'},
    'still_open': ['Q-20', 'Q-21', 'Q-22', 'Q-23', 'Q-24', 'Q-26'],
}

AUTHOR_RATIFICATIONS_2026_11_20 = {'date': '2026-11-20', 'source': 'author answers in the 20/11 session, after the round-30 review (checklist v1.15, Ra_soat_tien_do_2026-11-20.md) and after the comparison of the three options of Q-40 that the author asked for; recorded in the second pass of 20/11 (checklist v1.16)', 'decisions': {'46': 'RATIFIED (b) [Q-35]: the base-tier tables move to three-seed means with the across-seed SD (seeds 42, 43, 44); T05/T17/T18/F07 are regenerated from the facts packages of the three seeds; Method and Experiments are restated; every statement about a best pipeline is worded with the between-seed instability measured on the three seeds', '47': 'RATIFIED (a) [Q-36]: NULL variant_role is accepted in the facts of PRIMARY_GRID runs; the role is a registered property of the family (MODEL_REGISTRY); check 39 item 2 reads model_tier and run_purpose on every row and variant_role on exploratory packages; no re-export', '48': 'RATIFIED (a) [Q-37]: the fallback written into decisions 36 and 44 is applied: main contributions C1 (meta-dataset with the three-seed robustness analysis), C3 (cost-aware recommendation), C4 as a descriptive decomposition and C5; C2 is reported as the registered comparison without a superiority claim. Because decision 51 (b) was ratified in the same session, the conclusion on C2 is written on the full-design run (check 47), not on the analysis of 20/11; until then the manuscript states no outcome of H1. If the full-design run supports H1, the writing side reports it and the author revisits this decision; the writing side does not change the contributions contract', '49': 'RATIFIED (a) [Q-38]: the 8 seed-44 CQ cells keep an empty energy value; cost follows TIME (D-15); energy totals are reported on the measured runs with their count (1,605 of 1,836); the proposal of the team stays a note; no re-run', '50': 'RATIFIED (a) [Q-39]: the pinned Windows PC environment (Python 3.12.1, the environment of the 13/11 package) is the environment of record of the meta tier; the Linux host run is reported as a cross-platform replication with its measured differences; the pip freeze and the platform string of both machines go into the package', '51': "RATIFIED (b) [Q-40]: the registered design is completed before C2 is concluded: the five mandatory subgroups enter the meta release and E1 is run per task; the conclusion of decision 48 is written on that run. The text of the decision and of option (b) is corrected in four places, see 'corrections'"}, 'corrections': {'cohort_audits': "decision 51 said that 'the cohort audits of the facts packages hold the four other slices' and option (b) that the team 'exports the facts of the four cohort subgroups from the stored audits'. Wrong: cohort_audit/V*/seen_unseen_strict_overlap_metrics.csv holds the joint slices SEEN_COURSE / UNSEEN_COURSE x STRICT / OVERLAP with n_eval, macro_f1, balanced_accuracy and class supports (96 rows per pipeline), under a definition without the cutoff condition of Table 10; there is no LEARNER slice and no marginal COURSE slice with the full metric set. The four slices are recomputed from the stored per-sample predictions; nothing is trained and no inference is run (CODE_REFERENCE['subgroup_tooling_2026-11-20b'])", 'situations': "decision 51 said that E1-B 'has 48 recommendation situations (one per cluster) instead of 240'. Under Table 42 (section 10.3) the main report slice of the registered design is (ALL, ALL): E1-B is scored on the same 48 situations; the five subgroups enlarge the meta-training set (subgroup is a context feature; 120 recommendation groups per task and window, 24 of them on the main slice) and add the SEEN / UNSEEN slices as secondary reports", 'executed_analysis': "training and evaluation on (ALL, ALL) only is the robustness variant registered in Table 42 ('Chỉ subgroup (ALL, ALL)'); the analysis of 13/11 and 20/11 is that variant, run with the task-pooled E1 folds of Appendix E.4, where section 10.10 registers the main grid per task", 'effort': 'option (b) needs more than a facts export: seen flags by the registered rule for every evaluated enrollment and phase, subgroup facts of the 1,836 runs (58,752 new rows), an S0 profile with subgroup rows (240 rows) and an extension of the reference package, which trains and evaluates on one subgroup up to 0.2.6'}, 'consequences': ['check 39 item 2 is read as ratified (decision 47): the twenty PRIMARY_GRID directories of seeds 43 and 44 pass it', 'check 45: the three-seed M-15 is re-issued in the PC environment (decision 50) with metamodel 0.2.6; its item (i) moves to checks 46 and 47', 'new checks 46 (five-subgroup facts and release) and 47 (full-design M-15)', 'new decisions 52, 53, 54 (Q-41, Q-42, Q-43): three points of the full-design analysis that the registered documents leave open; they are answered before any five-subgroup result exists', 'per-task E1 runs are not added to the re-issue of check 45: they are part of the full-design run, so that no new result is read before decisions 52-54 are taken', "the six three-seed configurations of 20/11 are labelled 'robustness variant of Table 42, task-pooled E1' wherever they are recorded and are not cited as the registered test", 'decision 46 (b): T05/T17/T18/F07 are regenerated as three-seed means with SD; this is manuscript work under the plan-then-approval rule of the project'], 'applied_in': ['tempo_fix/registries.py rev 2026-11-20b', 'metamodel 0.2.6', 'checklist v1.16', '03_claims.md v1.9', '00_contributions.md v0.12', 'Ra_soat_tien_do_2026-11-20_luot2.md', 'Yeu_cau_doi_code_2026-11-20_ban2 (md + docx)', 'input/results/README_results.md rules 38-42'], 'still_open': ['Q-20', 'Q-21', 'Q-22', 'Q-23', 'Q-24', 'Q-26', 'Q-41', 'Q-42', 'Q-43']}

AUTHOR_RATIFICATIONS_2026_11_21 = {'date': '2026-11-21', 'source': "author answers of 21/11 to the three questions opened in the second pass of 20/11 and to the two points the writing side had set itself, sent with the code team's reply PHAN_HOI_YEU_CAU_20-11_BAN2_2026-11-21.docx (sha256 dbd2db4f451395ad58ab57671be24c9b6efae69efb4b0c85a167d7974ae464e2)", 'decisions': {'52': 'RATIFIED (a) [Q-41]: per-task training is primary; one model per task and fold, each scored on its own task; the verdict rows of E1-B are computed on the clusters of the two tasks together (48 on the registered grid) and the 24-cluster rows of each task are reported beside them; E1-A is the replication and the 96-cluster test follows section 10.8; the task-pooled run of Appendix E.4 is a labelled sensitivity analysis', '53': 'RATIFIED (a) [Q-42]: matched slice; B2, B3, the thresholds of B4 and the neighbours of B5 are estimated on the training rows of the subgroup of the situation they score; the inner selection minimises the mean regret of the (ALL, ALL) groups of the inner validation part; the all-rows variant is a labelled sensitivity analysis', '54': 'RATIFIED (b) [Q-43]: one family; Holm over every test row of mm_hypotheses, so that each added row changes the adjusted p of the primary rows; the writing side had recommended (a)'}, 'confirmations': {'facts_contract_conventions': "agreed by the author: s_leak of a subgroup row is inherited from the ALL cell, as for STRICT / OVERLAP; an empty or one-class slice keeps a row with NULL metrics and its group leaves the training set (INFEASIBLE), a small slice with at least two classes stays with small_subgroup_flag; the ALL rows keep their order in the facts table (POST_MATERIALIZE_CHECKS[46]['conventions'])", 'reading_of_decisions_48_and_51': 'agreed by the author: C2 is the registered comparison without a superiority claim; its result is written on the full-design run of check 47; no outcome of H1 is stated in the manuscript before that run; if the run supports H1 the writing side reports it and the author revisits decision 48'}, 'implementation': {'decision_52': 'metamodel 0.3.0, e1_scope = PER_TASK: E1-A, E1-B and E3 are built once per task (section 10.10 registers the main grid as task (2) x fold (2) and E3 as 3 tiers x 2 tasks); E2 is cross-task by definition; evaluation units: one task, or the two tasks together (every situation scored by the model of its own task); rows of mm_hypotheses: PRIMARY (E1-B, two tasks), PER_TASK (E1-B, one task), REPLICATION_E1A (E1-A, two tasks), POOLED_2FOLD (E1-A and E1-B, two tasks), TRANSFER_E2 (H5)', 'decision_53': 'baseline_scope = MATCHED_SLICE: on the main report slice the baselines are computed from the (ALL, ALL) training rows, so they equal those of the ALL-only analysis (tested); the learners are fitted on the rows of the five subgroups with subgroup_axis and subgroup_value as context features (FS0); hyper-parameters and the k of B5 are selected on the (ALL, ALL) groups of the inner validation part', 'decision_54': 'Holm at alpha_stat = 0.05 over every row of mm_hypotheses that carries a bootstrap p, except the rows marked DESCRIPTIVE (author decision of 13/11); the flag `supported` stays the confidence-interval criterion of Table 50 and the adjusted p is reported beside it; count of the design, not a result: on the registered grid the family holds at most 32 tests (five units, namely PRIMARY, PER_TASK CQ, PER_TASK LO, REPLICATION_E1A and POOLED_2FOLD, times the six hypotheses with a bootstrap p, H1-H4, H6 and H8, plus the two directions of H5) against 8 in the analysis executed so far; the bootstrap p has a step of 0.001 (B = 2,000, two-sided)'}, 'readings_recorded_by_the_writing_side': {'secondary_slices': 'Table 42 registers the four SEEN / UNSEEN slices as secondary report slices and Table 50 defines H1-H8 on the primary protocol: metamodel 0.3.0 writes the secondary-slice comparisons to mm_metrics_secondary as descriptions (summary, intervals, paired difference to B3) and does not put them into mm_hypotheses, so they are outside the Holm family; this reading is submitted to the author as decision 55 (Q-44); the per-group outcomes are kept in mm_recommendations_secondary, so the other reading can be computed from the same runs', 'verdict_rows': 'the verdict of a hypothesis is read on the PRIMARY rows; PER_TASK, REPLICATION_E1A and POOLED_2FOLD rows are reported beside them and change the adjusted p of the primary rows (decision 54 (b))', 'small_slices': 'rows flagged small_subgroup_flag stay in the fits (convention agreed by the author); `--small-subgroups drop-from-training` is a labelled sensitivity run (V4 of check 47)'}, 'state_of_knowledge_at_the_decision': {'known_to_the_writing_side_and_reported_to_the_author_on_20/11': 'the task-pooled three-seed results (H1 not supported on E1-B: +0.0029 [0.0006; 0.0057]) and the post-hoc split of the pooled model by task computed by the writing side (E1-B CQ +0.0006, LO +0.0052; 03_claims section D.5)', 'exploratory_per_task_run': "the code team's reply of 21/11 declares an exploratory per-task run of 20/11 and states that its regret and hypothesis results are not in the reply; the writing side has not opened them; whether the author had seen those tables before answering Q-41 to Q-43 is asked for the record (decision 56, Q-45)"}, 'applied_in': ['tempo_fix registries rev 2026-11-21', 'metamodel 0.3.0', 'Checklist_tien_do_CD3 v1.17', '03_claims.md v1.10', '00_contributions.md v0.13', 'Ra_soat_tien_do_2026-11-21.md', 'Yeu_cau_doi_code_2026-11-21 (md + docx)', 'input/results/README_results.md rules 43-47'], 'still_open': ['Q-20', 'Q-21', 'Q-22', 'Q-23', 'Q-24', 'Q-26', 'Q-44', 'Q-45']}

AUTHOR_RATIFICATIONS_2026_11_26B = {'date': '2026-11-26', 'pass': 'second', 'source': 'six numbered answers of the author of 26/11 to the summary of the first pass of round 34; written into the registry on 2026-11-26', 'decisions': {'59': 'RATIFIED (b) [Q-48], 2026-11-26', '60': 'RATIFIED (a) [Q-49], 2026-11-26', '61': 'RATIFIED (a) [Q-50], 2026-11-26'}, 'answers_2026-11-26_second_pass': {'1': 'agreed: Method v0.5 (EN) and Online Resource 1 v0.1 (S1 to S4) are approved', '2': 'Q-48: (b)', '3': 'Q-49: (a)', '4': 'Q-50: (a)', '5': 'no pre-submission inquiry to the Editor-in-Chief of TOIS', '6': 'the writing side prepares the complete request file for the code team, so that the team carries the remaining work to completion'}, 'consequences': ['Method v0.5.1 and Online Resource 1 v0.2 apply the three decisions to the approved texts (six places in the Method, S4 in the supplement); the approved versions are archived unchanged; no experimental number is added', 'metamodel 0.3.1 and the hand-off of 26/11; check 48 opened for the control-only re-run of the team', 'the two labelled post hoc analyses are computed by the writing side from delivered files (follow-up of check 47); their figures enter the manuscript at the Experiments step through 03_claims section B', '00_contributions.md v0.18: the mechanism cell of C3 no longer names a fitted cost model; the experiment cell of C4 names H7 as registered and the implemented row'], 'not_decided': ['Q-51 (decision 62)', 'licence of the code and of the data, time of the release tag, and whether the internal documents under docs/ of the public repository stay public']}

AUTHOR_RATIFICATIONS_2026_11_26 = {'date': '2026-11-26', 'source': 'author answers of 24/11 (second pass: Q-46, Q-47) and of 26/11 (twelve numbered answers to working/Documents/Ke_hoach_viet_bai_2026-11-24.md section 7, with the short report of the code team attached); written into the registry on 2026-11-26', 'decisions': {'57': 'RATIFIED (a) [Q-46], 2026-11-24', '58': 'RATIFIED (a) [Q-47], 2026-11-24; premise withdrawn on 2026-11-26, superseded by decision 59 (Q-48)'}, 'answers_2026-11-26': {'1': 'agreed: the delivered tables of the environment of record stay the tables of the paper; metamodel 0.3.1 fixes the cluster order of first appearance explicitly, with a reproduction test; the paper states the convention, the library versions and the sensitivity', '2': 'agreed: the revision of section 2 of 00_contributions.md proposed in v0.16 is applied with four adjustments (SHAP removed; block ablation replaced by the nested sets FS0 to FS5; (alpha, beta) sensitivity dropped; numeric-material cells of C1 and C5 updated) and the two axes of section 0 are swapped (main axis: temporal meta-dataset, pre-specified evaluation protocol and registered comparison with its negative result; secondary: C3, C4, C5); C1 to C5 unchanged', '3': 'agreed: English main text of at most 35 pages with an online supplement (Online Resource 1, S1 to S5); the Vietnamese report (Chuyen de 3) is the full version; on 26/11 the author adds that the report has no page limit and that its main content is recommended to stay under 50 pages', '4': "agreed: Method plan v0.5 (structure 4.1 to 4.8 kept, design described as run, 'pre-specified' instead of 'pre-registered', dated protocol history)", '5': 'agreed: Figures 1 and 2 redrawn for the evaluated design; the meta-observation figure moves to the supplement', '6': 'agreed: table plan of section 4 of the plan (base-tier tables as three-seed mean and SD; meta-tier tables from the phase C package) and the three labelled descriptive analyses computed from delivered files', '7': 'agreed: the writing side searches recent IR references and proposes candidates with DOI; the author verifies them and adds them to input/references/ before any is cited', '8': 'agreed, Q-26 (a): the two MantisV2 entries of references_additions_2026-11-06.bib are merged into references.bib', '9': 'the meta-dataset and the code are published at https://github.com/datachain-uit/CD3; the statement on the use of AI tools is checked against the rules and written by the author herself', '10': "agreed: Author = 'Thu Nguyen' in the properties of the figure files (PDF, PNG, SVG, .drawio) and of the chart data files; the writing side reviews the project resources to revise and produce figures and tables", '11': 'agreed: the paper stays with ACM TOIS under the proposed framing; the author asks whether the reframed paper fits the scope of the journal (answered in the summary of 26/11: arguable, not assured)', '12': 'submission of the paper in December 2026'}, 'instructions_2026-11-26': ['no AI tool is declared by the writing side anywhere in the technical content of the paper, of Online Resource 1 or of the cover letter; the author checks the rules and writes the only AI statement herself, in a section of its own', 'method figures are redrawn with draw.io from the research resources; experiment charts are generated only from the result tables of the author; table and figure names are short, symbols and reading notes go to a note below the table or figure', 'two versions: English for the journal, Vietnamese for the report of Chuyen de 3; the study is new and independent, with no earlier version', 'the code team has carried out the request of 24/11 (short report attached)'], 'not_decided': ['Q-48 (decision 59)', 'Q-49 (decision 60)', 'Q-50 (decision 61)', 'approval of Method v0.5 and of Online Resource 1 (S1 to S4)']}

AUTHOR_RATIFICATIONS_2026_11_21B = {'date': '2026-11-21', 'pass': 'second pass of 21/11 (round 31, pass 2); Q-45 restated by the author with the request of 23/11', 'source': 'author answers given in the second pass of 21/11, recorded that day in the project notes only because the author asked for no further step before the code team delivered; written into the registry on 23/11 together with the acceptance of phase B', 'decisions': {'55': 'RATIFIED (a) [Q-44]: the comparisons on the four secondary SEEN / UNSEEN slices are reports, not tests: per evaluation unit and slice the summary, its intervals and the paired difference of the mean regret to B3 are written to mm_metrics_secondary with status DESCRIPTIVE, the per-group outcomes to mm_recommendations_secondary; none of them enters mm_hypotheses or the Holm family; the writing side had recommended (a)', '56': "RATIFIED (a) [Q-45]: when answering Q-41 to Q-43 the author had not seen the regret or hypothesis tables of the exploratory per-task run of 20/11 and had not been told their content by the code team; the results known before the decisions are those of AUTHOR_RATIFICATIONS_2026_11_21['state_of_knowledge_at_the_decision']"}, 'other_instructions': {'exploratory_run': 'stays sealed until the full-design run of check 47 is accepted (author, second pass of 21/11); the writing side has not opened it; variant V1 of check 47 replaces it', 'wait': 'no further step before the code team delivers (author, end of the second pass of 21/11); lifted by the request of 23/11'}, 'consequences': ['decision 55 (a) is what metamodel 0.3.0 implements: the package, the ten frozen configurations and the request of 21/11 are unchanged', 'the Holm family of decision 54 (b) keeps at most 32 tests on the registered grid', 'in the manuscript the results of the SEEN / UNSEEN slices are written as descriptions, without a hypothesis verdict and without an adjusted p on a secondary slice', "the reading AUTHOR_RATIFICATIONS_2026_11_21['readings_recorded_by_the_writing_side']['secondary_slices'] is now an author decision"], 'applied_in': ['tempo_fix/registries.py rev 2026-11-23 (PENDING_DECISIONS 55 and 56: key ratified_2026-11-21)', 'working/Documents/Checklist_tien_do_CD3.docx v1.19', 'working/Documents/03_claims.md v1.12', 'working/Documents/00_contributions.md v0.15', 'input/results/README_results.md'], 'still_open': ['Q-20', 'Q-21', 'Q-22', 'Q-23', 'Q-24', 'Q-26']}

PENDING_DECISIONS = [
    {'id': 0, 'topic': 'LO courses with no scored signal', 'status': 'CLOSED 2026-10-01',
     'resolution': 'excluded with reason no_scored_signal_in_course (102 courses, 172,003 enrollments); LO re-paired as '
                   'v3_1_scored_signal_excluded; no remaining candidates [V3.1 §4, §5, §8]'},
    {'id': 1, 'topic': 'LO current-grade column group and the four inferred proxy field names', 'status': 'CLOSED_PARTIAL 2026-10-01',
     'resolution': 'current-grade group locked (9 columns) [V3.1 §6]; the four problem-field names remain open as item 7'},
    {'id': 2, 'topic': 'proxy_exclusion_reason per slice for the 18,008 ineligible rows', 'status': 'CLOSED 2026-10-01',
     'resolution': 'table by slice and reason recorded in LABEL_ARTIFACTS.LO.cohort.technical_exclusions_inside_assigned_slices [V3.1 §9]'},
    {'id': 3, 'topic': 'IR10_K10 PRIMARY; LO evaluation windows; probability metric for LO W2', 'status': 'CLOSED_PARTIAL 2026-10-01',
     'resolution': 'IR10_K10 and W1-primary / W2-W3-exploratory confirmed [V3.1 §6]; the probability-based metric for W2 '
                   '(log_loss or pr_auc_macro) was not addressed and is carried into item 8'},
    {'id': 4, 'topic': 'BALANCER_PARAMS k_neighbors = 5 and radius_quantile = 0.5 are starting values, not confirmed',
     'status': 'CLOSED 2026-10-04',
     'resolution': 'the registry records the implemented parameters of release_core/runtime_config.py: CDSMOTE n_clusters 5, SASMOTE '
                   'visible_k 16 / max_inspectors 4 / inspector_trees 16 / uncertainty 0.5, Radius-SMOTE fixed radius 0.092 in scaled '
                   'space with fallback_nearest_neighbour_rate audited (> 0.50 = warning); all three use IR10_K10 with cap 10 [RESP §1]'},
    {'id': 5, 'topic': 'AccTEMPO primary S_san+ version v1 vs v2', 'status': 'CLOSED 2026-10-05',
     'resolution': 'v1 is the preregistered primary; v2/s_cal is reported only as a calibration sensitivity analysis; every result '
                   'table publishes AccTEMPO, S_perf, S_san+ and all six components [DEC §2]'},
    {'id': 6, 'topic': 'LO catalog denominator (course ceilings 64% < 60, 91% < 85)', 'status': 'CLOSED 2026-10-01',
     'resolution': 'active-catalog hypothesis rejected (median active ratio 0.90 in the < 60 band); V3.1 kept as FINAL; ceiling and '
                   'per-slice coverage recorded in LABEL_ARTIFACTS.LO [V3.1.2 §14]'},
    {'id': 7, 'topic': 'exact names of the four problem proxy fields', 'status': 'CLOSED 2026-10-01',
     'resolution': 'assignment_problem_catalog_count, exam_problem_catalog_count, assignment_best_correct_sum, exam_best_correct_sum [V3.1.2 §15.1]'},
    {'id': 8, 'topic': 'reporting policy additions (probability metrics for LO W2; offering-cluster bootstrap)', 'status': 'CLOSED 2026-10-01',
     'resolution': 'METRIC_DEF v1.2 [V3.1.2 §15.2]'},
    {'id': 9, 'topic': 'augmentation seed policy (one fixed S2 artifact reused across model seeds vs one artifact per master seed)',
     'status': 'CLOSED 2026-10-05',
     'resolution': 'MATCH_MASTER_SEED: 216 S2 runs (run_augmentation_grid.ps1), run_model_grid.ps1 default match_model_seed, fixed '
                   'policy opt-in only; seed and augmentation_seed recorded in plan, summary, manifest and provenance [DEC §1]',
     'team_change_2026-10-31': 'LO/registries.py @ df2a867 rewrote this closed decision as "CLOSED updated 2026-10-31: reuse augmentation seed 42 '
                               'across model master seeds 42, 43 and 44; model seeds measure training variability" without the author',
     'status_2026-11-03': 'CLOSED 2026-10-05 here; the team change is handled as decision 32 (the author decides); until then no seed-43/44 cell',
     'status_2026-11-09': 'team registry @ 421dbcd now reads "CLOSED updated 2026-11-04 D-32: match augmentation seed to model master seed for new '
                          'multi-seed runs; seed-42 results remain unchanged" (convergent with this entry; decision 32 and check 35 closed on the code side)'},
    {'id': 10, 'topic': 'grid policy after the pilot (shortlist vs full design) and treatment of the 51 legacy LO cells',
     'status': 'CLOSED 2026-10-05',
     'resolution': 'full F1 grid after the L4 V0/W1 acceptance pilot; legacy LO cells quarantined; results promoted only after the '
                   'Volume-level S0/S1 and grain audits [DEC §3], [RESP §2]'},
    {'id': 11, 'topic': 'F2/F3 evaluation scope: PLAN v1.6 §3.3 counts M = 7 models over the full pipeline grid; CD3 @ 548d4d4 ran '
                        'PatchTST/MOMENT only as family_smoke/family_screen; CD3 @ 640be01 locks TEMPORAL_FAMILY_POLICY on its own',
     'status': 'OPEN 2026-10-12 (team proposal recorded, author ratification pending)',
     'blocks': ['any F2/F3 result', 'Meta-Dataset-Report §2.4, §3.3 N_L3, Appendix D2', 'paper claims about F2/F3'],
     'team_proposal_640be01': {'F2_PATCHTST': 'PRIMARY, full grid 17 x 3 windows x 3 master seeds after a determinism pilot',
                               'F3_MOMENT_SMALL': 'EXPLORATORY, registered subset V0 V1 V5 V9 V13 + V2 V6 V10 V14 (CDSMOTE) + '
                                                  'V4 V8 V12 V16 (Radius-SMOTE), 3 windows, 3 seeds, requires a frozen embedding cache',
                               'F3_MOMENT_BASE': 'DEFERRED from GD1',
                               'determinism_pilot': 'CQ/W1/V0/seed 42, two repetitions, PATCHTST and MOMENT_SMALL, checksum agreement'},
     'team_update_813e7ea': 'F3 core = V0 V1 V5 V9 V13 + CDSMOTE V2 V6 V10 V14 + SASMOTE V3 V7 V11 V15 (13); Radius-SMOTE V4 V8 '
                            'V12 V16 as sensitivity_pipeline_ids (registered fallback warning 56-90%); the 2026-10-12 inconsistency '
                            'is resolved and a regression test guards it',
     'team_update_be110a4': 'F3 MOMENT_SMALL deferred until the F2 grid completes (role DEFERRED, scope AFTER_F2_COMPLETE); the '
                            'determinism pilot now lists PATCHTST only; the F3 subset and cache requirement are unchanged',
     'cost_note': 'CQ has 274 dynamic channels (team comment, 813e7ea; confirm from feature_layout.json): one frozen-backbone pass '
                  'over W1 TRAIN (1,609,276 rows x 4 prefixes x 4 patches x 274 channels) is of the order of 1.5-3 L4-hours, '
                  'so the 13-pipeline core (87 TRAIN passes + 15 VAL/TEST passes) needs roughly 150-300 L4-hours once with caching '
                  'if W2/W3 are W1-sized (assumptions: 40-80 MFLOPs per token, 50 TFLOPS effective); trimming the input to 8k '
                  'positions per prefix saves about 37%; recomputing per epoch would multiply this by the epoch count',
     'options': ['(a) ratify as updated in 813e7ea (= option (c) of 2026-10-12 with an explicit core/sensitivity split)',
                 '(b) F3 on all 17 pipelines once the embedding cache exists (one backbone pass per window x pipeline x S2 artifact, '
                 'seed-independent for V0/V1/V5/V9/V13)',
                 '(c) F3 core = imputers + CDSMOTE + SASMOTE (13 pipelines), Radius as sensitivity if budget allows'],
     'note': "whatever is chosen, PENDING 11 closes only with the author's written decision; LO/registries.py @ 640be01 marks it CLOSED",
     'update_2026-11-06': 'F3 member replaced by MANTIS_V2 (decision 37); the ratified D-11 scope (13-pipeline core after F2, Radius-SMOTE '
                          'V4/V8/V12/V16 as sensitivity, frozen embeddings with cache, linear probe, three windows) carries over unchanged; '
                          'MOMENT_BASE no longer exists'},
    {'id': 12, 'topic': 'PatchTST fidelity: the first F2 implementation mixed channels inside a patch token; PatchTST is defined by '
                        'channel independence plus patching', 'status': 'CLOSED 2026-10-12',
     'resolution': 'option (a) implemented in CD3 @ c2856d2: channel-independent tokens with shared projection/encoder, post-encoder '
                   'channel concat in the head, revision patchtst_channel_independent_v2_prefixsafe; verified by tests and by an '
                   'independent CPU check (prefix safety, channel independence, convergence)'},
    {'id': 13, 'topic': 'execution backend for S3 cells: CD3 @ c2856d2 adds a portable VastAI runner (tools/vastai_train_shared.py, '
                        'CQ|LO/model/*/run_vastai.py) next to the registered Modal L4 jobs',
     'status': 'OPEN 2026-10-17: equivalence evidence delivered (LO/W1/V0/RNN/seed 42 Modal vs VastAI L4: row counts, y_true, y_pred '
               'and all probabilities identical, max |dp| = 0.0, REPORT_LO_V2 §10); author ratification and the Modal reference '
               'manifest (run_id, release, created_at, lineage) still required; prediction salts differ between backends. '
               'New on 2026-10-16: CQ LSTM/GRU/BiLSTM (153 cells) ran on VastAI with two runner sha256 values (LSTM/GRU '
               '65680d06..., BiLSTM 3b19dfb8...) while CQ RNN stays on Modal, so a CQ family comparison would span three code '
               'provenances; LO is uniform (one backend, 204 cells). The diff between the two runner versions must be disclosed '
               'or BiLSTM rerun with the LSTM/GRU runner, and CQ RNN rerun on VastAI (51 cells) for a single-provenance table',
     'evidence_2026-10-21': 'CQ RNN rerun on VastAI (51 cells, historical static layout, batch 2048) against the Modal RNN grid of '
                            '2026-10-08: the 51 window-level TEST AccTEMPO means agree to 1e-4 (max |diff| 0.0001, Spearman 0.99998); '
                            'together with the bit-identical LO/W1/V0 cell this is the equivalence evidence the gate asked for on both '
                            'tasks. Ready to ratify option (b): VastAI L4 with the pinned image for every F1/F2 cell, Modal kept as '
                            'reference; the two CQ receipts (RNN runner revision vs three-family revision) stay separate in L2',
     'status_2026-10-21': 'READY FOR RATIFICATION (b)',
     'status_2026-10-23': 'READY FOR RATIFICATION (b), unchanged; the PatchTST pilot (3 runs) and the LO matched-replay launcher '
                          '(585343e) both assume (b); the pilot manifests (runner commit, GPU, layout policy) were not delivered',
     'status_2026-10-25': 'RATIFIED (b) by the author on 2026-10-24 (AUTHOR_RATIFICATIONS_2026_10_24); new equivalence evidence: the '
                          'LO BiLSTM NVML replay (VastAI L4, runner of the 2026-10-23 campaign) equals the historical LO BiLSTM facts '
                          'to 1e-4 on all 17 pipeline means (TEST and VALIDATION); the LO r3 ingest must state the runner commit per '
                          'family (only the RNN W1/V0 repair cell names 7886a856)',
     'blocks': ['any cell produced outside Modal L4', 'C3 time/energy facts', 'paper hardware statement'],
     'facts': ['2026-10-15 consolidated reports: LO F1 seed 42 is complete as 204 VastAI cells (4 families x 17 x 3, batch 2048, L4 bf16, '
               'energy NOT_MEASURED) and the PatchTST pilot ran on VastAI; no Modal-vs-VastAI equivalence check exists; the audit facts '
               'cited for those cells were produced by code that is not in the repository',
               'proposed gate: rerun CQ/W1/V0/RNN/seed 42 (Modal run of 2026-10-08, best epoch 2) with the portable runner on a VastAI L4 '
               'and compare VALIDATION/TEST P1-P4 prediction checksums and metrics; bit-identical => backends equivalent for F1',
               'b5f55fe adopts the runner fixes (GPU gate, CUBLAS_WORKSPACE_CONFIG, provenance, vocabulary from release_core) and '
               'adds release_contract_sha256; BAO_CAO_PATCHTST_2026-10-13 shows the PatchTST determinism pilot and the F2 grid '
               'launch on the portable backend (/workspace/CD3/runs/...), i.e. the backend is in use before this decision',
               'the portable tree had no seed dimension for balanced TRAIN (train/<W>/<V>/balanced_train.parquet), so a grid over '
               'seeds 42/43/44 would reuse one S2 artifact (fixed policy) unless one tree per seed is built; review patch '
               '2026-10-13b resolves train/<W>/<V>/seed=<s>/ and refuses a mismatched S2 seed under MATCH_MASTER_SEED',
               'the launcher, shard plan and download_*_vastai_inputs.ps1 that build the tree are not in the repository',
               'same model.shared_phase implementation, seeds and salted prediction ids as S3',
               'no GPU gate: a rented instance may expose any GPU (bf16 and determinism differ across architectures)',
               'no NVML energy sampling; wall-clock not separated as in model_app (asset preparation excluded, nothing else)',
               'CUBLAS_WORKSPACE_CONFIG not set by the runner (strict determinism fails on CUDA unless the shell sets it)',
               'LO release vocabulary copied with a drifted label_threshold_set (fails the download-manifest check or stamps a wrong id)',
               'outputs are not ingested into the L2 facts / export jobs (different layout, no run_status, no run_id)'],
     'options': ['(a) Modal L4 only for every cell that enters a table; VastAI for smoke tests',
                 '(b) VastAI allowed for F2/F3 cells on NVIDIA L4 only, with the pinned image, review patch 2026-10-12b provenance, '
                 'an ingestion job, and a Modal-vs-VastAI equivalence check on one cell (POST_MATERIALIZE_CHECKS[12]); C3 energy '
                 'facts from Modal only',
                 '(c) VastAI on another GPU class declared as a separate hardware_id; no cross-hardware time/energy comparison']},
    {'id': 14, 'topic': 'PatchTST optimisation batch: the registered batch is 2048 (COMMON_HPARAMS, Meta-Dataset-Report Appendix D3) '
                        'but the F2 determinism pilot A/B (BAO_CAO_PATCHTST_2026-10-13) ran with batch 512 because B x C = 2048 x 274 '
                        'sequences with four prefix passes exceed a 24 GB L4',
     'status': 'OPEN 2026-10-13', 'blocks': ['F2 grid cells (launched with batch 512 per the report)', 'F1 vs F2 comparability claims'],
     'options': ['(a) gradient accumulation 4 x 512 = 2048 (review patch 2026-10-13b: identical optimiser update, recorded as '
                 'batch_size 2048 / micro_batch_size 512 / accumulation_steps 4); pilot A/B repeated once in that configuration',
                 '(b) register batch 512 for F2 only (hparam_config_id, Appendix D3, paper) and state the confound with F1 (2048)'],
     'note': 'the pilot evidence (bit-identical predictions and metrics across two runs) is valid for the configuration it ran in; '
             'it does not cover the configuration the registry declares',
     'team_update_265415d': 'option (a) implemented: accumulation_steps in model.shared_phase, --accumulation-steps / -AccumulationSteps, '
                            'README states 4 x 512 for PatchTST',
     'team_update_2026-10-15': 'pilot A/B repeated at 2048 = 4 x 512 on L4 bf16: 30 epochs, best epoch 25 in both, 8/8 prediction files, '
                               'metrics, feature layout and portable_run_id identical (REPORT_CQ_EXECUTION_CONSOLIDATED §4); evidence '
                               'bundle (determinism_audit.json, manifests, metrics, train_history) not yet delivered; cells started '
                               'with a plain batch 512 not reported',
     'status_note_2026-10-17': 'unchanged for F2 (no PatchTST grid cell reported yet); the same batch question now appears for the CQ F1 '
                               'VastAI cells (resource table batch_size 512) and is tracked as PENDING_DECISIONS[16]'},
    {'id': 15, 'topic': 'cost basis and table grain for cells without energy telemetry: VastAI cells report train_seconds only '
                        '(energy NOT_MEASURED); LO W1 is the registered primary analysis but the consolidated tables pool W1-W3 x P1-P4',
     'status': 'OPEN 2026-10-15', 'blocks': ['C3 claims for LO F1 and for F2', 'LO result tables in the paper'],
     'options': ['(a) energy claims only for Modal cells (CQ F1 RNN today), time-only comparisons elsewhere under REC_RULE '
                 'ENERGY_IF_MEASURED_ELSE_TIME, stated in the paper', '(b) require NVML on the rented L4 before any further VastAI grid'],
     'team_update_ce0486e': 'portable runner samples NVML power at 1 Hz and labels the integral NVML_POWER_SAMPLING_ESTIMATE '
                            '(energy_gpu_run_kwh stays null); the 204 historical LO cells remain NOT_MEASURED; recommendation: estimates '
                            'reported descriptively only, never a cost basis together with counter measurements, REC_RULE treats them as '
                            'not MEASURED',
     'table_rule': 'facts and tables at window x prefix grain, W1 reported separately as primary, pooled means only as a labelled summary',
     'evidence_2026-10-21': 'CQ: NVML GPU-only estimates in 204/204 manifests; train_seconds summed from history; per family '
                            '(mean of 51 runs) RNN 0.00312 kWh / 264 s, LSTM 0.00314 / 251 s, GRU 0.00272 / 221 s, BiLSTM 0.00447 / '
                            '299 s; whole CQ F1 grid about 0.69 kWh GPU-only and 14.7 train-hours; BiLSTM costs 1.6x GRU per run at '
                            'equal macro-F1 (0.713 vs 0.716). Window x phase tables now delivered for AccTEMPO, macro-F1, balanced '
                            'accuracy, s_ent and per-class recall (CQ R3). Usable descriptively under the ESTIMATED label; '
                            'REC_RULE still treats them as not MEASURED',
     'team_update_2026-10-16': 'LO resources now ingested (204 rows: wall_s 280-354 s and ram_peak_mb per family, batch 2048, bf16, '
                               'L4, epochs_config 50); CQ VastAI resources 153 rows (wall_s 455-885 s at batch 512, epochs_mean '
                               '8.6-10.1, energy_records 0 although vastai_run_family.sh passes --energy-sampling-interval-seconds 1.0); '
                               'both reports still pool W1-W3 x P1-P4 uniformly and give no per-window table, so the table_rule is '
                               'not yet met; whether the NVML estimates exist in the run manifests is unknown'},
    {'id': 16, 'topic': 'CQ F1 VastAI optimisation batch: REPORT_CQ_FULL_E2E_SEED42_2026-10-16 §7 lists batch_size 512 for the 153 '
                        'LSTM/GRU/BiLSTM cells, while the registered F1 batch is 2048 (COMMON_HPARAMS), CQ RNN (Modal) and all 204 LO '
                        'cells ran at 2048, and tools/vastai_run_family.sh defaults to 2048 with accumulation 1 for recurrent families',
     'status': 'OPEN 2026-10-17', 'blocks': ['CQ family comparison RNN vs LSTM/GRU/BiLSTM', 'CQ vs LO cross-task statements', 'CQ F1 '
                                             'numbers entering 03_claims'],
     'needs': 'the run manifests of the 153 cells: batch_size, micro_batch_size, accumulation_steps (shared_phase records all three)',
     'code_fact_2026-10-17': 'tools/vastai_train_shared.py writes batch_size = --batch-size (the optimisation batch) and micro_batch_size '
                             'separately, and the ingest (RESOURCE_FIELDS, 20de6db) carries both; a resource table column named batch_size '
                             'therefore reads the optimisation batch unless the report generator relabelled micro_batch_size. The CQ bundle '
                             'folder is named vastai_f1_batch2048_seed42 while the table says 512: one run_manifest.json settles it',
     'options': ['(a) if batch_size = 512 with accumulation_steps 1: rerun the 153 cells at 2048 (estimate 13-20 L4-hours from the LO '
                 'wall_s of 280-354 s per cell at 2048; CQ has more channels) and quarantine the 512 cells as a labelled sensitivity',
                 '(b) register 512 as the CQ F1 batch for the VastAI families, rerun CQ RNN on VastAI at 512 (51 cells, about 5-7 '
                 'L4-hours) so that the four CQ families share one configuration, and state the CQ/LO batch difference in the paper',
                 '(c) if 512 is the micro-batch of a 4 x 512 accumulation (batch_size 2048 in the manifest): only the resource fact '
                 'label needs correcting; no rerun'],
     'recommendation': '(a); (c) if the manifests show it; (b) only if GPU budget forbids (a)',
     'status_2026-10-19': 'RESOLVED BY RERUN (option (a) executed by the team, author ratification of the archive rule pending): '
                          '153 LSTM/GRU/BiLSTM cells rerun at batch 2048 on one runner / L4 and ingested as one ingest_id; the '
                          'historical manifests confirmed batch_size = 512 with no micro_batch_size/accumulation_steps fields; the '
                          '512 set stays archived as a labelled sensitivity. Measured batch effect (2048 minus 512, 12-cell means): '
                          'AccTEMPO +0.002 to +0.006 per family (per pipeline -0.010 to +0.016), macro-F1 -0.0003 to +0.005 '
                          '(per pipeline -0.011 to +0.016); Spearman of the pipeline ranking between the two batches 0.86-0.97 by '
                          'AccTEMPO but only 0.26-0.68 by macro-F1, i.e. pipeline differences in macro-F1 (range 0.705-0.723) are '
                          'at the level of a configuration perturbation and need seeds 43/44 plus CIs before any ranking claim'},
    {'id': 17, 'topic': 'LO W1 reporting after the 2026-10-16 diagnosis: W1 is the registered primary LO window, but its TEST block C '
                        'holds class E in a single offering (1,000 of 1,000) with an E prior 3.9x VALIDATION and 34x TRAIN, TEST '
                        'macro-F1 sits at or below the majority reference (0.321-0.325 vs 0.330) at every prefix while VALIDATION '
                        'reaches 0.46-0.55, and the gap grows from P1 to P4 (0.139 -> 0.230), which the validation-prefix truncation '
                        'mechanism cannot produce (P4 has no truncation)',
     'status': 'OPEN 2026-10-17', 'blocks': ['every LO W1 claim', 'LO section of Meta-Dataset-Report §3.2', 'LO rows of the paper tables'],
     'options': ['(a) keep W1 primary and 3-class; publish per-window x per-phase x per-class tables with the single-offering flag, no CI '
                 'for E (offering-cluster bootstrap undefined with one offering), and describe LO W1 as a single-offering stress test',
                 '(b) in addition to (a), register a 2-class secondary view I/D vs {G, E} for LO (TEST W1 minority 1,525; W3 1,108) '
                 'before reading any further LO result; a contribution-level change (00_contributions, METRIC_DEF v1.3)',
                 '(c) re-pair T1 or swap the roles of B and C: not recommended after TEST has been read; would need a new split_version, '
                 'new TEST prefix views and the 204 LO cells rerun (about 17 L4-hours at 300 s per cell)'],
     'prerequisite_diagnostics': 'POST_MATERIALIZE_CHECKS[15] items (static ablation, static-only probe, per-class per-phase tables for '
                                 'B and C, hash-matched cohorts) must be in hand before the author chooses',
     'evidence_2026-10-25': 'all prerequisites are now in hand (ablation P1 table, static-only probe, full 1,632-cell LO tables, '
                            'cohort audit computed). LO 1,632 cells: VALIDATION - TEST macro-F1 is +0.139 / +0.193 / +0.214 / +0.230 '
                            '(P1-P4) on W1, +0.006 / +0.004 / +0.009 / +0.014 on W2 and -0.073 / -0.053 / -0.064 / -0.057 on W3, so '
                            'the gap is a W1 (block C) property, not a model or contract property; TEST recall of E on W1 is at most '
                            '0.007 over all 68 configurations x 4 phases (W2 up to 0.18, W3 up to 0.59); the ablation (LSTM W1, V0 '
                            'and V8) shows that removing the statics does not close the gap (V0: VALIDATION 0.412 -> 0.460 without '
                            'statics, TEST 0.325 -> 0.326; V8: 0.462 -> 0.443 / 0.323 -> 0.324)',
     'recommendation_2026-10-25': '(a): keep W1 primary and 3-class, publish the per-window x per-phase x per-class tables with the '
                                  'single-offering flag and no CI for E on W1, and describe LO W1 as a single-offering stress test in '
                                  'which the 2020 cohort offering of class E is not predictable from any earlier offering; (b) only '
                                  'if the author wants a 2-class LO view as a registered secondary contribution',
     'code_fact_2026-10-17': 'the 15 LO static fields are now listed in tools/audit_prefix_validation_alignment.py (d8e9670): eleven '
                             'course-catalog attributes (ex_counts, resource_count, teacher_* x5, school_* x5), gender, timeline_source, '
                             'window_duration_seconds, split_rule_version (excluded since e17ae6e); the eleven catalog attributes are '
                             'constant inside a course and jointly identify it, so the static branch carries course identity by design; '
                             'tools/probe_static_only.py (review patch 2026-10-17b) measures how much of B versus C it explains',
     'recommendation': '(a) now; (b) as an author decision because it changes the contribution contract',
     'evidence_2026-10-19': 'static-only probe LO W1/V0 (REPORT_LO 19/10 §3, tools/probe_static_only.py): with class_weight balanced, '
                            'COURSE_FINGERPRINT alone recalls 76% of E and 54% of G on VALIDATION (balanced accuracy 0.642) and 0% of E '
                            'on TEST (balanced accuracy 0.207, below chance); NON_COURSE (gender, timeline_source, window_duration_seconds) '
                            'recalls 84% of E on VALIDATION and 6% on TEST; unweighted probes predict I/D only. The offering-identity '
                            'shortcut therefore reproduces the direction of the VALIDATION-TEST gap from the static branch alone; the '
                            '2-cell ablation remains the test of how much of the RNN gap it carries',
     'evidence_2026-10-28': 'the complete v2-contract grid (13 fields, no timeline_source) reproduces the W1 gap: VALIDATION - TEST '
                            'macro-F1 +0.140 / +0.192 / +0.219 / +0.236 at P1-P4 over 68 configurations (r3: +0.139 / +0.193 / '
                            '+0.214 / +0.230), balanced accuracy +0.126..+0.167; W2 +0.004..+0.011; W3 -0.061..-0.073. Recall E on W1 '
                            'TEST is 0 in 261 of 272 cells (max 0.002); the W1 TEST E support is the single 2020 offering (n = 1,000). '
                            'The contract change therefore moves nothing; (a) is the presentation rule with complete evidence',
     'status_2026-10-28': 'OPEN; evidence complete for (a); nothing further to run',
     'status_2026-11-01': 'RATIFIED (a) by the author on 2026-11-01 (Q-04): the LO W1 single-offering class E is presented as a finding, the '
                          'contract is unchanged; facts must carry the single-offering flag (M-05) [Ra_soat_tien_do_2026-11-01 §9]'},
    {'id': 18, 'topic': 'AccTEMPO_M3 structure (METRIC_DEF.acctempo_structure_note_2026-10-17): the seed-42 pipeline ranking is an '
                        's_ent ranking; balanced pipelines gain +0.056 (CQ) / +0.066 (LO) AccTEMPO with macro-F1 -0.002 / +0.009, '
                        'PR-AUC -0.026 / -0.022, ROC-AUC -0.016 / -0.090 and worse NLL/ECE; Spearman(AccTEMPO, macro-F1) across the 17 '
                        'CQ pipelines is -0.10 to 0.48 and Spearman(AccTEMPO, PR-AUC) is -0.74 to -0.80',
     'status': 'OPEN 2026-10-17', 'blocks': ['the pipeline-recommendation narrative (C-contribution on AccTEMPO)', 'REC_RULE objective'],
     'options': ['(a) keep v1 as the preregistered primary, make the decomposition (S_perf, S_san+, s_ent) and v2 mandatory in every '
                 'table and discuss the hedging reward explicitly in the paper',
                 '(b) preregister AccTEMPO_M4 = S_perf^0.6 x S_san+_v2^0.4 (s_cal instead of s_ent) as the primary for the paper and '
                 'keep v1 as the sensitivity; the meta-dataset keeps both columns, so no rerun is needed',
                 '(c) keep v1 and report S_perf as the headline performance metric with AccTEMPO as the secondary'],
     'recommendation': '(a) for the meta-dataset release; (b) or (c) only by written author decision recorded in 00_contributions',
     'evidence_2026-10-21': 'CQ R3 window x phase tables (TEST, mean of 17 pipelines, every family): W2 macro-F1 rises P1 -> P4 '
                            '(0.63 -> 0.66), balanced accuracy 0.62 -> 0.69, recall of the average class 0.55 -> 0.75, while s_ent '
                            'falls 0.41-0.46 -> 0.16-0.23 and AccTEMPO falls 0.68 -> 0.56; W3 macro-F1 0.73 -> 0.81 while AccTEMPO '
                            'falls 0.72 -> 0.69; W1 macro-F1 +0.16 while AccTEMPO +0.02. The composite inverts the phase trend '
                            'because confident predictions lower s_ent. AccTEMPO_M3 v1 therefore cannot carry the early-prediction '
                            'curves or the pipeline ranking in the paper',
     'recommendation_2026-10-21': 'keep v1 in the meta-dataset as preregistered (a), and for every trend or ranking statement in the '
                                  'paper use S_perf / macro-F1 with AccTEMPO_M4 (s_cal) as the composite (b)+(c); record the change '
                                  'in 00_contributions and METRIC_DEF v1.3 before the LO and F2 tables are written',
     'team_update_2026-10-23': 'CQ/registries.CQ_METRIC_AND_QA23_POLICY (5b14052, policy_id cq_v2_2_metric_qa23_closure_20261023) '
                               'writes the recommendation into the code registry: M3 stays the preregistered primary of the '
                               'meta-dataset, paper phase trends and rankings read S_perf / macro-F1 / balanced accuracy, M4 is the '
                               'sensitivity composite; the R4 export carries acctempo_m4 = S_perf^0.6 x S_san+_v2^0.4 for all 1,632 '
                               'cells. The team calls it a closure decision; it is still the author\'s decision to ratify',
     'evidence_2026-10-23': 'PatchTST V0 vs the four recurrent V0 cells (TEST, 12 window x phase cells): macro-F1 differs by -0.002 '
                            'on average (range -0.012 to +0.014; PatchTST first in 3 cells, last in 3), balanced accuracy -0.011, while '
                            'M3 differs by +0.034 on W1 (PatchTST first in all 4 W1 cells with the lowest macro-F1 at W1/P1: 0.594 vs '
                            '0.605-0.609) and -0.022 on W2 (last in all 4), because s_ent is +0.16 (W1/P1) and -0.08 (W2/P1) against '
                            'the recurrent V0 mean. M4 also falls P1 -> P4 on W2 (RNN mean of 17: -0.092; PatchTST -0.074) because '
                            's_leak of the V0 parent at W2 falls 0.232 -> 0.019 (a data property shared by every model), so even M4 '
                            'cannot carry the W2 phase trend; S_perf / macro-F1 remain the only trend metrics',
     'status_2026-10-23': 'READY FOR RATIFICATION: the team policy equals recommendation_2026-10-21; ratify it in 00_contributions and '
                          'METRIC_DEF v1.3, or object before the F2 grid and the LO tables are written'},
    {'id': 19, 'topic': 'disposition of the two non-catalog static inputs: timeline_source (which schedule fallback materialised the '
                        'offering: course timeline, global template, enrollment-anchored proxy) and window_duration_seconds '
                        '(offering_end_date minus enrollment time, the quantity behind the P1-P4 cutoffs) sit in the tensor of every '
                        'completed run; the team labels both RETAIN_AS_CONTEXT, which conflicts with the context__ convention (context '
                        'columns never enter tensors)',
     'status': 'OPEN 2026-10-17', 'blocks': ['STATIC_FEATURE_CONTRACT final dispositions', 'any rerun decided under 16 or 17'],
     'options': ['(a) keep both IN_TENSOR, state them in the paper as enrollment-timing and materialisation-regime inputs, and publish '
                 'the static-only probe next to the model results',
                 '(b) move timeline_source to CONTEXT_ONLY (it is a materialisation choice, not a learner attribute) and keep '
                 'window_duration_seconds IN_TENSOR; applies to reruns only, completed runs are labelled as they ran',
                 '(c) move both to CONTEXT_ONLY'],
     'recommendation': '(b), bundled with whichever rerun 16/17 triggers; never a silent change between runs of one grid',
     'team_proposal_2026-10-19': 'REPORT_LO 19/10 §4 proposes the same split: timeline_source CONTEXT_ONLY, window_duration_seconds '
                                 'IN_TENSOR if shown known at prediction time (the code derives it from window_end_exclusive and '
                                 'enroll_time, i.e. schedule-based); not applied to completed runs',
     'status_2026-10-25': 'RATIFIED (b) by the author on 2026-10-24 and implemented by the team in c225961 (LO contract v2: '
                          'timeline_source CONTEXT_ONLY and in model.data.IDENTITY_OR_PROVENANCE, window_duration_seconds IN_TENSOR, '
                          'fit_layout allowlist for LO); completed historical-layout runs keep their recorded layout'},
    {'id': 20, 'topic': 'static branch policy for every future grid (F1 reruns, F2, seeds 43/44): the eleven COURSE-grain catalog '
                        'fields act as an offering-identity shortcut (LO W1: 76% E recall on VALIDATION, 0% on TEST from the static '
                        'branch alone; CQ W1: course fingerprint at chance on VALIDATION and below chance on TEST, 0.215), while '
                        'window_duration_seconds and gender carry transferable enrollment-timing signal (CQ NON_COURSE balanced '
                        'accuracy 0.49 VALIDATION / 0.54 TEST)',
     'status': 'OPEN 2026-10-19', 'blocks': ['STATIC_FEATURE_CONTRACT v2', 'F2 grid launch', 'seeds 43/44', 'any LO rerun'],
     'options': ['(a) keep the full static branch; publish SEEN/UNSEEN slices and the static-only probe next to every table and '
                 'name the shortcut in the paper',
                 '(b) static branch = gender + window_duration_seconds (+ masks) for every new grid; course fingerprint and '
                 'timeline_source become context columns; the 357 completed F1 cells (CQ 153 + LO 204) are relabelled "with '
                 'catalog statics" and rerun only if the author wants one contract across the paper (about 40-55 L4-hours at the '
                 'observed 280-354 s per LO cell and a CQ cell of similar order)',
                 '(c) (b) for LO only, where the shortcut inflates VALIDATION; CQ keeps the full branch'],
     'prerequisite': 'the 2-cell ablation (LO W1 V0 and V8, LSTM, no statics) and the same two cells with gender + '
                     'window_duration_seconds only: four runs, under one L4-hour',
     'recommendation': '(b) if the ablation shows that VALIDATION falls towards TEST without the catalog fields; it also removes the '
                       'course-identity confound from the F2 comparison before that grid starts',
     'team_update_2026-10-21': 'the ablation ran (83c5056 --static-ablation; LO W1 V0 and V8, LSTM, no_static and gender_duration, '
                               'batch 2048, exploratory runs without a contract, own prediction salt, hash-matched SEEN/UNSEEN x '
                               'STRICT/OVERLAP slices). The team\'s text summary (tools/append_lo_static_ablation_report.py): without '
                               'statics VALIDATION P1 of V0 does not fall against the historical baseline, V8 falls; TEST P1 macro-F1 '
                               'changes little; E recall stays 0. The numbers (ablation_comparison.csv, P1-P4) were not delivered. If '
                               'confirmed, the dynamic branch alone also carries the offering regime (activity counts are bounded by '
                               'the course catalog), so removing the catalog statics would not remove the shortcut and option (b) '
                               'loses its main argument; the honest framing of LO W1 (decision 17 (a)) becomes the primary route',
     'needs': 'ablation_comparison.csv and the ablation report; then decide between (a) and (b)',
     'team_update_2026-10-23': 'no ablation numbers delivered (third round); 585343e adds the full LO matched-replay launcher '
                               '(204 cells, batch 2048, historical layout, NVML) that reads TEMPO_PREDICTION_SALT from '
                               'reference/ablation_salt: if that salt differs from the salt of the 204 Modal/VastAI LO runs, the '
                               'hash-matched cohort join between the old and the replayed LO grid is impossible and only aggregate '
                               'comparisons remain; state the salt provenance before the replay starts',
     'evidence_2026-10-25': 'ablation P1 (LSTM, W1, batch 2048, L4; exploratory runs with their own salt): V0 baseline_historical '
                            'VALIDATION macro-F1 0.4117 / TEST 0.3250 (epoch 2); V0 no_static 0.4595 / 0.3261 (epoch 12); V0 '
                            'gender_duration 0.4651 / 0.3266 (epoch 12); V8 baseline 0.4622 / 0.3230 (epoch 1); V8 no_static 0.4433 / '
                            '0.3238; V8 gender_duration 0.4516 / 0.3238; E recall 0 on TEST in all six. The VALIDATION - TEST gap '
                            'does not close without the statics (V0: 0.087 -> 0.133; V8: 0.139 -> 0.120), so the dynamic branch '
                            'alone carries the course regime and option (b) of 2026-10-19 loses its argument; the team closed the '
                            'contract as v2 = 11 catalog fields + gender + window_duration_seconds (c225961), i.e. option (a) with '
                            'timeline_source removed per decision 19 (b)',
     'options_2026-10-25': ['(a-v2) ratify contract v2 for every new LO layout and rerun the LO F1 seed-42 grid under v2 (204 cells, '
                            'about 12-15 L4-hours with NVML) so that F1, F2 and seeds 43/44 share one contract; the historical and '
                            'the NVML-replay grids become archived evidence',
                            '(a-hist) keep the historical 15-field F1 grid (or its NVML replay) as the paper grid and run LO F2 with '
                            'static_layout_policy = historical_reference, which keeps timeline_source in the tensor against decision '
                            '19 (b)',
                            '(mixed) keep the historical F1 grid and run F2 under v2: two static contracts inside one F1-vs-F2 table, '
                            'not recommended'],
     'recommendation_2026-10-25': '(a-v2); the cost is small and the ablation shows the contract change does not move TEST; '
                                  'decision 17 (a) stays the presentation rule for W1 whichever contract is chosen',
     'status_2026-10-25': 'READY FOR RATIFICATION (a-v2)',
     'team_update_2026-10-27': 'tools/vastai_run_lo_static_v2_grid.sh (0851aed) implements the (a-v2) replay (204 cells, '
                               'static_layout_policy current = contract v2, NVML, new output root, one family per instance); not run '
                               'yet; it reads the salt from reference/ablation_salt, so cohort joins with the historical grid are '
                               'not possible, which is acceptable if the v2 grid supersedes it; the replay must wait for check 27 '
                               '(training-loop equivalence after 044d6c7) and for the author\'s ratification',
     'team_update_2026-10-28': '(a-v2) EXECUTED by the team on 2026-10-26 before ratification: 204 cells (RNN, LSTM, GRU, BiLSTM x '
                               'V0-V16 x W1-W3, seed 42) at runner b0e5ae1 with static_layout_policy current = 13-field contract '
                               '(ex_counts, gender, resource_count, school_* x5, teacher_* x4, window_duration_seconds), batch 2048, '
                               'L4, NVML; audits B = 2,000 for the four families; closure archive sha256 9108...40d3. Family TEST '
                               'means move by at most 0.007 (macro-F1, balanced accuracy, M3) against r3; the 68-configuration '
                               'window x phase means move by at most 0.024 (recall G, W3). The grid was run before check 27 closed '
                               '(the whole grid is on the post-044d6c7 loop, so it is internally consistent)',
     'status_2026-10-28': 'READY FOR RATIFICATION (a-v2); ratification now designates the v2 grid as the LO F1 paper grid and the '
                          'historical and r3 grids as archived evidence',
     'status_2026-11-01': 'RATIFIED (a-v2) by the author on 2026-11-01 (Q-04): the 13-field static contract v2 applies to every new grid '
                          '[Ra_soat_tien_do_2026-11-01 §9]'},
    {'id': 21, 'topic': 'QA23 review list for CQ (eb80516, audit_cq_label_proxy.REVIEWED_BEHAVIOURAL_PREFIX_BASES): problem_count, '
                        'exercise_count, problem_context_count, score_sum, correct_problem_count, attempts_sum, '
                        'problem_catalog_coverage, problem_score_catalog_coverage are exempted from the label-proxy flag as '
                        '"prefix-observed behaviour, not label-derived", although they are the observed partials of the components '
                        'the CQ label is built from and QA23 flags them for high association with the final proximity',
     'status': 'OPEN 2026-10-21', 'blocks': ['feature_dictionary_v1 (CQ part) sign-off', 'QA23 statement in the paper'],
     'options': ['(a) ratify the list as the preregistered QA23 decision with the rationale in the registry (observed-so-far '
                 'behaviour is the legitimate signal of early prediction; the prefix mask guarantees no future values)',
                 '(b) ratify but report, per phase, the association of each exempted base with the label (|rho|, NMI) next to the '
                 'model results, so a reader can see how much of P4 performance is the accumulated label component itself',
                 '(c) exclude score_sum, correct_problem_count and problem_score_catalog_coverage (the score-bearing partials) and '
                 'keep the count/coverage features'],
     'recommendation': '(b); (c) only if the author wants early prediction to mean behaviour without partial scores, which changes '
                       'the feature contract and requires reruns',
     'team_update_2026-10-23': 'tools/export_cq_qa23_reviewed_behavioural_linkage.py extracts, per phase P1-P4 and per admissible '
                               'prefix column, n_obs, Spearman rho and NMI of the eight bases against the label and refuses any row '
                               'whose review note is not reviewed_prefix_observed_behaviour__not_label_derived; the 23/10 report '
                               'prints the per-phase maximum only: |rho| max 0.614 (P1), 0.729 (P2), 0.832 (P3), 0.879 (P4); NMI max '
                               '0.219 / 0.261 / 0.312 / 0.342 (8 / 16 / 24 / 32 columns). CQ_METRIC_AND_QA23_POLICY records the list '
                               'as APPROVED_PREFIX_OBSERVED_BEHAVIOUR',
     'label_construction_fact_2026-10-23': 'CQ label G = COELO^0.4 x AFELO^0.2 x ACELO^0.4 (cq_component_builder); COELO averages '
                                           'scaled attempts_sum and problem_count / course_problem_count, ACELO uses score_sum / '
                                           'course_full_score, so the eight bases are the running partials of the label\'s own inputs; '
                                           'at P4 (90 % of the window) they approach their final values, which is why |rho| reaches 0.88 '
                                           'and why P4 macro-F1 (W3: 0.81) is not an early-prediction result',
     'status_2026-10-23': 'option (b) implemented at summary grain; to ratify, the per-base table (8 bases x prefix x phase, '
                          'cq_qa23_reviewed_behavioural_linkage.csv) must be delivered and the paper must state the label '
                          'construction next to every P3/P4 CQ number',
     'status_2026-10-25': 'RATIFIED (b) by the author on 2026-10-24 with the two conditions; the per-base table is still not '
                          'delivered (unchanged in the regenerated 23/10 report)'},
    {'id': 22, 'topic': 'F2 grid launch for CQ seed 42 (48 remaining cells, V1-V16 x W1-W3) after the PatchTST V0 pilot of 2026-10-23: '
                        'the report concludes the pilot "ran per contract" and proposes opening the remaining pipelines',
     'status': 'OPEN 2026-10-23',
     'blocks': ['F2 grid launch (CQ)', 'the F1 vs F2 comparison table', 'C3 time/energy facts for F2'],
     'facts': ['pilot results: PatchTST V0 is at parity with the recurrent V0 cells on macro-F1 (mean -0.002, 12 TEST cells) and '
               'balanced accuracy (-0.011); the only systematic differences are s_ent (hedging) and the derived M3',
               'checkpoint selection: W3 selected epoch 1 of 6 (patience 5), W1 8 of 13, W2 7 of 12; VALIDATION W3 macro-F1 of the '
               'selected checkpoint is 0.62 (P1) / 0.83 (P4) against 0.68 / 0.90-0.91 for the recurrent V0 cells, while TEST W3 is at '
               'parity (0.81 vs 0.81-0.82): the W3 run peaked after one epoch and degraded on VALIDATION afterwards',
               'VALIDATION - TEST macro-F1 on W2 grows to +0.11 at P4 for PatchTST (recurrent V0: -0.006), i.e. the transformer fits '
               'the seen-course VALIDATION better than the recurrent models without a TEST gain',
               'the 23/10 report does not show model_revision, static_layout_policy, runner commit, GPU, elapsed time or NVML energy '
               'of the three runs, and its checkpoint table has a blank Score VAL column (report tool reads selection_score, the '
               'audit writes best_score); review patch 2026-10-23 derives these from the manifests and fails on a deviation',
               'S2 seeds 43/44 are still missing, so the F2 grid is seed 42 only, like F1; decision 20 (static branch) is LO-driven, '
               'the CQ static-only probe showed no course-identity shortcut (fingerprint at chance on VALIDATION)'],
     'options': ['(a) launch the 48 CQ cells now with the pinned image, the historical static layout of the recurrent grid and '
                 'accumulation 4 x 512',
                 '(b) launch after the three pilot manifests, train_history and the SEEN/UNSEEN x STRICT/OVERLAP slice table of the '
                 'pilot are delivered and the W3 epoch-1 selection is explained (per-epoch VALIDATION curve); if the curve shows '
                 'instability at lr 1e-3 for the transformer, preregister any PatchTST-specific change before the grid, not after',
                 '(c) hold F2 until decisions 18 and 20 are ratified and S2 seeds 43/44 exist'],
     'recommendation': '(b) for CQ (about one day of evidence work, no rerun); LO F2 waits for decision 20; whatever is launched '
                       'must record static_layout_policy = historical_reference with the CQ reference layout sha256 so that F2 and F1 '
                       'cells share one static contract',
     'status_2026-10-25': 'RATIFIED (b) by the author on 2026-10-24; the three conditions are met in the regenerated 23/10 report '
                          '(manifests: section 8b; epoch history: 8c; cohorts: 8e) although the files are not in input/results/. '
                          'Two facts change the launch question: the pilot ran with static_layout_policy = current, not with the '
                          'historical layout of the recurrent grid (difference: the constant split_rule_version column; the two '
                          'static lists must be printed side by side once and the 48 cells must keep the pilot policy so that F2 is '
                          'one contract), and the epoch history shows optimisation instability at the shared lr 1e-3 (W2 and W3 '
                          'VALIDATION macro-F1 swing by up to 0.09-0.15 between consecutive epochs; W3 selected epoch 1). The '
                          'launch itself is now decision 23',
     'status_2026-10-27': 'shard plan, sharded launcher and verification adopted (af079d8); launch itself governed by decision 23',
     'cohort_evidence_2026-10-25': 'PatchTST V0 TEST STRICT macro-F1 SEEN vs UNSEEN course: W2 P4 0.782 vs 0.614 (n 132,387 vs '
                                   '31,137), W3 P4 0.722 vs 0.897, W1 UNSEEN slices carry 0-3 rows of class c2 and are not readable; '
                                   'VALIDATION W2 P4 0.785 vs 0.776. The recurrent V0 cohorts at the same grain are not printed, so '
                                   'the +0.11 VALIDATION - TEST gap of W2 remains unexplained'},
    {'id': 23, 'topic': 'F2 grid execution policy after the pilot provenance (2026-10-25): cost and optimisation stability. Pilot: 5.9 '
                        'L4-hours and 0.42 kWh per run (epoch time 1,738-2,490 s, 6-13 epochs), about 125x a recurrent run; the 48 '
                        'remaining CQ seed-42 cells cost about 282 L4-hours and 20 kWh; D-N3 (A) implies about 306 PatchTST runs over '
                        'two tasks and three seeds (of the order of 1,800 L4-hours, 130 kWh). The per-epoch VALIDATION curve is noisy '
                        '(train CE spikes x9.5 at W1 epoch 3; W3 peaks at epoch 1 and never recovers; W2 swings 0.617-0.707 between '
                        'epochs 7-10), so the VALIDATION-selected checkpoint of a 48-cell grid would partly be a draw and the F1-vs-F2 '
                        'comparison would be confounded by optimisation rather than architecture',
     'status': 'OPEN 2026-10-25',
     'blocks': ['launch of the 48 CQ F2 cells', 'F2 on seeds 43/44 and on LO', 'the F1-vs-F2 statement of the paper', 'C3 cost facts'],
     'options': ['(a) launch the 48 CQ cells now at the registered configuration (HP_PATCHTST_CHANNEL_INDEPENDENT_v2, lr 1e-3, no '
                 'warm-up, no gradient clipping), archive every train_history and disclose the instability; 282 L4-hours, 20 kWh',
                 '(b) first a 2-run stabilisation pilot (W3 V0 and W2 V0, about 10 L4-hours) with a candidate '
                 'HP_PATCHTST_CHANNEL_INDEPENDENT_v3 (lower learning rate with one warm-up epoch and gradient-norm clipping; the '
                 'recurrent families untouched); if the VALIDATION curve is monotone or the selected epoch moves away from epoch 1, '
                 'pre-register v3 in the registry and the Method section, rerun the 3 pilot cells, then the grid; otherwise (a)',
                 '(c) amend D-N3 (A): full F2 grid on seed 42 only, seeds 43/44 on V0 and the four imputation-only pipelines '
                 '(5 x 3 windows x 2 seeds = 30 cells per task), F2 LO at the same reduced scope; about one third of the cost'],
     'recommendation': '(b) before any grid; the author decides (c) on budget grounds, with the cost figures above recorded in the '
                       'Method section either way; whichever option, parallel execution needs the shard plan of review patch '
                       '2026-10-25 and one runner commit per ingest',
     'code_readiness_2026-10-25': 'training, audit, cohort and ingest code are adequate for a parallel F2 grid (52 tests; manifests '
                                  'carry release identity, layout hash, runner commit, NVML; runner refuses to overwrite; ingest asserts '
                                  'uniform execution and unique cells); missing before launch: a shard plan (the launchers run every cell '
                                  'sequentially and would duplicate work on several instances), the explicit layout policy in the '
                                  'launcher, per-seed input trees for seeds 43/44 (S2 seeds 43/44 not yet materialised), the printed '
                                  'static lists of the historical and the current CQ layout',
     'team_pilot_2026-10-26': 'option (b) executed by the team before the author decided: lr 3e-4, linear per-update warm-up over '
                              'one epoch, gradient-norm clip 1.0, batch 2048 = 4 x 512, layout current, run_purpose '
                              'STABILITY_PILOT_D23, runner 044d6c7+, L4, NVML; W2/V0 selected epoch 4 of 9 (old 7 of 12), W3/V0 '
                              'selected epoch 1 of 6 (old 1 of 6); 9.7 L4-hours, 0.70 kWh; audit B = 2,000 complete '
                              '(REPORT_CQ_F1_D23_PATCHTST_CONFIGURATION_2026-10-27). Descriptive means over P1-P4: W2 TEST macro-F1 '
                              '-0.009, balanced accuracy +0.005, VALIDATION macro-F1 +0.005; W3 TEST macro-F1 -0.025, balanced accuracy '
                              '-0.027, VALIDATION macro-F1 +0.041; VALIDATION - TEST on W3 turns from -0.032 to +0.034. The report '
                              'declares the criterion met because two runs completed; the registered criterion (VALIDATION curve '
                              'monotone or selection away from epoch 1) is not evaluated: no per-epoch history is printed and W3 '
                              'still selects epoch 1',
     'status_2026-10-27': 'OPEN; criterion not demonstrated. Reading: the W3 selection at epoch 1 under both protocols points to '
                          'temporal drift between TRAIN A-E and VALIDATION F (the model is best for F before it fits A-E further) '
                          'rather than to optimisation instability; the W2 move 7/12 -> 4/9 is consistent with a calmer curve but '
                          'is unproven without the history; the TEST differences are one-seed descriptives and must not choose the '
                          'protocol',
     'options_2026-10-27': ['(a) run the 48 CQ cells at the registered protocol (lr 1e-3, no warm-up, no clipping), archive every '
                            'train_history, disclose the instability in the Method section and keep the D23 pilot as a documented '
                            'sensitivity (2 cells)',
                            '(b\') pre-register HP_PATCHTST_CHANNEL_INDEPENDENT_v3 = D23 on the grounds that warm-up and clipping are '
                            'standard transformer practice (not on the pilot numbers), rerun the three V0 pilot cells under v3 '
                            '(about 18 L4-hours) and run the 48 cells under v3, so that all 51 F2 cells share one protocol; note '
                            'that W3 keeps selecting epoch 1 under v3',
                            '(c) reduce the F2 scope as in options_2026-10-25'],
     'recommendation_2026-10-27': 'first the two D23 histories next to the old ones (review patch 2026-10-27 prints them with the '
                                  'criterion); if the D23 curves are unimodal without spikes, (b\') is defensible and documented; '
                                  'otherwise (a). Either way the registered protocol is what the F2 gate, the shard verifier and '
                                  'the ingest enforce until the registry entry changes, and no F2 cell starts before the author '
                                  'signs the protocol',
     'team_update_2026-10-28': 'the team evaluated the D23 histories (not delivered to the author) and reports that the W3 VALIDATION '
                               'curve is not unimodal and still selects epoch 1, so the registered criterion fails; LO/registries.py '
                               '@ 29da3b2 locks the F2 protocol at the registered v2 values (lr 1e-3, warm-up 0, no clipping, '
                               'PRIMARY_GRID) = option (a); the D23 pilot is kept as sensitivity evidence; the 48 cells are not run',
     'status_2026-10-28': 'TEAM-LOCKED (a); READY FOR RATIFICATION. The lock agrees with recommendation_2026-10-27 for the case '
                          '"otherwise (a)"; the author still signs it and the two D23 histories (or the regenerated D23 report with '
                          'section 4b) belong in the package. Open consequence: decision 25 (pilot cells vs runner identity)',
     'status_2026-10-29': 'unchanged; the 29/10 CQ report repeats the lock ("protocol gốc được nhóm khóa") and again prints no D23 '
                          'epoch history',
     'team_proposal_2026-10-31': 'BAO_CAO_TONG_HOP_R21 section 10 asks the author to ratify protocol v2 (lr 1e-3, warm-up 0, no clipping) as the '
                                 'F2 configuration and to use the three NEW V0 runs (current layout) as the base of the 48 remaining cells; D23 '
                                 'remains sensitivity; the D23 train_history files are now packaged (R21_evidence/CQ/D23) but not delivered',
     'status_2026-10-31': 'READY FOR RATIFICATION (a); the author signs; the D23 histories arrive with the R21 package',
     'status_2026-11-01': 'RATIFIED (a) by the author on 2026-11-01 (Q-06): protocol v2 (lr 1e-3, warm-up 0, no clipping) is the single F2 '
                          'protocol, the three NEW V0 runs are the base, D23 stays a sensitivity; the 48 CQ and 51 LO cells may open with a '
                          'shard plan from the V0 run root, one runner, no --exclude-completed against the old pilot [Ra_soat_tien_do_2026-11-01 §9; '
                          'Method v0.3 §4.8]',
     'team_update_2026-11-03': 'V1-V6 (18 cells) ran on 31/10-01/11 at runner 29da3b2 alongside the three V0 runs: one runner_git_commit and one '
                               'layout hash across the 21 cells, protocol v2 fields equal in every run contract, audits B = 2,000, salt join '
                               'complete (facts package cq_patchtst_v0_v6_full_facts_20261103, hash-verified); 181.81 L4-hours, 66.91 USD '
                               '(0.368 USD/h, estimate), 13.03 kWh GPU estimate; the per-epoch histories of the three V0 runs are now delivered '
                               '(cq_patchtst_v0_current_20261102/report_facts/training_history.csv): W3 VALIDATION macro-F1 peaks at epoch 1 '
                               '(0.790) and never recovers (0.731, 0.550, 0.677, 0.767, 0.665) with train-CE spikes at epochs 3 and 5, W2 swings '
                               '0.624-0.723 and selects epoch 4, W1 climbs to 0.755 at epoch 20 of 25; in the 18 new cells five selections sit at '
                               'epoch 1-3 (V3/W2 epoch 1 of 6, V0/W3 1 of 6, V3/W3 3 of 8, V4/W2 3 of 8, V6/W1 3 of 8); V7 stopped before completion; '
                               'the report claims nothing beyond seed 42',
     'status_2026-11-03': 'CLOSED (a) by ratification and execution for V0-V6; remaining before V7-V16: decision 32 does not block seed 42; the '
                          'shard-plan sha and the ingest assertion of check 26 for the 30 remaining cells; the instability of W3 (epoch-1 selection '
                          'under both protocols) is disclosed in Method §4.8 and in the threats section with the histories as evidence',
     'status_2026-11-04': 'the scope question of options_2026-10-25 (c) (amend D-N3 (A)) is settled by decision 36: phase 1 = seed 42 only, F1 of '
                          'both tasks and F2 PatchTST CQ V0-V6 (168 cells); V7-V16, LO F2 and seeds 43/44 move to the full release (phase 2) '
                          '[Ra_soat_tien_do_2026-11-04 §1]'},
    {'id': 24, 'topic': 'which LO F1 grid and which static contract enter the paper (2026-10-25): three LO seed-42 grids now exist, the '
                        'historical-layout grid (204 cells, energy NOT_MEASURED, r2 package), its NVML matched replay (204 cells, '
                        'batch 2048, L4, runner of the 2026-10-23 campaign, RNN W1/V0 repaired at 7886a856, ingest r3) and, if '
                        'decision 20 (a-v2) is taken, a v2-contract rerun; the paper needs one grid per task with one contract, one '
                        'runner revision and measured time (energy where estimated)',
     'status': 'OPEN 2026-10-25',
     'blocks': ['LO export into input/results/ (check 25)', 'LO rows of every paper table', 'C3 time/energy facts for LO'],
     'options': ['(a) the NVML replay (r3) as the LO paper grid: NVML energy, one backend, equals the historical facts to 1e-4 '
                 '(shown for BiLSTM; to be shown for RNN, LSTM, GRU), historical 15-field contract; the historical grid becomes '
                 'archived evidence',
                 '(b) a v2-contract rerun (decision 20 (a-v2)) as the LO paper grid: one contract across F1, F2 and seeds; r3 and the '
                 'historical grid archived; about 12-15 L4-hours',
                 '(c) the historical grid: no energy, superseded by r3 for every purpose; not recommended'],
     'recommendation': '(b) if decision 20 (a-v2) is ratified, otherwise (a); in both cases the export must name the runner commit '
                       'per family and the RNN W1/V0 repair',
     'status_2026-10-27': 'OPEN; the (b) launcher exists (0851aed), nothing run',
     'team_update_2026-10-28': '(b) executed de facto: the v2-contract grid is complete (204 cells, one runner b0e5ae1 for the four '
                               'families, NVML, four audits, closure archive sha256 9108...40d3); the RNN W1/V0 repair of r3 is no '
                               'longer needed because every v2 cell was trained by one runner',
     'status_2026-10-28': 'READY FOR RATIFICATION (b); the export of check 25 then names runner b0e5ae1, contract v2 (13 fields), '
                          'the single-offering flag of W1 block C and the registry pipeline mapping',
     'status_2026-11-01': 'RATIFIED (b) by the author on 2026-11-01 (Q-07): the LO static-v2 seed-42 grid (13 fields, runner b0e5ae1) is the LO '
                          'F1 grid of the paper; r3 and the historical grid are archived evidence [Ra_soat_tien_do_2026-11-01 §9]',
     'status_2026-11-03': 'the R4-grain LO export of M-01 (lo_static_v2_grid_seed42_20261102: 1,632 cells with acctempo_m4, 204 resource runs, '
                          'runner b0e5ae1, layout sha256:84761775...) is on the Drive; small files hash-verified, per-cell file (2.4 MB) and '
                          'lo_resource_per_run.csv (76 KB) wait for the sync of decision 31'},
    {'id': 25, 'topic': 'composition of the CQ F2 seed-42 ingest (2026-10-28): the three PatchTST V0 pilot cells of 2026-10-23 were '
                        'trained from runner 7886a856 (registered protocol, layout current, run_purpose PRIMARY_GRID), the 48 '
                        'remaining cells will be trained from e0ae433 or later; assert_uniform_execution requires one runner_sha256 '
                        '(and, with review patch 2026-10-28, one runner_git_commit) per ingest, and tools/f2_shard_plan.py '
                        '--exclude-completed silently plans the 48 cells around the pilot',
     'status': 'OPEN 2026-10-28',
     'blocks': ['the first F2 shard', 'check 26', 'every F2 table'],
     'options': ['(a) rerun the three V0 cells inside the shard plan (no --exclude-completed): 51 cells from one checkout, about 18 '
                 'extra L4-hours and 1.3 kWh; the 23/10 pilot stays archived evidence (check 24)',
                 '(b) keep the pilot cells and register an explicit exception in the ingest (allowlist of the pilot runner with the '
                 'CQ paired-replay receipt as justification); the receipt must then show the pilot checkout on the "before" side',
                 '(c) exclude V0 from the F2 claim (48 cells; V0 only as the pilot reference); not recommended because V0 is the '
                 'imputer_only_ref of every balanced pipeline (N10)'],
     'recommendation': '(a): 6% of the F2 budget buys one runner identity for the whole ingest; (b) only if the budget is exhausted',
     'cost_basis': 'pilot 5.9 L4-hours and 0.42 kWh per cell (REPORT 23/10); 48 cells about 282 L4-hours and 20 kWh',
     'team_proposal_2026-10-29': 'REPORT_CQ_DAY_DU_REPLAY_PATCHTST_2026-10-29 section 14: A = keep the three V0 cells with a registered '
                                 'provenance exception (= option (b) here), B = replay W1/V0 PatchTST first (about 6 L4-hours), C = rerun '
                                 'the three cells (about 18 L4-hours, = option (a)); the team proposes A and asks the author; it notes that '
                                 'model/data.py and model/shared_phase.py changed between 7886a856 and 29da3b2, the PatchTST architecture did '
                                 'not, and that the gradient-accumulation path was reordered',
     'analysis_2026-10-29': 'the reorder is exact: 044d6c7 moved GradScaler.unscale_ before the division by group_rows; the loss scale of '
                            'GradScaler is a power of two (2^16 initial, x2 / x0.5 updates), scaling by a power of two commutes with IEEE '
                            'rounding, so fl(fl(S*G)/N)/S equals fl(G/N) bit for bit for every parameter (only subnormal underflow could '
                            'differ); warm-up 0 and no clipping leave the step unchanged; the recurrent path (accumulation 1) is confirmed '
                            'empirically by the two RNN replays. What the argument does not cover is model/data.py: the CQ current layout '
                            'of a new run must hash to the pilot layout (feature_layout_sha256 equal)',
     'recommendation_2026-10-29': '(b)/A is acceptable and cheaper, provided the exception is receipt-backed: (1) a one-epoch replay of CQ W1/V0 '
                                  'PatchTST at the F2 runner (--max-epochs 1, about 0.6 L4-hours) whose epoch-1 train CE, VALIDATION macro-F1 '
                                  'and CE equal the pilot history row bit for bit (determinism then implies every later epoch), with equal '
                                  'feature_layout_sha256; (2) the exception registered through review patch 2026-10-29 '
                                  '(VASTAI_RUNNER_EXCEPTIONS: cell, runner_sha256, runner_git_commit 7886a856, sha256 of that receipt, '
                                  'registered_by = author); (3) the exception named in the paper package README. If the one-epoch replay '
                                  'differs in any value, (a) rerun. The full B (6 L4-hours) adds nothing beyond (1) under determinism',
     'status_2026-10-29': 'OPEN; team proposal A received; author decides',
     'team_update_2026-10-31': 'RESOLVED BY RERUN = option (a): three new PatchTST V0 runs (W1-W3, seed 42, current layout of 11 static fields '
                               'without timeline_source, registered protocol, run_purpose PRIMARY_GRID, one runner) replace the 23/10 pilot, which '
                               'had a 12-field layout (with timeline_source) and is kept as archived evidence; the report calls it "the user\'s '
                               'decision"; selected epochs W1 20, W2 4, W3 1 (from the builder text; the report itself was not delivered); a '
                               'one-epoch replay of the new W1/V0 run is bit-exact on the three epoch-1 metrics (determinism of the F2 runner)',
     'status_2026-10-31': 'CLOSED BY EXECUTION (a) pending the author\'s acknowledgement; the F2 ingest will have one runner for 51 cells; the '
                          'exception mechanism of review patch 2026-10-29 is not needed for CQ F2 seed 42',
     'status_2026-11-03': 'CLOSED (a): the author ratified the three NEW V0 runs as the base on 2026-11-01 (Q-06) and the facts package shows one '
                          'runner_git_commit 29da3b2 and one feature_layout_sha256 across V0-V6 (21 cells); the run bundles of the three V0 runs '
                          'are on the Drive (cq_patchtst_v0_current_20261102, M-04) with a bit-exact one-epoch replay receipt'},
    {'id': 26, 'topic': 'point-in-time availability of the static branch (2026-10-31, tools/update_cq_static_provenance_20261031.py): the '
                        'catalog attributes (ex_counts, resource_count, teacher_*, school_*) are joined by course_id from course, teacher and '
                        'school profiles whose snapshot date is unknown; gender comes from enrollments; window_duration_seconds is built from '
                        'offering_end_date (scheduled end, proxy branch for some offerings); the source cannot prove that every value was known '
                        'at each prediction cut-off; primary_risk_set is a constant (source 1, input 0) and carries no information',
     'status': 'OPEN 2026-10-31',
     'blocks': ['Method section static branch wording', 'threats to validity', 'the CQ F2 grid claim scope (the team asks to settle the '
                'static contract scope before the 48 cells)'],
     'options': ['(a) keep the 11-field CQ / 13-field LO contracts and declare the assumption in the paper: catalog and profile attributes are '
                 'treated as time-invariant course metadata, the scheduled offering end date is treated as known at enrolment, and the '
                 'SEEN/UNSEEN cohort slices are the empirical check of the course-identity shortcut (decision 20 evidence)',
                 '(b) drop the catalog/profile fields from every new grid (gender + window_duration_seconds + masks only) and rerun F1 '
                 '(CQ 204 + LO 204 cells, about 27 L4-hours) before F2',
                 '(c) (a) now and (b) as a registered sensitivity on V0 only (6 cells)'],
     'recommendation': '(a) with the explicit assumption and the cohort slices, plus the constant primary_risk_set removed from the next contract '
                       'revision (harmless but noise in the layout); (b) only if a reviewer-level objection on course metadata is expected',
     'evidence_2026-10-31': 'ablation of 2026-10-21 (LO V0/V8 without statics: TEST unchanged, VALIDATION gap unchanged); LO v2 grid without '
                            'timeline_source reproduces r3 within 0.007; primary_risk_set audit 18/18 inputs constant',
     'status_2026-11-01': 'RATIFIED (a) by the author on 2026-11-01 (Q-10): the 11-field CQ / 13-field LO contracts stay, the two availability '
                          'assumptions are declared in Method §4.1.2 and in the threats section, the SEEN/UNSEEN cohort slices are the empirical '
                          'check, primary_risk_set is dropped at the next contract revision [Ra_soat_tien_do_2026-11-01 §9; Method v0.3 §4.1.2]',
     'status_2026-11-03': 'evidence for the empirical check grows: 672 SEEN/UNSEEN x STRICT/OVERLAP slices of the PatchTST V0-V6 cells (all OK) and '
                          'the CQ class-offering support table (M-05) are on the Drive; the static-v2 ablation (M-03, decision 30) is still owed'},
    {'id': 27, 'topic': 'use of report-derived numbers in the draft (2026-10-31): input/results now holds CSV tables extracted from the team '
                        'reports (docx of 28/10, 29/10, 23/10, 27/10, 31/10), each traceable to the report file and section and checked '
                        'against the registry and against each other (68-configuration means = means of the 12 cells; label totals = split '
                        'registry); the official L2 export (R21_evidence_20261031, 151 files with a sha256 manifest) has not reached the author',
     'status': 'OPEN 2026-10-31',
     'blocks': ['W-EN-02 / W-EN-03 drafting with numbers', 'T1-EX-08 (03_claims section B)'],
     'options': ['(a) allow report-derived numbers in the draft with the tag [source: results/<package>/<file>, row ...; report-derived] and a '
                 'mandatory re-check against the L2 export before submission',
                 '(b) write the Experiments text now with empty number slots and fill them only from the L2 export',
                 '(c) wait for the export before any Experiments drafting'],
     'recommendation': '(a) for CQ F1 seed 42 (the R4 facts are frozen and the report equals them to 1e-4 on every check); (b) for LO until '
                       'decisions 20/24 are signed; the F2 numbers wait for the 51-cell grid in every case',
     'status_2026-11-01': 'RATIFIED (a) by the author on 2026-11-01 (Q-09): report-derived numbers may enter the draft with the tag '
                          '[source: results/<package>/<file>, row ...; report-derived] and a mandatory re-check against the L2 export before '
                          'submission [Ra_soat_tien_do_2026-11-01 §9]',
     'status_2026-11-02': 'largely superseded for the F1 base tiers: the official R4 export (14 files) and the four LO static-v2 family audits (28 '
                          'files) were copied from the Drive into input/results on 2026-11-02 and check 31 passed (report-derived tables equal the '
                          'facts within 5e-5); the tag now covers only the tables without facts counterpart [Ra_soat_tien_do_2026-11-02]',
     'status_2026-11-03': 'the PatchTST V0-V6 metric cells remain report-derived until the per-cell facts files of the 03/11 package are synced '
                          '(decision 31); the resources, checkpoints, cost, Radius fallback, S2 sampling, class-offering, split and R4/LO mean tables '
                          'are export-sourced (hash-verified small files in input/results)'},
    {'id': 28, 'topic': 'delivery channel of the team evidence (2026-11-02): the shared Drive tree Jobs/{CQ,LO}/organized_moved_20261029 versus the '
                        'zip package R21_evidence_20261031 (151 files)',
     'status': 'CLOSED 2026-11-02', 'author_question': 'Q-11',
     'resolution': 'RATIFIED (a) by the author on 2026-11-02: the shared Drive is the official delivery channel; the R21 placeholder in '
                   'input/results is closed (_superseded/); every missing piece of evidence is copied straight from the Drive and hash-checked '
                   '[Ra_soat_tien_do_2026-11-02 §8]',
     'consequence_2026-11-03': 'the 12 packages of 02-03/11 (facts V0-V6, V0 current, LO export, reconciled slices, provenance draft, Radius audit, '
                               'S2 sampling, class offering, split evidence, release identity, meta-join trial, QA23 detail) are read from the Drive; '
                               'small files hash-verified, large files per decision 31'},
    {'id': 29, 'topic': 'AccTEMPO_M3^(cal) for LO (2026-11-02): the LO static-v2 audits carry no acctempo_m4 column',
     'status': 'CLOSED 2026-11-02', 'author_question': 'Q-12',
     'resolution': 'RATIFIED (c) by the author on 2026-11-02: the draft uses the derived column acctempo_m3_cal_DERIVED (= s_perf^0.6 x '
                   'S_san+v2^0.4, formula verified to 2e-16 on CQ) with the tag "derived"; the team exports acctempo_m4 for LO and the tag is '
                   'replaced before submission [Ra_soat_tien_do_2026-11-02 §8]',
     'status_2026-11-03': 'the team export of M-01 (lo_static_v2_grid_seed42_20261102) carries acctempo_m4 computed as '
                          'max(s_perf, 0.001)^0.6 x max(s_san_plus_v2, 0.001)^0.4; once the per-cell file is synced and equals the derived column '
                          'within 1e-12 the "derived" tag is retired'},
    {'id': 30, 'topic': 'static-block ablation of the LO grid (2026-11-02): the existing ablation (2026-10-19) is exploratory, LSTM, W1, historical '
                        '15-field layout, runner_git_commit null; Method §4.1.2 describes an ablation on the paper grid',
     'status': 'CLOSED 2026-11-02', 'author_question': 'Q-13',
     'resolution': 'RATIFIED (c) by the author on 2026-11-02: the 19/10 ablation stays descriptive evidence (layout, family and window named); '
                   'the team runs no_static (and gender_duration if cheap) on the static-v2 grid, W1, V0 and V8, same family, runner b0e5ae1, '
                   'before submission (M-03); §4.1.2 unchanged [Ra_soat_tien_do_2026-11-02 §8]',
     'status_2026-11-03': 'not delivered (M-03 open)'},
    {'id': 31, 'topic': 'transfer route for the remaining Drive evidence (2026-11-02): 67 cohort-audit configurations, S2 manifests and ledgers, '
                        'receipts, L0_registry, D23 and replay bundles, static-contract audit; and from 03/11 the per-cell files of the new packages',
     'status': 'CLOSED 2026-11-02', 'author_question': 'Q-14',
     'resolution': 'RATIFIED (a) by the author on 2026-11-02: the author syncs the listed Drive subfolders to '
                   'input/results/_drive_mirror_20261029/Jobs/... (archives above 100 MB excluded); the writing side verifies on the computer; the '
                   'connector route stays for small files [Ra_soat_tien_do_2026-11-02 §8-§9]',
     'status_2026-11-03': 'sync not yet done; the connector route delivered 47 small files of 12 packages on 03/11; the list of large files with Drive '
                          'ids is in analysis_r23_2026-11-03.json and in each package README under input/results'},
    {'id': 32, 'topic': 'augmentation seed policy after the team change of 2026-10-31: LO/registries.py @ df2a867 sets augmentation_policy '
                        'FIXED_SEED_42 ("reuse the seed-42 S2 balanced TRAIN artifact across model master seeds 42, 43 and 44; model seeds measure '
                        'training variability") and rewrites closed decision 9; this registry, decision 9 [DEC §1], check 13, M-12 of the 02/11 '
                        'request list and the runner default all say MATCH_MASTER_SEED (one S2 artifact per master seed, 216 S2 runs); under the '
                        'team text the S2 runs for seeds 43/44 (144 runs) are not made and the seed dimension of the meta-dataset measures '
                        'training noise only, not sampling noise',
     'status': 'OPEN 2026-11-03', 'author_question': 'Q-16',
     'blocks': ['S2 seeds 43/44 (T1-S2-02..04, CP4)', 'every F1/F2 cell of seeds 43/44 (M-12)', 'the seed statement of the Method section and the '
                'variance decomposition of H1-H8', 'the metamodel seed-level rows (n_rows_seed_level)'],
     'options': ['(a) keep MATCH_MASTER_SEED as locked: the team reverts the registry text and the test, materialises S2 for seeds 43 and 44 '
                 '(2 tasks x 3 windows x 12 balanced pipelines x 2 seeds = 144 runs; the seed-42 S2 of CQ took 36 runs of the Modal volume) and '
                 'the paper reports seed variability that includes sampling variability',
                 '(b) accept FIXED_SEED_42: decision 9 is reopened and re-closed by the author, README / launcher default / runner check are '
                 'changed to the fixed policy, the Method section states that seeds 43/44 vary model initialisation and data order only, the '
                 'meta-dataset documents augmentation_seed = 42 for every balanced cell, and the sampling-variability claim is dropped',
                 '(c) (a) for F1 (recurrent families, cheap cells) and (b) for F2 PatchTST only, with the two policies named per tier'],
     'recommendation': '(a): the design was pre-registered and signed [DEC §1], the cost is 144 S2 runs (CPU-side sampling, no GPU), and a '
                       'reused fixed-seed artifact would make the three "seeds" share identical synthetic rows, which understates the '
                       'variance of every balanced pipeline exactly where the paper claims robustness; (c) only if the F2 budget forces it, '
                       'and then named in the Method section; whichever option, the team registry must follow the decision, not precede it',
     'cost_basis': 'S2 seed-42 facts: 36 runs per task, ledgers 25-43 MB each (ledger_inventory.json); no GPU; the F1 cells of seeds 43/44 '
                   '(408) are unchanged by the option',
     'status_2026-11-04': 'RATIFIED (a) by the author on 2026-11-04 (Q-16): MATCH_MASTER_SEED stays the registered augmentation seed policy; '
                          'the team restores LO/registries.py and the tests; S2 for seeds 43/44 are 144 runs without GPU; no seed-43/44 cell '
                          'before the four places of check 35 agree; seeds 43/44 belong to phase 2 under decision 36 '
                          '[Ra_soat_tien_do_2026-11-04 §1]',
     'status_2026-11-09': 'CLOSED on the code side: cfcfd40 restores MATCH_MASTER_SEED in LO/registries.py and decision 9, the launcher default, the '
                          'runner check and modal_jobs/README.md agree, model_app/model_preflight_app default to the run seed, '
                          'test_registry_release_alignment asserts it (check 35 PASS); the team asked for the "four places" list of check 35 and it is '
                          'answered in Ra_soat_tien_do_2026-11-09 §4; S2 seeds 43/44 (144 runs) not yet started'},
    {'id': 33, 'topic': 'Radius-SMOTE nearest-neighbour fallback (audit cq_radius_fallback_modal_20261103, hash-verified): with the registered '
                        'radius 0.092 in scaled space the fallback rate exceeds 0.50 in all 24 (window x class x imputer parent) rows of CQ seed '
                        '42: class average 0.561-0.607 (W1 0.585-0.589, W2 0.561-0.562, W3 0.607), class good 0.799-0.896 (W1 0.799-0.807, W2 '
                        '0.887-0.892, W3 0.895-0.896); the four Radius pipelines V4/V8/V12/V16 are therefore radius sampling for a minority of '
                        'the synthetic rows and nearest-neighbour interpolation for the rest; check 5 registered the > 0.50 warning on 2026-10-05 '
                        'and the S2 summary flags the 24 rows RADIUS_FALLBACK_GT_0_50; LO not yet audited (M-06 LO)',
     'status': 'OPEN 2026-11-03', 'author_question': 'Q-17',
     'blocks': ['Method §4.2 description of V4/V8/V12/V16', 'every Radius row of the F1 and F2 tables', 'the pipeline registry label of the four '
                'Radius pipelines', 'F2 V8/V12/V16 (not yet run) if option (b) is chosen'],
     'options': ['(a) keep the artefacts and document: the Method section describes the mechanism as "Radius-SMOTE with nearest-neighbour '
                 'fallback" and prints the fallback rates per window x class; the four pipelines keep the sensitivity label of decision 11; '
                 'the pipeline registry gains a balancer_note; no rerun',
                 '(b) recalibrate the radius per (window, class) to a target fallback rate (for example <= 0.10), rerun the 12 Radius S2 '
                 'artefacts per task and every model cell that consumed them (CQ F1 4 families x 12 cells = 48, LO F1 48, F2 V4 3 cells '
                 'already run plus V8/V12/V16), and register the new radii before the rerun',
                 '(c) drop the four Radius pipelines from the paper grid (13 pipelines), keeping them as a labelled appendix sensitivity'],
     'recommendation': '(a) now for seed 42 and the paper text, with the rates printed next to every Radius result and the LO audit added '
                       '(M-06 LO) before any LO Radius number; (b) only if the author wants the Radius mechanism itself to be a claim of the '
                       'paper (it is not a contribution C1-C5); (c) is unnecessary because decision 11 already labels Radius as sensitivity',
     'facts_source': 'radius_fallback_class_seed42.csv (24 rows; columns generated_rows, fallback_nearest_neighbour_rows, rate) and '
                     's2_sampling_summary_cq_seed42.csv (108 rows; fallback_class_status VERIFIED_POSTHOC_RADIUS_AUDIT) in input/results',
     'status_2026-11-04': 'RATIFIED (a) by the author on 2026-11-04 (Q-17): the artefacts are kept; the method is named "Radius-SMOTE with '
                          'nearest-neighbour fallback"; the fallback rate is printed per window x class in the paper; the sensitivity label of '
                          'decision 11 (D-11) stays; no rerun [Ra_soat_tien_do_2026-11-04 §1; Method v0.4 §4.1.2]',
     'status_2026-11-09': 'team M-06 package (LO/L2_facts/s2/s2_sampling_kappa_seed42_20261107, per the 08/11 reconciliation report): 108 S2 rows and 24 '
                          'Radius fallback rows per task, kappa_reached defined in METRIC_DEF_kappa_reached.json, radius_parent_identity_check.csv 24/24 '
                          '(manifest/path linkage, not byte-level); not yet fetched or hash-verified by the writing side; the paper wording of (a) stands'},
    {'id': 34, 'topic': 'CQ W1 TEST class good support concentrated in one offering (class_offering_support.csv, hash-verified): n = 11,307 '
                        'samples from 9 offering units, top_offering_share 0.9885; the registered cluster-bootstrap rule (METRIC_DEF v1.2: '
                        'n_offerings_with_class <= 2) does not fire (9 > 2) although the W1 TEST c2 recall of every pipeline and family is '
                        'effectively one course\'s outcome (PatchTST V0-V6 W1 TEST c2 recall 0.42-0.48 at P1 rising to 0.92-0.93 at P4 with '
                        'i.i.d. bootstrap CIs of +-0.009); other concentrated cells: W3 TEST good 0.672 (122 units), W2 VALIDATION good 0.385, '
                        'W3 TEST average 0.374, W1 TEST average 0.306; the LO counterpart (W1 TEST class E, one offering) is decision 17',
     'status': 'OPEN 2026-11-03', 'author_question': 'Q-18',
     'blocks': ['every per-class W1 TEST table (CQ F1 and F2)', 'the W1 phase-trend sentence for class good', 'METRIC_DEF v1.3 wording'],
     'options': ['(a) extend the rule: a (window, split, class) cell is flagged single_offering_dominant when top_offering_share >= 0.5; its '
                 'recall is printed with the flag and with an offering-cluster bootstrap CI (B = 2,000 over offering units) next to the '
                 'i.i.d. CI; the paper presents the W1 TEST good recall as the outcome of one large offering, as decision 17 does for LO',
                 '(b) exclude class good of W1 TEST from the per-class tables (macro-F1 and balanced accuracy keep it) and say why',
                 '(c) report as now (not acceptable: the CI would claim a precision the design does not have)'],
     'recommendation': '(a): the team already computes the support table and the cell flags (M-05) and the cluster bootstrap is in METRIC_DEF; '
                       'the threshold 0.5 and the flag name go into METRIC_DEF v1.3 and into the facts (cell_flags) before the F2 tables are '
                       'written; the same rule is applied to LO when its class-offering table arrives',
     'facts_source': 'class_offering_support.csv (27 rows) and cell_flags.csv (1,632 rows, Drive id 1RvIMJv4IBEWz7oME17bOsL3SEkIp4N3D, not yet '
                     'synced) of cq_class_offering_support_20261103; blocks.csv of cq_split_evidence_partial_20261103 gives 379 offering units '
                     'in block C',
     'status_2026-11-04': 'RATIFIED (a) by the author on 2026-11-04 (Q-18): the flag single_offering_dominant (top_offering_share >= 0.5) is '
                          'added to cell_flags for CQ and LO; clustered (offering-unit) bootstrap CIs are produced for the flagged cells; flagged '
                          'cells are presented as findings, as decision 17 (D-17) does for LO W1 class E [Ra_soat_tien_do_2026-11-04 §1]',
     'status_2026-11-09': 'team M-05 delivered per the 08/11 report: CQ cq_offering_bootstrap_phase1_20261108 (600 flagged TEST cells, 1,800 class rows, B = 2,000, '
                          'join/support PASS) and LO lo_offering_support_bootstrap_20261107 (1,632 cells, 4,896 class rows, 544 NOT_ESTIMABLE_SINGLE_OFFERING); '
                          'not yet fetched or hash-verified by the writing side; acceptance = check 31 on these two packages'},
    {'id': 35, 'topic': 'energy label of the LO static-v2 grid (2026-11-04): GRID_POLICY execution_status_2026-11-03 and the drafts of '
                        '00_contributions C3 / 02_baselines said "LO energy NOT_MEASURED" (the label of the archived historical LO grid, decision '
                        '24), while lo_resource_per_run.csv of the M-01 export (lo_static_v2_grid_seed42_20261102) carries '
                        'NVML_POWER_SAMPLING_ESTIMATE for 204/204 runs (0.4967 kWh); decision 15 makes TIME the primary cost basis and ENERGY a '
                        'flagged sensitivity because the NVML numbers are estimates, not counters',
     'status': 'CLOSED 2026-11-04', 'author_question': 'Q-19',
     'blocks': ['the energy column of the LO cost tables (C3)', 'the sentence "LO NOT_MEASURED" in 00_contributions C3 and 02_baselines',
                'the labelled ENERGY sensitivity for LO'],
     'options': ['(a) D-15 unchanged (TIME primary for both tasks); the LO static-v2 NVML estimates (204/204 runs, 0.4967 kWh) enter the labelled '
                 'ENERGY sensitivity for LO exactly as the CQ F1 estimates do for CQ; the "LO NOT_MEASURED" sentences in 00_contributions C3 and '
                 '02_baselines are corrected',
                 '(b) status quo before 04/11: keep "LO NOT_MEASURED", report LO on TIME alone and restrict the ENERGY sensitivity to CQ'],
     'recommendation': '(a): the LO static-v2 grid of decision 24 (b) has the same measurement type as the CQ F1 grid (NVML power-sampling '
                       'estimate on every run), so one ENERGY label serves both tasks; NOT_MEASURED stays the label of the archived historical LO '
                       'grid only',
     'facts_source': 'lo_resource_per_run.csv of the M-01 export lo_static_v2_grid_seed42_20261102 (204 runs, NVML_POWER_SAMPLING_ESTIMATE, '
                     '0.4967 kWh); AUTHOR_RATIFICATIONS_2026_10_24 decision 15',
     'resolution': 'RATIFIED (a) by the author on 2026-11-04 (Q-19): D-15 unchanged (TIME is the primary cost basis for both tasks); the LO '
                   'static-v2 grid carries NVML_POWER_SAMPLING_ESTIMATE for 204/204 runs (lo_resource_per_run.csv, 0.4967 kWh), so ENERGY may be '
                   'used as a labelled sensitivity for LO too; the sentence "LO NOT_MEASURED" in 00_contributions C3 and 02_baselines is corrected '
                   '[Ra_soat_tien_do_2026-11-04 §1; 00_contributions v0.8; 02_baselines v0.8]'},
    {'id': 36, 'status_2026-11-20': 'base tier complete on the three registered seeds (1,836 runs, checks 43 and 44); M-15 delivered on three seeds on 20/11, six days after the 14/11 gate: the gate itself was met by the phase-1 run of 13/11 (seed 42); the fallback branch of this decision (paper on C1, C4, C5 with C2/C3 as secondary results) is now the subject of decision 48 (Q-37)', 'status_2026-11-16': 'seed 43 base tier complete (612 cells, six packages verified by check 43); the phase-1 scope (seed 42) is unchanged; how seed 43 (and 44) enter the submission is decision 46 (Q-35)', 'status_2026-11-13': 'M-15 delivered on 2026-11-13, inside the 14/11 gate: the lateness fallback (C1, C4, C5) is not triggered; the primary configuration supports no hypothesis at seed 42 -> decision 44', 'topic': 'phase-1 scope of the TOIS submission (2026-11-04, deadline 2026-11-20): D-N3 (A) of 2026-10-24 asked for 2 tasks x 3 '
                        'master seeds x (F1 + F2); the primary seed-42 facts on 04/11 are CQ F1 R4 (1,632 cells), LO F1 static-v2 (1,632 cells) '
                        'and F2 PatchTST CQ V0-V6 (168 cells); seeds 43/44 need the 144 S2 runs of decision 32 and their F1/F2 cells, V7-V16 and '
                        'LO F2 are not run, and the meta layer (assemble + MM0-MM6; M-13, M-14, M-15 of the request list) is still to be run',
     'status': 'CLOSED 2026-11-04', 'author_question': 'phase-1 scope (04/11 session)',
     'blocks': ['the scope and seed statements of Method v0.4 and of the Experiments section', 'the meta-layer run of the team (M-13 / M-14 / '
                'M-15) and its planned_seeds', 'the hypothesis tests of phase 1 (cluster bootstrap, no across-seed variance decomposition)',
                'the fallback content of the paper (C1, C4, C5 only) if M-15 is later than 2026-11-14'],
     'options': ['(a) D-N3 (A) unchanged (AUTHOR_RATIFICATIONS_2026_10_24): 2 tasks x 3 master seeds x (F1 + F2) before submission',
                 '(b) the reduced three-seed scope of decision 23 options_2026-10-25 (c): full F2 grid on seed 42, seeds 43/44 on V0 and the four '
                 'imputation-only pipelines, LO F2 at the same reduced scope',
                 '(c) seed 42 only: F1 of both tasks (CQ R4 1,632 cells; LO static-v2 1,632 cells) and F2 PatchTST CQ V0-V6 (168 cells); the '
                 'meta layer is run on these facts with planned_seeds = [42]; seeds 43/44, V7-V16 and LO F2 move to the full release (phase 2)'],
     'recommendation': '(c): the D-N3 (A) remainder (S2 seeds 43/44 = 144 runs, the F1 cells of seeds 43/44, V7-V16, LO F2 and F2 on seeds 43/44) '
                       'does not fit before 2026-11-20; phase 1 reports one seed with cluster bootstrap over cells / offering units, states in '
                       'Method and in the threats section that no across-seed variance is estimated, and the full release (phase 2) adds the '
                       'seeds',
     'facts_source': 'GRID_POLICY execution_status_2026-11-03 (429 primary seed-42 runs: CQ F1 204 + LO F1 v2 204 + PatchTST V0-V6 21); R4 '
                     'export (1,632 CQ cells); M-01 export lo_static_v2_grid_seed42_20261102 (1,632 LO cells); facts package '
                     'cq_patchtst_v0_v6_full_facts_20261103 (168 sanity cells); milestones in Yeu_cau_tang_meta_doi_code_2026-11-04.docx',
     'resolution': 'RATIFIED (scope (c) of 04/11, amends D-N3 (A)) by the author on 2026-11-04: the phase-1 submission (TOIS, deadline 2026-11-20) '
                   'uses seed 42 only, F1 of both tasks (CQ R4 1632 cells; LO static-v2 1632 cells) and F2 PatchTST CQ V0-V6 (168 cells); the meta '
                   'layer (assemble + MM0-MM6) is run by the team on these facts with planned_seeds = [42] (M-13 F0 CQ / S0 profile / Z_M by '
                   '2026-11-09 together with M-14 assemble; M-15 run by 2026-11-12); if M-15 is later than 2026-11-14 the paper falls back to '
                   'reporting C1, C4, C5 only; seeds 43/44, V7-V16 and LO F2 move to the full release (phase 2); every hypothesis test in phase 1 '
                   'uses cluster bootstrap over cells/offering units and no across-seed variance decomposition [Ra_soat_tien_do_2026-11-04 §1; '
                   'Method v0.4; Yeu_cau_tang_meta_doi_code_2026-11-04.docx]',
     'status_2026-11-09': 'milestone 2026-11-09 missed for M-14: M-13 was delivered on 08/11 (cross_task_meta/work_in_progress/m13_inputs_phase1_20261108: '
                          'S0 profile 48 rows, Z_M 5 rows, F0 CQ_PARTIAL_TRIAD 24 rows; check 40) but the team reports that it never received the metamodel '
                          'package (v0.2.0/0.2.1) and the registry revision of 04/11, so M-14 (assemble) and M-15 (MM0-MM6) have not started; the hand-off '
                          'bundle of 09/11 is prepared for the author to upload (decision 40); meanwhile every seed-42 F2 cell of both tasks exists (decision 41)'},
    {'id': 37, 'topic': 'F3 backbone (2026-11-06): the code team reports after its tests that MOMENT_SMALL / MOMENT_BASE do not fit the F3 grid '
                        'and run too long, and proposes MantisV2 (paris-noah/MantisV2) instead; F3 is EXPLORATORY (D-11) and outside the '
                        'phase-1 release (decision 36); no F3 cell was run into L2 or read (the family_smoke / family_screen runs of 548d4d4 '
                        'never entered L2), so the change is made before any F3 outcome exists',
     'status': 'CLOSED 2026-11-06', 'author_question': 'author instruction of 2026-11-06 (check MantisV2 against the F3 conditions, update the '
                                                       'resources if it passes, code and guide for the team)',
     'blocks': ['MODEL_REGISTRY F3 row and Z_M of F3', 'check 37', 'Method section 4.8 (F3 sentence) and Figure 1', 'Meta-Dataset-Report '
                'Table 8 and section 2.4', '02_baselines section B', 'checklist S3 (T1-F3-01 .. T1-F3-05)'],
     'options': ['(a) keep MOMENT_SMALL (exploratory) and add the frozen-embedding cache that check 11 already requires',
                 '(b) replace MOMENT_SMALL and MOMENT_BASE by MANTIS_V2 as the single F3 member (exploratory): frozen encoder, linear probe, '
                 'registered channel adapter, cache',
                 '(c) drop F3 and state two architecture tiers in the paper'],
     'suitability_check_2026-11-06': {
         'K1_tier_identity': 'PASS: pretrained time-series classification foundation model (contrastive pre-training), distinct from F1 '
                             '(recurrent) and F2 (supervised channel-independent transformer)',
         'K2_frozen_linear_probe': 'PASS: frozen-encoder feature extraction is the main use of Mantis; logistic regression on standardised '
                                   'features beats random forest (UCR 0.8195 -> 0.836 for MantisV2; arXiv:2602.17868)',
         'K3_open_pinned': 'PASS: weights on Hugging Face at a pinned sha, package on PyPI with wheel hash, Apache-2.0',
         'K4_input_contract': 'PASS WITH ADAPTER: same common tensor (six channels, prefix views); 274 CQ channels need the channel adapter '
                              '(PCA, the authors own recommendation for many channels); static block at the head',
         'K5_prefix_safety': 'PASS: each prefix encoded from its own k steps; k-step and 4-step tensors give bit-identical embeddings '
                             '(f3_mantis tests)',
         'K6_finite_and_constant_channels': 'PASS WITH GUARD: no input mask, hence no masked-patch NaN; the instance normalisation has the '
                                            'float32 problem of MOMENT RevIN for constant series (reproduced) and needs the guard',
         'K7_shared_checkpoint_and_selection': 'PASS: one head for P1..P4, MEAN_PHASE_MACRO_F1 with cross-entropy tie-break, patience 5',
         'K8_determinism': 'PASS on CPU (bit-identical reruns); GPU pilot pending (check 37 (d))',
         'K9_cache': 'PASS: computed once per (window, imputer) plus synthetic rows per (balanced pipeline, seed)',
         'K10_cost': 'CONDITIONAL: per series 160.7 MFLOPs, same order as MOMENT-1-small (phase-as-patch); feasible only with the 8-component '
                     'adapter and the cache; measured on L4 in the pilot (check 37 (c))',
         'K11_scope_and_role': 'PASS: D-11 scope and the EXPLORATORY label unchanged; separate export; held-out tier in E3 only if run',
         'K12_pretraining_leakage': 'PASS: synthetic pre-training data only',
         'K13_Z_M': 'PASS: is_pretrained, pretrained_source, finetune_mode, parameter counts, max_seq_len, patch_len, patch_stride available',
         'K14_validity_domain': 'LIMITATION: Mantis was validated on series of length >= 15 and the ICML 2026 paper reports TabPFN ahead of '
                                'Mantis on UCR series shorter than 144 points; here a prefix has 1-4 steps resized to 512, and at P1 the '
                                'encoder only sees component levels; to be stated in the threats to validity'},
     'recommendation': '(b): MANTIS_V2 meets the F3 conditions as EXPLORATORY under four conditions: the registered channel adapter, the '
                       'constant-series guard, the cache with the cost and determinism pilots of check 37, and the validity-domain limitation '
                       'stated in the paper; the change does not touch phase 1, C1-C5 or any primary table',
     'facts_source': 'Hugging Face API paris-noah/MantisV2 (read 2026-11-06); PyPI mantis-tsfm 1.1.0 (wheel and source read 2026-11-06); '
                     'Feofanov et al. ICML 2026 PMLR 306 (PDF read 2026-11-06); arXiv:2602.17868; registry PENDING_DECISIONS[11] cost note; '
                     'f3_mantis 0.1.0 tests and flop count (2026-11-06)',
     'resolution': 'APPROVED (b) on 2026-11-06 under the author instruction, after the suitability check (K1-K14 above): MANTIS_V2 replaces '
                   'MOMENT_SMALL and MOMENT_BASE as the single F3 member, EXPLORATORY, full release only (decision 36); the adapter defaults '
                   '(8 PCA components on real TRAIN rows, layer index 2, combined token, linear resize to 512, constant-series guard, phase '
                   'one-hot at the head) are registered by the writing side and wait for the author confirmation Q-26; they may change '
                   'before the pilot (recorded here) and never after any F3 VALIDATION or TEST metric has been read',
     'status_2026-11-09': 'the team integrated f3_mantis 0.1.0 byte-identically (6a69b7f) and ran the whole CQ grid (51 cells, EXPLORATORY_CACHE_VALIDATION, '
                          'facts package cq_mantis_v2_v0_v16_full_facts_20261109) before the cost and determinism pilots of check 37 (c)/(d) were documented, '
                          'with its own DedupZstdStore cache (check 37 (h)) and without the package tests (check 37 (i)); the pin of check 37 (a) is satisfied '
                          'in every standardised run manifest; the adapter defaults were used as registered (Q-26 still unanswered, so (g) now binds: no '
                          'design change after the first metric was read on 07/11); Mantis LO V0/V1/V5/V9/V13 training; F3 stays phase 2 and never enters a '
                          'primary table'},
    {'id': 38, 'ratified_2026-11-13': 'RATIFIED (a) by the author on 2026-11-13 (Q-27): the LO PatchTST r2 package (one probe, reference copied) is the citable LO F2 source', 'topic': 'LO PatchTST V0-V16 facts (lo_patchtst_v0_v16_full_facts_20261109) mix three fits of the s_leak probe: pipelines V0-V4, V7, V11, V12 '
                        'come from the re-audit of 09/11 (probe AUC 0.84011 at W1 TEST P4), V5, V6, V8, V9, V10, V13, V15, V16 from the audits stored in '
                        'their bundles (0.83997) and V14 from a third fit equal to the LO F1 static-v2 export (0.84023); probe_fit_rows (7,150,228), n_eval, '
                        'probe_seed 42 and scopes are identical, so the probe is not deterministic across audit runs; |diff| up to 0.0234 at W3 (TEST P1 '
                        '0.0545 vs 0.0779), hence acctempo_m3 moves by up to 0.0139 and acctempo_m4 by up to 0.0163 per cell and the LO M4 order of the '
                        'mid-ranked pipelines changes when one probe is used for all cells (best M4 V7 and best M3 V6 are stable); the CQ exports (R4, '
                        'PatchTST V0-V16, Mantis) share one probe within 1.2e-5 and the LO F1 export is single-valued (phase-1 facts unaffected)',
     'status': 'OPEN 2026-11-09', 'author_question': 'Q-27',
     'blocks': ['every LO F2 S_san+, M3 and M4 comparison across pipelines', 'the LO rows of a phase-2 meta release', 'LO F3 Mantis audits (same audit code)'],
     'options': ['(a) the team recomputes s_leak, S_san+ v1/v2, M3 and M4 for all 51 LO F2 cells from the single LO F1 standard probe table (the s_leak '
                 'rows of GD1_LO_V3_1_clean_r1 / the static-v2 export, which the registered real-row contract defines as a property of (task, window, '
                 'split, phase)), re-exports the package with a note, and makes the probe fit deterministic (fixed solver, single thread, recorded '
                 'library versions) with an audit-time assertion that s_leak equals the registered reference within 1e-9 (check 38)',
                 '(b) the team re-runs the standard audit for all 51 LO F2 cells in one pass on one machine and re-exports',
                 '(c) accept the package as delivered; the writing side harmonises s_leak descriptively (lo_leak_harmonisation.json) and no LO F2 '
                 'S_san+/M3/M4 number is printed'],
     'recommendation': '(a): exact, cheap (no GPU, no re-audit of predictions), consistent with the phase-1 LO facts and with the registered contract; '
                       '(b) only if (a) is refused; under (c) the LO F2 tier cannot be compared on the composite',
     'facts_source': 'lo_patchtst_v0_v16_full_facts_20261109/sanity_components.csv (sha256 174cad03...), LO static-v2 export '
                     'lo_family_pipeline_window_phase_metrics.csv (1,632 rows), analysis_r26_2026-11-09.json (identity_checks, leak_groups, '
                     'lo_s_leak_harmonisation), sleak_cross_tier_check.json',
     'status_2026-11-10': 'option (a) EXECUTED by the team before the author answered (Q-27 still open for ratification): '
                          'lo_patchtst_v0_v16_full_facts_20261109_r2 (tools/recompute_lo_patchtst_sleak_r2_20261109.py, r2 09/11, r2b 10/11 '
                          'with runner commit and source inventory) copies s_leak / s_leak_probe_auc from the canonical LO F1 table and recomputes '
                          'S_san+ v1/v2, M3, M4; the writing side verified on the 10/11 files: identity spread 0.0 in all 24 cells, |diff| vs the '
                          'reference 0.0, formulas reproduced <= 2.7e-15, exactly six columns changed (M3 up to 0.01425, M4 up to 0.01658, as the '
                          'team summary states), 384 cells moved, every other column identical, checkpoint and resource tables unchanged except '
                          'runner_git_commit; r2_changes.csv lists old/new/diff per cell; the 09/11 package carries a SUPERSEDED marker (10/11) and '
                          'stays on the Drive as the provenance of r2_changes.csv (keep it, do not delete); the probe is deterministic from ea19afa '
                          'with the 1e-9 assertion for new audits. The package may be cited once the author ratifies (a); its S_san+/M3/M4 columns '
                          'are no longer MIXED_LEAK_PROBE'},
    {'id': 39, 'ratified_2026-11-13': 'RATIFIED (c) by the author on 2026-11-13 (Q-28): S0 profile v4 without tr_inactive_learner_ratio is the registered state profile', 'topic': 'M-13a S0 profile conventions (m13_inputs_phase1_20261108/s0_profile, 48 rows x 115 columns, minimum set complete, no unexpected '
                        'NULL, P4 parity PASS per the team): five conventions were chosen by the team and need the writing side: (1) '
                        'tr_inactive_learner_ratio = share of TRAIN enrollments whose cumulative event count did not increase in the last phase interval '
                        '(values 0.978-0.997 in all 48 rows, i.e. almost every learner counts as inactive, so the column carries no information); (2) '
                        'ev_mean_observed_length in whole days to the phase cutoff; (3) ev_mean_observed_fraction = floor(days to cutoff) / floor(days '
                        'enrollment to window end), cutoffs at q = 0.25/0.5/0.75/0.9; (4) drift_*_psi_mean over raw phase-matched features with decile '
                        'bins from the reference plus a missing bucket, eps 1e-6; (5) tr_mean_events_per_enrollment = cumulative segments + problems + '
                        'comments, NaN as 0',
     'status': 'OPEN 2026-11-09', 'author_question': 'Q-28',
     'blocks': ['M-14 assemble (the S0 profile is an input)', 'Meta-Dataset-Report Table E3 wording', 'meta-model features of E1-E3'],
     'options': ['(a) accept conventions (2)-(5) as delivered and replace (1) by a definition with spread: share of TRAIN enrollments with no event at '
                 'all before the phase cutoff (then tr_inactive_learner_ratio differs from tr_zero_activity_ratio only by the event types counted) or '
                 'with no event in the last quarter of the elapsed prefix; the team recomputes the column (no GPU)',
                 '(b) accept all five as delivered and document (1) as near-constant',
                 '(c) drop (1) from the minimum set'],
     'recommendation': '(a): the other 31 required columns pass; (1) as defined is degenerate and would enter the meta-model as a constant',
     'facts_source': 'm13_inputs_phase1_20261108/s0_profile/{s0_profile.parquet (sha256 afeee49c...), summary.json, s0_profile_README.md}; '
                     'analysis in Ra_soat_tien_do_2026-11-09 §3',
     'status_2026-11-10': 'option (c) EXECUTED by the team before the author answered (Q-28 open): m13a_s0_profile_20261109_v4 (48 rows x 113 '
                          'columns) drops tr_inactive_learner_ratio and its reason column with the argument that the recommended definition "no '
                          'event at all before the phase cutoff" equals tr_zero_activity_ratio (already in the profile; the builder asserts '
                          'tr_zero_activity_ratio <= tr_inactive_learner_ratio and reports the P1 identity) and that every inactivity share is '
                          '0.96-0.99; the writing side verified: exactly the two columns removed, every other value identical to v3 (reason columns '
                          'differ only in the NULL representation), the 31 required columns have 0 NULL, conventions (2)-(5) unchanged, cohort '
                          'written as ALL (the team used a FIXED copy for assemble; metamodel 0.2.2 normalises ALL -> FIXED). The writing side '
                          'changes its recommendation to (c) as executed: the alternative "no event in the last quarter of the prefix" would be '
                          'a new quantity, not a fix of (1), and can be added in phase 2 if the meta-model needs it; the builder and summary '
                          'label the change "Q-28 (author, 2026-11-09)", which must read "writing-side recommendation, ratified by the author on <date>"'},
    {'id': 40, 'topic': 'meta-tier hand-off and the 14/11 gate of decision 36: the team states (08/11 report, M-14 row) that it does not have the '
                        'metamodel package (v0.2.0, 21 tests; now 0.2.1 on the writing side) nor the registry revision of 04/11, and will not run an '
                        'assembler of its own; the milestones M-13 + M-14 by 09/11 and M-15 by 12/11 cannot be met without the package; the writing '
                        'side has prepared metamodel_handoff_2026-11-09.zip (metamodel 0.2.1, tempo_fix rev 2026-11-09 with its exports, f3_mantis '
                        'tests, README) in Progress/Ver 3/2026-11-09_Full_grid_Mantis_M13 for the author to upload to the Drive (the writing side '
                        'never writes to the Drive, decision 28)',
     'status': 'OPEN 2026-11-09', 'author_question': 'Q-29',
     'blocks': ['M-14 (assemble), M-15 (MM0-MM6), check 36', 'Experiments §5.3/§5.4 and H6-H8 of the phase-1 paper', 'the fallback clause of decision 36'],
     'options': ['(a) the author uploads the hand-off bundle to Results/cross_task_meta/work_in_progress/ today and the team runs M-14 by 11/11 and M-15 by '
                 '13/11; the 14/11 gate of decision 36 stays',
                 '(b) as (a) with the gate moved to 16/11 (two days of reserve for the writing of §5.3/§5.4 before 20/11)',
                 '(c) trigger the fallback of decision 36 now: the paper reports C1, C4, C5; C2/C3 move to phase 2'],
     'recommendation': '(a); if M-14 is not on the Drive by the evening of 12/11, switch to (c) without further delay so that §5.3/§5.4 can be rewritten',
     'facts_source': 'BAO_CAO_DOI_CHIEU_M01_M18_2026-11-08.docx (M-14 row and the 04/11 response table); Yeu_cau_tang_meta_doi_code_2026-11-04.md; '
                     'decision 36 resolution',
     'status_2026-11-10': 'option (a) EXECUTED: the team received metamodel_handoff_2026-11-09.zip (sha256 0b680fe8... equal to the writing-side zip), '
                          'ran metamodel/tests (21 passed) and tempo_fix/tests (29 passed) and assembled M-14 on 09/11 (meta_release_CQ_LO_p1_F2V0V16_20261109, '
                          'RUN_LOG with pip freeze: python 3.14.2, pandas 3.0.0, scikit-learn 1.8.0, scipy 1.17.1, numpy 2.4.2, pyarrow 25.0.1, no '
                          'lightgbm / optuna); the first assembly (meta_release_CQ_LO_p1_20261109, F2 V0-V6, 3,432 rows) had every X_STATE column NULL '
                          'because the S0 profile is written with cohort = ALL while metamodel 0.2.1 joins on cohort = FIXED and the R4 export has no '
                          'feature_regime column (the --key default was not applied to those rows); the team prepared copies (cohort FIXED, '
                          'feature_regime CQ_RAW_EARLY) and re-assembled; metamodel 0.2.2 (writing side, 10/11) normalises the keys, raises on a zero-row '
                          'join and writes join_stats, so no copy is needed. M-15 (mm_runs, MM0-MM6) is not run: lightgbm and optuna are not installed '
                          'on the team side; deadline 13/11; the 14/11 gate stands. Q-29 open for the record of (a)'},
    {'id': 41, 'ratified_2026-11-13': 'RATIFIED (b) by the author on 2026-11-13 (Q-30): F2 of phase 1 = CQ PatchTST V0-V16; the meta release has 3,672 seed-level rows; tables T05/T17/T18/F07 are regenerated from the r2 packages', 'topic': 'use of the complete CQ PatchTST V7-V16 facts in phase 1: decision 36 fixed F2 = CQ V0-V6 (168 cells) because V7-V16 were not run; '
                        'on 09/11 the 30 cells exist with the same runner, layout, protocol, audit depth (B = 2,000), R4 leak probe (1.2e-5) and '
                        'hash-verified facts (cq_patchtst_v7_v16_full_facts_20261109); M-14 has not been assembled yet (decision 40); LO F2 is complete '
                        'but carries decision 38; Mantis is exploratory by construction',
     'status': 'OPEN 2026-11-09', 'author_question': 'Q-30',
     'blocks': ['the F2 scope sentence of Method §4.8 / Experiments §5.1', 'tables T05, T17, T18 and Figure F07 (scripted)', 'the CQ part of the '
                'meta release (R4 union PatchTST)', 'check 36 row counts'],
     'options': ['(a) keep decision 36: F2 = V0-V6 in the primary tables and in the meta release; V7-V16 appear as one labelled supplementary table '
                 '(appendix) and are not pooled into any hypothesis test',
                 '(b) extend phase-1 F2 to CQ V0-V16 (51 cells) for the paper tables and for M-14 (assemble R4 union PatchTST V0-V16; planned_seeds '
                 '[42] unchanged); LO F2 stays phase 2 until decision 38 is executed',
                 '(c) (b) plus LO F2 once the team delivers the re-export of decision 38 (a) before M-14'],
     'recommendation': '(b): the facts are complete, consistent with R4 and verified; the table scripts regenerate in seconds; the meta release gains 30 '
                       'consistent cells before it is assembled; (c) only if the LO re-export arrives before the bundle is run',
     'facts_source': 'cq_patchtst_v7_v16_full_facts_20261109 (summary.json: 240 sanity cells, 960 cohort rows OK, partition PASS); analysis_r26_2026-11-09.json '
                     '(headline, report_vs_facts, identity_checks); decision 36 resolution',
     'status_2026-11-10': 'option (b) EXECUTED by the team in M-14 before the author answered (Q-30 open): meta_release_CQ_LO_p1_F2V0V16_20261109 assembles '
                          'CQ R4 + PatchTST V0-V6 + V7-V16 (f2_scope "CQ PatchTST V0-V16 (Q-30 (b), author decision 2026-11-09)" - to be reworded: '
                          'recommendation applied, ratification pending). Row arithmetic corrected: the 09/11 request wrote "+360" for option (b); the '
                          'facts give +240 (10 pipelines x 24 cells), so seed_level = 1,632 + 1,632 + 408 = 3,672 (verified from the parquet: CQ '
                          'F1_RECURRENT 1,632, CQ F2_TS_TRANSFORMER 408 over 17 pipelines, LO F1_RECURRENT 1,632). If the author chooses (a) instead, '
                          'the release is re-assembled without V7-V16 (no GPU, minutes) and the paper tables keep V0-V6'},
    {'id': 42, 'status_2026-11-20': 'contract applied to the six seed-44 packages: |s_leak - reference| = 0.0 on 4,896 rows, probe_seed = 42 (seed of the reference fit), s_leak_source = REFERENCE_TABLE_COPY_NO_REFIT; over the three seeds (14,688 rows) max |diff| 1.1e-16', 'status_2026-11-16': 'contract applied to the six seed-43 packages: |s_leak - reference| <= 1.1e-16 on 4,896 rows (writing-side check 43), probe not refit (s_leak_source = REFERENCE_TABLE_COPY_NO_REFIT, probe_fit_rows_source = REFERENCE_PROBE_FIT_SEED42_SAME_REAL_DATA); team probe re-check of 15/11 on the standard machine (default multi-thread mode, LO seeds 42-44, five parents, three windows): 0.0 between parents and seeds, <= 5.6e-17 to the reference; CQ not re-done', 'ratified_2026-11-13': 'RATIFIED (a) by the author on 2026-11-13 (Q-31): reference-copy contract: every F2/F3 export carries the registered s_leak; check 38 is an identity <= 1e-9 (metamodel 0.2.4 TOL_LEAK_IDENTITY = 1e-9); probe reproduction is the diagnostic check 41 with tolerance 1e-3 and the thread mode recorded', 'status_2026-11-13': 'option (a) EXECUTED by the team on 2026-11-10 (5ba9829) before the author answered: CQ PatchTST V0-V6 r2, V7-V16 r2, MANTIS_V2 r3 and the LO Mantis package copy the reference; the team L2 receipts report identity <= 1e-9 on five packages; ratification pending. New evidence for check 41: default multi-thread probe reproduces the reference at 0.0, single-thread differs by 2.1e-5 (CQ W1), 1.1e-4, 9.6e-4, 7.2e-6 (LO W1-W3)', 'topic': 'cross-environment reproduction of the s_leak probe and the reference-copy contract (2026-11-10): the deterministic probe of ea19afa '
                        'is bitwise repeatable and thread-independent on the CQ W1/V0 real data (6,437,104 probe rows, 43 iterations, team report) but '
                        'differs from the F1 R4 reference by up to 2.09e-6, above the 1e-9 assertion of check 38 (the F1 fit ran in an unrecorded '
                        'environment); the accepted CQ packages carry their own fits: |s_leak - reference| up to 4.98e-5 for PatchTST V0-V6 (126 of 168 '
                        'rows above 1e-5), 1.24e-5 for PatchTST V7-V16 (30 of 240) and for MANTIS_V2 (51 of 408); the LO r2 package copies the LO '
                        'reference (|diff| 0); inside the meta release s_leak_after therefore differs between the F1 and F2 rows of one situation by up '
                        'to 1.24e-5; the team proposes a 1e-5 tolerance, which would reject the three CQ packages',
     'status': 'OPEN 2026-11-10', 'author_question': 'Q-31',
     'blocks': ['check 38 tolerance for every future audit (seeds 43/44, LO Mantis)', 'metamodel 0.2.2 TOL_LEAK_IDENTITY (shipped at 1e-4)',
                'whether the three CQ F2/F3 packages get an _r2 like LO before the paper tables'],
     'options': ['(a) reference-copy contract: every F2/F3 export copies s_leak and s_leak_probe_auc from the registered reference table of its task '
                 '(s_leak_reference_20261109, as LO r2 does) and recomputes S_san+/M3/M4; check 38 then demands identity <= 1e-9 by construction; the '
                 'probe reproduction becomes a separate per-environment diagnostic (check 41) with tolerance 1e-5 and the environment block recorded; '
                 'the three CQ packages receive an _r2 (no GPU; s_leak changes <= 5e-5, M3/M4 <= about 2e-5) and the meta release is re-assembled '
                 'before the paper tables, not before M-15',
                 '(b) keep per-audit recomputation and set the check-38 tolerance to 1e-4 (covers 4.98e-5) with the environment recorded; no _r2 for CQ',
                 '(c) tolerance 1e-5 as proposed by the team: the three accepted CQ packages fail check 38 and would need an _r2 anyway'],
     'recommendation': '(a): one probe value per (task, window, split, phase) is the registered real-row contract, the copy is exact and free, and the '
                       'paper can state a single probe table per task; M-15 may run on the current release meanwhile (the differences are below the '
                       'rounding of every reported number); metamodel 0.2.2 ships with TOL_LEAK_IDENTITY = 1e-4 until the CQ _r2 packages exist, then '
                       'the constant is tightened to 1e-9',
     'facts_source': 'analysis_r27_2026-11-10.json (tolerance_evidence, cq_patchtst_v0_v6_vs_reference_CQ, cq_patchtst_v7_v16_vs_reference_CQ, '
                     'mantis_r2.s_leak_vs_reference_CQ, meta_release.s_leak_after_identity_across_models); s_leak_reference_20261109/{CQ,LO}.csv '
                     '(sha256 d723adbd..., ad1f424b...); PHAN_HOI_REVIEW_YEU_CAU_09-11_2026-11-10 section C2'},
    {'id': 43, 'status_2026-11-20': 'seed 44: F1 and PatchTST record 5ba9829 at run time (510/510 cells); Mantis CQ and LO carry 6a69b7f mapped retroactively (basis CODE_TAR_FILE_BLOB_MATCH_RETROACTIVE, label), the team asks the reviewer to accept seed 44 under the same rule as seed 43: accepted by the writing side under the ratified option (a), no new decision needed', 'status_2026-11-16': 'seed 43: F1 and PatchTST record 5ba9829 at run time (510/510 cells, RUN_MANIFEST_WRITTEN_AT_RUN_TIME); Mantis CQ and LO carry 6a69b7f mapped retroactively by code-tar blob match (mantis_lo_code_20261109.tar, 8 and 11 hosts, basis CODE_TAR_FILE_BLOB_MATCH_RETROACTIVE on all 51 cells) under the (a) label; the three NULL V0 cells of seed 42 are unchanged', 'ratified_2026-11-13': 'RATIFIED (a) by the author on 2026-11-13 (Q-32): the retroactive runner-commit basis (*_RETROACTIVE) is accepted with its label for CQ MANTIS_V2 r3, LO MANTIS_V2 and LO PatchTST r2, and the three NULL Mantis V0 cells stay NULL with their reason; new F1/F2 runs record the commit at run time', 'status_2026-11-13': 'the team asks the author to accept runner_git_commit_basis = *_RETROACTIVE as the ingest basis of three packages (CQ MANTIS_V2 r3, LO MANTIS_V2: runner_sha256 and code_tar_sha256 written at run time; LO PatchTST r2: tree match on 12 hosts only), otherwise the seed-42 grids must be re-run; Mantis CQ seed-43 cells also lack a run-time commit; open', 'topic': 'retroactive runner-commit mapping and the three NULL Mantis V0 cells (2026-11-10): the team filled runner_git_commit after the '
                        'runs: LO PatchTST 51/51 = df2a867 (the host code directory lo_patchtst_seed42_code, 38 files, identical 37-file set on 12 '
                        'hosts after line-ending normalisation, equals the repository tree at df2a867 (31/10), 834ad30 and 5872cac (03/11); the '
                        'earliest is recorded; check_gpu.py exists on one host and not in the repository; basis '
                        'CODE_DIR_TREE_MATCH_RETROACTIVE), CQ MANTIS_V2 48/51 = 6a69b7f (runner blob sha256 2cc8e3f8... found in the history; code tar '
                        'a8a9a10f... checked by the launch scripts; basis RUNNER_BLOB_SHA256_MATCH_RETROACTIVE); the three V0 cells stay NULL (basis '
                        'NOT_RECORDED_V0_EARLIER_SCRIPT) with indirect evidence only (one git version of the earlier runner, file last modified '
                        '2026-11-07 09:18 UTC+7 before the first V0 cell finished on 08/11 02:44; the code tar of the V0 runs does not contain the '
                        'runner); the evidence file labels this "author decision 2026-11-10" although the author has not decided',
     'status': 'OPEN 2026-11-10', 'author_question': 'Q-32',
     'blocks': ['check 39 item 1 for the LO PatchTST and Mantis packages', 'the provenance sentence of Experiments §5.1 / the reproducibility appendix',
                'whether the Mantis V0 cells appear in any exploratory table'],
     'options': ['(a) accept the retroactive mapping with its basis column and the three NULL V0 cells with NOT_RECORDED_V0_EARLIER_SCRIPT, and state in '
                 'the paper that the runner commit of phase-1 F2/F3 runs was established after the fact from byte identity; from now on every run '
                 'manifest records the commit at run time (check 39 item 1 becomes a hard gate for phase 2)',
                 '(b) re-run the three Mantis V0 cells with the grid runner (about 1.3 L4-hours train each, exploratory tier) so that all 51 cells '
                 'carry a recorded commit',
                 '(c) exclude the three V0 cells from every Mantis table (then the exploratory tier has no no-intervention reference)'],
     'recommendation': '(a): the tier is exploratory and never pooled with F1/F2; V0 is the reference the other 48 cells are compared with; the evidence '
                       'is documented and hash-anchored; (b) only if the author wants the exploratory table free of NULL provenance',
     'facts_source': 'lo_patchtst_v0_v16_full_facts_20261109_r2/runner_commit_evidence.json (sha256 b36b6dcb...), cq_mantis_v2_v0_v16_full_facts_20261109_r2/'
                     'runner_commit_evidence.json (1286fb2f...), resource_per_run.csv of both packages (runner_git_commit_basis), source_inventory.json '
                     '(18 LO archives, V0 being a run tree; 38 Mantis archives; bytes, sha256, Drive MD5 per archive); tools/build_c3_runner_commit_inventory_20261109.py @ 193b584'},
    {'id': 44, 'status_2026-11-20': "three-seed M-15 delivered (20/11). With the primary objective unchanged, H1 is not supported (the registered learner L3-FS3 has a higher regret than B3 on the registered fold, CI excludes 0), H6 is supported in all six configurations; the condition written on 13/11 ('if the primary objective still fails on three seeds, C2-C3 become secondary results') is met for C2 and not for C3 -> decision 48 (Q-37); the executed analysis is a reduced form of the registered design (subgroups, task-pooled folds) -> decision 51 (Q-40)", 'status_2026-11-16': 'seed 43 delivered; the three-seed M-15 waits for seed 44 (F1 trained, PatchTST CQ ~38/51, LO F2/F3 not started on 16/11); the 0.2.4 acceptance shows that release 20261112 lacked six alias metric columns on the CQ F1 rows, so the three-seed assembly must use 0.2.4 (as decided)', 'ratified_2026-11-13': 'RATIFIED (a) by the author on 2026-11-13 (Q-33): the primary objective stays PAPER_COMPOSITE_CAL (D-18); phase-1 results are reported as measured (full H1-H8 table of the six configurations, single-seed limitation stated); M-15 is re-run on the three-seed seed_agg before the conclusions of 5.3/5.4', 'topic': 'outcome of M-15 phase 1 and the presentation of C2-C3 (2026-11-13): under the registered primary objective (PAPER_COMPOSITE_CAL, E1-B, 36 clusters, seed 42) no hypothesis meets its criterion: H1 L3-FS3 - B3 mean regret -0.0014 [-0.0045, 0.0018]; H6 log2 cost ratio -0.796 [-0.940, -0.654] with objective difference +0.0057 whose lower bound -0.0080 is below -eps; with META_PRIMARY_M3_V1 H1, H3, H7 are supported, with SECONDARY_MACRO_F1 H1 (p_holm 0.077), H6, H7; the base-tier headroom oracle - V0 is small (0.0086 CQ, 0.0332 LO)',
     'options': ['(a) keep the primary objective and report as measured: full H1-H8 table for the six configurations, C2-C3 worded as not yet supported at seed 42, M-15 re-run on the three-seed seed_agg before the conclusions of 5.3/5.4',
                 '(b) move C2-C3 to secondary results and centre the paper on C1, C4, C5 (the fallback branch of decision 36)',
                 '(c) make META_PRIMARY_M3_V1 the primary objective'],
     'recommendation': '(a); (c) is not recommended: changing the primary objective after seeing the results contradicts the ratified D-18 and voids the test; if the primary configuration still supports nothing with three seeds, move to (b)',
     'blocks': ['sections 5.3 and 5.4, Introduction, Abstract', 'schedule of seeds 43/44 and of the second M-15'], 'author_question': 'Q-33', 'status': 'OPEN 2026-11-13'},
    {'id': 45, 'status_2026-11-20': 'H8 as restated: not supported on three seeds (primary: rho = -0.286 [-0.670, 0.132], 25 clusters >= 10, verdict allowed); the descriptive missing-rate row is reported outside the Holm family as decided', 'status_2026-11-16': 'no change; metamodel 0.2.4 (H8 restated) is the accepted version for the three-seed run', 'ratified_2026-11-13': 'RATIFIED (a) by the author on 2026-11-13 (Q-34): H8: the phase part is the test, the tr_missing_rate part is descriptive, a verdict needs at least 10 clusters; implemented in metamodel 0.2.4 before any three-seed run; the phase-1 run of 13/11 keeps its tables under the earlier definition', 'topic': 'restatement of H8 and a minimum number of clusters (2026-11-13): H8 requires Spearman(imp_share, phase_index) < 0 and Spearman(imp_share, tr_missing_rate) > 0, but in the S0 profile v4 tr_missing_rate rises monotonically with the phase in every task x window (CQ W3 0.696, 0.813, 0.859, 0.885; LO W3 0.657, 0.785, 0.838, 0.867), so the two parts exclude each other; the two H8 rows coincide to 16 digits in three configurations; the only supported H8 (sens_conservative) rests on 4 clusters',
     'options': ['(a) keep one part as the test (phase), report the other descriptively, and require at least 10 clusters for a verdict',
                 '(b) replace tr_missing_rate by a quantity that is not monotone in the phase (for example the within-phase deviation from the phase mean)',
                 '(c) keep H8 as registered and state that it cannot be tested on this data'],
     'recommendation': '(a); the change touches a registered hypothesis, so only the author decides, and the date must precede the three-seed run',
     'blocks': ['T2-MM1-01, T2-MM4-10', 'sections 4.6 and 5.4 (C4)'], 'author_question': 'Q-34', 'status': 'OPEN 2026-11-13'},
    {'id': 46, 'ratified_2026-11-20': 'RATIFIED (b) by the author on 2026-11-20 (Q-35): base-tier tables as three-seed means with the across-seed SD; T05/T17/T18/F07 regenerated; best-pipeline statements worded with the between-seed instability', 'status_2026-11-20': 'the three seeds are complete and the meta tier now runs on the three-seed aggregate, so option (b) (base-tier tables as three-seed means with across-seed SD) has become consistent with the meta-dataset actually analysed; three-seed evidence: cell-level Pearson 0.87-0.998 on M3cal (0.68-0.99 on macro-F1), Spearman of the 17 pipeline means -0.40 to 0.87 (macro-F1: -0.22 to 0.83), same best pipeline in 4 of 36 seed pairs on M3cal; recommendation of the writing side moves from (a) to (b); still OPEN', 'topic': 'use of the seed-43 (and seed-44) base-tier results in the phase-1 submission (2026-11-16): decision 36 fixed phase 1 on seed 42 and decision 44 (a) re-runs M-15 on three seeds; the six seed-43 facts packages are complete and verified (check 43): cell-level values agree with seed 42 (TEST, 51 cells per task x model: Pearson 0.96-0.998 on M4 and 0.82-0.99 on macro-F1, mean |diff| of M4 0.002-0.013) but the ranking of the 17 pipelines by their mean is unstable (Spearman 0.12-0.84 on M4, 0.02-0.82 on macro-F1) and the best pipeline differs between the seeds in every task x model',
     'options': ['(a) the phase-1 tables keep seed 42 as the pre-registered snapshot; a seed-robustness subsection (Experiments) reports the cell-level agreement and the ranking instability from seed 43 (seed 44 added when delivered), cited from the GD2/GD3 _seed43 packages; every single-seed statement about a best pipeline is worded as seed-specific',
                 '(b) the base-tier tables move to multi-seed means with across-seed SD (42+43 now, +44 when delivered): T05/T17/T18/F07 regenerated, Method and Experiments restated, M-15 unchanged (three seeds per decision 44)',
                 '(c) seed 42 only, seed 43 unreported in phase 1 (full release only)'],
     'recommendation': '(a) before 2026-11-20; (b) only in the full release, when seed 44 is complete and the ranking instability can be stated with three seeds; (c) withholds evidence the reviewers will ask for',
     'blocks': ['the seed-robustness paragraph of 5.1/5.2 and the threats section', 'wording of every best-pipeline claim', 'whether T05/T17/T18/F07 are regenerated again'],
     'author_question': 'Q-35', 'status': 'OPEN 2026-11-16'},
    {'id': 47, 'ratified_2026-11-20': 'RATIFIED (a) by the author on 2026-11-20 (Q-36): NULL variant_role accepted on PRIMARY_GRID facts; the role is read from MODEL_REGISTRY; check 39 item 2 as worded in option (a); no re-export', 'status_2026-11-20': "the ten F1/PatchTST directories of seed 44 also carry variant_role NULL (model_tier and run_purpose on every row); the team keeps 'NULL as in the source'; recommendation (a) unchanged; still OPEN", 'topic': 'variant_role NULL in the F1/F2 facts of seed 43 (2026-11-16): the ten PRIMARY_GRID directories (four F1 families and PatchTST, both tasks) carry model_tier and run_purpose on every row but variant_role is NULL (the team keeps the source value: not recorded at train time); the two Mantis packages carry EXPLORATORY; the team overlay seed43_variant_role_registry_overlay.csv maps the role from the registry (RNN, LSTM, PATCHTST = PRIMARY; GRU, BILSTM = ROBUSTNESS), the same as MODEL_REGISTRY here; the p1 release has no variant_role column and the meta-model does not use it',
     'options': ['(a) accept NULL in the facts of PRIMARY_GRID runs: the role is a registered property of the family (MODEL_REGISTRY), check 39 item 2 reads model_tier + run_purpose on every row and variant_role on exploratory packages; the assembler may add variant_role from the registry (no re-export)',
                 '(b) the team re-exports the ten directories with variant_role filled from the registry and a derived label (as the overlay does)',
                 '(c) keep the check 39 wording as is and record the ten directories as WITH_EXCEPTION'],
     'recommendation': '(a): the seed-42 F1 facts (R4, static-v2) carry no variant_role either, so (b) would reopen accepted packages for a label the paper takes from the registry',
     'blocks': ['check 39 wording', 'the L2 ingest status of the ten directories'], 'author_question': 'Q-36', 'status': 'OPEN 2026-11-16'},
    {'id': 48, 'ratified_2026-11-20': 'RATIFIED (a) by the author on 2026-11-20 (Q-37): C1, C3, C4 (descriptive) and C5 are the main contributions; C2 is the registered comparison without a superiority claim; with decision 51 (b) the conclusion on C2 is written on the full-design run (check 47) and no outcome of H1 is stated before it; if that run supports H1 the author revisits this decision', 'topic': 'position of C2, C3 and C4 in the paper after the three-seed M-15 (2026-11-20): on the registered primary analysis (PAPER_COMPOSITE_CAL, E1-B, 48 clusters, seed-aggregated table of seeds 42-44) the learned recommender does not beat the comparator (H1: L3-FS3 - B3 = +0.0029 [0.0006, 0.0057]; H2, H3, H4 not supported; H5 one direction), the cost-aware utility does (H6 in 6/6 configurations: -0.22 to -0.33 log2 cost at no loss beyond eps), H7 holds for three secondary objectives but not for the primary one, H8 is not supported; over the seven folds the fixed global-best pipeline B2 (0.0113) is the best non-oracle strategy and the elastic net L1-FS3 (0.0123) is ahead of the registered LightGBM learner L3-FS3 (0.0146); the negative control fails on the F2 and F3 hold-outs; the base tier explains why: between-pipeline differences are of the size of the seed noise (Spearman of pipeline means between seeds -0.40 to 0.87); the comparison is not stable across folds: on the replication fold E1-A it is -0.0021 [-0.0042, -0.0002] and on the two folds pooled (96 clusters) +0.0004 [-0.0013, 0.0021] (descriptive, computed by the writing side from the recommendation rows); the analysis run so far is a reduced form of the registered design, see decision 51', 'options': ['(a) apply the fallback written into decisions 36 and 44: main contributions C1 (meta-dataset, with the three-seed robustness analysis), C3 (cost-aware recommendation, H6), C4 as a descriptive decomposition and C5; C2 is reported as the registered comparison with a negative primary result (no superiority claim), with the per-fold picture and the comparison to B2/B6 stated as measured; unless decision 51 (b) is taken the text says that the comparison was run on a reduced form of the registered design', '(b) keep C2 as a main contribution by changing the registered analysis (primary learner L1 instead of L3, or the seven-fold mean instead of E1-B): a post hoc change that has to be disclosed as such; the E1-B result of L1-FS3 (0.0070 against B3 0.0104, B2 0.0077) has no registered test', '(c) postpone the submission and enlarge the meta-dataset before testing C2 again (more situations per group: seed-level meta-training, further windows or cohorts), with a new pre-registration'], 'recommendation': '(a), to be confirmed after decision 51 (Q-40): it is the branch agreed on 13/11 and it needs no new experiment; (b) trades the pre-registration for a result on one fold; (c) is the only way to a positive C2 claim but moves the paper by weeks', 'blocks': ['Experiments 5.3-5.4 (meta-tier results)', 'the contribution list of the Introduction and the abstract', 'the comparison table of Related Work (column for C2)', '00_contributions section 3'], 'author_question': 'Q-37', 'status': 'OPEN 2026-11-20'},
    {'id': 49, 'ratified_2026-11-20': 'RATIFIED (a) by the author on 2026-11-20 (Q-38): the 8 cells stay empty; cost follows TIME; energy totals on the measured runs with their count (1,605 of 1,836); no re-run', 'topic': 'GPU energy of the 8 seed-44 CQ cells without a measurement (2026-11-20): the power sampler returned no sample on the hosts of 7 PatchTST cells and 1 Mantis cell; the team proposes median power of the measured cells of the same model x elapsed time (0.39-1.43 kWh per PatchTST cell, 0.12 kWh for the Mantis cell; 4.78 kWh for the seven against 26.49 kWh measured on the other 44) and has not written it into the packages', 'options': ['(a) keep the cells empty: cost follows TIME (D-15), energy totals are reported on the measured runs with their count (1,605 of 1,836), the proposal stays a note', '(b) accept the proposal as a labelled imputation (new measurement type, e.g. IMPUTED_MEDIAN_POWER) used in descriptive energy totals only, never in a cost basis', '(c) re-run the 8 cells with a verified sampler (about 67 GPU hours for the seven PatchTST cells and 3 for the Mantis cell)'], 'recommendation': '(a): the 204 CQ F1 runs of seed 43 have no energy either, so eight imputed cells do not complete any table, and no registered test uses energy under the strict rule', 'blocks': ['the energy column of the resource table in Experiments', 'the cost basis of sens_energy once it is run with metamodel 0.2.5'], 'author_question': 'Q-38', 'status': 'OPEN 2026-11-20'},
    {'id': 50, 'ratified_2026-11-20': 'RATIFIED (a) by the author on 2026-11-20 (Q-39): the pinned Windows PC environment is the environment of record; the Linux host run is the cross-platform replication', 'topic': 'environment of record of the meta-tier runs (2026-11-20): the same six configurations on the same release give bit-identical baselines but different learner rows on a Windows PC (Python 3.12.1, the pinned environment of the 13/11 package) and on a Linux host (Python 3.12.15): 11-18 of 182 learner rows per configuration, mostly L4, L5, L6 and L3-FS4, |diff mean regret| up to 0.0271, 63-124 of 6,528 recommendations; no hypothesis verdict changes and the H1-H8 estimates agree to 4 decimals except H4 of sens_v1 (0.0007 against 0.0011); two runs on the PC are bit-identical', 'options': ['(a) the PC environment (pinned, the one of the phase-1 run) is the environment of record; the Linux run is reported as a cross-platform replication with the differences above', '(b) the Linux host is the environment of record', '(c) both sets are reported side by side for every learner row'], 'recommendation': '(a), with the pip freeze and the platform string of both machines in the package', 'blocks': ['which mm_metrics rows of L4, L5, L6 enter a table', 'the reproducibility statement'], 'author_question': 'Q-39', 'status': 'OPEN 2026-11-20'},
    {'id': 51, 'ratified_2026-11-20': 'RATIFIED (b) by the author on 2026-11-20 (Q-40): the five mandatory subgroups and per-task E1 runs are completed before C2 is concluded; see correction_2026-11-20b for the four statements of this entry that were wrong or incomplete', 'correction_2026-11-20b': "(1) the cohort audits do not hold the four slices: they hold COURSE x TEMPORAL joint slices with two metrics under a definition without the cutoff condition; the slices are recomputed from the stored per-sample predictions (no training, no inference); (2) E1-B is scored on 48 situations in the registered design as well: the main report slice is (ALL, ALL) (Table 42), the five subgroups enlarge the training set and add secondary reports; (3) the executed analysis is the robustness variant registered in Table 42, run with the task-pooled folds of Appendix E.4; (4) option (b) also needs seen flags by the registered rule, an S0 profile by subgroup and an extension of the reference package (AUTHOR_RATIFICATIONS_2026_11_20['corrections'])", 'topic': 'design scope of the meta tier behind every C2-C4 result so far (2026-11-20; stated by the team in section 8 of the Drive copy of its 20/11 report, a section the attached copy does not have; true of the phase-1 run of 13/11 as well): (i) Meta-Dataset-Report v1.9 registers five mandatory subgroups per situation, (ALL, ALL), (LEARNER, SEEN), (LEARNER, UNSEEN), (COURSE, SEEN), (COURSE, UNSEEN); every meta release holds the (ALL, ALL) rows only, so the registered fold E1-B has 48 recommendation situations (one per cluster) instead of 240 and the state block takes 24 distinct values (task x window x phase); the cohort audits of the facts packages hold the four other slices; (ii) section 10.8 names E1-B as the primary fold, E1-A as the replication and, because each task has only 24 clusters per window, an additional test on the two tasks and the two folds pooled (96 clusters); the runs follow the Appendix E command on the combined CQ+LO table, where the reference package pools the two tasks inside E1-A and E1-B and writes hypothesis rows for E1-B only: neither per-task E1 runs nor the replication and pooled rows exist in mm_hypotheses (gap of the reference package); the writing side computed H1-H4 and H7 on E1-A, on the 96 clusters and by task from the recommendation rows (descriptive, mm_replication_pooled_bytask.json)', 'options': ['(a) the executed analysis is the analysis of this paper: Method and threats state both reductions (one subgroup; task-pooled folds), the E1-A and pooled rows are reported next to E1-B from the team files, the per-task subsets descriptively; no run beyond the 0.2.5 re-issue', '(b) the registered design is completed before C2 is concluded: the team exports the facts of the four cohort subgroups from the stored audits (no training), the release is re-assembled with five subgroups, M-15 is re-run (with per-task E1 runs), and decision 48 is taken on that result', '(c) per-task E1 runs are added to the 0.2.5 re-issue now (child releases, no new data), the subgroups are deferred to the full release and stated as a limitation'], 'recommendation': '(c) as the immediate step, and (b) for the conclusion on C2 if the team confirms that the cohort-slice facts can be exported without retraining; under (a) or (c) the paper does not call the executed comparison the pre-registered test without naming the two reductions', 'blocks': ['decision 48 (Q-37)', 'the wording of H1-H8 in Method 4.6 and Experiments 5.3-5.4', 'C1: the description of the meta-dataset (situations per cluster)', 'the scope of the M-15 re-issue asked on 20/11'], 'author_question': 'Q-40', 'status': 'OPEN 2026-11-20'},
    {'id': 52, 'ratified_2026-11-21': 'RATIFIED (a) by the author on 2026-11-21 (Q-41): per-task training is primary, verdict rows on the clusters of the two tasks together, per-task rows beside them, E1-A replication, 96-cluster pooled test, task-pooled run as a labelled sensitivity analysis; implemented in metamodel 0.3.0 (e1_scope = PER_TASK, hypothesis_rows = REGISTERED)', 'topic': "full-design run, primary reading of E1 (2026-11-20b, opened by decision 51 (b)): section 10.10 of the Meta-Dataset-Report registers the main grid per task (task (2) x fold (2)) and Table 46 defines B2 on the meta-train 'of the task', while Appendix E.4 (confirmed on 24/10) documents one run on the combined CQ+LO table, in which E1-A and E1-B pool the two tasks, task is a context feature (FS0) and B3 averages the two tasks inside each (model, phase); every result so far follows Appendix E.4 (E1-B: 48 clusters). Section 10.8 names E1-B as the primary fold, E1-A as the replication and a pooled test on the two tasks and the two folds (96 clusters). Once per-task runs exist, the rows that carry the verdicts of H1-H4 and H6-H8 have to be named before any result is read", 'options': ['(a) per-task training is primary (section 10.10): one model per task and fold, each scored on its own task; the verdict rows of E1-B are computed on the 48 clusters of the two tasks together and the 24-cluster rows of each task are reported beside them; E1-A is the replication and the 96-cluster test follows section 10.8; the task-pooled run of Appendix E.4 is kept as a labelled sensitivity analysis', '(b) task-pooled training stays primary (Appendix E.4, the analysis reported so far); the per-task runs are the additional analysis', '(c) per-task training is primary and the verdict is given per task (two rows of 24 clusters for each hypothesis, no joint row)'], 'recommendation': '(a): it is the reading of the registered grid and of Table 46, it keeps the 48-cluster unit of every table so far, and it makes B3 a per-task comparator; (c) halves the clusters behind each verdict; (b) keeps a B3 that averages the two tasks, which Table 46 does not say', 'blocks': ['the next release of the reference package (full-design run)', 'check 47', 'decision 48: the wording of C2'], 'author_question': 'Q-41', 'status': 'OPEN 2026-11-20'},
    {'id': 53, 'ratified_2026-11-21': 'RATIFIED (a) by the author on 2026-11-21 (Q-42): baselines and inner selection on the matched slice; the all-rows variant is a labelled sensitivity analysis; implemented in metamodel 0.3.0 (baseline_scope = MATCHED_SLICE; ALL_ROWS for the variant)', 'topic': "full-design run, use of the subgroup rows by the baselines and by the inner selection (2026-11-20b): Table 42 puts the five subgroups into the meta-training set and names (ALL, ALL) as the main report slice; Table 46 defines B2 and B3 'on meta-train' without a subgroup key, and section 10.6 selects the hyper-parameters, the k of B5 and the thresholds of B4 by the mean regret of the inner validation groups without naming a slice; rows of different subgroups of the same (model, phase, window) are strongly dependent (section 10.3)", 'options': ['(a) matched slice: B2, B3, the thresholds of B4 and the neighbours of B5 are estimated on the training rows of the subgroup of the situation they score, and the inner selection minimises the mean regret of the (ALL, ALL) groups of the inner validation part; on the main slice the baselines are then exactly those of the ALL-only analysis and only the learners gain training rows; the all-rows variant is reported as a labelled sensitivity analysis', '(b) all training rows: the baselines are estimated on the five subgroups together without a subgroup key and the inner selection uses every group; the matched variant is reported as the sensitivity analysis'], 'recommendation': '(a): the comparator is not diluted by small slices, the quantity selected in the inner loop is the quantity reported, and the comparison with the tables of 13/11 and 20/11 isolates the effect of the added training rows', 'blocks': ['the next release of the reference package (full-design run)', 'check 47'], 'author_question': 'Q-42', 'status': 'OPEN 2026-11-20'},
    {'id': 54, 'ratified_2026-11-21': "RATIFIED (b) by the author on 2026-11-21 (Q-43): one Holm family over every test row of mm_hypotheses; the recommendation of the writing side was (a); the rows of the table are fixed before the run (AUTHOR_RATIFICATIONS_2026_11_21['implementation'] and decision 55)", 'topic': 'full-design run, Holm family (2026-11-20b): section 10.8 corrects H1-H8 by Holm at alpha_stat = 0.05; Appendix E applies Holm to every comparison with a bootstrap p in mm_hypotheses, a table that so far holds the rows of the primary fold only (and of E2 for H5); the full-design run adds the registered E1-A replication rows, the 96-cluster pooled rows, the per-task rows and the rows of the secondary SEEN / UNSEEN slices', 'options': ['(a) Holm inside the primary family only (the rows that carry the verdicts, as named by decision 52); every other row carries an analysis_role (REPLICATION_E1A, POOLED_2FOLD, PER_TASK, SECONDARY_SLICE, SENSITIVITY) and is adjusted inside its role; the verdict of a hypothesis stays the confidence-interval criterion of Table 50 on the primary rows', '(b) one family: Holm over every row of mm_hypotheses, so that each added row changes the adjusted p of the primary rows'], 'recommendation': '(a): it is the family of section 10.8 (H1-H8) and it keeps the adjusted p of the primary rows comparable with the tables so far; (b) follows the letter of Appendix E, which was written for a table without these rows', 'blocks': ['the next release of the reference package (full-design run)', 'check 47'], 'author_question': 'Q-43', 'status': 'OPEN 2026-11-20'},
    {'id': 55, 'topic': "full-design run, status of the comparisons on the secondary SEEN / UNSEEN slices (2026-11-21, opened by decision 54 (b)): Table 42 of the Meta-Dataset-Report registers the four slices as secondary report slices and Table 50 defines H1-H8 on the primary protocol; the topic of decision 54 named 'the rows of the secondary SEEN / UNSEEN slices' among the rows that the full-design run would add to mm_hypotheses; with one Holm family every row of that table changes the adjusted p of the primary rows, so the membership of the table is fixed before the run", 'options': ['(a) reports: for every evaluation unit and slice the summary, its intervals and the paired difference of the mean regret to B3 are written to mm_metrics_secondary with status DESCRIPTIVE; mm_hypotheses holds the registered tests only (primary, per task, E1-A replication, 96-cluster pooled, E2); this is what metamodel 0.3.0 does', '(b) tests: H1-H4 and H6-H8 are also tested on each of the four secondary slices and their rows enter the one Holm family (about four times more test rows)'], 'recommendation': '(a): Table 42 calls them report slices; a slice holds a subset of the enrollments of ALL, so its tests repeat the primary ones on dependent data; 38 of the 240 slice cells are flagged small and 19 hold two classes only (subgroup_slice_support.csv of 21/11); the per-group outcomes are kept in mm_recommendations_secondary, so (b) can be computed later from the same runs without retraining', 'blocks': ['the wording of the secondary-slice results'], 'does_not_block': 'the full-design runs of check 47', 'author_question': 'Q-44', 'status': 'OPEN 2026-11-21',
     'ratified_2026-11-21': 'RATIFIED (a) by the author on 2026-11-21 (second pass; Q-44), written into the registry on 2026-11-23: the secondary SEEN / UNSEEN slices are descriptive reports outside mm_hypotheses and outside the Holm family (AUTHOR_RATIFICATIONS_2026_11_21B)'},
    {'id': 56, 'topic': 'record of the state of knowledge behind decisions 52-54 (2026-11-21): the code team ran E1-A and E1-B per task on 20/11 with metamodel 0.2.4 on the (ALL, ALL) rows of release 20261120, before the request that asked not to, and read the results; the reply of 21/11 does not show them and the writing side has not opened them; the manuscript has to say whether the choice of the primary reading of E1 (decision 52) was made before or after these outcomes were seen by the person who made it', 'options': ['(a) the author had not seen the regret or hypothesis tables of the exploratory per-task run when answering Q-41 to Q-43: recorded as such; the run stays unopened until the full-design run is accepted', '(b) the author had seen them: the Experiments section states that the primary reading of E1 was chosen after an exploratory per-task run on the ALL-only rows, and that run is reported'], 'recommendation': 'none: this is a statement of fact by the author', 'blocks': ['the paragraph of the Experiments section on the order of the decisions and the runs'], 'does_not_block': 'the full-design runs of check 47', 'author_question': 'Q-45', 'status': 'OPEN 2026-11-21',
     'ratified_2026-11-21': 'RATIFIED (a) by the author on 2026-11-21 (second pass; Q-45), restated on 2026-11-23 and written into the registry that day: the author had not seen the tables of the exploratory per-task run when answering Q-41 to Q-43; the run stays sealed until check 47 is accepted (AUTHOR_RATIFICATIONS_2026_11_21B)'},
    {'id': 57, 'topic': "fitted meta-models and model explanation of the full-design run (2026-11-24): the table of outputs of the Meta-Dataset-Report lists mm_models/ (fitted models and preprocessors with sha256) and the contributions contract lists SHAP among the verification experiments of C2; metamodel <= 0.3.0 writes neither: the delivered runs keep the configuration, the seeds, best_params and the model-native importances (mm_feature_importance, mean and sd over the learner seeds); the checklist item T2-MM4-03 words SHAP as optional ('SHAP if installed')", 'options': ['(a) no re-run: the deviation from the output list is recorded and stated in the paper (the models are reproducible from the package, the frozen configuration, the seeds and the release; they are not archived); the explanation of C2 uses mm_feature_importance and the nested feature sets FS0-FS5; SHAP is removed from the verification experiments of C2 in 00_contributions.md', '(b) the writing side adds the export of fitted models and preprocessors (and SHAP values of L3-FS3 on the test rows) to a package 0.3.1 without changing a computation; the team re-runs the main configuration as a labelled reproduction run (the run of record took 9.9 hours); the writing side compares every table with the run of record, which stays the run of record', '(c) as (b) for the ten configurations'], 'recommendation': '(a): H1 and H2 are not supported and the negative control fails in most folds, so SHAP would explain a learner that does not beat the baselines, and determinism on the machine of record is already shown by B.5 r2 (48 tables equal to phase A); (b) if the author wants the output list of the design document met as written. Recommendation of the writing side, not a decision', 'blocks': ['the reproducibility statement of the paper', 'the list of verification experiments of C2 in 00_contributions.md (SHAP)'], 'does_not_block': 'the acceptance of check 47; the Method section', 'author_question': 'Q-46', 'status': 'OPEN 2026-11-24', 'ratified_2026-11-24': 'RATIFIED (a) by the author on 2026-11-24 (second pass; Q-46), written into the registry on 2026-11-26: no re-run; the paper states that the fitted meta-models are not archived and can be refitted from the package, the frozen configuration, the seeds and the release; SHAP is removed from the verification experiments of C2; the explanation uses mm_feature_importance and the nested feature sets'},
    {'id': 58, 'topic': "negative control MQ08 of the full-design run (2026-11-24): the registered control is one permutation of the state features in meta-train with one learner seed, compared with the five-seed model; it passes in 5/12 folds of the main configuration (5 to 7 of 12 in the nine configurations with 12 folds, 5/7 in V2); on E1-B of LO the permuted model has the lower regret (0.0181 against 0.0471; B3 0.0203); Table 53 of the Meta-Dataset-Report makes 'MQ01-MQ09 pass' the condition of stage MM3", 'options': ['(a) MQ08 is reported as measured, as a result: on this meta-dataset the state features do not carry a signal that the learner can use (in line with H2 not supported and with the rank of the FS0 learners); the stage condition of Table 53 is recorded as not met on MQ08 and the analysis proceeds, as in phase A; no further run', '(b) in addition a labelled sensitivity analysis outside the registered tables: K permutations x 5 learner seeds of L3-FS3 on the 12 folds of the main configuration, protocol fixed before the run (needs a package change by the writing side and a run by the team)'], 'recommendation': '(a): (b) adds precision to a negative result and no claim of the paper depends on it under decision 48 (a). Recommendation of the writing side, not a decision', 'blocks': ['the paragraph of the Experiments section on the negative control'], 'does_not_block': 'the acceptance of check 47', 'author_question': 'Q-47', 'status': 'OPEN 2026-11-24', 'ratified_2026-11-24': 'RATIFIED (a) by the author on 2026-11-24 (second pass; Q-47), written into the registry on 2026-11-26: MQ08 reported as measured, no further run', 'premise_withdrawn_2026-11-26': "the premise of the question was wrong: on 2026-11-24 the code team found a dtype defect of the package in the permutation step (POST_MATERIALIZE_CHECKS[47]['correction_2026-11-26']); 'as measured' would report a control that is confounded by the encoding of the state features; the decision is superseded by decision 59 (Q-48) and is not applied to the manuscript"},
    {'id': 59, 'topic': 'negative control of the full-design runs after the dtype defect of metamodel 0.3.0 (2026-11-26): the delivered mm_negative_control tables are confounded by the encoding of the state features; a dtype-preserved control of the main configuration exists (script of the team on the frozen folds: 6/12 folds pass against 5/12; E1-B fails in both tasks in both versions); the corresponding table for the ten configurations is announced in the report of the team and was not delivered', 'options': ['(a) the paper reports the dtype-preserved control (one permutation, one learner seed, as registered) and discloses the defect and the delivered tables in the supplement; the team delivers the table of the 115 folds and commits its script; the writing side verifies the table before any figure enters the manuscript; no new run of the analysis', '(b) as (a), and in addition the fix enters metamodel 0.3.1 and the team re-runs the control alone for the ten configurations with the package, so that the corrected table is an output of the package (needs a control-only entry point written by the writing side and a run by the team)', '(c) the control is left out of the results of the paper; the defect and the omission are disclosed in the supplement'], 'recommendation': '(a), with the fix of the permutation step entering 0.3.1 in any case: the corrected control leaves the reading unchanged on the verdict unit and no claim of the paper rests on it; (b) if the author wants every reported table to be an output of the package. Recommendation of the writing side, not a decision', 'blocks': ['the paragraph on the negative control in Sections 4.5 and 5 and item D5 of Online Resource 1', 'the row of MQ08 in the summary table of the ten configurations'], 'does_not_block': 'the review of Method v0.5; H1 to H8; the Experiments outline', 'supersedes': 'decision 58 (Q-47)', 'author_question': 'Q-48', 'status': 'OPEN 2026-11-26', 'ratified_2026-11-26': 'RATIFIED (b) by the author on 2026-11-26 (second pass; Q-48): the paper reports the dtype-preserved control and discloses the defect and the delivered tables in the supplement; the fix enters metamodel 0.3.1 and the code team re-runs the control alone for the ten configurations with the package (check 48); the delivered mm_negative_control tables stay in the record as evidence of the defect'},
    {'id': 60, 'topic': "cost at decision time (2026-11-26): the cost model F-COST of the design document was not fitted; the utility rule and H6 of the delivered runs use the relative cost recorded for each candidate of the scored group (POST_MATERIALIZE_CHECKS[47]['deviations_2026-11-26']['cost_model_not_fitted']); the component C3 of the contributions contract names F-COST in its mechanism", 'options': ['(a) the paper describes the rule as run (Method v0.5 does) and adds one labelled post hoc analysis computed by the writing side from the delivered files: the utility rule with a decision-time cost estimate (mean log2 relative cost of the same task, model and pipeline over the training windows of the fold) next to the rule with the recorded cost; the mechanism cell of C3 is reworded', '(b) the paper describes the rule as run, without the additional analysis; the mechanism cell of C3 is reworded', '(c) F-COST is implemented in metamodel 0.3.1 and the team re-runs the configurations (new runs after the results were seen, to be labelled as such)'], 'recommendation': '(a): it answers the question a reader will ask (does the cost saving survive when cost has to be anticipated) without a new run; relative training cost of a pipeline is stable across windows by construction of the grid, which the analysis will show or refute. Recommendation of the writing side, not a decision', 'blocks': ['the wording of the cost-aware component in the Introduction and the Abstract', 'the cost paragraph of Section 5'], 'does_not_block': 'the review of Method v0.5 (Section 4.6 describes the rule as run)', 'author_question': 'Q-49', 'status': 'OPEN 2026-11-26', 'ratified_2026-11-26': "RATIFIED (a) by the author on 2026-11-26 (second pass; Q-49): the rule is described as run; one labelled post hoc analysis with a decision-time cost estimate is computed by the writing side from the delivered files (POST_MATERIALIZE_CHECKS[47]['followup_2026-11-26b']['post_hoc_cost_at_decision_time']); the mechanism cell of C3 in the contributions contract is reworded"},
    {'id': 61, 'topic': "H7 as registered against H7 as implemented (2026-11-26): POST_MATERIALIZE_CHECKS[47]['deviations_2026-11-26']['H7_row']", 'options': ['(a) the writing side computes the registered comparison from mm_recommendations of full_main_cal_time and full_obj_macrof1 (paired by recommendation group, cluster bootstrap with the convention of record), labelled as computed after the runs from delivered outputs; the paper reports the registered comparison as H7 and the implemented row next to it', '(b) the paper reports the implemented row only and discloses the difference from the design document', '(c) the registered row is implemented in metamodel 0.3.1 and the team re-runs the configuration pair'], 'recommendation': '(a): the registered hypothesis is the one the paper should answer, and the two runs that it needs are registered configurations already delivered. Recommendation of the writing side, not a decision', 'blocks': ['the row of H7 in the table of hypotheses of Section 5 and the wording of Section 4.7'], 'does_not_block': 'the review of Method v0.5 (Table of hypotheses states the row as run, with an open comment)', 'author_question': 'Q-50', 'status': 'OPEN 2026-11-26', 'ratified_2026-11-26': "RATIFIED (a) by the author on 2026-11-26 (second pass; Q-50): the writing side computes the registered comparison from mm_recommendations of full_main_cal_time and full_obj_macrof1 (POST_MATERIALIZE_CHECKS[47]['followup_2026-11-26b']['post_hoc_H7_as_registered']); the paper reports the registered comparison as H7 and the implemented row beside it"},
    {'id': 62, 'topic': 'labelled table of several permutations for the negative control (2026-11-26, second pass): the registered control compares one fit (one permutation, one learner seed) with the model of record, which averages the scores of the learner seeds of the configuration; on 24/11 the team explored five permutations with every learner seed on the main configuration, and metamodel 0.3.1 reproduces that table (option --permutations of the control-only command)', 'options': ['(a) Online Resource 1 reports, beside the registered control, the labelled exploratory table of five permutations for the ten configurations; the team adds --permutations 5 to the control-only run (minutes of computation); the main text keeps the registered control', '(b) the labelled table is reported for the main configuration only (computed by the team on 24/11 and reproduced by the package)', '(c) the paper reports the registered control only'], 'recommendation': '(a): the registered control rests on one draw and on a comparison of one learner seed with five; in the main configuration the control is lower than the model in all five permutations in 4 of 12 folds and higher in all five in 4, so several flags depend on the draw; the table shows the reader how stable each flag is and is labelled as computed after the runs. Recommendation of the writing side, not a decision', 'blocks': ['one sentence and one table of item D5 in Online Resource 1'], 'does_not_block': 'the control-only re-run (check 48), the Experiments outline, everything else', 'author_question': 'Q-51', 'status': 'OPEN 2026-11-26'},
]

# Author questions still open on 2026-11-10 (the team executed the recommended or an alternative option before the answer).
OPEN_AUTHOR_QUESTIONS_2026_11_10 = {
    'Q-27': {'decision': 38, 'recommended': '(a)', 'executed_by_team': '(a)', 'needs': 'ratification of the LO r2 package as citable'},
    'Q-28': {'decision': 39, 'recommended': '(a) on 09/11, (c) as executed on 10/11', 'executed_by_team': '(c)', 'needs': 'ratification of S0 v4'},
    'Q-29': {'decision': 40, 'recommended': '(a)', 'executed_by_team': '(a)', 'needs': 'record only; M-15 by 13/11; gate 14/11'},
    'Q-30': {'decision': 41, 'recommended': '(b)', 'executed_by_team': '(b)', 'needs': 'ratification of F2 = CQ V0-V16 in the tables and in the meta release'},
    'Q-31': {'decision': 42, 'recommended': '(a)', 'executed_by_team': None, 'needs': 'tolerance / reference-copy contract for check 38'},
    'Q-32': {'decision': 43, 'recommended': '(a)', 'executed_by_team': '(a) provisionally', 'needs': 'acceptance of the retroactive mapping and the NULL V0 cells'},
}

# Author questions open on 2026-11-13 (round 28).
OPEN_AUTHOR_QUESTIONS_2026_11_13 = {
    'Q-14': {'decision': None, 'recommended': '(a)', 'executed_by_team': None, 'needs': 'the author copies the 10-13/11 package folders into input/results/_incoming_2026-11-13/; blocks every citation (check 42)',
             'executed_by_author': '(a) on 2026-11-13: 13 phase-1 packages copied, sha256 equal; check 42 PASSED', 'status': 'CLOSED 2026-11-13'},
    'Q-27': {'decision': 38, 'recommended': '(a)', 'executed_by_team': '(a)', 'needs': 'ratification'},
    'Q-28': {'decision': 39, 'recommended': '(c)', 'executed_by_team': '(c)', 'needs': 'ratification'},
    'Q-30': {'decision': 41, 'recommended': '(b)', 'executed_by_team': '(b)', 'needs': 'ratification; M-15 ran on this scope'},
    'Q-31': {'decision': 42, 'recommended': '(a) + check 41 tolerance 1e-3 with the thread mode recorded', 'executed_by_team': '(a)', 'needs': 'ratification'},
    'Q-32': {'decision': 43, 'recommended': '(a)', 'executed_by_team': '(a) provisionally', 'needs': 'acceptance of the *_RETROACTIVE basis for three packages'},
    'Q-33': {'decision': 44, 'recommended': '(a)', 'executed_by_team': None, 'needs': 'how C2-C3 are presented after M-15 phase 1'},
    'Q-34': {'decision': 45, 'recommended': '(a)', 'executed_by_team': None, 'needs': 'restatement of H8 before the three-seed run'},
}

# Author questions open on 2026-11-20 (round 30).
OPEN_AUTHOR_QUESTIONS_2026_11_20 = {'Q-37': {'decision': 48, 'summary': 'position of C2, C3, C4 after the three-seed M-15: H1 not supported on the registered analysis, H6 supported in 6/6 configurations', 'recommendation': '(a) fallback of decisions 36/44: C1, C3, C4 (descriptive), C5 as contributions; C2 as a registered negative result'}, 'Q-38': {'decision': 49, 'summary': 'energy of the 8 seed-44 CQ cells without a measurement: keep empty, accept the labelled imputation, or re-run', 'recommendation': '(a) keep empty'}, 'Q-39': {'decision': 50, 'summary': 'environment of record of the meta-tier runs (Windows PC against Linux host: learner rows differ, verdicts do not)', 'recommendation': '(a) the pinned PC environment'}, 'Q-40': {'decision': 51, 'summary': 'design scope of the meta tier: one subgroup instead of the five registered ones, task-pooled E1 folds, no replication or pooled rows in the hypothesis table', 'recommendation': '(c) per-task E1 runs in the re-issue now; (b) completing the five subgroups before concluding on C2 if the team confirms the export needs no training'}, 'still_open': ['Q-20', 'Q-21', 'Q-22', 'Q-23', 'Q-24', 'Q-26', 'Q-35', 'Q-36'], 'note': 'Q-40 is answered before Q-37. Q-35: the recommendation of the writing side moved from (a) to (b) on 2026-11-20 (three seeds complete; the meta tier is analysed on the three-seed aggregate)'}

# Author questions after the acceptance of phase C (round 33, 2026-11-24).
# Author questions open after the second pass of 2026-11-26 (round 34).
OPEN_AUTHOR_QUESTIONS_2026_11_26B = {'Q-51': {'decision': 62, 'summary': 'negative control: (a) labelled table of five permutations for the ten configurations in Online Resource 1, beside the registered control; (b) for the main configuration only; (c) registered control only. Recommendation of the writing side: (a)'}, 'answered_2026-11-26_second_pass': {'Q-48': '(b)', 'Q-49': '(a)', 'Q-50': '(a)'}, 'for_the_author_2026-11-26b': ['H7 as registered is not supported on the verdict unit: the health gain of the composite objective over the MacroF1 objective is +0.000236 with an interval that barely excludes 0, and the lower limit of the MacroF1 difference (-0.0126) is below the tolerance; the implemented row is not supported either', 'cost at the decision moment: with a cost estimate taken from earlier windows the cost of the recommendation does not fall on the verdict unit (+0.0542 log2 units against -0.3023 with the recorded cost); the claim of C3 has to be limited to the rule with known cost', 'public repository: licence of the code and of the data, time of the release tag, a persistent identifier for the data, and the fate of the internal documents under docs/ are decisions of the author', 'Method v0.5.1 and Online Resource 1 v0.2 wait for a reading of the sixteen listed changes', 'the Experiments outline v0.2 is the next step and is submitted for approval before any table is generated'], 'still_open': ['Q-20', 'Q-22', 'Q-23', 'Q-24', 'Q-51']}

# Author questions open on 2026-11-26 (round 34).
OPEN_AUTHOR_QUESTIONS_2026_11_26 = {'Q-48': {'decision': 59, 'summary': 'negative control after the dtype defect of metamodel 0.3.0: (a) report the dtype-preserved control with disclosure, the team delivers and commits the 115-fold table, no new run; (b) in addition a control-only re-run with 0.3.1; (c) leave the control out, with disclosure. Recommendation of the writing side: (a)'}, 'Q-49': {'decision': 60, 'summary': 'cost at decision time: (a) rule described as run plus a labelled post hoc analysis with a decision-time cost estimate from delivered files; (b) as run only; (c) F-COST implemented and re-run. Recommendation of the writing side: (a)'}, 'Q-50': {'decision': 61, 'summary': 'H7: (a) the registered comparison computed from the two delivered configurations and reported with the implemented row; (b) implemented row only, with disclosure; (c) re-run. Recommendation of the writing side: (a)'}, 'answered_2026-11-24_second_pass': {'Q-46': '(a)', 'Q-47': '(a), superseded by Q-48'}, 'answered_2026-11-26': {'Q-26': '(a)', 'Q-21': 'T17 and T18 stay in the main text (answer 6, plan section 4)'}, 'for_the_author_2026-11-26': ['Method v0.5 and Online Resource 1 (S1 to S4) are written and wait for approval; measured length of the Method in the acmsmall layout: about fourteen pages with four tables and two figures, above the estimate of the plan', 'scope of TOIS: the reframed paper is arguable under the charter items on evaluation methodology and on applications that expose weaknesses of techniques, but it stays at the edge of information retrieval; a pre-submission inquiry to the Editor-in-Chief is the way to know', 'open comments of Method v0.5: outcome table of QA01 to QA24 for release r2, interpreter version of the phase C environment, static layout of the CQ recurrent runs of seed 42, Radius-SMOTE fallback rates for the three seeds', 'Q-22 and Q-23 are replaced by the approved table plan as proposed in section 6 of the plan; they are confirmed with the Experiments outline v0.2; Q-20 and Q-24 are submitted again at their steps'], 'still_open': ['Q-20', 'Q-22', 'Q-23', 'Q-24', 'Q-48', 'Q-49', 'Q-50']}

OPEN_AUTHOR_QUESTIONS_2026_11_24 = {'Q-46': {'decision': 57, 'summary': 'fitted meta-models (mm_models/ of the design document) and SHAP are not produced by metamodel 0.3.0: (a) record and state the deviation, no re-run; (b) export added in 0.3.1 and a labelled reproduction run of the main configuration; (c) of the ten configurations. Recommendation of the writing side: (a)'}, 'Q-47': {'decision': 58, 'summary': 'negative control MQ08 passes in 5/12 folds of the main configuration: (a) reported as measured, no further run; (b) labelled multi-permutation sensitivity analysis. Recommendation of the writing side: (a)'}, 'for_the_author_2026-11-24': ["disclosure: the intervals and p values of mm_hypotheses depend on the pandas version through the cluster order of the bootstrap (POST_MATERIALIZE_CHECKS[47]['acceptance_2026-11-24']['findings']['bootstrap_cluster_order']); the values of record are those of the environment of record; under the other order 0 supported flags change in the ten configurations; the writing side proposes to keep the tables of record and to fix the order in the next package version; open to a veto of the author", 'decision 48 (a): on the row that carries the verdict H1 is supported in none of the ten configurations, so the clause that would have reopened the decision is not triggered; C2 is the registered comparison without a superiority claim', 'the revised mapping table of 00_contributions.md section 2 announced on 20/11 for after check 47 is proposed in 00_contributions.md v0.16 and is not applied before the author approves it', "the exploratory per-task run of 20/11 is still unopened by the writing side; the condition 'until check 47 is accepted' is met; it is opened only if the author asks (variant V1 replaces it)"], 'still_open': ['Q-20', 'Q-21', 'Q-22', 'Q-23', 'Q-24', 'Q-26', 'Q-46', 'Q-47'], 'note': 'neither question blocks the writing of the Method section; the table plan T05 / T17 / T18 / F07 of decision 46 (b) is still owed by the writing side'}

# Author questions after the acceptance of phase B (round 32, 2026-11-23).
OPEN_AUTHOR_QUESTIONS_2026_11_23 = {'answered_2026-11-21_second_pass': {'Q-44': '(a)', 'Q-45': '(a)'}, 'restated_2026-11-23': {'Q-45': '(a)'}, 'new_questions': 'none', 'for_the_author_2026-11-23': ["technical confirmation given by the writing side to the code team, open to a veto of the author: the ALL rows of the accepted fact packages are not recomputed, so six metric columns of the ALL rows of the eight F1 units of seed 42 keep the accepted values, which differ from the values the present builder recomputes (largest differences in POST_MATERIALIZE_CHECKS[46]['acceptance_2026-11-23']['report_only_differences']); none of the six is an objective; three of them feed warm-start inputs (FS4, FS5)", "disclosure: a smoke test of the full-design code path was run by the writing side on the rebuilt table after the ten digests had been computed (POST_MATERIALIZE_CHECKS[47]['smoke_test_2026-11-23'])"], 'still_open': ['Q-20', 'Q-21', 'Q-22', 'Q-23', 'Q-24', 'Q-26'], 'note': 'no author question blocks phase C; the table plan T05 / T17 / T18 / F07 of decision 46 (b) is still owed by the writing side'}

# Author questions open on 2026-11-21 (round 31).
OPEN_AUTHOR_QUESTIONS_2026_11_21 = {'Q-44': {'decision': 55, 'summary': 'full-design run: the secondary SEEN / UNSEEN slices are reports outside the Holm family (as implemented) or tests inside it', 'recommendation': '(a) reports, as Table 42 registers them'}, 'Q-45': {'decision': 56, 'summary': 'for the record: had the author seen the tables of the exploratory per-task run of 20/11 before answering Q-41 to Q-43', 'recommendation': 'none (statement of fact)'}, 'answered_2026-11-21': {'Q-41': '(a)', 'Q-42': '(a)', 'Q-43': '(b)'}, 'confirmed_2026-11-21': ['the three conventions of the facts contract (check 46)', 'the reading of decisions 48 (a) and 51 (b)'], 'still_open': ['Q-20', 'Q-21', 'Q-22', 'Q-23', 'Q-24', 'Q-26', 'Q-44', 'Q-45'], 'note': 'neither Q-44 nor Q-45 blocks the runs: the per-group outcomes of the secondary slices are written by the run, and Q-45 is a statement for the Experiments section'}

# Author questions open after the second pass of 2026-11-20 (round 30b).
OPEN_AUTHOR_QUESTIONS_2026_11_20B = {'Q-41': {'decision': 52, 'summary': 'full-design run: which E1 analysis carries the verdicts (per-task training of section 10.10 or the task-pooled run of Appendix E.4)', 'recommendation': '(a) per-task primary, verdict rows on the 48 clusters of the two tasks, task-pooled run as sensitivity'}, 'Q-42': {'decision': 53, 'summary': 'full-design run: baselines and inner selection on the matched slice or on all five subgroups', 'recommendation': '(a) matched slice, all-rows variant as sensitivity'}, 'Q-43': {'decision': 54, 'summary': 'full-design run: Holm inside the primary family or over every row of mm_hypotheses', 'recommendation': '(a) primary family only, other rows adjusted inside their analysis role'}, 'answered_2026-11-20': {'Q-35': '(b)', 'Q-36': '(a)', 'Q-37': '(a)', 'Q-38': '(a)', 'Q-39': '(a)', 'Q-40': '(b)'}, 'still_open': ['Q-20', 'Q-21', 'Q-22', 'Q-23', 'Q-24', 'Q-26', 'Q-41', 'Q-42', 'Q-43'], 'note': 'Q-41 to Q-43 block only the full-design run (check 47): the re-issue of check 45 and the five-subgroup facts and release of check 46 do not wait for them; they are answered before any five-subgroup result exists'}

# Author questions open on 2026-11-16 (round 29).
OPEN_AUTHOR_QUESTIONS_2026_11_16 = {
    'Q-35': {'decision': 46, 'recommended': '(a)', 'executed_by_team': None, 'needs': 'how seed 43 (and 44) enter the phase-1 submission; blocks the seed-robustness paragraph and the wording of best-pipeline claims'},
    'Q-36': {'decision': 47, 'recommended': '(a)', 'executed_by_team': 'the team left variant_role NULL and delivered a registry overlay', 'needs': 'acceptance of NULL variant_role on PRIMARY_GRID facts (check 39 wording)'},
    'still_open': ['Q-20', 'Q-21', 'Q-22', 'Q-23', 'Q-24', 'Q-26'],
}

# Pipeline checks that remain after the decisions above; they do not change label, split or registry identifiers.
POST_MATERIALIZE_CHECKS = [
    {'id': 0, 'check': 'S0 per slice A/T1/T2/T3 x timeline_source: missing_rate and event_sparsity per source; read before interpreting '
                       'the T1 vs T2/T3 label contrast as learner behaviour', 'stage': 'S0'},
    {'id': 1, 'check': 'strict P1-P4 shares and duration/long-offering audit attached to the V3.1 release (units unchanged, 102 courses fewer)',
     'stage': 'after materialize'},
    {'id': 2, 'check': 'QA23 per phase on the current-grade group (9 columns) vs final_score; report |rho| and NMI at P1-P4', 'stage': 'P0'},
    {'id': 3, 'check': 'refresh final_score_contract_audit so that proxy_feature_contract lists all 19 fields and the _P1.._P4 variants', 'stage': 'P0'},
    {'id': 4, 'check': 'run_manifest carries scenario=hybrid, split_version per task, split_registry_id, parent manifest/audit ids, '
                       'code/config hash, seed, label_rule_version, label_threshold_set', 'stage': 'every run'},
    {'id': 5, 'check': 'QA11/QA12 on every S2 run: sampling_plan equals sampling.plan_targets for the real TRAIN pool (IR10_K10, cap 10); '
                       'synthetic rows SAME_PHASE_ONLY with INTERSECTION_OF_PARENTS masks; Radius-SMOTE fallback_nearest_neighbour_rate '
                       'per (window, class) with a ledger warning when > 0.50 (radius 0.092 too small for that class) [RESP §1]',
     'stage': 'every S2 run; read before allocating the model grid',
     'status_2026-11-03': 'EVIDENCE RECEIVED for CQ seed 42 (hash-verified): the fallback rate is above 0.50 in all 24 (window x class x parent) '
                          'rows (0.561-0.896); the S2 sampling summary (108 rows, 36 runs) confirms the IR10_K10 targets (W1 average 19,394 -> '
                          '157,672, good 13,166 -> 131,660; W2 39,589 / 32,421 -> 189,105; W3 44,513 / 39,208 -> 224,031; targets identical '
                          'across the three balancers) but leaves kappa_reached null (UNRESOLVED_DEFINITION) and the ledger hashes un-rehashed '
                          '(PRIOR_INVENTORY_NOT_REHASHED); the team labels the package PARTIAL_NOT_READY_FOR_M06_ACCEPTANCE; QA11/QA12 on '
                          'the plan is therefore PASS for the counts, OPEN for kappa and for LO; the warning itself is decision 33'},
    {'id': 6, 'check': 'feature source is cumulative_phase_features_v2 and the materializer grain audit reports zero collapsed duplicates; '
                       'inspect_view_grain.py on the Modal Volume shows one row per enrollment in every model_inputs split and TEST prefix view '
                       '(the GD1 views were 2x) [R1_C9]', 'stage': 'S0/S1 before any model run'},
    {'id': 7, 'check': 'L4 acceptance pilot (GRID_POLICY.pilot): strict determinism without a cuBLAS error, model_revision '
                       f'{MODEL_REVISION}, four dynamic mask bases in feature_layout.json, context__* audit fields present, one sanity '
                       'run completed', 'stage': 'before the full model grid'},
    {'id': 8, 'check': 'R4 reporting jobs delivered before the paper tables: F0 references, subgroup job incl. TEMPORAL STRICT/OVERLAP, '
                       'QA23 on the current-grade group, VALIDATION AccTEMPO and per-class export, energy fallback when NVML is '
                       'unavailable', 'stage': 'after core S0-S3'},
    {'id': 9, 'check': 'registry identifiers equal release_core/contracts.RELEASE_SPECS and the uploaded release_manifest.json '
                       '(label_threshold_set, split_version, phase_version, split_registry_id, label_rule_version) for both tasks',
     'stage': 'registry export', 'status': 'CLOSED 2026-10-06: LO/registries.py @ 799cf9e reads both strings from RELEASE_SPECS and '
                                           'validate_release_alignment() runs inside all_registries(); regression test added'},
    {'id': 10, 'check': 'release upload (upload_release.ps1): the materialization_lineage_<view_release> sidecar is checked locally '
                        '(features row exact_duplicates_collapsed = 0, feature_source under cumulative_phase_features_v2), uploaded next '
                        'to the views under /input/<release>/, and release_manifest.json is written last; an existing namespace is never '
                        'overwritten without an explicit -Overwrite; workers record materialization_lineage_dirs',
     'stage': 'before S0', 'status': 'CLOSED 2026-10-11: 98e772f/5b45586 validate the lineage sidecar locally, upload it next to the views '
                                     'and replace stale parts with -ReplaceExisting; an overwrite without that flag is still not refused (low)'},
    {'id': 11, 'check': 'F2/F3 acceptance before any family run is read: MOMENT embeddings finite for P1-P4 under the phase-as-patch '
                        'encoding (v1 right-padding gives NaN; adopted in c2856d2); constant channels fed as exact zeros (adopted in '
                        '813e7ea, revision v2_1); PatchTST and MOMENT prefix logits identical from truncated and full inputs; '
                        'channel count per task read from feature_layout.json (CQ: 274 per the team) and the F3 backbone-pass cost '
                        'measured in the pilot before the F3 core is scheduled; MOMENT microbatch (64 rows x C channels) checked '
                        'against the same fused-kernel batch limit that forced math SDP for PatchTST; '
                        'determinism pilot as registered in TEMPORAL_FAMILY_POLICY (CQ/W1/V0/seed 42, two runs, PATCHTST and '
                        'MOMENT_SMALL, prediction/probability checksums, metrics, best_epoch and manifest identity agree); '
                        'frozen MOMENT embeddings computed once per (window, pipeline, prefix) and cached (not implemented at 640be01); '
                        'model_revision, pinned Hub revision and input_encoding present in the manifest (model_app @ 640be01 does)',
     'stage': 'determinism pilot on L4', 'status': 'PASS per team report 2026-10-15 for PatchTST at the registered configuration (2048 = 4 x 512, '
                                                   '30 epochs, best 25, 8/8 prediction files and portable_run_id identical); evidence bundle '
                                                   'pending; MOMENT pilot and cache deferred until after the F2 grid',
     'status_2026-11-06': 'MOMENT items (finite embeddings under phase-as-patch, constant-channel guard, MOMENT microbatch, MOMENT pilot '
                          'and cache) superseded by check 37 after decision 37; the PatchTST items stay'},
    {'id': 12, 'check': 'before any VastAI cell is used: the same cell (CQ/W1/V0/seed 42, PATCHTST) run on Modal L4 and on a VastAI '
                        'NVIDIA L4 with the pinned image gives identical prediction/probability checksums and metrics; the VastAI '
                        'manifest carries execution_backend, gpu, torch/cuda/cudnn versions, model_revision and the locked release '
                        'vocabulary from release_core (review patch 2026-10-12b); an ingestion path into the L2 facts exists',
     'stage': 'before any VastAI grid run', 'status': 'OPEN 2026-10-12 (PENDING_DECISIONS[13])'},
    {'id': 13, 'check': 'portable tree and launcher: one S2 artifact per master seed for every balanced pipeline (MATCH_MASTER_SEED), '
                        'seed read from the download-manifest remote path and checked against the cell seed before training (review patch '
                        '2026-10-13b); launcher/shard plan and download script committed to the repository; every grid manifest records '
                        'batch_size 2048 with micro_batch_size/accumulation_steps or a registered F2 batch (PENDING_DECISIONS[14])',
     'stage': 'before any F2 grid cell is accepted',
     'status': 'OPEN 2026-10-14: runner-side seed check and accumulation adopted (265415d); still missing: launcher and download '
               'script in the repository, confirmation of S2 artifacts for seeds 43/44, the status of cells started with batch 512 '
               'before 265415d (to be quarantined under option (a)), and the pilot evidence bundle',
     'status_2026-11-03': 'OPEN and now contested: the team registry switched to FIXED_SEED_42 while the runner check, the launcher default and '
                          'the README keep MATCH_MASTER_SEED (CODE_REFERENCE.seed_policy_consistency_2026-11-03); the S2 artifacts for seeds '
                          '43/44 do not exist; batch / micro_batch / accumulation are printed in every PatchTST manifest (2048 / 512 / 4, 21 '
                          'cells); resolution follows decision 32 and check 35'},
    {'id': 14, 'check': 'LO F1 seed-42 grid (204 VastAI cells, REPORT_LO_EXECUTION_CONSOLIDATED_2026-10-15) before any number enters a '
                        'table: PENDING_DECISIONS[13] resolved with the Modal-vs-VastAI equivalence test; metadata_contract.json for all '
                        '204 cells (release LO_V3_1, portable_run_id, runner sha) and a grain audit of the downloaded parquet (rows = '
                        'distinct enrollment per window and split) with per-window row counts; code revision of the runs and the audit '
                        'code committed; L2 ingestion and parquet exports at window x prefix x pipeline x family x split grain into '
                        'input/results/GD1_LO_V3_1_clean_r1/; Radius-SMOTE pipelines labelled as sensitivity (fallback 53.6-81.1%, 24/24 '
                        'cells); averaging rule of summary tables stated (per-cell AccTEMPO means sit 0.004-0.012 below AccTEMPO of mean '
                        'components; S_san+ means 0.02-0.08 below the geometric mean of mean components)',
     'stage': 'before LO F1 numbers enter 03_claims',
     'status': 'OPEN 2026-10-17b: contracts verified and facts ingested; resources now come from the hash-verified run_manifest.json '
               '(run_resources, 20de6db = review patch 2026-10-15) under ingest_id vastai_f2_seed42_clean_20261015_r2 with the '
               'uniform-execution receipt (one runner sha, L4), as required. Still open: grain audit of the downloaded tree, the '
               'receipt itself (runner sha of the 204 LO runs), Radius pipelines labelled as sensitivity in tables, parquet exports '
               'into input/results/GD1_LO_V3_1_clean_r1/, per-window tables, and POST_MATERIALIZE_CHECKS[15]'},
    {'id': 15, 'check': 'LO W1/P1 VALIDATION-TEST discrepancy (REPORT_LO_V2 §15): TEST balanced accuracy 0.334-0.372 and macro-F1 '
                        '0.314-0.333 for all 68 cells (3-class chance 0.333) while VALIDATION is 0.39-0.53 / 0.41-0.50; s_drift 0.963 vs '
                        '0.9985 and s_maj_jsd 0.966 vs 0.998; CQ TEST P1 macro-F1 is 0.66 (REPORT_CQ 2026-10-08). Before any LO W1/P1 '
                        'claim and before further grids on this selection protocol: (1) per-phase P1-P4 VALIDATION and TEST tables for '
                        'both tasks; (2) the static_columns and mask_static_columns of feature_layout.json with definitions (any column '
                        'computed over the whole window or identifying the course makes the VALIDATION prefix evaluation optimistic, '
                        'because validation prefixes truncate dynamic columns only); (3) TEST P1 by SEEN/UNSEEN course subgroup and '
                        'STRICT/OVERLAP; (4) per-class metrics at TEST P1 (constant majority prediction?); (5) if statics leak, '
                        'materialise VALIDATION prefix views like TEST and re-select checkpoints',
     'stage': 'now; blocks LO W1/P1 claims and the F2 grid launch until explained',
     'status': 'CLOSED 2026-10-25 as explained: every diagnostic of the list exists (ablation P1 table, static-only probe, '
               '1,632-cell per-phase tables, per-class and bootstrap facts, cohort audit at 68 configurations), and together they '
               'locate the W1 gap in the TEST block composition (single-offering class E; VALIDATION - TEST macro-F1 +0.14 to '
               '+0.23 on W1 against +0.01 on W2 and -0.06 on W3) rather than in the static contract (ablation) or in a prefix '
               'defect (full scan, parity); residual: the cohort numbers are not printed and item (7) (VALIDATION prefix views) is '
               'not needed because the ablation shows no static effect; the presentation rule is decision 17 (a)',
     'evidence_2026-10-16': ['LO W1 per-phase table delivered (REPORT_LO_FULL_E2E §4.1, 68 cells pooled): TEST macro-F1 0.3239 / 0.3249 / '
                             '0.3228 / 0.3205 and balanced accuracy 0.3522 -> 0.4346 at P1-P4; VALIDATION macro-F1 0.4629 -> 0.5508, '
                             'balanced accuracy 0.4783 -> 0.5997; the VALIDATION-TEST macro-F1 gap grows 0.139, 0.193, 0.214, 0.230',
                             'a majority predictor on C scores macro-F1 0.330 / balanced accuracy 0.333: TEST macro-F1 is at or below '
                             'that reference at every prefix while recall of the minority classes rises with the prefix (precision '
                             'collapses); pooled TEST NLL 0.095 (imputer-only) and 0.202 (balanced) exceed the prior NLL of C '
                             '(about 0.044-0.108), VALIDATION NLL is 0.012-0.03',
                             'SPLIT_REGISTRY block_classes: C holds E 1,000 (one offering) and G 525; B holds E 252 and G 532; A holds '
                             'E 655 and G 4,720; the single-offering cell was registered on 2026-10-01 (known_cells)',
                             'the P4 gap rules out validation-prefix truncation as the main mechanism (no truncation at P4); the '
                             'composition of C and a possible offering-identity signal in the 15 static fields remain',
                             'the team reports that earlier SEEN/UNSEEN and STRICT/OVERLAP cohorts were matched by label order, not '
                             'by enrollment hash, so the cohort tables (UNSEEN macro-F1 0.5191 with no E present) are not usable yet',
                             'CQ: no per-phase VALIDATION/TEST table delivered; pooled VALIDATION-TEST macro-F1 gap is 0.011-0.013 and '
                             'the TEST prefix views scan clean (0 non-null future cells in 122.8M at P1), 13 static fields, '
                             'split_rule_version present in historical layouts (constant), timeline_source and '
                             'window_duration_seconds named as suspects by the team'],
     'tools_2026-10-17': ['team: tools/audit_prefix_validation_alignment.py (static list + dispositions, prefix mask on row group 0 '
                          'of the first file, static parity P1-P4, cohorts joined by row order with a label-sequence guard, W1 '
                          'P1-P4 table, present-class macro-F1) and tools/export_w1_phase_validation_test_table.py (no per-class)',
                          'review patch 2026-10-17b: STATIC_FEATURE_CONTRACT in the registry, --full-scan, dual macro-F1 convention, '
                          'tools/probe_static_only.py, tools/audit_static_columns.py --allowlist-from-registry'],
     'progress_2026-10-19': ['done: (2) static-only probe for LO and CQ W1/V0; (4) definitions and audit flags of the 15 LO and 13 CQ '
                             'fields (all catalog fields OFFERING_ATTRIBUTE; primary_risk_set constant/unlisted in CQ; split_rule_version '
                             'constant 1 in all 204 LO layouts); (6) CQ TEST prefix full scan 538,608 rows per phase, 0 non-null; LO full '
                             'scan 409,508 rows per phase, 0 non-null; CQ W1/V0 CPU replay prefix-safe and selection rule 153/153',
                             'tool ready: hash-matched cohorts (salted enrollment hash) in audit_prefix_validation_alignment.py; not yet run',
                             'not done: (1) ablation, (3) per-class per-phase tables for B and C, (5) hash-matched cohort tables, (7)'],
     'progress_2026-10-21': ['(1) ablation run (4 exploratory cells), numbers not delivered (PENDING_DECISIONS[20])',
                             '(5) hash-matched SEEN/UNSEEN x STRICT/OVERLAP done for the 4 ablation runs with their own salt; the 204 '
                             'historical LO runs still need the original salt', 'prediction-grain scan of 1,632 LO prediction files '
                             '(null/duplicate hash, invalid strict flag) done; result in the undelivered LO report',
                             'still missing: (3) per-class per-phase tables for B and C of the historical runs (the CQ R3 export shows '
                             'the format), (7)'],
     'remaining': ['(1) static ablation: retrain LO W1 V0 and V8 (LSTM) with the 15 static fields removed and evaluate B and C per phase '
                   '(about 10 L4-minutes); if VALIDATION falls to the TEST level the statics carry offering identity',
                   '(2) static-only probe: logistic regression on the static fields only, fit on A, scored on B and C per class',
                   '(3) per-window x per-phase x per-class (E, G, I/D) tables for B and C, all families, at least V0 and V8 (G is the '
                   'controlled comparison: 532 vs 525 rows)',
                   '(4) definition, source and availability time of every static field (CQ 13, LO 15) and their offering-level '
                   'constancy (tools/audit_static_columns.py in review patch 2026-10-17)',
                   '(5) SEEN/UNSEEN and STRICT/OVERLAP re-matched by salted enrollment hash for B and C',
                   '(6) CQ W1 per-phase VALIDATION/TEST table (same export as LO §4.1)',
                   '(7) only if (1) shows a static effect: materialise VALIDATION prefix views like TEST and re-select checkpoints']},
    {'id': 16, 'check': 'CQ F1 VastAI cells before any CQ family table: run manifests of the 153 cells show batch_size / micro_batch_size '
                        '/ accumulation_steps (resource table says 512, registry 2048; PENDING_DECISIONS[16]); the diff between runner '
                        'sha256 65680d06... (LSTM/GRU) and 3b19dfb8... (BiLSTM) is disclosed or BiLSTM rerun; CQ RNN either rerun on '
                        'VastAI with the same runner or the Modal-vs-VastAI equivalence shown on a CQ cell; NVML power estimates of '
                        'the runs located (energy_records 0 although the launcher samples at 1 Hz) and labelled ESTIMATED',
     'stage': 'before CQ F1 numbers enter 03_claims',
     'status': 'CLOSED 2026-10-21: runner sha256:10cd38a2... reported for all 153 contracts; CQ RNN rerun on VastAI (51 cells, '
               'separate receipt, matched historical layout) agrees with Modal to 1e-4; NVML 204/204; the closure-table wording fixed '
               '("thay thế các diễn giải cũ về coverage tài nguyên"); the two runner revisions are kept as two receipts, which is the '
               'documented form the rule allows'},
    {'id': 17, 'check': 'metric conventions in code vs registry: macro_f1 with an absent class (code zero_division=0, registry NULL / '
                        'CLASS_ABSENT), the convention used by the slice audit (UNSEEN_COURSE W1 has no E), and '
                        'n_checkpoints_within_margin (always 2 because selection_margin = best - second best); fix or document before '
                        'the slice tables are read',
     'stage': 'before slice tables are read',
     'status': 'OPEN 2026-10-19 (low): both conventions are now reported by the audit (adopted in 6fd6315) and the slice facts use the '
               'parent contract, so ALL equals the main metric (verified in the CQ 19/10 tables: 0.6768 / 0.6783 / 0.6749 both ways); '
               'the registry/code mismatch (NULL vs 0 for an absent class in the main macro-F1) remains and matters only for slices'},
    {'id': 18, 'check': 'static feature contract: model.data.fit_layout selects every numeric non-phase column of the TRAIN frame that is '
                        'not an identity or the label; an explicit allowlist per task (name, definition, source table, time of '
                        'availability <= P1 cutoff, offering-level or enrollment-level) is written to the registry and '
                        'tools/audit_static_columns.py --strict passes on the W1 V0 TRAIN frame of both tasks; constant columns '
                        '(primary_risk_set, historical split_rule_version) and offering attributes are either allowlisted with a '
                        'justification or excluded',
     'stage': 'before any further model grid (F1 reruns, F2)',
     'status': 'OPEN 2026-10-19: LO contract in the registry (adopted), CQ contract provisional (CQ/registries.py, 13 fields incl. '
               'primary_risk_set REVIEW), audit --allowlist-from-registry --strict passes on LO W1/V0 with the current fit_layout '
               '(14 fields, 0 unlisted); still missing: fit_layout enforcement, point-in-time attestation of the catalog fields, '
               'PENDING_DECISIONS[19] and [20]',
     'status_2026-10-25': 'LO closed in code (c225961): contract v2 with 13 IN_TENSOR fields, fit_layout rejects any unregistered '
                          'numeric static for LO, test_registry_allowlist_matches_the_static_feature_contract updated; CQ still '
                          'provisional (no fit_layout allowlist, primary_risk_set REVIEW); the PatchTST pilot ran on the current CQ '
                          'layout (hash f99c3d32..., 13 statics per the prefix audit) while the recurrent grid used the historical '
                          'layout, so the two CQ static lists must be printed side by side before F1 and F2 are compared'},
    {'id': 19, 'check': 'audit code behind reported evidence is in the repository: tools/vastai_audit_w1.py (both upload scripts copy it '
                        'to the instance), the cq_full_prefix_static_audit_20261017 and rnn_prefix_audit_20261017 scripts of the CQ '
                        'appendix, the report generator that merges CQ ingest_ids, and the exact launcher invocation of the 153 CQ F1 '
                        'cells; the test suite passes at the reviewed commit (2 failures at d449831)',
     'stage': 'before the CQ appendix numbers are cited',
     'status': 'CLOSED 2026-10-21: report generators, maintenance scripts, closure and audit scripts committed in eb80516 (116 files); '
               'launchers run_cq_gru_bilstm_2048_vastai.sh and vastai_run_cq_rnn_historical_layout.sh committed; tests 35 pass'},
    {'id': 20, 'check': 'CQ phase trend inside windows (REPORT_CQ 19/10 §4, batch 2048): mean AccTEMPO over the 17 pipelines falls from P1 '
                        'to P4 by 0.110-0.119 in W2 for all three families and both pipeline groups (e.g. LSTM 0.678 -> 0.568), by '
                        '0.027-0.030 in W3, and rises by 0.023-0.024 in W1. Because AccTEMPO carries s_ent, which falls as predictions '
                        'become confident, the trend cannot be read as performance until macro-F1, balanced accuracy and s_ent are '
                        'tabulated at the same window x phase grain (tools/export_window_phase_tables.py), with per-class recall per '
                        'phase and the STRICT/OVERLAP split per phase for W2',
     'stage': 'before any early-prediction (P1 -> P4) statement for CQ',
     'status': 'CLOSED 2026-10-21 (explained): the R3 window x phase tables show macro-F1 and balanced accuracy rising in every '
               'window (W1 +0.16, W2 +0.01..+0.03, W3 +0.07) while s_ent falls 0.23-0.35, so the AccTEMPO decline is the s_ent '
               'term; the consequence lives in PENDING_DECISIONS[18]. W2 STRICT share rises 84.9% -> 90.6% P1 -> P4 (composition '
               'shift noted, not the driver)'},
    {'id': 21, 'check': 'slice facts: STRICT + OVERLAP confusion matrices add up to ALL in every cell (review patch 2026-10-19 asserts it '
                        'in _slice_rows) and ALL equals the sanity facts (team ingest check); the CQ 19/10 means show STRICT 0.74 and '
                        'OVERLAP 0.75 macro-F1 both above ALL 0.71 for every family, which a partition allows only through class '
                        'composition and must be confirmed per cell',
     'stage': 'before slice tables are cited',
     'status': 'CLOSED 2026-10-21: tools/audit_strict_overlap_partition.py run on 1,224 cells of the three families (0 violations) and '
               'on the RNN bundle; ids unique, flags binary; the STRICT/OVERLAP > ALL pattern is therefore class composition'},
    {'id': 22, 'status_2026-11-20': "the confirmation asked on 16/11 (no OTHER_RELEASE manifest feeds a delivered facts package) is reported as 'not confirmed' in the 20/11 report: the check stays CLOSED on the ledger content, the confirmation is asked again", 'status_2026-11-16': 'CLOSED 2026-11-16: the ledgers of both tasks are on the Drive (CQ/L0_registry/release_identity/cq_release_identity_ledger_20261116, LO/.../lo_release_identity_ledger_20261116; copied): CQ 301 manifests = CURRENT 78, UNVERSIONED_S2_PARENT 36, OTHER_RELEASE 187; LO 256 = 73, 36, 147; no UNMATCHED, ABSENT or UNREADABLE; LEGACY_WITH_LINEAGE 0; both identities recorded (identities_differ true). Label reading by the writing side: CURRENT = the locked release, OTHER_RELEASE = manifests of other releases on the Volume (imputation-v1 layer, historical runs), UNVERSIONED_S2_PARENT = S2 parents tolerated by design; one confirmation requested from the team: no OTHER_RELEASE manifest feeds a delivered facts package', 'check': 'data_release_id semantics (eb80516): release_inventory now excludes materialization_lineage_* from the identity '
                        'and the Modal exporters select runs by identity equality, so manifests recorded while the sidecar was part of '
                        'the inventory carry a different id; required: a ledger per locked release with both identities and a scan of '
                        'every run manifest (tools/release_identity_ledger.py, review patch 2026-10-21), and exporters that accept the '
                        'legacy identity by ledger entry rather than by recomputation; no UNMATCHED manifest may remain',
     'stage': 'before the next export from Modal L2 (CQ RNN Modal reference, imputation facts)',
     'status': 'OPEN 2026-10-23: code closed in 7886a85 (release_identity_aliases; every CQ exporter classifies CURRENT / '
               'LEGACY_WITH_LINEAGE and raises on an unknown identity; Modal ledger app fails on UNMATCHED / ABSENT / UNREADABLE; '
               'canonical S_leak overlay refuses inconsistent duplicates across identities); evidence pending: the ledger.json per task '
               'with its scan counts, including the UNVERSIONED_S2_PARENT count the team tolerates by design (S2 parents predate '
               'data_release_id and are reached only through S3 manifests); residual: imputation_app.audit_imputation_runs filters '
               'silently instead of raising (low)'},
    {'id': 23, 'check': 'CQ F1 seed-42 numbers into 03_claims: copy the R3 export (cq_family_pipeline_window_phase_metrics, '
                        'cq_family_window_phase_mean, cq_train_time_energy_family_pipeline, cq_resource_per_run, CSV + Parquet with '
                        'receipt ids and runner sha) into input/results/GD1_CQ_V2_2_clean_r1/ with a README naming the two receipts, '
                        'the historical static layout of all 204 runs (split_rule_version constant), the ESTIMATED energy label and '
                        'the averaging rules; then every table in the paper cites those files',
     'stage': 'before any CQ number enters a draft',
     'status': 'OPEN 2026-10-23: the R4 export (cq_recurrent_allfamilies_grid_r4_20261023: 1,632 cells with the full sanity contract, '
               'acctempo_m4, w2_strict_share, per-class and bootstrap long tables, QA23 linkage) supersedes R3 and agrees with it to '
               '1e-4; still not copied to input/results/GD1_CQ_V2_2_clean_r1/ and not in the repository; the README must now also name '
               'the M4 formula and the QA23 label-construction note',
     'status_2026-10-28': 'OPEN: the 28/10 consolidated CQ report reprints R4 unchanged (verified to 1e-4 on 68 family x pipeline '
                          'means, RNN mean-17 window x phase and recurrent V0 means) and adds the 816-cell appendix, the label counts '
                          'per block (equal to SPLIT_REGISTRY blocks A-G) and per-class bootstrap CIs; still nothing in '
                          'input/results/'},
    {'id': 24, 'check': 'PatchTST V0 pilot (2026-10-23) before any F2 number is quoted: (1) the three run manifests show '
                        'model_revision patchtst_channel_independent_v2_1_math_sdp, batch 2048 = 4 x 512, static_ablation none, '
                        'run_purpose PRIMARY_GRID, one static_layout_policy / reference layout / runner commit for all three windows '
                        '(review patch 2026-10-23 makes the report builder fail otherwise); (2) train_history of each run with the '
                        'selected epoch marked (W3: epoch 1 of 6); (3) SEEN/UNSEEN x STRICT/OVERLAP slices of the pilot next to the '
                        'recurrent V0 slices (W2 VALIDATION - TEST +0.11 at P4); (4) elapsed time and NVML energy per run for C3; '
                        '(5) comparisons only like for like: PatchTST V0 against the recurrent V0 cells, never against the mean of 17 '
                        'pipelines printed in the report; (6) the canonical S_leak of the pilot equals the recurrent V0 values (the '
                        '12 TEST cells average 0.2547, the constant of the 19/10 report)',
     'stage': 'before the F2 grid launch (decision 22)',
     'status': 'OPEN 2026-10-25: (1)-(6) delivered in the regenerated 23/10 report (sections 8b-8e, posthoc identity receipt): '
               'revision, 2048 = 4 x 512, runner 7886a856, NVML, elapsed and kWh, epoch history, cohorts, V0-vs-V0 table; residual '
               'before any F2 number is quoted: static_layout_policy current (not the recurrent historical layout), the files are '
               'not in input/results/, and the pilot manifests predate the release-identity fields (POSTHOC receipt, accepted as '
               'labelled)'},
    {'id': 25, 'check': 'LO seed-42 export into input/results/GD1_LO_V3_1_clean_r1/ (the LO counterpart of check 23): the grid chosen '
                        'under decision 24 at the R4 grain (1,632 cells with M3, M3^(cal), S_san+ v1/v2, six components, per-class, '
                        'bootstrap, slices, checkpoint selection, resources with the energy label), a README naming the ingest id, '
                        'the runner commit per family, the RNN W1/V0 repair, the static contract of the grid (historical 15 fields or '
                        'v2 13 fields), the single-offering flag of W1 block C, the Radius-SMOTE fallback rates per class, and the '
                        'registry pipeline mapping (V1 MEDIAN, V5 MEAN, V3 SASMOTE, V4 RADIUS_SMOTE); plus the equivalence table '
                        'replay vs historical for all four families (BiLSTM shown to 1e-4)',
     'stage': 'before any LO number enters a draft', 'status': 'OPEN 2026-10-25',
     'status_2026-10-28': 'OPEN: the candidate grid is now the v2-contract grid (decision 24 (b), decision 20 (a-v2)): one runner '
                          '(b0e5ae1) for 204 cells, so the per-family runner column and the RNN W1/V0 repair note fall away; the '
                          'README must instead name contract v2 (13 fields), the closure archive sha256, the cohort audit root and '
                          'the salt policy (the v2 grid cannot be hash-joined with the historical grid); the comparison table v2 vs '
                          'r3 becomes a descriptive appendix (family means within 0.007), not an equivalence claim; nothing in '
                          'input/results/ yet'},
    {'id': 26, 'check': 'parallel F2 execution (decision 23): one shard plan per ingest (tools/f2_shard_plan.py: every remaining cell '
                        'assigned to exactly one instance, plan sha recorded), every instance started from the same runner commit and '
                        'pinned image, --static-layout-policy explicit and equal to the pilot, per-seed input trees built from the S2 '
                        'artefacts of that seed, train_history.parquet archived for every cell, and the ingest asserts completeness '
                        '(51 cells per task x seed), uniqueness and uniform execution before any F2 table is read',
     'stage': 'before the F2 grid launch and at its ingest',
     'status': 'OPEN 2026-10-27: shard plan, launcher and verify adopted (af079d8); training-protocol fields added to the contract, '
               'the ingest assertion and the verifier (review patch 2026-10-27); the registered protocol must be signed by the author '
               '(decision 23) before the first shard starts; per-seed input trees for seeds 43/44 still missing',
     'status_2026-10-28': 'OPEN: protocol provenance adopted (651b458) and locked by the team (29da3b2); remaining before the first '
                          'shard: author signature of decision 23, decision 25 (the pilot cells and the shards cannot share one '
                          'ingest: review patch 2026-10-28 makes the plan show the reused commits and the ingest assert one '
                          'runner_git_commit), check 27 closed with named commits, and the S2 trees for seeds 43/44 before any '
                          'seed-43/44 shard',
     'status_2026-11-03': 'PARTLY CLOSED for V0-V6: decision 23 signed (01/11), decision 25 closed, one runner_git_commit 29da3b2 and one layout '
                          'hash over the 21 cells, every run manifest prints 2048 / 512 / 4 and the protocol fields, train_history present for '
                          'the V0 runs (V1-V6 histories in the verified archives, not exported); still missing for V7-V16: the shard plan sha in '
                          'the package (the facts package has no plan record; V7 stopped before completion), the ingest assertion report of '
                          'completeness (51 cells) and uniform execution over the final 51-cell set, the histories of V1-V16 as facts; '
                          'seeds 43/44 wait for decision 32'},
    {'id': 27, 'check': 'training-loop equivalence after 044d6c7: train_shared_checkpoint now routes every optimiser step of every '
                        'family through optimizer_step (explicit GradScaler.unscale_, gradient division after unscaling, optional '
                        'warm-up and clipping); with the registered protocol the arithmetic is the same up to floating-point order, '
                        'which is not the same as bit-identical. Before any further primary grid is trained with the new code (LO v2 '
                        'replay, seeds 43/44, F2), replay one completed recurrent cell per task (CQ W1/V0/RNN, LO W1/V0/RNN, seed 42) '
                        'with the 044d6c7+ runner and compare VALIDATION/TEST prediction checksums, metrics and best_epoch with the '
                        'archived run; a difference larger than the registered tolerance means the old and new grids are different '
                        'code revisions and must be labelled as such',
     'stage': 'before the next primary grid', 'status': 'OPEN 2026-10-27',
     'status_2026-10-28': 'OPEN, two paired replays delivered with delta 0: (i) CQ/W1/V0/RNN/seed 42 (cq_rnn_equivalence_20261028, 8 '
                          'canonical facts per side: AccTEMPO, six sanity components, macro-F1, balanced accuracy, three recalls; '
                          'maximum absolute delta 0; the report names neither the reference nor the current runner commit); (ii) '
                          'LO/W1/V0/RNN/seed 42 (tools/audit_lo_paired_replay_20261028.py: baseline b0e5ae1 vs replay 29da3b2, both '
                          'AFTER 044d6c7, epoch 4 both, exact equality of labels, predictions and probabilities on 8 split x phase '
                          'files). (ii) proves determinism of the backend, not loop equivalence. The check closes when the CQ '
                          'receipt shows a reference run trained BEFORE 044d6c7 (the archived R4 cell, runner 5b14052/7886a85 era) '
                          'against a current run trained AFTER it; review patch 2026-10-28 prints both commits and the verdict in '
                          'the report. Note that the LO v2 grid was trained entirely after 044d6c7, so it is internally consistent '
                          'whatever the outcome; the outcome decides whether CQ F1 (before) and the F2 / seed-43/44 grids (after) '
                          'may be labelled one code revision',
     'status_2026-10-29': 'CLOSED FOR THE SHARED LOOP, subject to one receipt field: matched historical replay CQ/W1/V0/RNN/seed 42 '
                          '(cq_rnn_matched_historical_20261029): baseline trained 2026-10-20 with the historical layout (hash b747da1e...), '
                          'replay at 29da3b2, layout equal, epoch 2 both, labels / predictions / three probabilities equal on 175,689 '
                          'VALIDATION and 178,095 TEST enrollments x P1-P4 (delta 0). The baseline manifest records no runner_git_commit; '
                          'its runner_sha256 identifies the commit interval (tools/identify_runner_commit.py: a 20/10 runner hashes to '
                          '83c5056..eb80516, before 044d6c7) and must be printed in the receipt instead of the timestamp argument. '
                          'PatchTST accumulation path: exact by the power-of-two argument (decision 25 analysis); the one-epoch replay of '
                          'decision 25 is its empirical receipt. The LO replay (b0e5ae1 vs 29da3b2) remains a determinism check',
     'status_2026-10-31': 'CLOSED 2026-10-31 for the shared loop: the baseline runner hash 4077c6c9... is the CRLF rendition of '
                          'tools/vastai_train_shared.py @ eb80516 (reproduced by the writing side and by the team), i.e. runner content committed '
                          '2026-10-21, five days before 044d6c7; with the bit-exact matched replay (353,784 enrollments x P1-P4, epoch 2 both) the '
                          'recurrent path of the shared loop is equivalent before and after 044d6c7. The team\'s residual caveat (the commit of the '
                          'working copy is not recorded, model/shared_phase.py is not hashed) is recorded as such. PatchTST accumulation path: '
                          'exact by the power-of-two argument; the one-epoch replay of 2026-10-31 shows determinism of the F2 runner; no pilot '
                          'comparison is needed any more because the F2 grid will consist of 51 cells from one runner (decision 25)'},
    {'id': 28, 'check': 'report and receipt provenance (2026-10-28): the delivered REPORT_CQ_CONSOLIDATED_EVIDENCE_2026-10-28_DAY_DU and '
                        'REPORT_LO_STATIC_V2_CONSOLIDATED_EVIDENCE_2026-10-28_DAY_DU differ from the output of the builder committed '
                        'in e0ae433 (sections 1, 7, 8 reworded; appendix sections 10-13 with 816-cell tables, label distribution, '
                        'support and bootstrap CI, STRICT/OVERLAP and SEEN/UNSEEN slice means are produced by no script in the '
                        'repository), and no tool in the repository writes cq_rnn_equivalence_20261028/canonical_facts_comparison.json. '
                        'Required before any number of the pair is quoted: the exact builder (with the appendix) and the receipt '
                        'writer committed, the receipts (CQ and LO replay, prefix audit, cohort summaries, closure receipt) delivered '
                        'with the package, and the report regenerated from the committed builder so that file and code agree',
     'stage': 'before any number of the 28/10 reports enters a draft', 'status': 'OPEN 2026-10-28',
     'status_2026-10-29': 'OPEN: the 29/10 CQ report (section 14, matched replay) and the R20 LO report were produced by builders and '
                          'tools that are still not on origin/main (e0ae433); the R4 and LO v2 metric tables of both reports are byte-identical '
                          'to the 28/10 versions (verified cell by cell)',
     'status_2026-10-31': 'PARTLY CLOSED: the appendix builder (append_complete_cq_lo_evidence_20261028.py, 93dcf1e), the consolidated builder '
                          'with replay provenance, the matched-replay audits and the R21 staging tool are on origin/main (3bdb8b6); still missing '
                          'in the repository: the tool that wrote cq_rnn_equivalence_20261028/canonical_facts_comparison.json (superseded by the '
                          'matched replay) and the matched-replay script itself for CQ (only its receipt path is referenced); the reports of '
                          '31/10 (V0 current, performance/replay, static provenance) were not delivered to the author'},
    {'id': 29, 'check': 'cohort slice tables (LO appendix section 13, SEEN/UNSEEN x STRICT/OVERLAP means over 68 configurations): '
                        'single-class slices print balanced accuracy 1.0 or 0.97 next to macro-F1 0.333 (e.g. W1/P4 UNSEEN OVERLAP n = '
                        '873, W2/P2 UNSEEN OVERLAP n = 62, W1/P1 SEEN STRICT n = 16,145), and three empty slices (W2/P3, W2/P4 and '
                        'W3/P4 UNSEEN OVERLAP, n = 0) print blank metrics with "Cells 68" instead of SLICE_EMPTY. Required: a '
                        'classes_present column (or n per class), NULL for balanced accuracy and macro-F1 when fewer than two classes '
                        'are present, SLICE_EMPTY for n = 0 (SPLIT_REGISTRY.temporal_slice rule), and the UNSEEN share per window x '
                        'phase next to the means; the CQ appendix has STRICT/OVERLAP only, the CQ SEEN/UNSEEN cohort audit of the full '
                        'grid is still missing',
     'stage': 'before any slice number enters a draft', 'status': 'OPEN 2026-10-28',
     'status_2026-10-29': 'CLOSED 2026-10-29 in the R20 LO report: status column (79 OK, 14 ONE_CLASS, 3 SLICE_EMPTY of 96 slices), '
                          'classes min-max, metrics blank below two classes, UNSEEN share per window x split (TEST 13.2 / 12.3 / 14.2 %, '
                          'VALIDATION 23.7 / 14.0 / 6.6 %); residual (low): two-class slices with a handful of minority rows still print '
                          'balanced accuracy far above macro-F1 (W1/P1 SEEN STRICT n = 16,145: 0.975 vs 0.326) without n per class, so the '
                          'small_support flag of METRIC_DEF should accompany every slice row'},
    {'id': 30, 'check': 'Drive archive versus the paper package (2026-10-29): README_STORAGE_TREE_CQ_LO_20261029 describes '
                        'gdrive:Jobs/{CQ,LO}/organized_moved_20261029 (L0, L1 S1/S2/S3, L2 fact_exports / audits_and_evidence, archives, '
                        'receipts; no L3). Required before any number is quoted: a manifest that maps every package of checks 23-25 '
                        '(R4 CQ export, LO v2 export with four audits, closure archive sha256, cohort and prefix audits, the two replay '
                        'receipts with runner commits or hashes, D23 histories, pilot manifests, ledger.json, QA23) to its Drive path and '
                        'sha256, and the copy of those files into input/results/ (the Drive connector of the writing side sees the root '
                        'folder only). The README itself is consistent with the registry: S1 = 5 imputers x 3 windows per task, S2 = 12 '
                        'balanced pipelines x 3 windows (V2-V4, V6-V8, V10-V12, V14-V16), seed 42 only; S2 for seeds 43/44 absent',
     'stage': 'before any number enters a draft', 'status': 'OPEN 2026-10-29',
     'status_2026-10-31': 'OPEN, half done by the team: tools/stage_r21_evidence_20261031.py stages 151 files with a sha256 manifest '
                          '(R4 CQ facts, LO r2 historical facts, LO v2 audits of four families, D23 histories, S2 manifests, QA23 summaries, prefix '
                          'audits, replay receipts, label consistency) into CQ/resuilt/input/results/R21_evidence_20261031 on the team disk; the '
                          'package has not been transferred to the author; the writing side filled input/results with report-derived CSV packages '
                          'and a placeholder README for R21_evidence (decision 27)'},
    {'id': 31, 'check': 'R21_evidence_20261031 on arrival: (1) manifest.json sha256 of every file recomputed; (2) CQ/facts equals the R4 export '
                        '(cq_family_pipeline_window_phase_metrics.parquet, 1,632 rows) and the report-derived CSV of GD1_CQ_V2_2_clean_r1_report_derived '
                        'to 1e-4 on every printed metric; (3) LO/audit_seed42 sanity_components of the four families (408 rows each) equal the '
                        'report-derived LO CSV to 1e-4; LO/facts is labelled historical r2 and never read for a paper table; (4) D23 histories '
                        'evaluated with build_cq_d23_configuration_report (criterion table); (5) the 36 S2 manifests name seed 42 and the registered '
                        'balancers; (6) 03_claims section A updated with the sha256 and the mapping report-derived -> export',
     'stage': 'on receipt of the team package; before any report-derived number is replaced', 'status': 'OPEN 2026-10-31',
     'status_2026-11-02': 'PASSED for the two F1 base tiers from the shared Drive (decision 28): R4 export 14/14 files and the four LO static-v2 '
                          'audits 28/28 files copied into input/results with sha256; grid structure, formulas (2e-16) and the report-derived '
                          'tables (<= 5e-5) check; LO facts labelled; D23 histories still not evaluated; S2 manifests not yet read [Ra_soat_tien_do_2026-11-02 §2]',
     'status_2026-11-03': 'PARTLY CLOSED further: 47 small files of the 12 Drive packages of 02-03/11 equal their sha256sums entries; the report '
                          'tables of BAO_CAO_CQ_PATCHTST_V0_V6_2026-11-02 equal the facts files (21 run rows: epoch and elapsed hours; cost per '
                          'pipeline and total 181.81 h / 66.91 USD; 21 resource rows: train and elapsed hours, kWh, NVML samples; the R4 '
                          'appendix means per family ALL slice; the Radius fallback mean/min/max per window x class); V0 cells equal the R21/R22 '
                          'facts (W2 P4 validation 0.8334 / test 0.6655; W2 TEST M3 0.5811 -> 0.4954); the 36 S2 manifest hashes are listed '
                          '(ledger_inventory.json) with the ledgers not rehashed; remaining: the per-cell files (sanity_components, '
                          'evaluation_slices, per-class, bootstrap, cohort status; LO per-cell export; reconciled CQ slices; cell_flags) after '
                          'the sync of decision 31, and (6) the 03_claims mapping of the new packages (done in v0.8 for the small files)',
     'status_2026-11-09': 'PASSED for the three full-grid facts packages of 09/11 on their small and medium files: cq_patchtst_v7_v16_full_facts_20261109 '
                          '(sanity_components.csv, cohort_slice_status.csv, checkpoint_selection.csv, resource_per_run.csv, summary.json, README.md, '
                          'source_inventory.json, sha256sums.txt), lo_patchtst_v0_v16_full_facts_20261109 and cq_mantis_v2_v0_v16_full_facts_20261109 '
                          '(the same minus source_inventory): 19 files equal their sha256sums entries; the six report tables of '
                          'BAO_CAO_PATCHTST_MANTIS_CQ_LO_2026-11-09 equal the facts at three decimals (440 values, 0 mismatches; the V0-V6 rows equal the '
                          '03/11 report-derived means); m13_inputs_phase1_20261108: 10 files (README.md, s0_profile/{s0_profile.parquet, summary.json, '
                          's0_profile_README.md}, z_m/{z_m.csv, z_m_param_counts_by_layout.csv, README.md}, f0_cq_partial_triad/{f0_cq_partial_triad.csv, '
                          'f0_manifest_databricks.json, README.md}) equal sha256sums_all.txt (29 verified files in all); not yet fetched: evaluation_slices, metrics_per_class, '
                          'bootstrap_metrics_per_class, the cohort_audit sub-folders, the M-05/M-06/M-07/M-09/M-10 packages of 07-08/11 and '
                          'FACTS_OF_RECORD_sha256.txt; the _drive_mirror sync of decision 31 has not happened'},
    {'id': 32, 'check': 'probability-metric convention (tools/check_cq_r4_probability_metric_definitions_20261103.py and the reconciled slice export): '
                        'model/metrics clips probabilities at 1e-7, the audit at 1e-12, so NLL / Brier / ECE / PR-AUC of the same cell differ beyond '
                        '1e-6 between the two code paths; the 03/11 export copies ALL from immutable R4 (model convention), recomputes STRICT / '
                        'OVERLAP from saved predictions with the model convention (ALL re-check within 1e-6, PASS_BY_SOURCE) and keeps the audit '
                        'convention inside s_cal and the S_san+ v2 composites. Required before any s_cal / M3^(cal) number is printed next to a '
                        'model NLL or Brier: (1) one clipping constant registered in METRIC_DEF (recommendation: the model convention 1e-7, '
                        'the audit recomputed once for s_cal with it, or the difference bounded per cell and shown to be below the printed '
                        'precision); (2) every export column named with its convention (audit_* columns already exist in the reconciled file); '
                        '(3) the same check for LO and for the PatchTST facts package',
     'stage': 'before any calibration or probability metric enters a draft table', 'status': 'OPEN 2026-11-03'},
    {'id': 33, 'check': 'report integrity of BAO_CAO_CQ_PATCHTST_V0_V6_2026-11-02 (sha256 1aa3c100...): (1) the appendix "Phu luc bo sung CQ: facts '
                        'R4 va audit RadiusSMOTE (03/11/2026)" has every Vietnamese diacritic replaced by "?" in the docx XML (encoding defect of '
                        'the appendix builder; content readable from context); (2) the report copy inside the facts package (sha256 6ebf1abe...) '
                        'is an earlier rendition than the delivered file; (3) the hourly price 0.368 USD/h behind the cost table is hard-coded in '
                        'tools/report_cq_patchtst_v0_v6_20261102.py and not sourced in the report (the exchange rate 25,990 VND/USD is sourced: '
                        'Vietcombank 02/11/2026 23:00); (4) n_checkpoints_within_margin = 2 in all 21 rows because selection_margin is the gap to '
                        'the runner-up (tautological column; V3/W3 margin 4.2e-5 = near tie); (5) the per-class tables print "recall [CI]" where '
                        'the R4 convention prints the bootstrap estimate (note (ii) of the 02/11 request list). Required before any number of '
                        'the report is quoted: regenerated appendix in UTF-8, the final docx re-staged in the package, the price source and date '
                        'in the cost section, the margin column renamed (gap_to_runner_up) or dropped, the recall column named',
     'stage': 'before any number of the 02/11 report enters a draft', 'status': 'OPEN 2026-11-03'},
    {'id': 34, 'check': 'R4 provenance for T1-EX-07 (cq_r4_provenance_20261103_DRAFT, status DRAFT_PENDING_RNN_RECEIPT_AND_SLICE_RECONCILIATION): the '
                        'inventory hashes the 14 R4 files and records data_release_id sha256:8db2b1d3..., but the 153-run ingest receipt covers '
                        'LSTM / GRU / BiLSTM only (runner sha256 10cd38a2...) and the RNN ingest (51 cells, historical layout, '
                        'cq_rnn_historical_layout_batch2048_seed42_20261020) has no receipt in the package; the slice reconciliation is now done '
                        '(check 32) but the RNN receipt and runner commit are still to be confirmed. Required: the RNN ingest receipt (runner '
                        'sha256 and commit, equivalence receipt of the matched replay of 29/10) added to the inventory, the README of T1-EX-07 '
                        '(aggregation rule, ESTIMATED label, V0-V16 mapping, backend, registry revision) and FACTS_OF_RECORD.md at the Jobs root '
                        '(M-09); until then the CQ F1 package in input/results is "official facts, provenance draft"',
     'stage': 'before the CQ F1 numbers are declared final (T1-EX-07)', 'status': 'OPEN 2026-11-03'},
    {'id': 35, 'check': 'seed policy stated in one way in four places before any seed-43/44 cell: LO/registries.py EXPERIMENT_SEEDS, '
                        'modal_jobs/README.md, modal_jobs/run_model_grid.ps1 default and tools/vastai_train_shared.py seed check, all equal to '
                        'the outcome of decision 32, with the per-seed S2 artifacts present in the portable tree under (a) or the fixed policy '
                        'passed explicitly and recorded in every manifest under (b); the team registry entry is changed only after the author '
                        'decides; test_registry_release_alignment then asserts the decided value. Also required: the D-18 objective mapping '
                        'written into LO/registries.py METRIC_DEF v1.3 (currently only the version string changed)',
     'stage': 'before the first seed-43/44 S2 run and before METRIC_DEF v1.3 is cited', 'status': 'OPEN 2026-11-03',
     'status_2026-11-04': 'decision 32 ratified (a); the check now verifies that the four places read MATCH_MASTER_SEED',
     'status_2026-11-09': 'PASS on the code side at 421dbcd: (1) LO/registries.py EXPERIMENT_SEEDS augmentation_policy MATCH_MASTER_SEED and decision 9 '
                          '"CLOSED updated 2026-11-04 D-32"; (2) modal_jobs/README.md lines 157, 168, 277; (3) modal_jobs/run_model_grid.ps1 '
                          '-AugmentationSeedPolicy default match_model_seed (mixing with -AugmentationSeed rejected); (4) tools/vastai_train_shared.py '
                          '--augmentation-seed-policy default match_model_seed with the runtime "MATCH_MASTER_SEED violated" check; in addition '
                          'modal_jobs/model_app.py and model_preflight_app.py default augmentation_seed -1 = run seed, and '
                          'tests/test_registry_release_alignment.py asserts MATCH_MASTER_SEED; the per-seed S2 artifacts of seeds 43/44 do not exist yet, '
                          'so the second half of the check (artifacts present before any seed-43/44 cell) stays open; the D-18 objective mapping is '
                          'still not written into LO/registries.py METRIC_DEF v1.3 (only the clip convention changed, model/metrics.py)'},
    {'id': 36, 'status_2026-11-20': 'three-seed release: manifest and column dictionary copied (14,688 x 557; seed_agg 4,896; seven QA flags 1.0; 70 hashed inputs, 61 matched to files of the writing side); per-cell and per-run extracts equal the facts; the parquet tables are not yet in input/results (connector limit 10 MB), so the row count, the hashes and the QA flags are not verified directly: PARTIAL', 'status_2026-11-16': 'release p1 20261112 unchanged (M-15 p1 stands); the team re-assembly with 0.2.4 (metamodel_024_acceptance_20261113: RUN_LOG, summary.json, four column_comparison csv, copied 16/11) equals it to 2.9e-11 on common columns and fills 58 columns on the CQ F1 rows; the three-seed release and M-15 wait for seed 44', 'verified_2026-11-13': 'verified by the writing side on the copied files: release 20261112 has 3,672 rows (CQ F1 1,632, CQ F2 408, LO F1 1,632), the seven qa_* flags are 1.0, s_leak_after spread per situation <= 1.2e-16; mm_runs p1 complete in input/results (131 files), point estimates and verdicts re-derived (check 42 (e))', 'status_2026-11-13': 'release half MET per the team L2 receipt (meta_release_CQ_LO_p1_F2V0V16_20261112: 3,672 rows, seven QA flags 1.0, metamodel 0.2.2) and mm_runs half DELIVERED on 2026-11-13 (six configurations); the six mm_hypotheses.csv are in input/results with the team sha256; independent verification of the rest waits for the files (check 42)', 'check': 'phase-1 meta layer on seed 42: meta_release manifest has planned_seeds == [42], row_status counts, QA01-QA24 rates, F0 '
                        'present for CQ only (LO NOT_AVAILABLE), S0 profile and Z_M present; mm_runs has mm_config sha256, protocols '
                        'E1-A/E1-B/E2/E3 as available, objectives PAPER_COMPOSITE_CAL (primary), PAPER_PERF_AXIS, META_PRIMARY_M3_V1 '
                        '(sensitivity), SECONDARY_MACRO_F1; cluster bootstrap B = 2000; Holm',
     'stage': 'before any phase-1 meta-layer number (MM0-MM6, H1-H8) enters a draft table (M-13/M-14 by 2026-11-09, M-15 by 2026-11-12; '
              'decision 36)', 'status': 'OPEN 2026-11-04',
     'status_2026-11-09': 'inputs delivered, release not assembled: m13_inputs_phase1_20261108 (S0 48 rows, Z_M 5 rows, F0 CQ 24 rows; check 40) and '
                          'meta_phase1_preflight_20261108 (3,432 unique fact keys, per the team) exist; M-14/M-15 blocked on the team side for lack of '
                          'the metamodel package and registry (decision 40); the writing side prepared the hand-off bundle',
     'status_2026-11-10': 'release half MET, verified from the files: meta_release_CQ_LO_p1_F2V0V16_20261109 manifest planned_seeds [42], synthetic false, '
                          'n_rows 3,672 = parquet rows (CQ 2,040, LO 1,632), row_status COMPLETE 3,672, QA rates metric_recompute / pairing / '
                          'delta_identity / decomposition / v0_zero_delta 1.0 and run_level_invariant 0.0 (0.2.1 defect, see decision 40; s_eff is constant '
                          'in all 459 runs, so the registered QA24 passes), F0 CQ 2,040/2,040 rows with six *_ref columns, LO NOT_AVAILABLE_PHASE1, S0 v4 '
                          'on every row, Z_M v1 (five rows) sufficient for F1/F2, registry manifest sha256 e1fdb8e3... = registries_v1.6, acceptance_check '
                          'overall pass, four small files hash-equal to sha256sums.txt, seed-level parquet sha256 60968928... as listed; scope F2 = CQ '
                          'V0-V16 pending Q-30. mm_runs half NOT MET: no MM0-MM6 run (M-15 due 13/11); the release should be re-assembled with '
                          'metamodel 0.2.2 (QA fields) before any number is cited'},
    {'id': 37, 'status_2026-11-16': 'LO MANTIS_V2 seed-43 package delivered (51 cells, exploratory, runner commit retroactive); pilot determinism unchanged', 'status_2026-11-13': 'bench and W1/V0 pilots reported uploaded (pilot_determinism_{CQ,LO}_V0_W1_20261110 exist on the Drive, content not read); LO facts package delivered (51 cells)', 'check': 'F3 MANTIS_V2 acceptance before any F3 cell is scheduled or read: (a) pin: python -m f3_mantis.cli pin resolves '
                        'paris-noah/MantisV2 at 8f6ca35cb54ab14b120618943c6fca5ddf5a76a6 and hashes the snapshot files; mantis-tsfm 1.1.0 '
                        'installed from the wheel with sha256 accdaf2e...; the snapshot loads with a strict key-by-key check, the truncated '
                        'backbone has 2,214,144 parameters and the sha256 of its weights is written to backbone_pin.json; (b) guard and '
                        'prefix safety: the f3_mantis tests pass on the grid image (33 + the registry test), and on the L4 the prefix-k '
                        'embeddings of one VALIDATION batch are bit-identical from k-step and 4-step tensors and finite; (c) cost pilot: '
                        'f3_mantis.cli bench on the L4 with the pinned snapshot (series per second, peak memory at 4,096 series per '
                        'microbatch, largest absolute embedding value against the float16 range) and an estimate of the core (level-A passes per task x window x imputer, level-B synthetic rows) '
                        'before the core is scheduled; (d) determinism pilot: CQ/W1/V0/seed 42 and LO/W1/V0/seed 42, two runs each on the '
                        'same L4 with two fresh cache roots (no adapter or embedding entry shared by the two runs), identical adapter '
                        'digest, embedding sha256, head state, prediction/probability checksums, metrics, best_epoch and '
                        'manifest identity; (e) channel adapter fitted on the real TRAIN rows of the imputer-only cell, explained-variance '
                        'ratio of the 8 components printed per task x window x imputer, digest in every manifest; (f) export: model_name '
                        'MANTIS_V2, model_tier F3_TS_FOUNDATION, variant_role EXPLORATORY, model_revision, hparam_config_id, '
                        'input_encoding, pretrained_revision and spec digest in every fact row and manifest, a Z_M row with parameter '
                        'counts, a separate export folder never pooled with F1/F2 tables or hypothesis tests; (g) no F3 design parameter '
                        'changes after the first F3 VALIDATION or TEST metric has been read',
     'stage': 'before the F3 core (full release, phase 2; decision 36)', 'status': 'OPEN 2026-11-06',
     'additions_2026-11-09': '(h) any cache store that replaces f3_mantis.store.EmbeddingStore (the team DedupZstdStore of 07/11) keeps the identity '
                             'contract: input_sha256, adapter_digest, encoder_digest, encoder_fingerprint and backbone_pin written per entry, '
                             'ensure/reusable unchanged, lossless round-trip of every frame, file hashes verified on open; covered by a test in the '
                             'repository; (i) the 34 f3_mantis package tests are copied into tests/ of the repository and pass on the grid image',
     'status_2026-11-09': 'PARTLY MET, out of order: (a) pin satisfied in every standardised manifest of the CQ grid (repo paris-noah/MantisV2, resolved '
                          'sha 8f6ca35cb54ab14b120618943c6fca5ddf5a76a6, model.safetensors sha256 49d46d9a..., strict_load true, '
                          'weights_sha256_truncated 48f1066f..., param_count_backbone_used 2,214,144); (b) not evidenced (package tests absent from the '
                          'repository, item (i)); (c) and (d) not documented, yet the whole CQ grid (51 cells) was run and audited as EXPLORATORY on '
                          '07-09/11; (e) adapter fitted on the real parent TRAIN (refit tools of 08-09/11; explained variance not seen); (f) export '
                          'in a separate folder with model_name MANTIS_V2, model_tier F3_TS_FOUNDATION, variant_role EXPLORATORY, spec digest '
                          '0876e786... in the manifests; the checkpoint_selection.csv carries model_tier/variant_role/run_purpose only on the V1 rows '
                          '(check 39); (g) binds since 07/11; (h) DedupZstdStore reviewed by reading only; (i) open',
     'status_2026-11-10': 'LARGELY MET: (b) and (i) the 34 package tests are in tests/ and pass per the team (34/34), (h) 6 DedupZstdStore tests '
                          '(8cf8b9b); (c) reported: f3_mantis.cli bench on the L4 9,473 series per second in bf16 (no output file on the Drive); (d) '
                          'reported: CQ/W1/V0 and LO/W1/V0 seed 42 re-run from an empty cache are bit-identical to the Drive originals (probabilities '
                          'max |diff| 0.0, argmax 100 %, best_epoch 2, 7 epochs for CQ) - the two pilot reports are not on the Drive; the only pilot '
                          'file on the Drive, repro_V2_W2_seed42_20261109 (CQ V2 W2, two runs), was read by the writing side: validation and test '
                          'probabilities identical bytes, adapter digest 36ee17d9... equal, best_epoch 3, 8 epochs, metrics |diff| 0.0 (parquet file '
                          'bytes differ by metadata only); (f) labels on 51/51 checkpoint rows in the r2 package; (a), (e), (g) unchanged. Remaining: '
                          'upload the (c) bench output and the two (d) W1/V0 reports (compare_pilot_det output with the environment block)'},
    {'id': 38, 'status_2026-11-20': 'PASSED on the six seed-44 packages (max |s_leak - reference| = 0.0 on 4,896 rows) and on the three seeds together (14,688 rows, 1.1e-16)', 'status_2026-11-16': 'PASSED on the six seed-43 packages: |s_leak - reference| <= 1.1e-16 (CQ) and 9.7e-17 (LO) on 4,896 rows; s_leak_probe_auc = 1 - s_leak/2 to 1.1e-16; s_leak_source = REFERENCE_TABLE_COPY_NO_REFIT in every row (analysis_r29_2026-11-16.json)', 'status_2026-11-13_verified': 're-verified by the writing side on the copied files (check 42 (b)): identity 0.0 for the three CQ r2/r3 packages, <= 1.1e-16 for LO Mantis', 'status_2026-11-13': 'the team L2 receipts report identity <= 1e-9 for the five current facts packages (reference copied, decision 42 (a) executed); not re-verified by the writing side (files not copied)', 'check': 'leak-probe reference identity for every F2/F3 export: for each (task, window, eval_split, phase) the exported s_leak and '
                        's_leak_probe_auc equal the value of the phase-1 F1 export of the same task (CQ R4 export; LO static-v2 export) within 1e-9 '
                        'for every pipeline and model, and the audit records the probe solver, its tolerance, thread count and library versions; an '
                        'export that fails is labelled MIXED_LEAK_PROBE and its S_san+, M3 and M4 columns are not compared across pipelines',
     'stage': 'on receipt of every F2/F3 facts package and before any S_san+/M3/M4 of that package is printed',
     'status': 'OPEN 2026-11-09: PASS for cq_patchtst_v7_v16_full_facts_20261109 and cq_mantis_v2_v0_v16_full_facts_20261109 at 1.2e-5 (float32 '
               'rounding of the R4 probe; the 1e-9 tolerance applies from the next export on); FAIL for lo_patchtst_v0_v16_full_facts_20261109 '
               '(three probe fits; decision 38)',
     'status_2026-11-10': 'LO r2 PASS at 0.0 (copied from the LO reference, 408/408 cells, both columns); CQ PatchTST V7-V16 and MANTIS_V2 at 1.24e-5 '
                          'and CQ PatchTST V0-V6 at 4.98e-5 against s_leak_reference_CQ.csv (the 09/11 wording "float32 rounding" is withdrawn: the '
                          'deviation is a second fit of the probe, reproducible to 2.09e-6 with the deterministic solver); the reference tables '
                          's_leak_reference_20261109 (24 cells per task, copies of the R4 and static-v2 exports, equal to the writing-side exports '
                          'of 09/11 to 4.8e-11) and the audit assertion --s-leak-reference (ea19afa) exist; the tolerance for the existing CQ '
                          'packages and the reference-copy contract are decision 42 (Q-31)'},
    {'id': 39, 'status_2026-11-21': 'unchanged on 21/11; the cause of the 8 seed-44 CQ runs without an energy value stays unknown (the source says ENERGY_NOT_MEASURED and the hosts and images are gone, reply of 21/11 item A.10); for later grids the team samples power on each host before a grid is assigned', 'status_2026-11-20b': 'item 2 is read as ratified on 2026-11-20 (decision 47 (a), Q-36): model_tier and run_purpose on every row, variant_role on exploratory packages; the ten PRIMARY_GRID directories of seed 43 and the ten of seed 44 pass item 2 with variant_role NULL; item 1: the 8 seed-44 CQ cells without an energy value stay empty with their recorded reason (decision 49 (a)); the other items as on 20/11', 'status_2026-11-20': 'seed 44: runner commit at run time 510/510 (F1, PatchTST), Mantis retroactive with label; tier and purpose labels on every row; variant_role NULL in the ten F1/PatchTST directories (decision 47); builder commit recorded in summary.json (7c24981, written after the build); energy 604/612 cells', 'status_2026-11-16': 'seed-43 packages (12 directories): (1) runner commit 5ba9829 at run time on 510/510 F1/PatchTST cells, Mantis 6a69b7f retroactive with label; (2) model_tier and run_purpose on every row, variant_role NULL on the ten PRIMARY_GRID directories -> decision 47; (3) summary counts 408/1,224/1,224/3,672/51/1,632 in all twelve; (4) README states the audit source but its title says seed 42 in all twelve and the r2 section is duplicated (documentation defect, no numeric effect); (5) source_inventory 51 archives per F1 family and per Mantis package, 15 (CQ) / 12 (LO) PatchTST archives; (6) runner identified', 'status_2026-11-13': 'L2 ingest receipts issued by the team for nine packages: six CONDITIONS_MET, three WITH_EXCEPTIONS (retroactive runner commit) -> decision 43', 'check': 'completeness of an F2/F3 facts package before it is cited: (1) resource_per_run has runner_git_commit, elapsed_seconds, '
                        'train_seconds and NVML energy for every run (LO PatchTST: runner_git_commit null in 51/51 rows; Mantis: V0 cells without '
                        'elapsed or energy, 3 cells UNAVAILABLE); (2) checkpoint_selection carries the same columns on every row (Mantis: '
                        'model_tier/variant_role/run_purpose only on V1); (3) summary.json row counts equal the files (PASS for the three packages); '
                        '(4) README states the audit source of every pipeline (LO README names the bundle audits of V5, V6, V8-V10, V13-V16); (5) a '
                        'source_inventory with archive sha256 (present for CQ V7-V16 only); (6) runner identification (sha256 or commit) for runners '
                        'shipped as a tar (Mantis: runner_sha256 and code_tar_sha256 in mantis_native)',
     'stage': 'on receipt of every F2/F3 facts package', 'status': 'OPEN 2026-11-09 (items 1, 2, 5 fail for LO PatchTST and/or Mantis)',
     'status_2026-11-10': 'LARGELY MET for the r2 packages: (1) runner_git_commit filled retroactively (LO 51/51 df2a867, Mantis 48/51 6a69b7f) with a '
                          'runner_git_commit_basis column; the three Mantis V0 cells stay NULL with basis NOT_RECORDED_V0_EARLIER_SCRIPT and '
                          'resource_null_reason NOT_RECORDED (decision 43); elapsed / energy NULL only where the reason column says so (3 V0, 3 '
                          'TELEMETRY_UNAVAILABLE); (2) checkpoint labels on 51/51 Mantis rows; (3) summary counts equal the files; (4) README '
                          'revisions r2 and r2b; (5) source_inventory.json for LO (18 archives; V0 is a run tree) and Mantis (38 archives) with bytes, sha256, '
                          'Drive MD5; (6) runner identification by blob / tree; byte-level receipts (DELIVERY_RECEIPT_CODE_TEAM, 88 + 87 + 58 files, 0 '
                          'problems) exist but are not L2 ingest receipts; the superseded 09/11 packages carry SUPERSEDED.md markers'},
    {'id': 40, 'check': 'acceptance of the M-13 inputs of phase 1 (m13_inputs_phase1_20261108): S0 profile 48 rows = 2 tasks x 3 windows x 4 phases x 2 '
                        'splits with the 32 required columns non-null (PASS; P1 prev/PSI-vs-previous NULL by definition, 12 rows each), conventions '
                        'per decision 39; Z_M 5 rows with parameter counts per reference layout (PASS; MANTIS_V2 row to be added when F3 facts '
                        'exist: 2,214,144 backbone used, 12,366 probe); F0 CQ_PARTIAL_TRIAD 24 rows (PASS: macro-F1 by phase 0.7563 / 0.8775 / 0.9566 '
                        '/ 0.9865, acctempo_m3 NULL NOT_APPLICABLE, n_absent_from_partial_artifact 7,989 (W1 P1 TEST) down to 0 (W3 P4), FINAL '
                        'self-check reproduces labels/cq_personal_v3 per the team); LO F0 NOT_AVAILABLE_PHASE1; sha256 of the four read files equal '
                        'sha256sums_all.txt',
     'stage': 'before M-14 is assembled', 'status': 'OPEN 2026-11-09 (tables pass; the S0 conventions wait for decision 39)',
     'status_2026-11-10': 'PASS on the files (ratification of Q-28 pending): S0 v4 48 rows x 113 columns (v3 minus tr_inactive_learner_ratio and its '
                          'reason; 31 required columns 0 NULL; values identical to v3; cohort ALL, feature_regime present), Z_M v2 six rows (rows 1-5 '
                          'numerically identical to v1; MANTIS_V2: param_count_total 2,226,510 = 2,214,144 backbone used + 12,366 probe, backbone total '
                          '4,188,672, frozen, return_transf_layer 2, output token combined, interp 512, PCA 8, max_seq_len / patch_len / patch_stride '
                          'NULL; the layout table (11 rows) adds CQ/W1/V0 (12,366 trainable, 21 static + 140 dynamic channels) and LO/W1/V0 '
                          '(12,378 trainable, total 2,226,522)), F0 CQ unchanged; all nine files hash-equal to '
                          'their sha256sums.txt'},
    {'id': 41, 'status_2026-11-20': 'no new probe refit: the seed-44 audit copies the reference without fitting (--skip-probe-refit); the check stays diagnostic', 'status_2026-11-16': 'team re-check of 15/11 on the standard machine (default multi-thread, 40 threads, LO seeds 42-44, five parents, three windows): 0.0 between parents and seeds, <= 5.6e-17 to the reference; CQ not re-done; the seed-43 audits copied the reference (no refit, probe_mode recorded in the audit manifests per the team); accepted as the per-environment diagnostic', 'status_2026-11-13': 'reports for CQ W1 and LO W1-W3 on the Drive (read from the README): default multi-thread mode 0.0, single-thread 2.1e-5 / 1.1e-4 / 9.6e-4 / 7.2e-6; the 1e-5 tolerance fails in the single-thread mode; proposed: tolerance 1e-3 with the thread mode recorded, audits copy the reference instead of asserting 1e-9', 'check': 'leak-probe reproduction diagnostic per audit environment: before the first audit of a new environment (host image, library '
                        'versions) and for every task, run tools/check_leak_probe_reproduction_20261109.py on one window/parent: two deterministic runs '
                        'bitwise equal, the default multi-thread run equal to them, |s_leak - reference| and |s_leak_probe_auc - reference| <= the '
                        'tolerance of decision 42, probe_fit_rows and n_iter recorded, the environment block (python, numpy, scipy, scikit-learn, '
                        'threadpools, platform) in the report; the report is uploaded next to the first facts package of that environment',
     'stage': 'before any audit in a new environment and before the phase-2 audits (seeds 43/44, LO Mantis)', 'status': 'OPEN 2026-11-10',
     'status_2026-11-10': 'CQ W1/V0 done per the team response (2.09e-6, 43 iterations, bitwise repeatable, thread-independent; report not on the '
                          'Drive); LO not run (RAM)'},
    {'id': 42, 'check': 'independent verification of the packages of 10-13/11 once their files are in input/results: (a) sha256 of every file against the team sha256sums; (b) check 38 on the three CQ r2/r3 packages and on the LO Mantis package against GD0_s_leak_reference_20261109; (c) r2_changes.csv of CQ PatchTST V0-V6 against the 03/11 package (4.98e-5 measured on 2026-11-10 versus 1.24e-5 in the r2 summary); (d) release 20261112: every numeric column outside qa_* and the macro_f1-dependent columns equals release 20261109; (e) the hypotheses tables re-derived from mm_predictions / mm_recommendations', 'stage': 'L2/L3/L4', 'status': 'PASSED 2026-11-13 (reading of (d) ratified by the author the same day)',
     'result_2026-11-13': "(a) 13 packages copied from the Drive by the author's browser into input/results/_incoming_2026-11-13/ (zips kept in _zips/): 523 files, the 510 listed in the 13 team sha256sums.txt all equal, no unlisted file (mm_runs p1 holds 130 listed files, not 127); (b) s_leak equals GD0_s_leak_reference_20261109 in every cell: 0.0 for CQ PatchTST V0-V6 r2 (168), V7-V16 r2 (240) and MANTIS_V2 r3 (408); <= 1.1e-16 for LO Mantis (408 cells, s_leak and s_leak_probe_auc); spread across pipelines 0.0 in the four packages; (c) the *_old columns of r2_changes.csv equal the 03/11 facts exactly and the *_new columns equal the r2 facts; the 03/11 facts deviate from the CQ reference by 1.24e-5 (21 of 168 rows above 1e-5), as the r2 summary states; the 4.98e-5 of round 27 was measured on report_derived/cq_f2_patchtst_v0_v6_sanity_components.csv, whose s_leak is rounded to 3-4 decimals (126 of 168 rows above 1e-5), not on the facts; no conflict remains; (d) release 20261112 against 20261109 (3,672 rows aligned; builder_version is the only differing string column): outside qa_* and the macro_f1-dependent columns, differences are confined to CQ PATCHTST rows and to s_leak-dependent columns (s_leak 1.24e-5, every derived column <= 1.74e-5), i.e. the r2 facts within the r2 max change; accepted by the author on 2026-11-13; macro_f1 columns filled for 1,632 CQ rows (f1_macro workaround), qa_run_level_invariant_ok True in 3,672 rows, is_pareto_f1_cost changed in 300 rows; (e) re-derived with metamodel 0.2.3 (hypothesis_tests on mm_recommendations.csv and prepare_frame on meta_dataset_seed_agg): estimates of H1-H5, H7 and H8 equal to <= 1.2e-16 and every supported flag equal in the six configurations; CI bounds and p_boot differ (up to 9.3e-4 and 0.033), so CI and p are cited from the team files; H6 not re-derived (needs the scored frame with the cost ratio); log input/results/_incoming_2026-11-13/_check42_log_20261113.json"},
    {'id': 43, 'check': 'verification of the six seed-43 facts packages (round 29, 2026-11-16): (a) sha256 of the eight aggregate files of each of the 12 directories against the team sha256sums.txt (summary, README, sanity_components, checkpoint_selection, resource_per_run, runner_commit_evidence, source_inventory; the other 78 files per directory stay on the Drive, listed in sha256sums.txt); (b) check 38 identity against s_leak_reference_{CQ,LO}; (c) formulas: S_perf = (macroF1 x BA x (MCC+1)/2 x (kappa+1)/2)^(1/4), S_san+ v1 = geometric mean of the six components, v2 with s_cal instead of s_ent, each component floored at 1e-3, M3 = S_perf^0.6 x v1^0.4, M4 = S_perf^0.6 x v2^0.4 (floor 1e-3); (d) coverage 408 rows = 51 cells x 2 splits x 4 phases, 51 checkpoint and 51 resource rows per directory, 17 pipelines; (e) the tables of the team report BAO_CAO_TONG_HOP_SEED42_43_2026-11-16_M4 re-derived from the facts (seed 42 from the facts in input/results: GD1 F1 tables, GD2 PatchTST r2, GD3 Mantis r3 / 20261110); (f) labels and provenance per decisions 43 and 47; (g) resource completeness (train, elapsed, energy)',
     'stage': 'before any seed-43 number is cited',
     'status': 'PASSED 2026-11-16: (a) 84/84 files equal; (b) <= 1.1e-16; (c) <= 1.2e-15 on 4,896 rows (the component floor is needed for LO RNN W3 V14 P4, s_ent < 1e-3); (d) 12/12 directories complete; (e) 2.1: 168/168, 2.2: 72/72 and the four 18-combo counts, 2.3: 72/72, 2.4: 60/60, 6: 288/288 values at 4 dp, 7: 64/64 at 2 dp (seed-42 F1 elapsed not compared: no per-run elapsed in the GD1 tables); release 20261112 vs facts for seed 42: <= 1.1e-16 on the common values but six alias metrics empty on the CQ F1 rows; (f) F1/PatchTST 5ba9829 at run time 510/510, Mantis retroactive with label, variant_role NULL on ten directories (decision 47 open); (g) train and elapsed 51/51 everywhere; energy 0/204 CQ F1 (ENERGY_NOT_MEASURED, NVML UNAVAILABLE), 48/51 CQ PatchTST, 46/51 LO PatchTST, 51/51 LO F1 and both Mantis; log: input/results/GD6_delivery_receipts_and_checks_20261116/analysis_r29_2026-11-16.json'},
    {'id': 44, 'check': 'verification of the six seed-44 facts packages (round 30, 2026-11-20), the same items as check 43: (a) sha256 of the eight aggregate files of each of the twelve directories against the team sha256sums.txt; (b) check 38 on every row; (c) S_perf, S_san+ v1/v2, M3 and M3cal re-derived from the components; (d) 408 unique sanity rows, 51 checkpoint cells and 51 resource runs per directory; (e) every table of sections 1-3 of the team report of 20/11 re-derived from the facts of the three seeds; (f) labels, runner commit and builder commit; (g) time and energy coverage with the reason of every gap', 'status': "PASSED 2026-11-20: (a) 84/84 files equal; (b) max |s_leak - reference| = 0.0, probe_seed = 42, s_leak_source = REFERENCE_TABLE_COPY_NO_REFIT; (c) max error 2.0e-15; (d) 12/12 directories 408/51/51; (e) coverage 36/36, table 2.1 288/288, mean and SD across seeds 48/48 (SD with ddof = 1), table 2.2 216/216 and 36/36 shares, table 2.3 108/108, table 2.4 108/108 values and 36/36 best-pipeline pairs, table 2.5 6/6, table 3.2 284/284, table of gaps 30/30 with the same ten combinations; (f) 5ba9829 at run time on 510/510 cells, Mantis 6a69b7f retroactive, builder commit 7c24981 in the twelve summary.json, README title 'seed 44' and one r2 section in 12/12, variant_role NULL in ten directories; (g) train and run time 612/612, energy 604/612 (PatchTST CQ 44/51, Mantis CQ 50/51), reasons as reported; the energy proposal of the team reproduces from the facts (71.6 W and 44.6 W medians)", 'evidence': 'input/results/GD6_delivery_receipts_and_checks_20261120/analysis_r30_2026-11-20.json'},
    {'id': 45, 'status_2026-11-21': 'PASSED 2026-11-21 on the re-issue (release ..._20261120_mm026, runs mm_runs_..._20261120_mm026; every number read from the files by the writing side): (a) the 70 input hashes of the manifest equal those of release 20261120; (b) the 4,896 seed-44 rows equal the twelve accepted fact files on 40 columns (max abs difference 0.0) and the 612 seed-44 runs equal the resource tables within 3.7e-12; (c) the two child seed-level tables (7,344 rows each) have the sha256 of the manifest, every row COMPLETE, the seven QA flags at 1.0; the seed-aggregated table (35 MB) cannot be downloaded through the connector: its sha256 in the release sums (96e7fd0c...) equals the one in the RUN_LOG of the runs, and the targets of four objectives in mm_predictions (1,632 ids each) equal the aggregation of the seed-level tables by metamodel 0.2.6 exactly; (d) 238 registry rows per configuration (OK 238, or 231 with 7 L6-FS3 rows skipped for obj_perf and obj_macrof1), no fallback model, MQ08 5/7, 4/7, 5/7, 3/7, 7/7, 6/7, the two regret tables and the H1-H8 table of the reply re-derived; (e) one release id and one package version (0.2.6) in the six configurations; the five configurations that do not use energy equal the earlier pc_one_thread set on every table held by the writing side (different: 0) and on every cell of mm_hypotheses.csv; (f) sens_energy: energy cost basis in 56 LO groups (BILSTM, GRU, LSTM, RNN 12 each, MANTIS_V2 8), equal to the energy coverage computed from the seed-level tables; 170 of 238 metric rows differ from main_cal_time in the cost columns only, the recommended pipeline is the same in 6,528 of 6,528 groups, H6 = -0.3343 [-0.4225; -0.2524] against -0.3326 [-0.4162; -0.2525]; (g) packaged with sha256sums (74 files downloaded and matched; the CSV and YAML duplicates and the logs are listed in the sums and were not downloaded), RUN_LOG, pip freeze, platform string and the run script; the team moves the release and the runs to cross_task_meta/accepted; (h) the Linux host set stays as history, its pip freeze is lost. Notes: code_commit is UNKNOWN in mm_run_registry (no checkout on the run machine; the commit is in the RUN_LOG); the set is the robustness variant of Table 42 with task-pooled E1 and is cited under that label', 'status_2026-11-20b': 'closing condition restated after the author decisions of 20/11: the release is re-assembled with metamodel 0.2.6 (strict measurement types; on an ALL-only input it differs from 0.2.5 by the slice-size columns kept on the seed-aggregated table) and the six configurations are re-run on it in the PC environment of record (decision 50 (a)); the Linux host run is the cross-platform replication, so item (h) is settled; item (i) leaves this check: the executed analysis is recorded as the robustness variant of Table 42 with task-pooled E1 folds, and the registered primary design is the subject of checks 46 and 47 (decision 51 (b)); items (c), (e), (f) and (g) are open as on 20/11; per-task E1 runs are not part of the re-issue', 'check': 'acceptance of the three-seed meta release and of the three-seed M-15 (round 30): (a) the release is built from the verified facts (input hashes); (b) its rows equal the facts; (c) row counts, hashes and QA flags of the parquet tables; (d) the tables of section 5.3 of the 20/11 report re-derived from the mm_* files; (e) one release and one package version for the six configurations; (f) sens_energy is a real sensitivity analysis; (g) the runs are packaged (sha256sums, RUN_LOG, pip freeze, input hash) under cross_task_meta/accepted; (h) reproducibility across machines stated; (i) the executed design against the registered one (subgroups, folds, replication and pooled tests)', 'status': 'PARTIAL 2026-11-20: (a) PASSED 61/70 input hashes matched, all 48 seed-43/44 files; (b) PASSED on the published extracts (1,836 cells, 1,836 runs); (c) PENDING, the parquet tables are not in input/results; (d) PASSED: 238 registry rows per configuration, statuses, MQ08 5/7, 4/7, 5/7, 3/7, 7/7, 6/7, run times, the two regret tables and the H1-H8 table equal the files of pc_one_thread; (e) NOT MET: five configurations on release 20261119 and sens_energy on 20261120, LO half assembled with a locally patched 0.2.4; (f) NOT MET: sens_energy equals main_cal_time by construction in 0.2.4 (fixed in 0.2.5); (g) NOT MET: work_in_progress, no sha256sums.txt, RUN_LOG or pip freeze; (h) MEASURED: baselines identical, learner rows differ on 11-18 of 182 per configuration, verdicts identical (decision 50); (i) NOT MET: one subgroup (ALL, ALL) instead of five, E1 folds pooled over the two tasks, hypothesis rows for E1-B only (decision 51); the writing side reproduced the E1-B point estimates of H1-H4 and H7 from the recommendation rows exactly (interval bounds within 6.4e-4 for the main configuration) and added the E1-A, pooled and per-task rows as descriptive', 'closes_when': 'the release is re-assembled with metamodel 0.2.5 (strict types), the six configurations are re-run on it in the environment of record, the package is hashed and moved to accepted/, and the two parquet tables are in input/results; item (i) follows decision 51', 'evidence': 'input/results/GD7_meta_runs_M15_3seed_20261120/, input/results/GD5_meta_release_CQ_LO_full_F1F2F3_seeds42_43_44_20261120/, analysis files of round 30 in GD6_delivery_receipts_and_checks_20261120/'},
    {'id': 46, 'status_2026-11-26': 'CLOSED 2026-11-26: the four questions left open on 24/11 are answered in the reply of the team (PHAN_HOI_REVIEW_PHA_C_2026-11-24.md, accepted/); the acceptance of 23/11 and 24/11 stands unchanged', 'closure_2026-11-26': {'status': 'CLOSED 2026-11-26: the four questions left open on 24/11 are answered in the reply of the team (PHAN_HOI_REVIEW_PHA_C_2026-11-24.md, accepted/); the acceptance of 23/11 and 24/11 stands unchanged', 'answers_of_the_team_not_reverified': ['the S0 means ev_mean_observed_length and ev_mean_observed_fraction use the valid-enrollment denominators (an additional scan is filed under accepted/phaseB_review_followup_20261123/)', 'ev_n_cells_observed_zero of the subgroup rows is counted from the raw view; the ALL rows are kept from profile v4', 'names of the complete archives, origin of pr_auc_macro (model/metrics.py at 7933143, not verified per cell by the team), meaning of n_unit_pipeline_rows'], 'evidence': 'input/results/GD6_delivery_receipts_and_checks_20261126/team/'},
     'status_2026-11-24': 'PASSED 2026-11-24, items (a) to (f): item (f) is closed by the push of the code of phase B (origin/main at ecad59d); the two tables of release r2 above 10 MB are verified by sha256 against sha256sums.txt of the team and compared with the parts and with the table rebuilt by the writing side (largest differences 0.0 and 1.4e-17); the acceptance of 23/11 on the data stands unchanged',
     'closure_2026-11-24': {'f_code': "closed: the code that produced the packages of phase B is in origin/main at ecad59d (CODE_REFERENCE['review_2026-11-24'])", 'two_tables_above_10_MB': 'downloaded by the author on 23-24/11 into input/results/GD5_meta_release_5subgroups_r2_20261122/release/ and read there: meta_dataset_seed_level.parquet sha256 57b56e1ab4dae42e5fdde3d66ee28c2b3a1f94a7aa346a5c3f7852e3717ef61e and meta_dataset_seed_agg.parquet sha256 26409d4e9b55723e4ff042d8312397cc7b0be099888e573ed4a7aa8a3d763f0a, both equal to sha256sums.txt of the team; the seed-level file holds the rows of the 30 parts (73,440 rows x 561 columns, same keys, 457 numeric and 104 other columns, largest difference 0.0, row order different); the seed-aggregated file against the table rebuilt by the writing side from the 30 parts: 24,480 rows, same keys, 1,708 numeric and 82 other common columns, largest difference 1.4e-17; the team table has 7 more columns (s_leak_probe_fit_once_max, s_leak_probe_fit_once_mean, s_leak_probe_fit_once_median, s_leak_probe_fit_once_min, s_leak_probe_fit_once_p90, s_leak_probe_fit_once_p95, s_leak_probe_fit_once_sd: aggregates of a diagnostic column, in no feature set); this file is the input of B.5 r2 and of the ten runs of phase C (input_sha256.json)', 'builder_versions': "read: see CODE_REFERENCE['review_2026-11-24']['notes']; no unit is regenerated", 'evidence': 'input/results/GD6_delivery_receipts_and_checks_20261124/checks/check_big_tables_r33.json and r33_facts.json'},
     'open_2026-11-24': ['denominator of ev_mean_observed_length and ev_mean_observed_fraction on a slice (asked on 23/11, not answered in the report of 24/11)', 'confirmation that ev_n_cells_observed_zero of the subgroup rows is counted from the raw view (asked on 23/11)', 'names of the two complete archives that replace the two truncated ones, column name n_unit_pipeline_rows of phaseB_two_class_cells.csv, function and commit that computed pr_auc_macro of the accepted F1 seed-42 facts (README notes asked on 23/11)', 'F0 of CQ by subgroup (not blocking)'],
     'status_2026-11-23': 'PASSED 2026-11-23 on the data, items (a) to (e): 36 of 36 unit packages (58,752 rows), S0 profile v5 (240 rows, ALL rows equal to v4), release CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2 (73,440 seed-level rows, ALL rows equal to the accepted release on 557 columns apart from the release id and the builder version, subgroup_report ok), B.5 r2 equal to the accepted set (54 tables, 0 different); the three gates set on 21/11 for the start of check 47 are met; item (f) stays OPEN: the code that produced the packages is not in the repository (origin/main unchanged at fc361b6); details in acceptance_2026-11-23',
     'acceptance_2026-11-23': {'delivery': 'Drive folder cross_task_meta/work_in_progress/delivery_phaseB_r2_20261123 (457 files in SHA256SUMS.txt; 169 of them downloaded by the writing side and equal to their sha256, the others being CSV and YAML copies of delivered tables, console logs, intermediate tables of the S0 computation, most tables of the abandoned r1 attempt and the six tables above 10 MB, namely the seed-level and seed-aggregated tables of the release and of its two child releases) and work_in_progress/subgroups_phaseB_20261121 (36 of 36 unit tables and 36 summaries, each equal to the sha256 of its unit and of the release manifest)', 'a_seen_flags': '48-row comparison delivered: the registered rule gives UNSEEN where the definition of the cohort audit gives SEEN on 29,274 of 4,299,256 evaluated enrollment-phase rows of CQ and 29,091 of 3,271,464 of LO, never the reverse (0 and 0); end-date report: 1 offering per task with a spread above 60 s (86400.9 s), 0 evaluated enrollments in it; taking the earliest instead of the latest end date changes 0 seen_course flags and 25 seen_learner flags; QA15: 0 and 0 rows', 'b_subgroup_facts': "36 units, 58,752 rows (1632 per unit); team status {'PASS': 28, 'PASS_WITH_REPORTED_DIFFS': 8}; every unit table equals the sha256 named in the release manifest (36 of 36) and its rows equal the subgroup rows of the release (58,752 rows, 71 numeric columns, largest difference 0.0); read from the release by the writing side: 5 rows for every (unit, window, pipeline, split, phase), slice_status OK on the 58,752 subgroup rows, SEEN + UNSEEN = ALL on n_eval_samples in 14,688 of 14,688 cells of each axis and on the class supports and predicted counts wherever the ALL row carries them (13,056 cells; 0 mismatches in all); n and class supports equal to the 240-row support table on every row (0 and 0 mismatches); confusion_matrix present on the 58,752 subgroup rows, its margins equal to supports, predicted counts and n, and SEEN + UNSEEN equal to the ALL matrix in 22,848 of 22,848 cells where the ALL row has one; macro-F1, balanced accuracy, G-mean, kappa and MCC recomputed from the matrices equal the delivered values within 1.7e-12 on every subgroup row; s_eff, s_leak and s_leak_probe_auc equal to the ALL row (largest difference 0.0), s_leak_probe_auc absent only where the accepted ALL rows lack it (4 CQ F1 units of seed 42); formulas of S_perf, S_cal, S_san+ v1 / v2, M3 and M3^(cal) within 2.2e-16 on the subgroup rows; support-weighted class recalls of SEEN and UNSEEN equal to the ALL recalls within 1.1e-16 and the Brier score within 9.7e-10", 'small_and_two_class_slices': "38 of 240 slice cells flagged small (CQ 2, LO 36); 19 cells hold two classes (all LO; {'COURSE|SEEN|VALIDATION': 4, 'COURSE|UNSEEN|TEST': 8, 'COURSE|UNSEEN|VALIDATION': 3, 'LEARNER|SEEN|TEST': 4}), 5,814 seed-level rows, all flagged small; no cell with fewer than two classes, so no INFEASIBLE row; on these rows the absent class enters macro-F1 and balanced accuracy with 0, G-mean is 0 and roc_auc_macro_ovr is NULL (convention of the fact function, agreed on 21/11)", 'report_only_differences': {'rule': 'the accepted fact packages are not recomputed (packaging rule of 21/11); the builder recomputes the ALL row of every cell and compares it with the accepted row; six metric columns of the eight F1 units of seed 42 differ; cause as stated in the README of the team (_shared/README.md), not verified by the writing side: the earlier facts clipped probabilities at 1e-7 (present function 1e-12) and pr_auc_macro came from an earlier implementation; the team treats them as reported, not as failures, and asks the writing side to confirm; confirmed on 23/11 as a technical convention, reported to the author', 'largest_difference_by_metric': {'cross_entropy': 0.0005635835817975, 'log_loss': 4.440892098500626e-16, 'multiclass_brier': 1.4330982234245224e-09, 'multiclass_nll': 0.0045993501763815, 'pr_auc_macro': 0.0004436362634502, 'top_label_ece_15': 2.2687585600825178e-06}, 'unit_of_the_largest': {'cross_entropy': 'CQ_RNN_seed42', 'log_loss': 'LO_MANTIS_V2_seed44', 'multiclass_brier': 'LO_BILSTM_seed42', 'multiclass_nll': 'CQ_BILSTM_seed42', 'pr_auc_macro': 'CQ_BILSTM_seed42', 'top_label_ece_15': 'CQ_GRU_seed42'}, 'units_above_1e-9': {'cross_entropy': ['CQ_BILSTM_seed42', 'CQ_GRU_seed42', 'CQ_LSTM_seed42', 'CQ_RNN_seed42', 'LO_BILSTM_seed42', 'LO_GRU_seed42', 'LO_LSTM_seed42', 'LO_RNN_seed42'], 'log_loss': [], 'multiclass_brier': ['LO_BILSTM_seed42', 'LO_GRU_seed42', 'LO_LSTM_seed42', 'LO_RNN_seed42'], 'multiclass_nll': ['CQ_BILSTM_seed42', 'CQ_GRU_seed42', 'CQ_LSTM_seed42', 'CQ_RNN_seed42', 'LO_BILSTM_seed42', 'LO_GRU_seed42', 'LO_LSTM_seed42', 'LO_RNN_seed42'], 'pr_auc_macro': ['CQ_BILSTM_seed42', 'CQ_GRU_seed42', 'CQ_LSTM_seed42', 'CQ_RNN_seed42'], 'top_label_ece_15': ['CQ_BILSTM_seed42', 'CQ_GRU_seed42', 'CQ_LSTM_seed42', 'CQ_RNN_seed42', 'LO_BILSTM_seed42', 'LO_GRU_seed42', 'LO_LSTM_seed42', 'LO_RNN_seed42']}, 'every_other_column': 'largest difference of a recomputed ALL row to its accepted row outside the six metrics: 3.3e-16 (36 summary.json)', 'seen_in_the_release': "n-weighted log_loss of SEEN and UNSEEN against the ALL value: 4.6e-03 at most, above 1e-9 in 4 units only (['CQ|BILSTM|42', 'CQ|GRU|42', 'CQ|LSTM|42', 'CQ|RNN|42']); in the four LO F1 units of seed 42 the weighted log_loss agrees with the ALL row although multiclass_nll of these units is among the reported differences (not examined further)", 'reach': 'log_loss, brier, ece and pr_auc_macro are not objectives; val_log_loss_before, val_brier_before, val_ece_before and val_pr_auc_macro_before are warm-start inputs of FS4 and FS5; the ALL rows are those of the accepted release, so the ALL-only analysis is unchanged'}, 'c_s0_profile_v5': 'm13a_s0_profile_20261122_v5_dtypefix: 240 rows x 113 columns, 240 unique keys, 48 rows per subgroup; sha256 equal to the summary of the team and to the state input of the release manifest; the 48 ALL rows equal v4 on 105 value columns with 0 different values and 0 dtype changes (the 29 all-NULL reason columns keep the dtypes of v4); 49 numeric columns equal the ALL row of the cell on every subgroup row and 23 evaluation-slice columns vary; SEEN + UNSEEN = ALL exactly on 14 count columns; ev_n_enrollments and ev_n_offerings equal the support table on the 240 rows; the release rows equal the profile row of their key on 105 columns (73,440 rows, 0 columns with a difference); JSD of the ALL slice against v4: 8.3e-17 (CQ), 1.1e-16 (LO)', 'c_notes': ['ev_n_cells_observed_zero is NULL with a registered reason on 18 ALL rows of the VALIDATION split (P1-P3, as in v4) and has a value on the 72 subgroup rows of the same cells; the runs read TEST rows only (eval_split = TEST), where the column is filled on every row', 'the n-weighted mean of ev_mean_observed_length over SEEN and UNSEEN differs from the ALL value by up to 0.042 day and that of ev_mean_observed_fraction by up to 1.7e-05; ev_missing_rate and ev_train_overlap_share agree exactly; the denominator of the two means is asked from the team', 'the bins of most_common_hour_sin were rebuilt from the stored ALL histograms (six mappings, eight histograms each, no observed hour with a second exact solution); the team does not claim to have recovered the original binning code', 'F0 of CQ by subgroup is not delivered (not blocking): the 12 F0 reference columns are NULL on the subgroup rows of the 18 CQ units'], 'd_release': "CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2 (created 2026-11-22T15:41:01 UTC, builder metamodel 0.3.0 (2026-11-21)): 30 seed-level parts equal to parts_manifest.json and to sha256sums.txt, 73,440 rows x 561 columns, 73,440 unique meta_obs_id, 14,688 rows per subgroup, row_status {'COMPLETE': 73440}, every QA flag true on every row; ALL rows against the accepted release of check 45: same 14,688 ids, 557 common columns, different only in ['builder_version', 'meta_release_id'] (0 other columns differ); four list-valued columns (['per_class_f1', 'per_class_precision', 'per_class_recall', 'per_class_support']) are written as JSON text by the combining script, values equal; three new columns ['seen_history_reference', 'seen_rule_version', 'slice_status']; pairing inside the subgroup: 4,320 recommendation groups of 17 candidates (864 per subgroup), reference = V0 of the same subgroup, 0 V0 rows with a non-zero delta, meta_cv_group of a subgroup row equal to that of its ALL row; metamodel 0.3.0 on the rebuilt table: subgroup_report ok with 0 violations, seed aggregation 24,480 rows (4896 per subgroup, all COMPLETE, three seeds each), 3,876 of them flagged small; the two tables of the team above 10 MB (seed-level 57b56e1ab4da..., seed-aggregated 26409d4e9b55...) were not downloaded; the seed-aggregated file is the input of B.5 r2 (input_sha256.json)", 'e_all_only_regression': "B.5 r2: six configurations with metamodel 0.3.0 and default options on the seed-aggregated table of r2, exit code 0 each (8,418 to 9,083 s, six in parallel); compared by the writing side with its copy of the accepted set of check 45: 48 parquet tables, 0 different, and the six mm_hypotheses.csv byte-equal (6 of 6); the configurations differ in ['meta_release_id'] only; team comparison: 54 tables, 0 different; first regression of 0.3.0 on real data", 'e_r1_attempt': "the first assembly (release id ..._5subgroups_r1, S0 v5 before the dtype fix) differed from the accepted set in mm_run_registry.dropped_features only: 154 learner rows of main_cal_time lacked the NEAR_CONSTANT entries of 8 all-NULL reason columns (['ev_missing_rate_reason', 'ev_n_cells_observed_eligible_reason', 'ev_n_cells_observed_missing_reason', 'ev_n_cells_observed_value_reason', 'ev_n_cells_structural_absence_reason', 'ev_n_cells_total_reason', 'ev_n_cells_unavailable_reason', 'ev_train_overlap_share_reason']), whose dtype had become object; n_features, best_params and mm_metrics were equal; 0.2.6 on r1 shows the same 154 rows and 0.3.0 on the dtype-fixed table 0; r1 was never run under the full design and is abandoned", 'f_packaging': "RUN_LOG.md, pip freeze, sha256sums and an rclone receipt (458 of 458 files) are delivered; the scripts are NOT committed (CODE_REFERENCE['review_2026-11-23'])", 'a8_a9_leftovers_of_check_45': "manifest scan: 2,252 manifests in 898 archives; outside historical/ 1,717 of 1,717 carry the CURRENT data_release_id ({'CQ': 749, 'LO': 968}); in historical/ {'NO_FIELD_OLD_SCHEMA': 473, 'CURRENT': 62}; flagged archives: 8 re-read, md5 equal on 8, verdicts {'COMPLETE': 6, 'PROBLEM': 2} (truncated: ['lo_patchtst_seed44_V2_host40077.tar', 'LO_static_v2_BILSTM.tar']); seed-44 facts against M-18: 612 of 612 cells on both sides, best epoch equal in 612, best score within 5.6e-17", 'drive': 'phase A is in cross_task_meta/accepted/ (release, child releases, runs of 20261120_mm026); the exploratory per-task set is in cross_task_meta/exploratory_not_for_conclusions/ and has not been opened by the writing side; S3_model is split by seed (seed=NN/), the delivered packages still quote the earlier paths (mapping tables on Drive)', 'evidence': 'input/results: GD5_meta_release_5subgroups_r2_20261122, GD4_s0_profile_v5_dtypefix_20261122, GD1_subgroup_facts_phaseB_36units_20261121, GD7_meta_runs_B5_r2_ALL_only_20261122, GD6_delivery_receipts_and_checks_20261123 (check files check_release_r2.json, check_s0_v5.json, check_shared_tables_r32.json, b5_r2_vs_phaseA_writing_side.json, b5_r1_diagnostics_registry.json, r32_facts.json)'},
     'open_2026-11-23': ['push of the builders, of the S0 v5 scripts, of the assembly script and of the B.5 driver to origin/main', 'denominator of ev_mean_observed_length and ev_mean_observed_fraction on a slice', 'two builder versions for the 36 units (27 + 9): the difference is read by the writing side once both commits are in the repository'],
     'status_2026-11-21': 'PARTIAL 2026-11-21: B.0 answered (predictions of 1,836 of 1,836 runs listed, join to user_id / course_id / offering_id verified on two families, cutoff from the phase views); (a) seen flags built (CQ 4,299,256 rows, LO 3,271,464 rows; QA15: 0 rows with seen_offering = 1, team QA files); support table read by the writing side: 240 rows, every slice with at least two classes, SEEN + UNSEEN = ALL in 48 of 48 cells on both axes, 38 cells flagged small (36 of them LO) and 19 with two classes present (all LO); the 48-row comparison with the definition of the cohort audit is NOT DONE; (b) pilot unit CQ RNN seed 42: 1,632 rows; contract CONFIRMED by the writing side: unique keys and full grid, n_eval_samples and class supports equal to the support table for every pipeline and adding up to the ALL rows of the accepted release, s_eff and s_leak inherited (differences 0.0 and 8.3e-17), formulas of S_perf, S_san+ v1/v2, M3 and M3^(cal) within 3.9e-16, support-weighted class recalls of SEEN and UNSEEN equal to the ALL recalls within 2.2e-16 and the Brier score within 8.0e-10; through metamodel 0.2.6: assemble_seed_level accepts the delivered rows with the ALL rows of the unit, 2,040 rows COMPLETE, subgroup_report ok with no violation, pairing inside the subgroup (96 new groups of 17 candidates); one difference recorded: the n-weighted log_loss of the slices differs from the ALL value of the accepted seed-42 facts by up to 1.75e-3 (the two axes agree with each other within 1.7e-16), because the accepted seed-42 facts of the R4 export were computed with the former probability clip of 1e-7 while the present metric function clips at 1e-12 (repo @ fc361b6: note METRIC_DEF v1.3 in model/metrics.py; EPS = 1e-12 in metrics_core/evaluation.py); log_loss is not part of any objective, but val_log_loss_before is a warm-start input of FS4 and FS5; 35 units pending; (c)-(f) not started', 'requests_2026-11-21': ['extend the self-check of the ALL row to every metric column and write the largest difference per column to summary.json', 'write confusion_matrix on the subgroup rows and copy s_leak_probe_auc and the provenance columns of the run (parent_pipeline, model_tier, variant_role, run_purpose, s_leak_source, probe columns) from its ALL row; s_leak_probe_auc is needed, not only wanted: the release builds val_s_leak_probe_auc_before from it, a warm-start input of FS4 and FS5, which would otherwise be NULL on the subgroup rows only; rule: the subgroup rows of a unit carry exactly the columns of its accepted ALL rows, run-level and cell-level columns copied, slice-level columns recomputed (in the accepted release s_leak_probe_auc has a value in 32 of the 36 units and is absent in the four CQ F1 seed-42 units of the R4 export; the pilot unit is one of these four, so it lacks nothing)', 'report the end-date spread of the two offerings above 60 s and the number of evaluated enrollments whose flags depend on it', 'deliver the 48-row comparison of seen_course with SEEN_COURSE of the cohort audit', 'regenerate the pilot unit with the final builder so that the 36 units share one builder commit, recorded in summary.json'], 'packaging_2026-11-21': {'release_id': 'CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r1 (the digests of check 47 depend on it; a re-assembly needs new digests from the writing side)', 'seed_level_parts': 'the release package holds seed_level_parts/: the seed-level table split by task x subgroup x seed (30 parquet files, each under 10 MB) with parts_manifest.json (rows and sha256 per part); reason: the Drive connector of the writing side refuses files above 10 MB and every table of a five-subgroup release exceeds that', 'all_only_regression': 'step B.5 is run with metamodel 0.3.0 and its default options (legacy design): the six configurations of check 45 on the seed-aggregated table of the five-subgroup release must equal the accepted set (compare_mm_dirs_r30b.py: different: 0); it is also the first regression of 0.3.0 on real data', 'gates_to_start_check_47': ['assemble --require-subgroups --compare-all-with <child release of check 45> ends with exit code 0 for CQ and for LO', 'the combined seed-level table has 73,440 rows (14,688 per subgroup)', 'the ALL-only regression prints different: 0 for the six configurations'], 'accepted_facts': 'the accepted fact packages are not recomputed and not overwritten; the log_loss of the older packages keeps its 1e-7 clip and the difference per unit is listed in the README'}, 'check': 'acceptance of the five-subgroup facts and of the five-subgroup meta release (decision 51 (b), 2026-11-20b): (a) seen flags of every evaluated enrollment and phase by the registered rule seen_v1_train_partition_only (Table 10: TRAIN-partition history ending before cutoff(e, P_k); reference implementation tempo_fix/seen_flags.py), kept with the predictions; seen_offering = 0 on every VALIDATION and TEST row (QA15); a support table of 240 rows (2 tasks x 3 windows x 2 splits x 4 phases x 5 subgroups) with n_eval, class supports, offerings and slice status; the number of rows whose COURSE flag differs from the definition of tools/audit_prediction_course_cohort.py is reported; (b) subgroup facts of the 1,836 runs recomputed from the stored predictions with the function used for ALL / STRICT / OVERLAP (tools/vastai_audit_shared.py _slice_rows): 58,752 new rows (36 task x family x seed units x 408 x 4 subgroups) with the columns of sanity_components plus subgroup_axis, subgroup_value and slice_status; s_eff = value of the run (QA24); s_leak = canonical value of the (window, parent pipeline, split, phase) cell, the rule applied to STRICT / OVERLAP; SEEN + UNSEEN = ALL on n_eval_samples, class supports and confusion matrices on both axes (QA06); one row for every planned combination, with NULL metrics and the real n_eval_samples when the slice is empty or holds one class (QA01); the accepted packages are not rewritten (addendum folders, sha256 of the accepted files unchanged); (c) S0 profile v5 with 240 rows: TRAIN-side columns equal to the ALL row of the cell and to v4, evaluation-slice columns (ev_*, evpool_*, drift_tr_ev_*) recomputed on the slice; F0 of CQ by subgroup (120 rows) when available, not blocking; (d) release assembled with metamodel 0.2.6 and `--require-subgroups --compare-all-with <accepted three-seed release>`: exit code 0, subgroup_report.ok and all_slice_against_reference ok for both tables, 73,440 seed-level rows, INFEASIBLE rows counted by subgroup; (e) the six ALL-only configurations on the five-subgroup release reproduce the re-issue of check 45 exactly (mm_metrics, mm_hypotheses, mm_recommendations) in the environment of record; (f) scripts committed, RUN_LOG, pip freeze, sha256sums', 'status': 'NOT STARTED 2026-11-20: asked from the code team in the second version of the 20/11 request (phase B); the team first confirms that the per-sample predictions of the 1,836 runs and the salted join to user_id and course_id are available (item B.0)', 'conventions': {'s_leak': 'inherited from the ALL cell, as for STRICT / OVERLAP in every accepted facts package; section 6.10 scores the probe on the slice of the row and section 6.11 treats s_leak as a run-level component in the bootstrap; s_leak is identical across the 17 pipelines of a recommendation group (check 38), so the choice changes a factor common to the group and no ranking inside it', 'undefined_slice': 'row_status INFEASIBLE with reason CLASS_ABSENT (metamodel 0.2.6); the group leaves the seed-aggregated table; small groups stay with small_subgroup_flag (section 2.5)', 'row_order': 'the four subgroup blocks are appended to the facts table and the ALL rows keep their relative order, so that the ALL-only runs repeat bit for bit'}, 'evidence': 'working/Data and Code/Progress/Ver 3/2026-11-20_Seed44_M15_3seed/Yeu_cau_doi_code_2026-11-20_ban2.md; metamodel 0.2.6 (assemble.subgroup_report, assemble.compare_main_slice, tests/test_subgroups_026.py)'},
    {'id': 47, 'followup_2026-11-26b': {'what': 'metamodel 0.3.1 (2026-11-26), written by the writing side after decision 59 (b): column-wise permutation of the state that keeps every dtype; command negative-control (the control alone on the folds and hyper-parameters of a delivered run, after a replay of the delivered control and of the model of record); explicit order of first appearance for the bootstrap clusters; command verify-bootstrap; environment record. MMConfig and the ten frozen digests are unchanged; the package is not used for any other table of phase C', 'run_of_the_writing_side': 'hand-off driver run_negative_control_r2.py on the ten delivered run directories, in the container of the writing side (python 3.13.18, pandas 3.0.5, numpy 2.5.3, scikit-learn 1.9.1, LightGBM 4.7.0, 1 learner thread); this is NOT the environment of record', 'control_alone': '115 of 115 folds OK; largest difference of the replay of the delivered control 0.0e+00 and of the replay of the model of record 0.0e+00; delivered control passes in 57 of 115 folds (the accepted tables), dtype-preserved control in 63 of 115 (22 flags change)', 'passes_by_configuration_delivered_to_dtype_preserved': {'full_main_cal_time': '5/12 -> 6/12', 'full_sens_v1': '6/12 -> 5/12', 'full_sens_energy': '5/12 -> 6/12', 'full_sens_conservative': '6/12 -> 9/12', 'full_obj_perf': '7/12 -> 7/12', 'full_obj_macrof1': '5/12 -> 5/12', 'var_all_only_main': '7/12 -> 7/12', 'var_task_pooled_main': '5/7 -> 6/7', 'var_all_rows_baselines_main': '6/12 -> 5/12', 'var_drop_small_main': '5/12 -> 7/12'}, 'by_protocol_dtype_preserved': {'E1-A': '9/19', 'E1-B': '6/19', 'E2': '13/20', 'E3': '35/57'}, 'verdict_unit_E1B_dtype_preserved_passes_by_configuration': {'full_main_cal_time': '0/2', 'full_sens_v1': '0/2', 'full_sens_energy': '0/2', 'full_sens_conservative': '1/2', 'full_obj_perf': '1/2', 'full_obj_macrof1': '2/2', 'var_all_only_main': '0/2', 'var_task_pooled_main': '0/1', 'var_all_rows_baselines_main': '1/2', 'var_drop_small_main': '1/2'}, 'main_configuration': {'E1B_CQ': {'model': '0.005500', 'delivered_control': '0.005406', 'dtype_preserved_control': '0.005137', 'pass': False}, 'E1B_LO': {'model': '0.047145', 'delivered_control': '0.018050', 'dtype_preserved_control': '0.015093', 'pass': False}, 'flags_changed': ['E1-A|LO:W1->W2: False -> True', 'E3|LO:holdout:F1_RECURRENT: False -> True', 'E3|LO:holdout:F3_TS_FOUNDATION: True -> False'], 'features': 'delivered control 465 to 832, dtype-preserved control 100 to 111, model 99 to 110'}, 'agreement_with_the_team': 'the totals equal the figures of the short report of the team of 24/11 (57 of 115 delivered, 63 of 115 dtype-preserved), which the team had not delivered as a file; the three flags that change in the main configuration are those of official_seed0_dtype_preserved/folds.csv', 'five_permutations_main': 'labelled exploratory table (option --permutations 5: permutation seeds 0 to 4, each fitted with the five learner seeds of the configuration and scored as the model of record), main configuration only: equal to five_permutations_dtype_preserved/fold_summary.csv of the team in 12 of 12 folds (largest difference 8.9e-17, counts equal: True); control lower than the model in all five permutations in 4 folds (E1-A|CQ:W1->W2, E1-B|LO:W1W2->W3, E3|CQ:holdout:F1_RECURRENT, E3|CQ:holdout:F2_TS_TRANSFORMER), higher in all five in 4 folds; NOT run by the writing side for the other nine configurations (decision 62 is open)', 'bootstrap': 'verify-bootstrap PASS on the ten run directories under pandas 3.0.5 and 3.1.0: 200 rows of H1 to H4 recomputed from mm_recommendations, largest difference to mm_hypotheses 0.0e+00', 'tests': {'metamodel_0.3.1_pandas_3.0.5': '55 passed', 'metamodel_0.3.1_pandas_3.1.0': '55 passed'}, 'status_of_these_figures': 'check of the writing side. The table of record of the dtype-preserved control is the output of the code team in the environment of record (check 48); until check 48 passes no value of the dtype-preserved control is printed in the manuscript', 'post_hoc_H7_as_registered': {'definition': 'Meta-Dataset-Report Table 50, row H7, with the mapping of objectives of D-18: recommendation of L3-FS3 under PAPER_COMPOSITE_CAL (full_main_cal_time) against the recommendation of L3-FS3 under SECONDARY_MACRO_F1 (full_obj_macrof1), paired by recommendation group; difference of the change in S_san+ v2 and of the change in MacroF1; paired cluster bootstrap of the runs (B = 2000, seed 42, clusters of record)', 'primary_row': 'E1-B, both tasks, 48 clusters: difference in the S_san+ change +0.000236 [+0.000002; +0.000489]; difference in the MacroF1 change -0.0035, lower limit -0.0126 against the tolerance -0.005; supported as registered: False; the two objectives recommend the same pipeline in 15 of 48 groups', 'supported_by_role': {'PRIMARY|CQ+LO': False, 'PER_TASK|CQ': False, 'PER_TASK|LO': False, 'REPLICATION_E1A|CQ+LO': False, 'POOLED_2FOLD|CQ+LO': False}, 'implemented_row_primary': 'recommended pipeline against V0: -0.000725 [-0.001199; -0.000319], supported: False', 'sensitivity_v1_primary': 'composite v1 (full_sens_v1) against MacroF1 on S_san+ v1: +0.0438 [+0.0290; +0.0583]; MacroF1 difference +0.0021, lower limit -0.0121; supported as registered: False', 'label': 'POST_HOC (computed from delivered files after the runs of record; outside the Holm family of the delivered tables)'}, 'post_hoc_cost_at_decision_time': {'estimator': 'mean recorded log2 relative cost of the same pipeline for the same task and probe model over the training rows of the fold (main report slice); fixed before its results were computed; outcomes read with the recorded cost', 'check': 'the script replays the five H6 rows of record of the main configuration from mm_predictions with a largest difference of 0.0e+00', 'primary_row': 'E1-B, both tasks: with the recorded cost (row of record) the cost of the recommendation changes by -0.3023 log2 units (supported: True); with the decision-time estimate by +0.0542 [-0.0001; +0.1081], objective difference lower limit +0.0018; criterion of H6 met: False', 'cost_change_by_role_decision_time': {'PRIMARY|CQ+LO': '+0.0542 [-0.0001; +0.1081]', 'PER_TASK|CQ': '+0.0913 [+0.0166; +0.1679]', 'PER_TASK|LO': '+0.0171 [-0.0572; +0.0864]', 'REPLICATION_E1A|CQ+LO': '-0.0957 [-0.1992; +0.0037]', 'POOLED_2FOLD|CQ+LO': '-0.0208 [-0.0832; +0.0358]'}, 'agreement_primary_lambda_0.02': 'the rule with the estimate and the rule with the recorded cost recommend the same pipeline in 11 of 48 groups', 'anticipation_E1B': 'candidates other than V0, 768 rows: mean absolute error 0.356 log2 units against a standard deviation of the recorded log2 cost of 0.808; mean rank correlation between estimate and record within a group 0.152; cheapest candidate identified in 0% of the groups', 'reading': 'on this benchmark the relative cost of a pipeline in earlier windows does not order the candidates of a later situation, and on the verdict unit the cost saving of the rule of record does not carry over to a rule that has to anticipate cost with this estimate (on the replication fold E1-A and on the pooled unit the point estimate of the cost change is negative and its interval contains 0); the paper can claim the first reading of H6 only (a cost penalty moves the recommendation of one effect model at no loss of the objective when the cost is known)', 'label': 'POST_HOC (computed from delivered files after the runs of record; outside the Holm family of the delivered tables)'}, 'evidence': 'input/results/GD6_delivery_receipts_and_checks_20261126b/ (README.md, checks/r34b_facts.json, control_only_writing_side/, verify_bootstrap/, post_hoc/)'},
     'status_2026-11-26': 'PASSED 2026-11-24, items (a) to (e), unchanged; on 2026-11-26 the delivery items are closed (driver in the repository at acd11c1; package copied to cross_task_meta/accepted/, 387 lines in its checksum list, equal to the list of the work_in_progress package; reply of the team filed) and the finding negative_control_MQ08 of 24/11 is corrected (correction_2026-11-26); two further deviations between the design document and the package are recorded (deviations_2026-11-26)',
     'correction_2026-11-26': {'what': 'defect of metamodel 0.3.0, written by the writing side and found by the code team on 24/11: in experiment._negative_control the line perm[state_cols] = first.loc[permuted_groups].to_numpy() assigns the permuted state block as one mixed-type array, so the numeric state columns of the permuted frame become object columns and the preprocessor one-hot encodes them', 'size': '87 of 98 state columns change dtype (table of the team; the probe of the writing side counts 86 numeric columns); the control model is fitted on 465 to 832 features instead of 99 to 110; the feature counts of the three constructions (train-fitted, delivered control, dtype-preserved control) are equal between the table of the team and the probe of the writing side in 12 of 12 folds', 'consequence': "the delivered mm_negative_control tables differ from the model in two things at once (assignment of the state to the situations and encoding of the state); they are not a clean measurement of the registered control. The readings 'the permuted model has the lower regret', 'MQ08 is a scientific check that fails' and the use of MQ08 as support for the reading of C2, written by the writing side on 24/11 (finding negative_control_MQ08, decision 58, request to the team of 24/11, 03_claims D.8, 00_contributions v0.16), are withdrawn in that form", 'scope': 'confined to mm_negative_control: the code of H1 to H8, mm_metrics and mm_recommendations does not read it; the team compared a run with the control against a run without it on a reduced design (EXPLORATORY_REDUCED_E1B_L3_FS3_2trials_2seeds_B20): 12 of 12 output tables identical', 'main_configuration': {'delivered_control_passes': '5/12', 'dtype_preserved_control_passes': '6/12', 'flags_changed': {'E1-A|LO:W1->W2': 'False -> True', 'E3|LO:holdout:F1_RECURRENT': 'False -> True', 'E3|LO:holdout:F3_TS_FOUNDATION': 'True -> False'}, 'E1B': {'CQ': {'model': '0.005500', 'delivered_control': '0.005406', 'dtype_preserved_control': '0.005137', 'dtype_preserved_pass': False}, 'LO': {'model': '0.047145', 'delivered_control': '0.018050', 'dtype_preserved_control': '0.015093', 'dtype_preserved_pass': False}}, 'five_permutations_exploratory': "team, 5 permutations x 5 learner seeds: the control is lower than the model in all five in ['E1-A|CQ:W1->W2', 'E1-B|LO:W1W2->W3', 'E3|CQ:holdout:F1_RECURRENT', 'E3|CQ:holdout:F2_TS_TRANSFORMER'] and higher in all five in ['E1-A|LO:W1->W2', 'E2|CQ->LO', 'E2|LO->CQ', 'E3|LO:holdout:F2_TS_TRANSFORMER']"}, 'reading_that_stands': 'with the dtype-preserved control the verdict unit E1-B still fails in both tasks, and in LO a model fitted on permuted state has a much lower regret than the model of record; H1 and H2 are unaffected; the reading of C2 of 24/11 (the state features do not improve the recommendation on this benchmark) rests on H1, H2 and the FS0 learners, not on MQ08', 'verified_by_the_writing_side': 'the mechanism and the feature counts on the 12 folds of the main configuration; equality of the delivered control in the evidence file with the accepted table (largest difference 9.7e-17); sha256 of 8 of 9 evidence files (README.md of the folder differs from its listed hash); the delivered control passes in 57 of 115 folds over the ten configurations (file of the team equal to the accepted tables)', 'not_verified': 'the dtype-preserved control itself was not re-run by the writing side (no LightGBM or Optuna in its container); the figures of the team for the ten configurations (63 of 115 folds pass, 22 flags change) come from a table described as local and not delivered: not quotable', 'fix': 'metamodel 0.3.1: column-wise assignment that keeps the dtype of every state column (as in the script of the team), with a test; decision 59 (Q-48) fixes what the paper reports', 'evidence': 'input/results/GD6_delivery_receipts_and_checks_20261126/ (README.md, mq08_dtype/, checks/r34_facts.json, checks/mq08_dtype_probe_full_main_cal_time.json)'},
     'deviations_2026-11-26': {'cost_model_not_fitted': 'the design document (Meta-Dataset-Report, F-COST) specifies a separate model that predicts log2 of the relative cost from decision-time features; metamodel <= 0.3.0 does not fit it: the utility rule and H6 use the relative cost recorded for each candidate of the scored group (experiment.py cost_ratio_run from assemble.cost_basis_frame). H6 therefore measures how far a cost penalty moves the recommendation of one effect model and at what price in the objective, not how well cost is anticipated at the decision moment; decision 60 (Q-49)', 'H7_row': 'Table 50 registers H7 as the recommendation under the composite objective against the recommendation under a MacroF1 objective (difference of the change in S_san+ above 0 with its interval, lower limit of the difference of the change in MacroF1 at or above -eps); experiment._hypothesis_rows computes the recommended pipeline against V0 (mean change in S_san+ of the version of the objective with lower limit above 0 and lower limit of the change in MacroF1 at or above -eps). The registered comparison can be computed from mm_recommendations of full_main_cal_time and full_obj_macrof1 without a run; decision 61 (Q-50)', 'release_description': 'what release r2 does not carry, read on the tables and the column dictionary: no enrollment-level bootstrap interval; the F0 reference columns (*_ref) are filled on the ALL rows of CQ only; block Z_T holds 15 columns; s_eff takes one value per (task, window) and s_leak one value per (task, window, split, phase); the manifest of the release does not record the outcome of QA01 to QA24 (the seven row-level qa_* flags are true on the 73,440 rows). Method v0.5 describes the release accordingly'},
     'open_2026-11-26': ['decision 59 (Q-48): what the paper reports for the negative control', 'decision 60 (Q-49): cost at decision time', 'decision 61 (Q-50): H7 as registered', 'team: deliver the table of the dtype-preserved control for the 115 folds of the ten configurations and commit its script', 'writing side: metamodel 0.3.1 (explicit cluster order of first appearance with a reproduction test; dtype-preserving permutation with a test)'],
     'status_2026-11-24': 'PASSED 2026-11-24, items (a) to (e): the ten runs carry the digests frozen on 23/11, use the seed-aggregated table of release r2 and the hand-off of 21/11 unchanged, ended with exit code 0 in one environment at commit ecad59d, and every delivered table is re-derived by the writing side from the release and the delivered scores (430 hypothesis rows and 28,706 metric rows within 1.1e-16); result on the row that carries the verdict (PRIMARY): H1 is supported in none of the ten configurations and H6 in all; findings and results in acceptance_2026-11-24; open: decisions 57 and 58, push of the phase C driver, move of the package to accepted/',
     'acceptance_2026-11-24': {'delivery': 'Drive folder cross_task_meta/work_in_progress/mm_runs_phaseC_r2_20261124 (387 files in SHA256SUMS.txt; receipt of the team: rclone check --checksum of 2026-11-24 15:17 +07, 388 files equal, 0 different); 184 files held by the writing side, each equal to its sha256: the 26 files of the package level (20 console logs, RUN_LOG.md, progress.log, pip_freeze.txt, input_sha256.json, qa_phaseC_20261124.json, frozen_configurations_r2.json) and, for every configuration, mm_config.json, mm_config_sha256.txt, mm_hypotheses.csv and every parquet table (128 tables); not downloaded: 128 CSV and YAML copies of those tables and the 75 files of large_file_parts/', 'a_frozen_configurations': 'the ten mm_config_sha256.txt equal the digests frozen on 23/11 (frozen_configurations_r2), the canonical hash of the ten mm_config.json and the digest of the plan rebuilt by the writing side from each JSON (10 of 10); frozen_configurations_r2.json of the delivery is byte-equal to the file of the hand-off; the digests were issued on 23/11 before the runs (preflight of the team at 2026-11-23T10:28:57 UTC)', 'b_inputs_and_package': 'input_sha256.json names the seed-aggregated table of release r2 (26409d4e9b55..., the file verified under check 46) and the hand-off zip of 21/11 (bdcb1b3a2b4d...), 21 files of the package verified by the preflight; every mm_run_registry row: metamodel_version 0.3.0 (2026-11-21), env_id 630fd3df27b9272a, code_commit ecad59d7ea81...; pip freeze equal to that of B.5 r2 (pandas 3.1.0, numpy 2.5.4, scikit-learn 1.9.1, lightgbm 4.7.0, optuna 5.0.0); mm_hypotheses of the main configuration: 43 rows with the roles PRIMARY, PER_TASK, REPLICATION_E1A, POOLED_2FOLD and TRANSFER_E2, 32 tests in the Holm family', 'c_variants': 'V1 var_all_only_main (training on the (ALL, ALL) rows only), V2 var_task_pooled_main (one model for the two tasks: 7 folds, 238 registry rows), V3 var_all_rows_baselines_main and V4 var_drop_small_main run beside the six configurations of the primary set and named as such', 'd_runs': 'ten configurations on one release, in one environment and at one commit, exit code 0 each (33,789 to 37,053 s for the six of the primary set run together, 9,643 to 36,560 s for the four variants; 316,677 process-seconds in all); every cell of L1-L4 x FS0-FS5 and of L5-FS3 OK, no fallback model; L6-FS3 skipped in the two single-axis configurations (finding L6_skipped); cost basis TIME for the 720 groups of the main configuration; packaged with SHA256SUMS.txt, RUN_LOG.md, pip freeze, input hashes and a receipt, in work_in_progress/ until accepted', 'e_rederivation': 'by the writing side with the package of the hand-off, for each of the ten configurations: y of the 842,112 prediction rows equal to the objective column of the release (largest difference 0.0); recommendations and outcomes of the baselines recomputed from the release table (920 frames, largest difference 5.6e-17), of the learners from the delivered scores (2,966 frames, 1.1e-16) and of the baselines on the secondary slices (3,272 frames, 1.1e-16); split manifests identical and no id in TRAIN and TEST of one fold; mm_metrics (3,886 rows, 1.1e-16), mm_metrics_joint (5,408 rows, 1.1e-16), mm_metrics_secondary (19,412 rows, 5.6e-17) and mm_hypotheses (430 rows, 5.6e-17) reproduced with their intervals and p values, the clusters being taken in the order of the run of record (finding bootstrap_cluster_order); learner rows of the secondary slices are recomputed from mm_recommendations_secondary, their scores not being delivered; the 22 tables of the team report of 24/11: 1,355 cells against the delivered files, 0 different', 'findings': {'bootstrap_cluster_order': {'what': 'metamodel <= 0.3.0 takes the clusters of the cluster bootstrap in the iteration order of pandas GroupBy.indices (metrics.cluster_bootstrap_mean, metrics.paired_cluster_bootstrap); the order decides which cluster a drawn index names, so intervals and bootstrap p values depend on it while point estimates do not; on a frame concatenated from the two tasks the order differs between pandas versions', 'verified': 'the same package and the same delivered mm_recommendations give, for the primary H1 row of the main configuration, [0.006991; 0.020864] under pandas 3.1.0 (order of first appearance; the delivered interval, bit for bit) and [0.006871; 0.020676] under pandas 3.0.5 (numpy 2.5.3 and Python 3.13.18 in both)', 'size': 'the 430 rows of mm_hypotheses of the ten configurations computed under both orders: estimates equal (0.0), largest difference of an interval bound 0.0208, of a bootstrap p 0.044; supported flags different: 0; configurations with the same set of Holm rejections at 0.05: 7 of 10', 'holm_p_crossing_0.05': ['full_obj_perf POOLED_2FOLD CQ+LO H1: Holm p 0.100 in the order of record, 0.042 in the other order (supported flag unchanged)', 'full_obj_macrof1 REPLICATION_E1A CQ+LO H2: Holm p 0.080 in the order of record, 0.042 in the other order (supported flag unchanged)', 'var_drop_small_main PRIMARY CQ+LO H1: Holm p 0.060 in the order of record, 0.022 in the other order (supported flag unchanged)'], 'record': 'the values of record are those of the environment of record (pandas 3.1.0, pip_freeze.txt of the package); the re-derivation of item (e) uses the order of the run of record', 'status': 'defect of the reference package of the writing side: the cluster order has to be fixed explicitly in the next version, which will then be used for any later run; the tables of this run are not recomputed; the paper states the software versions'}, 'negative_control_MQ08': {'passes_by_configuration': {'full_main_cal_time': '5/12', 'full_sens_v1': '6/12', 'full_sens_energy': '5/12', 'full_sens_conservative': '6/12', 'full_obj_perf': '7/12', 'full_obj_macrof1': '5/12', 'var_all_only_main': '7/12', 'var_task_pooled_main': '5/7', 'var_all_rows_baselines_main': '6/12', 'var_drop_small_main': '5/12'}, 'main_configuration_rows': {'E1-A|CQ:W1->W2': {'model': 0.012772, 'permuted': 0.009844, 'B3': 0.014357, 'pass': False}, 'E1-A|LO:W1->W2': {'model': 0.006723, 'permuted': 0.006625, 'B3': 0.007655, 'pass': False}, 'E1-B|CQ:W1W2->W3': {'model': 0.0055, 'permuted': 0.005406, 'B3': 0.005248, 'pass': False}, 'E1-B|LO:W1W2->W3': {'model': 0.047145, 'permuted': 0.01805, 'B3': 0.020324, 'pass': False}, 'E2|CQ->LO': {'model': 0.025423, 'permuted': 0.026337, 'B3': 0.021197, 'pass': True}, 'E2|LO->CQ': {'model': 0.005653, 'permuted': 0.007145, 'B3': 0.007229, 'pass': True}, 'E3|CQ:holdout:F1_RECURRENT': {'model': 0.006255, 'permuted': 0.00564, 'B3': 0.004482, 'pass': False}, 'E3|CQ:holdout:F2_TS_TRANSFORMER': {'model': 0.008734, 'permuted': 0.002655, 'B3': 0.002842, 'pass': False}, 'E3|CQ:holdout:F3_TS_FOUNDATION': {'model': 0.005947, 'permuted': 0.007339, 'B3': 0.003843, 'pass': True}, 'E3|LO:holdout:F1_RECURRENT': {'model': 0.018281, 'permuted': 0.016254, 'B3': 0.012162, 'pass': False}, 'E3|LO:holdout:F2_TS_TRANSFORMER': {'model': 0.01734, 'permuted': 0.034605, 'B3': 0.020039, 'pass': True}, 'E3|LO:holdout:F3_TS_FOUNDATION': {'model': 0.010972, 'permuted': 0.016461, 'B3': 0.018552, 'pass': True}}, 'rule': 'one permutation of the state features in meta-train with learner seed 0, compared with the five-seed model; pass = regret of the permuted model not below that of the model', 'reading': "a measurement, not an execution failure: in most folds the learner does not lose when its state features are permuted; recorded as measured, no run is repeated; Table 53 of the Meta-Dataset-Report makes 'MQ01-MQ09 pass' the condition of stage MM3: the condition is not met on MQ08, as in phase A; decision 58 (Q-47)"}, 'L6_skipped': "full_obj_perf and full_obj_macrof1: 12 cells each, L6-FS3 SKIPPED with the reason 'decomposition parts ... absent': the decomposition learner needs the two log parts of a composite objective, which a single-axis objective does not have; behaviour of the package by design, as in phase A; these configurations have 33 strategies and 81,600 prediction rows", 'V1_without_secondary_tables': 'var_all_only_main has no mm_metrics_secondary and no mm_recommendations_secondary: it reads the (ALL, ALL) rows only, so there is no secondary slice; the package writes no empty table; by design', 'fitted_models_not_written': 'the table of outputs of the Meta-Dataset-Report lists mm_models/ (fitted model and preprocessor with sha256, key mm_run_id); metamodel <= 0.3.0 never writes it and no check of this registry tracked it; mm_run_registry keeps best_params, the search backend, n_features and dropped_features of every cell and mm_feature_importance the model-native importances (mean and sd over the learner seeds); SHAP values are not produced; decision 57 (Q-46)', 'conservative_oracle': 'in full_sens_conservative the oracle B0 follows the conservative rule like every strategy, so its mean regret is not 0 (at most 0.0028 on a fold); in the nine other configurations B0 has regret 0 and top-1 rate 1 on every fold; B1 recommends V0 in every group of every configuration', 'driver': "the runs were launched by a driver of the team that is not in the repository (CODE_REFERENCE['not_in_repository_2026-11-24']); the delivered digests show that the ten frozen configurations were run"}, 'results': {'reading_rule': 'estimates, intervals, p values and supported flags are those of the delivered mm_hypotheses (environment of record); for H1, H2 and H4 a negative difference of the mean regret favours the first strategy', 'main_configuration_primary_rows': ['H1 L3-FS3 - B3 (mean regret): +0.01354 [+0.00699; +0.02086], 48 clusters, Holm p 0.000; not supported', 'H2 L3-FS3 - L3-FS2 (mean regret): -0.00037 [-0.00113; +0.00026], 48 clusters, Holm p 1.000; not supported', 'H3 L3-FS3 - B2 (harm rate), non-inferiority margin +0.05: +0.18750 [+0.06250; +0.31250], 48 clusters, Holm p 0.115; not supported', 'H4 L3-FS4 - L3-FS3 (mean regret): -0.00113 [-0.00277; +0.00016], 48 clusters, Holm p 1.000; not supported', 'H6 L3-FS3 utility lambda=0.02 - lambda=0: mean log2 cost ratio (CI) and objective of the recommended pipeline: -0.30226 [-0.39971; -0.21651], 48 clusters, Holm p 0.000, objective of the recommended pipeline +0.00450 (lower bound +0.00039); supported', 'H7 composite recommendation: dS_san > 0 and dMacroF1 lower CI >= -eps: -0.00072 [-0.00120; -0.00032], macro-F1 delta of the recommended pipeline +0.01337 (lower bound +0.00107); not supported', 'H8 Spearman(imp_share, phase_index) on cluster means, expected < 0: +0.00159 [-0.51293; +0.54237], 16 clusters, Holm p 1.000; not supported', 'H8 Spearman(imp_share, tr_missing_rate) on cluster means, descriptive: -0.02803 [-0.54130; +0.50161], 16 clusters; DESCRIPTIVE, no verdict'], 'H1_primary_by_configuration': {'full_main_cal_time': '+0.01354 [+0.00699; +0.02086]', 'full_sens_v1': '+0.00997 [+0.00107; +0.02028]', 'full_sens_energy': '+0.01354 [+0.00699; +0.02086]', 'full_sens_conservative': '+0.00774 [+0.00236; +0.01402]', 'full_obj_perf': '+0.01867 [+0.00718; +0.03148]', 'full_obj_macrof1': '-0.00421 [-0.01303; +0.00452]', 'var_all_only_main': '+0.00806 [+0.00191; +0.01484]', 'var_task_pooled_main': '+0.01444 [+0.00705; +0.02219]', 'var_all_rows_baselines_main': '+0.01385 [+0.00706; +0.02125]', 'var_drop_small_main': '+0.00814 [+0.00256; +0.01465]'}, 'H1_primary_reading': 'L3-FS3 - B3 on E1-B, both tasks, 48 clusters: supported in none of the ten configurations; the interval lies entirely above 0 in 9 of 10 (the learner has the higher regret); the exception is full_obj_macrof1 (-0.00421 [-0.01303; +0.00452])', 'H1_other_rows_main': {'PER_TASK CQ': '+0.00025 [-0.00019; +0.00080]', 'PER_TASK LO': '+0.02682 [+0.01537; +0.03839]', 'REPLICATION_E1A (48 clusters)': '-0.00126 [-0.00309; +0.00043]', 'POOLED_2FOLD (96 clusters)': '+0.00614 [+0.00244; +0.01007]'}, 'primary_rows_supported_by_configuration': {'full_main_cal_time': ['H6'], 'full_sens_v1': ['H4', 'H6', 'H7'], 'full_sens_energy': ['H6'], 'full_sens_conservative': ['H2', 'H6'], 'full_obj_perf': ['H2', 'H6', 'H7'], 'full_obj_macrof1': ['H2', 'H6', 'H7'], 'var_all_only_main': ['H6'], 'var_task_pooled_main': ['H6'], 'var_all_rows_baselines_main': ['H2', 'H6'], 'var_drop_small_main': ['H2', 'H4', 'H6']}, 'H6': 'supported on the primary unit in the ten configurations', 'H5_main': ['E2 L3-FS3 - B2(source task) (mean regret) CQ->LO: -0.00057 [-0.00810; +0.00749], not supported', 'E2 L3-FS3 - B2(source task) (mean regret) LO->CQ: +0.00015 [-0.00087; +0.00109], not supported', 'both transfer directions E2-all: not supported'], 'holm_main': '32 tests in the family, 9 rejected at 0.05: PRIMARY CQ+LO H1 (direction against the hypothesis); PRIMARY CQ+LO H6 (supported); PER_TASK CQ H6 (supported); PER_TASK CQ H8 (no verdict: 4 clusters < 10); PER_TASK LO H1 (direction against the hypothesis); PER_TASK LO H6 (supported); REPLICATION_E1A CQ+LO H6 (supported); POOLED_2FOLD CQ+LO H1 (direction against the hypothesis); POOLED_2FOLD CQ+LO H6 (supported); the family counts every row with a bootstrap p that is not marked DESCRIPTIVE, the row without verdict included', 'ranking_main_primary_unit': 'mean regret of the 34 strategies on E1-B, both tasks: B0 0.0000, B2 0.0077, L3-FS0 0.0104, B6 0.0116, L1-FS0 0.0125, L2-FS0 0.0126, B3 0.0128; L3-FS3 0.0263 (rank 27); B1 0.0344 (rank 34)', 'by_task_main_E1B': {'CQ': {'B2': 0.0027, 'B3': 0.00525, 'L3-FS0': 0.00527, 'L3-FS3': 0.0055}, 'LO': {'B2': 0.01278, 'B3': 0.02032, 'L3-FS0': 0.01551, 'L3-FS3': 0.04714}}, 'cost_description_main_primary_unit': {'note': 'descriptive, derived by the writing side from delivered tables: regret and mean log2 cost ratio of the recommended pipeline (cost basis TIME, relative to V0 of the group); the row of the utility rule is the row of L3-FS3 moved by the paired differences of the H6 row (same 48 groups); no test, no interval for the derived row', 'rows': {'B1': {'mean_regret': 0.0344, 'mean_log2_cost_ratio': 0.0, 'harm_rate': 0.0}, 'B2': {'mean_regret': 0.0077, 'mean_log2_cost_ratio': -0.1207, 'harm_rate': 0.125}, 'B3': {'mean_regret': 0.0128, 'mean_log2_cost_ratio': 0.0146, 'harm_rate': 0.2083}, 'B7': {'mean_regret': 0.015, 'mean_log2_cost_ratio': -0.2003, 'harm_rate': 0.0}, 'L3-FS0': {'mean_regret': 0.0104, 'mean_log2_cost_ratio': 0.0396, 'harm_rate': 0.2083}, 'L3-FS3': {'mean_regret': 0.0263, 'mean_log2_cost_ratio': -0.0813, 'harm_rate': 0.3125}, 'L3-FS3 utility lambda=0.02': {'mean_regret': 0.0218, 'mean_log2_cost_ratio': -0.3836, 'harm_rate': None}}}, 'state_points': 'measured on the release table: 98 columns of FS3 are not in FS0 (state features); in E1-B each per-task model is trained on 4,080 rows that carry 40 distinct vectors of them (2 windows x 4 phases x 5 slices) and is scored on 4 (the four phases of W3 on the main slice); in E1-A 20 and 4; a limit of the comparison that the paper has to state', 'decision_48': "on the row that carries the verdict H1 is supported in none of the ten configurations, so the clause of decision 48 (a) ('if that run supports H1 the author revisits this decision') is not triggered: C2 is written as the registered comparison without a superiority claim, on the tables of this run", 'numbers': 'no number of this run is in the manuscript yet; each enters through 03_claims.md section B when section 5.3 is written', 'H1_rows_with_the_supported_flag_outside_the_primary_row': {'count': '2 of the 40 non-primary H1 rows of the ten configurations (per task, replication on E1-A, pooled two folds); none has a Holm p at or below 0.05', 'rows': ['var_task_pooled_main PER_TASK CQ: -0.00074 [-0.00141; -0.00011], Holm p 0.420', 'var_task_pooled_main REPLICATION_E1A CQ+LO: -0.00287 [-0.00495; -0.00083], Holm p 0.132']}}, 'evidence': 'input/results: GD7_meta_runs_phaseC_r2_20261124 (the 184 delivered files held and SHA256SUMS.txt), GD6_delivery_receipts_and_checks_20261124 (team report, receipt, QA notes, checks/check_<configuration>.json, hyp_orders_<configuration>.json, check_report_tables_r33.json, check_big_tables_r33.json, state_points_r33.json, phaseC_results_r33.json, r33_facts.json)'},
     'open_2026-11-24': ['decision 57 (Q-46): fitted meta-models and SHAP', 'decision 58 (Q-47): sensitivity analysis of the negative control', 'team: push the driver of phase C, the QA script and the splitting script; move mm_runs_phaseC_r2_20261124 to cross_task_meta/accepted/', 'writing side: fix the cluster order of the bootstrap in the next package version; propose the revised mapping table of 00_contributions.md section 2 (announced on 20/11 for after check 47); table plan T05 / T17 / T18 / F07'],
     'status_2026-11-23': 'OPEN 2026-11-23, ready to start: (a) the ten configurations are frozen for release id CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2 (key frozen_configurations_r2; the r1 set of key frozen_configurations is superseded and was never run); (b) check 46 accepted on the data and its three gates met; the runs use the hand-off of 21/11 unchanged (zip sha256 bdcb1b3a..., the package that passed B.5 r2) with run_phaseC_r2.sh of 23/11; (c)-(e) to come',
     'frozen_configurations_r2': {'metamodel_version': '0.3.0 (2026-11-21)', 'release_id': 'CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2', 'common_options': '--protocols E1-A E1-B E2 E3 --learners L1 L2 L3 L4 --extra-learners L5 L6 --n-trials 50 --learner-seeds 5', 'frozen_on': '2026-11-23', 'command': 'python -m metamodel.cli run --meta <release>/meta_dataset_seed_agg.parquet --out <dir>/<name> --release-id CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2 --protocols E1-A E1-B E2 E3 --learners L1 L2 L3 L4 --extra-learners L5 L6 --n-trials 50 --learner-seeds 5 <flags> --expect-digest <mm_config_sha256> --progress', 'runs': [{'name': 'full_main_cal_time', 'role': 'primary design, main configuration (PAPER_COMPOSITE_CAL, cost basis TIME)', 'flags': '--design full', 'mm_config_sha256': '7c17b34f6cdd17e73f664b4d710768a956967d8dc47f20081f4d2c21d1d74b2f'}, {'name': 'full_sens_v1', 'role': 'primary design, objective AccTEMPO_M3 v1', 'flags': '--design full --objective META_PRIMARY_M3_V1', 'mm_config_sha256': '65f7c9022ee2a9e5ba4dc7d98d61a449b0d81183b651d5fdd23484cd8ec87177'}, {'name': 'full_sens_energy', 'role': 'primary design, energy estimates accepted for the cost basis', 'flags': '--design full --accept-energy-estimates', 'mm_config_sha256': 'a048bb3bd423b23080d8d6d470cba46c57b487c3cff8c76b5d81df46922bca42'}, {'name': 'full_sens_conservative', 'role': 'primary design, conservative recommendation rule', 'flags': '--design full --conservative', 'mm_config_sha256': 'a4be8b576bd25c4e89147275484dc95ca657c864d1f660daa39dab3265996dac'}, {'name': 'full_obj_perf', 'role': 'primary design, objective S_perf', 'flags': '--design full --objective PAPER_PERF_AXIS', 'mm_config_sha256': 'aa76a61aacefaff21b379b72b1d0c2a75f1a52ad82a392378fc052a310e13a12'}, {'name': 'full_obj_macrof1', 'role': 'primary design, objective Macro-F1', 'flags': '--design full --objective SECONDARY_MACRO_F1', 'mm_config_sha256': '25408bf302e7780144739258c82884d6e1042330d99e58688ffb1021998b7e10'}, {'name': 'var_all_only_main', 'role': 'V1: robustness variant of Table 42 (training on the (ALL, ALL) rows) with the registered per-task folds', 'flags': '--design full --training-subgroups all-only', 'mm_config_sha256': 'f3c2e88f8505156163390232626d90fec3714b8533ab2281058054cc531a4186'}, {'name': 'var_task_pooled_main', 'role': 'V2: task-pooled E1 of Appendix E.4 on the five subgroups (decision 52 (a): labelled sensitivity)', 'flags': '--design full --e1-scope pooled', 'mm_config_sha256': '6c1382b873d1de689892f8a94c33c88858b230c06cd15df316f6dc6bad30f733'}, {'name': 'var_all_rows_baselines_main', 'role': 'V3: baselines and inner selection on every training row (decision 53: labelled sensitivity)', 'flags': '--design full --baseline-scope all-rows', 'mm_config_sha256': 'eeb15fd612f28a07326f872ea4c1167aec45ae57e8a5699182b4e99d9b1ac3b7'}, {'name': 'var_drop_small_main', 'role': 'V4: secondary rows flagged small_subgroup_flag kept out of the fits (sensitivity)', 'flags': '--design full --small-subgroups drop-from-training', 'mm_config_sha256': '2f81db5fea1e5b186240cf0315504a5f48b0dbbd9923696eefea62eac0db0ca4'}], 'note': 're-issue of the ten configurations frozen on 21/11 for the release id of the second assembly: same names, flags and common options; the digest contains meta_release_id, so the ten values change with the id and nothing else changes; computed with `run --digest-only`, which reads no table, before any run of the full design on a five-subgroup table'},
     'smoke_test_2026-11-23': {'what': 'one run of `metamodel.cli run --design full` by the writing side on the seed-aggregated table rebuilt from the 30 parts, to check that the code path of the full design accepts the real table before the team starts runs of several hours: protocol E1-B only, learner L1 only, 2 trials, 1 learner seed, container without LightGBM and Optuna; not a registered configuration', 'structure': "exit code 0 in 2m1.212s; folds ['CQ:W1W2->W3', 'LO:W1W2->W3']; 4080 training rows and 2040 test rows per fold; 12 of 12 learner cells OK; features per set {'FS0': [87], 'FS1': [123], 'FS2': [166], 'FS3': [212], 'FS4': [214, 222], 'FS5': [246, 252]}; tables written: ['mm_cost_basis.parquet', 'mm_feature_importance.parquet', 'mm_fold_composition.parquet', 'mm_metrics.parquet', 'mm_metrics_joint.parquet', 'mm_metrics_secondary.parquet', 'mm_predictions.parquet', 'mm_recommendations.parquet', 'mm_recommendations_secondary.parquet', 'mm_run_registry.parquet', 'mm_split_manifest.parquet']; ['mm_hypotheses.parquet', 'mm_negative_control.parquet'] are not written because the learners of H1-H8 are absent", 'order': 'the ten r2 digests were written before this run was started (clock of the workspace on 23/11: digest file 09:24:13, first learner cell of the smoke run 09:24:45)', 'disclosure': 'the last lines of the run log, shown once on the console of the writing side, contained seven E1-B summary lines of the LO unit of this smoke run (B7 and L1-FS0..FS5; L1 only, 2 trials, 1 seed, fallback learners). No hypothesis table is produced by this configuration (the learners of H1-H8 are absent). The ten r2 digests had been computed before this run was started; the outputs of the smoke run were then removed from the workspace and are not copied into input/results.'},
     'status_2026-11-21': "OPEN 2026-11-21: (a) decisions 52-54 answered by the author on 21/11 and the configurations frozen (key frozen_configurations) before any five-subgroup or registered per-task result exists; (b) metamodel 0.3.0 delivered; the runs start when the automated gates of check 46 pass; (c) variants V1-V4 defined; (d), (e) to come. The exploratory per-task run of the team (GRID_POLICY['execution_status_2026-11-21']['exploratory_run']) is not part of this check and has not been opened by the writing side", 'frozen_configurations': {'metamodel_version': '0.3.0 (2026-11-21)', 'release_id': 'CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r1', 'common_options': '--protocols E1-A E1-B E2 E3 --learners L1 L2 L3 L4 --extra-learners L5 L6 --n-trials 50 --learner-seeds 5', 'frozen_on': '2026-11-21', 'command': 'python -m metamodel.cli run --meta <release>/meta_dataset_seed_agg.parquet --out <dir>/<name> --release-id CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r1 --protocols E1-A E1-B E2 E3 --learners L1 L2 L3 L4 --extra-learners L5 L6 --n-trials 50 --learner-seeds 5 <flags> --expect-digest <mm_config_sha256> --progress', 'runs': [{'name': 'full_main_cal_time', 'role': 'primary design, main configuration (PAPER_COMPOSITE_CAL, cost basis TIME)', 'flags': '--design full', 'mm_config_sha256': '222ecd231a289b98b642c51368a32438a1366a5f311178cc21874ae355133143'}, {'name': 'full_sens_v1', 'role': 'primary design, objective AccTEMPO_M3 v1', 'flags': '--design full --objective META_PRIMARY_M3_V1', 'mm_config_sha256': 'c163772153777219603f4caa326a1fb713ef1095cb3943de829c2ad2e97edf8d'}, {'name': 'full_sens_energy', 'role': 'primary design, energy estimates accepted for the cost basis', 'flags': '--design full --accept-energy-estimates', 'mm_config_sha256': 'a4c91b2bf8425ab5f4bad9895b66bac105a461dff2744b67d4373accbcace12d'}, {'name': 'full_sens_conservative', 'role': 'primary design, conservative recommendation rule', 'flags': '--design full --conservative', 'mm_config_sha256': '61da1cb160cfb1cf96e9b7516a243b7582681185c68120ea02ecc68d8e156d13'}, {'name': 'full_obj_perf', 'role': 'primary design, objective S_perf', 'flags': '--design full --objective PAPER_PERF_AXIS', 'mm_config_sha256': '1279f8b30a45fb6042c7e1482c945362f9df89b1e97302e1a49a9c7230380507'}, {'name': 'full_obj_macrof1', 'role': 'primary design, objective Macro-F1', 'flags': '--design full --objective SECONDARY_MACRO_F1', 'mm_config_sha256': '38c41137b685acf47b56c1984c7d1603e98e7705e8fbc797fbefb11e4547ef7a'}, {'name': 'var_all_only_main', 'role': 'V1: robustness variant of Table 42 (training on the (ALL, ALL) rows) with the registered per-task folds', 'flags': '--design full --training-subgroups all-only', 'mm_config_sha256': 'cf2fa4c2b26ec32311700de6dec02010192c4aea8a1038958f383b5ee9db32ac'}, {'name': 'var_task_pooled_main', 'role': 'V2: task-pooled E1 of Appendix E.4 on the five subgroups (decision 52 (a): labelled sensitivity)', 'flags': '--design full --e1-scope pooled', 'mm_config_sha256': '21e16eacbfa9925d5572dee83813b2f174b71b769c5812e8306b9c18452eb8a7'}, {'name': 'var_all_rows_baselines_main', 'role': 'V3: baselines and inner selection on every training row (decision 53: labelled sensitivity)', 'flags': '--design full --baseline-scope all-rows', 'mm_config_sha256': 'eb7afcfbf170419453affbed722b7218db7fba088278fba7c93a10d9c37202a0'}, {'name': 'var_drop_small_main', 'role': 'V4: secondary rows flagged small_subgroup_flag kept out of the fits (sensitivity)', 'flags': '--design full --small-subgroups drop-from-training', 'mm_config_sha256': 'efa0300d494132ef7d53938e326dbf1c8de9b42d7df30caa1cb0af249dffed93'}]}, 'check': 'acceptance of the full-design M-15 (decision 51 (b), 2026-11-20b): (a) decisions 52, 53 and 54 are answered and the configuration (mm_config sha256) is frozen and recorded before any five-subgroup E1-B result is read; (b) the run uses the release accepted by check 46 and a release of the reference package that implements the registered primary set of Table 42 (training on the five mandatory subgroups, main report slice (ALL, ALL), secondary SEEN / UNSEEN reports), per-task E1 (section 10.10), and writes the E1-A replication rows and the 96-cluster pooled rows of section 10.8 into mm_hypotheses; (c) the ALL-only variant (Table 42, robustness) and the task-pooled variant (Appendix E.4) are run beside it and labelled; (d) six configurations on one release in the environment of record, packaged as in check 45 (g); (e) the tables of the team report re-derived from the mm_* files by the writing side', 'status': 'NOT STARTED 2026-11-20: blocked by decisions 52-54 (Q-41, Q-42, Q-43), by check 46 and by the next release of the reference package (writing side)', 'evidence': 'none yet'},
    {'id': 48, 'name': 'control-only re-run of the negative control of the ten full-design runs with metamodel 0.3.1, by the code team in the environment of record (decision 59 (b), Q-48)', 'status': 'PENDING 2026-11-26: hand-off metamodel_handoff_2026-11-26.zip and the request of 26/11 (second pass) are with the author for the code team; nothing was delivered yet', 'criteria': {'a': 'the tree of the hand-off equals its sha256 list (handoff_tree_check.txt) and the test suite of the package passes in the environment of the run (55 tests)', 'b': 'the ten commands exit 0; in every summary: verdict PASS, folds_ok = folds (12; 7 for var_task_pooled_main; 115 in all), config_sha256 equal to the frozen digest, replay_max_abs_diff and replay_model_max_abs_diff at most 1e-10, all_state_dtypes_kept true, delivered_control_permutation LEGACY_MIXED_BLOCK_UP_TO_0_3_0, metamodel_version 0.3.1', 'c': 'delivered_passes of every configuration equal to the accepted mm_negative_control table (57 of 115 in all)', 'd': 'verify-bootstrap PASS on the ten accepted run directories (difference at most 1e-12)', 'e': 'the accepted run directories are unchanged (sha256 of every file before and after the run)', 'f': 'environment record of the run (interpreter, libraries, thread variables, learner threads), pip freeze and its difference to the pip freeze of the phase C delivery, with a written statement whether the environment is the one of the phase C runs', 'g': 'the two post hoc tables of the writing side are reproduced in the environment of the run (difference at most 1e-9)', 'h': 'writing side: the delivered table equals the table of its own container run fold by fold (tolerance 1e-10), or every difference is explained before acceptance'}, 'after_acceptance': 'the values of the dtype-preserved control of the 115 folds enter 03_claims and the manuscript from the output of the team; the delivered mm_negative_control tables stay in the record as evidence of the defect and are not quoted as a measurement', 'not_part_of_the_check': 'the labelled exploratory table of several permutations (decision 62, Q-51): run only after the author confirms'},
]


def validate_release_alignment() -> None:
    """Fail loudly if the label/split registries drift from the release identities (POST_MATERIALIZE_CHECKS[9])."""
    for rid, spec in RELEASE_SPECS.items():
        task = spec['task']
        lab, spl = LABEL_ARTIFACTS[task], SPLIT_REGISTRY['tasks'][task]
        assert lab['label_rule_version'] == spec['label_rule_version'], (rid, lab['label_rule_version'])
        assert lab['label_threshold_set'] == spec['label_threshold_set'], (rid, lab['label_threshold_set'])
        for key in ('split_version', 'phase_version', 'label_rule_version', 'label_threshold_set'):
            assert spl[key] == spec[key], (rid, key, spl[key], spec[key])
        assert spl['registry_id'] == spec['split_registry_id'] and spl['release_id'] == rid, rid


def all_registries() -> Dict[str, object]:
    pipes = build_pipeline_registry()
    validate_pipeline_registry(pipes)
    validate_release_alignment()
    return {'code_reference': CODE_REFERENCE, 'release_specs': RELEASE_SPECS, 'feature_source': FEATURE_SOURCE,
            'pipeline_registry': pipes, 'model_registry': MODEL_REGISTRY, 'metric_def': METRIC_DEF,
            's_san_formula': S_SAN_FORMULA, 'acctempo_def': ACCTEMPO_DEF, 'experiment_seeds': EXPERIMENT_SEEDS,
            'grid_policy': GRID_POLICY, 'rec_rule': REC_RULE,
            'label_artifacts': LABEL_ARTIFACTS, 'split_registry': SPLIT_REGISTRY, 'sampling_strategy': SAMPLING_STRATEGY,
            'pending_decisions': PENDING_DECISIONS, 'post_materialize_checks': POST_MATERIALIZE_CHECKS,
            'author_ratifications_2026_10_24': AUTHOR_RATIFICATIONS_2026_10_24,
            'author_ratifications_2026_11_01': AUTHOR_RATIFICATIONS_2026_11_01,
            'author_ratifications_2026_11_02': AUTHOR_RATIFICATIONS_2026_11_02,
            'author_ratifications_2026_11_04': AUTHOR_RATIFICATIONS_2026_11_04,
            'author_ratifications_2026_11_06': AUTHOR_RATIFICATIONS_2026_11_06,
            'open_author_questions_2026_11_10': OPEN_AUTHOR_QUESTIONS_2026_11_10,
            'open_author_questions_2026_11_13': OPEN_AUTHOR_QUESTIONS_2026_11_13,
            'author_ratifications_2026_11_13': AUTHOR_RATIFICATIONS_2026_11_13,
            'open_author_questions_2026_11_16': OPEN_AUTHOR_QUESTIONS_2026_11_16,
            'open_author_questions_2026_11_20': OPEN_AUTHOR_QUESTIONS_2026_11_20,
            'author_ratifications_2026_11_20': AUTHOR_RATIFICATIONS_2026_11_20,
            'open_author_questions_2026_11_20b': OPEN_AUTHOR_QUESTIONS_2026_11_20B,
            'author_ratifications_2026_11_21': AUTHOR_RATIFICATIONS_2026_11_21,
            'open_author_questions_2026_11_21': OPEN_AUTHOR_QUESTIONS_2026_11_21,
            'author_ratifications_2026_11_21b': AUTHOR_RATIFICATIONS_2026_11_21B,
            'open_author_questions_2026_11_23': OPEN_AUTHOR_QUESTIONS_2026_11_23,
            'open_author_questions_2026_11_24': OPEN_AUTHOR_QUESTIONS_2026_11_24,
            'author_ratifications_2026_11_26': AUTHOR_RATIFICATIONS_2026_11_26,
            'open_author_questions_2026_11_26': OPEN_AUTHOR_QUESTIONS_2026_11_26,
            'author_ratifications_2026_11_26b': AUTHOR_RATIFICATIONS_2026_11_26B,
            'open_author_questions_2026_11_26b': OPEN_AUTHOR_QUESTIONS_2026_11_26B}


def write_registries(outdir: str) -> Dict[str, str]:
    """Write every registry as YAML (if PyYAML available) and JSON, plus registry_manifest.json with sha256."""
    os.makedirs(outdir, exist_ok=True)
    regs = all_registries()
    manifest = {'registry_revision': REGISTRY_REVISION}
    try:
        import yaml  # type: ignore
    except Exception:  # pragma: no cover
        yaml = None
    for name, obj in regs.items():
        with open(os.path.join(outdir, f'{name}.json'), 'w', encoding='utf-8') as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        if yaml is not None:
            with open(os.path.join(outdir, f'{name}.yaml'), 'w', encoding='utf-8') as f:
                yaml.safe_dump(obj, f, allow_unicode=True, sort_keys=False)
        manifest[name] = sha256_of(obj)
    with open(os.path.join(outdir, 'registry_manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)
    return manifest


if __name__ == '__main__':  # pragma: no cover
    import sys
    print(json.dumps(write_registries(sys.argv[1] if len(sys.argv) > 1 else 'registries_out'), indent=2))
