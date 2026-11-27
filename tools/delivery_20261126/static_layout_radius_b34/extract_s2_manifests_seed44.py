"""Stream the seed-44 S2 tars from the shared Drive (read-only) and keep only run_manifest.json members."""
import subprocess, tarfile, sys, os, hashlib
from pathlib import Path
OUT = Path(sys.argv[1])
ROOT = '--drive-root-folder-id=1GWiedVROrxp8jvGbd0xmvVmWriZUkpOn'
env = dict(os.environ, MSYS_NO_PATHCONV='1')
for task in ('CQ', 'LO'):
    for w in ('W1', 'W2', 'W3'):
        for p in ('V1', 'V5', 'V9', 'V13'):
            name = f'{task}_{w}_{p}.tar'
            done = OUT / f'{task}_{w}_{p}.done'
            if done.exists():
                continue
            pr = subprocess.Popen(['rclone', 'cat', f'gdrive:{task}/L1_runs/S2_augmentation/seed44_17429_20261114/{name}', ROOT],
                                  stdout=subprocess.PIPE, env=env)
            n = 0
            with tarfile.open(fileobj=pr.stdout, mode='r|') as tf:
                for m in tf:
                    if m.isfile() and m.name.endswith('run_manifest.json'):
                        raw = tf.extractfile(m).read()
                        (OUT / f'{task}_{w}_{p}__{n}.json').write_bytes(raw)
                        (OUT / f'{task}_{w}_{p}__{n}.path').write_text(m.name, encoding='utf-8')
                        n += 1
            pr.stdout.close(); pr.wait()
            done.write_text(str(n)); print(name, n, flush=True)
