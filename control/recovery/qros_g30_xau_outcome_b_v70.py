#!/usr/bin/env python3
"""Independent execution path B correction for XAU G30 DEV.
Checks the executable entry tick itself for an immediate SL/TP condition.
This matches the frozen rule: entry at first executable quote, then SL-first at the first actually available price.
"""
import numpy as np
from numba import njit

@njit
def lb(a,x):
 lo=0;hi=len(a)
 while lo<hi:
  m=(lo+hi)//2
  if a[m]<x:lo=m+1
  else:hi=m
 return lo

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
  et[bi]=ts[j];eiout[bi]=j;dist[bi]=d;hit=False
  while j<len(ts) and ts[j]<deadline:
   if ask[j]>bid[j]:
    if side==1:
     if bid[j]<=stop:
      xt[bi]=ts[j];xiout[bi]=j;rr[bi]=(bid[j]-entry)/d;hit=True;break
     if bid[j]>=take:
      xt[bi]=ts[j];xiout[bi]=j;rr[bi]=(bid[j]-entry)/d;hit=True;break
    else:
     if ask[j]>=stop:
      xt[bi]=ts[j];xiout[bi]=j;rr[bi]=(entry-ask[j])/d;hit=True;break
     if ask[j]<=take:
      xt[bi]=ts[j];xiout[bi]=j;rr[bi]=(entry-ask[j])/d;hit=True;break
   j+=1
  if not hit:
   k=lb(ts,deadline)-1
   while k>=ei and ask[k]<=bid[k]:k-=1
   if k<ei:et[bi]=-1;eiout[bi]=-1;continue
   xt[bi]=ts[k];xiout[bi]=k;rr[bi]=(bid[k]-entry)/d if side==1 else (entry-ask[k])/d
 return et,xt,eiout,xiout,dist,rr
