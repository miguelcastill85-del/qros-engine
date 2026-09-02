from __future__ import annotations
import numpy as np
from numba import njit
STOP_ATR_MULT=3.0
ATR_STORAGE_DIVISOR=2.0
TAKE_R_MULT=1.5
TIME_STOP_BARS=20
@njit
def lower_bound(a,x):
    lo=0;hi=len(a)
    while lo<hi:
        m=(lo+hi)//2
        if a[m]<x:lo=m+1
        else:hi=m
    return lo
@njit
def outcome(ts,bid,ask,bucket,atr14,step,active,side):
    n=len(bucket);et=np.full(n,-1,np.int64);xt=np.full(n,-1,np.int64);eiout=np.full(n,-1,np.int64);xiout=np.full(n,-1,np.int64);dist=np.zeros(n,np.float64);rr=np.zeros(n,np.float64)
    for bi in range(n):
        if not active[bi] or not np.isfinite(atr14[bi]) or atr14[bi]<=0:continue
        close=bucket[bi]+step;deadline=close+TIME_STOP_BARS*step;day=((close//86400000)+1)*86400000
        if deadline>day:deadline=day
        j=lower_bound(ts,close)
        while j<len(ts) and ts[j]<deadline and ask[j]<=bid[j]:j+=1
        if j>=len(ts) or ts[j]>=deadline:continue
        ei=j;entry=ask[j] if side==1 else bid[j];d=STOP_ATR_MULT*atr14[bi]/ATR_STORAGE_DIVISOR;stop=entry-d if side==1 else entry+d;take=entry+TAKE_R_MULT*d if side==1 else entry-TAKE_R_MULT*d
        et[bi]=ts[j];eiout[bi]=j;dist[bi]=d;hit=False
        while j<len(ts) and ts[j]<deadline:
            if ask[j]>bid[j]:
                if side==1:
                    if bid[j]<=stop or bid[j]>=take:
                        xt[bi]=ts[j];xiout[bi]=j;rr[bi]=(bid[j]-entry)/d;hit=True;break
                else:
                    if ask[j]>=stop or ask[j]<=take:
                        xt[bi]=ts[j];xiout[bi]=j;rr[bi]=(entry-ask[j])/d;hit=True;break
            j+=1
        if not hit:
            k=lower_bound(ts,deadline)-1
            while k>=ei and ask[k]<=bid[k]:k-=1
            if k<ei:et[bi]=-1;eiout[bi]=-1;continue
            xt[bi]=ts[k];xiout[bi]=k;rr[bi]=(bid[k]-entry)/d if side==1 else (entry-ask[k])/d
    return et,xt,eiout,xiout,dist,rr

def select(mask,et,xt):
    out=[];prev=-1
    for q in np.flatnonzero(mask):
        if int(et[q])<0 or int(et[q])<=prev:continue
        out.append(int(q));prev=int(xt[q])
    return np.asarray(out,np.int64)
