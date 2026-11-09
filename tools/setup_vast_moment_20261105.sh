#!/usr/bin/env bash
set -Eeuo pipefail
cd /workspace/CD3
/venv/main/bin/python -m venv --system-site-packages /workspace/CD3/moment_venv_20261105
/workspace/CD3/moment_venv_20261105/bin/python -m pip install --no-cache-dir 'transformers==5.22.1' 'git+https://github.com/moment-timeseries-foundation-model/moment.git@38f7310ad594100747ca2a8357e9c7ca7d323e0e'
/workspace/CD3/moment_venv_20261105/bin/python -c 'import torch, momentfm, transformers; assert torch.cuda.is_available(); print(torch.__version__, torch.cuda.get_device_name(0), transformers.__version__)'
touch /workspace/CD3/moment_environment_ready_20261105
