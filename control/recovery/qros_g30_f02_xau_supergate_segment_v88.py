#!/usr/bin/env python3
"""Extract complete G30 F02 XAU Supergate ledgers from verified temporal segments.
Frozen 28-candidate input V87. No retuning or parameter selection.
Baseline signals/execution require A/B exact parity. Stress/ablation use the certified A execution path.
"""
from __future__ import annotations
import argparse, hashlib, json, math, sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import qros_g30_xau_gate_a_v68 as c
from qros_g30_xau_outcome_b_fast_v71 import outcome_B_fast
import qros_g30_f02_xau_holdout_v86 as h86

INPUT_SHA='0df9eefe74d6fae5541a0c6de1fed9bb4a5bd9141d106242bf65bb8be25019ab'
SEGMENTS={
 'A_2018_2021':{
  'src_sha':'77da8423b07d7d33168d8b713ef691627f0698760461c7349fa5ccc5e49ceaeb',
  'cache_sha':'35abe473cfb9b02c51f525ccd3ef870bff51106005f94236e8197a9f4a2d8bfd',
  'start':0,'end':1640995200000},
 'B_2022_2024':{
  'src_sha':'39ad5cbd4c60b4b2d0579682f368dc2a5834a9481f45accf7c679e750999e3a7',
  'cache_sha':'ab350b3c6fe9e5ba897e8113964e9b4f561d04df04fd7d04ff4f3c32a174d987',
  'start':1640995200000,'end':1735689600000},
 'C_2025_2026':{
  'src_sha':'9a5a2b22e111b7005a41e7e66771decd5e31805f5b455f21e5b794a72822c26e',
  'cache_sha':'201918b3a6d1a116a369d8b0d64ef90f11c28738e86f2dbf8d3957c0127b0e2d',
  'start':1735689600000,'end':9223372036854775807}}

def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return h.hexdigest()

def pf(x): return c.pf(np.asarray(x,float))
def safe(v):
 if isinstance(v,float) and not math.isfinite(v):return 'INF' if v>0 else ('-INF' if v<0 else 'NAN')
 if isinstance(v,list):return [safe(x) for x in v]
 if isinstance(v,dict):return {k:safe(x) for k,x in v.items()}
 return v

def direction_base_A(o,hh,ll,cl,fam,n,side):
 if fam=='SHOCK_BAR_BODY_DIRECTION_ONLY':return (cl>o) if side=='BUY' else (cl<o)
 b,s=h86.base_A(hh,ll,cl,fam,n);return b if side=='BUY' else s

