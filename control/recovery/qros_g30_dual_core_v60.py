from __future__ import annotations
import numpy as np, hashlib, json, sys, time, math
from pathlib import Path
from numba import njit
DT=np.dtype([('ts','<i8'),('bid','<i4'),('ask','<i4'),('flags','u1')])
DAY=86_400_000
TFM={'M1':1,'M5':5,'M10':10,'M15':15,'M30':30,'H1':60}
def sha_bytes_triplets(et,xt,rr):
    h=hashlib.sha256()
    for a,b,r in zip(et,xt,rr):
        h.update(np.int64(a).tobytes()); h.update(np.int64(b).tobytes()); h.update(np.float64(r).tobytes())
    return h.hexdigest()

def atr_vec(h,l,c):
    h=h.astype(np.float64); l=l.astype(np.float64); c=c.astype(np.float64)
    pc=np.r_[np.nan,c[:-1]]
    tr=np.fmax(h-l,np.fmax(np.abs(h-pc),np.abs(l-pc)))
    cs=np.cumsum(np.nan_to_num(tr))
    out=np.full(len(c),np.nan)
    out[13:]=(cs[13:]-np.r_[0.0,cs[:-14]])/14.0
    return out

@njit(cache=True)
def atr_loop(h,l,c):
    n=len(c); out=np.full(n,np.nan); tr=np.empty(n,np.float64); roll=0.0
    for i in range(n):
        v=float(h[i]-l[i])
        if i>0:
            a=abs(float(h[i]-c[i-1])); b=abs(float(l[i]-c[i-1]))
            if a>v: v=a
            if b>v: v=b
        tr[i]=v; roll+=v
        if i>=14: roll-=tr[i-14]
        if i>=13: out[i]=roll/14.0
    return out

def pred_vec(close,high,low,fam,n,side):
    out=np.zeros(len(close),bool)
    cw=np.lib.stride_tricks.sliding_window_view(close,n+1)
    if fam=='CLOSE_EXCEEDS_PRIOR_N_CLOSES':
        vals=(cw[:,-1]>cw[:,:-1].max(1)) if side=='BUY' else (cw[:,-1]<cw[:,:-1].min(1))
    elif fam=='STRICT_MONOTONIC_N_CLOSE_SEQUENCE':
        d=np.diff(cw,axis=1); vals=np.all(d>0,1) if side=='BUY' else np.all(d<0,1)
    elif fam=='CLOSE_BREAKS_PRIOR_N_BAR_EXTREME':
        hw=np.lib.stride_tricks.sliding_window_view(high,n+1); lw=np.lib.stride_tricks.sliding_window_view(low,n+1)
        vals=(cw[:,-1]>hw[:,:-1].max(1)) if side=='BUY' else (cw[:,-1]<lw[:,:-1].min(1))
    else: raise ValueError(fam)
    out[n:]=vals; return out

@njit(cache=True)
def pred_loop(close,high,low,famcode,n,sidecode):
    out=np.zeros(len(close),np.bool_)
    for i in range(n,len(close)):
        if famcode==0:
            if sidecode==1:
                m=close[i-n]
                for j in range(i-n+1,i):
                    if close[j]>m: m=close[j]
                out[i]=close[i]>m
            else:
                m=close[i-n]
                for j in range(i-n+1,i):
                    if close[j]<m: m=close[j]
                out[i]=close[i]<m
        elif famcode==1:
            ok=True
            for j in range(i-n,i):
                if sidecode==1:
                    if close[j+1]<=close[j]: ok=False; break
                else:
                    if close[j+1]>=close[j]: ok=False; break
            out[i]=ok
        else:
            if sidecode==1:
                m=high[i-n]
                for j in range(i-n+1,i):
                    if high[j]>m: m=high[j]
                out[i]=close[i]>m
            else:
                m=low[i-n]
                for j in range(i-n+1,i):
                    if low[j]<m: m=low[j]
                out[i]=close[i]<m
    return out

@njit(cache=True)
def lower_bound(a,x):
    lo=0; hi=len(a)
    while lo<hi:
        mid=(lo+hi)//2
        if a[mid]<x: lo=mid+1
        else: hi=mid
    return lo

