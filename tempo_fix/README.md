# tempo_fix — module tham chiếu cho các sửa đổi v1.6 của kế hoạch MDS

Bộ module này hiện thực hóa các quyết định trong `Mo_ta_meta-dataset_v1.6.docx` (bản Track Changes)
để nhóm thực nghiệm tích hợp vào pipeline hiện có (các module `temporal`, `features`, `views`, worker
imputation, trainer RNN, bước sanity hậu kiểm và các writer L2). Mọi module chỉ dùng numpy, pandas,
scikit-learn, scipy (pynvml là tùy chọn) và đều có test trên dữ liệu giả trong `tests/`.

```
pip install numpy pandas scikit-learn scipy pyyaml pytest   # pynvml chỉ cần trên worker GPU
python -m pytest tempo_fix/tests -q                          # 38 test, ~14 giây (rev 2026-11-23)
```

## Ánh xạ mục kế hoạch → module → điểm tích hợp

| Mục PLAN v1.6 | Module | Hàm chính | Tích hợp vào |
|---|---|---|---|
| §2.2 split v2, QA22 (thời điểm nhãn), lát TEMPORAL STRICT/OVERLAP, cột ngữ cảnh window | `split_v2.py` | `summarize_offerings`, `assign_blocks_v2` (cắt đều hoặc theo `boundaries`), `audit_temporal_overlap`, `qa22`, `strict_flags`, `strict_share_table`, `temporal_profile`, `duration_summary`, `choose_boundaries`, `split_manifest`; `remedy_exclusions` chỉ cho độ nhạy | `temporal.analyze_temporal_blocks` (thay bước phân tầng future pool), split registry, L2 `split_audit` |
| §2.6 is_label_proxy, audit QA23 | `feature_dictionary.py` | `build_feature_dictionary`, `regime_columns`, `imputer_predictor_columns`, `audit_label_proxy`, `qa23` | `features.build_scenario_phase_features` (xuất từ điển), worker imputation (danh sách predictor), L2 `label_proxy_audit` |
| §2.3, §2.4, §5.5, §6.10, §6.11, §12.3 registry; Bảng 4 nhãn LO V3; §2.2 split theo task | `registries.py` (`registries_rev_2026-10-12`) | `build_pipeline_registry`, `MODEL_REGISTRY`, `METRIC_DEF` v1.1 (cờ support cấp ô), `LABEL_ARTIFACTS` (LO V3 + hợp đồng proxy 19 cột), `SPLIT_REGISTRY` (lịch chung, CQ v2.2 / LO v3_catalog_normalized), `SAMPLING_STRATEGY` (số tham chiếu V3), `PENDING_DECISIONS`, `write_registries` | L0_registry (ghi một lần, sha256 vào run_manifest) |
| §2.3, §5.6 sampling_strategy cho balancer | `sampling.py` | `plan_targets`, `summarize`, `grid`, `DEFAULT_SCHEMES` | định cỡ run balancer trước khi chạy; kiểm `trpool_n_synth` sau khi chạy; nguồn số của Phuong_an_sampling_strategy.docx |
| §3.1, §3.2 seed và run_id | `seeds.py` (công thức theo cell như `model_app._role_seed`, `SEED_PREPROCESS = 20260922`) | `seed_bundle`, `derive_seed`, `derive_seed_plan_v1_6` (chỉ để đối chiếu), `run_id`, `canonical_json` | trainer, worker imputation/balancer, run_registry |
| §6.10, §6.11 thành phần sanity, S_san+ v1/v2, AccTEMPO_M3 | `sanity.py` | `compute_sanity`, `s_cal_v2`, `ece_top_label`, `leak_probe_auc`, `s_eff_from_mask`, `geometric_mean`, `acctempo_m3`, `log_decomposition` | bước sanity hậu kiểm (đọc probability matrix đã lưu), L2 `sanity_components` |
| §6.3, §6.8, Bảng 25 metric còn thiếu, bootstrap | `metrics_extra.py` | `overall_metrics`, `per_class_metrics`, `paired_bootstrap_delta` | L2 `metrics_overall`, `metrics_per_class`, `bootstrap_deltas` |
| §6.9 năng lượng NVML, cơ sở chi phí | `energy_nvml.py` | `GpuEnergyMeter`, `co2e_from_energy`, `cost_basis_for_group` | trainer (bọc train và infer từng phase), L2 `resource_usage`, khối R |
| §2.5 cờ seen/unseen, QA15 | `seen_flags.py` | `compute_seen_flags`, `subgroup_slices`, `qa15`, `seen_shares` | bước tính metric theo subgroup từ prediction table |
| §8 QA03/04/08/09/10/15/18/19/20/22/24 | `qa_checks.py` | từng hàm `qaNN_*`, `run_all` | builder L3, manifest meta-release |
| §3.1, §4.4, P2 pilot L3 | `l3_pilot.py` | `meta_key`, `meta_obs_id`, `rec_group_id`, `build_v0_rows`, `build_column_dictionary` | builder L3 |

## Chạy thử

```
# 1. Kiểm tra split hiện có (V1) và cắt lại v2 trên dữ liệu thật
python -m tempo_fix.split_v2 --enrollments <enrollments_with_labels.parquet> --out out/split \
       --audit-only-blocks <offering_block_v1.csv>            # chỉ audit V1
python -m tempo_fix.split_v2 --enrollments <enrollments_with_labels.parquet> --out out/split   # cắt v2 + QA22

# 2. Ghi registry L0
python -m tempo_fix.registries out/registries
```

Bảng enrollment cần các cột (đổi tên qua `SplitSchema` nếu khác): `enrollment_id, offering_id, course_id,
user_id, enroll_time, offering_start_date, offering_end_date, label (c0/c1/c2), timeline_source`.

Ví dụ đầu ra trên dữ liệu giả nằm trong `examples/split_v2_demo/`; registry L0 hiện hành (bản 30/09/2026, kể cả `pending_decisions.json`) nằm trong `examples/registries_v1.6/` (tạo lại dữ liệu giả bằng `python tempo_fix/examples/make_synthetic.py`).
Sửa đổi 28/09/2026 (SPLIT_V2_QA_INCIDENT_REPORT): trên dữ liệu thật, purge theo ngày bắt đầu loại 90–100%
tập đánh giá vì các offering chạy song song. Vì vậy QA22 chỉ yêu cầu thứ tự theo thời điểm nhãn (TRAIN kết
thúc trước VALIDATION/TEST) và tập đánh giá không rỗng; `ev_train_overlap_share` chỉ báo cáo; không purge;
tính hợp lệ nghiêm ngặt được đo bằng lát TEMPORAL STRICT/OVERLAP (`strict_flags`) từ dự đoán đã lưu.

## Những gì module KHÔNG làm

* Không đọc trực tiếp feature store, checkpoint hay tensor của dự án; đầu vào là DataFrame với tên cột
  theo kế hoạch.
* Không hiện thực CDSMOTE/SASMOTE/Radius-SMOTE; chỉ chốt `sampling_strategy` (IR_target) trong registry.
* Không thay thế các kiểm tra phụ thuộc artefact riêng (QA01, QA02, QA05–QA07, QA11–QA14, QA16, QA17,
  QA21); hợp đồng của chúng nằm trong CHANGE_SPEC.
Sửa đổi 30/09/2026 (`registries_rev_2026-09-30`): nhãn LO chuyển sang `lo_final_score_catalog_normalized_v3`
(REPORT_LO_V3) với bộ độ nhạy TEMPO_LEGACY_CLIP và hợp đồng proxy 19 cột; split đăng ký theo task trên cùng lịch CQ
(CQ v2.2, LO v3_catalog_normalized); QA22 = thứ tự thời điểm nhãn + hai tập đánh giá không rỗng; cờ `small_support_flag`
(n < 400, cấp ô) tách khỏi `small_subgroup_flag`; quyết định giữ offering dài kèm cột ngữ cảnh. Các điểm chưa chốt nằm
trong `PENDING_DECISIONS` và không được coi là đã khóa.
Sửa đổi 01/10/2026 (`registries_rev_2026-10-01`): nhãn LO `lo_final_score_catalog_normalized_v3_1` (loại 102 course không có
attempt ở thành phần chấm điểm, cohort 2 605 423 / 711 course); split LO `v3_1_scored_signal_excluded` với số lớp theo block;
nhóm cột current-grade (9 cột) đã khóa; bảng trần điểm mức course; PENDING 0–3 đóng, mở 6 (mẫu số catalog, chặn model LO),
7 (bốn tên cột proxy), 8 (metric xác suất cho W2, CI theo cụm offering).
Sửa đổi 01/10/2026, lần 2 (`registries_rev_2026-10-01.2`, REPORT_LO_V3_1_2 §14–§15): audit mẫu số catalog bác giả thuyết
catalog thổi phồng (active ratio p50 0.90 ở band trần < 60), nhãn V3.1 là FINAL; bốn tên cột proxy nhóm problem xác nhận;
METRIC_DEF v1.2 (log_loss và PR-AUC macro cho window exploratory, bootstrap theo cụm offering khi n_offerings_with_class ≤ 2,
`course_score_ceiling_observed` là cột ngữ cảnh chỉ để báo cáo, cấm làm đầu vào model); PENDING 6–8 đóng;
`POST_MATERIALIZE_CHECKS` liệt kê các kiểm tra còn lại của pipeline.

