#!/usr/bin/env python3
"""G30 DEV-only signal identity parity for one NQX TF/feature side.

Independent path:
- raw PACKED17 bars are rebuilt by a chunked streaming reducer;
- shock tests reproduce the frozen IEEE-754 ratio semantics from an independently computed rolling TR sum;
- persistence predicates use shifted-array/rolling-difference logic.

The frozen replacement candidate is used only as the comparison implementation.
No economic outcomes, PnL, holdout, or MT5 are accessed.
"""
from __future__ import annotations
import argparse, gc, hashlib, importlib.util, json
from pathlib import Path
import numpy as np

DT=np.dtype([('ts','<i8'),('bid','<i4'),('ask','<i4'),('flags','u1')])
INPUT_SHA='451843c567d23a53fc7ee5c5cffbcb020112bf91e3b0ee87c5b219b1461aeedf'
CANDIDATE_SHA='5f45d5267694ed31140b7ba2a9d8913c86eda7797cd1725d0267ee09f4a060e2'
THRESHOLDS=[(1,1),(5,4),(3,2),(7,4),(2,1),(5,2),(3,1),(7,2),(4,1)]
THRESHOLD_LABELS=['1','1.25','1.5','1.75','2','2.5','3','3.5','4']
NS=[1,2,3,4,5,8]
TIMINGS=['CURRENT_BAR_INCLUDED','LAGGED_ONE_BAR_PRE_SHOCK']
FAMILIES=['CLOSE_EXCEEDS_PRIOR_N_CLOSES','STRICT_MONOTONIC_N_CLOSE_SEQUENCE','CLOSE_BREAKS_PRIOR_N_BAR_EXTREME']

def sha_file(p:Path)->str:
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8<<20),b''): h.update(b)
 return h.hexdigest()

def digest_arrays(arrs)->str:
 h=hashlib.sha256()
 for a in arrs:
  z=np.ascontiguousarray(a)
  h.update(str(z.dtype).encode('ascii')+b'\0')
  h.update(np.int64(z.size).tobytes())
  h.update(z.tobytes())
 return h.hexdigest()

def row_digests(rows):
 seq=hashlib.sha256(); unique=[]; seen=set(); raw=[]
 for key,buy,sell in rows:
  enc=np.zeros(len(buy),np.int8); enc[buy]=1; enc[sell]=-1
  d=hashlib.sha256(enc.tobytes()).hexdigest(); raw.append((key,d))
  seq.update(key.encode('utf-8')+b'\0'+bytes.fromhex(d))
  if d not in seen: seen.add(d); unique.append(d)
 us=hashlib.sha256(('\n'.join(sorted(unique))+'\n').encode('ascii')).hexdigest()
 return seq.hexdigest(),us,len(unique),raw

