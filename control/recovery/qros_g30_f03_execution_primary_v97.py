from __future__ import annotations
import numpy as np
from numba import njit
STOP_ATR_MULT=3.0
ATR_STORAGE_DIVISOR=2.0
TAKE_R_MULT=1.5
TIME_STOP_BARS=20
@njit
def lb(a,x):
    lo=0;hi=len(a)
    while lo<hi:
        m=(lo+hi)//2
        if a[m]<x:lo=m+1
        else:hi=m
    return lo
@njit
def outcome(ts,bid,ask,bucket,atr14,step,eb,ebh,ebl,eah,eal,first,last,active,side):
    n=len(bucket);et=np.full(n,-1,np.int64);xt=np.full(n,-1,np.int64);eiout=np.full(n,-1,np.int64);xiout=np.full(n,-1,np.int64);dist=np.zeros(n,np.float64);rr=np.zeros(n,np.float64)
    for bi in range(n):
        if not active[bi] or not np.isfinite(atr14[bi]) or atr14[bi]<=0:continue
        close=bucket[bi]+step;deadline=min(close+TIME_STOP_BARS*step,((close//86400000)+1)*86400000);mi=lb(eb,close)
        if mi>=len(eb) or eb[mi]>=deadline:continue
        ei=first[mi]
        while ei<=last[mi] and (ts[ei]<close or ask[ei]<=bid[ei]):ei+=1
        if ei>last[mi] or ts[ei]>=deadline:continue
        entry=ask[ei] if side==1 else bid[ei];d=STOP_ATR_MULT*atr14[bi]/ATR_STORAGE_DIVISOR;stop=entry-d if side==1 else entry+d;take=entry+TAKE_R_MULT*d if side==1 else entry-TAKE_R_MULT*d
        et[bi]=ts[ei];eiout[bi]=ei;dist[bi]=d;mend=lb(eb,deadline);hit=False
        for mj in range(mi,mend):
            possible=(ebl[mj]<=stop or ebh[mj]>=take) if side==1 else (eah[mj]>=stop or eal[mj]<=take)
            if not possible:continue
            j0=first[mj]
            if j0<ei:j0=ei
            for j in range(j0,last[mj]+1):
                if ts[j]>=deadline:break
                if ask[j]<=bid[j]:continue
                if side==1:
                    if bid[j]<=stop or bid[j]>=take:
                        xt[bi]=ts[j];xiout[bi]=j;rr[bi]=(bid[j]-entry)/d;hit=True;break
                else:
                    if ask[j]>=stop or ask[j]<=take:
                        xt[bi]=ts[j];xiout[bi]=j;rr[bi]=(entry-ask[j])/d;hit=True;break
            if hit:break
        if not hit:
            if mend<=mi:et[bi]=-1;eiout[bi]=-1;continue
            j=last[mend-1]
            while j>=0 and (ts[j]>=deadline or ask[j]<=bid[j]):j-=1
            if j<ei:et[bi]=-1;eiout[bi]=-1;continue
            xt[bi]=ts[j];xiout[bi]=j;rr[bi]=(bid[j]-entry)/d if side==1 else (entry-ask[j])/d
    return et,xt,eiout,xiout,dist,rr
@njit
def select(mask,et,xt):
    ids=np.flatnonzero(mask);out=np.empty(len(ids),np.int64);k=0;prev=-1
    for q in ids:
        if et[q]<0 or et[q]<=prev:continue
        out[k]=q;k+=1;prev=xt[q]
    return out[:k]