Sửa đổi 05/10/2026 (`registries_rev_2026-10-05`, đối chiếu repo CD3 @ `dff9a3f`): tham số imputer, balancer và mô hình lấy
đúng `release_core/runtime_config.py` (MICE 3 vòng / fit 1M dòng, ExtraTrees 1 cây sâu 5, CDSMOTE 5 cụm, SASMOTE theo inspector,
Radius-SMOTE 0.092 kèm cảnh báo fallback > 0.50, batch 2048, hidden 128, dropout 0.3, bf16 trên L4); `EXPERIMENT_SEEDS`
(master seed 42/43/44, MATCH_MASTER_SEED, 216 run S2, công thức seed theo cell, `seed_preprocess 20260922`); `GRID_POLICY`
(lưới F1 đầy đủ sau pilot L4, cách ly 51 cell LO cũ, năm job R4); `ACCTEMPO_DEF` khóa S_san+ v1 là chính, v2/s_cal là phụ;
`RELEASE_SPECS` và `FEATURE_SOURCE` (định danh release đúng chuỗi manifest, feature v2 một dòng mỗi enrollment × phase);
mọi PENDING đã đóng (0–10). `seeds.py` chuyển sang công thức đang chạy; công thức PLAN v1.6 giữ lại chỉ để đối chiếu.
Registry xuất mẫu trong `examples/registries_v1.6/` được tạo lại từ bản này.
Sửa đổi 06/10/2026 (`registries_rev_2026-10-06`, đối chiếu repo CD3 @ `c07e02c`): không đổi tham số đã khóa; `CODE_REFERENCE` trỏ
commit mới và registry thực thi `LO/registries.py registries_rev_2026-10-05_r1` (đã tiếp nhận patch 05/10c); ghi chú triển khai
`small_subgroup_flag` đóng (metrics_core theo đúng quy tắc, có regression test); `POST_MATERIALIZE_CHECKS` 9 đóng, 10 mở (tải release
kèm sidecar `materialization_lineage_*` lên Volume, patch 06/10).
Sửa đổi 12/10/2026 (`registries_rev_2026-10-12`, đối chiếu repo CD3 @ `548d4d4`): bổ sung tham số đã triển khai của F2 PatchTST
(token trộn kênh, patch 2/stride 1, 2 lớp, 4 head) và F3 MOMENT (frozen linear probe, revision ghim, mã hóa phase-as-patch
kèm thống kê RevIN sau patch 12/10 vì mã hóa đệm phải cho embedding NaN); mở hai quyết định 11 (phạm vi lưới F2/F3) và 12
(PatchTST độc lập kênh hay đổi tên); thêm check 11 (nghiệm thu F2/F3 trên L4).

## Revision 2026-10-12b (round 8: CD3 @ 640be01)

- `registries.py` -> `registries_rev_2026-10-12b`: PATCHTST row is channel-independent (team adopted decision 12 option (a));
  MOMENT rows keep the adopted phase-as-patch v2 and record the proposed v2_1 constant-channel guard; PENDING 12 closed,
  11 still open (team proposal and its Radius/SASMOTE inconsistency recorded), 13 added (VastAI execution backend);
  POST_MATERIALIZE_CHECKS 11 updated, 12 added (Modal-vs-VastAI equivalence). Row-specific values now take precedence over
  the F1 defaults of COMMON_HPARAMS (previously the F1 model_revision overwrote the F2/F3 rows in the export).
- Exports regenerated in `examples/registries_v1.6/`; tests: 26 passed.

## Revision 2026-10-13 (round 9: CD3 @ 813e7ea)

- Team adopted the constant-channel guard (MOMENT v2_1), the contract/registry alignment and the F3 core/sensitivity split
  (SASMOTE in the core, Radius-SMOTE as sensitivity). PATCHTST revision `patchtst_channel_independent_v2_1_math_sdp`.
- Not adopted: the VastAI runner fixes (vocabulary from release_core, CUBLAS env, GPU gate, provenance) although the README now
  describes them; re-issued as `review_patches_2026-10-13.patch` together with a scoped `sdpa_kernel` for PatchTST.
- PENDING 11 still awaits the author's ratification (cost note added: CQ has 274 dynamic channels); 13 unchanged.

## Revision 2026-10-13b (round 10: CD3 @ b5f55fe, BAO_CAO_PATCHTST_2026-10-13)

- Team adopted review patch 2026-10-13 (scoped math-SDP, VastAI provenance/vocabulary) and reported a bit-identical PatchTST
  A/B pilot, but at batch 512 on the portable backend; PENDING 14 (batch policy) and 13 (backend) opened/updated, check 13 added.
- `review_patches_2026-10-13b.patch`: gradient accumulation (registered 2048 kept), per-seed balanced TRAIN in the portable
  tree with a MATCH_MASTER_SEED check, epoch timings in train_history.

## Revision 2026-10-14 (round 11: CD3 @ be110a4)

- Team adopted review patch 2026-10-13b verbatim (gradient accumulation, per-seed balanced TRAIN + MATCH_MASTER_SEED check,
  epoch timings) and deferred MOMENT_SMALL until the F2 grid completes. `review_patches_2026-10-14.patch` only declares the
  accumulated batch in the registry row and the README commands. Decisions 11, 13, 14 still await the author.

## Revision 2026-10-15 (round 12: consolidated execution reports CQ/LO)

- No new commit (be110a4). PatchTST pilot repeated at the registered 2048 = 4 x 512 (PASS per report, evidence pending).
  LO F1 seed 42 exists as 204 VastAI cells: PENDING 13 urgent with a proposed Modal-vs-VastAI equivalence test; 15 added
  (energy/time basis, W1-primary tables); check 14 added (LO promotion conditions). No number from the reports enters 03_claims.

## Revision 2026-10-15b (round 13: CD3 @ 294a17d, REPORT_LO_V2_EXECUTION_L2_INGESTED)

- VastAI tooling, power sampler, portable audit, L2 ingest and export reviewed; `review_patches_2026-10-15.patch` fixes the
  null resource rows (contract has no resources section), adds uniform runner/GPU assertions, per-seed grid trees and a grain
  verifier. Decision 13 now has equivalence evidence (LO/W1/V0/RNN/42 bit-identical). Check 15 added: LO W1/P1 TEST at chance
  versus VALIDATION 0.39-0.53 must be explained before any LO W1/P1 claim.

## Revision 2026-10-17 (round 14: REPORT_CQ/LO_FULL_E2E_SEED42_2026-10-16; repository unreachable)

- The CD3 repository could not be read from the review session (403 / not listed: private or renamed). Commits after
  294a17d are not reviewed; `CODE_REFERENCE.access_note_2026-10-17` records this and the two pending review patches.
- `review_patches_2026-10-17.patch` (on 294a17d): `tools/audit_static_columns.py` makes the static set that
  `model.data.fit_layout` selects by exclusion explicit and scores constancy, offering-level constancy/ICC, label association,
  TRAIN->eval shift and allowlist status (`--strict`); test added. LO registry note corrected (the single-offering E cell is W1
  TEST) and `n_checkpoints_within_margin` documented as 2 by construction.
- Reports: CQ F1 seed 42 now 51 Modal + 153 VastAI cells (batch 512 in the resource table, two runner sha256); LO 204 cells with
  resources. Decisions 16 (CQ batch 512), 17 (LO W1 reporting after the single-offering diagnosis), 18 (AccTEMPO driven by
  s_ent) added; checks 16-18 added; check 15 updated with the per-phase evidence (gap grows P1->P4, TEST at the majority
  reference). `derived_minority_shares_pct` added to the LO split entry. No number from the reports enters 03_claims.

## Revision 2026-10-17b (round 14, part 2: CD3 public again, reviewed to d449831)

- Nine commits after 294a17d read: review patch 2026-10-15 adopted in 20de6db (four files verbatim, ingest/exporter extended);
  ingest and export generalised to CQ (VASTAI_TASK / VASTAI_FAMILIES / VASTAI_INGEST_ID, ingest_id partition); canonical
  S_leak overlay fix; `tools/audit_prefix_validation_alignment.py` and `tools/export_w1_phase_validation_test_table.py`
  (W1 diagnostics); `split_rule_version` excluded in `model.data`. Two tests fail at d449831 (modal stub lacks `Image.env`).
- `review_patches_2026-10-17b.patch` (on d449831, supersedes 2026-10-17): `STATIC_FEATURE_CONTRACT` in `LO/registries.py`
  (15 fields, dispositions, course fingerprint) read by the alignment audit; dual macro-F1 convention and `--full-scan`;
  `tools/probe_static_only.py`; `tools/audit_static_columns.py --allowlist-from-registry`; stub fix; 26 tests pass.
- Registry: CODE_REFERENCE d449831; decision 19 (disposition of timeline_source / window_duration_seconds) and check 19
  (audit code behind reported evidence not in the repository: vastai_audit_w1.py, CQ appendix scripts, report merger,
  CQ launcher invocation); checks 14-18 updated with what the code now shows; decision 16 sharpened (manifest batch_size
  is the optimisation batch by construction).

## Revision 2026-10-19 (round 15: CD3 @ 6fd6315, REPORT_CQ/LO_TONG_HOP_DAY_DU_SEED42_2026-10-19)

