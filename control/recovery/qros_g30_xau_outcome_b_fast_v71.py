#!/usr/bin/env python3
"""Efficient independent execution path B for XAU G30 DEV.
Uses the verified executable-minute index only as a search accelerator; all fills are confirmed on raw ticks.
SL is checked before TP, including the executable entry tick itself.
"""
import numpy as np
from numba import njit

@njit
def lower(a,x):
 lo=0; hi=len(a)
 while lo<hi:
  m=lo+(hi-lo)//2
  if a[m] < x: lo=m+1
  else: hi=m
 return lo

@njit
def outcome_B_fast(ts,bid,ask,bucket,atr,step,eb,ebh,ebl,eah,eal,first,last,active,side):
 n=len(bucket);et=np.full(n,-1,np.int64);xt=np.full(n,-1,np.int64);eiout=np.full(n,-1,np.int64);xiout=np.full(n,-1,np.int64);dist=np.zeros(n,np.float64);rr=np.zeros(n,np.float64)
 for bi in range(n):
  if not active[bi] or not np.isfinite(atr[bi]) or atr[bi]<=0: continue
  close=bucket[bi]+step; day=((close//86400000)+1)*86400000; deadline=close+20*step
  if deadline>day:deadline=day
  m=lower(eb,close)
  if m>=len(eb) or eb[m]>=deadline: continue
  j=first[m]
  while j<=last[m] and (ts[j]<close or ask[j]<=bid[j]): j+=1
  if j>last[m] or ts[j]>=deadline: continue
  ei=j;entry=ask[j] if side==1 else bid[j];d=3.0*atr[bi]/2.0;stop=entry-d if side==1 else entry+d;take=entry+1.5*d if side==1 else entry-1.5*d
  et[bi]=ts[j];eiout[bi]=j;dist[bi]=d; mend=lower(eb,deadline);done=False
  while m<mend:
   may=False
   if side==1:
    if ebl[m]<=stop: may=True
    elif ebh[m]>=take: may=True
   else:
    if eah[m]>=stop: may=True
    elif eal[m]<=take: may=True
   if may:
    q=first[m]
    if q<ei:q=ei
    while q<=last[m] and ts[q]<deadline:
     if ask[q]>bid[q]:
      if side==1:
       if bid[q]<=stop:
        xt[bi]=ts[q];xiout[bi]=q;rr[bi]=(bid[q]-entry)/d;done=True;break
       if bid[q]>=take:
        xt[bi]=ts[q];xiout[bi]=q;rr[bi]=(bid[q]-entry)/d;done=True;break
      else:
       if ask[q]>=stop:
        xt[bi]=ts[q];xiout[bi]=q;rr[bi]=(entry-ask[q])/d;done=True;break
       if ask[q]<=take:
        xt[bi]=ts[q];xiout[bi]=q;rr[bi]=(entry-ask[q])/d;done=True;break
     q+=1
    if done:break
   m+=1
  if not done:
   if mend<=0:et[bi]=-1;eiout[bi]=-1;continue
   q=last[mend-1]
   while q>=ei and (ts[q]>=deadline or ask[q]<=bid[q]):q-=1
   if q<ei:et[bi]=-1;eiout[bi]=-1;continue
   xt[bi]=ts[q];xiout[bi]=q;rr[bi]=(bid[q]-entry)/d if side==1 else (entry-ask[q])/d
 return et,xt,eiout,xiout,dist,rr
