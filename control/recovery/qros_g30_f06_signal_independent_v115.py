from __future__ import annotations
import numpy as np
TIM=('CURRENT_BAR_INCLUDED','LAGGED_ONE_BAR_PRE_SHOCK')
TH=(1.0,1.25,1.5,1.75,2.0,2.5,3.0,3.5,4.0)
NS=(1,2,3,4,5,8)
FAMS=('CURRENT_CLOSE_EXCEEDS_ALL_PRIOR_N_CLOSES','STRICT_MONOTONIC_N_CLOSE_SEQUENCE','CURRENT_CLOSE_BREAKS_PRIOR_N_BAR_EXTREME')
WICK=('MAX_OPPOSING_WICK_50PCT_RANGE','MAX_OPPOSING_WICK_33PCT_RANGE','MAX_OPPOSING_WICK_20PCT_RANGE')
def rolling_sum_int(x,n):
 cs=np.cumsum(x,dtype=np.int64);out=np.empty(len(x)-n+1,np.int64);out[0]=cs[n-1]
 if len(out)>1:out[1:]=cs[n:]-cs[:-n]
 return out
def bars(mb,o,h,l,c,tf):
 step=tf*60000
 if tf==1:return tuple(np.asarray(x,dtype=np.int64).copy() for x in (mb,o,h,l,c))
 b=(mb//step)*step;st=np.flatnonzero(np.r_[True,b[1:]!=b[:-1]]);en=np.r_[st[1:]-1,len(b)-1]
 return b[st].astype(np.int64),o[st].astype(np.int64),np.maximum.reduceat(h,st).astype(np.int64),np.minimum.reduceat(l,st).astype(np.int64),c[en].astype(np.int64)
def atr_sma(h,l,c,p=14):
 H=h.astype(np.int64);L=l.astype(np.int64);C=c.astype(np.int64);prior=np.r_[C[0],C[:-1]];tr=np.maximum(H-L,np.maximum(np.abs(H-prior),np.abs(L-prior))).astype(np.int64);tr[0]=H[0]-L[0];out=np.full(len(C),np.nan);out[p-1:]=rolling_sum_int(tr,p).astype(float)/p;return out
def prepare(bucket,o,h,l,c):
 nbar=len(c);bases={};d=np.diff(c);pos=(d>0).astype(np.int8);neg=(d<0).astype(np.int8)
 for n in NS:
  pc=np.vstack([c[n-k:nbar-k] for k in range(1,n+1)]);ph=np.vstack([h[n-k:nbar-k] for k in range(1,n+1)]);pl=np.vstack([l[n-k:nbar-k] for k in range(1,n+1)])
  b=np.zeros(nbar,bool);s=np.zeros(nbar,bool);b[n:]=c[n:]>pc.max(0);s[n:]=c[n:]<pc.min(0);bases[(FAMS[0],n)]=(b,s)
  b=np.zeros(nbar,bool);s=np.zeros(nbar,bool);b[n:]=rolling_sum_int(pos,n)==n;s[n:]=rolling_sum_int(neg,n)==n;bases[(FAMS[1],n)]=(b,s)
  b=np.zeros(nbar,bool);s=np.zeros(nbar,bool);b[n:]=c[n:]>ph.max(0);s[n:]=c[n:]<pl.min(0);bases[(FAMS[2],n)]=(b,s)
 weekday=((bucket//86400000+3)%7)<5;R=(h-l).astype(np.int64);a=atr_sma(h,l,c,14);shocks={}
 for timing in TIM:
  den=a.copy() if timing==TIM[0] else np.r_[np.nan,a[:-1]];ratio=np.full(nbar,np.nan);ok=np.isfinite(den)&(den>0);ratio[ok]=R[ok]/den[ok]
  for t in TH:shocks[(timing,t)]=(ratio>=t)&weekday
 valid=R>0;lowwick=np.where(o<c,o-l,c-l).astype(np.int64);upwick=np.where(o>c,h-o,h-c).astype(np.int64)
 wick={'MAX_OPPOSING_WICK_50PCT_RANGE':(valid&(lowwick*2<=R),valid&(upwick*2<=R)),'MAX_OPPOSING_WICK_33PCT_RANGE':(valid&(lowwick*3<=R),valid&(upwick*3<=R)),'MAX_OPPOSING_WICK_20PCT_RANGE':(valid&(lowwick*5<=R),valid&(upwick*5<=R))}
 return {'bases':bases,'shocks':shocks,'wick':wick,'atr14':a}
def mask(prep,o,h,l,c,wick,timing,t,fam,n):
 sh=prep['shocks'][(timing,t)];wb,ws=prep['wick'][wick]
 if fam=='SHOCK_BAR_BODY_DIRECTION_ONLY':return np.logical_and(np.logical_and(c>o,sh),wb),np.logical_and(np.logical_and(c<o,sh),ws)
 b,s=prep['bases'][(fam,n)];return np.logical_and(np.logical_and(b,sh),wb),np.logical_and(np.logical_and(s,sh),ws)
