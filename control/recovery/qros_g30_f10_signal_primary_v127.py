from __future__ import annotations
import numpy as np
from numba import njit
TIM=('CURRENT_BAR_INCLUDED','LAGGED_ONE_BAR_PRE_SHOCK')
TH=(1.0,1.25,1.5,1.75,2.0,2.5,3.0,3.5,4.0)
NS=(1,2,3,4,5,8)
FAMS=('CURRENT_CLOSE_EXCEEDS_ALL_PRIOR_N_CLOSES','STRICT_MONOTONIC_N_CLOSE_SEQUENCE','CURRENT_CLOSE_BREAKS_PRIOR_N_BAR_EXTREME')
CTX=('TICK_COUNT_ABOVE_MEDIAN','TICK_COUNT_TOP_QUINTILE')
LBS=(20,50,100,500)
def bars(mb,o,h,l,c,tf):
 step=tf*60000;b=(mb//step)*step;st=np.r_[0,np.flatnonzero(b[1:]!=b[:-1])+1];en=np.r_[st[1:],len(b)]
 return b[st].astype(np.int64),o[st],np.maximum.reduceat(h,st),np.minimum.reduceat(l,st),c[en-1]
def count_bars(mb,count,tf):
 step=tf*60000;b=(mb//step)*step;st=np.r_[0,np.flatnonzero(b[1:]!=b[:-1])+1]
 return np.add.reduceat(count.astype(np.int64),st).astype(np.int64)
def tr_sum14(h,l,c):
 H=h.astype(np.int64);L=l.astype(np.int64);C=c.astype(np.int64);pc=np.r_[C[0],C[:-1]];tr=np.maximum(H-L,np.maximum(np.abs(H-pc),np.abs(L-pc)));tr[0]=H[0]-L[0]
 cs=np.cumsum(tr,dtype=np.int64);out=np.full(len(C),-1,np.int64);out[13:]=cs[13:]-np.r_[0,cs[:-14]];return out
def atr_sma(h,l,c,p=14):
 s=tr_sum14(h,l,c);out=np.full(len(s),np.nan);ok=s>=0;out[ok]=s[ok]/14.0;return out
@njit(cache=True)
def _bit_add(bit,i,d):
 i+=1
 while i<len(bit):bit[i]+=d;i+=i&-i
@njit(cache=True)
def _bit_kth(bit,k):
 idx=0;step=1
 while (step<<1)<len(bit):step<<=1
 while step:
  nxt=idx+step
  if nxt<len(bit) and bit[nxt]<k:idx=nxt;k-=bit[nxt]
  step>>=1
 return idx
@njit(cache=True)
def rolling_contexts_fenwick(vals,uniq,L):
 n=len(vals);out=np.zeros((2,n),np.bool_);bit=np.zeros(len(uniq)+1,np.int32);cnt=0;r50=(L+1)//2;r80=(4*L+4)//5
 for t in range(n):
  ai=t-2
  if ai>=0:
   q=np.searchsorted(uniq,vals[ai]);_bit_add(bit,q,1);cnt+=1
  ri=t-L-2
  if ri>=0:
   q=np.searchsorted(uniq,vals[ri]);_bit_add(bit,q,-1);cnt-=1
  if t>=1 and cnt==L:
   ref=vals[t-1];q50=uniq[_bit_kth(bit,r50)];q80=uniq[_bit_kth(bit,r80)];out[0,t]=ref>q50;out[1,t]=ref>=q80
 return out
def prepare(bucket,o,h,l,c,tick_count):
 nbar=len(c);bases={}
 for n in NS:
  cw=np.lib.stride_tricks.sliding_window_view(c,n+1);hw=np.lib.stride_tricks.sliding_window_view(h,n+1);lw=np.lib.stride_tricks.sliding_window_view(l,n+1)
  b=np.zeros(nbar,bool);s=np.zeros(nbar,bool);b[n:]=cw[:,-1]>cw[:,:-1].max(1);s[n:]=cw[:,-1]<cw[:,:-1].min(1);bases[(FAMS[0],n)]=(b,s)
  d=np.diff(cw,axis=1);b=np.zeros(nbar,bool);s=np.zeros(nbar,bool);b[n:]=np.all(d>0,1);s[n:]=np.all(d<0,1);bases[(FAMS[1],n)]=(b,s)
  b=np.zeros(nbar,bool);s=np.zeros(nbar,bool);b[n:]=cw[:,-1]>hw[:,:-1].max(1);s[n:]=cw[:,-1]<lw[:,:-1].min(1);bases[(FAMS[2],n)]=(b,s)
 weekday=((bucket//86400000+3)%7)<5;numer=(h-l).astype(float);a=atr_sma(h,l,c);shocks={}
 for timing in TIM:
  den=a if timing==TIM[0] else np.r_[np.nan,a[:-1]];ratio=np.divide(numer,den,out=np.full(nbar,np.nan),where=np.isfinite(den)&(den>0))
  for t in TH:shocks[(timing,t)]=(ratio>=t)&weekday
 uniq=np.unique(tick_count);contexts={}
 for L in LBS:
  z=rolling_contexts_fenwick(tick_count,uniq,L)
  for i,name in enumerate(CTX):contexts[(name,L)]=z[i]
 return {'bases':bases,'shocks':shocks,'contexts':contexts,'atr14':a}
def mask(prep,o,h,l,c,ctx,L,timing,t,fam,n):
 sh=prep['shocks'][(timing,t)]&prep['contexts'][(ctx,L)]
 if fam=='SHOCK_BAR_BODY_DIRECTION_ONLY':return (c>o)&sh,(c<o)&sh
 b,s=prep['bases'][(fam,n)];return b&sh,s&sh
