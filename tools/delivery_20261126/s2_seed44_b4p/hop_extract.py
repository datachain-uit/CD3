"""Read run_manifest.json members of plain tars on the shared Drive through a local read-only rclone http server using HTTP range requests (headers and manifests only)."""
import http.client, json, os, sys, pandas as pd, urllib.parse
from concurrent.futures import ThreadPoolExecutor
OUT='<WORK_DIR>/raw'
PORT={'CQ':8741,'LO':8742}
plan=pd.read_csv('<WORK_DIR>/run_tar_plan.csv')
tars=sorted(plan.tar.unique())
idx={t:i for i,t in enumerate(tars)}
def rng(c,path,a,n):
    for k in range(5):
        try:
            c.request('GET',path,headers={'Range':f'bytes={a}-{a+n-1}'}); r=c.getresponse(); b=r.read()
            if r.status in (200,206): return b if r.status==206 else b[a:a+n]
        except Exception as e:
            c.close(); c.connect()
    raise RuntimeError('range failed')
def num(b):
    if b[0]&0x80: return int.from_bytes(bytes([b[0]&0x7f])+b[1:],'big')
    s=b.split(b'\0')[0].strip(); return int(s,8) if s else 0
def work(t):
    i=idx[t]; done=f'{OUT}/t{i:03d}.done'
    if os.path.exists(done) or t.endswith('.gz'): return
    task=t.split('/')[0]; rel=t.split('seed=44/',1)[1]
    path='/'+urllib.parse.quote(rel); c=http.client.HTTPConnection('127.0.0.1',PORT[task],timeout=120); c.connect()
    pos=0; n=0; names=[]; longname=None
    while True:
        h=rng(c,path,pos,512)
        if len(h)<512 or h.count(0)==512: break
        name=h[:100].split(b'\0')[0].decode('utf-8','replace'); pre=h[345:500].split(b'\0')[0].decode('utf-8','replace')
        if h[257:262]==b'ustar' and pre: name=pre+'/'+name
        size=num(h[124:136]); tf=chr(h[156]) if h[156] else '0'
        data=pos+512; nxt=data+((size+511)//512)*512
        if tf=='L': longname=rng(c,path,data,size).split(b'\0')[0].decode('utf-8','replace')
        elif tf=='x':
            for line in rng(c,path,data,size).split(b'\n'):
                if b' path=' in line: longname=line.split(b' path=',1)[1].decode('utf-8','replace')
        else:
            if longname: name=longname; longname=None
            if tf in ('0','\0') and name.endswith('run_manifest.json'):
                open(f'{OUT}/t{i:03d}__{n}.json','wb').write(rng(c,path,data,size)); names.append(name); n+=1
        pos=nxt
    json.dump({'tar':t,'members':names,'expected':None,'method':'range'},open(done,'w'))
    print(i,t.split('/')[-1],n,flush=True)
with ThreadPoolExecutor(4) as ex: list(ex.map(work,tars))
print('HOP DONE')
