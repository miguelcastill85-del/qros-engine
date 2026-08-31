import numpy as np, sys, hashlib, json
from pathlib import Path
SRC=Path('/mnt/data/NQX_DEV_PACKED17_2018_2019_v1.bin')
OUT=Path('/mnt/data/g30_m30_indep3_parts');OUT.mkdir(exist_ok=True)
DT=np.dtype([('ts','<i8'),('bid','<i4'),('ask','<i4'),('flags','u1')])
NCH=16
mm=np.memmap(SRC,dtype=DT,mode='r')
k=int(sys.argv[1]); n=len(mm); a=n*k//NCH; b=n*(k+1)//NCH
arr=mm[a:b];ts=arr['ts'];bid=arr['bid'];ask=arr['ask']
ex=ask>bid
idx=np.flatnonzero(ex)
t=ts[idx]; bb=bid[idx].astype(np.int64); aa=ask[idx].astype(np.int64)
mb=(t//60000)*60000
st=np.r_[0,np.flatnonzero(mb[1:]!=mb[:-1])+1]; en=np.r_[st[1:],len(mb)]
bh=np.maximum.reduceat(bb,st); bl=np.minimum.reduceat(bb,st); ah=np.maximum.reduceat(aa,st); al=np.minimum.reduceat(aa,st)
first=(a+idx[st]).astype(np.int64); last=(a+idx[en-1]).astype(np.int64)
p=OUT/f'part_{k:02d}.npz';np.savez(p,mb=mb[st].astype(np.int64),bh=bh,bl=bl,ah=ah,al=al,first=first,last=last)
print(json.dumps({'k':k,'a':a,'b':b,'minutes':len(st),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}))
