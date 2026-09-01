#!/usr/bin/env python3
"""Efficient dual-path wrapper for qros_g30_xau_gate_a_v68.
Path B uses the independently implemented executable-minute accelerator; scientific rules are unchanged.
"""
from __future__ import annotations
import argparse, json, math, sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import qros_g30_xau_gate_a_v68 as c
from qros_g30_xau_outcome_b_fast_v71 import outcome_B_fast

def safe(x):
 if isinstance(x,float) and not math.isfinite(x): return 'INF' if x>0 else ('-INF' if x<0 else 'NAN')
 if isinstance(x,dict): return {k:safe(v) for k,v in x.items()}
 if isinstance(x,list): return [safe(v) for v in x]
 return x

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--src',type=Path,required=True);ap.add_argument('--cache',type=Path,required=True);ap.add_argument('--tf',type=int,required=True);ap.add_argument('--feature-side',choices=['BID','MID'],required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 if c.sha_file(a.src)!=c.CANONICAL_XAU_DEV_SHA:raise SystemExit('DEV SHA mismatch')
 if c.sha_file(a.cache)!=c.CACHE_SHA:raise SystemExit('cache SHA mismatch')
 mm=np.memmap(a.src,dtype=c.DT,mode='r')
 with np.load(a.cache) as z:
  mb=z['mb'];ks=('bo','bh','bl','bc') if a.feature_side=='BID' else ('mo','mh','ml','mc');vals=[z[k] for k in ks]
  A=c.bars_A(mb,*vals,a.tf);B=c.bars_B(mb,*vals,a.tf)
  if c.digest_arrays(A)!=c.digest_arrays(B):raise SystemExit('BAR_PARITY_FAIL')
  atrA,rA=c.rows_A(*A);atrB,rB=c.rows_B(*B);rawA,setA,uA=c.row_digest(rA);rawB,setB,uB=c.row_digest(rB)
  if rawA!=rawB or setA!=setB or len(uA)!=len(uB):raise SystemExit('SIGNAL_PARITY_FAIL')
  if [x[0] for x in uA]!=[x[0] for x in uB] or [x[3] for x in uA]!=[x[3] for x in uB]:raise SystemExit('DEDUPE_PARITY_FAIL')
  unionB=np.zeros(len(A[0]),bool);unionS=np.zeros(len(A[0]),bool)
  for _,b,s,_ in uA:unionB|=b;unionS|=s
  ex=[z[k] for k in ('eb','ebh','ebl','eah','eal','first','last')];step=a.tf*60000
  oaB=c.outcome_A(mm['ts'],mm['bid'],mm['ask'],A[0],atrA,step,*ex,unionB,1);obB=outcome_B_fast(mm['ts'],mm['bid'],mm['ask'],B[0],atrB,step,*ex,unionB,1)
  oaS=c.outcome_A(mm['ts'],mm['bid'],mm['ask'],A[0],atrA,step,*ex,unionS,-1);obS=outcome_B_fast(mm['ts'],mm['bid'],mm['ask'],B[0],atrB,step,*ex,unionS,-1)
  records=[];passers=[];parity_fail=0
  for key,bmask,smask,sigsha in uA:
   for side,mask,OA,OB in [('BUY',bmask,oaB,obB),('SELL',smask,oaS,obS)]:
    chA=c.select_A(mask,OA[0],OA[1]);chB=c.select_B(mask,OB[0],OB[1]);same=np.array_equal(chA,chB)
    if same and len(chA):
     for k in range(6):
      if not np.array_equal(OA[k][chA],OB[k][chB]):same=False;break
    if not same:parity_fail+=1;continue
    rr=OA[5][chA].astype(float);ei=OA[2][chA];xi=OA[3][chA];dist=OA[4][chA]
    if len(chA):
     spread=(mm['ask'][ei]-mm['bid'][ei]).astype(float)+(mm['ask'][xi]-mm['bid'][xi]).astype(float);extra=np.divide(spread,dist,out=np.zeros(len(spread)),where=dist>0);cons=rr-0.5*extra;sev=rr-extra;eyear=OA[0][chA];y18=float(rr[eyear<c.CUT_2019].sum());y19=float(rr[eyear>=c.CUT_2019].sum())
    else:cons=rr.copy();sev=rr.copy();y18=y19=0.
    pfc=c.pf(rr);pfk=c.pf(cons);pfs=c.pf(sev);passed=len(chA)>=60 and pfc>=1.20 and pfk>=1.10 and pfs>=1.00 and y18>0 and y19>0
    rec={'id':key,'signal_sha256':sigsha,'side':side,'n':int(len(chA)),'net_c':float(rr.sum()),'net_k':float(cons.sum()),'net_s':float(sev.sum()),'pf_c':pfc,'pf_k':pfk,'pf_s':pfs,'r2018':y18,'r2019':y19,'ledger_sha256':c.ledger_sha(chA,OA[0],OA[1],OA[5]),'pass':bool(passed)};records.append(rec)
    if passed:passers.append(rec)
  if parity_fail:raise SystemExit(f'TRADE_PARITY_FAIL {parity_fail}')
  shard=('H1' if a.tf==60 else f'M{a.tf}')+'_'+a.feature_side
  obj={'schema':'QROS_G30_XAU_GATE_A_SHARD_V71_v1','scope':'XAU_DEV_2018_2019_ONLY_NO_2020_PLUS_PNL','shard':shard,'bars':int(len(A[0])),'raw_identities':len(rA),'unique_masks':len(uA),'evaluated_configurations':len(records),'bar_digest':c.digest_arrays(A),'raw_identity_sequence_sha256':rawA,'unique_mask_set_sha256':setA,'union_buy':int(unionB.sum()),'union_sell':int(unionS.sum()),'trade_parity':'PASS_EXACT','parity_failures':0,'gate':{'min_trades':60,'pf_central_min':1.20,'pf_conservative_min':1.10,'pf_severe_min':1.00,'both_dev_years_positive_central':True},'passed':len(passers),'passed_buy':sum(x['side']=='BUY' for x in passers),'passed_sell':sum(x['side']=='SELL' for x in passers),'passers':passers,'all_records':records,'future_pnl_read':False,'status':'PASS'}
  a.out.write_text(json.dumps(safe(obj),separators=(',',':'),allow_nan=False),encoding='utf-8');print(json.dumps({k:obj[k] for k in ['shard','bars','raw_identities','unique_masks','evaluated_configurations','passed','passed_buy','passed_sell','trade_parity']},sort_keys=True))
if __name__=='__main__':main()
