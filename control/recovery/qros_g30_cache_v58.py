import numpy as np, hashlib, json, sys, time
from pathlib import Path
from numba import njit
DT=np.dtype([('ts','<i8'),('bid','<i4'),('ask','<i4'),('flags','u1')])
STEP=60000
@njit(cache=True)
def counts(ts,bid,ask):
    nf=0; ne=0
    lf=np.int64(-9223372036854775807); le=lf
    for i in range(len(ts)):
        m=(ts[i]//STEP)*STEP
        if ask[i]>=bid[i] and m!=lf:
            nf+=1; lf=m
        if ask[i]>bid[i] and m!=le:
            ne+=1; le=m
    return nf,ne
@njit(cache=True)
def build(ts,bid,ask,nf,ne):
    mb=np.empty(nf,np.int64)
    bo=np.empty(nf,np.int64); bh=np.empty(nf,np.int64); bl=np.empty(nf,np.int64); bc=np.empty(nf,np.int64)
    mo=np.empty(nf,np.int64); mh=np.empty(nf,np.int64); ml=np.empty(nf,np.int64); mc=np.empty(nf,np.int64)
    eb=np.empty(ne,np.int64); ebh=np.empty(ne,np.int64); ebl=np.empty(ne,np.int64); eah=np.empty(ne,np.int64); eal=np.empty(ne,np.int64); first=np.empty(ne,np.int64); last=np.empty(ne,np.int64)
    fi=-1; ei=-1; lf=np.int64(-9223372036854775807); le=lf
    for i in range(len(ts)):
        m=(ts[i]//STEP)*STEP; b=np.int64(bid[i]); a=np.int64(ask[i])
        if a>=b:
            xb=2*b; xm=b+a
            if m!=lf:
                fi+=1; lf=m; mb[fi]=m
                bo[fi]=xb; bh[fi]=xb; bl[fi]=xb; bc[fi]=xb
                mo[fi]=xm; mh[fi]=xm; ml[fi]=xm; mc[fi]=xm
            else:
                if xb>bh[fi]: bh[fi]=xb
                if xb<bl[fi]: bl[fi]=xb
                bc[fi]=xb
                if xm>mh[fi]: mh[fi]=xm
                if xm<ml[fi]: ml[fi]=xm
                mc[fi]=xm
        if a>b:
            if m!=le:
                ei+=1; le=m; eb[ei]=m; ebh[ei]=b; ebl[ei]=b; eah[ei]=a; eal[ei]=a; first[ei]=i; last[ei]=i
            else:
                if b>ebh[ei]: ebh[ei]=b
                if b<ebl[ei]: ebl[ei]=b
                if a>eah[ei]: eah[ei]=a
                if a<eal[ei]: eal[ei]=a
                last[ei]=i
    return mb,bo,bh,bl,bc,mo,mh,ml,mc,eb,ebh,ebl,eah,eal,first,last

def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        while True:
            b=f.read(8<<20)
            if not b: break
            h.update(b)
    return h.hexdigest()

def main(src,out):
    t=time.time(); mm=np.memmap(src,dtype=DT,mode='r')
    nf,ne=counts(mm['ts'],mm['bid'],mm['ask']); print('counts',nf,ne,'sec',time.time()-t,flush=True)
    arr=build(mm['ts'],mm['bid'],mm['ask'],nf,ne); print('built sec',time.time()-t,flush=True)
    keys=['mb','bo','bh','bl','bc','mo','mh','ml','mc','eb','ebh','ebl','eah','eal','first','last']
    np.savez(out,**dict(zip(keys,arr)))
    print(json.dumps({'src':str(src),'records':len(mm),'m1_feature_minutes':int(nf),'exec_minutes':int(ne),'out':str(out),'sha256':sha(out),'seconds':time.time()-t},sort_keys=True))
if __name__=='__main__': main(Path(sys.argv[1]),Path(sys.argv[2]))
