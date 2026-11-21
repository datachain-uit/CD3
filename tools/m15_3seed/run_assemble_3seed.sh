#!/bin/bash
# 3-seed release (seeds 42, 43, 44): F1 + F2 + F3 for CQ and LO. Same inputs and keys as run_assemble_full.sh (full42), plus the seed-43 and seed-44 fact packages.
cd ${TEMPO_WORK_ROOT:-.}/m15_3seed
export PATH="${TEMPO_VENV_BIN:-$HOME/venv/Scripts}:$PATH" PYTHONNOUSERSITE=1
R=${TEMPO_REPO_ROOT:-.}; P=$R/CQ/resuilt; LP=$R/LO/resuilt; A=${TEMPO_AUDIT44_ROOT:-./audit44}/asm_inputs; F44=${TEMPO_AUDIT44_ROOT:-./audit44}/facts44
f1() { for fam in RNN LSTM GRU BILSTM; do echo "$1/$fam/$2"; done; }
T=$1
if [ "$T" = CQ ]; then
  FACTS="${TEMPO_WORK_ROOT:-.}/m14c/cq_r4_with_regime_macro.parquet $P/cq_patchtst_v0_v6_full_facts_20261103_r2/sanity_components.csv $P/cq_patchtst_v7_v16_full_facts_20261109_r2/sanity_components.csv $P/cq_mantis_v2_v0_v16_full_facts_20261109_r3/sanity_components.csv"
  RES="$R/upload_staging/m09/r4/cq_resource_per_run.parquet $P/cq_patchtst_v0_v6_full_facts_20261103_r2/resource_per_run.csv $P/cq_patchtst_v7_v16_full_facts_20261109_r2/resource_per_run.csv $P/cq_mantis_v2_v0_v16_full_facts_20261109_r3/resource_per_run.csv"
  for S in 43 44; do
    if [ $S = 43 ]; then B=$A/seed43/CQ; else B=$F44/CQ; fi
    if [ $S = 43 ]; then F1D=${B}_f1_recurrent; PTD=${B}_patchtst; MD=${B}_mantis_v2; else F1D=${B}_f1_recurrent_v0_v16_seed44; PTD=${B}_patchtst_v0_v16_seed44; MD=${B}_mantis_v2_v0_v16_seed44; fi
    FACTS="$FACTS $(f1 $F1D sanity_components.csv | tr '\n' ' ') $PTD/sanity_components.csv $MD/sanity_components.csv"
    RES="$RES $(f1 $F1D resource_per_run.csv | tr '\n' ' ') $PTD/resource_per_run.csv $MD/resource_per_run.csv"
  done
  python -m metamodel.cli assemble --facts $FACTS --resources $RES \
    --state $P/m13a_s0_profile_20261109_v4/s0_profile.parquet --model-context $P/m13b_z_m_delivery_20261109_v2/z_m.csv --f0 $P/f0_cq_partial_triad_20261108/f0_cq_partial_triad.csv \
    --key task=CQ --key label_rule_version=cq_vector_proximity_v1_zero_activity_policy --key label_threshold_set=CQ_VECTOR_PROXIMITY_PRIMARY_V1 --key feature_regime=CQ_RAW_EARLY \
    --registry tempo_fix/examples/registries_v1.6 --planned-seeds 42 43 44 --release-id CQ_V2_2_full_seeds42_43_44 --out meta_release/CQ_3seed --csv > assemble_CQ_3seed.log 2>&1
  echo CQ_RC=$? >> assemble_CQ_3seed.log
else
  L=$LP/lo_static_v2_grid_seed42_20261102
  FACTS="${TEMPO_WORK_ROOT:-.}/m14c/lo_static_v2_facts_no_confusion.parquet $LP/lo_patchtst_v0_v16_full_facts_20261109_r2/sanity_components.csv $LP/lo_mantis_v2_v0_v16_full_facts_20261110/sanity_components.csv"
  RES="$L/lo_resource_per_run.parquet $LP/lo_patchtst_v0_v16_full_facts_20261109_r2/resource_per_run.csv $LP/lo_mantis_v2_v0_v16_full_facts_20261110/resource_per_run.csv"
  for S in 43 44; do
    if [ $S = 43 ]; then B=$A/seed43/LO; F1D=${B}_f1_recurrent; PTD=${B}_patchtst; MD=${B}_mantis_v2; else B=$F44/LO; F1D=${B}_f1_recurrent_v0_v16_seed44; PTD=${B}_patchtst_v0_v16_seed44; MD=${B}_mantis_v2_v0_v16_seed44; fi
    FACTS="$FACTS $(f1 $F1D sanity_components.csv | tr '\n' ' ') $PTD/sanity_components.csv $MD/sanity_components.csv"
    RES="$RES $(f1 $F1D resource_per_run.csv | tr '\n' ' ') $PTD/resource_per_run.csv $MD/resource_per_run.csv"
  done
  python -m metamodel.cli assemble --facts $FACTS --resources $RES \
    --state $P/m13a_s0_profile_20261109_v4/s0_profile.parquet --model-context $P/m13b_z_m_delivery_20261109_v2/z_m.csv \
    --key task=LO --key label_rule_version=lo_final_score_catalog_normalized_v3_1 --key label_threshold_set=CATALOG_NORMALIZED_PRIMARY_V3_1__EXCLUDE_NO_SCORED_SIGNAL \
    --registry tempo_fix/examples/registries_v1.6 --planned-seeds 42 43 44 --release-id LO_V3_1_full_seeds42_43_44 --out meta_release/LO_3seed --csv > assemble_LO_3seed.log 2>&1
  echo LO_RC=$? >> assemble_LO_3seed.log
fi