- Review patch 2026-10-17b adopted and extended by the team (alignment audit with `--task CQ` and salted-hash cohort join,
  provisional CQ static contract, slice facts with the parent contract and an ALL == sanity ingest check, `runner_git_commit`,
  `vastai_audit_w1.py` committed). CQ LSTM/GRU/BiLSTM rerun at batch 2048 (153 cells, one runner, NVML estimates 153/153,
  selection rule 153/153, W1/V0 replay prefix-safe); decision 16 resolved by rerun, batch effect measured (AccTEMPO +0.002 to
  +0.006; macro-F1 ranking of pipelines changes, Spearman 0.26-0.68).
- Static-only probes delivered for both tasks: LO W1 course fingerprint recalls 76% of E on VALIDATION and 0% on TEST
  (offering-identity shortcut); decision 20 (static branch policy for future grids) added; check 20 (CQ W2 phase decline
  needs macro-F1/s_ent at window x phase grain) and check 21 (slice partition invariant) added.
- `review_patches_2026-10-19.patch` (on 6fd6315): STRICT + OVERLAP confusion matrices must sum to ALL;
  `tools/export_window_phase_tables.py`; tests (34 pass).

## Revision 2026-10-23 (round 17: CD3 @ 5b14052, REPORT_CQ_CURRENT_RECURRENT_PATCHTST_V0_SEED42_2026-10-23)

- Review patch 2026-10-21 adopted in 7886a85 and extended: `meta_storage.release_identity_aliases` names the CURRENT and the
  LEGACY_WITH_LINEAGE identity, every CQ Modal exporter classifies a manifest and raises on an unknown identity, a Modal
  ledger app writes `ledger.json` per task. Check 22 is closed in code; the ledger scan counts are still to be delivered.
- 5b14052 writes `CQ_METRIC_AND_QA23_POLICY` into `CQ/registries.py` (M3 primary in the meta-dataset, paper trends on
  S_perf / macro-F1 / balanced accuracy, M4 sensitivity, QA23 eight bases approved) and exports the per-phase QA23 linkage.
  Decision 18 is READY FOR RATIFICATION (the team policy equals the 21/10 recommendation); decision 21 (b) is implemented at
  summary grain (|rho| max 0.61 -> 0.88 from P1 to P4) and needs the per-base table plus the label-construction note.
- PatchTST V0 pilot (3 runs, seed 42): at parity with the recurrent V0 cells on macro-F1 (-0.002 mean over 12 TEST cells);
  M3 differences are s_ent differences again; W3 selected epoch 1 of 6; VALIDATION - TEST on W2 reaches +0.11 at P4.
  New decision 22 (F2 grid launch for CQ: recommendation (b), evidence first, no rerun) and check 24 (pilot provenance).
  R4 export equals R3 to 1e-4 and now carries M4, the full sanity contract, per-class and bootstrap facts (check 23).
- `review_patches_2026-10-23.patch` (on 5b14052): report builder reads the F2 protocol from the run manifests and fails on a
  deviation, `best_score` fix (blank Score VAL), provenance and per-epoch tables; identity-acceptance tests (52 pass).

## Revision 2026-10-21 (round 16: CD3 @ eb80516, REPORT_CQ_TONG_HOP_HOAN_CHINH_SEED42_2026-10-21)

- Review patch 2026-10-19 adopted (stricter: null strict flags refused). CQ RNN rerun on VastAI with the historical static
  layout: four families on one backend, 204/204 NVML estimates, slice partition invariant 0 violations, R3 export at the
  registered grain (1,632 cells). RNN Modal vs VastAI agree to 1e-4 on 51 window-level means: decision 13 ready to ratify.
