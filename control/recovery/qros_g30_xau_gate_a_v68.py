#!/usr/bin/env python3
"""QROS G30 XAU Gate-A DEV runner, corrected first-available-price semantics.

Scope: XAUUSD Darwinex 2018-2019 development only.
Two independent paths are implemented in this file:
 A) vectorized bar/signal construction + executable-minute envelope execution.
 B) loop/rolling signal construction + direct raw-tick execution.
They must agree trade-by-trade before any Gate-A result is accepted.
No 2020+ strategy PnL is accessed.
"""
from __future__ import annotations
import argparse, hashlib, json, math
from pathlib import Path
import numpy as np
from numba import njit

DT=np.dtype([('ts','<i8'),('bid','<i4'),('ask','<i4'),('flags','u1')])
CANONICAL_XAU_DEV_SHA='3ddb3c95acb9284196c5b6db84385271702800209ee33b1b1a2e1bd59cc9ff53'
CACHE_SHA='f5d847a51ffbbddd29dc4089aa65c04ebe4df01336b91af35223609551923e62'
TH=[1.,1.25,1.5,1.75,2.,2.5,3.,3.5,4.]
NS=[1,2,3,4,5,8]
TIM=['CURRENT_BAR_INCLUDED','LAGGED_ONE_BAR_PRE_SHOCK']
FAMS=['CLOSE_EXCEEDS_PRIOR_N_CLOSES','STRICT_MONOTONIC_N_CLOSE_SEQUENCE','CLOSE_BREAKS_PRIOR_N_BAR_EXTREME']
CUT_2019=1546300800000

def sha_file(p:Path):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8<<20),b''): h.update(b)
 return h.hexdigest()

def digest_arrays(arrs):
 h=hashlib.sha256()
 for a in arrs:
  z=np.ascontiguousarray(a); h.update(str(z.dtype).encode()+b'\0'); h.update(np.int64(z.size).tobytes()); h.update(z.tobytes())
 return h.hexdigest()

