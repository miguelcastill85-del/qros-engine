from __future__ import annotations
import numpy as np

SMOOTH=('WILDER_RMA_TR','EMA_TR')
TIM=('CURRENT_BAR_INCLUDED','LAGGED_ONE_BAR_PRE_SHOCK')
TH=(1.0,1.25,1.5,1.75,2.0,2.5,3.0,3.5,4.0)
NS=(1,2,3,4,5,8)
FAMS=('CURRENT_CLOSE_EXCEEDS_ALL_PRIOR_N_CLOSES','STRICT_MONOTONIC_N_CLOSE_SEQUENCE','CURRENT_CLOSE_BREAKS_PRIOR_N_BAR_EXTREME')
P=14

def bars(mb,o,h,l,c,tf):
    step=tf*60000
    b=(mb//step)*step
    st=np.r_[0,np.flatnonzero(b[1:]!=b[:-1])+1]
    en=np.r_[st[1:],len(b)]
    return b[st].astype(np.int64),o[st],np.maximum.reduceat(h,st),np.minimum.reduceat(l,st),c[en-1]

def true_range(h,l,c):
    H=h.astype(float);L=l.astype(float);C=c.astype(float)
    tr=np.empty(len(C),dtype=float)
    if len(C)==0:return tr
    tr[0]=H[0]-L[0]
    if len(C)>1:
        pc=C[:-1]
        tr[1:]=np.maximum(H[1:]-L[1:],np.maximum(np.abs(H[1:]-pc),np.abs(L[1:]-pc)))
    return tr

def atr_sma(h,l,c,p=P):
    tr=true_range(h,l,c)
    out=np.full(len(tr),np.nan)
    if len(tr)<p:return out
    cs=np.cumsum(tr,dtype=float)
    out[p-1:]=(cs[p-1:]-np.r_[0.0,cs[:-p]])/float(p)
    return out

def atr_wilder(h,l,c,p=P):
    tr=true_range(h,l,c);out=np.full(len(tr),np.nan)
    if len(tr)<p:return out
    seed=float(np.sum(tr[:p],dtype=float)/float(p));out[p-1]=seed
    prev=seed
    for i in range(p,len(tr)):
        prev=((p-1)*prev+tr[i])/float(p);out[i]=prev
    return out

def atr_ema(h,l,c,p=P):
    tr=true_range(h,l,c);out=np.full(len(tr),np.nan)
    if len(tr)<p:return out
    seed=float(np.sum(tr[:p],dtype=float)/float(p));out[p-1]=seed
    alpha=2.0/float(p+1);beta=1.0-alpha;prev=seed
    for i in range(p,len(tr)):
        prev=alpha*tr[i]+beta*prev;out[i]=prev
    return out

def prepare(bucket,o,h,l,c):
    nbar=len(c);bases={}
    for n in NS:
        cw=np.lib.stride_tricks.sliding_window_view(c,n+1)
        hw=np.lib.stride_tricks.sliding_window_view(h,n+1)
        lw=np.lib.stride_tricks.sliding_window_view(l,n+1)
        b=np.zeros(nbar,bool);s=np.zeros(nbar,bool);b[n:]=cw[:,-1]>cw[:,:-1].max(1);s[n:]=cw[:,-1]<cw[:,:-1].min(1);bases[(FAMS[0],n)]=(b,s)
        d=np.diff(cw,axis=1);b=np.zeros(nbar,bool);s=np.zeros(nbar,bool);b[n:]=np.all(d>0,1);s[n:]=np.all(d<0,1);bases[(FAMS[1],n)]=(b,s)
        b=np.zeros(nbar,bool);s=np.zeros(nbar,bool);b[n:]=cw[:,-1]>hw[:,:-1].max(1);s[n:]=cw[:,-1]<lw[:,:-1].min(1);bases[(FAMS[2],n)]=(b,s)
    weekday=((bucket//86400000+3)%7)<5
    numer=(h-l).astype(float)
    atrs={'WILDER_RMA_TR':atr_wilder(h,l,c,P),'EMA_TR':atr_ema(h,l,c,P)}
    shocks={}
    for sm,a in atrs.items():
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
