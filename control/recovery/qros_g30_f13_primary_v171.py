from __future__ import annotations
import math
import numpy as np
from numba import njit

TIM=('CURRENT_BAR_INCLUDED','LAGGED_ONE_BAR_PRE_SHOCK')
TH=(1.0,1.25,1.5,1.75,2.0,2.5,3.0,3.5,4.0)
NS=(1,2,3,4,5,8)
FAMS=('CURRENT_CLOSE_EXCEEDS_ALL_PRIOR_N_CLOSES','STRICT_MONOTONIC_N_CLOSE_SEQUENCE','CURRENT_CLOSE_BREAKS_PRIOR_N_BAR_EXTREME')
DOW=('MON','TUE','WED','THU','FRI')

BASE={
 'shock_measure':'HIGH_LOW_RANGE_OVER_ATR','atr_period':14,'atr_smoothing':'SMA_TR',
 'close_location_filter':None,'wick_filter':None,
 'post_shock_confirmation':None,'confirmation_window_bars':0,
 'volatility_regime_context':None,'volatility_lookback':0,
 'spread_context':None,'spread_lookback':0,
 'tick_intensity_context':None,'tick_intensity_lookback':0,
 'event_refractory_bars':0,'day_of_week':None,
}

def bars(mb,o,h,l,c,tf):
 step=int(tf)*60000;b=(mb//step)*step
 st=np.r_[0,np.flatnonzero(b[1:]!=b[:-1])+1];en=np.r_[st[1:],len(b)]
 return b[st].astype(np.int64),o[st].astype(np.int64),np.maximum.reduceat(h,st).astype(np.int64),np.minimum.reduceat(l,st).astype(np.int64),c[en-1].astype(np.int64)

def true_range(h,l,c):
 H=h.astype(np.float64);L=l.astype(np.float64);C=c.astype(np.float64)
 tr=np.empty(len(C),np.float64)
 if not len(C): return tr
 tr[0]=H[0]-L[0]
 if len(C)>1:
  pc=C[:-1];tr[1:]=np.maximum(H[1:]-L[1:],np.maximum(np.abs(H[1:]-pc),np.abs(L[1:]-pc)))
 return tr

def atr(h,l,c,p=14,smoothing='SMA_TR'):
 tr=true_range(h,l,c);n=len(tr);out=np.full(n,np.nan,np.float64);p=int(p)
 if n<p:return out
 seed=float(np.sum(tr[:p],dtype=np.float64)/p)
 if smoothing=='SMA_TR':
  cs=np.cumsum(tr,dtype=np.float64);out[p-1:]=(cs[p-1:]-np.r_[0.0,cs[:-p]])/float(p);return out
 out[p-1]=seed
 if smoothing=='WILDER_RMA_TR':
  prev=seed
  for i in range(p,n):prev=((p-1)*prev+tr[i])/float(p);out[i]=prev
  return out
 if smoothing=='EMA_TR':
  a=2.0/float(p+1);b=1.0-a;prev=seed
  for i in range(p,n):prev=a*tr[i]+b*prev;out[i]=prev
  return out
 raise ValueError(smoothing)

def persistence_bases(h,l,c):
 nbar=len(c);out={}
 for n in NS:
  cw=np.lib.stride_tricks.sliding_window_view(c,n+1);hw=np.lib.stride_tricks.sliding_window_view(h,n+1);lw=np.lib.stride_tricks.sliding_window_view(l,n+1)
  b=np.zeros(nbar,bool);s=np.zeros(nbar,bool);b[n:]=cw[:,-1]>cw[:,:-1].max(1);s[n:]=cw[:,-1]<cw[:,:-1].min(1);out[(FAMS[0],n)]=(b,s)
  if n>1: # V168 canonical: monotonic N=1 is an alias of close-exceeds-prior N=1
   d=np.diff(cw,axis=1);b=np.zeros(nbar,bool);s=np.zeros(nbar,bool);b[n:]=np.all(d>0,1);s[n:]=np.all(d<0,1);out[(FAMS[1],n)]=(b,s)
  b=np.zeros(nbar,bool);s=np.zeros(nbar,bool);b[n:]=cw[:,-1]>hw[:,:-1].max(1);s[n:]=cw[:,-1]<lw[:,:-1].min(1);out[(FAMS[2],n)]=(b,s)
 return out

def persistence_specs():
 for fam in FAMS:
  for n in NS:
   if fam==FAMS[1] and n==1:continue
   yield fam,n
 yield 'SHOCK_BAR_BODY_DIRECTION_ONLY',1

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
def _rolling_quantile_masks(vals,valid_mode,L,mode,cap):
 # mode: 0 volatility -> q20/q50/q80; 1 spread -> q75/q90+cap; 2 ticks -> q50/q80
 n=len(vals);rows=4 if mode==0 else (3 if mode==1 else 2);out=np.zeros((rows,n),np.bool_)
 valid=np.zeros(n,np.bool_)
 for i in range(n): valid[i]=(vals[i]>=0 if valid_mode==0 else (vals[i]>0 if valid_mode==1 else True))
 u=np.unique(vals[valid]);bit=np.zeros(len(u)+1,np.int32);cnt=0
 r20=(L+4)//5;r50=(L+1)//2;r75=(3*L+3)//4;r80=(4*L+4)//5;r90=(9*L+9)//10
 for t in range(n):
  ai=t-2
  if ai>=0 and valid[ai]:q=np.searchsorted(u,vals[ai]);_bit_add(bit,q,1);cnt+=1
  ri=t-L-2
  if ri>=0 and valid[ri]:q=np.searchsorted(u,vals[ri]);_bit_add(bit,q,-1);cnt-=1
  if t>=1 and valid[t-1]:
   ref=vals[t-1]
   if mode==1: out[2,t]=ref<=cap
   if cnt==L:
    if mode==0:
     q20=u[_bit_kth(bit,r20)];q50=u[_bit_kth(bit,r50)];q80=u[_bit_kth(bit,r80)]
     out[0,t]=ref>q50;out[1,t]=ref>=q20 and ref<=q80;out[2,t]=ref>=q80;out[3,t]=ref<=q20
    elif mode==1:
     q75=u[_bit_kth(bit,r75)];q90=u[_bit_kth(bit,r90)];out[0,t]=ref<=q75;out[1,t]=ref<=q90
    else:
     q50=u[_bit_kth(bit,r50)];q80=u[_bit_kth(bit,r80)];out[0,t]=ref>q50;out[1,t]=ref>=q80
 return out

def tr_sum14_int(h,l,c):
 H=h.astype(np.int64);L=l.astype(np.int64);C=c.astype(np.int64);pc=np.r_[C[0],C[:-1]]
 tr=np.maximum(H-L,np.maximum(np.abs(H-pc),np.abs(L-pc)));tr[0]=H[0]-L[0];cs=np.cumsum(tr,dtype=np.int64);out=np.full(len(C),-1,np.int64);out[13:]=cs[13:]-np.r_[0,cs[:-14]];return out

def prepare(bucket,o,h,l,c,spread=None,tick_count=None,asset='NQX'):
 n=len(c);bucket=np.asarray(bucket,np.int64);o=np.asarray(o,np.int64);h=np.asarray(h,np.int64);l=np.asarray(l,np.int64);c=np.asarray(c,np.int64)
 prep={'bucket':bucket,'o':o,'h':h,'l':l,'c':c,'bases':persistence_bases(h,l,c),'shock_cache':{}}
 prep['weekday']=((bucket//86400000+3)%7).astype(np.int8)
 H=h.astype(np.float64);L=l.astype(np.float64);C=c.astype(np.float64);O=o.astype(np.float64);pc=np.r_[np.nan,C[:-1]]
 prep['numerators']={
  'HIGH_LOW_RANGE_OVER_ATR':H-L,
  'TRUE_RANGE_OVER_ATR':np.r_[H[0]-L[0],np.maximum(H[1:]-L[1:],np.maximum(np.abs(H[1:]-C[:-1]),np.abs(L[1:]-C[:-1])))],
  'ABS_CLOSE_TO_CLOSE_RETURN_OVER_ATR':np.r_[np.nan,np.abs(C[1:]-C[:-1])],
  'BODY_OVER_ATR':np.abs(C-O),
 }
 prep['atr_cache']={}
 R=(h-l).astype(np.int64);X=(c-l).astype(np.int64);valid=R>0
 prep['loc']={
  'TOP_BOTTOM_50PCT':(valid&(2*X>=R),valid&(2*X<=R)),
  'TOP_BOTTOM_33PCT':(valid&(3*X>=2*R),valid&(3*X<=R)),
  'TOP_BOTTOM_25PCT':(valid&(4*X>=3*R),valid&(4*X<=R)),
 }
 lw=(np.minimum(o,c)-l).astype(np.int64);uw=(h-np.maximum(o,c)).astype(np.int64)
 prep['wick']={
  'MAX_OPPOSING_WICK_50PCT_RANGE':(valid&(2*lw<=R),valid&(2*uw<=R)),
  'MAX_OPPOSING_WICK_33PCT_RANGE':(valid&(3*lw<=R),valid&(3*uw<=R)),
  'MAX_OPPOSING_WICK_20PCT_RANGE':(valid&(5*lw<=R),valid&(5*uw<=R)),
 }
 # F07 contiguity
 step=int(bucket[1]-bucket[0]) if n>1 else 0;one=np.zeros(n,bool)
 if n>1:one[:-1]=(bucket[1:]-bucket[:-1])==step
 contig={1:one.copy()};c2=np.zeros(n,bool);c3=np.zeros(n,bool)
 if n>2:c2[:-2]=one[:-2]&one[1:-1]
 if n>3:c3[:-3]=one[:-3]&one[1:-2]&one[2:-1]
 contig[2]=c2;contig[3]=c3;prep['contig']=contig
 # pre-shock context inputs
 vs=tr_sum14_int(h,l,c);prep['vol_ctx']={}
 for Lb in (20,50,100,200,500):
  z=_rolling_quantile_masks(vs,0,Lb,0,0)
  for i,name in enumerate(('ATR_ABOVE_MEDIAN','ATR_PERCENTILE_20_80','ATR_TOP_QUINTILE','PRE_SHOCK_COMPRESSION')):prep['vol_ctx'][(name,Lb)]=z[i]
 prep['spread_ctx']={}
 if spread is not None:
  sp=np.asarray(spread,np.int64);cap=10 if asset=='NQX' else 15
  for Lb in (50,100,500,2000):
   z=_rolling_quantile_masks(sp,1,Lb,1,cap);prep['spread_ctx'][('SPREAD_BELOW_ROLLING_P75',Lb)]=z[0];prep['spread_ctx'][('SPREAD_BELOW_ROLLING_P90',Lb)]=z[1]
   if Lb==50:prep['spread_ctx'][('SPREAD_POINTS_BELOW_FROZEN_CAP','CANONICAL_NOT_APPLICABLE')]=z[2]
 prep['tick_ctx']={}
 if tick_count is not None:
  tc=np.asarray(tick_count,np.int64)
  for Lb in (20,50,100,500):
   z=_rolling_quantile_masks(tc,2,Lb,2,0);prep['tick_ctx'][('TICK_COUNT_ABOVE_MEDIAN',Lb)]=z[0];prep['tick_ctx'][('TICK_COUNT_TOP_QUINTILE',Lb)]=z[1]
 prep['management_atr14']=atr(h,l,c,14,'SMA_TR')
 return prep

def pair_params(pair):
 p=dict(BASE);p.update(pair['a']);p.update(pair['b']);return p

def _signal_atr(prep,p,smooth):
 k=(int(p),smooth)
 if k not in prep['atr_cache']:prep['atr_cache'][k]=atr(prep['h'],prep['l'],prep['c'],p,smooth)
 return prep['atr_cache'][k]

def _confirm(base,prep,kind,w,side):
 o,h,l,c=prep['o'],prep['h'],prep['l'],prep['c'];n=len(base);out=np.zeros(n,bool);done=np.zeros(n,bool);contig=prep['contig']
 js=range(1,w+1) if kind!='TWO_BAR_CONTINUATION' else range(2,w+1)
 for j in js:
  if n<=j:continue
  if kind=='NEXT_BAR_DIRECTIONAL_CLOSE':cond=(c[j:]>o[j:]) if side==1 else (c[j:]<o[j:])
  elif kind=='NEXT_BAR_BREAK_SHOCK_EXTREME':cond=(h[j:]>h[:-j]) if side==1 else (l[j:]<l[:-j])
  else:
   if side==1:cond=(c[j-1:-1]>o[j-1:-1])&(c[j:]>o[j:])&(c[j:]>c[j-1:-1])&(c[j-1:-1]>c[:-j])
   else:cond=(c[j-1:-1]<o[j-1:-1])&(c[j:]<o[j:])&(c[j:]<c[j-1:-1])&(c[j-1:-1]<c[:-j])
  cand=base[:-j]&contig[j][:-j]&cond&(~done[:-j]);idx=np.flatnonzero(cand)
  if len(idx):out[idx+j]=True;done[idx]=True
 return out

def _refractory(mask,r):
 if not r:return mask
 out=np.zeros(len(mask),bool);last=-10**18
 for i in np.flatnonzero(mask):
  if int(i)-last>r:out[i]=True;last=int(i)
 return out

def mask(prep,pair,timing,threshold,fam,n):
 p=pair_params(pair);o,h,l,c=prep['o'],prep['h'],prep['l'],prep['c']
 sk=(p['shock_measure'],int(p['atr_period']),p['atr_smoothing'],timing,float(threshold))
 if sk not in prep['shock_cache']:
  a=_signal_atr(prep,p['atr_period'],p['atr_smoothing']);den=a if timing==TIM[0] else np.r_[np.nan,a[:-1]];num=prep['numerators'][p['shock_measure']]
  ratio=np.divide(num,den,out=np.full(len(c),np.nan),where=np.isfinite(num)&np.isfinite(den)&(den>0))
  prep['shock_cache'][sk]=(ratio>=threshold)&(prep['weekday']<5)
 sh=prep['shock_cache'][sk]
 if fam=='SHOCK_BAR_BODY_DIRECTION_ONLY':b=(c>o)&sh;s=(c<o)&sh
 else:b0,s0=prep['bases'][(fam,n)];b=b0&sh;s=s0&sh
 if p['close_location_filter'] is not None:
  x,y=prep['loc'][p['close_location_filter']];b&=x;s&=y
 if p['wick_filter'] is not None:
  x,y=prep['wick'][p['wick_filter']];b&=x;s&=y
 if p['volatility_regime_context'] is not None:
  q=prep['vol_ctx'][(p['volatility_regime_context'],p['volatility_lookback'])];b&=q;s&=q
 if p['spread_context'] is not None:
  q=prep['spread_ctx'][(p['spread_context'],p['spread_lookback'])];b&=q;s&=q
 if p['tick_intensity_context'] is not None:
  q=prep['tick_ctx'][(p['tick_intensity_context'],p['tick_intensity_lookback'])];b&=q;s&=q
 if p['post_shock_confirmation'] is not None:
  b=_confirm(b,prep,p['post_shock_confirmation'],p['confirmation_window_bars'],1);s=_confirm(s,prep,p['post_shock_confirmation'],p['confirmation_window_bars'],-1)
 if p['day_of_week'] is not None:
  di=DOW.index(p['day_of_week']);b&=prep['weekday']==di;s&=prep['weekday']==di
 if p['event_refractory_bars']:
  b=_refractory(b,p['event_refractory_bars']);s=_refractory(s,p['event_refractory_bars'])
 return b,s
