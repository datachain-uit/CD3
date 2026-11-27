import hashlib,glob,os,json
out={}
for f in sorted(glob.glob('<S2_CHILDREN_DIR>/*/*/*/balanced_train.parquet')):
    p=f.replace(chr(92),'/').split('/'); t,w,v=p[-4],p[-3],p[-2]
    h=hashlib.sha256(); m=hashlib.md5()
    with open(f,'rb') as fh:
        for b in iter(lambda:fh.read(1<<24),b''): h.update(b); m.update(b)
    out[f'{t}|{w}|{v}']=(h.hexdigest(),m.hexdigest(),os.path.getsize(f))
json.dump(out,open('<WORK_DIR>/local_s2_children_hash.json','w'),indent=0); print(len(out),sorted({k.split('|')[0] for k in out}))
