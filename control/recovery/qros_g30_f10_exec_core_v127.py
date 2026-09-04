from __future__ import annotations
import numpy as np, hashlib, math
from numba import njit
DT=np.dtype([('ts','<i8'),('bid','<i4'),('ask','<i4'),('flags','u1')]);CUT_2019=np.int64(1546300800000);STOP_ATR_MULT=3.;ATR_STORAGE_DIVISOR=2.;TAKE_R_MULT=1.5;TIME_STOP_BARS=20
@njit(cache=True)
def lower(a,x):
 lo=0;hi=len(a)
 while lo<hi:
  m=(lo+hi)//2
  if a[m]<x:lo=m+1
  else:hi=m
 return lo
@njit(cache=True)
def outcome_primary(ts,bid,ask,bucket,atr14,step,eb,ebh,ebl,eah,eal,first,last,active,side):
 n=len(bucket);et=np.full(n,-1,np.int64);xt=np.full(n,-1,np.int64);eiout=np.full(n,-1,np.int64);xiout=np.full(n,-1,np.int64);dist=np.zeros(n,np.float64);rr=np.zeros(n,np.float64)
 for bi in range(n):
  if not active[bi] or not np.isfinite(atr14[bi]) or atr14[bi]<=0:continue
  close=bucket[bi]+step;deadline=min(close+TIME_STOP_BARS*step,((close//86400000)+1)*86400000);mi=lower(eb,close)
  if mi>=len(eb) or eb[mi]>=deadline:continue
  ei=first[mi]
  while ei<=last[mi] and (ts[ei]<close or ask[ei]<=bid[ei]):ei+=1
  if ei>last[mi] or ts[ei]>=deadline:continue
  entry=ask[ei] if side==1 else bid[ei];d=STOP_ATR_MULT*atr14[bi]/ATR_STORAGE_DIVISOR;stop=entry-d if side==1 else entry+d;take=entry+TAKE_R_MULT*d if side==1 else entry-TAKE_R_MULT*d;et[bi]=ts[ei];eiout[bi]=ei;dist[bi]=d;mend=lower(eb,deadline);hit=False
  for mj in range(mi,mend):
   possible=(ebl[mj]<=stop or ebh[mj]>=take) if side==1 else (eah[mj]>=stop or eal[mj]<=take)
   if not possible:continue
   j0=max(first[mj],ei)
   for j in range(j0,last[mj]+1):
    if ts[j]>=deadline:break
    if ask[j]<=bid[j]:continue
    if side==1:
     if bid[j]<=stop:xt[bi]=ts[j];xiout[bi]=j;rr[bi]=(bid[j]-entry)/d;hit=True;break
     if bid[j]>=take:xt[bi]=ts[j];xiout[bi]=j;rr[bi]=(bid[j]-entry)/d;hit=True;break
    else:
     if ask[j]>=stop:xt[bi]=ts[j];xiout[bi]=j;rr[bi]=(entry-ask[j])/d;hit=True;break
     if ask[j]<=take:xt[bi]=ts[j];xiout[bi]=j;rr[bi]=(entry-ask[j])/d;hit=True;break
   if hit:break
  if not hit:
   if mend<=mi:et[bi]=-1;eiout[bi]=-1;continue
   j=last[mend-1]
   while j>=ei and (ts[j]>=deadline or ask[j]<=bid[j]):j-=1
   if j<ei:et[bi]=-1;eiout[bi]=-1;continue
   xt[bi]=ts[j];xiout[bi]=j;rr[bi]=(bid[j]-entry)/d if side==1 else (entry-ask[j])/d
 return et,xt,eiout,xiout,dist,rr
@njit(cache=True)
def outcome_independent(ts,bid,ask,bucket,atr14,step,eb,ebh,ebl,eah,eal,first,last,active,side):
 n=len(bucket);et=np.full(n,-1,np.int64);xt=np.full(n,-1,np.int64);eiout=np.full(n,-1,np.int64);xiout=np.full(n,-1,np.int64);dist=np.zeros(n,np.float64);rr=np.zeros(n,np.float64);bi=0
 while bi<n:
  if active[bi] and np.isfinite(atr14[bi]) and atr14[bi]>0:
   close=bucket[bi]+step;deadline=close+TIME_STOP_BARS*step;day=((close//86400000)+1)*86400000
   if deadline>day:deadline=day
   mi=lower(eb,close)
   if mi<len(eb) and eb[mi]<deadline:
    q=first[mi]
    while q<=last[mi] and (ts[q]<close or ask[q]<=bid[q]):q+=1
    if q<=last[mi] and ts[q]<deadline:
     ei=q;entry=ask[q] if side==1 else bid[q];d=(STOP_ATR_MULT*atr14[bi])/ATR_STORAGE_DIVISOR;stop=entry-d if side==1 else entry+d;take=entry+TAKE_R_MULT*d if side==1 else entry-TAKE_R_MULT*d;et[bi]=ts[q];eiout[bi]=q;dist[bi]=d;mend=lower(eb,deadline);done=False;m=mi
     while m<mend and not done:
      may=(ebl[m]<=stop or ebh[m]>=take) if side==1 else (eah[m]>=stop or eal[m]<=take)
      if may:
       j=max(first[m],ei)
       while j<=last[m] and ts[j]<deadline:
        if ask[j]>bid[j]:
         if side==1:
          if bid[j]<=stop:xt[bi]=ts[j];xiout[bi]=j;rr[bi]=(bid[j]-entry)/d;done=True;break
          elif bid[j]>=take:xt[bi]=ts[j];xiout[bi]=j;rr[bi]=(bid[j]-entry)/d;done=True;break
         else:
          if ask[j]>=stop:xt[bi]=ts[j];xiout[bi]=j;rr[bi]=(entry-ask[j])/d;done=True;break
          elif ask[j]<=take:xt[bi]=ts[j];xiout[bi]=j;rr[bi]=(entry-ask[j])/d;done=True;break
        j+=1
      m+=1
     if not done:
      if mend>mi:
       j=last[mend-1]
       while j>=ei and (ts[j]>=deadline or ask[j]<=bid[j]):j-=1
       if j>=ei:xt[bi]=ts[j];xiout[bi]=j;rr[bi]=(bid[j]-entry)/d if side==1 else (entry-ask[j])/d
       else:et[bi]=-1;eiout[bi]=-1
      else:et[bi]=-1;eiout[bi]=-1
  bi+=1
 return et,xt,eiout,xiout,dist,rr
@njit(cache=True)
def select_a(ids,et,xt):
 out=np.empty(len(ids),np.int64);k=0;prev=np.int64(-1)
 for i in range(len(ids)):
  q=ids[i]
  if et[q]<0 or et[q]<=prev:continue
  out[k]=q;k+=1;prev=xt[q]
 return out[:k]
@njit(cache=True)
def select_b(ids,et,xt):
 out=np.empty(len(ids),np.int64);k=0;prev=np.int64(-1);i=0
 while i<len(ids):
  q=ids[i]
  if et[q]>=0 and et[q]>prev:out[k]=q;k+=1;prev=xt[q]
  i+=1
 return out[:k]
def mask_digest(b,s):
 enc=np.zeros(len(b),np.int8);enc[b]=1;enc[s]=-1;return hashlib.sha256(enc.tobytes()).hexdigest()
def ledger_sha(ch,et,xt,rr):
 rec=np.empty(len(ch),dtype=np.dtype([('et','<i8'),('xt','<i8'),('rr','<f8')]));rec['et']=et[ch];rec['xt']=xt[ch];rec['rr']=rr[ch];return hashlib.sha256(rec.tobytes()).hexdigest()
def pf(x):
 pos=float(x[x>0].sum());neg=float(-x[x<0].sum());return (float('inf') if pos>0 else 0.) if neg==0 else pos/neg
