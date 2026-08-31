import numpy as np, hashlib, json, time
from pathlib import Path
from numba import njit
SRC=Path('/mnt/data/NQX_DEV_PACKED17_2018_2019_v1.bin'); PART=Path('/mnt/data/g30_m30_indep3_parts')
REF=Path('/mnt/data/G30_NQX_M30_BID_V5_FAST_SENTINEL_v1.json'); OUT=Path('/mnt/data/G30_NQX_M30_BID_V5_INDEP3_v1.json')
DT=np.dtype([('ts','<i8'),('bid','<i4'),('ask','<i4'),('flags','u1')]); STEP=1800000
THR=[1,1.25,1.5,1.75,2,2.5,3,3.5,4]; NS=[1,2,3,4,5,8]; TIM=['CURRENT_BAR_INCLUDED','LAGGED_ONE_BAR_PRE_SHOCK']; FAMS=['CLOSE_EXCEEDS_PRIOR_N_CLOSES','STRICT_MONOTONIC_N_CLOSE_SEQUENCE','CLOSE_BREAKS_PRIOR_N_BAR_EXTREME']
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load_minutes():
 rows=[]
 for k in range(16):
  z=np.load(PART/f'part_{k:02d}.npz')
  for i in range(len(z['mb'])): rows.append((int(z['mb'][i]),int(z['bh'][i]),int(z['bl'][i]),int(z['ah'][i]),int(z['al'][i]),int(z['first'][i]),int(z['last'][i])))
 rows.sort(key=lambda x:(x[0],x[5])); out=[]
 for r in rows:
  if out and out[-1][0]==r[0]:
   q=out[-1]; out[-1]=(q[0],max(q[1],r[1]),min(q[2],r[2]),max(q[3],r[3]),min(q[4],r[4]),min(q[5],r[5]),max(q[6],r[6]))
  else: out.append(r)
 return np.asarray(out,dtype=np.int64)
