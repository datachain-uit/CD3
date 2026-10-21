"""Compare downloaded ablation files against SHA-256 hashes on the Vast host."""
import hashlib
import subprocess
from pathlib import Path

root = Path('LO/resuilt/lo_static_ablation_20261019')
cmd = ['ssh', '-o', 'BatchMode=yes', '-p', '40014', 'root@162.210.22.189',
       'cd /workspace/CD3/runs/lo_static_ablation && find . -type f -print0 | sort -z | xargs -0 sha256sum']
result = subprocess.run(cmd, check=True, text=True, stdout=subprocess.PIPE)
count = 0
for line in result.stdout.splitlines():
    expected, name = line.split('  ', 1)
    path = root / name.removeprefix('./')
    digest = hashlib.sha256()
    with path.open('rb') as file:
        for block in iter(lambda: file.read(4 * 1024 * 1024), b''):
            digest.update(block)
    if digest.hexdigest() != expected:
        raise ValueError(f'Hash mismatch: {path}')
    count += 1
print(f'verified_files={count}')
