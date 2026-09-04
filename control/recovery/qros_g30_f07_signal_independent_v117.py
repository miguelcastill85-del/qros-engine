from __future__ import annotations
import numpy as np
from numba import njit
TIM=('CURRENT_BAR_INCLUDED','LAGGED_ONE_BAR_PRE_SHOCK')
TH=(1.0,1.25,1.5,1.75,2.0,2.5,3.0,3.5,4.0)
NS=(1,2,3,4,5,8)
FAMS=('CURRENT_CLOSE_EXCEEDS_ALL_PRIOR_N_CLOSES','STRICT_MONOTONIC_N_CLOSE_SEQUENCE','CURRENT_CLOSE_BREAKS_PRIOR_N_BAR_EXTREME')
VARIANTS=(('NEXT_BAR_DIRECTIONAL_CLOSE',1),('NEXT_BAR_DIRECTIONAL_CLOSE',2),('NEXT_BAR_DIRECTIONAL_CLOSE',3),('NEXT_BAR_BREAK_SHOCK_EXTREME',1),('NEXT_BAR_BREAK_SHOCK_EXTREME',2),('NEXT_BAR_BREAK_SHOCK_EXTREME',3),('TWO_BAR_CONTINUATION',2),('TWO_BAR_CONTINUATION',3))

def rolling_sum_int(x,n):
 cs=np.cumsum(x,dtype=np.int64);out=np.empty(len(x)-n+1,np.int64);out[0]=cs[n-1]
 if len(out)>1:out[1:]=cs[n:]-cs[:-n]
 return out

def bars(mb,o,h,l,c,tf):
 step=tf*60000
 if tf==1:return tuple(np.asarray(x,dtype=np.int64).copy() for x in (mb,o,h,l,c))
 b=(mb//step)*step;starts=np.flatnonzero(np.r_[True,b[1:]!=b[:-1]]);ends=np.r_[starts[1:]-1,len(b)-1]
 return b[starts].astype(np.int64),o[starts].astype(np.int64),np.maximum.reduceat(h,starts).astype(np.int64),np.minimum.reduceat(l,starts).astype(np.int64),c[ends].astype(np.int64)

def atr_sma(h,l,c,p=14):
 H=h.astype(np.int64);L=l.astype(np.int64);C=c.astype(np.int64);prior=np.r_[C[0],C[:-1]];tr=np.maximum(H-L,np.maximum(np.abs(H-prior),np.abs(L-prior))).astype(np.int64);tr[0]=H[0]-L[0];out=np.full(len(C),np.nan);out[p-1:]=rolling_sum_int(tr,p).astype(float)/float(p);return out

def prepare(bucket,o,h,l,c):
 nbar=len(c);bases={};d=np.diff(c);pos=(d>0).astype(np.int8);neg=(d<0).astype(np.int8)
 for n in NS:
  pc=np.vstack([c[n-k:nbar-k] for k in range(1,n+1)]);ph=np.vstack([h[n-k:nbar-k] for k in range(1,n+1)]);pl=np.vstack([l[n-k:nbar-k] for k in range(1,n+1)])
  b=np.zeros(nbar,bool);s=np.zeros(nbar,bool);b[n:]=c[n:]>pc.max(0);s[n:]=c[n:]<pc.min(0);bases[(FAMS[0],n)]=(b,s)
  b=np.zeros(nbar,bool);s=np.zeros(nbar,bool);b[n:]=rolling_sum_int(pos,n)==n;s[n:]=rolling_sum_int(neg,n)==n;bases[(FAMS[1],n)]=(b,s)
  b=np.zeros(nbar,bool);s=np.zeros(nbar,bool);b[n:]=c[n:]>ph.max(0);s[n:]=c[n:]<pl.min(0);bases[(FAMS[2],n)]=(b,s)
 weekday=((bucket//86400000+3)%7)<5;R=(h-l).astype(float);a=atr_sma(h,l,c,14);shocks={}
 for timing in TIM:
  den=a.copy() if timing==TIM[0] else np.r_[np.nan,a[:-1]];ratio=np.zeros(nbar,float);ok=np.isfinite(den)&(den>0);ratio[ok]=R[ok]/den[ok];ratio[~ok]=np.nan
  for t in TH:shocks[(timing,t)]=(ratio>=t)&weekday
 return {'bases':bases,'shocks':shocks,'atr14':a,'bucket':bucket}

@njit(cache=True)
def confirm_loop(base,bucket,o,h,l,c,kind_code,w,side):
 n=len(base);out=np.zeros(n,np.bool_)
 if n<2:return out
 step=bucket[1]-bucket[0]
 for i in range(n):
  if not base[i]:continue
  maxj=w
  if i+maxj>=n:maxj=n-i-1
  first=1 if kind_code<2 else 2
  for j in range(first,maxj+1):
   ok=True
   for q in range(1,j+1):
    if bucket[i+q]-bucket[i+q-1]!=step:ok=False;break
   if not ok:break
   hit=False
   if kind_code==0:
    hit=(c[i+j]>o[i+j]) if side==1 else (c[i+j]<o[i+j])
   elif kind_code==1:
    hit=(h[i+j]>h[i]) if side==1 else (l[i+j]<l[i])
   else:
    if side==1:hit=(c[i+j-1]>o[i+j-1] and c[i+j]>o[i+j] and c[i+j]>c[i+j-1] and c[i+j-1]>c[i])
    else:hit=(c[i+j-1]<o[i+j-1] and c[i+j]<o[i+j] and c[i+j]<c[i+j-1] and c[i+j-1]<c[i])
   if hit:out[i+j]=True;break
 return out

def mask(prep,o,h,l,c,kind,w,timing,t,fam,n):
 sh=prep['shocks'][(timing,t)]
 if fam=='SHOCK_BAR_BODY_DIRECTION_ONLY':b=(c>o)&sh;s=(c<o)&sh
 else:
  bb,ss=prep['bases'][(fam,n)];b=bb&sh;s=ss&sh
 code=0 if kind=='NEXT_BAR_DIRECTIONAL_CLOSE' else (1 if kind=='NEXT_BAR_BREAK_SHOCK_EXTREME' else 2)
 return confirm_loop(b,prep['bucket'],o,h,l,c,code,w,1),confirm_loop(s,prep['bucket'],o,h,l,c,code,w,-1)
