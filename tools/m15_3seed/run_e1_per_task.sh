#!/bin/bash
# E1-A and E1-B per task (the meta file is filtered to one task, so every fold is single-task); six configurations; one thread per process
cd ${TEMPO_WORK_ROOT:-.}/m15_3seed
export PATH="${TEMPO_VENV_BIN:-$HOME/venv/Scripts}:$PATH" PYTHONNOUSERSITE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 LOKY_MAX_CPU_COUNT=1
OUT=mm_runs_e1_per_task; RID=CQ_LO_full_F1F2F3_seeds42_43_44_20261120_E1_PER_TASK; mkdir -p $OUT
runone() { t=$1; name=$2; shift 2; s=$(date +%s); echo "START $OUT/${name}_$t $(date -Is)" >> $OUT/progress.log
  python m15_run_logged.py run --meta e1_per_task/meta_seed_agg_$t.parquet --out $OUT/${name}_$t --release-id $RID --protocols E1-A E1-B --learners L1 L2 L3 L4 --extra-learners L5 L6 --n-trials 50 --learner-seeds 5 "$@" > $OUT/${name}_$t.stdout.log 2> $OUT/${name}_$t.stderr.log
  echo "END $OUT/${name}_$t rc=$? seconds=$(( $(date +%s) - s ))" >> $OUT/progress.log; }
for t in CQ LO; do
  runone $t main_cal_time &
  runone $t obj_macrof1 --objective SECONDARY_MACRO_F1 &
  runone $t sens_v1 --objective META_PRIMARY_M3_V1 &
  runone $t sens_energy --accept-energy-estimates &
  runone $t sens_conservative --conservative &
  runone $t obj_perf --objective PAPER_PERF_AXIS &
  wait
done
echo "E1_PER_TASK_DONE $(date -Is)" >> $OUT/progress.log
