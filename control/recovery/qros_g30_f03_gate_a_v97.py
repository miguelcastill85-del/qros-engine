#!/usr/bin/env python3
"""QROS G30 F03 ATR_PERIOD development-only Gate-A runner.

F03 mutates SIGNAL ATR period only: 7/10/20/28/50. Management remains
frozen at ATR14 stop x3.0, 1.5R target, 20-bar/same-day exit.
Two independent signal/bar paths and two independent execution paths must
match exactly. Only exact canonical 2018-2019 DEV sources are accepted.
No 2020+ economic data is accepted.
"""
from __future__ import annotations
import argparse, hashlib, json, math, sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import qros_g30_f03_signal_primary_v97 as sa
import qros_g30_f03_signal_independent_v97 as sb
import qros_g30_f03_execution_primary_v97 as ea
import qros_g30_f03_execution_independent_v97 as eb

DT=np.dtype([('ts','<i8'),('bid','<i4'),('ask','<i4'),('flags','u1')])
ASSET_AUTH={
 'XAUUSD':{'src':'3ddb3c95acb9284196c5b6db84385271702800209ee33b1b1a2e1bd59cc9ff53','cache':'f5d847a51ffbbddd29dc4089aa65c04ebe4df01336b91af35223609551923e62'},
 'NQX':{'src':'451843c567d23a53fc7ee5c5cffbcb020112bf91e3b0ee87c5b219b1461aeedf','cache':'8e70138c358ac4a61b3eb602419fc3173640ae6fbcfa939364680dc03488a1ca'}
}
PERIODS=(7,10,20,28,50)
TIM=('CURRENT_BAR_INCLUDED','LAGGED_ONE_BAR_PRE_SHOCK')
TH=(1.0,1.25,1.5,1.75,2.0,2.5,3.0,3.5,4.0)
NS=(1,2,3,4,5,8)
FAMS=('CURRENT_CLOSE_EXCEEDS_ALL_PRIOR_N_CLOSES','STRICT_MONOTONIC_N_CLOSE_SEQUENCE','CURRENT_CLOSE_BREAKS_PRIOR_N_BAR_EXTREME')
CUT_2019=np.int64(1546300800000)
EXPECTED_RAW=1710


def sha_file(p:Path):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return h.hexdigest()

def digest_arrays(arrs):
 h=hashlib.sha256()
 for a in arrs:
  z=np.ascontiguousarray(a);h.update(str(z.dtype).encode()+b'\0');h.update(np.int64(z.size).tobytes());h.update(z.tobytes())
 return h.hexdigest()

def safe(v):
 if isinstance(v,float) and not math.isfinite(v):return 'INF' if v>0 else ('-INF' if v<0 else 'NAN')
 if isinstance(v,list):return [safe(x) for x in v]
 if isinstance(v,dict):return {k:safe(x) for k,x in v.items()}
 return v

def specs():
 for p in PERIODS:
  for timing in TIM:
   for t in TH:
    for fam in FAMS:
     for n in NS:yield (p,timing,t,fam,n)
    yield (p,timing,t,'SHOCK_BAR_BODY_DIRECTION_ONLY',1)

def spec_key(sp):
 p,timing,t,fam,n=sp
 return f'ATR{p}|{timing}|{t:g}|{fam}|{n}'

def mask_digest(b,s):
 enc=np.zeros(len(b),np.int8);enc[b]=1;enc[s]=-1
 return hashlib.sha256(enc.tobytes()).hexdigest()

def pf(x):
 pos=float(x[x>0].sum());neg=float(-x[x<0].sum())
 if neg==0:return float('inf') if pos>0 else 0.0
 return pos/neg

def ledger_sha(ch,et,xt,rr):
 h=hashlib.sha256()
 for q in ch:
  h.update(np.int64(et[q]).tobytes());h.update(np.int64(xt[q]).tobytes());h.update(np.float64(rr[q]).tobytes())
 return h.hexdigest()