def shock_A(bucket,o,hh,ll,cl,atr,meas,timing,t):
 den=atr if timing=='CURRENT_BAR_INCLUDED' else np.r_[np.nan,atr[:-1]]
 num=h86.numerator_A(o,hh,ll,cl,meas);ratio=np.divide(num,den,out=np.full(len(cl),np.nan),where=np.isfinite(num)&np.isfinite(den)&(den>0))
 weekday=((bucket//86400000+3)%7)<5
 return (ratio>=t)&weekday

def metrics_for_mask(mask,out,mm,side,with_excursions=False,exc_cache=None):
 ch=c.select_A(mask,out[0],out[1]); et=out[0][ch];xt=out[1][ch];ei=out[2][ch];xi=out[3][ch];dist=out[4][ch];rr=out[5][ch].astype(float)
 if len(ch):
  spr=(mm['ask'][ei]-mm['bid'][ei]).astype(float)+(mm['ask'][xi]-mm['bid'][xi]).astype(float);extra=np.divide(spr,dist,out=np.zeros(len(spr)),where=dist>0)
 else:extra=np.empty(0,float)
 cons=rr-.5*extra;sev=rr-extra
 rec={'entry_t':et.tolist(),'exit_t':xt.tolist(),'entry_i':ei.tolist(),'exit_i':xi.tolist(),'distance':dist.tolist(),'r_c':rr.tolist(),'spread_extra_r':extra.tolist(),'r_k':cons.tolist(),'r_s':sev.tolist(),'n':int(len(ch)),'net_c':float(rr.sum()),'net_k':float(cons.sum()),'net_s':float(sev.sum()),'pf_c':pf(rr),'pf_k':pf(cons),'pf_s':pf(sev),'ledger_sha256':h86.ledger_sha(ch,out[0],out[1],out[5])}
 if with_excursions:
  maes=[];mfes=[]
  if exc_cache is None:exc_cache={}
  for E,X,D in zip(ei,xi,dist):
   entry=float(mm['ask'][E] if side=='BUY' else mm['bid'][E]); key=(side,int(E),int(X),float(D))
   if key in exc_cache: ma,mi=exc_cache[key]
   else:
    z=mm[int(E):int(X)+1]; ok=z['ask']>z['bid']
    if np.any(ok):
     if side=='BUY':path=(z['bid'][ok].astype(float)-entry)/float(D)
     else:path=(entry-z['ask'][ok].astype(float))/float(D)
     ma=max(0.0,float(-np.min(path)));mi=max(0.0,float(np.max(path)))
    else:ma=mi=0.0
    exc_cache[key]=(ma,mi)
   maes.append(ma);mfes.append(mi)
  rec['mae_r']=maes;rec['mfe_r']=mfes
 return rec

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--segment',choices=SEGMENTS,required=True);ap.add_argument('--src',type=Path,required=True);ap.add_argument('--cache',type=Path,required=True);ap.add_argument('--input',type=Path,required=True);ap.add_argument('--shard',required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();S=SEGMENTS[a.segment]
 if sha(a.src)!=S['src_sha']:raise SystemExit('SRC_SHA_MISMATCH')
 if sha(a.cache)!=S['cache_sha']:raise SystemExit('CACHE_SHA_MISMATCH')
 if sha(a.input)!=INPUT_SHA:raise SystemExit('INPUT_SHA_MISMATCH')
 I=json.load(open(a.input));qs=[q for q in I['candidates'] if q['representative'].split(':',1)[0]==a.shard]
 if not qs:raise SystemExit('NO_CANDIDATES')
 tfname,feat=a.shard.split('_');tf=60 if tfname=='H1' else int(tfname[1:]);step=np.int64(tf*60000)
 mm=np.memmap(a.src,dtype=c.DT,mode='r')
 with np.load(a.cache) as z:
  mb=z['mb'];ks=('bo','bh','bl','bc') if feat=='BID' else ('mo','mh','ml','mc');vals=[z[k] for k in ks]
  A=c.bars_A(mb,*vals,tf);B=c.bars_B(mb,*vals,tf)
  if c.digest_arrays(A)!=c.digest_arrays(B):raise SystemExit('BAR_PARITY_FAIL')
  atrA=c.atr_A(A[2],A[3],A[4]);atrB=c.atr_B(B[2],B[3],B[4]);period=((A[0]+step)>=S['start'])&((A[0]+step)<S['end'])
  masks={};abl_shock={};abl_dir={};u={'BUY':np.zeros(len(A[0]),bool),'SELL':np.zeros(len(A[0]),bool)};us={'BUY':np.zeros(len(A[0]),bool),'SELL':np.zeros(len(A[0]),bool)};ud={'BUY':np.zeros(len(A[0]),bool),'SELL':np.zeros(len(A[0]),bool)}
  for q in qs:
   rep=q['representative'];sh,side,key,tf2,fe2,meas,timing,t,fam,n=h86.parse_rep(rep)
   ma=h86.signal_A(*A,atrA,meas,timing,t,fam,n,side)&period; mbb=h86.signal_B(*B,atrB,meas,timing,t,fam,n,side)&period
   if not np.array_equal(ma,mbb):raise SystemExit('SIGNAL_PARITY_FAIL '+rep)
   masks[rep]=ma;u[side]|=ma
   dmask=direction_base_A(A[1],A[2],A[3],A[4],fam,n,side)&(((A[0]//86400000+3)%7)<5)&period
   smask=shock_A(*A,atrA,meas,timing,t)&period
   abl_shock[rep]=dmask;abl_dir[rep]=smask;us[side]|=dmask;ud[side]|=smask
  ex=[z[k] for k in ('eb','ebh','ebl','eah','eal','first','last')]
  outs={};del1={};del2={};osh={};odir={}
  for side,code in [('BUY',1),('SELL',-1)]:
   if u[side].any():
    oa=c.outcome_A(mm['ts'],mm['bid'],mm['ask'],A[0],atrA,step,*ex,u[side],code);ob=outcome_B_fast(mm['ts'],mm['bid'],mm['ask'],B[0],atrB,step,*ex,u[side],code)
    outs[side]=(oa,ob)
    # temporal sensitivity: shift the entire execution clock by 1 or 2 signal bars, preserving ATR/signal identity.
    del1[side]=c.outcome_A(mm['ts'],mm['bid'],mm['ask'],A[0]+step,atrA,step,*ex,u[side],code)
    del2[side]=c.outcome_A(mm['ts'],mm['bid'],mm['ask'],A[0]+2*step,atrA,step,*ex,u[side],code)
   if us[side].any():osh[side]=c.outcome_A(mm['ts'],mm['bid'],mm['ask'],A[0],atrA,step,*ex,us[side],code)
   if ud[side].any():odir[side]=c.outcome_A(mm['ts'],mm['bid'],mm['ask'],A[0],atrA,step,*ex,ud[side],code)
  exc_cache={};records=[]
  for q in qs:
   rep=q['representative'];side=q['direction'];oa,ob=outs[side];ca=c.select_A(masks[rep],oa[0],oa[1]);cb=c.select_B(masks[rep],ob[0],ob[1])
   if not np.array_equal(ca,cb):raise SystemExit('SELECT_PARITY_FAIL '+rep)
   if len(ca):
    for k in range(6):
     if not np.array_equal(oa[k][ca],ob[k][cb]):raise SystemExit('TRADE_PARITY_FAIL '+rep)
   base=metrics_for_mask(masks[rep],oa,mm,side,True,exc_cache)
   t1=metrics_for_mask(masks[rep],del1[side],mm,side,False)
   t2=metrics_for_mask(masks[rep],del2[side],mm,side,False)
   no_shock=metrics_for_mask(abl_shock[rep],osh[side],mm,side,False)
   no_dir=metrics_for_mask(abl_dir[rep],odir[side],mm,side,False)
   records.append({'cluster_id':q['cluster_id'],'representative':rep,'direction':side,'cluster_type':q['type'],'cluster_size':q['size'],'baseline':base,'delay_1bar':t1,'delay_2bar':t2,'ablation_no_shock':no_shock,'ablation_no_direction':no_dir})
 obj={'schema':'QROS_G30_F02_XAU_SUPERGATE_SEGMENT_V88_v1','status':'PASS','segment':a.segment,'period_start':S['start'],'period_end':S['end'],'shard':a.shard,'candidate_count':len(records),'source_sha256':S['src_sha'],'cache_sha256':S['cache_sha'],'input_sha256':INPUT_SHA,'signal_parity':'PASS_EXACT','baseline_trade_parity':'PASS_EXACT','records':records}
 a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(safe(obj),separators=(',',':'),allow_nan=False));print(json.dumps({'segment':a.segment,'shard':a.shard,'candidates':len(records),'status':'PASS_EXACT'}));print('bytes',a.out.stat().st_size,'sha256',sha(a.out))
if __name__=='__main__':main()
