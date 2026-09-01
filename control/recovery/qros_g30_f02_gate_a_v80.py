#!/usr/bin/env python3
"""QROS G30 F02 development-only Gate-A runner.
Alternative shock identity frontier: TR/ATR, abs close-to-close/ATR, body/ATR.
Two independent bar/signal paths + two independent raw-tick execution paths.
No 2020+ economic data is accepted by this program.
"""
from __future__ import annotations
import argparse, hashlib, json, math, sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import qros_g30_xau_gate_a_v68 as c
from qros_g30_xau_outcome_b_fast_v71 import outcome_B_fast

ASSET_AUTH={
 'XAUUSD':{'src':'3ddb3c95acb9284196c5b6db84385271702800209ee33b1b1a2e1bd59cc9ff53','cache':'f5d847a51ffbbddd29dc4089aa65c04ebe4df01336b91af35223609551923e62'},
 'NQX':{'src':'451843c567d23a53fc7ee5c5cffbcb020112bf91e3b0ee87c5b219b1461aeedf','cache':'8e70138c358ac4a61b3eb602419fc3173640ae6fbcfa939364680dc03488a1ca'}
}
MEAS=['TRUE_RANGE_OVER_ATR','ABS_CLOSE_TO_CLOSE_RETURN_OVER_ATR','BODY_OVER_ATR']
TH=[1.,1.25,1.5,1.75,2.,2.5,3.,3.5,4.]
NS=[1,2,3,4,5,8]
TIM=['CURRENT_BAR_INCLUDED','LAGGED_ONE_BAR_PRE_SHOCK']
FAMS=['CURRENT_CLOSE_EXCEEDS_ALL_PRIOR_N_CLOSES','STRICT_MONOTONIC_N_CLOSE_SEQUENCE','CURRENT_CLOSE_BREAKS_PRIOR_N_BAR_EXTREME']
CUT_2019=np.int64(1546300800000)

def sha_file(p:Path):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return h.hexdigest()

def safe(v):
 if isinstance(v,float) and not math.isfinite(v): return 'INF' if v>0 else ('-INF' if v<0 else 'NAN')
 if isinstance(v,list): return [safe(x) for x in v]
 if isinstance(v,dict): return {k:safe(x) for k,x in v.items()}
 return v

def bases_A(o,h,l,cl):
 L=len(cl);out={}
 for n in NS:
  cw=np.lib.stride_tricks.sliding_window_view(cl,n+1);hw=np.lib.stride_tricks.sliding_window_view(h,n+1);lw=np.lib.stride_tricks.sliding_window_view(l,n+1)
  b=np.zeros(L,bool);s=np.zeros(L,bool);b[n:]=cw[:,-1]>cw[:,:-1].max(1);s[n:]=cw[:,-1]<cw[:,:-1].min(1);out[(FAMS[0],n)]=(b,s)
  d=np.diff(cw,axis=1);b=np.zeros(L,bool);s=np.zeros(L,bool);b[n:]=np.all(d>0,1);s[n:]=np.all(d<0,1);out[(FAMS[1],n)]=(b,s)
  b=np.zeros(L,bool);s=np.zeros(L,bool);b[n:]=cw[:,-1]>hw[:,:-1].max(1);s[n:]=cw[:,-1]<lw[:,:-1].min(1);out[(FAMS[2],n)]=(b,s)
 return out

