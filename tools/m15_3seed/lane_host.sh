#!/bin/bash
# M-15 on a rented host: three configurations in parallel, one process each (same command and flags as run_m15_vast.sh of 2026-11-13), 3-seed release
cd /workspace/m15_3seed
export PATH=/workspace/venv_mm/bin:$PATH OMP_NUM_THREADS=6 OPENBLAS_NUM_THREADS=6 PYTHONNOUSERSITE=1
REL=meta_release_CQ_LO_full_F1F2F3_seeds42_43_44_20261119; OUT=mm_runs_full3seed; RID=CQ_LO_full_F1F2F3_seeds42_43_44_20261119
mkdir -p $OUT
runone() { name=$1; shift; s=$(date +%s); echo "START $OUT/$name $(date -Is) python=$(python --version 2>&1)" >> $OUT/m15_progress.log
  python -m metamodel.cli run --meta $REL/meta_dataset_seed_agg.parquet --out $OUT/$name --release-id $RID --protocols E1-A E1-B E2 E3 --learners L1 L2 L3 L4 --extra-learners L5 L6 --n-trials 50 --learner-seeds 5 "$@" > $OUT/$name.stdout.log 2> $OUT/$name.stderr.log
  echo "END $OUT/$name rc=$? seconds=$(( $(date +%s) - s ))" >> $OUT/m15_progress.log; }
if [ "$1" = A ]; then
  runone main_cal_time &
  runone sens_v1 --objective META_PRIMARY_M3_V1 &
  runone sens_energy --accept-energy-estimates &
else
  runone obj_macrof1 --objective SECONDARY_MACRO_F1 &
  runone sens_conservative --conservative &
  runone obj_perf --objective PAPER_PERF_AXIS &
fi
wait
echo "M15_HOST_$1_ALL_DONE $(date -Is)" >> $OUT/m15_progress.log
