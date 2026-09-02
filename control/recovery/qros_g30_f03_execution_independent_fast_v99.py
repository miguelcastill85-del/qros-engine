from __future__ import annotations
import numpy as np
from numba import njit
STOP_ATR_MULT=3.0
ATR_STORAGE_DIVISOR=2.0
TAKE_R_MULT=1.5
TIME_STOP_BARS=20
EXEC_STEP=60000
_CACHE={}

@njit(cache=True)
def lower(a,x):
    lo=0;hi=len(a)
    while lo<hi:
        m=lo+(hi-lo)//2
        if a[m]<x:lo=m+1
        else:hi=m
    return lo

@njit(cache=True)
def count_exec_minutes(ts,bid,ask):
    n=0;last=np.int64(-9223372036854775807)
    for i in range(len(ts)):
        if ask[i]<=bid[i]:continue
        m=(ts[i]//EXEC_STEP)*EXEC_STEP
        if m!=last:n+=1;last=m
    return n

@njit(cache=True)
def build_exec_minutes(ts,bid,ask,n):
    eb=np.empty(n,np.int64);ebh=np.empty(n,np.int64);ebl=np.empty(n,np.int64);eah=np.empty(n,np.int64);eal=np.empty(n,np.int64);first=np.empty(n,np.int64);last=np.empty(n,np.int64)
    k=-1;cur=np.int64(-9223372036854775807)
    for i in range(len(ts)):
        if ask[i]<=bid[i]:continue
        m=(ts[i]//EXEC_STEP)*EXEC_STEP;b=np.int64(bid[i]);a=np.int64(ask[i])
        if m!=cur:
            k+=1;cur=m;eb[k]=m;ebh[k]=b;ebl[k]=b;eah[k]=a;eal[k]=a;first[k]=i;last[k]=i
        else:
            if b>ebh[k]:ebh[k]=b
            if b<ebl[k]:ebl[k]=b
            if a>eah[k]:eah[k]=a
            if a<eal[k]:eal[k]=a
            last[k]=i
    return eb,ebh,ebl,eah,eal,first,last

@njit(cache=True)
def outcome_core(ts,bid,ask,bucket,atr,step,eb,ebh,ebl,eah,eal,first,last,active,side):
    n=len(bucket);et=np.full(n,-1,np.int64);xt=np.full(n,-1,np.int64);eiout=np.full(n,-1,np.int64);xiout=np.full(n,-1,np.int64);dist=np.zeros(n,np.float64);rr=np.zeros(n,np.float64)
    for bi in range(n):
        if not active[bi] or not np.isfinite(atr[bi]) or atr[bi]<=0:continue
        close=bucket[bi]+step;day=((close//86400000)+1)*86400000;deadline=close+TIME_STOP_BARS*step
        if deadline>day:deadline=day
        m=lower(eb,close)
        if m>=len(eb) or eb[m]>=deadline:continue
        j=first[m]
        while j<=last[m] and (ts[j]<close or ask[j]<=bid[j]):j+=1
        if j>last[m] or ts[j]>=deadline:continue
        ei=j;entry=ask[j] if side==1 else bid[j];d=STOP_ATR_MULT*atr[bi]/ATR_STORAGE_DIVISOR;stop=entry-d if side==1 else entry+d;take=entry+TAKE_R_MULT*d if side==1 else entry-TAKE_R_MULT*d
        et[bi]=ts[j];eiout[bi]=j;dist[bi]=d;mend=lower(eb,deadline);done=False
        mm=m
        while mm<mend:
            may=False
            if side==1:
                if ebl[mm]<=stop:may=True
                elif ebh[mm]>=take:may=True
            else:
                if eah[mm]>=stop:may=True
                elif eal[mm]<=take:may=True
            if may:
                q=first[mm]
                if q<ei:q=ei
                while q<=last[mm] and ts[q]<deadline:
                    if ask[q]>bid[q]:
                        if side==1:
                            if bid[q]<=stop:
                                xt[bi]=ts[q];xiout[bi]=q;rr[bi]=(bid[q]-entry)/d;done=True;break
                            if bid[q]>=take:
                                xt[bi]=ts[q];xiout[bi]=q;rr[bi]=(bid[q]-entry)/d;done=True;break
                        else:
                            if ask[q]>=stop:
                                xt[bi]=ts[q];xiout[bi]=q;rr[bi]=(entry-ask[q])/d;done=True;break
                            if ask[q]<=take:
                                xt[bi]=ts[q];xiout[bi]=q;rr[bi]=(entry-ask[q])/d;done=True;break
                    q+=1
                if done:break
            mm+=1
        if not done:
            if mend<=0:et[bi]=-1;eiout[bi]=-1;continue
            q=last[mend-1]
            while q>=ei and (ts[q]>=deadline or ask[q]<=bid[q]):q-=1
            if q<ei:et[bi]=-1;eiout[bi]=-1;continue
            xt[bi]=ts[q];xiout[bi]=q;rr[bi]=(bid[q]-entry)/d if side==1 else (entry-ask[q])/d
    return et,xt,eiout,xiout,dist,rr

def _index(ts,bid,ask):
    key=(int(ts.__array_interface__['data'][0]),int(bid.__array_interface__['data'][0]),int(ask.__array_interface__['data'][0]),len(ts))
    z=_CACHE.get(key)
    if z is None:
        n=count_exec_minutes(ts,bid,ask);z=build_exec_minutes(ts,bid,ask,n);_CACHE.clear();_CACHE[key]=z
    return z

def outcome(ts,bid,ask,bucket,atr14,step,active,side):
    return outcome_core(ts,bid,ask,bucket,atr14,step,*_index(ts,bid,ask),active,side)

def select(mask,et,xt):
    out=[];prev=-1
    for q in np.flatnonzero(mask):
        if int(et[q])<0 or int(et[q])<=prev:continue
        out.append(int(q));prev=int(xt[q])
    return np.asarray(out,np.int64)
