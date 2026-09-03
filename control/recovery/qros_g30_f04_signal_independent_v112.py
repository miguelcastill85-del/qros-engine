from __future__ import annotations
import numpy as np
from numba import njit

SMOOTH=('WILDER_RMA_TR','EMA_TR')
TIM=('CURRENT_BAR_INCLUDED','LAGGED_ONE_BAR_PRE_SHOCK')
TH=(1.0,1.25,1.5,1.75,2.0,2.5,3.0,3.5,4.0)
NS=(1,2,3,4,5,8)
FAMS=('CURRENT_CLOSE_EXCEEDS_ALL_PRIOR_N_CLOSES','STRICT_MONOTONIC_N_CLOSE_SEQUENCE','CURRENT_CLOSE_BREAKS_PRIOR_N_BAR_EXTREME')
P=14

def rolling_sum_int(x,n):
    cs=np.cumsum(x,dtype=np.int64);out=np.empty(len(x)-n+1,np.int64);out[0]=cs[n-1]
    if len(out)>1:out[1:]=cs[n:]-cs[:-n]
    return out

def bars(mb,o,h,l,c,tf):
    step=tf*60000
    if tf==1:return tuple(np.asarray(x,dtype=np.int64).copy() for x in (mb,o,h,l,c))
    bb=[];oo=[];hh=[];ll=[];cc=[];cur=-1
    for i in range(len(mb)):
        q=int(mb[i]//step*step)
        if q!=cur:
            bb.append(q);oo.append(int(o[i]));hh.append(int(h[i]));ll.append(int(l[i]));cc.append(int(c[i]));cur=q
        else:
            if h[i]>hh[-1]:hh[-1]=int(h[i])
            if l[i]<ll[-1]:ll[-1]=int(l[i])
            cc[-1]=int(c[i])
    return tuple(np.asarray(x,np.int64) for x in (bb,oo,hh,ll,cc))

def _tr_int(h,l,c):
    H=h.astype(np.int64);L=l.astype(np.int64);C=c.astype(np.int64);prior=np.r_[C[0],C[:-1]]
    tr=np.maximum(H-L,np.maximum(np.abs(H-prior),np.abs(L-prior))).astype(np.int64)
    if len(tr):tr[0]=H[0]-L[0]
    return tr

def atr_sma(h,l,c,p=P):
    tr=_tr_int(h,l,c);out=np.full(len(tr),np.nan)
    if len(tr)>=p:out[p-1:]=rolling_sum_int(tr,p).astype(float)/float(p)
    return out

@njit(cache=True)
def _wilder_numba(tr,p):
    out=np.empty(len(tr),np.float64)
    for i in range(len(out)):out[i]=np.nan
    if len(tr)<p:return out
    s=0.0
    for i in range(p):s+=float(tr[i])
    prev=s/float(p);out[p-1]=prev
    for i in range(p,len(tr)):
        prev=((p-1)*prev+float(tr[i]))/float(p);out[i]=prev
    return out

@njit(cache=True)
def _ema_numba(tr,p):
    out=np.empty(len(tr),np.float64)
    for i in range(len(out)):out[i]=np.nan
    if len(tr)<p:return out
    s=0.0
    for i in range(p):s+=float(tr[i])
    prev=s/float(p);out[p-1]=prev
    alpha=2.0/float(p+1);beta=1.0-alpha
    for i in range(p,len(tr)):
        prev=alpha*float(tr[i])+beta*prev;out[i]=prev
    return out

def atr_wilder(h,l,c,p=P):return _wilder_numba(_tr_int(h,l,c),p)
def atr_ema(h,l,c,p=P):return _ema_numba(_tr_int(h,l,c),p)

def prepare(bucket,o,h,l,c):
    nbar=len(c);bases={};d=np.diff(c);pos=(d>0).astype(np.int8);neg=(d<0).astype(np.int8)
    for n in NS:
        pc=np.vstack([c[n-k:nbar-k] for k in range(1,n+1)])
        ph=np.vstack([h[n-k:nbar-k] for k in range(1,n+1)])
        pl=np.vstack([l[n-k:nbar-k] for k in range(1,n+1)])
        b=np.zeros(nbar,bool);s=np.zeros(nbar,bool);b[n:]=c[n:]>pc.max(0);s[n:]=c[n:]<pc.min(0);bases[(FAMS[0],n)]=(b,s)
        b=np.zeros(nbar,bool);s=np.zeros(nbar,bool);b[n:]=rolling_sum_int(pos,n)==n;s[n:]=rolling_sum_int(neg,n)==n;bases[(FAMS[1],n)]=(b,s)
        b=np.zeros(nbar,bool);s=np.zeros(nbar,bool);b[n:]=c[n:]>ph.max(0);s[n:]=c[n:]<pl.min(0);bases[(FAMS[2],n)]=(b,s)
    weekday=((bucket//86400000+3)%7)<5
    numer=(h-l).astype(float)
    atrs={'WILDER_RMA_TR':atr_wilder(h,l,c,P),'EMA_TR':atr_ema(h,l,c,P)};shocks={}
    for sm in SMOOTH:
        a=atrs[sm]
        for timing in TIM:
            den=a if timing==TIM[0] else np.r_[np.nan,a[:-1]]
            ratio=np.divide(numer,den,out=np.full(nbar,np.nan),where=np.isfinite(den)&(den>0))
            for t in TH:shocks[(sm,timing,t)]=(ratio>=t)&weekday
    return {'bases':bases,'shocks':shocks,'atrs':atrs}

def mask(prep,o,h,l,c,sm,timing,t,fam,n):
    shock=prep['shocks'][(sm,timing,t)]
    if fam=='SHOCK_BAR_BODY_DIRECTION_ONLY':return (c>o)&shock,(c<o)&shock
    b,s=prep['bases'][(fam,n)]
    return b&shock,s&shock