def bars_A(mb,o,h,l,c,tf):
 step=tf*60000; b=(mb//step)*step; st=np.r_[0,np.flatnonzero(b[1:]!=b[:-1])+1]; en=np.r_[st[1:],len(b)]
 return b[st].astype(np.int64),o[st],np.maximum.reduceat(h,st),np.minimum.reduceat(l,st),c[en-1]

def bars_B(mb,o,h,l,c,tf):
 step=tf*60000
 if tf==1: return tuple(np.asarray(x,dtype=np.int64).copy() for x in (mb,o,h,l,c))
 bb=[];oo=[];hh=[];ll=[];cc=[]; cur=-1
 for i in range(len(mb)):
  q=int(mb[i]//step*step)
  if q!=cur:
   bb.append(q); oo.append(int(o[i])); hh.append(int(h[i])); ll.append(int(l[i])); cc.append(int(c[i])); cur=q
  else:
   if h[i]>hh[-1]: hh[-1]=int(h[i])
   if l[i]<ll[-1]: ll[-1]=int(l[i])
   cc[-1]=int(c[i])
 return tuple(np.asarray(x,np.int64) for x in (bb,oo,hh,ll,cc))

def atr_A(h,l,c):
 H=h.astype(float);L=l.astype(float);C=c.astype(float); pc=np.r_[np.nan,C[:-1]]
 tr=np.fmax(H-L,np.fmax(np.abs(H-pc),np.abs(L-pc))); cs=np.cumsum(np.nan_to_num(tr)); out=np.full(len(C),np.nan)
 out[13:]=(cs[13:]-np.r_[0.,cs[:-14]])/14.; return out

def rolling_sum_int(x,n):
 cs=np.cumsum(x,dtype=np.int64); out=np.empty(len(x)-n+1,np.int64); out[0]=cs[n-1]
 if len(out)>1: out[1:]=cs[n:]-cs[:-n]
 return out

def atr_B(h,l,c):
 H=h.astype(np.int64);L=l.astype(np.int64);C=c.astype(np.int64); prior=np.r_[C[0],C[:-1]]
 tr=np.maximum(H-L,np.maximum(np.abs(H-prior),np.abs(L-prior))).astype(np.int64); tr[0]=H[0]-L[0]
 out=np.full(len(C),np.nan); out[13:]=rolling_sum_int(tr,14).astype(float)/14.; return out

def rows_A(bucket,o,h,l,c):
 L=len(c); atr=atr_A(h,l,c); weekday=((bucket//86400000+3)%7)<5; bases={}
 for n in NS:
  cw=np.lib.stride_tricks.sliding_window_view(c,n+1); hw=np.lib.stride_tricks.sliding_window_view(h,n+1); lw=np.lib.stride_tricks.sliding_window_view(l,n+1)
  b=np.zeros(L,bool);s=np.zeros(L,bool); b[n:]=cw[:,-1]>cw[:,:-1].max(1); s[n:]=cw[:,-1]<cw[:,:-1].min(1); bases[(FAMS[0],n)]=(b,s)
  b=np.zeros(L,bool);s=np.zeros(L,bool); d=np.diff(cw,axis=1); b[n:]=np.all(d>0,1);s[n:]=np.all(d<0,1); bases[(FAMS[1],n)]=(b,s)
  b=np.zeros(L,bool);s=np.zeros(L,bool); b[n:]=cw[:,-1]>hw[:,:-1].max(1);s[n:]=cw[:,-1]<lw[:,:-1].min(1); bases[(FAMS[2],n)]=(b,s)
 rows=[]
 for ti,timing in enumerate(TIM):
  den=atr if ti==0 else np.r_[np.nan,atr[:-1]]; ratio=np.divide(h-l,den,out=np.full(L,np.nan),where=np.isfinite(den)&(den>0))
  for t in TH:
   shock=(ratio>=t)&weekday
   for fam in FAMS:
    for n in NS:
     b,s=bases[(fam,n)]; rows.append((f'{timing}|{t:g}|{fam}|{n}',b&shock,s&shock))
   rows.append((f'{timing}|{t:g}|SHOCK_BAR_BODY_DIRECTION_ONLY|1',(c>o)&shock,(c<o)&shock))
 return atr,rows

def rows_B(bucket,o,h,l,c):
 L=len(c); atr=atr_B(h,l,c); weekday=((bucket//86400000+3)%7)<5; bases={}
 for n in NS:
  pc=np.vstack([c[n-k:L-k] for k in range(1,n+1)]); ph=np.vstack([h[n-k:L-k] for k in range(1,n+1)]); pl=np.vstack([l[n-k:L-k] for k in range(1,n+1)])
  b=np.zeros(L,bool);s=np.zeros(L,bool); b[n:]=c[n:]>pc.max(0);s[n:]=c[n:]<pc.min(0);bases[(FAMS[0],n)]=(b,s)
  d=np.diff(c); pos=(d>0).astype(np.int8);neg=(d<0).astype(np.int8); b=np.zeros(L,bool);s=np.zeros(L,bool);b[n:]=rolling_sum_int(pos,n)==n;s[n:]=rolling_sum_int(neg,n)==n;bases[(FAMS[1],n)]=(b,s)
  b=np.zeros(L,bool);s=np.zeros(L,bool);b[n:]=c[n:]>ph.max(0);s[n:]=c[n:]<pl.min(0);bases[(FAMS[2],n)]=(b,s)
 rows=[]
 for ti,timing in enumerate(TIM):
  den=atr if ti==0 else np.r_[np.nan,atr[:-1]]; ratio=np.divide(h-l,den,out=np.full(L,np.nan),where=np.isfinite(den)&(den>0))
  for t in TH:
   shock=(ratio>=t)&weekday
   for fam in FAMS:
    for n in NS:
     b,s=bases[(fam,n)]; rows.append((f'{timing}|{t:g}|{fam}|{n}',b&shock,s&shock))
   rows.append((f'{timing}|{t:g}|SHOCK_BAR_BODY_DIRECTION_ONLY|1',(c>o)&shock,(c<o)&shock))
 return atr,rows

def row_digest(rows):
 h=hashlib.sha256(); seen=set(); uniq=[]
 for key,b,s in rows:
  enc=np.zeros(len(b),np.int8);enc[b]=1;enc[s]=-1; d=hashlib.sha256(enc.tobytes()).hexdigest(); h.update(key.encode()+b'\0'+bytes.fromhex(d))
  if d not in seen: seen.add(d);uniq.append((key,b,s,d))
 us=hashlib.sha256(('\n'.join(sorted(seen))+'\n').encode()).hexdigest()
 return h.hexdigest(),us,uniq

@njit
def lb(a,x):
 lo=0;hi=len(a)
 while lo<hi:
  m=(lo+hi)//2
  if a[m]<x:lo=m+1
  else:hi=m
 return lo

@njit
def outcome_A(ts,bid,ask,bucket,atr,step,eb,ebh,ebl,eah,eal,first,last,active,side):
 n=len(bucket); et=np.full(n,-1,np.int64);xt=np.full(n,-1,np.int64);eiout=np.full(n,-1,np.int64);xiout=np.full(n,-1,np.int64);dist=np.zeros(n,np.float64);rr=np.zeros(n,np.float64)
 for bi in range(n):
  if not active[bi] or not np.isfinite(atr[bi]) or atr[bi]<=0: continue
  close=bucket[bi]+step; deadline=min(close+20*step,((close//86400000)+1)*86400000); mi=lb(eb,close)
  if mi>=len(eb) or eb[mi]>=deadline: continue
  ei=first[mi]
  while ei<=last[mi] and (ts[ei]<close or ask[ei]<=bid[ei]): ei+=1
  if ei>last[mi] or ts[ei]>=deadline: continue
  entry=ask[ei] if side==1 else bid[ei]; d=3.0*atr[bi]/2.0; stop=entry-d if side==1 else entry+d; take=entry+1.5*d if side==1 else entry-1.5*d
  et[bi]=ts[ei];eiout[bi]=ei;dist[bi]=d; mend=lb(eb,deadline); hit=False
  for mj in range(mi,mend):
   possible=(ebl[mj]<=stop or ebh[mj]>=take) if side==1 else (eah[mj]>=stop or eal[mj]<=take)
   if not possible: continue
   j0=first[mj]
   if j0<ei:j0=ei
   for j in range(j0,last[mj]+1):
    if ts[j]>=deadline:break
    if ask[j]<=bid[j]:continue
    if side==1:
     if bid[j]<=stop or bid[j]>=take:
      xt[bi]=ts[j];xiout[bi]=j;rr[bi]=(bid[j]-entry)/d;hit=True;break
    else:
     if ask[j]>=stop or ask[j]<=take:
      xt[bi]=ts[j];xiout[bi]=j;rr[bi]=(entry-ask[j])/d;hit=True;break
   if hit:break
  if not hit:
   if mend<=mi:et[bi]=-1;eiout[bi]=-1;continue
   j=last[mend-1]
   while j>=0 and (ts[j]>=deadline or ask[j]<=bid[j]):j-=1
   if j<ei:et[bi]=-1;eiout[bi]=-1;continue
   xt[bi]=ts[j];xiout[bi]=j;rr[bi]=(bid[j]-entry)/d if side==1 else (entry-ask[j])/d
 return et,xt,eiout,xiout,dist,rr

@njit
def outcome_B(ts,bid,ask,bucket,atr,step,active,side):
 n=len(bucket);et=np.full(n,-1,np.int64);xt=np.full(n,-1,np.int64);eiout=np.full(n,-1,np.int64);xiout=np.full(n,-1,np.int64);dist=np.zeros(n,np.float64);rr=np.zeros(n,np.float64)
 for bi in range(n):
  if not active[bi] or not np.isfinite(atr[bi]) or atr[bi]<=0:continue
  close=bucket[bi]+step;deadline=close+20*step;day=((close//86400000)+1)*86400000
  if deadline>day:deadline=day
  j=lb(ts,close)
  while j<len(ts) and ts[j]<deadline and ask[j]<=bid[j]:j+=1
  if j>=len(ts) or ts[j]>=deadline:continue
  ei=j;entry=ask[j] if side==1 else bid[j];d=3.0*atr[bi]/2.0;stop=entry-d if side==1 else entry+d;take=entry+1.5*d if side==1 else entry-1.5*d
  et[bi]=ts[j];eiout[bi]=j;dist[bi]=d;hit=False;j+=1
  while j<len(ts) and ts[j]<deadline:
   if ask[j]>bid[j]:
    if side==1:
     if bid[j]<=stop or bid[j]>=take:
      xt[bi]=ts[j];xiout[bi]=j;rr[bi]=(bid[j]-entry)/d;hit=True;break
    else:
     if ask[j]>=stop or ask[j]<=take:
      xt[bi]=ts[j];xiout[bi]=j;rr[bi]=(entry-ask[j])/d;hit=True;break
   j+=1
  if not hit:
   k=lb(ts,deadline)-1
   while k>=ei and ask[k]<=bid[k]:k-=1
   if k<ei:et[bi]=-1;eiout[bi]=-1;continue
   xt[bi]=ts[k];xiout[bi]=k;rr[bi]=(bid[k]-entry)/d if side==1 else (entry-ask[k])/d
 return et,xt,eiout,xiout,dist,rr

@njit
def select_A(mask,et,xt):
 ids=np.flatnonzero(mask);out=np.empty(len(ids),np.int64);k=0;prev=-1
 for q in ids:
  if et[q]<0 or et[q]<=prev:continue
  out[k]=q;k+=1;prev=xt[q]
 return out[:k]

def select_B(mask,et,xt):
 out=[];prev=-1
 for q in np.flatnonzero(mask):
  if int(et[q])<0 or int(et[q])<=prev:continue
  out.append(int(q));prev=int(xt[q])
 return np.asarray(out,np.int64)

def pf(x):
 pos=float(x[x>0].sum());neg=float(-x[x<0].sum())
 if neg==0:return float('inf') if pos>0 else 0.0
 return pos/neg

def ledger_sha(chosen,et,xt,rr):
 h=hashlib.sha256()
 for q in chosen:
  h.update(np.int64(et[q]).tobytes());h.update(np.int64(xt[q]).tobytes());h.update(np.float64(rr[q]).tobytes())
 return h.hexdigest()

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--src',type=Path,required=True);ap.add_argument('--cache',type=Path,required=True);ap.add_argument('--tf',type=int,required=True);ap.add_argument('--feature-side',choices=['BID','MID'],required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 if sha_file(a.src)!=CANONICAL_XAU_DEV_SHA:raise SystemExit('DEV SHA mismatch')
 if sha_file(a.cache)!=CACHE_SHA:raise SystemExit('cache SHA mismatch')
 mm=np.memmap(a.src,dtype=DT,mode='r')
 with np.load(a.cache) as z:
  mb=z['mb']; ks=('bo','bh','bl','bc') if a.feature_side=='BID' else ('mo','mh','ml','mc'); vals=[z[k] for k in ks]
  A=bars_A(mb,*vals,a.tf);B=bars_B(mb,*vals,a.tf)
  if digest_arrays(A)!=digest_arrays(B):raise SystemExit('BAR_PARITY_FAIL')
  atrA,rA=rows_A(*A);atrB,rB=rows_B(*B); rawA,setA,uA=row_digest(rA);rawB,setB,uB=row_digest(rB)
  if rawA!=rawB or setA!=setB or len(uA)!=len(uB):raise SystemExit('SIGNAL_PARITY_FAIL')
  if [x[0] for x in uA]!=[x[0] for x in uB] or [x[3] for x in uA]!=[x[3] for x in uB]:raise SystemExit('DEDUPE_PARITY_FAIL')
  unionB=np.zeros(len(A[0]),bool);unionS=np.zeros(len(A[0]),bool)
  for _,b,s,_ in uA:unionB|=b;unionS|=s
  ex=[z[k] for k in ('eb','ebh','ebl','eah','eal','first','last')]
  step=a.tf*60000
  oaB=outcome_A(mm['ts'],mm['bid'],mm['ask'],A[0],atrA,step,*ex,unionB,1); obB=outcome_B(mm['ts'],mm['bid'],mm['ask'],B[0],atrB,step,unionB,1)
  oaS=outcome_A(mm['ts'],mm['bid'],mm['ask'],A[0],atrA,step,*ex,unionS,-1);obS=outcome_B(mm['ts'],mm['bid'],mm['ask'],B[0],atrB,step,unionS,-1)
  records=[];passers=[]; parity_fail=0
  for idx,(key,bmask,smask,sigsha) in enumerate(uA):
   for side,mask,OA,OB in [('BUY',bmask,oaB,obB),('SELL',smask,oaS,obS)]:
    chA=select_A(mask,OA[0],OA[1]);chB=select_B(mask,OB[0],OB[1])
    same=np.array_equal(chA,chB)
    if same and len(chA):
     for k in range(6):
      if not np.array_equal(OA[k][chA],OB[k][chB]):same=False;break
    if not same:parity_fail+=1;continue
    rr=OA[5][chA].astype(float); ei=OA[2][chA];xi=OA[3][chA];dist=OA[4][chA]
    if len(chA):
     spread=(mm['ask'][ei]-mm['bid'][ei]).astype(float)+(mm['ask'][xi]-mm['bid'][xi]).astype(float)
     extra=np.divide(spread,dist,out=np.zeros(len(spread)),where=dist>0); cons=rr-0.5*extra;sev=rr-extra
     eyear=OA[0][chA]; y18=float(rr[eyear<CUT_2019].sum());y19=float(rr[eyear>=CUT_2019].sum())
    else:
     cons=rr.copy();sev=rr.copy();y18=y19=0.
    rec={'id':key,'signal_sha256':sigsha,'side':side,'n':int(len(chA)),'net_c':float(rr.sum()),'net_k':float(cons.sum()),'net_s':float(sev.sum()),'pf_c':pf(rr),'pf_k':pf(cons),'pf_s':pf(sev),'r2018':y18,'r2019':y19,'ledger_sha256':ledger_sha(chA,OA[0],OA[1],OA[5])}
    passed=rec['n']>=60 and rec['pf_c']>=1.20 and rec['pf_k']>=1.10 and rec['pf_s']>=1.00 and y18>0 and y19>0
    rec['pass']=bool(passed);records.append(rec)
    if passed:passers.append(rec)
  if parity_fail:raise SystemExit(f'TRADE_PARITY_FAIL {parity_fail}')
  shard=('H1' if a.tf==60 else f'M{a.tf}')+'_'+a.feature_side
  obj={'schema':'QROS_G30_XAU_GATE_A_SHARD_V68_v1','scope':'XAU_DEV_2018_2019_ONLY_NO_2020_PLUS_PNL','shard':shard,'bars':int(len(A[0])),'raw_identities':len(rA),'unique_masks':len(uA),'evaluated_configurations':len(records),'bar_digest':digest_arrays(A),'raw_identity_sequence_sha256':rawA,'unique_mask_set_sha256':setA,'union_buy':int(unionB.sum()),'union_sell':int(unionS.sum()),'trade_parity':'PASS_EXACT','parity_failures':0,'gate':{'min_trades':60,'pf_central_min':1.20,'pf_conservative_min':1.10,'pf_severe_min':1.00,'both_dev_years_positive_central':True,'cost_conservative':'central minus 0.5*(entry_spread+exit_spread)/ATR_stop_distance','cost_severe':'central minus 1.0*(entry_spread+exit_spread)/ATR_stop_distance'},'passed':len(passers),'passed_buy':sum(x['side']=='BUY' for x in passers),'passed_sell':sum(x['side']=='SELL' for x in passers),'passers':passers,'all_records':records,'future_pnl_read':False,'status':'PASS'}
  a.out.write_text(json.dumps(obj,separators=(',',':'),allow_nan=False),encoding='utf-8');print(json.dumps({k:obj[k] for k in ['shard','bars','raw_identities','unique_masks','evaluated_configurations','passed','passed_buy','passed_sell','trade_parity']},sort_keys=True))
if __name__=='__main__':main()