def load_candidate(path:Path):
 if sha_file(path)!=CANDIDATE_SHA: raise SystemExit('candidate source SHA mismatch')
 spec=importlib.util.spec_from_file_location('g30_candidate',path)
 m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def independent_bars(mm,step_ms:int,side:str,chunk=2_000_000):
 blocks=[[],[],[],[],[]]; pending=None
 n=len(mm)
 for s in range(0,n,chunk):
  x=mm[s:min(n,s+chunk)]; valid=x['ask']>=x['bid']
  if not np.any(valid): continue
  ts=x['ts'][valid]
  if side=='BID': val=x['bid'][valid].astype(np.int64)*2
  elif side=='MID': val=x['bid'][valid].astype(np.int64)+x['ask'][valid].astype(np.int64)
  else: raise ValueError(side)
  buck=(ts//step_ms)*step_ms
  starts=np.r_[0,np.flatnonzero(buck[1:]!=buck[:-1])+1]; ends=np.r_[starts[1:],len(buck)]
  bb=buck[starts].astype(np.int64); oo=val[starts]; hh=np.maximum.reduceat(val,starts); ll=np.minimum.reduceat(val,starts); cc=val[ends-1]
  i0=0
  if pending is not None:
   if int(bb[0])==pending[0]:
    pending=(pending[0],pending[1],max(pending[2],int(hh[0])),min(pending[3],int(ll[0])),int(cc[0])); i0=1
    if i0==len(bb):
     continue
    for j,v in enumerate(pending): blocks[j].append(np.asarray([v],dtype=np.int64))
    pending=None
   else:
    for j,v in enumerate(pending): blocks[j].append(np.asarray([v],dtype=np.int64))
    pending=None
  remain=len(bb)-i0
  if remain<=0: continue
  if remain>1:
   sl=slice(i0,len(bb)-1)
   for j,a in enumerate((bb,oo,hh,ll,cc)): blocks[j].append(np.asarray(a[sl],dtype=np.int64))
  k=len(bb)-1; pending=(int(bb[k]),int(oo[k]),int(hh[k]),int(ll[k]),int(cc[k]))
 if pending is not None:
  for j,v in enumerate(pending): blocks[j].append(np.asarray([v],dtype=np.int64))
 return tuple(np.concatenate(b) if b else np.empty(0,np.int64) for b in blocks)

def rolling_sum_int(x,n):
 cs=np.cumsum(x,dtype=np.int64); out=np.empty(len(x)-n+1,np.int64); out[0]=cs[n-1]
 if len(out)>1: out[1:]=cs[n:]-cs[:-n]
 return out

def independent_rows(bucket,opn,high,low,close):
 L=len(close); prior=np.r_[close[0],close[:-1]]
 tr=np.maximum(high-low,np.maximum(np.abs(high-prior),np.abs(low-prior))).astype(np.int64); tr[0]=high[0]-low[0]
 atr=np.full(L,np.nan,np.float64); atr[13:]=rolling_sum_int(tr,14).astype(np.float64)/14.0
 weekday=((bucket//86_400_000+3)%7)<5
 bases={}
 for n in NS:
  pc=np.vstack([close[n-k:L-k] for k in range(1,n+1)])
  ph=np.vstack([high[n-k:L-k] for k in range(1,n+1)])
  pl=np.vstack([low[n-k:L-k] for k in range(1,n+1)])
  b=np.zeros(L,bool); s=np.zeros(L,bool); b[n:]=close[n:]>pc.max(axis=0); s[n:]=close[n:]<pc.min(axis=0); bases[(FAMILIES[0],n)]=(b,s)
  d=np.diff(close); pos=(d>0).astype(np.int8); neg=(d<0).astype(np.int8)
  b=np.zeros(L,bool); s=np.zeros(L,bool); b[n:]=rolling_sum_int(pos,n)==n; s[n:]=rolling_sum_int(neg,n)==n; bases[(FAMILIES[1],n)]=(b,s)
  b=np.zeros(L,bool); s=np.zeros(L,bool); b[n:]=close[n:]>ph.max(axis=0); s[n:]=close[n:]<pl.min(axis=0); bases[(FAMILIES[2],n)]=(b,s)
 rows=[]
 rng=(high-low).astype(np.float64)
 threshold_values=[1.0,1.25,1.5,1.75,2.0,2.5,3.0,3.5,4.0]
 for ti,timing in enumerate(TIMINGS):
  den=atr if ti==0 else np.r_[np.nan,atr[:-1]]
  ratio=np.divide(rng,den,out=np.full(L,np.nan,np.float64),where=np.isfinite(den)&(den>0))
  for threshold,label in zip(threshold_values,THRESHOLD_LABELS):
   shock=(ratio>=threshold)&weekday
   for fam in FAMILIES:
    for n in NS:
     b,s=bases[(fam,n)]; rows.append((f'{timing}|{label}|{fam}|{n}',b&shock,s&shock))
   rows.append((f'{timing}|{label}|SHOCK_BAR_BODY_DIRECTION_ONLY|1',(close>opn)&shock,(close<opn)&shock))
 return rows

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--src',type=Path,required=True); ap.add_argument('--candidate',type=Path,required=True); ap.add_argument('--tf-minutes',type=int,required=True); ap.add_argument('--feature-side',choices=['BID','MID'],required=True); ap.add_argument('--out',type=Path,required=True); a=ap.parse_args()
 if sha_file(a.src)!=INPUT_SHA: raise SystemExit('input SHA mismatch')
 m=load_candidate(a.candidate); mm=np.memmap(a.src,dtype=DT,mode='r'); step=a.tf_minutes*60_000
 cb=m.make_feature_bars(mm,step,a.feature_side); cbar=digest_arrays(cb); _,crows=m.signal_masks(*cb); craw,cuniq,cuc,_=row_digests(crows); ccount=len(crows)
 del crows,cb; gc.collect()
 ib=independent_bars(mm,step,a.feature_side); ibar=digest_arrays(ib); irows=independent_rows(*ib); iraw,iuniq,iuc,_=row_digests(irows); icount=len(irows)
 obj={'schema':'QROS_G30_SIGNAL_IDENTITY_INDEPENDENT_PARITY_v3','scope':'DEV_2018_2019_SIGNAL_ONLY_NO_PNL_NO_HOLDOUT','input_sha256':INPUT_SHA,'candidate_source_sha256':CANDIDATE_SHA,'tf_minutes':a.tf_minutes,'feature_side':a.feature_side,'bars':len(ib[0]),'bar_digest_candidate':cbar,'bar_digest_independent':ibar,'bar_exact':cbar==ibar,'raw_identities_candidate':ccount,'raw_identities_independent':icount,'raw_identity_sequence_sha256_candidate':craw,'raw_identity_sequence_sha256_independent':iraw,'raw_identity_exact':craw==iraw,'unique_masks_candidate':cuc,'unique_masks_independent':iuc,'unique_mask_set_sha256_candidate':cuniq,'unique_mask_set_sha256_independent':iuniq,'unique_mask_set_exact':cuniq==iuniq,'status':'PASS' if cbar==ibar and craw==iraw and cuniq==iuniq else 'FAIL','holdout_opened':False,'pnl_read':False}
 a.out.write_text(json.dumps(obj,separators=(',',':')),encoding='utf-8'); print(json.dumps(obj,sort_keys=True))
if __name__=='__main__': main()
