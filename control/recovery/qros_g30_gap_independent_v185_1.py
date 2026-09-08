#!/usr/bin/env python3
from __future__ import annotations
import numpy as np
from numba import njit

THRESHOLDS=(1.0,1.25,1.5,1.75,2.0,2.5,3.0,3.5,4.0)
FAMILIES={
 'CURRENT_CLOSE_EXCEEDS_ALL_PRIOR_N_CLOSES':(1,2,3,4,5,8),
 'STRICT_MONOTONIC_N_CLOSE_SEQUENCE':(2,3,4,5,8),
 'CURRENT_CLOSE_BREAKS_PRIOR_N_BAR_EXTREME':(1,2,3,4,5,8),
 'SHOCK_BAR_BODY_DIRECTION_ONLY':(0,),
}
TIMINGS=('CURRENT_BAR_INCLUDED','LAGGED_ONE_BAR_PRE_SHOCK')

@njit(cache=True)
def atr14_loop(high,low,close):
    m=len(close); out=np.full(m,np.nan); tr=np.empty(m,np.float64); s=0.0
    for i in range(m):
        v=float(high[i]-low[i])
        if i>0:
            a=abs(float(high[i]-close[i-1])); b=abs(float(low[i]-close[i-1]));
            if a>v:v=a
            if b>v:v=b
        tr[i]=v; s+=v
        if i>=14:s-=tr[i-14]
        if i>=13:out[i]=s/14.0
    return out

@njit(cache=True)
def gap_loop(bucket,step_ms):
    m=len(bucket); reopen=np.zeros(m,np.bool_); run=np.empty(m,np.int64)
    if m==0:return reopen,run
    run[0]=1
    for i in range(1,m):
        d=bucket[i]-bucket[i-1]
        if d<=0 or d%step_ms!=0: raise ValueError('bucket integrity')
        if d==step_ms: run[i]=run[i-1]+1
        else: reopen[i]=True; run[i]=1
    return reopen,run

@njit(cache=True)
def shock_threshold_loop(high,low,den,th):
    m=len(high); s=np.zeros(m,np.bool_)
    for i in range(m):
        if np.isfinite(den[i]) and den[i]>0 and float(high[i]-low[i])/den[i]>=th:
            s[i]=True
    return s

@njit(cache=True)
def predicate(close,high,low,open_,fam_code,n):
    m=len(close); buy=np.zeros(m,np.bool_); sell=np.zeros(m,np.bool_)
    if fam_code==3:
        for i in range(m): buy[i]=close[i]>open_[i]; sell[i]=close[i]<open_[i]
        return buy,sell
    for i in range(n,m):
        if fam_code==0:
            mx=close[i-n]; mn=close[i-n]
            for j in range(i-n,i):
                if close[j]>mx:mx=close[j]
                if close[j]<mn:mn=close[j]
            buy[i]=close[i]>mx; sell[i]=close[i]<mn
        elif fam_code==1:
            up=True; dn=True
            for j in range(i-n,i):
                if close[j+1]<=close[j]:up=False
                if close[j+1]>=close[j]:dn=False
            buy[i]=up; sell[i]=dn
        else:
            mx=high[i-n]; mn=low[i-n]
            for j in range(i-n,i):
                if high[j]>mx:mx=high[j]
                if low[j]<mn:mn=low[j]
            buy[i]=close[i]>mx; sell[i]=close[i]<mn
    return buy,sell

def prepared(open_,high,low,close,bucket,step_ms):
    atr=atr14_loop(high,low,close); reopening,run=gap_loop(bucket,np.int64(step_ms))
    fam_code={'CURRENT_CLOSE_EXCEEDS_ALL_PRIOR_N_CLOSES':0,'STRICT_MONOTONIC_N_CLOSE_SEQUENCE':1,'CURRENT_CLOSE_BREAKS_PRIOR_N_BAR_EXTREME':2,'SHOCK_BAR_BODY_DIRECTION_ONLY':3}
    b={}
    for fam,ns in FAMILIES.items():
        for n in ns:b[(fam,n)]=predicate(close,high,low,open_,fam_code[fam],n)
    shocks={}
    for ti,timing in enumerate(TIMINGS):
        den=atr if ti==0 else np.r_[np.nan,atr[:-1]]
        for th in THRESHOLDS:
            shocks[(timing,th)]=shock_threshold_loop(high,low,den,th)
    return b,shocks,reopening,run

def masks_for_identity(prep,timing,th,fam,n):
    b,sh,reopening,run=prep; bb,ss=b[(fam,n)]; shock=sh[(timing,th)]
    base_buy=bb&shock; base_sell=ss&shock
    required=14 if timing=='CURRENT_BAR_INCLUDED' else 15
    if fam!='SHOCK_BAR_BODY_DIRECTION_ONLY':required=max(required,n+1)
    cont=np.zeros(len(run),bool)
    for i in range(len(run)):cont[i]=run[i]>=required
    excl=np.logical_not(reopening)
    return {
      'CONTINUOUS_FULL_DEPENDENCY':(base_buy&cont,base_sell&cont),
      'EXCLUDE_REOPENING':(base_buy&excl,base_sell&excl),
      'REOPENING_ONLY':(base_buy&reopening,base_sell&reopening),
    }