def bars():
 mm=np.memmap(SRC,dtype=DT,mode='r'); ok=mm['ask']>=mm['bid']; ids=np.flatnonzero(ok); ts=mm['ts'][ids]; v=mm['bid'][ids].astype(np.int64); b=(ts//STEP)*STEP
 st=np.r_[0,np.flatnonzero(b[1:]!=b[:-1])+1]; en=np.r_[st[1:],len(b)]
 return mm,b[st].astype(np.int64),v[st],np.maximum.reduceat(v,st),np.minimum.reduceat(v,st),v[en-1]
def atr14(h,l,c):
 h=h.astype(float);l=l.astype(float);c=c.astype(float);pc=np.r_[np.nan,c[:-1]];tr=np.fmax(h-l,np.fmax(np.abs(h-pc),np.abs(l-pc)));cs=np.cumsum(np.nan_to_num(tr));a=np.full(len(c),np.nan);a[13:]=(cs[13:]-np.r_[0.,cs[:-14]])/14.;return a
def masks(bucket,o,h,l,c):
 a=atr14(h,l,c);w=((bucket//86400000+3)%7)<5;res=[]
 for ti,timing in enumerate(TIM):
  den=a if ti==0 else np.r_[np.nan,a[:-1]]; ratio=np.divide(h-l,den,out=np.full(len(c),np.nan),where=np.isfinite(den)&(den>0))
  for th in THR:
   shock=(ratio>=th)&w
   for fam in FAMS:
    for n in NS:
     buy=np.zeros(len(c),bool);sell=np.zeros(len(c),bool)
     if fam==FAMS[0]:
      for i in range(n,len(c)): z=c[i-n:i];buy[i]=c[i]>z.max();sell[i]=c[i]<z.min()
     elif fam==FAMS[1]:
      for i in range(n,len(c)): z=c[i-n:i+1];buy[i]=np.all(z[1:]>z[:-1]);sell[i]=np.all(z[1:]<z[:-1])
     else:
      for i in range(n,len(c)): buy[i]=c[i]>h[i-n:i].max();sell[i]=c[i]<l[i-n:i].min()
     buy &= shock;sell &= shock;res.append((f'{timing}|{th:g}|{fam}|{n}',buy,sell))
   res.append((f'{timing}|{th:g}|SHOCK_BAR_BODY_DIRECTION_ONLY|1',(c>o)&shock,(c<o)&shock))
 return a,res
@njit
def lb(a,x):
 lo=0;hi=len(a)
 while lo<hi:
  m=(lo+hi)//2
  if a[m]<x:lo=m+1
  else:hi=m
 return lo
@njit
def outcomes(ts,bid,ask,bucket,atr,mb,bh,bl,ah,al,first,last,side):
 n=len(bucket);et=np.full(n,-1,np.int64);xt=np.full(n,-1,np.int64);rr=np.zeros(n,np.float64)
 for bi in range(n):
  if not np.isfinite(atr[bi]) or atr[bi]<=0:continue
  close=bucket[bi]+STEP; deadline=min(close+20*STEP,((close//86400000)+1)*86400000); mi=lb(mb,close)
  if mi>=len(mb) or mb[mi]>=deadline:continue
  ei=first[mi]
  while ei<=last[mi] and (ts[ei]<close or ask[ei]<=bid[ei]):ei+=1
  if ei>last[mi] or ts[ei]>=deadline:continue
  e=ask[ei] if side==1 else bid[ei];dist=3.*atr[bi];sl=e-dist if side==1 else e+dist;tp=e+1.5*dist if side==1 else e-1.5*dist;et[bi]=ts[ei]
  mend=lb(mb,deadline);hitm=-1
  for mj in range(mi,mend):
   if side==1:
    if bl[mj]<=sl or bh[mj]>=tp: hitm=mj;break
   else:
    if ah[mj]>=sl or al[mj]<=tp: hitm=mj;break
  hit=False
  if hitm>=0:
   j0=max(first[hitm],ei);j1=last[hitm]+1
   for j in range(j0,j1):
    if ts[j]>=deadline:break
    if ask[j]<=bid[j]:continue
    if side==1:
     if bid[j]<=sl:rr[bi]=-1.;xt[bi]=ts[j];hit=True;break
     if bid[j]>=tp:rr[bi]=1.5;xt[bi]=ts[j];hit=True;break
    else:
     if ask[j]>=sl:rr[bi]=-1.;xt[bi]=ts[j];hit=True;break
     if ask[j]<=tp:rr[bi]=1.5;xt[bi]=ts[j];hit=True;break
  if not hit:
   if mend<=mi:et[bi]=-1;continue
   j=last[mend-1]
   while j>=first[mend-1] and (ts[j]>=deadline or ask[j]<=bid[j]):j-=1
   if j<ei:et[bi]=-1;continue
   xt[bi]=ts[j];rr[bi]=(bid[j]-e)/dist if side==1 else (e-ask[j])/dist
 return et,xt,rr
@njit
def sel(mask,et,xt):
 ids=np.flatnonzero(mask);o=np.empty(len(ids),np.int64);k=0;prev=-1
 for q in ids:
  if et[q]<0 or et[q]<=prev:continue
  o[k]=q;k+=1;prev=xt[q]
 return o[:k]
def main():
 t=time.time();M=load_minutes(); mm,bucket,o,h,l,c=bars(); atr,ms=masks(bucket,o,h,l,c); ts=mm['ts'];bid=mm['bid'];ask=mm['ask'];mb,bh,bl,ah,al,first,last=[M[:,i] for i in range(7)]
 eb,xb,rb=outcomes(ts,bid,ask,bucket,atr,mb,bh,bl,ah,al,first,last,1);es,xs,rs=outcomes(ts,bid,ask,bucket,atr,mb,bh,bl,ah,al,first,last,-1)
 seen=set();uniq=[]
 for key,bm,sm in ms:
  z=np.zeros(len(bucket),np.int8);z[bm]=1;z[sm]=-1;sh=hashlib.sha256(z.tobytes()).hexdigest()
  if sh not in seen:seen.add(sh);uniq.append((key,bm,sm,sh))
 rows=[]
 for key,bm,sm,sh in uniq:
  for sd,mask,et,xt,r in [('BUY',bm,eb,xb,rb),('SELL',sm,es,xs,rs)]:
   ii=sel(mask,et,xt);hh=hashlib.sha256();vals=r[ii]
   for q in ii:hh.update(np.int64(et[q]).tobytes());hh.update(np.int64(xt[q]).tobytes());hh.update(np.float64(r[q]).tobytes())
   rows.append({'id':key,'signal_sha256':sh,'side':sd,'n':int(len(ii)),'net_r':float(vals.sum()),'ledger_sha256':hh.hexdigest()})
 obj={'schema':'QROS_G30_NQX_M30_BID_V5_INDEP3_V1','scope':'DEV_2018_2019_ONLY_NO_HOLDOUT','bars':len(bucket),'raw_identities':len(ms),'unique_masks':len(uniq),'records':rows,'input_sha256':'451843c567d23a53fc7ee5c5cffbcb020112bf91e3b0ee87c5b219b1461aeedf','minute_part_hashes':[sha(PART/f'part_{k:02d}.npz') for k in range(16)],'holdout_opened':False};OUT.write_text(json.dumps(obj,separators=(',',':')))
 ref=json.loads(REF.read_text());A={(x['signal_sha256'],x['side']):x for x in rows};R={(x['signal_sha256'],x['side']):x for x in ref['records']};m=[k for k in set(A)|set(R) if k not in A or k not in R or A[k]['ledger_sha256']!=R[k]['ledger_sha256']]
 s={'bars':len(bucket),'raw_identities':len(ms),'unique_masks':len(uniq),'side_records':len(rows),'total_trades':sum(x['n'] for x in rows),'net_r_sum':sum(x['net_r'] for x in rows),'ref_total_trades':sum(x['n'] for x in ref['records']),'ref_net_r_sum':sum(x['net_r'] for x in ref['records']),'same_keyset':set(A)==set(R),'ledger_hash_mismatches':len(m),'exec_minutes':len(M),'runner_sha256':sha(__file__),'output_sha256':sha(OUT),'seconds':time.time()-t};Path(str(OUT)+'.summary.json').write_text(json.dumps(s,indent=2));print(json.dumps(s,indent=2))
main()