def verify_unit_receipt(path:Path):
 obj=json.loads(path.read_text(encoding='utf-8'))
 if obj.get('status')!='PASS' or obj.get('decision')!='ECONOMIC_SCORING_UNIT_BINDING_AUTHORIZED' or obj.get('economic_scoring_unit_binding_authorized') is not True:
  raise SystemExit('UNIT_BINDING_PREFLIGHT_NOT_AUTHORIZED')
 return obj

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--asset',choices=['NQX','XAUUSD'],required=True);ap.add_argument('--src',type=Path,required=True);ap.add_argument('--cache',type=Path,required=True);ap.add_argument('--tf',type=int,choices=[1,5,10,15,30,60],required=True);ap.add_argument('--feature-side',choices=['BID','MID'],required=True);ap.add_argument('--unit-receipt',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 unit_receipt=verify_unit_receipt(a.unit_receipt)
 auth=ASSET_AUTH[a.asset]
 if sha_file(a.src)!=auth['src']:raise SystemExit('DEV_SHA_MISMATCH')
 if sha_file(a.cache)!=auth['cache']:raise SystemExit('CACHE_SHA_MISMATCH')
 mm=np.memmap(a.src,dtype=DT,mode='r')
 with np.load(a.cache) as z:
  mb=z['mb'];ks=('bo','bh','bl','bc') if a.feature_side=='BID' else ('mo','mh','ml','mc');vals=[z[k] for k in ks]
  A=sa.bars(mb,*vals,a.tf);B=sb.bars(mb,*vals,a.tf)
  bar_digest_A=digest_arrays(A);bar_digest_B=digest_arrays(B)
  if bar_digest_A!=bar_digest_B:raise SystemExit('BAR_PARITY_FAIL')
  pa=sa.prepare(*A);pb=sb.prepare(*B)
  atr14A=sa.atr(A[2],A[3],A[4],14);atr14B=sb.atr(B[2],B[3],B[4],14)
  if not np.array_equal(np.nan_to_num(atr14A,nan=-1.0),np.nan_to_num(atr14B,nan=-1.0)):raise SystemExit('MANAGEMENT_ATR14_PARITY_FAIL')
  seq=hashlib.sha256();by={};order=[];unionBA=np.zeros(len(A[0]),bool);unionSA=np.zeros(len(A[0]),bool);unionBB=np.zeros(len(B[0]),bool);unionSB=np.zeros(len(B[0]),bool);raw=0
  for sp in specs():
   raw+=1;key=spec_key(sp);bA,sA=sa.mask(pa,*A[1:],*sp);bB,sB=sb.mask(pb,*B[1:],*sp)
   if not np.array_equal(bA,bB) or not np.array_equal(sA,sB):raise SystemExit('SIGNAL_PARITY_FAIL '+key)
   dA=mask_digest(bA,sA);dB=mask_digest(bB,sB)
   if dA!=dB:raise SystemExit('SIGNAL_DIGEST_PARITY_FAIL '+key)
   seq.update(key.encode()+b'\0'+bytes.fromhex(dA));unionBA|=bA;unionSA|=sA;unionBB|=bB;unionSB|=sB
   if dA not in by:by[dA]={'spec':sp,'key':key,'aliases':[key]};order.append(dA)
   else:by[dA]['aliases'].append(key)
  if raw!=EXPECTED_RAW:raise SystemExit(f'RAW_CARDINALITY_FAIL {raw}')
  if not np.array_equal(unionBA,unionBB) or not np.array_equal(unionSA,unionSB):raise SystemExit('UNION_PARITY_FAIL')
  setroot=hashlib.sha256(('\n'.join(sorted(by))+'\n').encode()).hexdigest();rawroot=seq.hexdigest()
  ex=[z[k] for k in ('eb','ebh','ebl','eah','eal','first','last')];step=a.tf*60000
  oaB=ea.outcome(mm['ts'],mm['bid'],mm['ask'],A[0],atr14A,step,*ex,unionBA,1);obB=eb.outcome(mm['ts'],mm['bid'],mm['ask'],B[0],atr14B,step,unionBB,1)
  oaS=ea.outcome(mm['ts'],mm['bid'],mm['ask'],A[0],atr14A,step,*ex,unionSA,-1);obS=eb.outcome(mm['ts'],mm['bid'],mm['ask'],B[0],atr14B,step,unionSB,-1)
  records=[];passers=[]
  for d in order:
   meta=by[d];sp=meta['spec'];key=meta['key'];bA,sA=sa.mask(pa,*A[1:],*sp);bB,sB=sb.mask(pb,*B[1:],*sp)
   if not np.array_equal(bA,bB) or not np.array_equal(sA,sB) or mask_digest(bA,sA)!=d or mask_digest(bB,sB)!=d:raise SystemExit('REPLAY_SIGNAL_PARITY_FAIL '+key)
   for side,maskA,maskB,OA,OB in [('BUY',bA,bB,oaB,obB),('SELL',sA,sB,oaS,obS)]:
    chA=ea.select(maskA,OA[0],OA[1]);chB=eb.select(maskB,OB[0],OB[1])
    if not np.array_equal(chA,chB):raise SystemExit('SELECT_PARITY_FAIL '+key+' '+side)
    if len(chA):
     for k in range(6):
      if not np.array_equal(OA[k][chA],OB[k][chB]):raise SystemExit('TRADE_PARITY_FAIL '+key+' '+side)
    rr=OA[5][chA].astype(float);ei=OA[2][chA];xi=OA[3][chA];dist=OA[4][chA];et=OA[0][chA]
    if len(chA):
     spread=(mm['ask'][ei]-mm['bid'][ei]).astype(float)+(mm['ask'][xi]-mm['bid'][xi]).astype(float);extra=np.divide(spread,dist,out=np.zeros(len(spread)),where=dist>0);cons=rr-0.5*extra;sev=rr-extra
    else:cons=rr.copy();sev=rr.copy()
    y18=float(rr[et<CUT_2019].sum());y19=float(rr[et>=CUT_2019].sum());pfc=pf(rr);pfk=pf(cons);pfs=pf(sev)
    passed=len(chA)>=60 and pfc>=1.20 and pfk>=1.10 and pfs>=1.00 and rr.sum()>0 and cons.sum()>0 and sev.sum()>0 and y18>0 and y19>0
    rec={'id':key,'aliases':meta['aliases'],'signal_sha256':d,'side':side,'n':int(len(chA)),'net_c':float(rr.sum()),'net_k':float(cons.sum()),'net_s':float(sev.sum()),'pf_c':pfc,'pf_k':pfk,'pf_s':pfs,'r2018':y18,'r2019':y19,'ledger_sha256':ledger_sha(chA,OA[0],OA[1],OA[5]),'pass':bool(passed)}
    records.append(rec)
    if passed:passers.append(rec)
  shard=('H1' if a.tf==60 else f'M{a.tf}')+'_'+a.feature_side
  obj={'schema':'QROS_G30_F03_GATE_A_SHARD_V97_v1','campaign':'QROS_G30_PUBLIC_VOLATILITY_SHOCK_MOMENTUM_v1','frontier':'F03_ATR_PERIOD','asset':a.asset,'scope':'EXPOSED_DEV_2018_2019_ONLY_NO_2020_PLUS_PNL','shard':shard,'bars':int(len(A[0])),'raw_identities':raw,'unique_masks':len(order),'exact_alias_count':raw-len(order),'evaluated_configurations':len(records),'bar_digest':bar_digest_A,'raw_identity_sequence_sha256':rawroot,'unique_mask_set_sha256':setroot,'union_buy':int(unionBA.sum()),'union_sell':int(unionSA.sum()),'signal_parity':'PASS_EXACT','trade_parity':'PASS_EXACT','management':{'signal_atr_periods':[7,10,20,28,50],'stop_atr_period':14,'atr_stop_mult':3.0,'reward_r_multiple':1.5,'time_stop_bars':20},'unit_binding':{'receipt_input_sha256':unit_receipt.get('input_sha256'),'status':'PASS','effective_stop_atr_mult':3.0},'gate':{'min_trades':60,'pf_central_min':1.20,'pf_conservative_min':1.10,'pf_severe_min':1.00,'both_dev_years_positive_central':True,'net_positive_all_costs':True},'passed':len(passers),'passed_buy':sum(x['side']=='BUY' for x in passers),'passed_sell':sum(x['side']=='SELL' for x in passers),'passers':passers,'all_records':records,'future_pnl_read':False,'historical_holdout_opened':False,'status':'PASS'}
  a.out.write_text(json.dumps(safe(obj),separators=(',',':'),allow_nan=False),encoding='utf-8')
  print(json.dumps({k:obj[k] for k in ['asset','shard','bars','raw_identities','unique_masks','exact_alias_count','evaluated_configurations','passed','passed_buy','passed_sell','signal_parity','trade_parity']},sort_keys=True))
if __name__=='__main__':main()
