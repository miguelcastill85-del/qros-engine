#!/usr/bin/env python3
"""Memory-bounded M1 scorer for G30 F02.
Same frozen F02 formulas/gates as qros_g30_f02_gate_a_v80, but signal identities are streamed one-by-one.
Execution outcomes are computed once for the causal union. Two independent signal paths and execution paths must agree exactly.
"""
from __future__ import annotations
import argparse,hashlib,json,math,sys
from pathlib import Path
import numpy as np
from numba import njit
sys.path.insert(0,str(Path(__file__).resolve().parent))
import qros_g30_xau_gate_a_v68 as c
from qros_g30_xau_outcome_b_fast_v71 import outcome_B_fast
ASSET_AUTH={
 'XAUUSD':{'src':'3ddb3c95acb9284196c5b6db84385271702800209ee33b1b1a2e1bd59cc9ff53','cache':'f5d847a51ffbbddd29dc4089aa65c04ebe4df01336b91af35223609551923e62'},
 'NQX':{'src':'451843c567d23a53fc7ee5c5cffbcb020112bf91e3b0ee87c5b219b1461aeedf','cache':'8e70138c358ac4a61b3eb602419fc3173640ae6fbcfa939364680dc03488a1ca'}}
MEAS=['TRUE_RANGE_OVER_ATR','ABS_CLOSE_TO_CLOSE_RETURN_OVER_ATR','BODY_OVER_ATR'];TIM=['CURRENT_BAR_INCLUDED','LAGGED_ONE_BAR_PRE_SHOCK'];TH=[1.,1.25,1.5,1.75,2.,2.5,3.,3.5,4.];NS=[1,2,3,4,5,8]
FAMS=['CURRENT_CLOSE_EXCEEDS_ALL_PRIOR_N_CLOSES','STRICT_MONOTONIC_N_CLOSE_SEQUENCE','CURRENT_CLOSE_BREAKS_PRIOR_N_BAR_EXTREME'];CUT=np.int64(1546300800000)
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return h.hexdigest()
def safe(v):
 if isinstance(v,float) and not math.isfinite(v):return 'INF' if v>0 else ('-INF' if v<0 else 'NAN')
 if isinstance(v,list):return [safe(x) for x in v]
 if isinstance(v,dict):return {k:safe(x) for k,x in v.items()}
 return v
def build_bases_A(o,h,l,cl):
 L=len(cl);d={}
 for n in NS:
  cw=np.lib.stride_tricks.sliding_window_view(cl,n+1);hw=np.lib.stride_tricks.sliding_window_view(h,n+1);lw=np.lib.stride_tricks.sliding_window_view(l,n+1)
  b=np.zeros(L,bool);s=np.zeros(L,bool);b[n:]=cw[:,-1]>cw[:,:-1].max(1);s[n:]=cw[:,-1]<cw[:,:-1].min(1);d[(FAMS[0],n)]=(b,s)
  z=np.diff(cw,axis=1);b=np.zeros(L,bool);s=np.zeros(L,bool);b[n:]=np.all(z>0,1);s[n:]=np.all(z<0,1);d[(FAMS[1],n)]=(b,s)
  b=np.zeros(L,bool);s=np.zeros(L,bool);b[n:]=cw[:,-1]>hw[:,:-1].max(1);s[n:]=cw[:,-1]<lw[:,:-1].min(1);d[(FAMS[2],n)]=(b,s)
 return d
def build_bases_B(o,h,l,cl):
 L=len(cl);d={};diff=np.diff(cl);pos=(diff>0).astype(np.int8);neg=(diff<0).astype(np.int8)
 for n in NS:
  pc=np.vstack([cl[n-k:L-k] for k in range(1,n+1)]);ph=np.vstack([h[n-k:L-k] for k in range(1,n+1)]);pl=np.vstack([l[n-k:L-k] for k in range(1,n+1)])
  b=np.zeros(L,bool);s=np.zeros(L,bool);b[n:]=cl[n:]>pc.max(0);s[n:]=cl[n:]<pc.min(0);d[(FAMS[0],n)]=(b,s)
  b=np.zeros(L,bool);s=np.zeros(L,bool);b[n:]=c.rolling_sum_int(pos,n)==n;s[n:]=c.rolling_sum_int(neg,n)==n;d[(FAMS[1],n)]=(b,s)
  b=np.zeros(L,bool);s=np.zeros(L,bool);b[n:]=cl[n:]>ph.max(0);s[n:]=cl[n:]<pl.min(0);d[(FAMS[2],n)]=(b,s)
 return d
