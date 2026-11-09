"""Read-only approximate folder sizes; skip reparse points and inaccessible files."""
import os,sys,concurrent.futures
from pathlib import Path
targets=[Path(os.path.expandvars(x)) for x in (r'%LOCALAPPDATA%\Google',r'%LOCALAPPDATA%\Temp',r'%LOCALAPPDATA%\Packages',r'%LOCALAPPDATA%\Docker',r'%LOCALAPPDATA%\Programs',r'%LOCALAPPDATA%\Microsoft',r'%LOCALAPPDATA%\pip',r'%LOCALAPPDATA%\uv',r'%LOCALAPPDATA%\npm-cache',r'%LOCALAPPDATA%\pnpm',r'%USERPROFILE%\.cache',r'%USERPROFILE%\.codex',r'%USERPROFILE%\Downloads',r'%USERPROFILE%\AppData\Roaming',r'C:\Windows\Temp',r'C:\ProgramData\Docker')]
if len(sys.argv)>1:
    targets=[]
    for root in map(Path,sys.argv[1:]):
        try: targets.extend(x for x in root.iterdir() if x.is_dir() and not x.is_symlink())
        except OSError as e: print(f'{root}: {e}',flush=True)
def scan(path):
    size=0; files=0; errors=0; stack=[str(path)]; top=[]
    while stack:
        cur=stack.pop()
        try:
            with os.scandir(cur) as entries:
                for e in entries:
                    try:
                        st=e.stat(follow_symlinks=False)
                        if getattr(st,'st_file_attributes',0)&1024: continue
                        if e.is_dir(follow_symlinks=False): stack.append(e.path)
                        elif e.is_file(follow_symlinks=False):
                            size+=st.st_size; files+=1
                            if st.st_size>512*1024*1024: top.append((st.st_size,e.path))
                    except OSError: errors+=1
        except OSError: errors+=1
    return str(path),size,files,errors,sorted(top,reverse=True)[:8]
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
    for x in concurrent.futures.as_completed([pool.submit(scan,p) for p in targets]):
        p,n,c,e,b=x.result(); print(f'{n/2**30:8.2f} GiB files={c} errors={e} {p}',flush=True)
        for v,f in b: print(f'    {v/2**30:.2f} GiB {f}',flush=True)
