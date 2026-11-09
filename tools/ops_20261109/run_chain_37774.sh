#!/bin/bash
# 37774: after LO V16 (training + audit + bundle) finishes, run Mantis V16 W1 using the LO CUDA13 environment
cd /workspace/CD3
S=/workspace/CD3/runs/lo_patch_V16_newhost_20261108
export LD_LIBRARY_PATH="$S/cuda13/usr/local/cuda-13.0/compat${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export ENVROOT=/workspace/CD3/.venv-cq
bash chain_after_lo.sh V16 V13 W1 /workspace/CD3/up_par13 /workspace/CD3/par13_cache 12582912