def rows_A(bucket,o,h,l,cl):
 L=len(cl);atr=c.atr_A(h,l,cl);bases=bases_A(o,h,l,cl);weekday=((bucket//86400000+3)%7)<5
 H=h.astype(float);Lw=l.astype(float);C=cl.astype(float);O=o.astype(float);pc=np.r_[np.nan,C[:-1]]
 nums={
  'TRUE_RANGE_OVER_ATR':np.fmax(H-Lw,np.fmax(np.abs(H-pc),np.abs(Lw-pc))),
  'ABS_CLOSE_TO_CLOSE_RETURN_OVER_ATR':np.abs(C-pc),
  'BODY_OVER_ATR':np.abs(C-O)
 }
 rows=[]
 for meas in MEAS:
  num=nums[meas]
  for ti,timing in enumerate(TIM):
   den=atr if ti==0 else np.r_[np.nan,atr[:-1]]
   ratio=np.divide(num,den,out=np.full(L,np.nan),where=np.isfinite(num)&np.isfinite(den)&(den>0))
   for t in TH:
    shock=(ratio>=t)&weekday
    for fam in FAMS:
     for n in NS:
      b,s=bases[(fam,n)];rows.append((f'{meas}|{timing}|{t:g}|{fam}|{n}',b&shock,s&shock))
    rows.append((f'{meas}|{timing}|{t:g}|SHOCK_BAR_BODY_DIRECTION_ONLY|1',(cl>o)&shock,(cl<o)&shock))
 return atr,rows

def bases_B(o,h,l,cl):
 L=len(cl);out={};d=np.diff(cl);pos=(d>0).astype(np.int8);neg=(d<0).astype(np.int8)
 for n in NS:
  pc=np.vstack([cl[n-k:L-k] for k in range(1,n+1)]);ph=np.vstack([h[n-k:L-k] for k in range(1,n+1)]);pl=np.vstack([l[n-k:L-k] for k in range(1,n+1)])
  b=np.zeros(L,bool);s=np.zeros(L,bool);b[n:]=cl[n:]>pc.max(0);s[n:]=cl[n:]<pc.min(0);out[(FAMS[0],n)]=(b,s)
  b=np.zeros(L,bool);s=np.zeros(L,bool);b[n:]=c.rolling_sum_int(pos,n)==n;s[n:]=c.rolling_sum_int(neg,n)==n;out[(FAMS[1],n)]=(b,s)
  b=np.zeros(L,bool);s=np.zeros(L,bool);b[n:]=cl[n:]>ph.max(0);s[n:]=cl[n:]<pl.min(0);out[(FAMS[2],n)]=(b,s)
 return out

def rows_B(bucket,o,h,l,cl):
 L=len(cl);atr=c.atr_B(h,l,cl);bases=bases_B(o,h,l,cl);weekday=((bucket//86400000+3)%7)<5
 H=h.astype(np.int64);Lw=l.astype(np.int64);C=cl.astype(np.int64);O=o.astype(np.int64);prior=np.r_[C[0],C[:-1]]
 tr=np.maximum(H-Lw,np.maximum(np.abs(H-prior),np.abs(Lw-prior))).astype(np.int64);tr[0]=H[0]-Lw[0]
 cc=np.abs(C-prior).astype(np.int64);cc[0]=0
 nums={'TRUE_RANGE_OVER_ATR':tr,'ABS_CLOSE_TO_CLOSE_RETURN_OVER_ATR':cc,'BODY_OVER_ATR':np.abs(C-O).astype(np.int64)}
 rows=[]
 for meas in MEAS:
  num=nums[meas].astype(float)
  for ti,timing in enumerate(TIM):
   den=atr if ti==0 else np.r_[np.nan,atr[:-1]]
   ratio=np.divide(num,den,out=np.full(L,np.nan),where=np.isfinite(den)&(den>0))
   for t in TH:
    shock=(ratio>=t)&weekday
    for fam in FAMS:
     for n in NS:
      b,s=bases[(fam,n)];rows.append((f'{meas}|{timing}|{t:g}|{fam}|{n}',b&shock,s&shock))
    rows.append((f'{meas}|{timing}|{t:g}|SHOCK_BAR_BODY_DIRECTION_ONLY|1',(cl>o)&shock,(cl<o)&shock))
 return atr,rows

def canonicalize(rows):
 seq=hashlib.sha256();order=[];by={}
 for key,b,s in rows:
  enc=np.zeros(len(b),np.int8);enc[b]=1;enc[s]=-1;d=hashlib.sha256(enc.tobytes()).hexdigest();seq.update(key.encode()+b'\0'+bytes.fromhex(d))
  if d not in by:
   by[d]=[key,b,s,[key]];order.append(d)
  else: by[d][3].append(key)
 root=hashlib.sha256(('\n'.join(sorted(by))+'\n').encode()).hexdigest()
 return seq.hexdigest(),root,[(by[d][0],by[d][1],by[d][2],d,by[d][3]) for d in order]

def ledger_sha(ch,et,xt,rr):
 h=hashlib.sha256()
 for q in ch:
  h.update(np.int64(et[q]).tobytes());h.update(np.int64(xt[q]).tobytes());h.update(np.float64(rr[q]).tobytes())
 return h.hexdigest()

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--asset',choices=['NQX','XAUUSD'],required=True);ap.add_argument('--src',type=Path,required=True);ap.add_argument('--cache',type=Path,required=True);ap.add_argument('--tf',type=int,required=True);ap.add_argument('--feature-side',choices=['BID','MID'],required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 auth=ASSET_AUTH[a.asset]
 if sha_file(a.src)!=auth['src']:raise SystemExit('DEV_SHA_MISMATCH')
 if sha_file(a.cache)!=auth['cache']:raise SystemExit('CACHE_SHA_MISMATCH')
 mm=np.memmap(a.src,dtype=c.DT,mode='r')
 with np.load(a.cache) as z:
  mb=z['mb'];ks=('bo','bh','bl','bc') if a.feature_side=='BID' else ('mo','mh','ml','mc');vals=[z[k] for k in ks]
  A=c.bars_A(mb,*vals,a.tf);B=c.bars_B(mb,*vals,a.tf)
  if c.digest_arrays(A)!=c.digest_arrays(B):raise SystemExit('BAR_PARITY_FAIL')
  atrA,rA=rows_A(*A);atrB,rB=rows_B(*B)
  rawA,setA,uA=canonicalize(rA);rawB,setB,uB=canonicalize(rB)
  if rawA!=rawB or setA!=setB or len(uA)!=len(uB):raise SystemExit('SIGNAL_PARITY_FAIL')
  if [(x[0],x[3],x[4]) for x in uA] != [(x[0],x[3],x[4]) for x in uB]:raise SystemExit('DEDUPE_PARITY_FAIL')
  unionB=np.zeros(len(A[0]),bool);unionS=np.zeros(len(A[0]),bool)
  for _,b,s,_,_ in uA:unionB|=b;unionS|=s
  ex=[z[k] for k in ('eb','ebh','ebl','eah','eal','first','last')];step=a.tf*60000
  oaB=c.outcome_A(mm['ts'],mm['bid'],mm['ask'],A[0],atrA,step,*ex,unionB,1);obB=outcome_B_fast(mm['ts'],mm['bid'],mm['ask'],B[0],atrB,step,*ex,unionB,1)
  oaS=c.outcome_A(mm['ts'],mm['bid'],mm['ask'],A[0],atrA,step,*ex,unionS,-1);obS=outcome_B_fast(mm['ts'],mm['bid'],mm['ask'],B[0],atrB,step,*ex,unionS,-1)
  records=[];passers=[]
  for key,bmask,smask,sigsha,aliases in uA:
   for side,mask,OA,OB in [('BUY',bmask,oaB,obB),('SELL',smask,oaS,obS)]:
    chA=c.select_A(mask,OA[0],OA[1]);chB=c.select_B(mask,OB[0],OB[1])
    if not np.array_equal(chA,chB):raise SystemExit('SELECT_PARITY_FAIL '+key+' '+side)
    if len(chA):
     for k in range(6):
      if not np.array_equal(OA[k][chA],OB[k][chB]):raise SystemExit('TRADE_PARITY_FAIL '+key+' '+side)
    rr=OA[5][chA].astype(float);ei=OA[2][chA];xi=OA[3][chA];dist=OA[4][chA];et=OA[0][chA]
    if len(chA):
     spread=(mm['ask'][ei]-mm['bid'][ei]).astype(float)+(mm['ask'][xi]-mm['bid'][xi]).astype(float);extra=np.divide(spread,dist,out=np.zeros(len(spread)),where=dist>0);cons=rr-0.5*extra;sev=rr-extra
    else:cons=rr.copy();sev=rr.copy()
    y18=float(rr[et<CUT_2019].sum());y19=float(rr[et>=CUT_2019].sum());pfc=c.pf(rr);pfk=c.pf(cons);pfs=c.pf(sev)
    passed=len(chA)>=60 and pfc>=1.20 and pfk>=1.10 and pfs>=1.00 and rr.sum()>0 and cons.sum()>0 and sev.sum()>0 and y18>0 and y19>0
    rec={'id':key,'aliases':aliases,'signal_sha256':sigsha,'side':side,'n':int(len(chA)),'net_c':float(rr.sum()),'net_k':float(cons.sum()),'net_s':float(sev.sum()),'pf_c':pfc,'pf_k':pfk,'pf_s':pfs,'r2018':y18,'r2019':y19,'ledger_sha256':ledger_sha(chA,OA[0],OA[1],OA[5]),'pass':bool(passed)}
    records.append(rec)
    if passed:passers.append(rec)
  shard=('H1' if a.tf==60 else f'M{a.tf}')+'_'+a.feature_side
  obj={'schema':'QROS_G30_F02_GATE_A_SHARD_V80_v1','campaign':'QROS_G30_PUBLIC_VOLATILITY_SHOCK_MOMENTUM_v1','frontier':'F02_SHOCK_MEASURE_ALTERNATIVES','asset':a.asset,'scope':'DEV_2018_2019_ONLY_NO_2020_PLUS_PNL','shard':shard,'bars':int(len(A[0])),'raw_identities':len(rA),'unique_masks':len(uA),'exact_alias_count':len(rA)-len(uA),'evaluated_configurations':len(records),'bar_digest':c.digest_arrays(A),'raw_identity_sequence_sha256':rawA,'unique_mask_set_sha256':setA,'trade_parity':'PASS_EXACT','gate':{'min_trades':60,'pf_central_min':1.20,'pf_conservative_min':1.10,'pf_severe_min':1.00,'both_dev_years_positive_central':True,'net_positive_all_costs':True},'passed':len(passers),'passed_buy':sum(x['side']=='BUY' for x in passers),'passed_sell':sum(x['side']=='SELL' for x in passers),'passers':passers,'all_records':records,'future_pnl_read':False,'status':'PASS'}
  a.out.write_text(json.dumps(safe(obj),separators=(',',':'),allow_nan=False),encoding='utf-8')
  print(json.dumps({k:obj[k] for k in ['asset','shard','bars','raw_identities','unique_masks','exact_alias_count','evaluated_configurations','passed','passed_buy','passed_sell','trade_parity']},sort_keys=True))
if __name__=='__main__':main()