def numerators_A(o,h,l,cl):
 H=h.astype(float);L=l.astype(float);C=cl.astype(float);O=o.astype(float);pc=np.r_[np.nan,C[:-1]]
 return {'TRUE_RANGE_OVER_ATR':np.fmax(H-L,np.fmax(np.abs(H-pc),np.abs(L-pc))),'ABS_CLOSE_TO_CLOSE_RETURN_OVER_ATR':np.abs(C-pc),'BODY_OVER_ATR':np.abs(C-O)}
def numerators_B(o,h,l,cl):
 H=h.astype(np.int64);L=l.astype(np.int64);C=cl.astype(np.int64);O=o.astype(np.int64);pc=np.r_[C[0],C[:-1]]
 tr=np.maximum(H-L,np.maximum(np.abs(H-pc),np.abs(L-pc))).astype(np.int64);tr[0]=H[0]-L[0];cc=np.abs(C-pc);cc[0]=0
 return {'TRUE_RANGE_OVER_ATR':tr.astype(float),'ABS_CLOSE_TO_CLOSE_RETURN_OVER_ATR':cc.astype(float),'BODY_OVER_ATR':np.abs(C-O).astype(float)}
@njit
def select_B_fast(mask,et,xt):
 ids=np.flatnonzero(mask);out=np.empty(len(ids),np.int64);k=0;prev=np.int64(-1)
 for i in range(len(ids)):
  q=ids[i]
  if et[q]<0 or et[q]<=prev:continue
  out[k]=q;k+=1;prev=xt[q]
 return out[:k]
def ledger(ch,et,xt,rr):
 h=hashlib.sha256()
 for q in ch:h.update(np.int64(et[q]).tobytes()+np.int64(xt[q]).tobytes()+np.float64(rr[q]).tobytes())
 return h.hexdigest()
