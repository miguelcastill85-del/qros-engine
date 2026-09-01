#!/usr/bin/env python3
"""Independent DEV-only G30 M1 MID V5 economic ledger engine.

This runner is a parity implementation, not a replacement of historical hashes.
It verifies and imports the independently frozen signal engine v3, but does not
call the durable replacement candidate's outcome or selection functions.
No holdout, MT5, or parameter selection is performed.
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, json
from pathlib import Path
import numpy as np
from numba import njit

DT=np.dtype([('ts','<i8'),('bid','<i4'),('ask','<i4'),('flags','u1')])
INPUT_SHA='451843c567d23a53fc7ee5c5cffbcb020112bf91e3b0ee87c5b219b1461aeedf'
SIGNAL_RUNNER_SHA='65933b2de83051919820776ff3ae23ce5b751f2842fcaf4d6657f9e85f0dd1b8'
EXPECTED_SIGNAL_SEQUENCE_SHA='693d74e4f5493bedbeadebaa207cf4f28c3039d34bcc081bd7476fe5a5038b00'
EXPECTED_UNIQUE_SET_SHA='17bad4e5bb05c05396ee1d796956b34896b29348bc06f05110488015519a491a'
STEP=60_000


def sha_file(p:Path)->str:
 h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(8<<20),b''): h.update(block)
 return h.hexdigest()


def load_signal_module(path:Path):
 if sha_file(path)!=SIGNAL_RUNNER_SHA: raise SystemExit('independent signal runner SHA mismatch')
 spec=importlib.util.spec_from_file_location('g30_signal_independent_v3',path)
 mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod


def load_minutes(parts:Path):
 files=sorted(parts.glob('part_*.npz'))
 if len(files)!=16: raise SystemExit(f'expected 16 executable-minute parts, got {len(files)}')
 rows=[]
 for p in files:
  with np.load(p) as z:
   rows.extend(zip(z['mb'],z['bh'],z['bl'],z['ah'],z['al'],z['first'],z['last']))
 rows.sort(key=lambda r:(int(r[0]),int(r[5])))
 merged=[]
 for raw in rows:
  r=tuple(map(int,raw))
  if merged and merged[-1][0]==r[0]:
   q=merged[-1]
   merged[-1]=(q[0],max(q[1],r[1]),min(q[2],r[2]),max(q[3],r[3]),min(q[4],r[4]),min(q[5],r[5]),max(q[6],r[6]))
  else: merged.append(r)
 return np.asarray(merged,dtype=np.int64)


def unique_masks(rows):
 seen=set(); out=[]; seq=hashlib.sha256()
 for key,buy,sell in rows:
  enc=np.zeros(len(buy),np.int8); enc[buy]=1; enc[sell]=-1
  digest=hashlib.sha256(enc.tobytes()).hexdigest()
  seq.update(key.encode('utf-8')+b'\0'+bytes.fromhex(digest))
  if digest not in seen:
   seen.add(digest); out.append((key,buy,sell,digest))
 unique_set=hashlib.sha256(('\n'.join(sorted(seen))+'\n').encode('ascii')).hexdigest()
 return out,seq.hexdigest(),unique_set


@njit
def lower_bound(a,x):
 lo=0; hi=len(a)
 while lo<hi:
  mid=(lo+hi)//2
  if a[mid]<x: lo=mid+1
  else: hi=mid
 return lo


@njit
def independent_outcomes(ts,bid,ask,bucket,atr_x2,mb,bh,bl,ah,al,first,last,side):
 n=len(bucket); et=np.full(n,-1,np.int64); xt=np.full(n,-1,np.int64); rv=np.zeros(n,np.float64)
 for bi in range(n):
  if not np.isfinite(atr_x2[bi]) or atr_x2[bi]<=0: continue
  signal_close=bucket[bi]+STEP
  deadline=signal_close+20*STEP
  day_end=((signal_close//86_400_000)+1)*86_400_000
  if day_end<deadline: deadline=day_end
  mi=lower_bound(mb,signal_close)
  if mi>=len(mb) or mb[mi]>=deadline: continue
  j=first[mi]
  while j<=last[mi] and (ts[j]<signal_close or ask[j]<=bid[j]): j+=1
  if j>last[mi] or ts[j]>=deadline: continue
  entry_idx=j; entry=ask[j] if side==1 else bid[j]
  distance=3.0*atr_x2[bi]/2.0
  stop=entry-distance if side==1 else entry+distance
  take=entry+1.5*distance if side==1 else entry-1.5*distance
  et[bi]=ts[entry_idx]
  mend=lower_bound(mb,deadline); exited=False
  for mk in range(mi,mend):
   possible=False
   if side==1:
    possible=(bl[mk]<=stop or bh[mk]>=take)
   else:
    possible=(ah[mk]>=stop or al[mk]<=take)
   if not possible: continue
   q0=first[mk]
   if q0<entry_idx: q0=entry_idx
   q1=last[mk]+1
   for q in range(q0,q1):
    if ts[q]>=deadline: break
    if ask[q]<=bid[q]: continue
    if side==1:
     if bid[q]<=stop: rv[bi]=-1.0; xt[bi]=ts[q]; exited=True; break
     if bid[q]>=take: rv[bi]=1.5; xt[bi]=ts[q]; exited=True; break
    else:
     if ask[q]>=stop: rv[bi]=-1.0; xt[bi]=ts[q]; exited=True; break
     if ask[q]<=take: rv[bi]=1.5; xt[bi]=ts[q]; exited=True; break
   if exited: break
  if exited: continue
  mk=mend-1
  found=-1
  while mk>=mi and found<0:
   q=last[mk]
   while q>=first[mk]:
    if q<entry_idx: break
    if ts[q]<deadline and ask[q]>bid[q]: found=q; break
    q-=1
   mk-=1
  if found<entry_idx:
   et[bi]=-1; continue
  xt[bi]=ts[found]
  if side==1: rv[bi]=(bid[found]-entry)/distance
  else: rv[bi]=(entry-ask[found])/distance
 return et,xt,rv


@njit
def independent_select(mask,et,xt):
 ids=np.flatnonzero(mask); out=np.empty(len(ids),np.int64); k=0; prev=-1
 for q in ids:
  if et[q]<0: continue
  if et[q]<=prev: continue
  out[k]=q; k+=1; prev=xt[q]
 return out[:k]


def ledgers(unique,buy_out,sell_out):
 records=[]
 for key,buy,sell,sig_sha in unique:
  for side,mask,outcome in (('BUY',buy,buy_out),('SELL',sell,sell_out)):
   et,xt,rv=outcome; chosen=independent_select(mask,et,xt); h=hashlib.sha256()
   for q in chosen:
    h.update(np.asarray(et[q],dtype='<i8').tobytes())
    h.update(np.asarray(xt[q],dtype='<i8').tobytes())
    h.update(np.asarray(rv[q],dtype='<f8').tobytes())
   records.append({'id':key,'signal_sha256':sig_sha,'side':side,'n':int(len(chosen)),'net_r':float(rv[chosen].sum()),'ledger_sha256':h.hexdigest()})
 return records


def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--src',type=Path,required=True); ap.add_argument('--minutes-dir',type=Path,required=True); ap.add_argument('--signal-runner',type=Path,required=True); ap.add_argument('--out',type=Path,required=True); a=ap.parse_args()
 if sha_file(a.src)!=INPUT_SHA: raise SystemExit('canonical NQX DEV SHA mismatch')
 sig=load_signal_module(a.signal_runner); mm=np.memmap(a.src,dtype=DT,mode='r')
 bucket,opn,high,low,close=sig.independent_bars(mm,STEP,'MID')
 rows=sig.independent_rows(bucket,opn,high,low,close); unique,seq_sha,set_sha=unique_masks(rows)
 if len(bucket)!=673097 or len(rows)!=342 or len(unique)!=324: raise SystemExit('M1 MID signal count mismatch')
 if seq_sha!=EXPECTED_SIGNAL_SEQUENCE_SHA or set_sha!=EXPECTED_UNIQUE_SET_SHA: raise SystemExit('M1 MID signal identity mismatch')
 # Recompute ATR x2 independently from the exact MID bars using the frozen IEEE-754 recipe.
 prior=np.r_[np.nan,close[:-1].astype(np.float64)]; hf=high.astype(np.float64); lf=low.astype(np.float64); cf=close.astype(np.float64)
 tr=np.fmax(hf-lf,np.fmax(np.abs(hf-prior),np.abs(lf-prior))); cs=np.cumsum(np.nan_to_num(tr)); atr=np.full(len(close),np.nan); atr[13:]=(cs[13:]-np.r_[0.0,cs[:-14]])/14.0
 minute=load_minutes(a.minutes_dir); mb,bh,bl,ah,al,first,last=[minute[:,i] for i in range(7)]
 buy=independent_outcomes(mm['ts'],mm['bid'],mm['ask'],bucket,atr,mb,bh,bl,ah,al,first,last,1)
 sell=independent_outcomes(mm['ts'],mm['bid'],mm['ask'],bucket,atr,mb,bh,bl,ah,al,first,last,-1)
 records=ledgers(unique,buy,sell)
 obj={'schema':'QROS_G30_M1_MID_INDEPENDENT_ECONOMIC_ENGINE_OUTPUT_v1','scope':'NQX_DEV_2018_2019_ONLY_NO_HOLDOUT','input_sha256':INPUT_SHA,'signal_runner_sha256':SIGNAL_RUNNER_SHA,'bars':len(bucket),'raw_identities':len(rows),'unique_masks':len(unique),'signal_identity_sequence_sha256':seq_sha,'unique_mask_set_sha256':set_sha,'side_ledgers':len(records),'records':records,'holdout_opened':False}
 a.out.write_text(json.dumps(obj,separators=(',',':')),encoding='utf-8')
 print(json.dumps({'bars':len(bucket),'raw_identities':len(rows),'unique_masks':len(unique),'side_ledgers':len(records),'output_sha256':sha_file(a.out)},sort_keys=True))

if __name__=='__main__': main()
