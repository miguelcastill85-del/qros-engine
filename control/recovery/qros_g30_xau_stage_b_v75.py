#!/usr/bin/env python3
"""QROS G30 XAU Stage-B 2020-2021 runner for the 28 representatives frozen in V74.

Scientific scope:
- Signal context may use the canonical 2018-2021 prefix.
- Economic verdict uses entries in [2020-01-01, 2022-01-01) source-clock only.
- No 2022+ bytes are present in the input prefix.
- Two independent bar/signal paths and two independent raw-tick execution paths must match exactly.
- No retuning and no economic selection beyond the prospectively frozen V75 gate.
"""
from __future__ import annotations
import argparse, hashlib, json, math, sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import qros_g30_xau_gate_a_v68 as c
from qros_g30_xau_outcome_b_fast_v71 import outcome_B_fast

PREFIX_SHA='77da8423b07d7d33168d8b713ef691627f0698760461c7349fa5ccc5e49ceaeb'
CACHE_SHA='35abe473cfb9b02c51f525ccd3ef870bff51106005f94236e8197a9f4a2d8bfd'
STAGE_START=np.int64(1577836800000)
STAGE_END=np.int64(1640995200000)
CUT_2021=np.int64(1609459200000)
REPRESENTATIVES=[
'H1_MID:BUY:CURRENT_BAR_INCLUDED|2|STRICT_MONOTONIC_N_CLOSE_SEQUENCE|3',
'H1_BID:BUY:LAGGED_ONE_BAR_PRE_SHOCK|2.5|STRICT_MONOTONIC_N_CLOSE_SEQUENCE|3',
'H1_BID:BUY:LAGGED_ONE_BAR_PRE_SHOCK|2|STRICT_MONOTONIC_N_CLOSE_SEQUENCE|4',
'M10_BID:BUY:LAGGED_ONE_BAR_PRE_SHOCK|3.5|STRICT_MONOTONIC_N_CLOSE_SEQUENCE|2',
'M10_BID:SELL:LAGGED_ONE_BAR_PRE_SHOCK|2.5|STRICT_MONOTONIC_N_CLOSE_SEQUENCE|5',
'M10_MID:SELL:LAGGED_ONE_BAR_PRE_SHOCK|2|STRICT_MONOTONIC_N_CLOSE_SEQUENCE|5',
'M15_BID:BUY:CURRENT_BAR_INCLUDED|2.5|CLOSE_BREAKS_PRIOR_N_BAR_EXTREME|8',
'M15_BID:BUY:CURRENT_BAR_INCLUDED|2.5|STRICT_MONOTONIC_N_CLOSE_SEQUENCE|2',
'M15_BID:BUY:CURRENT_BAR_INCLUDED|2.5|STRICT_MONOTONIC_N_CLOSE_SEQUENCE|3',
'M15_BID:BUY:CURRENT_BAR_INCLUDED|2.5|STRICT_MONOTONIC_N_CLOSE_SEQUENCE|4',
'M15_BID:BUY:CURRENT_BAR_INCLUDED|2|STRICT_MONOTONIC_N_CLOSE_SEQUENCE|5',
'M15_BID:BUY:LAGGED_ONE_BAR_PRE_SHOCK|2.5|STRICT_MONOTONIC_N_CLOSE_SEQUENCE|3',
'M15_BID:BUY:LAGGED_ONE_BAR_PRE_SHOCK|2.5|STRICT_MONOTONIC_N_CLOSE_SEQUENCE|5',
'M15_MID:SELL:LAGGED_ONE_BAR_PRE_SHOCK|2|STRICT_MONOTONIC_N_CLOSE_SEQUENCE|5',
'M30_BID:BUY:CURRENT_BAR_INCLUDED|1.75|STRICT_MONOTONIC_N_CLOSE_SEQUENCE|4',
'M30_BID:BUY:CURRENT_BAR_INCLUDED|2.5|CLOSE_BREAKS_PRIOR_N_BAR_EXTREME|8',
'M30_BID:BUY:CURRENT_BAR_INCLUDED|2.5|STRICT_MONOTONIC_N_CLOSE_SEQUENCE|2',
'M30_BID:BUY:CURRENT_BAR_INCLUDED|2.5|STRICT_MONOTONIC_N_CLOSE_SEQUENCE|3',
'M30_MID:BUY:CURRENT_BAR_INCLUDED|2|STRICT_MONOTONIC_N_CLOSE_SEQUENCE|3',
'M30_BID:BUY:LAGGED_ONE_BAR_PRE_SHOCK|1.75|STRICT_MONOTONIC_N_CLOSE_SEQUENCE|3',
'M30_MID:BUY:LAGGED_ONE_BAR_PRE_SHOCK|2.5|CLOSE_EXCEEDS_PRIOR_N_CLOSES|5',
'M30_BID:BUY:LAGGED_ONE_BAR_PRE_SHOCK|2.5|STRICT_MONOTONIC_N_CLOSE_SEQUENCE|2',
'M30_BID:BUY:LAGGED_ONE_BAR_PRE_SHOCK|2.5|STRICT_MONOTONIC_N_CLOSE_SEQUENCE|3',
'M30_BID:BUY:LAGGED_ONE_BAR_PRE_SHOCK|3.5|CLOSE_BREAKS_PRIOR_N_BAR_EXTREME|8',
'M30_MID:BUY:LAGGED_ONE_BAR_PRE_SHOCK|1.5|STRICT_MONOTONIC_N_CLOSE_SEQUENCE|5',
'M30_MID:BUY:LAGGED_ONE_BAR_PRE_SHOCK|1.75|STRICT_MONOTONIC_N_CLOSE_SEQUENCE|5',
'M30_MID:BUY:LAGGED_ONE_BAR_PRE_SHOCK|4|CLOSE_BREAKS_PRIOR_N_BAR_EXTREME|2',
'M5_MID:BUY:CURRENT_BAR_INCLUDED|1|STRICT_MONOTONIC_N_CLOSE_SEQUENCE|8'
]