def mask_digest(b,s):
 x=np.zeros(len(b),np.int8);x[b]=1;x[s]=-1;return hashlib.sha256(x.tobytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--asset',choices=['NQX','XAUUSD'],required=True);ap.add_argument('--src',type=Path,required=True);ap.add_argument('--cache',type=Path,required=True);ap.add_argument('--feature-side',choices=['BID','MID'],required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();auth=ASSET_AUTH[a.asset]
 if sha(a.src)!=auth['src']:raise SystemExit('DEV_SHA_MISMATCH')
 if sha(a.cache)!=auth['cache']:raise SystemExit('CACHE_SHA_MISMATCH')
 mm=np.memmap(a.src,dtype=c.DT,mode='r')
 with np.load(a.cache) as z:
  mb=z['mb'];ks=('bo','bh','bl','bc') if a.feature_side=='BID' else ('mo','mh','ml','mc');o,h,l,cl=[z[k] for k in ks]
  A=(mb.copy(),o.copy(),h.copy(),l.copy(),cl.copy());B=tuple(np.asarray(x,np.int64).copy() for x in (mb,o,h,l,cl))
  if c.digest_arrays(A)!=c.digest_arrays(B):raise SystemExit('BAR_PARITY_FAIL')
  atrA=c.atr_A(h,l,cl);atrB=c.atr_B(B[2],B[3],B[4]);bA=build_bases_A(o,h,l,cl);bB=build_bases_B(B[1],B[2],B[3],B[4]);nA=numerators_A(o,h,l,cl);nB=numerators_B(B[1],B[2],B[3],B[4]);weekday=((mb//86400000+3)%7)<5
  active=np.zeros(len(mb),bool)
  for meas in MEAS:
   for ti in range(2):
    da=atrA if ti==0 else np.r_[np.nan,atrA[:-1]];ra=np.divide(nA[meas],da,out=np.full(len(mb),np.nan),where=np.isfinite(nA[meas])&np.isfinite(da)&(da>0));active|=(ra>=1.0)&weekday
  ex=[z[k] for k in ('eb','ebh','ebl','eah','eal','first','last')]
  oaB=c.outcome_A(mm['ts'],mm['bid'],mm['ask'],mb,atrA,60000,*ex,active,1);obB=outcome_B_fast(mm['ts'],mm['bid'],mm['ask'],mb,atrB,60000,*ex,active,1)
  oaS=c.outcome_A(mm['ts'],mm['bid'],mm['ask'],mb,atrA,60000,*ex,active,-1);obS=outcome_B_fast(mm['ts'],mm['bid'],mm['ask'],mb,atrB,60000,*ex,active,-1)
  rawh=hashlib.sha256();seen={};order=[];records=[];passers=[];raw_count=0
  for meas in MEAS:
   for ti,timing in enumerate(TIM):
    da=atrA if ti==0 else np.r_[np.nan,atrA[:-1]];db=atrB if ti==0 else np.r_[np.nan,atrB[:-1]]
    ra=np.divide(nA[meas],da,out=np.full(len(mb),np.nan),where=np.isfinite(nA[meas])&np.isfinite(da)&(da>0));rb=np.divide(nB[meas],db,out=np.full(len(mb),np.nan),where=np.isfinite(db)&(db>0))
    for t in TH:
     sa=(ra>=t)&weekday;sb=(rb>=t)&weekday
     identities=[]
     for fam in FAMS:
      for n in NS:identities.append((f'{meas}|{timing}|{t:g}|{fam}|{n}',bA[(fam,n)][0]&sa,bA[(fam,n)][1]&sa,bB[(fam,n)][0]&sb,bB[(fam,n)][1]&sb))
     identities.append((f'{meas}|{timing}|{t:g}|SHOCK_BAR_BODY_DIRECTION_ONLY|1',(cl>o)&sa,(cl<o)&sa,(B[4]>B[1])&sb,(B[4]<B[1])&sb))
     for key,ba,ssa,bb,ssb in identities:
      raw_count+=1
      if not np.array_equal(ba,bb) or not np.array_equal(ssa,ssb):raise SystemExit('SIGNAL_PARITY_FAIL '+key)
      d=mask_digest(ba,ssa);rawh.update(key.encode()+b'\0'+bytes.fromhex(d))
      if d in seen:seen[d]['aliases'].append(key);continue
      entry={'canonical':key,'aliases':[key]};seen[d]=entry;order.append(d)
      for side,mask,OA,OB in [('BUY',ba,oaB,obB),('SELL',ssa,oaS,obS)]:
       ca=c.select_A(mask,OA[0],OA[1]);cb=select_B_fast(mask,OB[0],OB[1])
       if not np.array_equal(ca,cb):raise SystemExit('SELECT_PARITY_FAIL '+key+' '+side)
       if len(ca):
        for k in range(6):
         if not np.array_equal(OA[k][ca],OB[k][cb]):raise SystemExit('TRADE_PARITY_FAIL '+key+' '+side)
       rr=OA[5][ca].astype(float);ei=OA[2][ca];xi=OA[3][ca];dist=OA[4][ca];et=OA[0][ca]
       if len(ca):
        spr=(mm['ask'][ei]-mm['bid'][ei]).astype(float)+(mm['ask'][xi]-mm['bid'][xi]).astype(float);extra=np.divide(spr,dist,out=np.zeros(len(spr)),where=dist>0);cons=rr-0.5*extra;sev=rr-extra
       else:cons=rr.copy();sev=rr.copy()
       y18=float(rr[et<CUT].sum());y19=float(rr[et>=CUT].sum());pc=c.pf(rr);pk=c.pf(cons);ps=c.pf(sev);passed=len(ca)>=60 and pc>=1.20 and pk>=1.10 and ps>=1.00 and rr.sum()>0 and cons.sum()>0 and sev.sum()>0 and y18>0 and y19>0
       rec={'id':key,'signal_sha256':d,'side':side,'n':int(len(ca)),'net_c':float(rr.sum()),'net_k':float(cons.sum()),'net_s':float(sev.sum()),'pf_c':pc,'pf_k':pk,'pf_s':ps,'r2018':y18,'r2019':y19,'ledger_sha256':ledger(ca,OA[0],OA[1],OA[5]),'pass':bool(passed)};records.append(rec)
       if passed:passers.append(rec)
  amap={d:seen[d]['aliases'] for d in order}
  for r in records:r['aliases']=amap[r['signal_sha256']]
  root=hashlib.sha256(('\n'.join(sorted(order))+'\n').encode()).hexdigest();shard='M1_'+a.feature_side
  obj={'schema':'QROS_G30_F02_M1_STREAM_SHARD_V82_v1','campaign':'QROS_G30_PUBLIC_VOLATILITY_SHOCK_MOMENTUM_v1','frontier':'F02_SHOCK_MEASURE_ALTERNATIVES','asset':a.asset,'scope':'DEV_2018_2019_ONLY_NO_2020_PLUS_PNL','shard':shard,'bars':int(len(mb)),'raw_identities':raw_count,'unique_masks':len(order),'exact_alias_count':raw_count-len(order),'evaluated_configurations':len(records),'raw_identity_sequence_sha256':rawh.hexdigest(),'unique_mask_set_sha256':root,'trade_parity':'PASS_EXACT','passed':len(passers),'passed_buy':sum(x['side']=='BUY' for x in passers),'passed_sell':sum(x['side']=='SELL' for x in passers),'passers':passers,'all_records':records,'future_pnl_read':False,'status':'PASS'}
  a.out.write_text(json.dumps(safe(obj),separators=(',',':'),allow_nan=False),encoding='utf-8');print(json.dumps({k:obj[k] for k in ['asset','shard','bars','raw_identities','unique_masks','exact_alias_count','evaluated_configurations','passed','passed_buy','passed_sell','trade_parity']},sort_keys=True))
if __name__=='__main__':main()
