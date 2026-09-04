from __future__ import annotations
import numpy as np
from numba import njit
TIM=('CURRENT_BAR_INCLUDED','LAGGED_ONE_BAR_PRE_SHOCK');TH=(1.0,1.25,1.5,1.75,2.0,2.5,3.0,3.5,4.0);NS=(1,2,3,4,5,8);FAMS=('CURRENT_CLOSE_EXCEEDS_ALL_PRIOR_N_CLOSES','STRICT_MONOTONIC_N_CLOSE_SEQUENCE','CURRENT_CLOSE_BREAKS_PRIOR_N_BAR_EXTREME');CTX=('TICK_COUNT_ABOVE_MEDIAN','TICK_COUNT_TOP_QUINTILE');LBS=(20,50,100,500)
def rolling_sum_int(x,n):
 cs=np.cumsum(x,dtype=np.int64);out=np.empty(len(x)-n+1,np.int64);out[0]=cs[n-1]
 if len(out)>1:out[1:]=cs[n:]-cs[:-n]
 return out
def bars(mb,o,h,l,c,tf):
 step=tf*60000
 if tf==1:return tuple(np.asarray(x,dtype=np.int64).copy() for x in (mb,o,h,l,c))
 b=(mb//step)*step;st=np.flatnonzero(np.r_[True,b[1:]!=b[:-1]]);en=np.r_[st[1:]-1,len(b)-1]
 return b[st].astype(np.int64),o[st].astype(np.int64),np.maximum.reduceat(h,st).astype(np.int64),np.minimum.reduceat(l,st).astype(np.int64),c[en].astype(np.int64)
def count_bars(mb,count,tf):
 step=tf*60000;b=(mb//step)*step;st=np.flatnonzero(np.r_[True,b[1:]!=b[:-1]]);return np.add.reduceat(count.astype(np.int64),st).astype(np.int64)
def tr_sum14(h,l,c):
 H=h.astype(np.int64);L=l.astype(np.int64);C=c.astype(np.int64);pc=np.r_[C[0],C[:-1]];tr=np.maximum(H-L,np.maximum(np.abs(H-pc),np.abs(L-pc))).astype(np.int64);tr[0]=H[0]-L[0];out=np.full(len(C),-1,np.int64);out[13:]=rolling_sum_int(tr,14);return out
def atr_sma(h,l,c,p=14):
 s=tr_sum14(h,l,c);out=np.full(len(s),np.nan);ok=s>=0;out[ok]=s[ok]/14.;return out
@njit(cache=True)
def add(tree,base,i,d):
 p=base+i;tree[p]+=d;p//=2
 while p:tree[p]=tree[2*p]+tree[2*p+1];p//=2
@njit(cache=True)
def kth(tree,base,k):
 p=1
 while p<base:
  if tree[2*p]>=k:p*=2
  else:k-=tree[2*p];p=2*p+1
 return p-base
@njit(cache=True)
def rolling_contexts_segment(vals,uniq,L):
 n=len(vals);base=1
 while base<len(uniq):base*=2
 tree=np.zeros(base*2,np.int32);out=np.zeros((2,n),np.bool_);cnt=0;r50=(L+1)//2;r80=(4*L+4)//5
 for t in range(n):
  ai=t-2
  if ai>=0:q=np.searchsorted(uniq,vals[ai]);add(tree,base,q,1);cnt+=1
  ri=t-L-2
  if ri>=0:q=np.searchsorted(uniq,vals[ri]);add(tree,base,q,-1);cnt-=1
  if t>=1 and cnt==L:
   ref=vals[t-1];q50=uniq[kth(tree,base,r50)];q80=uniq[kth(tree,base,r80)];out[0,t]=ref>q50;out[1,t]=ref>=q80
 return out
def prepare(bucket,o,h,l,c,tick_count):
 nbar=len(c);bases={};d=np.diff(c);pos=(d>0).astype(np.int8);neg=(d<0).astype(np.int8)
 for n in NS:
  pc=np.vstack([c[n-k:nbar-k] for k in range(1,n+1)]);ph=np.vstack([h[n-k:nbar-k] for k in range(1,n+1)]);pl=np.vstack([l[n-k:nbar-k] for k in range(1,n+1)])
  b=np.zeros(nbar,bool);s=np.zeros(nbar,bool);b[n:]=c[n:]>pc.max(0);s[n:]=c[n:]<pc.min(0);bases[(FAMS[0],n)]=(b,s)
  b=np.zeros(nbar,bool);s=np.zeros(nbar,bool);b[n:]=rolling_sum_int(pos,n)==n;s[n:]=rolling_sum_int(neg,n)==n;bases[(FAMS[1],n)]=(b,s)
  b=np.zeros(nbar,bool);s=np.zeros(nbar,bool);b[n:]=c[n:]>ph.max(0);s[n:]=c[n:]<pl.min(0);bases[(FAMS[2],n)]=(b,s)
 weekday=((bucket//86400000+3)%7)<5;R=(h-l).astype(float);a=atr_sma(h,l,c);shocks={}
 for timing in TIM:
  den=a if timing==TIM[0] else np.r_[np.nan,a[:-1]];ratio=np.zeros(nbar,float);ok=np.isfinite(den)&(den>0);ratio[ok]=R[ok]/den[ok];ratio[~ok]=np.nan
  for t in TH:shocks[(timing,t)]=(ratio>=t)&weekday
 uniq=np.unique(tick_count);contexts={}
 for L in LBS:
  z=rolling_contexts_segment(tick_count,uniq,L)
  for i,name in enumerate(CTX):contexts[(name,L)]=z[i]
 return {'bases':bases,'shocks':shocks,'contexts':contexts,'atr14':a}
def mask(prep,o,h,l,c,ctx,L,timing,t,fam,n):
 sh=np.logical_and(prep['shocks'][(timing,t)],prep['contexts'][(ctx,L)])
 if fam=='SHOCK_BAR_BODY_DIRECTION_ONLY':return np.logical_and(c>o,sh),np.logical_and(c<o,sh)
 b,s=prep['bases'][(fam,n)];return np.logical_and(b,sh),np.logical_and(s,sh)
