from __future__ import annotations
import numpy as np
from numba import njit

TIM=('CURRENT_BAR_INCLUDED','LAGGED_ONE_BAR_PRE_SHOCK')
TH=(1.0,1.25,1.5,1.75,2.0,2.5,3.0,3.5,4.0)
NS=(1,2,3,4,5,8)
F0='CURRENT_CLOSE_EXCEEDS_ALL_PRIOR_N_CLOSES';F1='STRICT_MONOTONIC_N_CLOSE_SEQUENCE';F2='CURRENT_CLOSE_BREAKS_PRIOR_N_BAR_EXTREME'
DOWMAP={'MON':0,'TUE':1,'WED':2,'THU':3,'FRI':4}
BASE={'shock_measure':'HIGH_LOW_RANGE_OVER_ATR','atr_period':14,'atr_smoothing':'SMA_TR','close_location_filter':None,'wick_filter':None,'post_shock_confirmation':None,'confirmation_window_bars':0,'volatility_regime_context':None,'volatility_lookback':0,'spread_context':None,'spread_lookback':0,'tick_intensity_context':None,'tick_intensity_lookback':0,'event_refractory_bars':0,'day_of_week':None}

def bars(mb,o,h,l,c,tf):
 step=int(tf)*60000;bb=[];oo=[];hh=[];ll=[];cc=[];cur=None
 for i in range(len(mb)):
  q=int(mb[i]//step*step)
  if q!=cur:bb.append(q);oo.append(int(o[i]));hh.append(int(h[i]));ll.append(int(l[i]));cc.append(int(c[i]));cur=q
  else:hh[-1]=max(hh[-1],int(h[i]));ll[-1]=min(ll[-1],int(l[i]));cc[-1]=int(c[i])
 return tuple(np.asarray(x,np.int64) for x in (bb,oo,hh,ll,cc))

def _tr(h,l,c):
 n=len(c);z=np.empty(n,np.float64)
 if not n:return z
 z[0]=float(h[0]-l[0])
 for i in range(1,n):z[i]=max(float(h[i]-l[i]),abs(float(h[i]-c[i-1])),abs(float(l[i]-c[i-1])))
 return z

def atr(h,l,c,p=14,smoothing='SMA_TR'):
 tr=_tr(h,l,c);n=len(tr);out=np.full(n,np.nan);p=int(p)
 if n<p:return out
 if smoothing=='SMA_TR':
  s=float(np.sum(tr[:p]));out[p-1]=s/p
  for i in range(p,n):s+=tr[i]-tr[i-p];out[i]=s/p
  return out
 seed=float(np.sum(tr[:p])/p);out[p-1]=seed;v=seed
 if smoothing=='WILDER_RMA_TR':
  for i in range(p,n):v=(v*(p-1)+tr[i])/p;out[i]=v
 elif smoothing=='EMA_TR':
  a=2.0/(p+1.0)
  for i in range(p,n):v=a*tr[i]+(1-a)*v;out[i]=v
 else:raise ValueError(smoothing)
 return out

def persistence_bases(h,l,c):
 nbar=len(c);out={}
 for n in NS:
  b=np.zeros(nbar,bool);s=np.zeros(nbar,bool)
  for i in range(n,nbar):
   cv=c[i];b[i]=all(cv>c[j] for j in range(i-n,i));s[i]=all(cv<c[j] for j in range(i-n,i))
  out[(F0,n)]=(b,s)
  if n>1:
   b=np.zeros(nbar,bool);s=np.zeros(nbar,bool)
   for i in range(n,nbar):b[i]=all(c[j]>c[j-1] for j in range(i-n+1,i+1));s[i]=all(c[j]<c[j-1] for j in range(i-n+1,i+1))
   out[(F1,n)]=(b,s)
  b=np.zeros(nbar,bool);s=np.zeros(nbar,bool)
  for i in range(n,nbar):b[i]=c[i]>max(h[i-n:i]);s[i]=c[i]<min(l[i-n:i])
  out[(F2,n)]=(b,s)
 return out

def persistence_specs():
 for fam in (F0,F1,F2):
  for n in NS:
   if fam==F1 and n==1:continue
   yield fam,n
 yield 'SHOCK_BAR_BODY_DIRECTION_ONLY',1

@njit(cache=True)
def _tree_add(tree,base,pos,d):
 i=base+pos;tree[i]+=d;i//=2
 while i:tree[i]=tree[2*i]+tree[2*i+1];i//=2
@njit(cache=True)
def _tree_kth(tree,base,k):
 i=1
 while i<base:
  if tree[2*i]>=k:i=2*i
  else:k-=tree[2*i];i=2*i+1
 return i-base
@njit(cache=True)
def _rolling_ctx(vals,valid_mode,L,mode,cap):
 n=len(vals);rows=4 if mode==0 else (3 if mode==1 else 2);out=np.zeros((rows,n),np.bool_);valid=np.zeros(n,np.bool_)
 for i in range(n):valid[i]=(vals[i]>=0 if valid_mode==0 else (vals[i]>0 if valid_mode==1 else True))
 u=np.unique(vals[valid]);base=1
 while base<len(u):base*=2
 tree=np.zeros(2*base,np.int32);cnt=0
 r20=(L+4)//5;r50=(L+1)//2;r75=(3*L+3)//4;r80=(4*L+4)//5;r90=(9*L+9)//10
 for t in range(n):
  ai=t-2
  if ai>=0 and valid[ai]:q=np.searchsorted(u,vals[ai]);_tree_add(tree,base,q,1);cnt+=1
  ri=t-L-2
  if ri>=0 and valid[ri]:q=np.searchsorted(u,vals[ri]);_tree_add(tree,base,q,-1);cnt-=1
  if t>=1 and valid[t-1]:
   ref=vals[t-1]
   if mode==1:out[2,t]=ref<=cap
   if cnt==L:
    if mode==0:
     q20=u[_tree_kth(tree,base,r20)];q50=u[_tree_kth(tree,base,r50)];q80=u[_tree_kth(tree,base,r80)];out[0,t]=ref>q50;out[1,t]=ref>=q20 and ref<=q80;out[2,t]=ref>=q80;out[3,t]=ref<=q20
    elif mode==1:
     q75=u[_tree_kth(tree,base,r75)];q90=u[_tree_kth(tree,base,r90)];out[0,t]=ref<=q75;out[1,t]=ref<=q90
    else:
     q50=u[_tree_kth(tree,base,r50)];q80=u[_tree_kth(tree,base,r80)];out[0,t]=ref>q50;out[1,t]=ref>=q80
 return out

def _trsum14(h,l,c):
 tr=_tr(h,l,c).astype(np.int64);out=np.full(len(c),-1,np.int64)
 if len(c)>=14:
  s=int(np.sum(tr[:14]));out[13]=s
  for i in range(14,len(c)):s+=int(tr[i])-int(tr[i-14]);out[i]=s
 return out

def prepare(bucket,o,h,l,c,spread=None,tick_count=None,asset='NQX'):
 bucket=np.asarray(bucket,np.int64);o=np.asarray(o,np.int64);h=np.asarray(h,np.int64);l=np.asarray(l,np.int64);c=np.asarray(c,np.int64);n=len(c)
 p={'bucket':bucket,'o':o,'h':h,'l':l,'c':c,'bases':persistence_bases(h,l,c),'day':np.asarray([int((int(x)//86400000+3)%7) for x in bucket],np.int8),'atr_cache':{},'shock_cache':{}}
 H=h.astype(float);L=l.astype(float);C=c.astype(float);O=o.astype(float)
 tr=_tr(h,l,c);cc=np.full(n,np.nan);cc[1:]=np.abs(C[1:]-C[:-1])
 p['nums']={'HIGH_LOW_RANGE_OVER_ATR':H-L,'TRUE_RANGE_OVER_ATR':tr,'ABS_CLOSE_TO_CLOSE_RETURN_OVER_ATR':cc,'BODY_OVER_ATR':np.abs(C-O)}
 R=h-l;valid=R>0;X=c-l;p['loc']={}
 for name,num,den in [('TOP_BOTTOM_50PCT',1,2),('TOP_BOTTOM_33PCT',2,3),('TOP_BOTTOM_25PCT',3,4)]:p['loc'][name]=(valid&((c-l)*den>=num*R),valid&((c-l)*den<=(den-num)*R))
 # overwrite with exact frozen integer definitions to avoid generic formula ambiguity
 p['loc']['TOP_BOTTOM_50PCT']=(valid&(2*X>=R),valid&(2*X<=R));p['loc']['TOP_BOTTOM_33PCT']=(valid&(3*X>=2*R),valid&(3*X<=R));p['loc']['TOP_BOTTOM_25PCT']=(valid&(4*X>=3*R),valid&(4*X<=R))
 lw=np.minimum(o,c)-l;uw=h-np.maximum(o,c);p['wick']={'MAX_OPPOSING_WICK_50PCT_RANGE':(valid&(2*lw<=R),valid&(2*uw<=R)),'MAX_OPPOSING_WICK_33PCT_RANGE':(valid&(3*lw<=R),valid&(3*uw<=R)),'MAX_OPPOSING_WICK_20PCT_RANGE':(valid&(5*lw<=R),valid&(5*uw<=R))}
 p['contig_step']=int(bucket[1]-bucket[0]) if n>1 else 0
 vs=_trsum14(h,l,c);p['vol_ctx']={}
 for Lb in (20,50,100,200,500):
  z=_rolling_ctx(vs,0,Lb,0,0)
  for i,name in enumerate(('ATR_ABOVE_MEDIAN','ATR_PERCENTILE_20_80','ATR_TOP_QUINTILE','PRE_SHOCK_COMPRESSION')):p['vol_ctx'][(name,Lb)]=z[i]
 p['spread_ctx']={}
 if spread is not None:
  sp=np.asarray(spread,np.int64);cap=10 if asset=='NQX' else 15
  for Lb in (50,100,500,2000):
   z=_rolling_ctx(sp,1,Lb,1,cap);p['spread_ctx'][('SPREAD_BELOW_ROLLING_P75',Lb)]=z[0];p['spread_ctx'][('SPREAD_BELOW_ROLLING_P90',Lb)]=z[1]
   if Lb==50:p['spread_ctx'][('SPREAD_POINTS_BELOW_FROZEN_CAP','CANONICAL_NOT_APPLICABLE')]=z[2]
 p['tick_ctx']={}
 if tick_count is not None:
  tc=np.asarray(tick_count,np.int64)
  for Lb in (20,50,100,500):
   z=_rolling_ctx(tc,2,Lb,2,0);p['tick_ctx'][('TICK_COUNT_ABOVE_MEDIAN',Lb)]=z[0];p['tick_ctx'][('TICK_COUNT_TOP_QUINTILE',Lb)]=z[1]
 p['management_atr14']=atr(h,l,c,14,'SMA_TR');return p

def pair_params(pair):q=dict(BASE);q.update(pair['a']);q.update(pair['b']);return q

def _sigatr(p,period,smooth):
 k=(int(period),smooth)
 if k not in p['atr_cache']:p['atr_cache'][k]=atr(p['h'],p['l'],p['c'],period,smooth)
 return p['atr_cache'][k]

def _contiguous(p,i,j):
 step=p['contig_step'];b=p['bucket']
 for k in range(i,i+j):
  if b[k+1]-b[k]!=step:return False
 return True

def _confirm(base,p,kind,w,side):
 n=len(base);out=np.zeros(n,bool);o,h,l,c=p['o'],p['h'],p['l'],p['c'];step=p['contig_step']
 if n<2:return out
 bad=np.zeros(n,np.int64);bad[1:]=(p['bucket'][1:]-p['bucket'][:-1]!=step).astype(np.int64);pref=np.cumsum(bad)
 done=np.zeros(n,bool);js=range(1,w+1) if kind!='TWO_BAR_CONTINUATION' else range(2,w+1)
 for j in js:
  if n<=j:continue
  contiguous=(pref[j:]-pref[:-j])==0
  if kind=='NEXT_BAR_DIRECTIONAL_CLOSE':cond=(c[j:]>o[j:]) if side==1 else (c[j:]<o[j:])
  elif kind=='NEXT_BAR_BREAK_SHOCK_EXTREME':cond=(h[j:]>h[:-j]) if side==1 else (l[j:]<l[:-j])
  else:
   if side==1:cond=(c[j-1:-1]>o[j-1:-1])&(c[j:]>o[j:])&(c[j:]>c[j-1:-1])&(c[j-1:-1]>c[:-j])
   else:cond=(c[j-1:-1]<o[j-1:-1])&(c[j:]<o[j:])&(c[j:]<c[j-1:-1])&(c[j-1:-1]<c[:-j])
  cand=base[:-j]&contiguous&cond&(~done[:-j]);idx=np.flatnonzero(cand)
  if len(idx):out[idx+j]=True;done[idx]=True
 return out

def _refract(mask,r):
 if not r:return mask.copy()
 out=np.zeros(len(mask),bool);idx=np.flatnonzero(mask);k=0;last=-10**18
 while k<len(idx):
  i=int(idx[k])
  if i-last>r:out[i]=True;last=i
  k+=1
 return out

def mask(p,pair,timing,threshold,fam,n):
 q=pair_params(pair);o,h,l,c=p['o'],p['h'],p['l'],p['c'];sk=(q['shock_measure'],int(q['atr_period']),q['atr_smoothing'],timing,float(threshold))
 if sk not in p['shock_cache']:
  a=_sigatr(p,q['atr_period'],q['atr_smoothing']);den=np.empty(len(c),float)
  if timing==TIM[0]:den[:]=a
  else:den[0]=np.nan;den[1:]=a[:-1]
  num=p['nums'][q['shock_measure']];ratio=np.divide(num,den,out=np.full(len(c),np.nan),where=np.isfinite(num)&np.isfinite(den)&(den>0))
  p['shock_cache'][sk]=(ratio>=threshold)&(p['day']<5)
 sh=p['shock_cache'][sk]
 if fam=='SHOCK_BAR_BODY_DIRECTION_ONLY':b=(c>o)&sh;s=(c<o)&sh
 else:b0,s0=p['bases'][(fam,n)];b=b0&sh;s=s0&sh
 if q['close_location_filter'] is not None:x,y=p['loc'][q['close_location_filter']];b&=x;s&=y
 if q['wick_filter'] is not None:x,y=p['wick'][q['wick_filter']];b&=x;s&=y
 if q['volatility_regime_context'] is not None:x=p['vol_ctx'][(q['volatility_regime_context'],q['volatility_lookback'])];b&=x;s&=x
 if q['spread_context'] is not None:x=p['spread_ctx'][(q['spread_context'],q['spread_lookback'])];b&=x;s&=x
 if q['tick_intensity_context'] is not None:x=p['tick_ctx'][(q['tick_intensity_context'],q['tick_intensity_lookback'])];b&=x;s&=x
 if q['post_shock_confirmation'] is not None:b=_confirm(b,p,q['post_shock_confirmation'],q['confirmation_window_bars'],1);s=_confirm(s,p,q['post_shock_confirmation'],q['confirmation_window_bars'],-1)
 if q['day_of_week'] is not None:
  d=DOWMAP[q['day_of_week']];b&=p['day']==d;s&=p['day']==d
 if q['event_refractory_bars']:b=_refract(b,q['event_refractory_bars']);s=_refract(s,q['event_refractory_bars'])
 return b,s
