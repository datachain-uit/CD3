#!/bin/bash
# all six M-15 configurations on the local PC, one process each, ONE thread each (env caps, metamodel code unmodified)
cd ${TEMPO_WORK_ROOT:-.}/m15_3seed
export PATH="${TEMPO_VENV_BIN:-$HOME/venv/Scripts}:$PATH" PYTHONNOUSERSITE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 LOKY_MAX_CPU_COUNT=1
REL=${TEMPO_REPO_ROOT:-.}/CQ/resuilt/meta_release_CQ_LO_full_F1F2F3_seeds42_43_44_20261119; OUT=mm_runs_local_1t; RID=CQ_LO_full_F1F2F3_seeds42_43_44_20261119
runone() { name=$1; shift; s=$(date +%s); echo "START $OUT/$name $(date -Is) python=$(python --version 2>&1)" >> $OUT/m15_progress.log
  python m15_run_logged.py run --meta $REL/meta_dataset_seed_agg.parquet --out $OUT/$name --release-id $RID --protocols E1-A E1-B E2 E3 --learners L1 L2 L3 L4 --extra-learners L5 L6 --n-trials 50 --learner-seeds 5 "$@" > $OUT/$name.stdout.log 2> $OUT/$name.stderr.log
  echo "END $OUT/$name rc=$? seconds=$(( $(date +%s) - s ))" >> $OUT/m15_progress.log; }
mkdir -p $OUT
runone main_cal_time &
runone obj_macrof1 --objective SECONDARY_MACRO_F1 &
runone sens_v1 --objective META_PRIMARY_M3_V1 &
runone sens_energy --accept-energy-estimates &
runone sens_conservative --conservative &
runone obj_perf --objective PAPER_PERF_AXIS &
wait
echo "M15_LOCAL_ALL_DONE $(date -Is)" >> $OUT/m15_progress.log
