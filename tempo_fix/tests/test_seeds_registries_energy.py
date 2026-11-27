import json
import os

import pytest

from tempo_fix import seeds, registries
from tempo_fix import energy_nvml as en


def test_seed_derivation_matches_cd3_model_app():
    # implemented scheme (modal_jobs/model_app._role_seed @ dff9a3f): per-cell streams, master seed for augmentation
    import hashlib
    def role_seed(master, role, task, window, pipeline_id, model_name):
        payload = f"{master}|{role}|{task}|{window}|{pipeline_id}|{model_name}".encode("utf-8")
        return int(hashlib.sha256(payload).hexdigest()[:8], 16) % (2 ** 31 - 1)
    b = seeds.seed_bundle(42, 'CQ', 'W1', 'V14', 'LSTM')
    assert b == seeds.seed_bundle(42, 'CQ', 'W1', 'V14', 'LSTM')
    assert b['seed_model'] == role_seed(42, 'model', 'CQ', 'W1', 'V14', 'LSTM')
    assert b['seed_dataloader'] == role_seed(42, 'dataloader', 'CQ', 'W1', 'V14', 'LSTM')
    assert b['seed_sampler'] == b['seed_augmentation'] == 42 and b['seed_preprocess'] == 20260922
    assert all(0 <= v < 2 ** 31 for v in b.values() if v is not None)
    assert seeds.derive_seed(42, 'model', 'CQ', 'W1', 'V0', 'RNN') != seeds.derive_seed(43, 'model', 'CQ', 'W1', 'V0', 'RNN')
    assert seeds.derive_seed(42, 'model', 'CQ', 'W1', 'V0', 'RNN') != seeds.derive_seed(42, 'model', 'CQ', 'W1', 'V0', 'LSTM')
    v0 = seeds.seed_bundle(42, 'CQ', 'W1', 'V0', 'RNN', has_balancer=False)
    assert v0['seed_sampler'] is None and v0['seed_augmentation'] is None
    assert seeds.seed_bundle(43, 'LO', 'W2', 'V4', 'GRU', augmentation_seed=42)['seed_augmentation'] == 42   # fixed policy, opt-in
    assert seeds.MASTER_SEEDS == (42, 43, 44) and seeds.AUGMENTATION_SEED_POLICY == 'MATCH_MASTER_SEED'
    assert seeds.SEED_PREPROCESS_PLAN_V1_6 == seeds.derive_seed_plan_v1_6(0, 'preprocess') == 4072383768
    assert 'augmentation_seed' in seeds.RUN_ID_FIELDS


def test_run_id_and_canonical_json():
    cfg = {k: 'x' for k in seeds.RUN_ID_FIELDS}
    rid = seeds.run_id(cfg)
    assert len(rid) == 64 and rid == seeds.run_id(dict(reversed(list(cfg.items()))))
    with pytest.raises(KeyError):
        seeds.run_id({'task': 'CQ'})
    assert seeds.canonical_json({'b': 1, 'a': [1, 2]}) == '{"a":[1,2],"b":1}'
    assert seeds.attempt_id(rid, 3).endswith('-0003')


def test_pipeline_registry_matches_plan(tmp_path):
    rows = registries.build_pipeline_registry()
    registries.validate_pipeline_registry(rows)
    by = {r['pipeline_id']: r for r in rows}
    assert by['V0']['is_no_intervention'] == 1 and by['V0']['v0_fill_rule'] == 'ZERO_RAW_PRE_TRANSFORM'
    assert by['V14']['imputer'] == 'MICE' and by['V14']['balancer'] == 'CDSMOTE' and by['V14']['imputer_only_ref'] == 'V13'
    assert by['V4']['balancer_params']['ir_target'] == 10
    assert by['V16']['pipeline_name'] == 'V16-MICE-RadiusSMOTE'
    man = registries.write_registries(str(tmp_path))
    assert set(man) >= {'pipeline_registry', 'model_registry', 'metric_def', 's_san_formula', 'acctempo_def', 'rec_rule'}
    assert os.path.exists(tmp_path / 'registry_manifest.json') and os.path.exists(tmp_path / 'pipeline_registry.yaml')
    # stable hashes
    assert man['pipeline_registry'] == registries.write_registries(str(tmp_path))['pipeline_registry']
    md = registries.METRIC_DEF
    assert md['class_index']['CQ'] == {'c0': 'W', 'c1': 'A', 'c2': 'G'}
    assert [m for m in registries.MODEL_REGISTRY if m['model_name'] == 'RNN'][0]['selection_metric'] == 'MEAN_PHASE_MACRO_F1'
    assert set(man) >= {'label_artifacts', 'split_registry', 'sampling_strategy', 'pending_decisions'}
    assert man['registry_revision'] == registries.REGISTRY_REVISION == 'registries_rev_2026-11-26b'
    # N10 (2026-10-24): imputation-only pipelines are their own imputer-only reference
    assert by['V1']['imputer_only_ref'] == 'V1' and by['V5']['imputer_only_ref'] == 'V5' and by['V13']['imputer_only_ref'] == 'V13'
    assert 'author_ratifications_2026_10_24' in man and 'author_ratifications_2026_11_01' in man and 'author_ratifications_2026_11_02' in man
    assert set(man) >= {'code_reference', 'release_specs', 'feature_source', 'experiment_seeds', 'grid_policy'}


