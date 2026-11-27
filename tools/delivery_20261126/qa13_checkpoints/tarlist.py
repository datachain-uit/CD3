import sys, tarfile, subprocess, hashlib, time, json
ROOT='1GWiedVROrxp8jvGbd0xmvVmWriZUkpOn'
def scan(remote):
    """stream one archive; return list of (name,size,sha256 or None) for every non-parquet member (sha256 for members < 64 MB that look like checkpoints/adapters)"""
    p = subprocess.Popen(['rclone','--drive-root-folder-id',ROOT,'cat',f'gdrive:{remote}'], stdout=subprocess.PIPE, bufsize=1<<20)
    out=[]; n=0
    try:
        with tarfile.open(fileobj=p.stdout, mode='r|*') as a:
            for m in a:
                n+=1
                if not m.isfile(): continue
                b=m.name.rsplit('/',1)[-1]
                if b.endswith('.parquet') and '/predictions/' in m.name:
                    out.append((m.name,m.size,None)); continue
                h=None
                if m.size<(1<<27) and (b.endswith(('.pt','.pth','.ckpt','.safetensors','.npz','.npy','.bin')) or b.startswith('checkpoint') or b.endswith(('.json',))):
                    h=hashlib.sha256(a.extractfile(m).read()).hexdigest()
                out.append((m.name,m.size,h))
    except (tarfile.ReadError, EOFError) as e:      # truncated or interrupted stream: keep the members read so far and mark it
        out.append(('__STREAM_ENDED_EARLY__: ' + str(e), 0, None))
    finally:
        while p.stdout.read(1<<22): pass
        p.wait()
    return out
if __name__=='__main__':
    t=time.time(); r=scan(sys.argv[1]); print(time.time()-t,'s')
    for x in r: print(x)