- Check 20 closed as explained: macro-F1 and balanced accuracy rise P1 -> P4 in every window while s_ent falls, so the
  AccTEMPO decline is the composite's entropy term; decision 18 now recommends S_perf / macro-F1 plus AccTEMPO_M4 for every
  trend or ranking statement. Checks 16, 19, 21 closed; checks 22 (data_release_id ledger after eb80516's identity change)
  and 23 (CQ exports into input/results/) added; decision 21 (QA23 reviewed prefix list) added; decision 20 awaits the LO
  ablation numbers (the team's text: V0 VALIDATION does not fall without statics, V8 does).
- `review_patches_2026-10-21.patch` (on eb80516): `tools/release_identity_ledger.py` + tests (37 pass).

## Revision 2026-11-13b (round 28b: check 42 on the copied packages; author answers of 13/11)

- `POST_MATERIALIZE_CHECKS[42]`: status `PASSED 2026-11-13` with `result_2026-11-13` (a)-(e); the 4.98e-5 of round 27 traced to the rounded report-derived CSV (the 03/11 facts are at 1.24e-5, as the r2 summary states); reading of (d) ratified by the author.
- `POST_MATERIALIZE_CHECKS[38]`: `status_2026-11-13_verified` (identity 0.0 / <= 1.1e-16 on the copied files).
- `OPEN_AUTHOR_QUESTIONS_2026_11_13['Q-14']`: `executed_by_author`, `status` CLOSED 2026-11-13.
- Patch script: `Progress/Ver 3/2026-11-13_M15_seed43_receipts/_build/patch_registry_r28b_check42.py`. Tests: 32 passed (`test_registries_round28b_check42`). Export `examples/registries_v1.6/` regenerated: only `post_materialize_checks.*`, `open_author_questions_2026_11_13.*` and `registry_manifest.json` changed.

## Revision 2026-11-26b (round 34, second pass: decisions 59 (b), 60 (a), 61 (a); metamodel 0.3.1; check 48 opened; decision 62 opened)

- `REGISTRY_REVISION = 'registries_rev_2026-11-26b'`; no locked parameter changes.
- `PENDING_DECISIONS`: 59, 60 and 61 get `ratified_2026-11-26` ((b), (a), (a)); their options and status of the first pass are kept as written; new 62 (Q-51: labelled table of several permutations for the negative control), OPEN.
- `POST_MATERIALIZE_CHECKS`: **47** gets `followup_2026-11-26b` (metamodel 0.3.1; run of the writing side on the ten delivered run directories, not the environment of record; the two labelled post hoc analyses: H7 as registered, cost at the decision moment); new **48** (control-only re-run of the negative control by the code team with metamodel 0.3.1; criteria (a) to (h); PENDING).
- `CODE_REFERENCE['review_2026-11-26b']`: state of the public repository (no licence, no release, analysis package and data not in the repository).
- New `AUTHOR_RATIFICATIONS_2026_11_26B` (three decisions, six answers) and `OPEN_AUTHOR_QUESTIONS_2026_11_26B`; `GRID_POLICY['execution_status_2026-11-26b']`.
- Tests: 41 (one new: `test_registries_rev_2026_11_26b_second_pass_decisions_and_check_48`). Export `examples/registries_v1.6/` regenerated (75 files). Patch script: `Progress/Ver 3/2026-11-26b_Handoff_metamodel_0.3.1/_build/patch_registry_r34b.py`.

## Revision 2026-11-26 (round 34: author answers of 24/11 and 26/11, repository at acd11c1, correction of the MQ08 finding, decisions 59 to 61 opened)

- `REGISTRY_REVISION = 'registries_rev_2026-11-26'`; no locked parameter changes.
- `CODE_REFERENCE` moves to `acd11c1` (`review_2026-11-26`, `commits_reviewed_2026-11-26`, `resolved_since_2026-11-24`, `not_in_repository_2026-11-26`; `previous_reference` is now ecad59d and the former one is kept as `previous_reference_2026-11-24`).
- `POST_MATERIALIZE_CHECKS`: **46** gets `status_2026-11-26` (CLOSED) and `closure_2026-11-26`; **47** gets `status_2026-11-26`, `correction_2026-11-26` (dtype defect of the negative control of metamodel 0.3.0; the readings of 24/11 that used MQ08 are withdrawn in that form), `deviations_2026-11-26` (cost model not fitted, H7 row, description of the release) and `open_2026-11-26`. The entries of 24/11 are kept as written.
- `PENDING_DECISIONS`: 57 and 58 get `ratified_2026-11-24` ((a), (a)); 58 gets `premise_withdrawn_2026-11-26`; new 59 (Q-48: negative control), 60 (Q-49: cost at decision time), 61 (Q-50: H7 as registered), all OPEN.
- New `AUTHOR_RATIFICATIONS_2026_11_26` (two decisions, twelve answers, four instructions) and `OPEN_AUTHOR_QUESTIONS_2026_11_26`; `GRID_POLICY['execution_status_2026-11-26']`.
- Known defects of metamodel <= 0.3.0 recorded for 0.3.1: cluster order of the bootstrap (24/11) and dtype of the permuted state block in the negative control (26/11). Neither changes a row of H1 to H8.
- Tests: 40 (one new: `test_registries_rev_2026_11_26_author_answers_and_mq08_correction`). Export `examples/registries_v1.6/` regenerated.

## Revision 2026-11-24 (round 33: repository at ecad59d, check 46 closed, acceptance of phase C (check 47), decisions 57 and 58 opened)

- `REGISTRY_REVISION = 'registries_rev_2026-11-24'`; no locked parameter changes.
- `CODE_REFERENCE` moves to `ecad59d` (`review_2026-11-24`, `commits_reviewed_2026-11-24`, `not_in_repository_2026-11-24`, `resolved_since_2026-11-23`; `previous_reference` is now fc361b6 and the former one is kept as `previous_reference_2026-11-21`).
- `POST_MATERIALIZE_CHECKS`: **46** gets `status_2026-11-24` (PASSED, items (a) to (f)), `closure_2026-11-24` (code pushed; the two tables above 10 MB verified by sha256) and `open_2026-11-24`; **47** gets `status_2026-11-24` (PASSED, items (a) to (e)), `acceptance_2026-11-24` (delivery, the five items, `findings`, `results`) and `open_2026-11-24`.
- `PENDING_DECISIONS`: new 57 (Q-46: fitted meta-models and SHAP) and 58 (Q-47: sensitivity analysis of the negative control), both OPEN.
- New `OPEN_AUTHOR_QUESTIONS_2026_11_24`; `GRID_POLICY['execution_status_2026-11-24']`.
- Known defect of metamodel <= 0.3.0 recorded (finding `bootstrap_cluster_order`): the cluster order of the bootstrap follows pandas `GroupBy.indices`; the tables of record are those of the environment of record.
- Tests: 39 (one new: `test_registries_rev_2026_11_24_phase_c_acceptance`). Export `examples/registries_v1.6/` regenerated (67 files).

## Revision 2026-11-23 (round 32: Q-44 (a) and Q-45 (a) written in, acceptance of phase B, frozen configurations for release r2)

- `REGISTRY_REVISION = 'registries_rev_2026-11-23'`; no locked parameter changes; `CODE_REFERENCE` stays at fc361b6 (`review_2026-11-23`: origin/main unchanged, the code of phase B is not pushed, three delivered copies read).
- New `AUTHOR_RATIFICATIONS_2026_11_21B` (decisions 55 (a) = Q-44 and 56 (a) = Q-45 of the second pass of 21/11; Q-45 restated on 23/11) and `OPEN_AUTHOR_QUESTIONS_2026_11_23` (no new question; open: Q-20 to Q-24, Q-26). The blocks of the first pass of 21/11 are kept as written.
- `PENDING_DECISIONS`: key `ratified_2026-11-21` on 55 and 56 (`status` kept).
- `POST_MATERIALIZE_CHECKS`: **46** gets `status_2026-11-23` (PASSED on the data, items (a) to (e); item (f) open: code not in the repository), `acceptance_2026-11-23` (figures read from the files by the writing side) and `open_2026-11-23`; **47** gets `status_2026-11-23`, `frozen_configurations_r2` (ten digests for release id `CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2`; the r1 set of `frozen_configurations` is superseded and was never run) and `smoke_test_2026-11-23`.
- `GRID_POLICY['execution_status_2026-11-23']`.
- Tests: 38 (one new: `test_registries_rev_2026_11_23_phase_b_acceptance`). Export `examples/registries_v1.6/` regenerated (65 files).

## Revision 2026-11-21 (round 31: author decisions on the full-design run, acceptance of the three-seed re-issue, frozen configurations)

- `REGISTRY_REVISION = 'registries_rev_2026-11-21'`; no locked parameter changes; `CODE_REFERENCE` moves to fc361b6 (four commits of 21/11, 42 files under tools/ and docs/; `commits_reviewed_2026-11-21`, `review_2026-11-21` with its `open` list).
- `AUTHOR_RATIFICATIONS_2026_11_21`: decisions 52 (a), 53 (a), 54 (b) [Q-41, Q-42, Q-43]; `confirmations` (the three conventions of the facts contract; the reading of decisions 48 and 51); `implementation` (how metamodel 0.3.0 carries each decision); `readings_recorded_by_the_writing_side`; `state_of_knowledge_at_the_decision`.
- `PENDING_DECISIONS`: `ratified_2026-11-21` on 52-54; new **55** (Q-44: the secondary SEEN / UNSEEN slices as reports outside the Holm family, or as tests inside it) and **56** (Q-45: a statement of fact on the exploratory per-task run). `OPEN_AUTHOR_QUESTIONS_2026_11_21`.
- `POST_MATERIALIZE_CHECKS`: `status_2026-11-21` on 39, **45 (PASSED)**, 46 (PARTIAL: pilot unit confirmed; `requests_2026-11-21`) and 47 (OPEN; `frozen_configurations`: the release id, the common options and the mm_config sha256 of the ten runs of the full design).
- `GRID_POLICY['execution_status_2026-11-21']` (decisions, base_tier, meta_phase_A, meta_phase_B, meta_phase_C, exploratory_run, package, numbers).
- `all_registries()` has 30 keys; 37 tests (`test_registries_rev_2026_11_21_author_decisions`); export `examples/registries_v1.6/` regenerated (61 files).
- The companion package `metamodel` moves to 0.3.0 (`run --design full`; the default options compute what 0.2.6 computes).

## Revision 2026-11-20b (round 30, second pass: the six author decisions of 20/11 and the preparation of the five-subgroup design)

- `REGISTRY_REVISION = 'registries_rev_2026-11-20b'`; no locked parameter changes; `CODE_REFERENCE` stays at 6274591 and gains `subgroup_tooling_2026-11-20b` (what the repository holds for the five mandatory subgroups: the ALL/STRICT/OVERLAP slice function, the COURSE x TEMPORAL cohort audit, no LEARNER slice).
- `AUTHOR_RATIFICATIONS_2026_11_20`: decisions 46 (b), 47 (a), 48 (a), 49 (a), 50 (a), 51 (b) [Q-35 to Q-40], with `corrections` (four statements of decision 51 that were wrong or incomplete: the cohort audits do not hold the four slices; E1-B is scored on 48 situations in the registered design as well; the executed analysis is the robustness variant of Table 42; the effort of option (b)) and `consequences`.
- `PENDING_DECISIONS`: `ratified_2026-11-20` on 46-51, `correction_2026-11-20b` on 51; new **52** (Q-41: per-task or task-pooled E1 as the primary reading), **53** (Q-42: baselines and inner selection on the matched slice or on all subgroups), **54** (Q-43: Holm family once the replication and pooled rows are written). `OPEN_AUTHOR_QUESTIONS_2026_11_20B`.
- `POST_MATERIALIZE_CHECKS`: `status_2026-11-20b` on 39 (item 2 as ratified) and 45 (re-issue with metamodel 0.2.6 in the PC environment; item (i) moved out); new **46** (five-subgroup facts and release, with the three conventions s_leak / undefined slice / row order) and **47** (full-design M-15), both NOT STARTED.
- `GRID_POLICY['execution_status_2026-11-20b']` (decisions, base_tier, meta, package, numbers).
- `all_registries()` has 28 keys; 36 tests (`test_registries_rev_2026_11_20b_author_decisions`); export `examples/registries_v1.6/` regenerated (57 files).
- The companion package `metamodel` moves to 0.2.6 (five-subgroup input checked at assembly; `run` unchanged).

## Revision 2026-11-20 (round 30: CD3 @ 6274591; BAO_CAO_TONG_HOP_SEED42_43_44_2026-11-20; six seed-44 facts packages, the three-seed meta release and the three-seed M-15 copied from the Drive and checked)

- `REGISTRY_REVISION = 'registries_rev_2026-11-20'`; `CODE_REFERENCE` at 6274591 with `commits_reviewed_2026-11-20` (three commits of 19-20/11, tools only), `review_2026-11-20` (verdict + 4 notes), `not_in_repository_2026-11-20` (8 items), `resolved_since_2026-11-16`; `previous_reference` = cb575df, `previous_reference_2026-11-16` = 7cad8b1.
- `GRID_POLICY['execution_status_2026-11-20']`: seed 44 COMPLETE for both tasks; base tier complete on the three registered seeds (1,836 runs, 14,688 sanity rows); the three-seed release and M-15 with the measured hypothesis results; the sens_energy defect of metamodel 0.2.4; the cross-machine comparison; the citation rule for the three-seed numbers.
- `PENDING_DECISIONS`: `status_2026-11-20` on 36, 42, 43, 44, 45, 46, 47; new **48** (Q-37: position of C2, C3, C4 after the three-seed M-15), **49** (Q-38: energy of the 8 seed-44 cells without a measurement), **50** (Q-39: environment of record of the meta-tier runs), **51** (Q-40: design scope of the meta tier, one subgroup instead of five and task-pooled E1 folds). `OPEN_AUTHOR_QUESTIONS_2026_11_20`.
- `POST_MATERIALIZE_CHECKS`: `status_2026-11-20` on 22, 36, 38, 39, 41; new **44** (six seed-44 packages, PASSED) and **45** (three-seed release and M-15, PARTIAL with the closing condition).
- `all_registries()` has 26 keys; 35 tests (`test_registries_rev_2026_11_20_round30`); export `examples/registries_v1.6/` regenerated (53 files).
- The companion package `metamodel` moves to 0.2.5 on the same day (cost basis follows the run configuration; estimate fills an empty run-energy column; energy basis on the aggregated table needs every planned seed).

## Revision 2026-11-16 (round 29: CD3 @ cb575df; BAO_CAO_TONG_HOP_SEED42_43_2026-11-16_M4; six seed-43 facts packages copied from the Drive and verified)

- `REGISTRY_REVISION = 'registries_rev_2026-11-16'`; `CODE_REFERENCE` at cb575df with `commits_reviewed_2026-11-16` (five commits of 13/11: audit copy-reference default, full42 packaging, Q-28 wording, check 41 tolerance 1e-3, reply 13/11), `review_2026-11-16` (verdict + 3 notes), `uncommitted_tools_2026-11-16` (the 15-16/11 tooling of the seed-43 packages); `previous_reference` = 7cad8b1, `previous_reference_2026-11-13` = 193b584.
- `GRID_POLICY['execution_status_2026-11-16']`: seed 43 COMPLETE for both tasks (six packages, 408/51/51 each, identity <= 1.1e-16, runner commit 5ba9829 at run time for F1/PatchTST, Mantis retroactive 6a69b7f), seed-44 status, the 0.2.4 acceptance (58 columns filled on the CQ F1 rows of the p1 release), the seed-43 evidence copied (receipts, identity scan, M-18, M-08 ledgers), citation rule for seed-43 numbers.
- `PENDING_DECISIONS`: `status_2026-11-16` on 36, 42, 43, 44, 45; new **46** (Q-35: use of seed 43/44 in the phase-1 submission; cell-level agreement vs ranking instability) and **47** (Q-36: variant_role NULL on PRIMARY_GRID facts), both OPEN, recommendation (a).
- `OPEN_AUTHOR_QUESTIONS_2026_11_16` (Q-35, Q-36, still_open Q-20..Q-24, Q-26); `all_registries()` has 25 keys.
- `POST_MATERIALIZE_CHECKS`: `status_2026-11-16` on 22 (CLOSED: M-08 ledgers delivered, no UNMATCHED), 36, 37, 38 (PASSED on the seed-43 packages), 39, 41; new **43** (verification of the six seed-43 packages: hashes, identity, formulas, coverage, report reproduction, labels, resources) PASSED 2026-11-16.
- Patch script: `Progress/Ver 3/2026-11-16_Seed43_facts_verified/_build/patch_registry_r29.py` (applies to rev 2026-11-13_r2). Tests: 34 (`test_registries_rev_2026_11_16_round29`; earlier tests follow the moved base commit and the new counts). Export `examples/registries_v1.6/` regenerated (51 files, manifest sha256 96b5c1e4...72c6).

## Revision 2026-11-13_r2 (rounds 28b and 28c: check 42 on the copied packages; author ratifications of 13/11)

- Round 28b: `POST_MATERIALIZE_CHECKS[42]` PASSED with `result_2026-11-13` (hashes, check 38 identity, r2_changes, release comparison, re-derived hypotheses); check 38 `status_2026-11-13_verified`; Q-14 closed. Correction: the 4.98e-5 of 2026-11-10 was measured on a report-derived file with rounded s_leak, not on the facts (1.24e-5).
- Round 28c: `REGISTRY_REVISION = 'registries_rev_2026-11-13_r2'`; `AUTHOR_RATIFICATIONS_2026_11_13` (decisions 38 (a), 39 (c), 41 (b), 42 (a), 43 (a), 44 (a), 45 (a)); `ratified_2026-11-13` on those decisions (base `status` keys kept); check 36 `verified_2026-11-13`; `GRID_POLICY['execution_status_2026-11-13']['numbers_after_ratification']`; `all_registries()` has 24 keys.
- Tests: 33. Export `examples/registries_v1.6/` regenerated (49 files).

## Revision 2026-11-13 (round 28: CD3 @ 7cad8b1; PHAN_HOI_YEU_CAU_10-11_2026-11-13; Drive deliveries of 10-13/11 read, not copied)

- `REGISTRY_REVISION = 'registries_rev_2026-11-13'`; `CODE_REFERENCE` at 7cad8b1 with `commits_reviewed_2026-11-13` (15 tooling commits), `review_2026-11-13` (verdict + 5 notes), `team_registry_revision_2026-11-13`, `not_copied_2026-11-13`; `previous_reference` = 193b584, `previous_reference_2026-11-10` = 421dbcd.
- `GRID_POLICY['execution_status_2026-11-13']`: M-15 phase 1 delivered (six configurations; the primary configuration supports none of H1-H8 at seed 42), release re-assembled on 12/11, seed-43 progress as reported by the team, nothing of 10-13/11 citable yet.
- `PENDING_DECISIONS`: dated status on 36 (gate met by date), 42 (option (a) executed by the team; probe-mode evidence), 43 (team asks to accept the retroactive basis); new **44** (Q-33: presentation of C2-C3 after M-15) and **45** (Q-34: restatement of H8, minimum clusters), both OPEN.
- `OPEN_AUTHOR_QUESTIONS_2026_11_13` (Q-14, Q-27, Q-28, Q-30...Q-34); `all_registries()` now has 23 keys.
- `POST_MATERIALIZE_CHECKS`: dated status on 36, 37, 38, 39, 41; new **42** (independent verification of the 10-13/11 packages once copied).
- Tests: 31 (`test_registries_rev_2026_11_13_round28`; earlier tests follow the moved base commit and the new counts). Export `examples/registries_v1.6/` regenerated (47 files, manifest sha256 c4fcb988...).

## Revision 2026-11-10 (round 27: CD3 @ 193b584; PHAN_HOI_REVIEW_YEU_CAU_09-11_2026-11-10; Drive deliveries of 09-10/11)

- `CODE_REFERENCE` -> `193b584` (six commits of 10/11, static review). ea19afa makes the leak probe deterministic (`PROBE_CONFIG`
  lbfgs, C 1.0, tol 1e-4, max_iter 500; `fit_missingness_probe(..., deterministic=True)` under one BLAS thread; `probe_environment()`)
  and adds the audit assertion `--s-leak-reference` / `--s-leak-tolerance` (default 1e-9) with manifest blocks `probe_config`,
  `probe_environment`, `s_leak_check` (4 tests). 8c3fd80 adds the LO r2 recomputation tool, the meta-release combiner and acceptance
  checker, the S0 v4 and Z_M v2 builders, the determinism-pilot tools and the facts-of-record verifier. ba5c1c6 adds the runner-commit
  inventory (LO: 38-file host directory vs the repository history, 37 equal, earliest match df2a867; Mantis: runner blob 2cc8e3f8... =
  6a69b7f, V0 NULL) and the byte-level delivery receipts. f478b23 adds the real-data probe reproduction check. 8cf8b9b brings the 34
  f3_mantis package tests and 6 DedupZstdStore tests into `tests/`, the D-18 objective mapping into the team `METRIC_DEF`
  (`test_metric_def_maps_the_paper_objectives_d18`), cleans the `MANTIS_V2` row (licence, pretraining data, references) and records the
  ACELO `with_comment` provenance (30,231 enrollments, 0.95 %, not reproduced by the builder in the repository). 193b584 is operational.
  Dropped from `not_in_repository`: the 34 tests, the deterministic probe, the runner commits, the hand-off bundle (M-14 done), Z_M MANTIS
  row, S0 v4, LO r2. Still missing on the Drive: the check 37 (c) bench output and the (d) W1/V0 pilot reports of CQ and LO, the probe
  reproduction report (CQ W1/V0, 2.09e-6, 43 iterations), the LO Mantis facts package, M-15, every phase-2 cell.
- `GRID_POLICY.execution_status_2026-11-10`: M-14 assembled by the team on 09/11 17:04 UTC with metamodel 0.2.1 and `registries_v1.6`
  (manifest sha256 e1fdb8e3... = writing side): `meta_release_CQ_LO_p1_F2V0V16_20261109`, 3,672 seed-level rows (CQ 2,040 = F1 1,632 +
  PatchTST V0-V16 408; LO 1,632), 545 columns, cohort FIXED, S0 v4 on every row, F0 CQ on 2,040 rows, QA rates 1.0 except
  `qa_run_level_invariant_ok` 0.0 (metamodel 0.2.1 counted s_leak as run-level; s_eff constant in all 459 runs; fixed in 0.2.2). The
  first assembly (`meta_release_CQ_LO_p1_20261109`, V0-V6, 3,432 rows, X_STATE all NULL because the S0 profile is written with
  cohort = ALL and the R4 export has no `feature_regime`) is marked SUPERSEDED. M-15 not run (lightgbm / optuna). LO MANTIS_V2 grid
  running (result tars of at least V2-V4, V6-V8, V13-V16 at W1-W3 uploaded up to 10/11 03:13 UTC, no package). Phase 2 not started.
- `S_SAN_FORMULA.v1.component_behaviour_2026-11-10`: LO r2 copies the LO F1 reference exactly (spread 0.0, |diff| 0.0, 408/408 cells;
  six columns changed vs the 09/11 package: s_leak 384 cells up to 0.02342, s_leak_probe_auc 384 / 0.01171, s_san_plus 392 / 0.02673,
  s_san_plus_v2 389 / 0.03551, acctempo_m3 390 / 0.01425, acctempo_m4 387 / 0.01658; formulas reproduced to 2.7e-15; TEST M4 order keeps
  V7 first and V16 last, V6 moves from 7th to 2nd). The three accepted CQ packages keep their own probe fit: |s_leak - CQ reference| up
  to 4.98e-5 (PatchTST V0-V6, 126 of 168 rows above 1e-5), 1.24e-5 (V7-V16, 30 of 240; MANTIS_V2, 51 of 408). The 09/11 wording
  "float32 rounding" is withdrawn.
- `PENDING_DECISIONS`: 38 (a), 39 (c), 40 (a), 41 (b) EXECUTED by the team before the author answered (`status_2026-11-10`; the
  manifests call them "author decision 2026-11-09", which must read "recommendation applied, ratification pending"); 39: the writing
  side now recommends (c) as executed; 41: "+360" corrected to +240 (3,672 rows). New: 42 (cross-environment s_leak tolerance and the
  reference-copy contract, Q-31, recommend (a): every F2/F3 export copies the registered reference, check 38 identity <= 1e-9 by
  construction, probe reproduction as a separate diagnostic at 1e-5; the team's 1e-5 would reject the three CQ packages) and 43
  (retroactive runner-commit mapping and the three NULL Mantis V0 cells, Q-32, recommend (a) accept with the basis column).
  `OPEN_AUTHOR_QUESTIONS_2026_11_10` (Q-27 .. Q-32 -> decisions 38-43, executed_by_team flags) exported as a registry of its own.
  `POST_MATERIALIZE_CHECKS`: 36 release half MET / mm_runs NOT MET; 37 LARGELY MET ((b), (h), (i) in the repository; (c)/(d) reported,
  W1/V0 evidence files not on the Drive; the V2/W2 repro report read: bit-identical, adapter digest 36ee17d9..., best_epoch 3, 8
  epochs); 38 LO r2 PASS at 0.0, CQ packages 1.24e-5 / 4.98e-5 -> decision 42; 39 LARGELY MET for the r2 packages (V0 NULL ->
  decision 43; byte receipts are not L2 ingest; SUPERSEDED markers); 40 PASS on S0 v4 (48 x 113) and Z_M v2 (6 rows, MANTIS_V2
  2,226,510 = 2,214,144 + 12,366); 41 new (leak-probe reproduction diagnostic per audit environment).
- Export `examples/registries_v1.6/` regenerated (changed: code_reference, grid_policy, pending_decisions, post_materialize_checks,
  s_san_formula, registry_manifest; new: open_author_questions_2026_11_10). 30 tests. Scripts: `Progress/Ver 3/2026-11-10_Meta_release_r2_probe/
  _build/patch_registry_r27.py`, `patch_tests_r27.py`. Analysis: `analysis_r27_2026-11-10.json` in the same folder.

## Revision 2026-11-09 (round 26: CD3 @ 421dbcd; BAO_CAO_DOI_CHIEU_M01_M18_2026-11-08; BAO_CAO_PATCHTST_MANTIS_CQ_LO_2026-11-09; Drive facts packages of 09/11)

- `CODE_REFERENCE` -> `421dbcd` (three commits of 09/11, 267 files). cfcfd40 restores `MATCH_MASTER_SEED` in `LO/registries.py` and
  rewrites decision 9 as "CLOSED updated 2026-11-04 D-32"; `model/metrics.py` clips probabilities at 1e-12 in float64 (M-16); the
  `MANTIS_V2` architecture row and the RETIRED MOMENT rows appear in the team registry (`registries_rev_2026-11-08_d32_mantis_local`);
  `modal_jobs/model_app.py` and `model_preflight_app.py` default `augmentation_seed = -1` (follow the run seed). 6a69b7f adds
  `f3_mantis/`, byte-identical to the writing-side package 0.1.0 (sha256 of all 10 files equal) but without its 34 tests, and the team
  runners replace `EmbeddingStore` by `DedupZstdStore` (zstd frames, per-row dedup, round-trip and encoder-identity checks).
  `registry_drift_2026-11-09`: augmentation policy CONVERGED; the D-18 objective mapping is still absent from the team `METRIC_DEF`.
- Check 35 PASS on the code side: the four places (`LO/registries.py`; `modal_jobs/README.md` lines 157/168/277;
  `modal_jobs/run_model_grid.ps1` default; `tools/vastai_train_shared.py` default plus runtime check) and the two Modal entry points read
  `MATCH_MASTER_SEED`; the per-seed S2 artifacts of seeds 43/44 still do not exist, so the artifact half of the check stays open.
- `GRID_POLICY.execution_status_2026-11-09`: every seed-42 cell of F1 and F2 exists for both tasks (510 of 1,530 primary runs).
  CQ PatchTST V7-V16: 30 cells, runner 29da3b2, 251.52 L4-hours, 17.36 kWh. LO PatchTST V0-V16: 51 cells, 352.17 L4-hours, 24.17 kWh,
  `runner_git_commit` null in every resource row. CQ MANTIS_V2 V0-V16: 51 EXPLORATORY cells, pin satisfied in every standardised
  manifest, 101.23 L4-hours elapsed (29.81 train), 5.48 kWh in 45 runs; the cost and determinism pilots of check 37 (c)/(d) are not
  documented although the grid was run. The six report tables of 09/11 equal the facts at three decimals (440 values, 0 mismatches).
- `S_SAN_FORMULA.v1.component_behaviour_2026-11-09`: the CQ exports (R4, PatchTST V0-V16, Mantis) carry one leak probe within 1.2e-5;
  the LO PatchTST export mixes three probe fits (V14 = LO F1 exactly; eight bundle audits <= 1.1e-3; the 09/11 re-audit of V0-V4, V7,
  V11, V12 up to 0.0234 at W3), which moves M3 by up to 0.0139 and M4 by up to 0.0163 per cell and reorders the mid-ranked LO pipelines
  on M4. Phase-1 F1 facts are unaffected.
- `PENDING_DECISIONS`: 38 (LO F2 leak-probe harmonisation, Q-27, recommend (a) recompute from the LO F1 standard probe table),
  39 (S0 profile conventions of M-13a, Q-28, recommend (a) replace the degenerate `tr_inactive_learner_ratio`), 40 (meta-tier hand-off
  and the 14/11 gate, Q-29, recommend (a) upload the bundle today), 41 (phase-1 use of CQ PatchTST V7-V16, Q-30, recommend (b)); dated
  status on 9, 32, 33, 34, 36, 37. `POST_MATERIALIZE_CHECKS`: 38 (leak-probe reference identity within 1e-9), 39 (F2/F3 facts package
  completeness), 40 (M-13 input acceptance) new; dated status on 31 (PASSED for the 29 hash-verified files), 35, 36, 37 (additions (h)
  cache store contract, (i) package tests in the repository).
- Export `examples/registries_v1.6/` regenerated (changed: code_reference, experiment_seeds, grid_policy, pending_decisions,
  post_materialize_checks, s_san_formula, registry_manifest). 29 tests. Scripts: `Progress/Ver 3/2026-11-09_Full_grid_Mantis_M13/_build/
  patch_registry_r26.py`, `patch_tests_r26.py`. Analysis: `analysis_r26_2026-11-09.json` in the same folder.

## Revision 2026-11-06 (decision 37: F3 = MANTIS_V2; author instruction of 06/11)

- The code team reported after its tests that MOMENT_SMALL / MOMENT_BASE do not fit the F3 grid and run too long, and proposed
  MantisV2. The author asked to check the model against the conditions of F3 as EXPLORATORY and to update the resources if it passes.
  The check (`PENDING_DECISIONS[37]['suitability_check_2026-11-06']`, K1-K14) passed with four conditions: registered channel adapter,
  constant-series guard, cache with the cost and determinism pilots of check 37, validity-domain limitation stated in the paper.
- `MODEL_REGISTRY`: the two MOMENT rows move verbatim to `RETIRED_MODEL_ROWS` (never run into L2); `MANTIS_V2` is the single F3 row
  (EXPLORATORY): `paris-noah/MantisV2` @ `8f6ca35cb54ab14b120618943c6fca5ddf5a76a6`, `mantis-tsfm==1.1.0`, truncated after transformer
  layer index 2 (2,214,144 parameters), output token `combined`, PCA across channels (8 components, standardised, real TRAIN rows,
  seed 20260922), prefixes resized to 512 points, constant-series guard, shared-phase linear probe on cached float16 features;
  `model_revision mantisv2_frozen_linear_probe_v1_pca8_interp512`, `hparam_config_id HP_MANTISV2_FROZEN_LINEAR_PROBE_v1_pca8`.
- `PENDING_DECISIONS`: 37 new, CLOSED 2026-11-06 (APPROVED (b) under the author instruction); 11 gains `update_2026-11-06` (D-11 scope
  unchanged). `POST_MATERIALIZE_CHECKS`: 37 new (pin, guard and prefix safety, cost pilot, determinism pilot, adapter, export label,
  freeze rule); 11 gains `status_2026-11-06` (MOMENT items superseded). `AUTHOR_RATIFICATIONS_2026_11_06` new and exported.
- Cost note: one backbone series costs 160.7 MFLOPs, the same order as MOMENT-1-small under phase-as-patch; the saving comes from the
  8-component adapter (274 -> 8 series per row and prefix for CQ) and from the cache.
- Code: writing-side package `working/Data and Code/f3_mantis_v0.1.0_2026-11-06/` (33 tests + 1 registry test; selftest; bench;
  integration snippets). Guide: `Progress/Ver 3/2026-11-06_F3_MantisV2/Huong_dan_doi_code_F3_MantisV2_2026-11-06.docx`.
- Second pass of the same day, after an independent code review of the package before delivery: the `MANTIS_V2` row gains
  `embedding_cache.key` (adapter digest + encoder fingerprint: weights sha256, encoding settings, precision, microbatch, device) and
  `embedding_cache.reuse_rule` (every entry verified by ids and input sha256; a stale entry stops the run), `weight_loading` (strict),
  `channel_adapter.fit_order` (row-id order, sha256 of the fitted rows) and `interp_constant_rows` (equal values replicated);
  check 37 (a) strict load and weights sha256 in `backbone_pin.json`, (b) test count, (c) largest embedding value, (d) two fresh
  cache roots for the determinism pilot. Script: `Progress/Ver 3/2026-11-06_F3_MantisV2/_build/patch_registry_20261106_review.py`.
- `metamodel/contracts.py` 0.2.1: `MODEL_TIER`/`MODEL_FAMILY` gain `MANTIS_V2`. Export `examples/registries_v1.6/` regenerated
  (43 files; changed: model_registry, pending_decisions, post_materialize_checks, registry_manifest; new:
  author_ratifications_2026_11_06). 28 tests.

## Revision 2026-11-04 (author decisions of the 04/11 writing session: Ra_soat_tien_do_2026-11-04.md §1; checklist Q-01, Q-02, Q-03, Q-05, Q-16 .. Q-19; phase-1 scope)

- Author ratifications recorded: `AUTHOR_RATIFICATIONS_2026_11_04` (decisions 32 (a), 33 (a), 34 (a), 35 (a), 36; D-S1-5, D-S1-8 (b),
  D-S1-6, Q-05). Exported next to the earlier blocks (41 files in `examples/registries_v1.6/`). `CODE_REFERENCE` unchanged at 5872cac.
- Decisions 32-34 closed (`status_2026-11-04`): 32 (a) MATCH_MASTER_SEED stays the registered augmentation seed policy, the team restores
  `LO/registries.py` and the tests, S2 for seeds 43/44 = 144 runs without GPU, no seed-43/44 cell before the four places of check 35 agree;
  33 (a) the artefacts are kept, the method is named "Radius-SMOTE with nearest-neighbour fallback", the fallback rate is printed per
  window x class, the sensitivity label of D-11 stays, no rerun; 34 (a) flag `single_offering_dominant` (top_offering_share >= 0.5) in
  `cell_flags` for CQ and LO, offering-unit bootstrap CIs for flagged cells, flagged cells presented as findings like D-17.
- New decisions, closed on the day: 35 energy label of the LO static-v2 grid (D-15 unchanged, TIME primary for both tasks; the grid carries
  NVML_POWER_SAMPLING_ESTIMATE for 204/204 runs, `lo_resource_per_run.csv`, 0.4967 kWh, so ENERGY is a labelled sensitivity for LO too; the
  sentence "LO NOT_MEASURED" in 00_contributions C3 and 02_baselines is corrected); 36 phase-1 scope amending D-N3 (A): seed 42 only, F1 of
  both tasks (CQ R4 1,632 cells; LO static-v2 1,632 cells) and F2 PatchTST CQ V0-V6 (168 cells); the meta layer (assemble + MM0-MM6) is run
  by the team with planned_seeds = [42] (M-13 / M-14 by 2026-11-09, M-15 by 2026-11-12; if M-15 is later than 2026-11-14 the paper reports
  C1, C4, C5 only); seeds 43/44, V7-V16 and LO F2 move to the full release (phase 2); cluster bootstrap over cells / offering units, no
  across-seed variance decomposition. Decision 23 (`options_2026-10-25` (c)) points to decision 36.
- Checks: 35 updated (decision 32 ratified (a); the four places must read MATCH_MASTER_SEED); 36 new (phase-1 meta layer on seed 42:
  meta_release manifest with planned_seeds == [42], row_status counts, QA01-QA24 rates, F0 for CQ only (LO NOT_AVAILABLE), S0 profile and
  Z_M; mm_runs with mm_config sha256, protocols E1-A/E1-B/E2/E3 as available, objectives PAPER_COMPOSITE_CAL (primary), PAPER_PERF_AXIS,
  META_PRIMARY_M3_V1 (sensitivity), SECONDARY_MACRO_F1; cluster bootstrap B = 2000; Holm).
- Framework name TEMPO-MDS (Temporal Meta-Dataset for intervention Selection), successor of TEMPO-DQ (D-S1-5, Q-01). F0 LO:
  LO_HEURISTIC_PROGRESS_GRADE NOT_AVAILABLE in phase 1, F0 references for CQ only (CQ_PARTIAL_TRIAD), stated in threats and future work
  (D-S1-8 (b), Q-03). SASMOTE = Kosolwattana et al. (2023), bib key `kosolwattana2023selfinspected` (D-S1-6, Q-02). P2, P4, P8 outside
  phase 1; P8 listed as future work (Q-05).
- Applied in: Ra_soat_tien_do_2026-11-04.md §1; 00_contributions.md v0.8, 02_baselines.md v0.8, 03_claims.md v1.0; Content/4 Method.tex
  v0.4; Yeu_cau_tang_meta_doi_code_2026-11-04.docx (M-13/M-14/M-15 with the two milestones). Still open: M-15 (milestone 2026-11-12); the
  Experiments outline §6 of Ra_soat_tien_do_2026-11-01 was approved implicitly on 04/11 and is adjusted for decision 36.
- Tests: `test_registries_rev_2026_11_04_author_ratifications` (block, revision string, closed decisions, check 36, export + manifest);
  27 pass.

## Revision 2026-11-03 (round 23: CD3 @ 5872cac; BAO_CAO_CQ_PATCHTST_V0_V6_2026-11-02; Drive packages of 02-03/11)

- Author ratifications recorded: `AUTHOR_RATIFICATIONS_2026_11_01` (decisions 17 (a), 20 (a-v2), 23 (a), 24 (b), 26 (a), 27 (a);
  checklist Q-04/Q-06/Q-07/Q-09/Q-10) and `AUTHOR_RATIFICATIONS_2026_11_02` (decisions 28-31 = Q-11..Q-14: shared Drive as the
  delivery channel, LO M3^(cal) derived column, static-v2 ablation before submission, Drive sync by the author). Both are exported
  (39 files in `examples/registries_v1.6/`).
- CODE_REFERENCE -> 5872cac (df2a867, 834ad30, 5872cac): review patch 2026-10-31 adopted; 23 export/audit tools (M-01, M-02, M-04,
  M-05 CQ, M-06/M-07/M-08 partial, M-09 draft, M-10, M-14 trial); 68 tests. df2a867 also rewrote `EXPERIMENT_SEEDS` to
  FIXED_SEED_42 and re-closed decision 9 without the author, while README / launcher default / runner check keep MATCH_MASTER_SEED
  -> decision 32 (Q-16) and check 35; the s_eff / s_leak sentences converged on the real-row contract of this file (recorded in
  `S_SAN_FORMULA['v1']['team_alignment_2026-10-31']`).
- PatchTST V0-V6 (21 cells, one runner 29da3b2, protocol v2, audits B = 2,000, 181.81 L4-hours, 66.91 USD estimate, 13.03 kWh):
  decision 23 CLOSED (a) by ratification and execution; decision 25 CLOSED (a); `GRID_POLICY['execution_status_2026-11-03']`
  (429 of 1,530 primary seed-42 cells). The V0 epoch histories are delivered (W3 peaks at epoch 1 and never recovers).
  `ACCTEMPO_DEF['decomposition_patchtst_2026-11-03']`: the M3 gains of the balanced variants (+0.036 .. +0.074) are carried by
  s_ent; under M3^(cal) they are +0.008 .. +0.013 (report-derived, tagged).
- New decisions: 32 augmentation seed policy (team FIXED_SEED_42 vs locked MATCH_MASTER_SEED; recommendation (a)); 33 Radius-SMOTE
  nearest-neighbour fallback > 0.50 in all 24 CQ class rows (recommendation (a): document and print the rates); 34 CQ W1 TEST class
  good = 98.85 % one offering (recommendation (a): flag at top_offering_share >= 0.5 plus offering-cluster bootstrap).
- New checks: 32 probability clipping convention (model 1e-7 vs audit 1e-12); 33 integrity of the 02/11 report (appendix encoding,
  stale copy in the package, unsourced hourly price, tautological margin column, recall column name); 34 R4 RNN receipt for
  T1-EX-07; 35 seed policy stated once in four places plus METRIC_DEF v1.3 content. Checks 5, 13, 26, 31 updated (31: 47 small
  files of 12 Drive packages hash-verified; report tables equal the facts files).
- No review patch this round: the repository changes are tools and registry text; the registry text change is a decision for the
  author, not a code fix.

## Revision 2026-10-31 (round 22: CD3 @ 3bdb8b6; BAO_CAO_TONG_HOP_R21_CQ_LO_2026-10-31; first input/results packages)

- origin/main moved to 3bdb8b6 (5 commits): review patches 2026-10-28 and 2026-10-29 adopted; the DAY_DU appendix builder, the
  one-epoch PatchTST replay audit, the primary_risk_set and label-view audits, the R21 evidence staging tool (151 files, sha256
  manifest) are in the repository; 65 tests.
- Decision 25 closed by execution (a): three NEW PatchTST V0 runs on the current 11-field layout replace the 12-field pilot of
  23/10; decision 23 READY FOR RATIFICATION (a) (team proposal, section 10 of the R21 report). New decisions 26 (point-in-time
  availability of the static branch; constant primary_risk_set) and 27 (report-derived numbers in the draft).
- Check 27 CLOSED for the shared loop: the baseline runner hash 4077c6c9... = CRLF rendition of the eb80516 runner (reproduced
  here; review patch 2026-10-31 teaches identify_runner_commit the LF/CRLF renditions); check 28 partly closed; check 30 half done
  (package staged on the team disk, not transferred); new check 31 (what to verify when R21_evidence arrives).
- input/results (writing side): three report-derived CSV packages with source docx, README and manifest (49 files), placeholder for
  R21_evidence_20261031; 03_claims.md v0.5 section A records them.

## Revision 2026-10-29 (round 21: origin/main unchanged at e0ae433; REPORT_CQ_DAY_DU_REPLAY_PATCHTST_2026-10-29, REPORT_LO_STATIC_V2 ... R20, Drive tree README)

- No new commit on GitHub; the two reports come from local, unpushed tools. CQ and LO metric tables are byte-identical to 28/10.
- Check 27 closed for the shared loop by the matched historical replay CQ/W1/V0/RNN (baseline 20/10, replay 29da3b2, bit-exact on
  353,784 enrollments x P1-P4, epoch 2 both), subject to the baseline runner_sha256 being printed in the receipt: the hash identifies
  the commit interval (83c5056..eb80516, before 044d6c7) through `tools/identify_runner_commit.py` of review patch 2026-10-29.
- Decision 25: the team proposes A (keep the three PatchTST V0 cells with a registered exception). The 044d6c7 reorder of the
  accumulation path is exact (power-of-two loss scale commutes with rounding), so A is acceptable with a one-epoch replay receipt
  and the receipt-backed exception mechanism of the patch (`VASTAI_RUNNER_EXCEPTIONS`); otherwise rerun.
- Check 29 closed (ONE_CLASS / SLICE_EMPTY / classes / UNSEEN share in the R20 LO report; residual n per class). New check 30:
  Drive archive (README_STORAGE_TREE_CQ_LO_20261029) mapped to the paper packages with sha256 and copied into input/results/.
- `review_patches_2026-10-29.patch` is the cumulative series on e0ae433 (28/10 + 29/10): runner git commit per ingest, reused-cell
  commits in the shard plan, replay provenance with hash attribution, receipt-backed runner exceptions (65 tests pass).

## Revision 2026-10-28 (round 20: CD3 @ e0ae433, REPORT_CQ_CONSOLIDATED_EVIDENCE + REPORT_LO_STATIC_V2_CONSOLIDATED_EVIDENCE 2026-10-28_DAY_DU)

- Review patch 2026-10-27 adopted verbatim (651b458). 29da3b2: the team locked the F2 PatchTST protocol at the registered
  v2 values (lr 1e-3, warm-up 0, no clipping) after the W3 D23 history failed the registered criterion; recorded as
  `optimisation_protocol_lock_2026-10-27` (TEAM-LOCKED, author ratification pending = decision 23 option (a)).
- LO F1 seed-42 grid under the v2 13-field contract is COMPLETE (204 cells, runner b0e5ae1, four audits B = 2,000, closure
  archive sha256 9108...40d3, cohort audit 68 x 96 cells, prefix audit): decision 20 (a-v2) and decision 24 (b) were executed
  by the team before ratification and are READY FOR RATIFICATION. Against r3 the family TEST means move by at most 0.007;
  the W1 VALIDATION - TEST gap (+0.14 .. +0.24 macro-F1) and recall E = 0 on W1 TEST persist (decision 17: evidence complete).
- CQ report = R4 unchanged (verified to 1e-4); label counts per block equal SPLIT_REGISTRY blocks A-G for both tasks.
- Check 27: two paired replays with delta 0 (CQ W1/V0/RNN without named commits; LO W1/V0/RNN b0e5ae1 vs 29da3b2, both after
  044d6c7) -> still OPEN until the CQ receipt names a reference run trained before 044d6c7. New decision 25 (the three PatchTST
  V0 pilot cells, runner 7886a856, cannot share one ingest with the 48 F2 shards; recommendation: rerun them, about 18 L4-hours).
  New checks 28 (the delivered DAY_DU reports come from a builder not in the repository; the CQ replay receipt has no writer in
  the repository) and 29 (single-class and empty cohort slices printed without classes_present / SLICE_EMPTY).
- `review_patches_2026-10-28.patch` (on e0ae433): one `runner_git_commit` per ingest, `excluded_runner_commits` in the shard
  plan, `replay_provenance()` in the consolidated report builder (63 tests pass).

## Revision 2026-10-27 (round 19: CD3 @ af079d8, REPORT_CQ_F1_D23_PATCHTST_CONFIGURATION_2026-10-27)

- Review patch 2026-10-25 adopted (shard plan + launcher verbatim, labels, N10). 044d6c7 adds per-update warm-up and
  gradient clipping to the shared training loop and the flags `--learning-rate / --warmup-epochs / --gradient-clip-norm /
  --run-purpose`; the team ran the D-23 (b) pilot (W2/V0, W3/V0 at lr 3e-4, warm-up 1, clip 1.0) and proposes to lock it
  for F2. The registered acceptance criterion (unimodal spike-free VALIDATION curve or selection away from epoch 1) is not
  demonstrated: no history is printed and W3 still selects epoch 1; decision 23 stays OPEN with options (a) / (b') / (c)
  and the candidate recorded in MODEL_REGISTRY as NOT REGISTERED.
- New check 27 (training-loop equivalence after 044d6c7: replay one recurrent cell per task before any new primary grid);
  check 26 updated (shard plan adopted; protocol provenance in review patch 2026-10-27). Decision 20/24: the v2 LO replay
  launcher exists (0851aed), nothing run.
- `review_patches_2026-10-27.patch` (on af079d8): training protocol in the contract identity, the ingest uniform-execution
  assertion and the shard verifier; registered optimisation protocol in the F2 report gate; D-23 (b) criterion computed in
  the D23 report builder from train_history (60 tests pass).

## Revision 2026-10-25 (round 18: CD3 @ c225961, REPORT_CQ 23/10 regenerated + REPORT_LO_CURRENT_EVIDENCE_CLOSED_SEED42_2026-10-25)

- Base: the device copy rev 2026-10-24 (N10, `AUTHOR_RATIFICATIONS_2026_10_24`); nothing of 24/10 is undone.
- `METRIC_DEF` v1.3 registered (`v1_3_change_2026-10-24`): names AccTEMPO_M3 / AccTEMPO_M3^(cal) (exporter column
  `acctempo_m4`), objectives PAPER_COMPOSITE_CAL / PAPER_PERF_AXIS / META_PRIMARY_M3_V1 / SECONDARY_MACRO_F1, the
  hypothesis -> objective mapping (H1-H6, H8 on the calibrated composite, H7 against macro-F1, v1 sensitivity), the
  trend-and-ranking rule and the disclosure; mirrors `metamodel.contracts` v0.2.0.
- Review patch 2026-10-23 adopted in 75eae0c; c225961 locks the LO static contract v2 (13 fields, `fit_layout` allowlist)
  and ingests the LO NVML replay (r3). Decisions 13, 19, 21, 22 marked RATIFIED (24/10); 17 and 20 now have the ablation
  evidence and a recommendation ((a) and (a-v2)); new decisions 23 (F2 cost and optimisation stability: pilot 5.9 L4-h and
  0.42 kWh per run, 48 cells about 282 L4-h; VALIDATION curve unstable; recommendation (b) stabilisation pilot first) and
  24 (which LO grid and contract enter the paper). Check 15 closed as explained (the W1 gap is block-C composition, not the
  static contract: VALIDATION - TEST +0.14..+0.23 on W1 vs +0.01 on W2 and -0.06 on W3); check 18 closed for LO; new
  checks 25 (LO export) and 26 (parallel F2 execution preconditions).
- `CODE_REFERENCE` -> c225961; the N1 label defect (`PIPELINE_LABELS`: V1/V5 and V3/V4 swapped) is still in the repository
  and in the 25/10 LO report; fixed in `review_patches_2026-10-25.patch` together with the N10 mirror for
  `CQ/registries.py` / `LO/registries.py`, `tools/f2_shard_plan.py` and the sharded PatchTST launcher.

Sửa đổi 24/10/2026 (`registries_rev_2026-10-24`, do trợ lý viết bài áp dụng theo quyết định của tác giả, đợt 2):
(1) **N10:** `build_pipeline_registry` đặt `imputer_only_ref` = chính pipeline đó khi balancer = NONE (V1→V1, V5→V5,
V9→V9, V13→V13); `validate_pipeline_registry` kiểm theo định nghĩa mới; Bảng 14 của Meta-Dataset-Report cần sửa theo.
Hệ quả cho tầng L3: Δ_imp = Δ và Δ_bal = 0 cho pipeline chỉ imputation (`metamodel` ≥ 0.1.0 đã dùng định nghĩa này;
`metamodel.contracts.load_registry_overrides` chấp nhận cả export cũ và báo `PRE_N10_LITERAL_IN_REGISTRY`).
(2) Thêm `AUTHOR_RATIFICATIONS_2026_10_24` (xuất thành `author_ratifications_2026_10_24.json`): D-11, D-13 (b), D-14 (a),
D-15, D-16, D-18 (ánh xạ giả thuyết), D-19 (b), D-21 (b), D-22 (b), D-N3 (A), N10, B7, RQ8/H8; còn mở: D-17, D-20, F0 LO,
tên framework, xác nhận bài SASMOTE. Các mục trong `PENDING_DECISIONS` giữ nguyên lịch sử; `CQ/registries.py` và
`LO/registries.py` của repo cần được nhóm đồng bộ (patch: `patches/2026-10-24_imputer_only_ref_N10.patch`).
(3) Export `examples/registries_v1.6/` tạo lại từ bản này (`python -m tempo_fix.registries tempo_fix/examples/registries_v1.6`).