def sha_file(p:Path):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return h.hexdigest()

def safe(x):
 if isinstance(x,float) and not math.isfinite(x): return 'INF' if x>0 else ('-INF' if x<0 else 'NAN')
 if isinstance(x,dict):return {k:safe(v) for k,v in x.items()}
 if isinstance(x,list):return [safe(v) for v in x]
 return x

def parse_rep(s):
 shard,side,key=s.split(':',2)
 if '_' not in shard: raise ValueError(s)
 tfname,feature=shard.rsplit('_',1)
 tf=60 if tfname=='H1' else int(tfname[1:])
 return tf,feature,side,key

def reps_for(tf,feature):
 return [(s,side,key) for s in REPRESENTATIVES for tf0,feat0,side,key in [parse_rep(s)] if tf0==tf and feat0==feature]

def ledger_sha(ch,et,xt,rr):
 h=hashlib.sha256()
 for q in ch:
  h.update(np.int64(et[q]).tobytes());h.update(np.int64(xt[q]).tobytes());h.update(np.float64(rr[q]).tobytes())
 return h.hexdigest()

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--src',type=Path,required=True);ap.add_argument('--cache',type=Path,required=True);ap.add_argument('--tf',type=int,required=True);ap.add_argument('--feature-side',choices=['BID','MID'],required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 if sha_file(a.src)!=PREFIX_SHA:raise SystemExit('PREFIX_SHA_MISMATCH')
 if sha_file(a.cache)!=CACHE_SHA:raise SystemExit('CACHE_SHA_MISMATCH')
 reps=reps_for(a.tf,a.feature_side)
 if not reps:raise SystemExit('NO_FROZEN_REPRESENTATIVES_FOR_SHARD')
 mm=np.memmap(a.src,dtype=c.DT,mode='r')
 with np.load(a.cache) as z:
  mb=z['mb'];ks=('bo','bh','bl','bc') if a.feature_side=='BID' else ('mo','mh','ml','mc');vals=[z[k] for k in ks]
  A=c.bars_A(mb,*vals,a.tf);B=c.bars_B(mb,*vals,a.tf)
  if c.digest_arrays(A)!=c.digest_arrays(B):raise SystemExit('BAR_PARITY_FAIL')
  atrA,rowsA=c.rows_A(*A);atrB,rowsB=c.rows_B(*B)
  mapA={k:(b,s) for k,b,s in rowsA};mapB={k:(b,s) for k,b,s in rowsB}
  unionB=np.zeros(len(A[0]),bool);unionS=np.zeros(len(A[0]),bool)
  for stable,side,key in reps:
   if key not in mapA or key not in mapB:raise SystemExit('MISSING_KEY '+key)
   ma=mapA[key][0 if side=='BUY' else 1];mbb=mapB[key][0 if side=='BUY' else 1]
   if not np.array_equal(ma,mbb):raise SystemExit('SIGNAL_PARITY_FAIL '+stable)
   if side=='BUY':unionB|=ma
   else:unionS|=ma
  ex=[z[k] for k in ('eb','ebh','ebl','eah','eal','first','last')];step=a.tf*60000
  outcomes={}
  if unionB.any():
   outcomes['BUY']=(c.outcome_A(mm['ts'],mm['bid'],mm['ask'],A[0],atrA,step,*ex,unionB,1),outcome_B_fast(mm['ts'],mm['bid'],mm['ask'],B[0],atrB,step,*ex,unionB,1))
  if unionS.any():
   outcomes['SELL']=(c.outcome_A(mm['ts'],mm['bid'],mm['ask'],A[0],atrA,step,*ex,unionS,-1),outcome_B_fast(mm['ts'],mm['bid'],mm['ask'],B[0],atrB,step,*ex,unionS,-1))
  records=[]
  for stable,side,key in reps:
   mask=mapA[key][0 if side=='BUY' else 1];OA,OB=outcomes[side]
   chA=c.select_A(mask,OA[0],OA[1]);chB=c.select_B(mask,OB[0],OB[1])
   if not np.array_equal(chA,chB):raise SystemExit('SELECT_PARITY_FAIL '+stable)
   if len(chA):
    for k in range(6):
     if not np.array_equal(OA[k][chA],OB[k][chB]):raise SystemExit('TRADE_PARITY_FAIL '+stable)
   stage=(OA[0][chA]>=STAGE_START)&(OA[0][chA]<STAGE_END)
   ch=chA[stage]
   rr=OA[5][ch].astype(float);ei=OA[2][ch];xi=OA[3][ch];dist=OA[4][ch];et=OA[0][ch]
   if len(ch):
    spread=(mm['ask'][ei]-mm['bid'][ei]).astype(float)+(mm['ask'][xi]-mm['bid'][xi]).astype(float)
    extra=np.divide(spread,dist,out=np.zeros(len(spread)),where=dist>0);cons=rr-0.5*extra;sev=rr-extra
   else:
    cons=rr.copy();sev=rr.copy()
   r20=float(rr[et<CUT_2021].sum());r21=float(rr[et>=CUT_2021].sum())
   pfc=c.pf(rr);pfk=c.pf(cons);pfs=c.pf(sev)
   passed=len(ch)>=20 and pfc>=1.20 and pfk>=1.10 and pfs>=1.00 and rr.sum()>0 and cons.sum()>0 and sev.sum()>0 and r20>0 and r21>0
   sigsha=hashlib.sha256(np.ascontiguousarray(mask).tobytes()).hexdigest()
   rec={'stable_id':stable,'side':side,'n':int(len(ch)),'net_c':float(rr.sum()),'net_k':float(cons.sum()),'net_s':float(sev.sum()),'pf_c':pfc,'pf_k':pfk,'pf_s':pfs,'r2020':r20,'r2021':r21,'signal_mask_sha256_full_context':sigsha,'ledger_sha256_stage':ledger_sha(ch,OA[0],OA[1],OA[5]),'pass':bool(passed)}
   records.append(rec)
  shard=('H1' if a.tf==60 else f'M{a.tf}')+'_'+a.feature_side
  obj={'schema':'QROS_G30_XAU_STAGE_B_2020_2021_SHARD_V75_v1','campaign':'QROS_G30_PUBLIC_VOLATILITY_SHOCK_MOMENTUM_v1','scope':'XAU_STAGE_B_2020_2021_ONLY_2022_PLUS_NOT_IN_INPUT','shard':shard,'input_prefix_sha256':PREFIX_SHA,'cache_sha256':CACHE_SHA,'stage_start_ms':int(STAGE_START),'stage_end_ms':int(STAGE_END),'representatives_evaluated':len(records),'trade_parity':'PASS_EXACT','gate':{'min_trades':20,'pf_central_min':1.20,'pf_conservative_min':1.10,'pf_severe_min':1.00,'net_positive_all_costs':True,'positive_full_years_central':[2020,2021]},'passed':sum(r['pass'] for r in records),'records':records,'retuning':False,'future_2022_plus_pnl_read':False,'status':'PASS'}
  a.out.write_text(json.dumps(safe(obj),separators=(',',':'),allow_nan=False),encoding='utf-8')
  print(json.dumps({'shard':shard,'evaluated':len(records),'passed':obj['passed'],'trade_parity':obj['trade_parity']},sort_keys=True))
if __name__=='__main__':main()
