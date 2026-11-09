#!/bin/bash
set -Eeuo pipefail
BASE=/workspace/cuda13_probe
mkdir -p "$BASE"
cd "$BASE"
apt-get download cuda-compat-13-0
dpkg-deb -x cuda-compat-13-0*.deb extracted
uv venv --python 3.12 "$BASE/venv"
uv pip install --python "$BASE/venv/bin/python" torch==2.14.1
export LD_LIBRARY_PATH="$BASE/extracted/usr/local/cuda-13.0/compat${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
"$BASE/venv/bin/python" "$BASE/check.py"
