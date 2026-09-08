#!/usr/bin/env python3
from __future__ import annotations
import numpy as np

THRESHOLDS=(1.0,1.25,1.5,1.75,2.0,2.5,3.0,3.5,4.0)
FAMILIES={
 'CURRENT_CLOSE_EXCEEDS_ALL_PRIOR_N_CLOSES':(1,2,3,4,5,8),
 'STRICT_MONOTONIC_N_CLOSE_SEQUENCE':(2,3,4,5,8),
 'CURRENT_CLOSE_BREAKS_PRIOR_N_BAR_EXTREME':(1,2,3,4,5,8),
 'SHOCK_BAR_BODY_DIRECTION_ONLY':(0,),
}
TIMINGS=('CURRENT_BAR_INCLUDED','LAGGED_ONE_BAR_PRE_SHOCK')

def atr14(high,low,close):
    h=high.astype(np.float64); l=low.astype(np.float64); c=close.astype(np.float64)
    pc=np.r_[np.nan,c[:-1]]
    tr=np.fmax(h-l,np.fmax(np.abs(h-pc),np.abs(l-pc)))
    cs=np.cumsum(np.nan_to_num(tr))
    out=np.full(len(c),np.nan)
    out[13:]=(cs[13:]-np.r_[0.0,cs[:-14]])/14.0
    return out

def gap_state(bucket,step_ms):
    n=len(bucket)
    if n==0: return np.empty(0,bool),np.empty(0,np.int64)
    d=np.diff(bucket)
    if np.any(d<=0) or np.any(d%step_ms!=0): raise ValueError('bucket integrity')
    reopening=np.r_[False,d>step_ms]
    idx=np.arange(n,dtype=np.int64)
    starts=np.where(np.r_[True,d!=step_ms],idx,0)
    last=np.maximum.accumulate(starts)
    run=idx-last+1
    return reopening,run

def bases(open_,high,low,close):
    out={}
    for fam,ns in FAMILIES.items():
        for n in ns:
            if fam=='SHOCK_BAR_BODY_DIRECTION_ONLY':
                out[(fam,n)]=(close>open_,close<open_); continue
            cw=np.lib.stride_tricks.sliding_window_view(close,n+1)
            buy=np.zeros(len(close),bool); sell=np.zeros(len(close),bool)
            if fam=='CURRENT_CLOSE_EXCEEDS_ALL_PRIOR_N_CLOSES':
                buy[n:]=cw[:,-1]>cw[:,:-1].max(axis=1); sell[n:]=cw[:,-1]<cw[:,:-1].min(axis=1)
            elif fam=='STRICT_MONOTONIC_N_CLOSE_SEQUENCE':
                dd=np.diff(cw,axis=1); buy[n:]=np.all(dd>0,axis=1); sell[n:]=np.all(dd<0,axis=1)
            else:
                hw=np.lib.stride_tricks.sliding_window_view(high,n+1); lw=np.lib.stride_tricks.sliding_window_view(low,n+1)
                buy[n:]=cw[:,-1]>hw[:,:-1].max(axis=1); sell[n:]=cw[:,-1]<lw[:,:-1].min(axis=1)
            out[(fam,n)]=(buy,sell)
    return out

def prepared(open_,high,low,close,bucket,step_ms):
    atr=atr14(high,low,close); reopening,run=gap_state(bucket,step_ms); b=bases(open_,high,low,close)
    shocks={}
    for ti,timing in enumerate(TIMINGS):
        den=atr if ti==0 else np.r_[np.nan,atr[:-1]]
        ratio=np.divide(high-low,den,out=np.full(len(close),np.nan),where=np.isfinite(den)&(den>0))
        for th in THRESHOLDS: shocks[(timing,th)]=ratio>=th
    return b,shocks,reopening,run

def masks_for_identity(prep,timing,th,fam,n):
    bases_,shocks,reopening,run=prep; buy0,sell0=bases_[(fam,n)]; shock=shocks[(timing,th)]
    base_buy=buy0&shock; base_sell=sell0&shock
    required=14 if timing=='CURRENT_BAR_INCLUDED' else 15
    if fam!='SHOCK_BAR_BODY_DIRECTION_ONLY': required=max(required,n+1)
    continuous=run>=required
    exclude=~reopening
    return {
      'CONTINUOUS_FULL_DEPENDENCY':(base_buy&continuous,base_sell&continuous),
      'EXCLUDE_REOPENING':(base_buy&exclude,base_sell&exclude),
      'REOPENING_ONLY':(base_buy&reopening,base_sell&reopening),
    }
