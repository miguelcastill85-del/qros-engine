from __future__ import annotations
import numpy as np
from numba import njit
TIM=('CURRENT_BAR_INCLUDED','LAGGED_ONE_BAR_PRE_SHOCK')
TH=(1.0,1.25,1.5,1.75,2.0,2.5,3.0,3.5,4.0)
NS=(1,2,3,4,5,8)
FAMS=('CURRENT_CLOSE_EXCEEDS_ALL_PRIOR_N_CLOSES','STRICT_MONOTONIC_N_CLOSE_SEQUENCE','CURRENT_CLOSE_BREAKS_PRIOR_N_BAR_EXTREME')
CTX=('ATR_ABOVE_MEDIAN','ATR_PERCENTILE_20_80','ATR_TOP_QUINTILE','PRE_SHOCK_COMPRESSION')
LBS=(20,50,100,200,500)

def rolling_sum_int(x,n):
 cs=np.cumsum(x,dtype=np.int64);out=np.empty(len(x)-n+1,np.int64);out[0]=cs[n-1]
 if len(out)>1:out[1:]=cs[n:]-cs[:-n]
 return out

def bars(mb,o,h,l,c,tf):
 step=tf*60000
 if tf==1:return tuple(np.asarray(x,dtype=np.int64).copy() for x in (mb,o,h,l,c))
 b=(mb//step)*step;starts=np.flatnonzero(np.r_[True,b[1:]!=b[:-1]]);ends=np.r_[starts[1:]-1,len(b)-1]
 return b[starts].astype(np.int64),o[starts].astype(np.int64),np.maximum.reduceat(h,starts).astype(np.int64),np.minimum.reduceat(l,starts).astype(np.int64),c[ends].astype(np.int64)

def tr_sum14(h,l,c):
 H=h.astype(np.int64);L=l.astype(np.int64);C=c.astype(np.int64);prior=np.r_[C[0],C[:-1]];tr=np.maximum(H-L,np.maximum(np.abs(H-prior),np.abs(L-prior))).astype(np.int64);tr[0]=H[0]-L[0];out=np.full(len(C),-1,np.int64);out[13:]=rolling_sum_int(tr,14);return out

def atr_sma(h,l,c,p=14):
 s=tr_sum14(h,l,c);out=np.full(len(s),np.nan);ok=s>=0;out[ok]=s[ok]/14.0;return out

@njit(cache=True)
def seg_add(tree,base,i,delta):
 p=base+i;tree[p]+=delta;p//=2
 while p:
  tree[p]=tree[p*2]+tree[p*2+1];p//=2
@njit(cache=True)
def seg_kth(tree,base,k):
 p=1
 while p<base:
  if tree[p*2]>=k:p=p*2
  else:k-=tree[p*2];p=p*2+1
 return p-base
@njit(cache=True)
def rolling_contexts_segment(vals,uniq,L):
 n=len(vals);out=np.zeros((4,n),np.bool_);base=1
 while base<len(uniq):base*=2
 tree=np.zeros(base*2,np.int32);count=0;r20=(L+4)//5;r50=(L+1)//2;r80=(4*L+4)//5
 for t in range(n):
  ai=t-2
  if ai>=0 and vals[ai]>=0:
   q=np.searchsorted(uniq,vals[ai]);seg_add(tree,base,q,1);count+=1
  ri=t-L-2
  if ri>=0 and vals[ri]>=0:
   q=np.searchsorted(uniq,vals[ri]);seg_add(tree,base,q,-1);count-=1
  if t>=1 and count==L and vals[t-1]>=0:
   ref=vals[t-1];q20=uniq[seg_kth(tree,base,r20)];q50=uniq[seg_kth(tree,base,r50)];q80=uniq[seg_kth(tree,base,r80)]
   out[0,t]=ref>q50;out[1,t]=q20<=ref<=q80;out[2,t]=ref>=q80;out[3,t]=ref<=q20
 return out

def prepare(bucket,o,h,l,c):
 nbar=len(c);bases={};d=np.diff(c);pos=(d>0).astype(np.int8);neg=(d<0).astype(np.int8)
 for n in NS:
  pc=np.vstack([c[n-k:nbar-k] for k in range(1,n+1)]);ph=np.vstack([h[n-k:nbar-k] for k in range(1,n+1)]);pl=np.vstack([l[n-k:nbar-k] for k in range(1,n+1)])
  b=np.zeros(nbar,bool);s=np.zeros(nbar,bool);b[n:]=c[n:]>pc.max(0);s[n:]=c[n:]<pc.min(0);bases[(FAMS[0],n)]=(b,s)
  b=np.zeros(nbar,bool);s=np.zeros(nbar,bool);b[n:]=rolling_sum_int(pos,n)==n;s[n:]=rolling_sum_int(neg,n)==n;bases[(FAMS[1],n)]=(b,s)
  b=np.zeros(nbar,bool);s=np.zeros(nbar,bool);b[n:]=c[n:]>ph.max(0);s[n:]=c[n:]<pl.min(0);bases[(FAMS[2],n)]=(b,s)
 weekday=((bucket//86400000+3)%7)<5;R=(h-l).astype(float);a=atr_sma(h,l,c);shocks={}
 for timing in TIM:
  den=a.copy() if timing==TIM[0] else np.r_[np.nan,a[:-1]];ratio=np.zeros(nbar,float);ok=np.isfinite(den)&(den>0);ratio[ok]=R[ok]/den[ok];ratio[~ok]=np.nan
  for t in TH:shocks[(timing,t)]=(ratio>=t)&weekday
 s=tr_sum14(h,l,c);uniq=np.unique(s[s>=0]);contexts={}
 for L in LBS:
  z=rolling_contexts_segment(s,uniq,L)
  for i,name in enumerate(CTX):contexts[(name,L)]=z[i]
 return {'bases':bases,'shocks':shocks,'contexts':contexts,'atr14':a}

def mask(prep,o,h,l,c,ctx,L,timing,t,fam,n):
 sh=np.logical_and(prep['shocks'][(timing,t)],prep['contexts'][(ctx,L)])
 if fam=='SHOCK_BAR_BODY_DIRECTION_ONLY':return np.logical_and(c>o,sh),np.logical_and(c<o,sh)
 b,s=prep['bases'][(fam,n)];return np.logical_and(b,sh),np.logical_and(s,sh)