def test_registries_rev_2026_09_30_locked_values():
    # METRIC_DEF v1.1: cell-level support flag and plan-level subgroup flag kept apart
    md = registries.METRIC_DEF
    assert md['metric_def_version'] == 'metric_def_v1.3'
    v13 = md['v1_3_change_2026-10-24']
    assert v13['objectives'] == {'PAPER_COMPOSITE_CAL': 'acctempo_m3_cal', 'PAPER_PERF_AXIS': 's_perf', 'META_PRIMARY_M3_V1': 'acctempo_m3', 'SECONDARY_MACRO_F1': 'macro_f1'}
    assert all(v13['hypothesis_objectives'][h] == 'PAPER_COMPOSITE_CAL' for h in ('H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'H8')) and v13['hypothesis_objectives']['H7'].startswith('PAPER_COMPOSITE_CAL vs')
    assert md['cluster_bootstrap']['rule'].startswith('when n_offerings_with_class <= 2')
    assert md['course_score_ceiling_observed']['model_input'].startswith('FORBIDDEN')
    assert 'course_score_ceiling_observed' in md['prediction_level_context_columns']
    assert md['support_flags']['small_support_flag']['rule'] == 'n_support < 400'
    assert md['support_flags']['small_subgroup_flag']['rule'] == 'n_g < 30 or any class support < 5'
    assert md['checkpoint_selection']['metric'] == 'MEAN_PHASE_MACRO_F1' and md['checkpoint_selection']['split'] == 'VALIDATION'
    assert 'long_offering_flag' in md['prediction_level_context_columns']
    # LO label V3 [V3 §2-§3]
    lo = registries.LABEL_ARTIFACTS['LO']
    assert lo['label_rule_version'] == 'lo_final_score_catalog_normalized_v3_1'
    assert lo['structural_bound'] == [0.0, 100.0] and lo['thresholds']['E'] == '[85, 100]'
    assert 'TEMPO_LEGACY_CLIP' in lo['sensitivity_sets']
    c = lo['cohort']
    assert sum(c['class_counts'].values()) == c['eligible_enrollments'] == 2605423
    assert c['exclusion_reasons']['no_scored_signal_in_course']['enrollments'] == 172003
    assert sum(v['enrollments'] for v in c['exclusion_reasons'].values()) + c['eligible_enrollments'] == c['raw_enrollments'] == 11807090
    pc = lo['proxy_contract']
    assert sum(len(v) for v in pc['canonical_fields'].values()) == pc['n_canonical_fields'] == 19
    assert pc['names_to_confirm'] == [] and 'assignment_problem_catalog_count' in pc['canonical_fields']['problem']
    cs = lo['course_score_ceiling']['by_slice']
    assert sum(v['enrollments'] for v in cs.values()) == 2605423
    assert sum(v['ceiling_ge_60'] for v in cs.values()) == lo['course_score_ceiling']['ceiling_ge_60']['enrollments'] == 936819
    assert sum(v['ceiling_ge_85'] for v in cs.values()) == lo['course_score_ceiling']['ceiling_ge_85']['enrollments'] == 233029
    assert lo['label_status'].startswith('FINAL')
    # split registry: shared calendar, per-task version, blocks add up [CL §2, §7.5], [V3 §5-§6]
    sr = registries.SPLIT_REGISTRY
    assert sr['calendar']['slice_boundaries'] == {'T1': '2020-09-13', 'T2': '2020-12-31', 'T3': '2022-01-18'}
    assert sr['calendar']['tau_w']['W3'] == '2020-12-31' and sr['purge_mode'] == 'NONE' and sr['qa22']['min_eval_enrollments'] == 1
    for task, d in sr['tasks'].items():
        assert sum(d['blocks'].values()) == d['population'], task
    assert sr['tasks']['CQ']['split_version'] == 'v2_2' and sr['tasks']['LO']['split_version'] == 'v3_1'
    bc = sr['tasks']['LO']['block_classes']
    assert all(sum(bc[b].values()) == sr['tasks']['LO']['blocks'][b] for b in bc)
    assert sum(d['c2'] for d in bc.values()) == 2003 and sum(d['c1'] for d in bc.values()) == 6996
    assert lo['course_score_ceiling']['ceiling_below_60']['courses'] == 493
    assert len(lo['proxy_contract']['current_grade_group']['columns']) == 9
    assert sr['tasks']['CQ']['pairing'] == 'balanced' and sr['tasks']['LO']['pairing'] == 'rarest_first'
    assert sr['long_offering']['decision'] == 'KEEP_UNITS' and sr['long_offering']['threshold_days'] == 270
    assert 'ev_train_overlap_share' in sr['overlap_metrics'] and 'p1_cutoff_overlap_share' in sr['overlap_metrics']
    # pending items are enumerated, not silently decided
    ids = [d['id'] for d in registries.PENDING_DECISIONS]
    assert ids == list(range(len(ids))) and any('denominator' in d['topic'] for d in registries.PENDING_DECISIONS)
    assert all(d['status'].startswith('CLOSED') for d in registries.PENDING_DECISIONS if d['id'] <= 10)   # 11, 12 opened 2026-10-12
    assert 'post_materialize_checks' in registries.all_registries()


def test_registries_rev_2026_10_05_locked_values():
    r = registries
    # runtime_config.py @ dff9a3f
    assert r.MICE_PARAMS['max_iter'] == 3 and r.MICE_PARAMS['fit_sample_rows'] == 1000000 and r.MICE_PARAMS['tol'] == 1e-3
    assert r.EXTRATREES_PARAMS['n_estimators'] == 1 and r.EXTRATREES_PARAMS['max_depth'] == 5 and r.EXTRATREES_PARAMS['max_iter'] == 1
    assert r.BALANCER_PARAMS['CDSMOTE']['n_clusters'] == 5 and r.BALANCER_PARAMS['SASMOTE']['visible_k'] == 16
    assert r.BALANCER_PARAMS['RADIUS_SMOTE']['radius'] == 0.092 and r.BALANCER_PARAMS['RADIUS_SMOTE']['radius_space'] == 'scaled_numeric_model_input'
    hp = r.COMMON_HPARAMS
    assert hp['batch_size'] == 2048 and hp['hidden_size'] == 128 and hp['dropout'] == 0.3 and hp['weight_decay'] == 1e-5
    assert hp['max_epochs'] == 50 and hp['early_stopping_patience'] == 5 and hp['lr'] == 1e-3 and hp['precision_policy'] == 'bf16_amp'
    assert hp['model_revision'] == 'recurrent_shared_phase_v2_4_prefixsafe_epoch50' and len(hp['phase_mask_bases']) == 4
    # pipeline registry carries the runtime values and IR10_K10
    by = {row['pipeline_id']: row for row in r.build_pipeline_registry()}
    assert by['V13']['imputer_params']['max_iter'] == 3 and by['V9']['imputer_params']['n_estimators'] == 1
    assert by['V16']['balancer_params']['radius'] == 0.092 and by['V16']['balancer_params']['sampling_strategy_id'] == 'IR10_K10'
    assert by['V2']['balancer_params']['n_clusters'] == 5 and by['V2']['balancer_params']['max_expansion_per_class'] == 10
    # decisions of 2026-10-05
    assert r.ACCTEMPO_DEF['primary_s_san_version'] == 'v1' and r.ACCTEMPO_DEF['decision_status'].startswith('LOCKED 2026-10-05')
    assert 'decision_pending' not in r.ACCTEMPO_DEF and 's_cal' in r.ACCTEMPO_DEF['mandatory_columns']
    es = r.EXPERIMENT_SEEDS
    assert es['master_seeds'] == [42, 43, 44] and es['augmentation_policy'] == 'MATCH_MASTER_SEED' and es['s2_plan']['n_runs'] == 216
    assert es['role_seeds']['seed_preprocess'] == 20260922
    assert r.GRID_POLICY['status'].startswith('LOCKED') and r.GRID_POLICY['legacy_quarantine']['rule'].startswith('kept on the Volume')
    ids = [d['id'] for d in r.PENDING_DECISIONS]
    assert ids == list(range(63)) and len(set(ids)) == 63   # 62 added 2026-11-26, second pass (OPEN); 59, 60, 61 added 2026-11-26; 57, 58 added 2026-11-24 (OPEN); 48-51 added 2026-11-20 (OPEN); 46, 47 added 2026-11-16 (OPEN); 44, 45 added 2026-11-13 (OPEN);   # 35, 36 added and closed 2026-11-04; 37 added and closed 2026-11-06; 38-41 added 2026-11-09 (OPEN); 42, 43 added 2026-11-10 (OPEN)
    assert all(r.PENDING_DECISIONS[i]['status'].startswith('OPEN') for i in (11, 13, 14, 15, 17, 18, 19, 20, 21, 22))
    assert r.PENDING_DECISIONS[16]['recommendation'].startswith('(a)') and 'single offering' in r.PENDING_DECISIONS[17]['topic']
    assert 's_ent' in r.PENDING_DECISIONS[18]['topic'] and 'AccTEMPO_M4' in r.PENDING_DECISIONS[18]['options'][1]
    assert r.PENDING_DECISIONS[12]['status'] == 'CLOSED 2026-10-12' and 'V4 V8 V12 V16' in r.PENDING_DECISIONS[11]['team_proposal_640be01']['F3_MOMENT_SMALL']
    assert r.PENDING_DECISIONS[4]['status'] == 'CLOSED 2026-10-04' and r.PENDING_DECISIONS[5]['status'] == 'CLOSED 2026-10-05'
    assert r.PENDING_DECISIONS[9]['status'] == 'CLOSED 2026-10-05'
    # release identities (release_core/contracts.RELEASE_SPECS) are the registry identifiers, not paraphrases
    r.validate_release_alignment()
    assert r.LABEL_ARTIFACTS['CQ']['label_threshold_set'] == 'CQ_VECTOR_PROXIMITY_PRIMARY_V1'
    assert r.LABEL_ARTIFACTS['LO']['label_threshold_set'] == 'CATALOG_NORMALIZED_PRIMARY_V3_1__EXCLUDE_NO_SCORED_SIGNAL'
    assert r.SPLIT_REGISTRY['tasks']['CQ']['phase_version'] == 'wide_prefix_v2_2' and r.SPLIT_REGISTRY['tasks']['LO']['release_id'] == 'LO_V3_1'
    assert r.FEATURE_SOURCE['active'] == 'cumulative_phase_features_v2' and 'cumulative_phase_features_v1' in r.FEATURE_SOURCE['forbidden']
    assert 'augmentation_seed' in r.SPLIT_REGISTRY['run_manifest_required'] and 'model_revision' in r.SPLIT_REGISTRY['run_manifest_required']
    assert [c['id'] for c in r.POST_MATERIALIZE_CHECKS] == list(range(49))   # checks 44, 45 added 2026-11-20; check 43 added 2026-11-16;   # check 36 added 2026-11-04, check 37 2026-11-06, checks 38-40 2026-11-09, check 41 2026-11-10
    assert r.POST_MATERIALIZE_CHECKS[9]['status'].startswith('CLOSED')
    assert r.POST_MATERIALIZE_CHECKS[15]['status'].startswith('CLOSED 2026-10-25') and len(r.POST_MATERIALIZE_CHECKS[15]['remaining']) == 7
    assert all(r.POST_MATERIALIZE_CHECKS[i]['status'].startswith('CLOSED 2026-10-21') for i in (16, 19, 20, 21)) and r.CODE_REFERENCE['commit'] == 'acd11c1' and r.CODE_REFERENCE['previous_reference'].startswith('ecad59d') and r.CODE_REFERENCE['previous_reference_2026-11-24'].startswith('fc361b6') and r.CODE_REFERENCE['previous_reference_2026-11-21'].startswith('6274591') and r.CODE_REFERENCE['previous_reference_2026-11-20'].startswith('cb575df') and r.CODE_REFERENCE['previous_reference_2026-11-16'].startswith('7cad8b1') and r.CODE_REFERENCE['previous_reference_2026-11-09'].startswith('5872cac') and r.CODE_REFERENCE['previous_reference_2026-11-03'].startswith('3bdb8b6')
    assert all(r.POST_MATERIALIZE_CHECKS[i]['status'].startswith('OPEN 2026-10-23') for i in (22, 23)) and r.POST_MATERIALIZE_CHECKS[24]['status'].startswith('OPEN 2026-10-25')
    assert r.POST_MATERIALIZE_CHECKS[15]['status'].startswith('CLOSED 2026-10-25') and r.POST_MATERIALIZE_CHECKS[25]['status'].startswith('OPEN 2026-10-25')
    assert all(r.POST_MATERIALIZE_CHECKS[i]['status'].startswith('OPEN 2026-10-27') for i in (26, 27))
    assert r.PENDING_DECISIONS[23]['status_2026-10-27'].startswith('OPEN') and r.PENDING_DECISIONS[23]['recommendation_2026-10-27'].startswith('first the two D23 histories')
    patch = next(m for m in r.MODEL_REGISTRY if m['model_name'] == 'PATCHTST')
    assert patch['hparam_config_id'] == 'HP_PATCHTST_CHANNEL_INDEPENDENT_v2' and patch['hparam_candidate_2026-10-26']['status'].startswith('NOT REGISTERED')
    assert r.CODE_REFERENCE['pipeline_label_defect_N1_status_2026-10-27'].startswith('closed') and len(r.CODE_REFERENCE['not_in_repository_2026-10-27']) == 8
    assert all(r.PENDING_DECISIONS[i]['status_2026-10-25'].startswith('RATIFIED') for i in (13, 19, 21, 22)) and r.PENDING_DECISIONS[20]['status_2026-10-25'].startswith('READY')
    assert r.PENDING_DECISIONS[23]['status'].startswith('OPEN 2026-10-25') and r.PENDING_DECISIONS[23]['recommendation'].startswith('(b)') and r.PENDING_DECISIONS[24]['status'].startswith('OPEN 2026-10-25')
    assert r.PENDING_DECISIONS[17]['recommendation_2026-10-25'].startswith('(a)') and 'F2_cost' in r.GRID_POLICY['execution_status_2026-10-25']
    assert r.PENDING_DECISIONS[18]['status_2026-10-23'].startswith('READY') and r.PENDING_DECISIONS[22]['recommendation'].startswith('(b)')
    assert 'acctempo_m4_export_note_2026-10-23' in r.METRIC_DEF and r.CODE_REFERENCE['review_patch_2026-10-21_status'].startswith('adopted')
    assert '0.88' in r.PENDING_DECISIONS[21]['label_construction_fact_2026-10-23'] and 'best_score' in r.PENDING_DECISIONS[22]['facts'][3]
    assert 'access_note_2026-10-17' in r.CODE_REFERENCE and len(r.CODE_REFERENCE['review_patches_pending']) == 1
    assert r.CODE_REFERENCE['review_patch_2026-10-15_status'].startswith('adopted') and len(r.CODE_REFERENCE['not_in_repository_2026-10-21']) == 1 and len(r.CODE_REFERENCE['not_in_repository_2026-10-23']) == 4 and len(r.CODE_REFERENCE['not_in_repository_2026-10-25']) == 7
    assert r.PENDING_DECISIONS[19]['recommendation'].startswith('(b)') and 'contract' in r.POST_MATERIALIZE_CHECKS[18]['status']
    assert r.PENDING_DECISIONS[16]['status_2026-10-19'].startswith('RESOLVED BY RERUN') and r.PENDING_DECISIONS[20]['status'].startswith('OPEN')
    assert 'execution_status_2026-10-27' in r.GRID_POLICY and r.POST_MATERIALIZE_CHECKS[20]['status'].startswith('CLOSED 2026-10-21')
    assert r.REGISTRY_REVISION == 'registries_rev_2026-11-26b' and r.CODE_REFERENCE['review_patch_2026-10-25_status'].startswith('adopted')
    # revision 2026-10-28: team lock of decision 23, LO v2 grid complete, pilot-runner mismatch (decision 25), checks 28/29
    assert r.CODE_REFERENCE['review_patch_2026-10-27_status'].startswith('adopted') and len(r.CODE_REFERENCE['not_in_repository_2026-10-28']) == 10
    assert r.PENDING_DECISIONS[23]['status_2026-10-28'].startswith('TEAM-LOCKED (a)') and r.PENDING_DECISIONS[20]['status_2026-10-28'].startswith('READY FOR RATIFICATION (a-v2)')
    assert r.PENDING_DECISIONS[24]['status_2026-10-28'].startswith('READY FOR RATIFICATION (b)') and r.PENDING_DECISIONS[17]['status_2026-10-28'].startswith('OPEN; evidence complete')
    assert r.PENDING_DECISIONS[25]['status'] == 'OPEN 2026-10-28' and r.PENDING_DECISIONS[25]['recommendation'].startswith('(a)') and len(r.PENDING_DECISIONS[25]['options']) == 3
    assert patch['optimisation_protocol_lock_2026-10-27']['status'].startswith('TEAM-LOCKED') and patch['optimisation_protocol_lock_2026-10-27']['learning_rate'] == 1e-3
    assert all(r.POST_MATERIALIZE_CHECKS[i]['status'] == 'OPEN 2026-10-28' for i in (28, 29)) and r.POST_MATERIALIZE_CHECKS[27]['status_2026-10-28'].startswith('OPEN, two paired replays')
    assert all('status_2026-10-28' in r.POST_MATERIALIZE_CHECKS[i] for i in (23, 25, 26, 27))
    st = r.GRID_POLICY['execution_status_2026-10-28']
    assert st['LO'].startswith('F1 seed-42 grid under the v2 13-field contract COMPLETE') and '411 of 1,530' in st['runs'] and 'check 28' in st['numbers']
    assert 'pilot_runner_mismatch_2026-10-28' in r.CODE_REFERENCE and 'report_builder_provenance_2026-10-28' in r.CODE_REFERENCE
    # revision 2026-10-29: origin/main unchanged, matched CQ replay, team proposal A for decision 25, check 29 closed, check 30 new
    assert r.CODE_REFERENCE['remote_status_2026-10-29'].startswith('origin/main still e0ae433') and 'review_patch_2026-10-29' in r.CODE_REFERENCE
    assert r.PENDING_DECISIONS[25]['recommendation_2026-10-29'].startswith('(b)/A is acceptable') and r.PENDING_DECISIONS[25]['status_2026-10-29'].startswith('OPEN; team proposal A')
    assert r.POST_MATERIALIZE_CHECKS[27]['status_2026-10-29'].startswith('CLOSED FOR THE SHARED LOOP') and r.POST_MATERIALIZE_CHECKS[29]['status_2026-10-29'].startswith('CLOSED 2026-10-29')
    assert r.POST_MATERIALIZE_CHECKS[30]['status'] == 'OPEN 2026-10-29' and 'execution_status_2026-10-29' in r.GRID_POLICY
    assert len(r.CODE_REFERENCE['not_in_repository_2026-10-29']) == 5 and 'drive_storage_tree_2026-10-29' in r.CODE_REFERENCE
    # revision 2026-10-31: patches 28/29 adopted, pilot rerun (decision 25 closed by execution), decisions 26/27, checks 27 closed, 31 new
    assert r.CODE_REFERENCE['review_patch_2026-10-29_status'].startswith('adopted') and 'baseline_runner_attribution_2026-10-31' in r.CODE_REFERENCE
    assert r.PENDING_DECISIONS[25]['status_2026-10-31'].startswith('CLOSED BY EXECUTION (a)') and r.PENDING_DECISIONS[23]['status_2026-10-31'].startswith('READY FOR RATIFICATION (a)')
    assert r.PENDING_DECISIONS[26]['status'] == 'OPEN 2026-10-31' and r.PENDING_DECISIONS[26]['recommendation'].startswith('(a)')
    assert r.PENDING_DECISIONS[27]['status'] == 'OPEN 2026-10-31' and len(r.PENDING_DECISIONS[27]['options']) == 3
    assert r.POST_MATERIALIZE_CHECKS[27]['status_2026-10-31'].startswith('CLOSED 2026-10-31') and r.POST_MATERIALIZE_CHECKS[31]['status'] == 'OPEN 2026-10-31'
    assert len(r.CODE_REFERENCE['not_in_repository_2026-10-31']) == 7 and 'results_package_2026-10-31' in r.CODE_REFERENCE and 'execution_status_2026-10-31' in r.GRID_POLICY
    assert r.AUTHOR_RATIFICATIONS_2026_10_24['decisions']['N10'].startswith('RATIFIED')
    # revision 2026-11-03 (round 23): author ratifications of 01/11 and 02/11, team registry drift, PatchTST V0-V6, decisions 28-34, checks 32-35
    a1, a2 = r.AUTHOR_RATIFICATIONS_2026_11_01, r.AUTHOR_RATIFICATIONS_2026_11_02
    assert sorted(a1['decisions']) == ['17', '20', '23', '24', '26', '27'] and all(v.startswith('RATIFIED') for v in a1['decisions'].values())
    assert sorted(a2['decisions']) == ['28', '29', '30', '31'] and all(v.startswith('RATIFIED') for v in a2['decisions'].values())
    assert a1['decisions']['23'].startswith('RATIFIED (a)') and a1['decisions']['20'].startswith('RATIFIED (a-v2)') and a1['decisions']['24'].startswith('RATIFIED (b)')
    for i, tag in ((17, 'RATIFIED (a)'), (20, 'RATIFIED (a-v2)'), (23, 'RATIFIED (a)'), (24, 'RATIFIED (b)'), (26, 'RATIFIED (a)'), (27, 'RATIFIED (a)')):
        assert r.PENDING_DECISIONS[i]['status_2026-11-01'].startswith(tag), i
    for i in (28, 29, 30, 31):
        assert r.PENDING_DECISIONS[i]['status'] == 'CLOSED 2026-11-02' and r.PENDING_DECISIONS[i]['resolution'].startswith('RATIFIED') and r.PENDING_DECISIONS[i]['author_question'] == f'Q-{i - 17}'
    for i, q in ((32, 'Q-16'), (33, 'Q-17'), (34, 'Q-18')):
        d = r.PENDING_DECISIONS[i]
        assert d['status'] == 'OPEN 2026-11-03' and d['author_question'] == q and len(d['options']) == 3 and d['recommendation'].startswith('(a)'), i
    assert 'FIXED_SEED_42' in r.PENDING_DECISIONS[32]['topic'] and r.PENDING_DECISIONS[9]['status'] == 'CLOSED 2026-10-05' and 'team_change_2026-10-31' in r.PENDING_DECISIONS[9]
    assert r.EXPERIMENT_SEEDS['augmentation_policy'] == 'MATCH_MASTER_SEED' and 'team_change_2026-10-31' in r.EXPERIMENT_SEEDS and r.EXPERIMENT_SEEDS['status_2026-11-03'].startswith('this registry keeps MATCH_MASTER_SEED')
    assert '0.50' in r.PENDING_DECISIONS[33]['topic'] and 'nearest-neighbour fallback' in r.PENDING_DECISIONS[33]['options'][0]
    assert '0.9885' in r.PENDING_DECISIONS[34]['topic'] and 'top_offering_share >= 0.5' in r.PENDING_DECISIONS[34]['options'][0]
    assert r.PENDING_DECISIONS[23]['status_2026-11-03'].startswith('CLOSED (a)') and r.PENDING_DECISIONS[25]['status_2026-11-03'].startswith('CLOSED (a)')
    assert r.PENDING_DECISIONS[27]['status_2026-11-02'].startswith('largely superseded') and r.PENDING_DECISIONS[24]['status_2026-11-03'].startswith('the R4-grain LO export')
    assert all(r.POST_MATERIALIZE_CHECKS[i]['status'] == 'OPEN 2026-11-03' for i in (32, 33, 34, 35))
    assert r.POST_MATERIALIZE_CHECKS[31]['status_2026-11-02'].startswith('PASSED for the two F1 base tiers') and r.POST_MATERIALIZE_CHECKS[31]['status_2026-11-03'].startswith('PARTLY CLOSED further')
    assert r.POST_MATERIALIZE_CHECKS[5]['status_2026-11-03'].startswith('EVIDENCE RECEIVED') and r.POST_MATERIALIZE_CHECKS[13]['status_2026-11-03'].startswith('OPEN and now contested')
    assert r.POST_MATERIALIZE_CHECKS[26]['status_2026-11-03'].startswith('PARTLY CLOSED for V0-V6') and '1e-7' in r.POST_MATERIALIZE_CHECKS[32]['check']
    assert 'team_alignment_2026-10-31' in r.S_SAN_FORMULA['v1'] and 'component_behaviour_2026-11-03' in r.S_SAN_FORMULA['v1'] and 'calibration_convention_note_2026-11-03' in r.S_SAN_FORMULA['v2']
    assert 'decomposition_patchtst_2026-11-03' in r.ACCTEMPO_DEF and 'author_mapping_2026-11-01' in r.ACCTEMPO_DEF
    st = r.GRID_POLICY['execution_status_2026-11-03']
    assert st['CQ'].startswith('F2 PatchTST seed 42: V0-V6 complete = 21 cells') and '429 of 1,530' in st['runs'] and '5872cac' in st['repository']
    cr = r.CODE_REFERENCE
    assert len(cr['commits_reviewed_2026-11-03']) == 3 and cr['review_patch_2026-10-31_status'].startswith('adopted') and cr['registry_drift_2026-11-03']['augmentation_policy'].startswith('DIVERGED')
    assert cr['registry_drift_2026-11-03']['s_eff_s_leak'].startswith('CONVERGED') and len(cr['not_in_repository_2026-11-03']) == 9 and 'seed_policy_consistency_2026-11-03' in cr
    regs = r.all_registries()
    assert 'author_ratifications_2026_11_01' in regs and 'author_ratifications_2026_11_02' in regs and len(regs) == 37   # + 2026_11_04, 2026_11_06, open_author_questions_2026_11_10 ... 2026_11_20
    lo = r.SPLIT_REGISTRY['tasks']['LO']
    shares = lo['derived_minority_shares_pct']
    for block, counts in lo['block_classes'].items():
        total = sum(counts.values())
        assert abs(shares[block]['c1_G'] - 100 * counts['c1'] / total) < 0.0006, block
        assert abs(shares[block]['c2_E'] - 100 * counts['c2'] / total) < 0.0006, block
    assert 'macro_policy_code_status_2026-10-17' in r.METRIC_DEF and 'execution_status_2026-10-17' in r.GRID_POLICY
    moment = [m for m in r.RETIRED_MODEL_ROWS if m['model_name'] == 'MOMENT_SMALL'][0]   # retired 2026-11-06 (decision 37)
    assert moment['input_encoding'].startswith('PHASE_AS_PATCH_REPEAT_v1_1') and moment['model_revision'] == 'moment_frozen_linear_probe_v2_1_phase_patch'
    patchtst = [m for m in r.MODEL_REGISTRY if m['model_name'] == 'PATCHTST'][0]
    assert patchtst['channel_mixing'] is False and patchtst['model_revision'] == 'patchtst_channel_independent_v2_1_math_sdp'
    assert r.METRIC_DEF['small_subgroup_flag_implementation_note'].startswith('CLOSED')
    # drift guard: a paraphrased identifier must fail the alignment check
    saved = r.LABEL_ARTIFACTS['CQ']['label_threshold_set']
    r.LABEL_ARTIFACTS['CQ']['label_threshold_set'] = 'PRIMARY'
    try:
        with pytest.raises(AssertionError):
            r.validate_release_alignment()
    finally:
        r.LABEL_ARTIFACTS['CQ']['label_threshold_set'] = saved


def test_registries_rev_2026_11_04_author_ratifications(tmp_path):
    r = registries
    # revision 2026-11-04: author replies of the 04/11 writing session (Q-01, Q-02, Q-03, Q-05, Q-16 .. Q-19, phase-1 scope)
    a4 = r.AUTHOR_RATIFICATIONS_2026_11_04
    assert a4['date'] == '2026-11-04' and set(a4) == {'date', 'source', 'decisions', 'applied_in', 'still_open'}
    assert set(a4['decisions']) >= {'32', '33', '34', '35', '36', 'D-S1-5', 'D-S1-8'} and {'D-S1-6', 'Q-05'} <= set(a4['decisions'])
    assert all(a4['decisions'][k].startswith('RATIFIED (a)') for k in ('32', '33', '34', '35')) and a4['decisions']['36'].startswith('RATIFIED')
    assert 'planned_seeds = [42]' in a4['decisions']['36'] and 'seed 42 only' in a4['decisions']['36'] and 'C1, C4, C5' in a4['decisions']['36']
    assert 'TEMPO-MDS' in a4['decisions']['D-S1-5'] and a4['decisions']['D-S1-8'].startswith('RATIFIED (b)') and 'NOT_AVAILABLE' in a4['decisions']['D-S1-8']
    assert 'kosolwattana2023selfinspected' in a4['decisions']['D-S1-6'] and 'MATCH_MASTER_SEED' in a4['decisions']['32']
    assert 'nearest-neighbour fallback' in a4['decisions']['33'] and 'single_offering_dominant' in a4['decisions']['34'] and '0.4967 kWh' in a4['decisions']['35']
    assert len(a4['applied_in']) == 4 and set(a4['still_open']) == {'M-15', 'outline'}
    assert r.REGISTRY_REVISION == 'registries_rev_2026-11-26b'
    # the open decisions of 03/11 are closed by the ratification keys; 35 and 36 mirror the structure of 34 and are closed on the day
    for i, q in ((32, 'Q-16'), (33, 'Q-17'), (34, 'Q-18')):
        d = r.PENDING_DECISIONS[i]
        assert d['status'] == 'OPEN 2026-11-03' and d['status_2026-11-04'].startswith(f'RATIFIED (a) by the author on 2026-11-04 ({q})'), i
    for i in (35, 36):
        d = r.PENDING_DECISIONS[i]
        assert d['id'] == i and d['status'] == 'CLOSED 2026-11-04' and d['resolution'].startswith('RATIFIED'), i
        assert set(r.PENDING_DECISIONS[34]) - {'status_2026-11-04', 'status_2026-11-09', 'status_2026-11-10'} <= set(d), i   # dated status keys are not structural
    assert r.PENDING_DECISIONS[35]['author_question'] == 'Q-19' and len(r.PENDING_DECISIONS[35]['options']) == 2
    assert 'planned_seeds = [42]' in r.PENDING_DECISIONS[36]['resolution'] and len(r.PENDING_DECISIONS[36]['options']) == 3
    assert 'decision 36' in r.PENDING_DECISIONS[23]['status_2026-11-04'] and 'D-N3' in r.PENDING_DECISIONS[23]['status_2026-11-04']
    assert r.POST_MATERIALIZE_CHECKS[35]['status_2026-11-04'] == 'decision 32 ratified (a); the check now verifies that the four places read MATCH_MASTER_SEED'
    c36 = r.POST_MATERIALIZE_CHECKS[36]
    assert c36['status'] == 'OPEN 2026-11-04' and 'planned_seeds == [42]' in c36['check'] and 'Holm' in c36['check'] and set(c36) - {'status_2026-11-09', 'status_2026-11-10', 'status_2026-11-13', 'verified_2026-11-13', 'status_2026-11-16', 'status_2026-11-20'} == set(r.POST_MATERIALIZE_CHECKS[35]) - {'status_2026-11-04', 'status_2026-11-09'}
    # export: the block is a registry of its own and the sha256 manifest covers it
    regs = r.all_registries()
    assert 'author_ratifications_2026_11_04' in regs and regs['author_ratifications_2026_11_04'] is a4
    man = r.write_registries(str(tmp_path))
    assert os.path.exists(tmp_path / 'author_ratifications_2026_11_04.json') and 'author_ratifications_2026_11_04' in man
    assert man['author_ratifications_2026_11_04'] == seeds.sha256_of(a4) and man['registry_revision'] == 'registries_rev_2026-11-26b'
    with open(tmp_path / 'author_ratifications_2026_11_04.json', encoding='utf-8') as f:
        assert json.load(f)['decisions']['36'] == a4['decisions']['36']


def test_energy_meter_degrades_to_null_without_nvml():
    with en.GpuEnergyMeter(stage='train') as m:
        pass
    r = m.result()
    if en.pynvml is None:
        assert r['energy_gpu_train_kwh'] is None and r['null_reason'] == 'TELEMETRY_UNAVAILABLE'
        assert r['energy_measurement_type'] == 'UNAVAILABLE'
    assert r['energy_boundary'] == 'GPU_ONLY'
    assert en.co2e_from_energy(None, 400, 'x')['null_reason'] == 'TELEMETRY_UNAVAILABLE'
    assert en.co2e_from_energy(1.5, None, None)['null_reason'] == 'NOT_COMPUTED'
    assert en.co2e_from_energy(1.5, 400.0, 'ci_vn_2025')['co2e_gpu_run_g'] == 600.0
    assert en.cost_basis_for_group([{'energy_measurement_type': 'MEASURED', 'energy_gpu_run_kwh': 0.1}] * 3) == 'ENERGY'
    assert en.cost_basis_for_group([{'energy_measurement_type': 'MEASURED', 'energy_gpu_run_kwh': 0.1}, {'energy_measurement_type': 'UNAVAILABLE'}]) == 'TIME'


def test_registries_rev_2026_11_06_f3_mantis(tmp_path):
    r = registries
    # revision 2026-11-06: decision 37 (MOMENT_SMALL / MOMENT_BASE -> MANTIS_V2, EXPLORATORY, full release only) and check 37
    names = [m['model_name'] for m in r.MODEL_REGISTRY]
    assert 'MANTIS_V2' in names and not any(n.startswith('MOMENT') for n in names)
    assert [m['model_name'] for m in r.RETIRED_MODEL_ROWS] == ['MOMENT_SMALL', 'MOMENT_BASE']
    assert all(m['retired_by'] == 'PENDING_DECISIONS[37]' and m['replaced_by'] == 'MANTIS_V2' for m in r.RETIRED_MODEL_ROWS)
    f3 = [m for m in r.MODEL_REGISTRY if m['model_tier'] == 'F3_TS_FOUNDATION']
    assert len(f3) == 1
    m = f3[0]
    assert m['variant_role'] == 'EXPLORATORY' and m['is_pretrained'] == 1 and m['finetune_mode'] == 'LINEAR_PROBE' and m['encoder_frozen'] == 1
    assert m['pretrained_repo'] == 'paris-noah/MantisV2' and m['pretrained_revision'] == '8f6ca35cb54ab14b120618943c6fca5ddf5a76a6'
    assert m['library'] == 'mantis-tsfm==1.1.0' and m['return_transf_layer'] == 2 and m['output_token'] == 'combined'
    assert m['channel_adapter']['n_components'] == 8 and m['channel_adapter']['fit_rows'] == 'REAL_TRAIN_ROWS_ONLY'
    assert m['param_count_backbone_total'] == 4188672 and m['param_count_backbone_used'] == 2214144
    assert m['model_revision'] == 'mantisv2_frozen_linear_probe_v1_pca8_interp512' and m['model_revision'] != r.MODEL_REVISION
    # code review of 2026-11-06 (before delivery): cache identity, strict loading, adapter order, equal values replicated
    assert 'encoder fingerprint' in m['embedding_cache']['key'] and 'stops the run' in m['embedding_cache']['reuse_rule']
    assert m['weight_loading'].startswith('strict') and m['channel_adapter']['fit_order'].startswith('rows sorted by row id')
    assert 'replicated exactly' in m['interp_constant_rows'] and 'independent code review' in m['implementation']
    assert m['selection_metric'] == 'MEAN_PHASE_MACRO_F1' and m['batch_size'] == 2048 and m['lr'] == 1e-3   # COMMON_HPARAMS of the head
    d = r.PENDING_DECISIONS[37]
    assert d['id'] == 37 and d['status'] == 'CLOSED 2026-11-06' and d['resolution'].startswith('APPROVED (b)') and len(d['options']) == 3
    assert len(d['suitability_check_2026-11-06']) == 14 and d['suitability_check_2026-11-06']['K14_validity_domain'].startswith('LIMITATION')
    assert 'MANTIS_V2' in r.PENDING_DECISIONS[11]['update_2026-11-06'] and r.PENDING_DECISIONS[11]['status'].startswith('OPEN')
    c = r.POST_MATERIALIZE_CHECKS[37]
    assert c['status'] == 'OPEN 2026-11-06' and '8f6ca35cb54ab14b120618943c6fca5ddf5a76a6' in c['check'] and 'EXPLORATORY' in c['check']
    assert 'two fresh cache roots' in c['check'] and 'strict key-by-key check' in c['check']
    assert 'superseded by check 37' in r.POST_MATERIALIZE_CHECKS[11]['status_2026-11-06']
    a6 = r.AUTHOR_RATIFICATIONS_2026_11_06
    assert a6['date'] == '2026-11-06' and a6['decisions']['37'].startswith('APPROVED (b)') and set(a6['still_open']) == {'Q-26', 'pilot'}
    regs = r.all_registries()
    assert regs['author_ratifications_2026_11_06'] is a6
    exported = [x['model_name'] for x in regs['model_registry']]
    assert 'MANTIS_V2' in exported and 'MOMENT_SMALL' not in exported
    man = r.write_registries(str(tmp_path))
    assert man['registry_revision'] == 'registries_rev_2026-11-26b' and man['author_ratifications_2026_11_06'] == seeds.sha256_of(a6)
    with open(tmp_path / 'model_registry.json', encoding='utf-8') as f:
        assert [x for x in json.load(f) if x['model_name'] == 'MANTIS_V2'][0]['input_encoding'] == 'PCA8_PER_PHASE_THEN_LINEAR_RESIZE_512_v1'


def test_registries_rev_2026_11_09_round26(tmp_path):
    r = registries
    # revision 2026-11-09: CD3 @ 421dbcd reviewed, full seed-42 F2 grids and the exploratory Mantis grid recorded, decisions 38-41 and checks 38-40
    cr = r.CODE_REFERENCE
    assert cr['previous_reference_2026-11-10'] == '421dbcd (checked 2026-11-09)' and len(cr['commits_reviewed_2026-11-09']) == 3   # base commit moved to 193b584 on 2026-11-10
    assert cr['commits_reviewed_2026-11-09'][0].startswith('cfcfd40') and cr['commits_reviewed_2026-11-09'][2].startswith('421dbcd')
    assert cr['registry_drift_2026-11-09']['augmentation_policy'].startswith('CONVERGED') and cr['seed_policy_consistency_2026-11-09'].startswith('CONSISTENT')
    assert 'byte-identical' in cr['commits_reviewed_2026-11-09'][1] and 'NOT in the repository' in cr['commits_reviewed_2026-11-09'][1]
    assert 'registries_rev_2026-11-08_d32_mantis_local' in cr['team_registry_revision_2026-11-09']
    assert len(cr['not_in_repository_2026-11-09']) == 9 and cr['not_in_repository_2026-11-09'][0].startswith('f3_mantis tests (34)')
    # seed policy converged on the team side; decision 32 and check 35 closed on the code side, seeds 43/44 still phase 2
    assert r.EXPERIMENT_SEEDS['augmentation_policy'] == 'MATCH_MASTER_SEED' and r.EXPERIMENT_SEEDS['status_2026-11-09'].startswith('CONVERGED')
    assert r.PENDING_DECISIONS[32]['status_2026-11-09'].startswith('CLOSED on the code side') and r.PENDING_DECISIONS[32]['status'] == 'OPEN 2026-11-03'   # base key unchanged since 03/11
    assert r.PENDING_DECISIONS[9]['status_2026-11-09'].startswith('team registry @ 421dbcd')
    c35 = r.POST_MATERIALIZE_CHECKS[35]
    assert c35['status_2026-11-09'].startswith('PASS on the code side at 421dbcd') and 'tools/vastai_train_shared.py' in c35['status_2026-11-09']
    assert 'modal_jobs/README.md lines 157, 168, 277' in c35['status_2026-11-09'] and 'stays open' in c35['status_2026-11-09']
    # execution status: every seed-42 F1/F2 cell exists, Mantis exploratory, LO facts carry decision 38
    st = r.GRID_POLICY['execution_status_2026-11-09']
    assert st['CQ'].startswith('F2 PatchTST seed 42 complete: V0-V16 = 51 cells') and 'EXPLORATORY_CACHE_VALIDATION' in st['CQ'] and '29da3b2' in st['CQ']
    assert st['LO'].startswith('F2 PatchTST seed 42 complete: V0-V16 = 51 cells') and 'runner_git_commit NOT RECORDED' in st['LO']
    assert '510 of 1,530' in st['runs'] and 'seeds 43/44: nothing' in st['runs'] and '421dbcd' in st['repository']
    assert '440 values compared, 0 mismatches' in st['numbers']
    assert r.GRID_POLICY['execution_status_2026-11-03']['CQ'].startswith('F2 PatchTST seed 42: V0-V6 complete')   # history kept
    # component behaviour: CQ exports single-valued, LO F2 mixes three probe fits
    cb = r.S_SAN_FORMULA['v1']['component_behaviour_2026-11-09']
    assert 'within 1.2e-5' in cb and 'three probe fits coexist' in cb and 'up to 0.0139' in cb and 'up to 0.0163' in cb
    # decisions 38-41 open with author questions Q-27..Q-30
    for i, q in zip((38, 39, 40, 41), ('Q-27', 'Q-28', 'Q-29', 'Q-30')):
        d = r.PENDING_DECISIONS[i]
        assert d['id'] == i and d['status'] == 'OPEN 2026-11-09' and d['author_question'] == q and len(d['options']) == 3 and d['recommendation']
    assert r.PENDING_DECISIONS[38]['recommendation'].startswith('(a)') and 'single LO F1 standard probe table' in r.PENDING_DECISIONS[38]['options'][0]
    assert r.PENDING_DECISIONS[39]['recommendation'].startswith('(a)') and 'tr_inactive_learner_ratio' in r.PENDING_DECISIONS[39]['topic']
    assert r.PENDING_DECISIONS[40]['recommendation'].startswith('(a)') and 'metamodel_handoff_2026-11-09.zip' in r.PENDING_DECISIONS[40]['topic']
    assert r.PENDING_DECISIONS[41]['recommendation'].startswith('(b)') and 'V7-V16' in r.PENDING_DECISIONS[41]['topic']
    assert r.PENDING_DECISIONS[36]['status_2026-11-09'].startswith('milestone 2026-11-09 missed for M-14')
    assert r.PENDING_DECISIONS[37]['status_2026-11-09'].startswith('the team integrated f3_mantis 0.1.0 byte-identically')
    # checks 38-40
    c38, c39, c40 = (r.POST_MATERIALIZE_CHECKS[i] for i in (38, 39, 40))
    assert c38['status'].startswith('OPEN 2026-11-09: PASS for cq_patchtst_v7_v16') and 'FAIL for lo_patchtst_v0_v16' in c38['status'] and 'within 1e-9' in c38['check']
    assert c39['status'].startswith('OPEN 2026-11-09') and 'runner_git_commit' in c39['check']
    assert c40['status'].startswith('OPEN 2026-11-09') and '48 rows' in c40['check'] and 'MANTIS_V2 row to be added' in c40['check']
    c37 = r.POST_MATERIALIZE_CHECKS[37]
    assert c37['status'] == 'OPEN 2026-11-06' and c37['status_2026-11-09'].startswith('PARTLY MET, out of order') and '(h)' in c37['additions_2026-11-09'] and '(i)' in c37['additions_2026-11-09']
    assert r.POST_MATERIALIZE_CHECKS[31]['status_2026-11-09'].startswith('PASSED for the three full-grid facts packages') and r.POST_MATERIALIZE_CHECKS[36]['status_2026-11-09'].startswith('inputs delivered')
    # nothing of 2026-11-06 changed: MANTIS_V2 row, ratifications, decision 37 resolution
    assert [m['model_name'] for m in r.RETIRED_MODEL_ROWS] == ['MOMENT_SMALL', 'MOMENT_BASE'] and r.PENDING_DECISIONS[37]['status'] == 'CLOSED 2026-11-06'
    man = r.write_registries(str(tmp_path))
    assert man['registry_revision'] == 'registries_rev_2026-11-26b'
    with open(tmp_path / 'pending_decisions.json', encoding='utf-8') as f:
        pend = json.load(f)
    assert [d['id'] for d in pend] == list(range(63)) and pend[38]['author_question'] == 'Q-27'
    with open(tmp_path / 'post_materialize_checks.json', encoding='utf-8') as f:
        assert len(json.load(f)) == 49   # check 48 added 2026-11-26 (second pass); checks 44, 45 added 2026-11-20; check 43 added 2026-11-16


def test_registries_rev_2026_11_10_round27(tmp_path):
    r = registries
    # revision 2026-11-10: CD3 @ 193b584 (six commits of 10/11), the r2 packages, the M-14 release, decisions 42/43, check 41
    cr = r.CODE_REFERENCE
    assert cr['previous_reference_2026-11-13'] == '193b584 (checked 2026-11-10)' and cr['previous_reference_2026-11-10'] == '421dbcd (checked 2026-11-09)'   # base commit moved to cb575df on 2026-11-16
    assert cr['previous_reference_2026-11-09'] == '5872cac (checked 2026-11-03)' and cr['previous_reference_2026-11-03'] == '3bdb8b6 (checked 2026-10-31)'
    rev = cr['commits_reviewed_2026-11-10']
    assert len(rev) == 6 and [c[:7] for c in rev] == ['8cf8b9b', '8c3fd80', 'ea19afa', 'ba5c1c6', 'f478b23', '193b584']
    assert 'lbfgs' in rev[2] and '1e-9' in rev[2] and 'test_leak_probe_determinism.py (4 tests' in rev[2]
    assert 'df2a867' not in rev[3] and 'check_gpu.py not in the repository' in rev[3] and '2cc8e3f8' in rev[3]
    assert 'v1_3_change_2026-10-24' in cr['team_registry_revision_2026-11-10'] and 'test_metric_def_maps_the_paper_objectives_d18' in cr['team_registry_revision_2026-11-10']
    assert cr['review_2026-11-10']['verdict'].startswith('the six commits implement') and len(cr['review_2026-11-10']['notes']) == 5
    assert len(cr['not_in_repository_or_drive_2026-11-10']) == 6 and len(cr['resolved_since_2026-11-09']) == 7
    assert len(cr['not_in_repository_2026-11-09']) == 9   # history kept
    # execution status 10/11: M-14 assembled, M-15 not run, LO Mantis running, phase 2 not started
    st = r.GRID_POLICY['execution_status_2026-11-10']
    assert st['meta'].startswith('M-14 assembled by the team on 09/11 17:04 UTC') and '3,672 seed-level' in st['meta'] and 'e1fdb8e3' in st['meta']
    assert 'run_level_invariant 0.0' in st['meta'] and 'M-15' in st['meta'] and 'SUPERSEDED' in st['meta']
    assert 'MANTIS_V2 grid running' in st['LO'] and 'df2a867' in st['LO'] and '6a69b7f' in st['CQ'] and 'V0 NULL' in st['CQ']
    assert 'seeds 43/44: nothing' in st['runs'] and '193b584' in st['repository'] and '198/198 ok' in st['archive']
    assert r.GRID_POLICY['execution_status_2026-11-09']['CQ'].startswith('F2 PatchTST seed 42 complete')   # history kept
    # component behaviour 10/11: LO r2 exact, CQ packages within 4.98e-5 / 1.24e-5
    cb = r.S_SAN_FORMULA['v1']['component_behaviour_2026-11-10']
    assert '|diff| 0.0' in cb and '4.98e-5' in cb and '1.24e-5' in cb and '2.09e-6' in cb and 'acctempo_m4 387, 0.01658' in cb
    # decisions 38-41 executed by the team, 42/43 new and open
    for i in (38, 39, 40, 41):
        assert r.PENDING_DECISIONS[i]['status'] == 'OPEN 2026-11-09' and 'EXECUTED' in r.PENDING_DECISIONS[i]['status_2026-11-10']
    assert r.PENDING_DECISIONS[38]['status_2026-11-10'].startswith('option (a) EXECUTED') and 'identity spread 0.0' in r.PENDING_DECISIONS[38]['status_2026-11-10']
    assert r.PENDING_DECISIONS[39]['status_2026-11-10'].startswith('option (c) EXECUTED') and 'changes its recommendation to (c)' in r.PENDING_DECISIONS[39]['status_2026-11-10']
    assert r.PENDING_DECISIONS[40]['status_2026-11-10'].startswith('option (a) EXECUTED') and 'metamodel 0.2.2' in r.PENDING_DECISIONS[40]['status_2026-11-10']
    assert r.PENDING_DECISIONS[41]['status_2026-11-10'].startswith('option (b) EXECUTED') and '+240' in r.PENDING_DECISIONS[41]['status_2026-11-10'] and '3,672' in r.PENDING_DECISIONS[41]['status_2026-11-10']
    for i, q in ((42, 'Q-31'), (43, 'Q-32')):
        d = r.PENDING_DECISIONS[i]
        assert d['id'] == i and d['status'] == 'OPEN 2026-11-10' and d['author_question'] == q and len(d['options']) == 3 and d['recommendation'].startswith('(a)')
    assert 'TOL_LEAK_IDENTITY' in r.PENDING_DECISIONS[42]['blocks'][1] and 'reference-copy contract' in r.PENDING_DECISIONS[42]['options'][0]
    assert '1e-5 as proposed by the team' in r.PENDING_DECISIONS[42]['options'][2] and 'NOT_RECORDED_V0_EARLIER_SCRIPT' in r.PENDING_DECISIONS[43]['topic']
    oq = r.OPEN_AUTHOR_QUESTIONS_2026_11_10
    assert list(oq) == ['Q-27', 'Q-28', 'Q-29', 'Q-30', 'Q-31', 'Q-32'] and [oq[q]['decision'] for q in oq] == [38, 39, 40, 41, 42, 43]
    assert oq['Q-31']['executed_by_team'] is None and oq['Q-30']['executed_by_team'] == '(b)'
    # checks 36-40 status, 41 new
    c36, c37, c38, c39, c40, c41 = (r.POST_MATERIALIZE_CHECKS[i] for i in (36, 37, 38, 39, 40, 41))
    assert c36['status_2026-11-10'].startswith('release half MET') and 'mm_runs half NOT MET' in c36['status_2026-11-10']
    assert c37['status_2026-11-10'].startswith('LARGELY MET') and 'not on the Drive' in c37['status_2026-11-10'] and '36ee17d9' in c37['status_2026-11-10']
    assert c38['status_2026-11-10'].startswith('LO r2 PASS at 0.0') and 'decision 42' in c38['status_2026-11-10'] and c38['status'].startswith('OPEN 2026-11-09')
    assert c39['status_2026-11-10'].startswith('LARGELY MET for the r2 packages') and 'decision 43' in c39['status_2026-11-10']
    assert c40['status_2026-11-10'].startswith('PASS on the files') and '2,226,510' in c40['status_2026-11-10'] and '113 columns' in c40['status_2026-11-10']
    assert c41['id'] == 41 and c41['status'] == 'OPEN 2026-11-10' and 'check_leak_probe_reproduction_20261109.py' in c41['check'] and 'decision 42' in c41['check']
    # nothing structural of 2026-11-09 changed
    assert r.PENDING_DECISIONS[37]['status'] == 'CLOSED 2026-11-06' and r.POST_MATERIALIZE_CHECKS[35]['status_2026-11-09'].startswith('PASS on the code side at 421dbcd')
    man = r.write_registries(str(tmp_path))
    assert man['registry_revision'] == 'registries_rev_2026-11-26b' and 'open_author_questions_2026_11_10' in man
    with open(tmp_path / 'pending_decisions.json', encoding='utf-8') as f:
        pend = json.load(f)
    assert [d['id'] for d in pend] == list(range(63)) and pend[42]['author_question'] == 'Q-31' and pend[43]['author_question'] == 'Q-32'
    with open(tmp_path / 'post_materialize_checks.json', encoding='utf-8') as f:
        assert len(json.load(f)) == 49   # check 48 added 2026-11-26 (second pass); checks 44, 45 added 2026-11-20; check 43 added 2026-11-16
    with open(tmp_path / 'open_author_questions_2026_11_10.json', encoding='utf-8') as f:
        assert json.load(f) == oq


def test_registries_rev_2026_11_13_round28(tmp_path):
    r = registries
    cr = r.CODE_REFERENCE
    assert r.REGISTRY_REVISION == 'registries_rev_2026-11-26b' and cr['previous_reference_2026-11-16'] == '7cad8b1 (checked 2026-11-13)'   # base commit moved to cb575df on 2026-11-16 and to 6274591 on 2026-11-20
    rev = cr['commits_reviewed_2026-11-13']
    assert len(rev) == 15 and rev[0].startswith('18d00fe') and rev[-1].startswith('7cad8b1') and '1e-9' in rev[3] and '1e-3' in rev[4]
    assert cr['review_2026-11-13']['verdict'].startswith('the fifteen commits are tooling') and len(cr['review_2026-11-13']['notes']) == 5
    assert 'd18_mantis_clean' in cr['team_registry_revision_2026-11-13'] and len(cr['commits_reviewed_2026-11-10']) == 6   # history kept
    st = r.GRID_POLICY['execution_status_2026-11-13']
    assert st['meta'].startswith('M-15 phase 1 delivered on 13/11') and 'none of H1-H8 supported' in st['meta'] and '0494d1a5' in st['meta']
    assert '203/204' in st['CQ'] and '204/204' in st['LO'] and 'not citable' not in st['runs'] and 'is citable' in st['numbers'] and '7cad8b1' in st['repository']
    assert r.GRID_POLICY['execution_status_2026-11-10']['meta'].startswith('M-14 assembled by the team')   # history kept
    assert r.PENDING_DECISIONS[36]['status_2026-11-13'].startswith('M-15 delivered on 2026-11-13') and 'decision 44' in r.PENDING_DECISIONS[36]['status_2026-11-13']
    assert r.PENDING_DECISIONS[42]['status_2026-11-13'].startswith('option (a) EXECUTED by the team on 2026-11-10') and r.PENDING_DECISIONS[42]['status'] == 'OPEN 2026-11-10'
    assert '*_RETROACTIVE' in r.PENDING_DECISIONS[43]['status_2026-11-13']
    for i, q in ((44, 'Q-33'), (45, 'Q-34')):
        d = r.PENDING_DECISIONS[i]
        assert d['id'] == i and d['status'] == 'OPEN 2026-11-13' and d['author_question'] == q and len(d['options']) == 3 and d['recommendation'].startswith('(a)')
    assert '-0.0014' in r.PENDING_DECISIONS[44]['topic'] and 'D-18' in r.PENDING_DECISIONS[44]['recommendation'] and 'monotonically' in r.PENDING_DECISIONS[45]['topic']
    oq = r.OPEN_AUTHOR_QUESTIONS_2026_11_13
    assert list(oq) == ['Q-14', 'Q-27', 'Q-28', 'Q-30', 'Q-31', 'Q-32', 'Q-33', 'Q-34'] and oq['Q-33']['decision'] == 44 and oq['Q-34']['decision'] == 45
    c = r.POST_MATERIALIZE_CHECKS
    assert [x['id'] for x in c] == list(range(49)) and c[42]['status'].startswith('PASSED 2026-11-13') and '4.98e-5' in c[42]['check']   # closed in round 28b
    assert c[36]['status_2026-11-13'].startswith('release half MET per the team L2 receipt') and 'DELIVERED on 2026-11-13' in c[36]['status_2026-11-13']
    assert '9.6e-4' in c[41]['status_2026-11-13'] and c[41]['status'] == 'OPEN 2026-11-10' and 'six CONDITIONS_MET' in c[39]['status_2026-11-13']
    regs = r.all_registries()
    assert 'open_author_questions_2026_11_13' in regs and 'open_author_questions_2026_11_10' in regs
    man = r.write_registries(str(tmp_path))
    assert man['registry_revision'] == 'registries_rev_2026-11-26b' and 'open_author_questions_2026_11_13' in man


def test_registries_round28b_check42():
    r = registries
    c = r.POST_MATERIALIZE_CHECKS[42]
    assert c['status'].startswith('PASSED 2026-11-13') and 'report_derived' in c['result_2026-11-13'] and '510' in c['result_2026-11-13'] and 'H6 not re-derived' in c['result_2026-11-13']
    assert 'status_2026-11-13_verified' in r.POST_MATERIALIZE_CHECKS[38]
    q = r.OPEN_AUTHOR_QUESTIONS_2026_11_13['Q-14']
    assert q['status'] == 'CLOSED 2026-11-13' and q['executed_by_author'].startswith('(a)')


def test_registries_rev_2026_11_13_r2_author_ratifications(tmp_path):
    r = registries
    a = r.AUTHOR_RATIFICATIONS_2026_11_13
    assert r.REGISTRY_REVISION == 'registries_rev_2026-11-26b' and a['date'] == '2026-11-13' and list(a['decisions']) == ['38', '39', '41', '42', '43', '44', '45']
    assert a['decisions']['44'].startswith('RATIFIED (a) [Q-33]') and a['decisions']['39'].startswith('RATIFIED (c) [Q-28]') and a['decisions']['41'].startswith('RATIFIED (b) [Q-30]')
    assert 'report-derived' in a['other']['correction'] and a['still_open'] == ['Q-20', 'Q-21', 'Q-22', 'Q-23', 'Q-24', 'Q-26']
    for i, q in ((38, 'Q-27'), (39, 'Q-28'), (41, 'Q-30'), (42, 'Q-31'), (43, 'Q-32'), (44, 'Q-33'), (45, 'Q-34')):
        d = r.PENDING_DECISIONS[i]
        assert d['id'] == i and d['ratified_2026-11-13'].startswith('RATIFIED') and f'({q})' in d['ratified_2026-11-13'] and d['status'].startswith('OPEN')   # base key kept
    assert 'at least 10 clusters' in r.PENDING_DECISIONS[45]['ratified_2026-11-13'] and 'TOL_LEAK_IDENTITY = 1e-9' in r.PENDING_DECISIONS[42]['ratified_2026-11-13']
    assert 'seven qa_* flags are 1.0' in r.POST_MATERIALIZE_CHECKS[36]['verified_2026-11-13']
    assert 'numbers_after_ratification' in r.GRID_POLICY['execution_status_2026-11-13']
    man = r.write_registries(str(tmp_path))
    assert 'author_ratifications_2026_11_13' in man and man['registry_revision'] == 'registries_rev_2026-11-26b'


def test_registries_rev_2026_11_16_round29(tmp_path):
    r = registries
    cr = r.CODE_REFERENCE
    assert r.REGISTRY_REVISION == 'registries_rev_2026-11-26b' and cr['previous_reference_2026-11-20'] == 'cb575df (checked 2026-11-16)'   # base commit moved to 6274591 on 2026-11-20 and to fc361b6 on 2026-11-21
    rev = cr['commits_reviewed_2026-11-16']
    assert len(rev) == 5 and rev[0].startswith('2152d49') and rev[-1].startswith('cb575df') and 'copy-reference' in rev[0] and '1e-3' in rev[3]
    assert cr['review_2026-11-16']['verdict'].startswith('the five commits') and len(cr['review_2026-11-16']['notes']) == 3 and len(cr['uncommitted_tools_2026-11-16']) == 5
    assert len(cr['commits_reviewed_2026-11-13']) == 15 and cr['previous_reference_2026-11-16'] == '7cad8b1 (checked 2026-11-13)'   # history kept
    st = r.GRID_POLICY['execution_status_2026-11-16']
    assert st['CQ'].startswith('seed 43 COMPLETE') and st['LO'].startswith('seed 43 COMPLETE') and '5ba9829' in st['CQ'] and '6a69b7f' in st['LO'] and 'NOT measured' in st['CQ']
    assert '58 columns' in st['meta'] and 'cb575df' in st['repository'] and 'uncommitted' in st['repository'] and '1,044 files' in st['archive'] and 'decision 46' in st['numbers']
    assert r.GRID_POLICY['execution_status_2026-11-13']['meta'].startswith('M-15 phase 1 delivered on 13/11')   # history kept
    for i in (36, 42, 43, 44, 45):
        assert 'status_2026-11-16' in r.PENDING_DECISIONS[i] and (i == 36 or 'ratified_2026-11-13' in r.PENDING_DECISIONS[i])
    assert 'decision 46' in r.PENDING_DECISIONS[36]['status_2026-11-16'] and '5.6e-17' in r.PENDING_DECISIONS[42]['status_2026-11-16'] and '510/510' in r.PENDING_DECISIONS[43]['status_2026-11-16']
    for i, q in ((46, 'Q-35'), (47, 'Q-36')):
        d = r.PENDING_DECISIONS[i]
        assert d['id'] == i and d['status'] == 'OPEN 2026-11-16' and d['author_question'] == q and len(d['options']) == 3 and d['recommendation'].startswith('(a)')
    assert 'Spearman 0.12-0.84' in r.PENDING_DECISIONS[46]['topic'] and 'MODEL_REGISTRY' in r.PENDING_DECISIONS[47]['topic']
    oq = r.OPEN_AUTHOR_QUESTIONS_2026_11_16
    assert list(oq) == ['Q-35', 'Q-36', 'still_open'] and oq['Q-35']['decision'] == 46 and oq['Q-36']['decision'] == 47 and oq['still_open'] == ['Q-20', 'Q-21', 'Q-22', 'Q-23', 'Q-24', 'Q-26']
    c = r.POST_MATERIALIZE_CHECKS
    assert [x['id'] for x in c][:44] == list(range(44)) and c[43]['status'].startswith('PASSED 2026-11-16') and '84/84' in c[43]['status'] and '168/168' in c[43]['status'] and '0/204' in c[43]['status']
    assert c[38]['status_2026-11-16'].startswith('PASSED on the six seed-43 packages') and '1.1e-16' in c[38]['status_2026-11-16']
    assert c[22]['status_2026-11-16'].startswith('CLOSED 2026-11-16') and 'OTHER_RELEASE 187' in c[22]['status_2026-11-16'] and c[22]['status'].startswith('OPEN 2026-10-23')   # base key kept
    assert 'decision 47' in c[39]['status_2026-11-16'] and '58 columns' in c[36]['status_2026-11-16'] and '5.6e-17' in c[41]['status_2026-11-16'] and 'seed-43 package' in c[37]['status_2026-11-16']
    regs = r.all_registries()
    assert 'open_author_questions_2026_11_16' in regs and 'open_author_questions_2026_11_13' in regs and len(regs) == 37
    man = r.write_registries(str(tmp_path))
    assert man['registry_revision'] == 'registries_rev_2026-11-26b' and 'open_author_questions_2026_11_16' in man


def test_registries_rev_2026_11_20_round30(tmp_path):
    r = registries
    cr = r.CODE_REFERENCE
    assert r.REGISTRY_REVISION == 'registries_rev_2026-11-26b' and cr['previous_reference_2026-11-21'] == '6274591 (checked 2026-11-20)'
    rev = cr['commits_reviewed_2026-11-20']
    assert len(rev) == 3 and rev[0].startswith('7c24981') and rev[1].startswith('11941f1') and rev[2].startswith('6274591') and '--skip-probe-refit' in rev[0]
    assert cr['review_2026-11-20']['verdict'].startswith('the three commits') and len(cr['review_2026-11-20']['notes']) == 4 and len(cr['not_in_repository_2026-11-20']) == 8
    assert any('phaseB_orch.py' in x for x in cr['not_in_repository_2026-11-20']) and len(cr['resolved_since_2026-11-16']) == 2
    assert len(cr['commits_reviewed_2026-11-16']) == 5 and len(cr['uncommitted_tools_2026-11-16']) == 5   # history kept
    st = r.GRID_POLICY['execution_status_2026-11-20']
    assert list(st) == ['CQ', 'LO', 'runs', 'meta', 'repository', 'archive', 'numbers']
    assert st['CQ'].startswith('seed 44 COMPLETE') and st['LO'].startswith('seed 44 COMPLETE') and '1,836 runs' in st['runs'] and '1,605 of 1,836' in st['runs']
    assert '+0.0029 [0.0006, 0.0057]' in st['meta'] and 'H6 supported' in st['meta'] and '0.2.5' in st['meta'] and '11-18 of 182' in st['meta'] and '10 MB' in st['meta']
    assert 'decision 48' in st['numbers'] and 'check 45' in st['numbers'] and r.GRID_POLICY['execution_status_2026-11-16']['CQ'].startswith('seed 43 COMPLETE')   # history kept
    for i in (36, 42, 43, 44, 45, 46, 47):
        assert 'status_2026-11-20' in r.PENDING_DECISIONS[i], i
    assert 'decision 48' in r.PENDING_DECISIONS[44]['status_2026-11-20'] and r.PENDING_DECISIONS[46]['status'] == 'OPEN 2026-11-16' and 'moves from (a) to (b)' in r.PENDING_DECISIONS[46]['status_2026-11-20']
    assert [d['id'] for d in r.PENDING_DECISIONS] == list(range(63))
    for i, q in ((48, 'Q-37'), (49, 'Q-38'), (50, 'Q-39')):
        d = r.PENDING_DECISIONS[i]
        assert d['id'] == i and d['status'] == 'OPEN 2026-11-20' and d['author_question'] == q and len(d['options']) == 3 and d['recommendation'].startswith('(a)')
    assert '+0.0029 [0.0006, 0.0057]' in r.PENDING_DECISIONS[48]['topic'] and '71' not in r.PENDING_DECISIONS[48]['topic'] and '26.49 kWh' in r.PENDING_DECISIONS[49]['topic']
    oq = r.OPEN_AUTHOR_QUESTIONS_2026_11_20
    d = r.PENDING_DECISIONS[51]
    assert d['author_question'] == 'Q-40' and d['status'] == 'OPEN 2026-11-20' and len(d['options']) == 3 and 'five mandatory subgroups' in d['topic'] and '96 clusters' in d['topic']
    assert 'decision 51' in r.PENDING_DECISIONS[48]['topic'] and 'decision 51' in r.PENDING_DECISIONS[44]['status_2026-11-20'] and 'decision 51' in st['meta'] and 'decision 51' in st['numbers']
    assert [oq[k]['decision'] for k in ('Q-37', 'Q-38', 'Q-39', 'Q-40')] == [48, 49, 50, 51] and oq['still_open'] == ['Q-20', 'Q-21', 'Q-22', 'Q-23', 'Q-24', 'Q-26', 'Q-35', 'Q-36']
    c = r.POST_MATERIALIZE_CHECKS
    assert [x['id'] for x in c] == list(range(49)) and c[44]['status'].startswith('PASSED 2026-11-20') and '84/84' in c[44]['status'] and '288/288' in c[44]['status'] and '604/612' in c[44]['status']
    assert c[45]['status'].startswith('PARTIAL 2026-11-20') and 'NOT MET' in c[45]['status'] and 'metamodel 0.2.5' in c[45]['closes_when']
    for i in (22, 36, 38, 39, 41):
        assert 'status_2026-11-20' in c[i], i
    assert c[38]['status_2026-11-20'].startswith('PASSED on the six seed-44 packages') and 'PARTIAL' in c[36]['status_2026-11-20'] and c[43]['status'].startswith('PASSED 2026-11-16')   # history kept
    regs = r.all_registries()
    assert 'open_author_questions_2026_11_20' in regs and len(regs) == 37
    man = r.write_registries(str(tmp_path))
    assert man['registry_revision'] == 'registries_rev_2026-11-26b' and 'open_author_questions_2026_11_20' in man and len(man) == 38


def test_registries_rev_2026_11_20b_author_decisions(tmp_path):
    r = registries
    assert r.REGISTRY_REVISION == 'registries_rev_2026-11-26b' and 'subgroup_tooling_2026-11-20b' in r.CODE_REFERENCE   # no new commit reviewed in the second pass
    tool = r.CODE_REFERENCE['subgroup_tooling_2026-11-20b']
    assert len(tool['findings']) == 3 and '_slice_rows' in tool['findings'][0] and 'no LEARNER slice' in tool['findings'][2] and 'no inference' in tool['consequence']
    a = r.AUTHOR_RATIFICATIONS_2026_11_20
    assert a['date'] == '2026-11-20' and list(a['decisions']) == ['46', '47', '48', '49', '50', '51']
    assert [a['decisions'][k].split(' [')[0] for k in a['decisions']] == ['RATIFIED (b)', 'RATIFIED (a)', 'RATIFIED (a)', 'RATIFIED (a)', 'RATIFIED (a)', 'RATIFIED (b)']
    assert [a['decisions'][k].split('[')[1].split(']')[0] for k in a['decisions']] == ['Q-35', 'Q-36', 'Q-37', 'Q-38', 'Q-39', 'Q-40']
    assert set(a['corrections']) == {'cohort_audits', 'situations', 'executed_analysis', 'effort'} and '58,752' in a['corrections']['effort']
    assert 'check 47' in a['decisions']['48'] and 'no outcome of H1' in a['decisions']['48'] and '1,605 of 1,836' in a['decisions']['49']
    assert a['still_open'] == ['Q-20', 'Q-21', 'Q-22', 'Q-23', 'Q-24', 'Q-26', 'Q-41', 'Q-42', 'Q-43'] and len(a['consequences']) == 7
    pend = r.PENDING_DECISIONS
    assert [d['id'] for d in pend] == list(range(63))
    for i, opt in ((46, '(b)'), (47, '(a)'), (48, '(a)'), (49, '(a)'), (50, '(a)'), (51, '(b)')):
        assert pend[i]['ratified_2026-11-20'].startswith(f'RATIFIED {opt} by the author on 2026-11-20'), i
    assert pend[51]['correction_2026-11-20b'].startswith('(1) the cohort audits do not hold the four slices') and 'correction_2026-11-20b' not in pend[50]
    assert 'instead of 240' in pend[51]['topic']        # the text of 20/11 is kept as written; the correction is a separate key
    for i, q, n_opt in ((52, 'Q-41', 3), (53, 'Q-42', 2), (54, 'Q-43', 2)):
        d = pend[i]
        assert d['id'] == i and d['status'] == 'OPEN 2026-11-20' and d['author_question'] == q and len(d['options']) == n_opt and d['recommendation'].startswith('(a)')
        assert 'check 47' in d['blocks'] and 'ratified_2026-11-20' not in d and 'ratified_2026-11-21' in d
    assert 'section 10.10' in pend[52]['topic'] and 'Appendix E.4' in pend[52]['topic'] and 'Table 46' in pend[53]['topic'] and 'analysis_role' in pend[54]['options'][0]
    oq = r.OPEN_AUTHOR_QUESTIONS_2026_11_20B
    assert [oq[k]['decision'] for k in ('Q-41', 'Q-42', 'Q-43')] == [52, 53, 54] and oq['answered_2026-11-20'] == {'Q-35': '(b)', 'Q-36': '(a)', 'Q-37': '(a)', 'Q-38': '(a)', 'Q-39': '(a)', 'Q-40': '(b)'}
    assert oq['still_open'] == a['still_open'] and r.OPEN_AUTHOR_QUESTIONS_2026_11_20['still_open'][-2:] == ['Q-35', 'Q-36']   # history kept
    c = r.POST_MATERIALIZE_CHECKS
    assert [x['id'] for x in c] == list(range(49)) and 'status_2026-11-20b' in c[39] and 'status_2026-11-20b' in c[45]
    assert 'decision 47 (a)' in c[39]['status_2026-11-20b'] and 'metamodel 0.2.6' in c[45]['status_2026-11-20b'] and 'checks 46 and 47' in c[45]['status_2026-11-20b']
    assert c[45]['status'].startswith('PARTIAL 2026-11-20')     # the status of the first pass is kept
    assert c[46]['status'].startswith('NOT STARTED 2026-11-20') and '58,752' in c[46]['check'] and '73,440' in c[46]['check'] and '240 rows' in c[46]['check']
    assert set(c[46]['conventions']) == {'s_leak', 'undefined_slice', 'row_order'} and 'INFEASIBLE' in c[46]['conventions']['undefined_slice']
    assert c[47]['status'].startswith('NOT STARTED 2026-11-20') and 'decisions 52-54' in c[47]['status'] and 'frozen' in c[47]['check']
    st = r.GRID_POLICY['execution_status_2026-11-20b']
    assert list(st) == ['decisions', 'base_tier', 'meta', 'package', 'numbers'] and 'check 47' in st['numbers'] and 'metamodel 0.2.6' in st['package']
    assert r.GRID_POLICY['execution_status_2026-11-20']['CQ'].startswith('seed 44 COMPLETE')   # history kept
    regs = r.all_registries()
    assert 'author_ratifications_2026_11_20' in regs and 'open_author_questions_2026_11_20b' in regs and len(regs) == 37
    man = r.write_registries(str(tmp_path))
    assert man['registry_revision'] == 'registries_rev_2026-11-26b' and man['author_ratifications_2026_11_20'] == seeds.sha256_of(a) and len(man) == 38


def test_registries_rev_2026_11_21_author_decisions(tmp_path):
    r = registries
    cr = r.CODE_REFERENCE
    assert r.REGISTRY_REVISION == 'registries_rev_2026-11-26b' and cr['previous_reference_2026-11-24'].startswith('fc361b6 (checked 2026-11-21')   # base commit moved to ecad59d on 2026-11-24
    rev = cr['commits_reviewed_2026-11-21']
    assert len(rev) == 4 and [x[:7] for x in rev] == ['8494886', 'f6cefe7', '35e806e', 'fc361b6'] and 'subgroups_phaseB' in rev[0]
    assert cr['review_2026-11-21']['verdict'].startswith('the four commits') and len(cr['review_2026-11-21']['notes']) == 6 and len(cr['review_2026-11-21']['open']) == 4
    a = r.AUTHOR_RATIFICATIONS_2026_11_21
    assert a['date'] == '2026-11-21' and list(a['decisions']) == ['52', '53', '54']
    assert [a['decisions'][k].split(' [')[0] for k in a['decisions']] == ['RATIFIED (a)', 'RATIFIED (a)', 'RATIFIED (b)']
    assert [a['decisions'][k].split('[')[1].split(']')[0] for k in a['decisions']] == ['Q-41', 'Q-42', 'Q-43'] and 'had recommended (a)' in a['decisions']['54']
    assert set(a['confirmations']) == {'facts_contract_conventions', 'reading_of_decisions_48_and_51'} and 'no outcome of H1' in a['confirmations']['reading_of_decisions_48_and_51']
    assert set(a['implementation']) == {'decision_52', 'decision_53', 'decision_54'} and '3 tiers x 2 tasks' in a['implementation']['decision_52']
    assert 'DESCRIPTIVE' in a['implementation']['decision_54'] and 'decision 55' in a['readings_recorded_by_the_writing_side']['secondary_slices']
    assert 'has not opened' in a['state_of_knowledge_at_the_decision']['exploratory_per_task_run'] and a['still_open'][-2:] == ['Q-44', 'Q-45']
    pend = r.PENDING_DECISIONS
    assert [d['id'] for d in pend] == list(range(63))
    for i, opt in ((52, '(a)'), (53, '(a)'), (54, '(b)')):
        assert pend[i]['ratified_2026-11-21'].startswith(f'RATIFIED {opt} by the author on 2026-11-21'), i
        assert pend[i]['status'] == 'OPEN 2026-11-20'              # the text of 20/11 is kept as written; the ratification is a separate key
    for i, q in ((55, 'Q-44'), (56, 'Q-45')):
        d = pend[i]
        assert d['status'] == 'OPEN 2026-11-21' and d['author_question'] == q and len(d['options']) == 2 and d['does_not_block'] == 'the full-design runs of check 47'
    assert pend[55]['recommendation'].startswith('(a)') and pend[56]['recommendation'].startswith('none') and 'Table 42' in pend[55]['topic']
    oq = r.OPEN_AUTHOR_QUESTIONS_2026_11_21
    assert [oq[k]['decision'] for k in ('Q-44', 'Q-45')] == [55, 56] and oq['answered_2026-11-21'] == {'Q-41': '(a)', 'Q-42': '(a)', 'Q-43': '(b)'}
    assert oq['still_open'] == a['still_open'] and r.OPEN_AUTHOR_QUESTIONS_2026_11_20B['still_open'][-3:] == ['Q-41', 'Q-42', 'Q-43']   # history kept
    c = r.POST_MATERIALIZE_CHECKS
    assert [x['id'] for x in c] == list(range(49)) and all('status_2026-11-21' in c[i] for i in (39, 45, 46, 47))
    assert c[45]['status_2026-11-21'].startswith('PASSED 2026-11-21') and '6,528 of 6,528' in c[45]['status_2026-11-21'] and c[45]['status'].startswith('PARTIAL 2026-11-20')
    assert c[46]['status_2026-11-21'].startswith('PARTIAL 2026-11-21') and '1.75e-3' in c[46]['status_2026-11-21'] and len(c[46]['requests_2026-11-21']) == 5
    assert len(c[46]['packaging_2026-11-21']['gates_to_start_check_47']) == 3 and '5subgroups_r1' in c[46]['packaging_2026-11-21']['release_id'] and '36 of them LO' in c[46]['status_2026-11-21']
    assert c[47]['status_2026-11-21'].startswith('OPEN 2026-11-21') and c[47]['status'].startswith('NOT STARTED 2026-11-20')
    fz = c[47]['frozen_configurations']
    assert fz['metamodel_version'].startswith('0.3.0') and fz['release_id'] == 'CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r1' and len(fz['runs']) == 10
    assert [x['name'] for x in fz['runs']][:6] == ['full_main_cal_time', 'full_sens_v1', 'full_sens_energy', 'full_sens_conservative', 'full_obj_perf', 'full_obj_macrof1']
    assert all(len(x['mm_config_sha256']) == 64 for x in fz['runs']) and len({x['mm_config_sha256'] for x in fz['runs']}) == 10
    assert all('--design full' in x['flags'] for x in fz['runs']) and fz['runs'][6]['flags'].endswith('--training-subgroups all-only')
    st = r.GRID_POLICY['execution_status_2026-11-21']
    assert list(st) == ['decisions', 'base_tier', 'meta_phase_A', 'meta_phase_B', 'meta_phase_C', 'exploratory_run', 'package', 'numbers']
    assert 'has not opened any outcome table' in st['exploratory_run'] and 'metamodel 0.3.0' in st['package'] and 'check 45 PASSED' in st['meta_phase_A']
    assert r.GRID_POLICY['execution_status_2026-11-20b']['decisions'].startswith('six author decisions')   # history kept
    regs = r.all_registries()
    assert 'author_ratifications_2026_11_21' in regs and 'open_author_questions_2026_11_21' in regs and len(regs) == 37
    man = r.write_registries(str(tmp_path))
    assert man['registry_revision'] == 'registries_rev_2026-11-26b' and man['author_ratifications_2026_11_21'] == seeds.sha256_of(a) and len(man) == 38



def test_registries_rev_2026_11_23_phase_b_acceptance(tmp_path):
    r = registries
    cr = r.CODE_REFERENCE
    assert r.REGISTRY_REVISION == 'registries_rev_2026-11-26b' and cr['previous_reference_2026-11-24'].startswith('fc361b6 (checked 2026-11-21')      # on 23/11 there was no new commit; the reference moved on 24/11
    rv = cr['review_2026-11-23']
    assert rv['checked_on'] == '2026-11-23' and 'fc361b651208102796c6d4b80a9fd7170d2c1632' in rv['origin'] and len(rv['not_in_repository']) == 4 and len(rv['delivered_copies_read_by_the_writing_side']) == 3
    assert 'd19fb122b795' in rv['not_in_repository'][0] and 'b13e1b963092' in rv['not_in_repository'][0] and '27 units' in rv['not_in_repository'][0]
    a = r.AUTHOR_RATIFICATIONS_2026_11_21B
    assert a['date'] == '2026-11-21' and list(a['decisions']) == ['55', '56'] and all(v.startswith('RATIFIED (a)') for v in a['decisions'].values())
    assert '[Q-44]' in a['decisions']['55'] and 'DESCRIPTIVE' in a['decisions']['55'] and '[Q-45]' in a['decisions']['56'] and 'had not seen' in a['decisions']['56']
    assert a['still_open'] == ['Q-20', 'Q-21', 'Q-22', 'Q-23', 'Q-24', 'Q-26'] and 'sealed' in a['other_instructions']['exploratory_run'] and len(a['consequences']) == 4
    assert r.AUTHOR_RATIFICATIONS_2026_11_21['still_open'][-2:] == ['Q-44', 'Q-45']                     # the block of the first pass is kept as written
    pend = r.PENDING_DECISIONS
    assert [d['id'] for d in pend] == list(range(63))
    for i, q in ((55, 'Q-44'), (56, 'Q-45')):
        assert pend[i]['status'] == 'OPEN 2026-11-21' and pend[i]['ratified_2026-11-21'].startswith('RATIFIED (a) by the author on 2026-11-21') and q in pend[i]['ratified_2026-11-21']
    oq = r.OPEN_AUTHOR_QUESTIONS_2026_11_23
    assert oq['answered_2026-11-21_second_pass'] == {'Q-44': '(a)', 'Q-45': '(a)'} and oq['restated_2026-11-23'] == {'Q-45': '(a)'} and oq['new_questions'] == 'none'
    assert oq['still_open'] == a['still_open'] and len(oq['for_the_author_2026-11-23']) == 2 and r.OPEN_AUTHOR_QUESTIONS_2026_11_21['still_open'][-2:] == ['Q-44', 'Q-45']
    c = r.POST_MATERIALIZE_CHECKS
    assert [x['id'] for x in c] == list(range(49))
    assert c[46]['status_2026-11-23'].startswith('PASSED 2026-11-23 on the data, items (a) to (e)') and 'item (f) stays OPEN' in c[46]['status_2026-11-23'] and c[46]['status_2026-11-21'].startswith('PARTIAL 2026-11-21')
    acc = c[46]['acceptance_2026-11-23']
    assert set(acc) == {'delivery', 'a_seen_flags', 'b_subgroup_facts', 'small_and_two_class_slices', 'report_only_differences', 'c_s0_profile_v5', 'c_notes', 'd_release', 'e_all_only_regression', 'e_r1_attempt',
                        'f_packaging', 'a8_a9_leftovers_of_check_45', 'drive', 'evidence'}
    assert '58,752 rows' in acc['b_subgroup_facts'] and '73,440 rows' in acc['d_release'] and '24,480 rows' in acc['d_release'] and '5subgroups_r2' in acc['d_release']
    assert '48 parquet tables, 0 different' in acc['e_all_only_regression'] and '6 of 6' in acc['e_all_only_regression'] and '154' in acc['e_r1_attempt'] and 'NOT committed' in acc['f_packaging']
    assert '(CQ 2, LO 36)' in acc['small_and_two_class_slices'] and '19 cells hold two classes' in acc['small_and_two_class_slices'] and '5,814' in acc['small_and_two_class_slices']
    rd = acc['report_only_differences']
    assert set(rd['largest_difference_by_metric']) == {'cross_entropy', 'log_loss', 'multiclass_brier', 'multiclass_nll', 'pr_auc_macro', 'top_label_ece_15'}
    assert 4e-3 < rd['largest_difference_by_metric']['multiclass_nll'] < 5e-3 and 4e-4 < rd['largest_difference_by_metric']['pr_auc_macro'] < 5e-4 and rd['largest_difference_by_metric']['log_loss'] < 1e-12
    assert len(c[46]['open_2026-11-23']) == 3 and len(acc['c_notes']) == 4 and '240 rows x 113 columns' in acc['c_s0_profile_v5']
    assert c[47]['status_2026-11-23'].startswith('OPEN 2026-11-23, ready to start') and c[47]['status_2026-11-21'].startswith('OPEN 2026-11-21')
    fz1, fz2 = c[47]['frozen_configurations'], c[47]['frozen_configurations_r2']
    assert fz1['release_id'].endswith('_5subgroups_r1') and fz2['release_id'] == 'CQ_LO_full_F1F2F3_seeds42_43_44_5subgroups_r2' and fz2['frozen_on'] == '2026-11-23' and fz2['metamodel_version'].startswith('0.3.0')
    assert [(x['name'], x['flags']) for x in fz1['runs']] == [(x['name'], x['flags']) for x in fz2['runs']] and fz1['common_options'] == fz2['common_options'] and len(fz2['runs']) == 10
    d1, d2 = {x['mm_config_sha256'] for x in fz1['runs']}, {x['mm_config_sha256'] for x in fz2['runs']}
    assert len(d2) == 10 and not (d1 & d2) and all(len(x) == 64 for x in d2) and '5subgroups_r2' in fz2['command']
    sm = c[47]['smoke_test_2026-11-23']
    assert set(sm) == {'what', 'structure', 'order', 'disclosure'} and 'not a registered configuration' in sm['what'] and 'before this run was started' in sm['order'] and 'No hypothesis table' in sm['disclosure']
    st = r.GRID_POLICY['execution_status_2026-11-23']
    assert list(st) == ['decisions', 'base_tier', 'meta_phase_A', 'meta_phase_B', 'meta_phase_C', 'exploratory_run', 'package', 'repository', 'numbers']
    assert st['meta_phase_B'] == c[46]['status_2026-11-23'] and 'not opened by the writing side' in st['exploratory_run'] and 'fc361b6' in st['repository']
    assert r.GRID_POLICY['execution_status_2026-11-21']['meta_phase_A'].startswith('check 45 PASSED') or 'check 45 PASSED' in r.GRID_POLICY['execution_status_2026-11-21']['meta_phase_A']   # history kept
    regs = r.all_registries()
    assert 'author_ratifications_2026_11_21b' in regs and 'open_author_questions_2026_11_23' in regs and len(regs) == 37
    man = r.write_registries(str(tmp_path))
    assert man['registry_revision'] == 'registries_rev_2026-11-26b' and man['author_ratifications_2026_11_21b'] == seeds.sha256_of(a) and len(man) == 38


def test_registries_rev_2026_11_24_phase_c_acceptance(tmp_path):
    r = registries
    cr = r.CODE_REFERENCE
    assert r.REGISTRY_REVISION == 'registries_rev_2026-11-26b' and cr['previous_reference'] == 'ecad59d (checked 2026-11-24)' and cr['review_2026-11-24']['checked_on'] == '2026-11-24'   # the reference moved to acd11c1 on 2026-11-26
    assert cr['previous_reference_2026-11-24'].startswith('fc361b6') and cr['previous_reference_2026-11-21'] == '6274591 (checked 2026-11-20)' and cr['review_2026-11-23']['checked_on'] == '2026-11-23'   # history kept
    rv = cr['review_2026-11-24']
    assert rv['checked_on'] == '2026-11-24' and len(cr['commits_reviewed_2026-11-24']) == 6 and cr['commits_reviewed_2026-11-24'][-1].startswith('ecad59d') and len(rv['notes']) == 7
    assert '249132bbd023' in rv['notes'][0] and 'e0da303 and e182a6f' in rv['notes'][0] and 'c3da76a6973f' in rv['notes'][0] and 'without regenerating a unit' in rv['notes'][1]
    assert len(cr['not_in_repository_2026-11-24']) == 3 and 'PHASE_C_ALL_COMPLETE' in cr['not_in_repository_2026-11-24'][0] and len(cr['resolved_since_2026-11-23']) == 4
    c = r.POST_MATERIALIZE_CHECKS
    assert [x['id'] for x in c] == list(range(49))
    assert c[46]['status_2026-11-24'].startswith('PASSED 2026-11-24, items (a) to (f)') and c[46]['status_2026-11-23'].startswith('PASSED 2026-11-23 on the data')
    cl = c[46]['closure_2026-11-24']
    assert set(cl) == {'f_code', 'two_tables_above_10_MB', 'builder_versions', 'evidence'} and '26409d4e9b55723e4ff042d8312397cc7b0be099888e573ed4a7aa8a3d763f0a' in cl['two_tables_above_10_MB']
    assert '57b56e1ab4dae42e5fdde3d66ee28c2b3a1f94a7aa346a5c3f7852e3717ef61e' in cl['two_tables_above_10_MB'] and '73,440 rows' in cl['two_tables_above_10_MB'] and '24,480 rows' in cl['two_tables_above_10_MB']
    assert len(c[46]['open_2026-11-24']) == 4
    assert c[47]['status_2026-11-24'].startswith('PASSED 2026-11-24, items (a) to (e)') and c[47]['status_2026-11-23'].startswith('OPEN 2026-11-23')
    acc = c[47]['acceptance_2026-11-24']
    assert list(acc) == ['delivery', 'a_frozen_configurations', 'b_inputs_and_package', 'c_variants', 'd_runs', 'e_rederivation', 'findings', 'results', 'evidence']
    assert '387 files' in acc['delivery'] and '184 files held' in acc['delivery'] and '(10 of 10)' in acc['a_frozen_configurations'] and '0.3.0 (2026-11-21)' in acc['b_inputs_and_package']
    assert '1,355 cells' in acc['e_rederivation'] and '0 different' in acc['e_rederivation'] and 'largest difference 0.0' in acc['e_rederivation']
    fz = c[47]['frozen_configurations_r2']
    fd = acc['findings']
    assert list(fd) == ['bootstrap_cluster_order', 'negative_control_MQ08', 'L6_skipped', 'V1_without_secondary_tables', 'fitted_models_not_written', 'conservative_oracle', 'driver']
    assert set(fd['bootstrap_cluster_order']) == {'what', 'verified', 'size', 'holm_p_crossing_0.05', 'record', 'status'} and 'pandas 3.1.0' in fd['bootstrap_cluster_order']['verified'] and 'pandas 3.0.5' in fd['bootstrap_cluster_order']['verified']
    mq = fd['negative_control_MQ08']['passes_by_configuration']
    assert list(mq) == [x['name'] for x in fz['runs']] and mq['full_main_cal_time'] == '5/12' and mq['var_task_pooled_main'] == '5/7' and len(fd['negative_control_MQ08']['main_configuration_rows']) == 12
    assert sum(v['pass'] for v in fd['negative_control_MQ08']['main_configuration_rows'].values()) == 5
    rs = acc['results']
    assert len(rs['main_configuration_primary_rows']) == 8 and rs['main_configuration_primary_rows'][0].startswith('H1 L3-FS3 - B3 (mean regret): +0.01354 [+0.00699; +0.02086]') and rs['main_configuration_primary_rows'][0].endswith('not supported')
    assert list(rs['H1_primary_by_configuration']) == [x['name'] for x in fz['runs']] and 'in 9 of 10' in rs['H1_primary_reading'] and rs['H6'].startswith('supported on the primary unit in the ten')
    assert set(rs['H1_other_rows_main']) == {'PER_TASK CQ', 'PER_TASK LO', 'REPLICATION_E1A (48 clusters)', 'POOLED_2FOLD (96 clusters)'} and '32 tests in the family, 9 rejected' in rs['holm_main']
    assert all('H1' not in v for v in rs['primary_rows_supported_by_configuration'].values()) and all('H6' in v for v in rs['primary_rows_supported_by_configuration'].values())
    assert '40 distinct vectors' in rs['state_points'] and 'not triggered' in rs['decision_48'] and rs['by_task_main_E1B']['LO']['L3-FS3'] > rs['by_task_main_E1B']['LO']['B3'] > rs['by_task_main_E1B']['LO']['B2']
    assert len(c[47]['open_2026-11-24']) == 4
    pend = r.PENDING_DECISIONS
    assert [d['id'] for d in pend] == list(range(63)) and pend[57]['author_question'] == 'Q-46' and pend[58]['author_question'] == 'Q-47' and all(pend[i]['status'] == 'OPEN 2026-11-24' for i in (57, 58))
    assert len(pend[57]['options']) == 3 and len(pend[58]['options']) == 2 and all('not a decision' in pend[i]['recommendation'] for i in (57, 58)) and 'ratified_2026-11-24' in pend[57]   # ratified (a) on 24/11, recorded on 26/11
    oq = r.OPEN_AUTHOR_QUESTIONS_2026_11_24
    assert oq['Q-46']['decision'] == 57 and oq['Q-47']['decision'] == 58 and oq['still_open'] == ['Q-20', 'Q-21', 'Q-22', 'Q-23', 'Q-24', 'Q-26', 'Q-46', 'Q-47'] and len(oq['for_the_author_2026-11-24']) == 4
    assert r.OPEN_AUTHOR_QUESTIONS_2026_11_23['still_open'] == ['Q-20', 'Q-21', 'Q-22', 'Q-23', 'Q-24', 'Q-26']                     # the block of 23/11 is kept as written
    st = r.GRID_POLICY['execution_status_2026-11-24']
    assert list(st) == ['decisions', 'base_tier', 'meta_phase_A', 'meta_phase_B', 'meta_phase_C', 'exploratory_run', 'package', 'repository', 'numbers']
    assert st['meta_phase_C'] == c[47]['status_2026-11-24'] and st['meta_phase_B'] == c[46]['status_2026-11-24'] and 'not opened by the writing side' in st['exploratory_run'] and 'ecad59d' in st['repository']
    assert 'fc361b6' in r.GRID_POLICY['execution_status_2026-11-23']['repository']                                                 # history kept
    regs = r.all_registries()
    assert 'open_author_questions_2026_11_24' in regs and len(regs) == 37
    man = r.write_registries(str(tmp_path))
    assert man['registry_revision'] == 'registries_rev_2026-11-26b' and man['open_author_questions_2026_11_24'] == seeds.sha256_of(oq) and len(man) == 38


def test_registries_rev_2026_11_26_author_answers_and_mq08_correction(tmp_path):
    r = registries
    cr = r.CODE_REFERENCE
    assert r.REGISTRY_REVISION == 'registries_rev_2026-11-26b' and cr['commit'] == 'acd11c1' and cr['checked_on'] == '2026-11-26' and cr['commit_full'] == 'acd11c1ec6671105675e33720cfbddf5dc3e7a14'
    assert cr['previous_reference'] == 'ecad59d (checked 2026-11-24)' and cr['previous_reference_2026-11-24'].startswith('fc361b6') and cr['review_2026-11-24']['checked_on'] == '2026-11-24'   # history kept
    rv = cr['review_2026-11-26']
    assert rv['checked_on'] == '2026-11-26' and len(rv['notes']) == 3 and 'PREFLIGHT PASS' in rv['notes'][0] and 'not byte-identical' in rv['notes'][1] and len(cr['commits_reviewed_2026-11-26']) == 1
    assert cr['commits_reviewed_2026-11-26'][0].startswith('acd11c1') and len(cr['resolved_since_2026-11-24']) == 1 and len(cr['not_in_repository_2026-11-26']) == 1
    assert len(cr['not_in_repository_2026-11-24']) == 3                                                                              # the list of 24/11 is kept as written
    c = r.POST_MATERIALIZE_CHECKS
    assert [x['id'] for x in c] == list(range(49))
    assert c[46]['status_2026-11-26'].startswith('CLOSED 2026-11-26') and c[46]['status_2026-11-24'].startswith('PASSED 2026-11-24, items (a) to (f)') and len(c[46]['closure_2026-11-26']['answers_of_the_team_not_reverified']) == 3
    assert c[47]['status_2026-11-26'].startswith('PASSED 2026-11-24, items (a) to (e), unchanged') and c[47]['status_2026-11-24'].startswith('PASSED 2026-11-24, items (a) to (e)')
    co = c[47]['correction_2026-11-26']
    assert list(co) == ['what', 'size', 'consequence', 'scope', 'main_configuration', 'reading_that_stands', 'verified_by_the_writing_side', 'not_verified', 'fix', 'evidence']
    assert 'to_numpy()' in co['what'] and '87 of 98 state columns' in co['size'] and '465 to 832 features instead of 99 to 110' in co['size'] and 'in 12 of 12 folds' in co['size']
    assert 'are withdrawn in that form' in co['consequence'] and '12 of 12 output tables identical' in co['scope'] and 'not quotable' in co['not_verified'] and '57 of 115 folds' in co['verified_by_the_writing_side']
    mc = co['main_configuration']
    assert mc['delivered_control_passes'] == '5/12' and mc['dtype_preserved_control_passes'] == '6/12' and len(mc['flags_changed']) == 3
    assert not mc['E1B']['CQ']['dtype_preserved_pass'] and not mc['E1B']['LO']['dtype_preserved_pass'] and mc['E1B']['LO']['model'] == '0.047145' and mc['E1B']['LO']['dtype_preserved_control'] == '0.015093'
    fd = c[47]['acceptance_2026-11-24']['findings']['negative_control_MQ08']
    assert fd['passes_by_configuration']['full_main_cal_time'] == '5/12'                                                             # the finding of 24/11 is kept as written; the correction stands next to it
    dv = c[47]['deviations_2026-11-26']
    assert list(dv) == ['cost_model_not_fitted', 'H7_row', 'release_description'] and 'decision 60 (Q-49)' in dv['cost_model_not_fitted'] and 'decision 61 (Q-50)' in dv['H7_row'] and '73,440 rows' in dv['release_description']
    assert len(c[47]['open_2026-11-26']) == 5 and len(c[47]['open_2026-11-24']) == 4
    pend = r.PENDING_DECISIONS
    assert [d['id'] for d in pend] == list(range(63)) and [pend[i]['author_question'] for i in (59, 60, 61)] == ['Q-48', 'Q-49', 'Q-50'] and all(pend[i]['status'] == 'OPEN 2026-11-26' for i in (59, 60, 61))
    assert pend[57]['ratified_2026-11-24'].startswith('RATIFIED (a)') and pend[58]['ratified_2026-11-24'].startswith('RATIFIED (a)') and 'superseded by decision 59' in pend[58]['premise_withdrawn_2026-11-26']
    assert all(len(pend[i]['options']) == 3 and 'not a decision' in pend[i]['recommendation'] and 'ratified_2026-11-26' in pend[i] for i in (59, 60, 61)) and pend[59]['supersedes'] == 'decision 58 (Q-47)'   # ratified on 26/11, second pass
    ar = r.AUTHOR_RATIFICATIONS_2026_11_26
    assert ar['date'] == '2026-11-26' and list(ar['decisions']) == ['57', '58'] and list(ar['answers_2026-11-26']) == [str(i) for i in range(1, 13)] and len(ar['instructions_2026-11-26']) == 4
    assert 'https://github.com/datachain-uit/CD3' in ar['answers_2026-11-26']['9'] and 'December 2026' in ar['answers_2026-11-26']['12'] and 'no AI tool is declared' in ar['instructions_2026-11-26'][0] and len(ar['not_decided']) == 4
    oq = r.OPEN_AUTHOR_QUESTIONS_2026_11_26
    assert [oq[q]['decision'] for q in ('Q-48', 'Q-49', 'Q-50')] == [59, 60, 61] and oq['still_open'] == ['Q-20', 'Q-22', 'Q-23', 'Q-24', 'Q-48', 'Q-49', 'Q-50'] and len(oq['for_the_author_2026-11-26']) == 4
    assert r.OPEN_AUTHOR_QUESTIONS_2026_11_24['still_open'] == ['Q-20', 'Q-21', 'Q-22', 'Q-23', 'Q-24', 'Q-26', 'Q-46', 'Q-47']         # the block of 24/11 is kept as written
    st = r.GRID_POLICY['execution_status_2026-11-26']
    assert list(st) == ['decisions', 'base_tier', 'meta_phase_A', 'meta_phase_B', 'meta_phase_C', 'exploratory_run', 'package', 'repository', 'manuscript', 'numbers']
    assert st['meta_phase_C'] == c[47]['status_2026-11-26'] and st['meta_phase_B'] == c[46]['status_2026-11-26'] and 'acd11c1' in st['repository'] and 'Method v0.5' in st['manuscript']
    assert 'ecad59d' in r.GRID_POLICY['execution_status_2026-11-24']['repository']                                                   # history kept
    regs = r.all_registries()
    assert 'open_author_questions_2026_11_26' in regs and 'author_ratifications_2026_11_26' in regs and len(regs) == 37
    man = r.write_registries(str(tmp_path))
    assert man['registry_revision'] == 'registries_rev_2026-11-26b' and man['open_author_questions_2026_11_26'] == seeds.sha256_of(oq) and man['author_ratifications_2026_11_26'] == seeds.sha256_of(ar) and len(man) == 38


def test_registries_rev_2026_11_26b_second_pass_decisions_and_check_48(tmp_path):
    r = registries
    assert r.REGISTRY_REVISION == 'registries_rev_2026-11-26b' and r.CODE_REFERENCE['commit'] == 'acd11c1'
    pub = r.CODE_REFERENCE['review_2026-11-26b']
    assert len(pub['public_release_state']) == 5 and 'no metamodel/ and no tempo_fix/ directory' in pub['public_release_state'][1] and 'no LICENSE' in pub['public_release_state'][2]
    assert r.CODE_REFERENCE['review_2026-11-26']['checked_on'] == '2026-11-26'                                                        # the review of the first pass is kept
    pend = r.PENDING_DECISIONS
    assert [d['id'] for d in pend] == list(range(63))
    assert pend[59]['ratified_2026-11-26'].startswith('RATIFIED (b)') and pend[60]['ratified_2026-11-26'].startswith('RATIFIED (a)') and pend[61]['ratified_2026-11-26'].startswith('RATIFIED (a)')
    assert all(pend[i]['status'] == 'OPEN 2026-11-26' and len(pend[i]['options']) == 3 for i in (59, 60, 61))                         # options and status of the first pass kept as written
    d62 = pend[62]
    assert d62['author_question'] == 'Q-51' and d62['status'] == 'OPEN 2026-11-26' and len(d62['options']) == 3 and 'not a decision' in d62['recommendation'] and not any(k.startswith('ratified') for k in d62)
    c = r.POST_MATERIALIZE_CHECKS
    assert [x['id'] for x in c] == list(range(49))
    fu = c[47]['followup_2026-11-26b']
    assert list(fu) == ['what', 'run_of_the_writing_side', 'control_alone', 'passes_by_configuration_delivered_to_dtype_preserved', 'by_protocol_dtype_preserved',
                        'verdict_unit_E1B_dtype_preserved_passes_by_configuration', 'main_configuration', 'agreement_with_the_team', 'five_permutations_main', 'bootstrap', 'tests',
                        'status_of_these_figures', 'post_hoc_H7_as_registered', 'post_hoc_cost_at_decision_time', 'evidence']
    assert '115 of 115 folds OK' in fu['control_alone'] and '57 of 115' in fu['control_alone'] and 'NOT the environment of record' in fu['run_of_the_writing_side']
    assert len(fu['passes_by_configuration_delivered_to_dtype_preserved']) == 10 and fu['passes_by_configuration_delivered_to_dtype_preserved']['full_main_cal_time'] == '5/12 -> 6/12'
    assert fu['main_configuration']['E1B_LO']['model'] == '0.047145' and not fu['main_configuration']['E1B_LO']['pass'] and not fu['main_configuration']['E1B_CQ']['pass']
    assert 'no value of the dtype-preserved control is printed' in fu['status_of_these_figures'] and 'PASS on the ten run directories' in fu['bootstrap']
    assert 'supported as registered: False' in fu['post_hoc_H7_as_registered']['primary_row'] and len(fu['post_hoc_H7_as_registered']['supported_by_role']) == 5
    assert 'criterion of H6 met: False' in fu['post_hoc_cost_at_decision_time']['primary_row'] and len(fu['post_hoc_cost_at_decision_time']['cost_change_by_role_decision_time']) == 5
    assert c[47]['status_2026-11-26'].startswith('PASSED 2026-11-24, items (a) to (e), unchanged') and 'correction_2026-11-26' in c[47]   # the first pass is kept as written
    c48 = c[48]
    assert c48['status'].startswith('PENDING 2026-11-26') and list(c48['criteria']) == list('abcdefgh') and '57 of 115' in c48['criteria']['c'] and 'decision 62' in c48['not_part_of_the_check']
    ar = r.AUTHOR_RATIFICATIONS_2026_11_26B
    assert ar['date'] == '2026-11-26' and ar['pass'] == 'second' and list(ar['decisions']) == ['59', '60', '61'] and list(ar['answers_2026-11-26_second_pass']) == [str(i) for i in range(1, 7)]
    assert 'approved' in ar['answers_2026-11-26_second_pass']['1'] and 'no pre-submission inquiry' in ar['answers_2026-11-26_second_pass']['5'] and len(ar['consequences']) == 4 and len(ar['not_decided']) == 2
    oq = r.OPEN_AUTHOR_QUESTIONS_2026_11_26B
    assert oq['Q-51']['decision'] == 62 and oq['still_open'] == ['Q-20', 'Q-22', 'Q-23', 'Q-24', 'Q-51'] and len(oq['for_the_author_2026-11-26b']) == 5
    assert r.OPEN_AUTHOR_QUESTIONS_2026_11_26['still_open'] == ['Q-20', 'Q-22', 'Q-23', 'Q-24', 'Q-48', 'Q-49', 'Q-50']                # the block of the first pass is kept as written
    assert list(r.AUTHOR_RATIFICATIONS_2026_11_26['decisions']) == ['57', '58']
    st = r.GRID_POLICY['execution_status_2026-11-26b']
    assert list(st) == ['decisions', 'base_tier', 'meta_phase_C', 'exploratory_run', 'package', 'post_hoc', 'repository', 'manuscript', 'numbers'] and 'check 48, PENDING' in st['meta_phase_C']
    assert 'Method v0.5.1' in st['manuscript'] and 'Method v0.5 (EN)' in r.GRID_POLICY['execution_status_2026-11-26']['manuscript']   # history kept
    regs = r.all_registries()
    assert 'open_author_questions_2026_11_26b' in regs and 'author_ratifications_2026_11_26b' in regs and len(regs) == 37
    man = r.write_registries(str(tmp_path))
    assert man['registry_revision'] == 'registries_rev_2026-11-26b' and man['open_author_questions_2026_11_26b'] == seeds.sha256_of(oq) and man['author_ratifications_2026_11_26b'] == seeds.sha256_of(ar) and len(man) == 38
