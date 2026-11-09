#!/bin/bash
# usage: split_driver.sh <V> <ENVROOT> [LD_DIR]
# Stop the sequential driver (NOT the running python), then package W1 once its python has finished.
V=$1; ENVR=$2; LDD=$3
cd /workspace/CD3
for p in $(ps -eo pid,args | grep "[b]ash lo_mantis_parent.sh $V" | awk '{print $1}'); do kill $p; done
sleep 1
cat > pkg_w1_$V.sh <<EOS
cd /workspace/CD3
while ps -eo args | grep -q "[r]un_mantis_grid_zstd_20261109.py --task LO --window W1 --pipeline $V"; do sleep 60; done
[ -n "$LDD" ] && export LD_LIBRARY_PATH="$LDD/usr/local/cuda-13.0/compat:\$LD_LIBRARY_PATH"
ENVROOT=$ENVR bash lo_mantis_parent.sh $V "W1" > mantis_lo_${V}_w1pkg.log 2> mantis_lo_${V}_w1pkg.err.log
EOS
nohup bash pkg_w1_$V.sh > /dev/null 2>&1 < /dev/null &
echo "driver stopped for $V; python still running: $(ps -eo args | grep -c "[r]un_mantis_grid_zstd_20261109.py --task LO --window W1 --pipeline $V")"
