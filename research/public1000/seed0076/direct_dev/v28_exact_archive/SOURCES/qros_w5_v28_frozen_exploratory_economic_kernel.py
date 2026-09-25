#!/usr/bin/env python3
# Source recovery: QROS_SEED0076_DIRECT_M1_W5_STRICT_17258_EVIDENCE_20260923.zip,
# direct_economic_event_cache_v1_1.py, exact unmodified Numba kernels below.
# 19:30 original exposed-DEV exploratory flat; commission and broker calendar not certified.
from __future__ import annotations
import numpy as np
from numba import njit
DAY=86400000;OPEN=61*60000;FLAT=(19*60+30)*60000;CLOSE=(23*60+59)*60000;FRI=(23*60+55)*60000
@njit(cache=True)
def bar_valid_extrema(ts_bid,ts_ask,first,last):
 n=len(first);minb=np.full(n,np.iinfo(np.int32).max,np.int32);maxa=np.full(n,np.iinfo(np.int32).min,np.int32)
 for bi in range(n):
  mb=np.iinfo(np.int32).max;ma=np.iinfo(np.int32).min
  for ix in range(first[bi],last[bi]+1):
   bid=ts_bid[ix];ask=ts_ask[ix]
   if bid>0 and ask>bid:
    if bid<mb:mb=bid
    if ask>ma:ma=ask
  minb[bi]=mb;maxa[bi]=ma
 return minb,maxa

@njit(cache=True)
def precompute_trajectory(ts,bid,ask,bucket,first,last,minb,maxa,raw_idx,stops,bar_idx,side):
 n=len(raw_idx);entry_ix=np.full(n,-1,np.int64);exit_ix=np.full(n,-1,np.int64);entrypx=np.zeros(n,np.int32);exitpx=np.zeros(n,np.int32);risk=np.zeros(n,np.int32);reason=np.zeros(n,np.int8)
 # reason codes: 0 out-of-session; 1 no quote in signal minute; 2 stop geometry; 3 unresolved exit; 4 STOP; 5 FLAT
 for j in range(n):
  si=raw_idx[j];s=stops[j];b=bar_idx[j]
  if si<0 or si>=len(ts):raise RuntimeError('CANDIDATE_OOB')
  day=ts[si]//DAY;tod=ts[si]%DAY;week=(day+3)%7
  if week>4 or tod<OPEN or tod>=FLAT:continue
  bar_end=(ts[si]//60000+1)*60000
  ei=-1
  for k in range(si,last[b]+1):
   if ts[k]>=bar_end:break
   if bid[k]>0 and ask[k]>bid[k]:ei=k;break
  if ei<0:reason[j]=1;continue
  price=ask[ei] if side==1 else bid[ei];r=price-s if side==1 else s-price
  if r<=0 or (side==1 and bid[ei]<=s) or (side==-1 and ask[ei]>=s):reason[j]=2;continue
  entry_ix[j]=ei;entrypx[j]=price;risk[j]=r
  end=(day*DAY)+(FRI if week==4 else CLOSE)
  out=-1;px=0;why=3
  for bi in range(b,len(bucket)):
   if bucket[bi]//DAY!=day or bucket[bi]>=end:break
   start=first[bi];endbar=last[bi]
   if start<ei:start=ei
   if start>endbar:continue
   postflat=bucket[bi]>=day*DAY+FLAT
   # If bar strictly before flat and no executable quote can touch stop, skip entire bar.
   if not postflat and ((side==1 and minb[bi]>s) or (side==-1 and maxa[bi]<s)):continue
   for k in range(start,endbar+1):
    if ts[k]>=end:break
    if bid[k]<=0 or ask[k]<=bid[k]:continue
    mark=bid[k] if side==1 else ask[k]
    if (side==1 and mark<=s) or (side==-1 and mark>=s):out=k;px=mark;why=4;break
    if ts[k]>=day*DAY+FLAT:out=k;px=mark;why=5;break
   if out>=0:break
  exit_ix[j]=out;exitpx[j]=px;reason[j]=why
 return entry_ix,exit_ix,entrypx,exitpx,risk,reason

# Single pure scheduler: timestamps are explicit provenance-bound inputs.
@njit(cache=True)
def schedule_pure(timestamps,tr_raw,ix,ei,xi,ep,xp,risk,reason,stop,side,num_max=3,return_trades=False):
 current=-1;daily=0;active=-1;N=0;rsum=0.;pos=0.;neg=0.;high=0.;dd=0.;rejected=np.zeros(8,np.int64)
 tr=np.empty((len(ix),11),np.float64) if return_trades else np.empty((0,11),np.float64)
 for ci in ix:
  si=tr_raw[ci];state=reason[ci]
  if si<=active:rejected[0]+=1;continue
  if state==0:rejected[1]+=1;continue
  day=timestamps[si]//DAY
  if day!=current:current=day;daily=0
  if daily>=num_max:rejected[2]+=1;continue
  if state==1:rejected[3]+=1;continue
  if state==2:rejected[4]+=1;continue
  if state==3:rejected[5]+=1;break
  if state not in (4,5):raise RuntimeError('BAD_PRECOMPUTED_EVENT_STATE')
  rv=(xp[ci]-ep[ci])/risk[ci] if side==1 else (ep[ci]-xp[ci])/risk[ci]
  rsum+=rv
  if rv>0:pos+=rv
  elif rv<0:neg-=rv
  if rsum>high:high=rsum
  d=high-rsum
  if d>dd:dd=d
  if return_trades:tr[N]=[ci,side,si,ei[ci],xi[ci],ep[ci],stop[ci],xp[ci],rv,1 if state==4 else 2,day]
  N+=1;daily+=1;active=xi[ci]
 return N,rsum,pos,neg,dd,rejected,tr[:N]