@njit(cache=True)
def outcomes_A(ts,bid,ask,bucket,atr,step,eb,ebh,ebl,eah,eal,first,last,side):
    n=len(bucket)
    eti=np.full(n,-1,np.int64); xti=np.full(n,-1,np.int64)
    et=np.full(n,-1,np.int64); xt=np.full(n,-1,np.int64)
    rr=np.zeros(n,np.float64); dist=np.zeros(n,np.float64); rr_actual=np.zeros(n,np.float64)
    hitkind=np.zeros(n,np.int8)
    for bi in range(n):
        if not np.isfinite(atr[bi]) or atr[bi]<=0: continue
        close_t=bucket[bi]+step; deadline=close_t+20*step; dayend=((close_t//DAY)+1)*DAY
        if deadline>dayend: deadline=dayend
        mi=lower_bound(eb,close_t)
        if mi>=len(eb) or eb[mi]>=deadline: continue
        ei=first[mi]
        while ei<=last[mi] and (ts[ei]<close_t or ask[ei]<=bid[ei]): ei+=1
        if ei>last[mi] or ts[ei]>=deadline: continue
        entry=ask[ei] if side==1 else bid[ei]
        d=3.0*atr[bi]/2.0; stop=entry-d if side==1 else entry+d; take=entry+1.5*d if side==1 else entry-1.5*d
        eti[bi]=ei; et[bi]=ts[ei]; dist[bi]=d
        mend=lower_bound(eb,deadline); hm=-1
        for mj in range(mi,mend):
            if side==1:
                if ebl[mj]<=stop or ebh[mj]>=take: hm=mj; break
            else:
                if eah[mj]>=stop or eal[mj]<=take: hm=mj; break
        resolved=False
        if hm>=0:
            j0=first[hm]
            if j0<ei: j0=ei
            for j in range(j0,last[hm]+1):
                if ts[j]>=deadline: break
                if ask[j]<=bid[j]: continue
                if side==1:
                    if bid[j]<=stop:
                        rr[bi]=-1.0; rr_actual[bi]=(bid[j]-entry)/d; hitkind[bi]=-1; xti[bi]=j; xt[bi]=ts[j]; resolved=True; break
                    if bid[j]>=take:
                        rr[bi]=1.5; rr_actual[bi]=(bid[j]-entry)/d; hitkind[bi]=1; xti[bi]=j; xt[bi]=ts[j]; resolved=True; break
                else:
                    if ask[j]>=stop:
                        rr[bi]=-1.0; rr_actual[bi]=(entry-ask[j])/d; hitkind[bi]=-1; xti[bi]=j; xt[bi]=ts[j]; resolved=True; break
                    if ask[j]<=take:
                        rr[bi]=1.5; rr_actual[bi]=(entry-ask[j])/d; hitkind[bi]=1; xti[bi]=j; xt[bi]=ts[j]; resolved=True; break
        if not resolved:
            if mend<=mi: eti[bi]=-1; et[bi]=-1; continue
            j=last[mend-1]
            while j>=first[mend-1] and (ts[j]>=deadline or ask[j]<=bid[j]): j-=1
            if j<ei: eti[bi]=-1; et[bi]=-1; continue
            xti[bi]=j; xt[bi]=ts[j]
            v=(bid[j]-entry)/d if side==1 else (entry-ask[j])/d
            rr[bi]=v; rr_actual[bi]=v
    return eti,xti,et,xt,rr,dist,rr_actual,hitkind

@njit(cache=True)
def outcomes_B(ts,bid,ask,bucket,atr,step,eb,ebh,ebl,eah,eal,first,last,side):
    # Independent control flow; same frozen V5 semantics.
    n=len(bucket)
    eti=np.full(n,-1,np.int64); xti=np.full(n,-1,np.int64); et=np.full(n,-1,np.int64); xt=np.full(n,-1,np.int64)
    rv=np.zeros(n,np.float64); ds=np.zeros(n,np.float64); actual=np.zeros(n,np.float64); hk=np.zeros(n,np.int8)
    for i in range(n):
        a=atr[i]
        if not np.isfinite(a) or a<=0.0: continue
        sc=bucket[i]+step
        de=((sc//DAY)+1)*DAY
        dl=sc+20*step
        if dl>de: dl=de
        k=lower_bound(eb,sc)
        if k==len(eb) or eb[k]>=dl: continue
        q=first[k]
        qend=last[k]
        while q<=qend:
            if ts[q]>=sc and ask[q]>bid[q]: break
            q+=1
        if q>qend or ts[q]>=dl: continue
        ep=ask[q] if side>0 else bid[q]
        d=1.5*a; ds[i]=d
        sl=ep-d if side>0 else ep+d; tp=ep+1.5*d if side>0 else ep-1.5*d
        eti[i]=q; et[i]=ts[q]
        kend=lower_bound(eb,dl)
        done=False
        for km in range(k,kend):
            possible=(ebl[km]<=sl or ebh[km]>=tp) if side>0 else (eah[km]>=sl or eal[km]<=tp)
            if not possible: continue
            q0=first[km]
            if q0<q: q0=q
            for j in range(q0,last[km]+1):
                if ts[j]>=dl: break
                if ask[j]<=bid[j]: continue
                if side>0:
                    px=bid[j]
                    if px<=sl:
                        rv[i]=-1.0; actual[i]=(px-ep)/d; hk[i]=-1; xti[i]=j; xt[i]=ts[j]; done=True; break
                    elif px>=tp:
                        rv[i]=1.5; actual[i]=(px-ep)/d; hk[i]=1; xti[i]=j; xt[i]=ts[j]; done=True; break
                else:
                    px=ask[j]
                    if px>=sl:
                        rv[i]=-1.0; actual[i]=(ep-px)/d; hk[i]=-1; xti[i]=j; xt[i]=ts[j]; done=True; break
                    elif px<=tp:
                        rv[i]=1.5; actual[i]=(ep-px)/d; hk[i]=1; xti[i]=j; xt[i]=ts[j]; done=True; break
            break
        if not done:
            if kend<=k:
                eti[i]=-1; et[i]=-1; continue
            j=last[kend-1]
            while j>=first[kend-1]:
                if ts[j]<dl and ask[j]>bid[j]: break
                j-=1
            if j<q:
                eti[i]=-1; et[i]=-1; continue
            xti[i]=j; xt[i]=ts[j]
            v=(bid[j]-ep)/d if side>0 else (ep-ask[j])/d
            rv[i]=v; actual[i]=v
    return eti,xti,et,xt,rv,ds,actual,hk

@njit(cache=True)
def select_mask(mask,et,xt):
    out=np.empty(len(mask),np.int64); k=0; prev=np.int64(-1)
    for i in range(len(mask)):
        if not mask[i]: continue
        if et[i]<0 or et[i]<=prev: continue
        out[k]=i; k+=1; prev=xt[i]
    return out[:k]

@njit(cache=True)
def count_target_bars(ts,bid,ask,step):
    n=0; last=np.int64(-9223372036854775807)
    for i in range(len(ts)):
        if ask[i]<bid[i]: continue
        b=(ts[i]//step)*step
        if b!=last: n+=1; last=b
    return n

@njit(cache=True)
def build_target_bars_direct(ts,bid,ask,step,mid):
    n=count_target_bars(ts,bid,ask,step)
    bu=np.empty(n,np.int64); op=np.empty(n,np.int64); hi=np.empty(n,np.int64); lo=np.empty(n,np.int64); cl=np.empty(n,np.int64)
    k=-1; last=np.int64(-9223372036854775807)
    for i in range(len(ts)):
        if ask[i]<bid[i]: continue
        b=(ts[i]//step)*step; x=(np.int64(bid[i])+np.int64(ask[i])) if mid else 2*np.int64(bid[i])
        if b!=last:
            k+=1; last=b; bu[k]=b; op[k]=x; hi[k]=x; lo[k]=x; cl[k]=x
        else:
            if x>hi[k]: hi[k]=x
            if x<lo[k]: lo[k]=x
            cl[k]=x
    return bu,op,hi,lo,cl

def aggregate_from_m1(z,tf,side):
    step=TFM[tf]*60_000
    mb=z['mb']; p='b' if side=='BID' else 'm'
    o=z[p+'o']; h=z[p+'h']; l=z[p+'l']; c=z[p+'c']
    if step==60_000: return mb,o,h,l,c
    b=(mb//step)*step; starts=np.r_[0,np.flatnonzero(b[1:]!=b[:-1])+1]; ends=np.r_[starts[1:],len(b)]
    return b[starts],o[starts],np.maximum.reduceat(h,starts),np.minimum.reduceat(l,starts),c[ends-1]

def signal_mask_A(bucket,o,h,l,c,timing,thr,fam,n,side):
    atr=atr_vec(h,l,c); denom=atr if timing=='CURRENT_BAR_INCLUDED' else np.r_[np.nan,atr[:-1]]
    ratio=np.divide(h-l,denom,out=np.full(len(c),np.nan),where=np.isfinite(denom)&(denom>0))
    weekday=((bucket//DAY+3)%7)<5
    return atr,(ratio>=thr)&weekday&pred_vec(c,h,l,fam,n,side)

def signal_mask_B(bucket,o,h,l,c,timing,thr,fam,n,side):
    atr=atr_loop(h,l,c); denom=np.empty(len(atr),np.float64)
    if timing=='CURRENT_BAR_INCLUDED': denom[:]=atr
    else:
        denom[0]=np.nan; denom[1:]=atr[:-1]
    shock=np.zeros(len(c),bool)
    for i in range(len(c)):
        d=denom[i]
        if np.isfinite(d) and d>0 and ((bucket[i]//DAY+3)%7)<5 and (h[i]-l[i])/d>=thr: shock[i]=True
    fmap={'CLOSE_EXCEEDS_PRIOR_N_CLOSES':0,'STRICT_MONOTONIC_N_CLOSE_SEQUENCE':1,'CLOSE_BREAKS_PRIOR_N_BAR_EXTREME':2}
    pred=pred_loop(c,h,l,fmap[fam],n,1 if side=='BUY' else -1)
    return atr,shock&pred
