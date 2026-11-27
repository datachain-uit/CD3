"""Stream the head of one seed-44 CQ recurrent tar from the shared Drive (read-only) and hash its first feature_layout.json members."""
import subprocess, tarfile, hashlib, os, sys, json
env = dict(os.environ, MSYS_NO_PATHCONV='1')
for path in sys.argv[1:]:
    pr = subprocess.Popen(['rclone', 'cat', 'gdrive:' + path, '--drive-root-folder-id=1GWiedVROrxp8jvGbd0xmvVmWriZUkpOn'], stdout=subprocess.PIPE, env=env)
    n = 0
    with tarfile.open(fileobj=pr.stdout, mode='r|') as tf:
        for m in tf:
            if m.name.endswith('feature_layout.json'):
                b = tf.extractfile(m).read(); d = json.loads(b)
                print(path.split('/')[-1], m.name.split('seed=')[0], 'sha256:' + hashlib.sha256(b).hexdigest(), len(d['static_columns']), ';'.join(d['static_columns']))
                n += 1
                if n >= 2: break
    pr.kill()
