from __future__ import annotations
import numpy as np
TIM=('CURRENT_BAR_INCLUDED','LAGGED_ONE_BAR_PRE_SHOCK')
TH=(1.0,1.25,1.5,1.75,2.0,2.5,3.0,3.5,4.0)
NS=(1,2,3,4,5,8)
FAMS=('CURRENT_CLOSE_EXCEEDS_ALL_PRIOR_N_CLOSES','STRICT_MONOTONIC_N_CLOSE_SEQUENCE','CURRENT_CLOSE_BREAKS_PRIOR_N_BAR_EXTREME')
VARIANTS=(('NEXT_BAR_DIRECTIONAL_CLOSE',1),('NEXT_BAR_DIRECTIONAL_CLOSE',2),('NEXT_BAR_DIRECTIONAL_CLOSE',3),('NEXT_BAR_BREAK_SHOCK_EXTREME',1),('NEXT_BAR_BREAK_SHOCK_EXTREME',2),('NEXT_BAR_BREAK_SHOCK_EXTREME',3),('TWO_BAR_CONTINUATION',2),('TWO_BAR_CONTINUATION',3))

def bars(mb,o,h,l,c,tf):
 step=tf*60000;b=(mb//step)*step;st=np.r_[0,np.flatnonzero(b[1:]!=b[:-1])+1];en=np.r_[st[1:],len(b)]
 return b[st].astype(np.int64),o[st],np.maximum.reduceat(h,st),np.minimum.reduceat(l,st),c[en-1]

def atr_sma(h,l,c,p=14):
 H=h.astype(float);L=l.astype(float);C=c.astype(float);pc=np.r_[np.nan,C[:-1]];tr=np.fmax(H-L,np.fmax(np.abs(H-pc),np.abs(L-pc)));cs=np.cumsum(np.nan_to_num(tr));out=np.full(len(C),np.nan);out[p-1:]=(cs[p-1:]-np.r_[0.0,cs[:-p]])/float(p);return out

def prepare(bucket,o,h,l,c):
 nbar=len(c);bases={}
 for n in NS:
  cw=np.lib.stride_tricks.sliding_window_view(c,n+1);hw=np.lib.stride_tricks.sliding_window_view(h,n+1);lw=np.lib.stride_tricks.sliding_window_view(l,n+1)
  b=np.zeros(nbar,bool);s=np.zeros(nbar,bool);b[n:]=cw[:,-1]>cw[:,:-1].max(1);s[n:]=cw[:,-1]<cw[:,:-1].min(1);bases[(FAMS[0],n)]=(b,s)
  d=np.diff(cw,axis=1);b=np.zeros(nbar,bool);s=np.zeros(nbar,bool);b[n:]=np.all(d>0,1);s[n:]=np.all(d<0,1);bases[(FAMS[1],n)]=(b,s)
  b=np.zeros(nbar,bool);s=np.zeros(nbar,bool);b[n:]=cw[:,-1]>hw[:,:-1].max(1);s[n:]=cw[:,-1]<lw[:,:-1].min(1);bases[(FAMS[2],n)]=(b,s)
 weekday=((bucket//86400000+3)%7)<5;numer=(h-l).astype(float);a=atr_sma(h,l,c,14);shocks={}
 for timing in TIM:
  den=a if timing==TIM[0] else np.r_[np.nan,a[:-1]];ratio=np.divide(numer,den,out=np.full(nbar,np.nan),where=np.isfinite(den)&(den>0))
  for t in TH:shocks[(timing,t)]=(ratio>=t)&weekday
 step=int(bucket[1]-bucket[0]) if nbar>1 else 0;one=np.zeros(nbar,bool);one[:-1]=(bucket[1:]-bucket[:-1])==step;contig={1:one.copy()}
 c2=np.zeros(nbar,bool);c2[:-2]=one[:-2]&one[1:-1];contig[2]=c2
 c3=np.zeros(nbar,bool);c3[:-3]=one[:-3]&one[1:-2]&one[2:-1];contig[3]=c3
 return {'bases':bases,'shocks':shocks,'atr14':a,'contig':contig}

def _confirm(base,bucket,o,h,l,c,kind,w,side,contig):
 n=len(base);out=np.zeros(n,bool);done=np.zeros(n,bool)
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

def mask(prep,o,h,l,c,kind,w,timing,t,fam,n):
 sh=prep['shocks'][(timing,t)]
 if fam=='SHOCK_BAR_BODY_DIRECTION_ONLY':b=(c>o)&sh;s=(c<o)&sh
 else:
  bb,ss=prep['bases'][(fam,n)];b=bb&sh;s=ss&sh
 dummy=np.empty(0,dtype=np.int64)
 return _confirm(b,dummy,o,h,l,c,kind,w,1,prep['contig']),_confirm(s,dummy,o,h,l,c,kind,w,-1,prep['contig'])
