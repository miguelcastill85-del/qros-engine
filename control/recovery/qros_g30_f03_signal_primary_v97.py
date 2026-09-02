from __future__ import annotations
import numpy as np

PERIODS=(7,10,20,28,50)
TIM=('CURRENT_BAR_INCLUDED','LAGGED_ONE_BAR_PRE_SHOCK')
TH=(1.0,1.25,1.5,1.75,2.0,2.5,3.0,3.5,4.0)
NS=(1,2,3,4,5,8)
FAMS=('CURRENT_CLOSE_EXCEEDS_ALL_PRIOR_N_CLOSES','STRICT_MONOTONIC_N_CLOSE_SEQUENCE','CURRENT_CLOSE_BREAKS_PRIOR_N_BAR_EXTREME')

def bars(mb,o,h,l,c,tf):
    step=tf*60000
    b=(mb//step)*step
    st=np.r_[0,np.flatnonzero(b[1:]!=b[:-1])+1]
    en=np.r_[st[1:],len(b)]
    return b[st].astype(np.int64),o[st],np.maximum.reduceat(h,st),np.minimum.reduceat(l,st),c[en-1]

def atr(h,l,c,p):
    H=h.astype(float);L=l.astype(float);C=c.astype(float)
    pc=np.r_[np.nan,C[:-1]]
    tr=np.fmax(H-L,np.fmax(np.abs(H-pc),np.abs(L-pc)))
    cs=np.cumsum(np.nan_to_num(tr))
    out=np.full(len(C),np.nan)
    out[p-1:]=(cs[p-1:]-np.r_[0.0,cs[:-p]])/float(p)
    return out

def prepare(bucket,o,h,l,c):
    nbar=len(c); bases={}
    for n in NS:
        cw=np.lib.stride_tricks.sliding_window_view(c,n+1)
        hw=np.lib.stride_tricks.sliding_window_view(h,n+1)
        lw=np.lib.stride_tricks.sliding_window_view(l,n+1)
        b=np.zeros(nbar,bool);s=np.zeros(nbar,bool);b[n:]=cw[:,-1]>cw[:,:-1].max(1);s[n:]=cw[:,-1]<cw[:,:-1].min(1);bases[(FAMS[0],n)]=(b,s)
        d=np.diff(cw,axis=1);b=np.zeros(nbar,bool);s=np.zeros(nbar,bool);b[n:]=np.all(d>0,1);s[n:]=np.all(d<0,1);bases[(FAMS[1],n)]=(b,s)
        b=np.zeros(nbar,bool);s=np.zeros(nbar,bool);b[n:]=cw[:,-1]>hw[:,:-1].max(1);s[n:]=cw[:,-1]<lw[:,:-1].min(1);bases[(FAMS[2],n)]=(b,s)
    weekday=((bucket//86400000+3)%7)<5
    shocks={}; atrs={}
    numer=(h-l).astype(float)
    for p in PERIODS:
        a=atr(h,l,c,p);atrs[p]=a
        for timing in TIM:
            den=a if timing==TIM[0] else np.r_[np.nan,a[:-1]]
            ratio=np.divide(numer,den,out=np.full(nbar,np.nan),where=np.isfinite(den)&(den>0))
            for t in TH:shocks[(p,timing,t)]=(ratio>=t)&weekday
    return {'bases':bases,'shocks':shocks,'atrs':atrs}

def mask(prep,o,h,l,c,p,timing,t,fam,n):
    shock=prep['shocks'][(p,timing,t)]
    if fam=='SHOCK_BAR_BODY_DIRECTION_ONLY':return (c>o)&shock,(c<o)&shock
    b,s=prep['bases'][(fam,n)]
    return b&shock,s&shock
