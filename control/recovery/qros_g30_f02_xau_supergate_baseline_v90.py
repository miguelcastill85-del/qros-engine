#!/usr/bin/env python3
"""Baseline-only, dual-parity G30 F02 XAU Supergate extractor.
Infrastructure optimization: computes the complete frozen-rule baseline ledger only.
Later expensive latency/ablation/MAE-MFE tests are reserved for candidates that survive
all baseline-derived hard gates. No scientific rule or threshold is changed.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np
import qros_g30_f02_xau_supergate_segment_v88 as v

def base(mask,out,mm):
 ch=v.c.select_A(mask,out[0],out[1]);et=out[0][ch];xt=out[1][ch];ei=out[2][ch];xi=out[3][ch];dist=out[4][ch];rr=out[5][ch].astype(float)
 if len(ch):
  spr=(mm['ask'][ei]-mm['bid'][ei]).astype(float)+(mm['ask'][xi]-mm['bid'][xi]).astype(float);extra=np.divide(spr,dist,out=np.zeros(len(spr)),where=dist>0)
 else:extra=np.empty(0,float)
 k=rr-.5*extra;s=rr-extra
 return {'entry_t':et.tolist(),'exit_t':xt.tolist(),'entry_i':ei.tolist(),'exit_i':xi.tolist(),'distance':dist.tolist(),'r_c':rr.tolist(),'spread_extra_r':extra.tolist(),'r_k':k.tolist(),'r_s':s.tolist(),'n':int(len(ch)),'net_c':float(rr.sum()),'net_k':float(k.sum()),'net_s':float(s.sum()),'pf_c':v.pf(rr),'pf_k':v.pf(k),'pf_s':v.pf(s),'ledger_sha256':v.h86.ledger_sha(ch,out[0],out[1],out[5])}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--segment',choices=v.SEGMENTS,required=True);ap.add_argument('--src',type=Path,required=True);ap.add_argument('--cache',type=Path,required=True);ap.add_argument('--input',type=Path,required=True);ap.add_argument('--shard',required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();S=v.SEGMENTS[a.segment]
 if v.sha(a.src)!=S['src_sha']:raise SystemExit('SRC_SHA_MISMATCH')
 if v.sha(a.cache)!=S['cache_sha']:raise SystemExit('CACHE_SHA_MISMATCH')
 if v.sha(a.input)!=v.INPUT_SHA:raise SystemExit('INPUT_SHA_MISMATCH')
 I=json.load(open(a.input));qs=[q for q in I['candidates'] if q['representative'].split(':',1)[0]==a.shard]
 if not qs:raise SystemExit('NO_CANDIDATES')
 tfname,feat=a.shard.split('_');tf=60 if tfname=='H1' else int(tfname[1:]);step=np.int64(tf*60000);mm=np.memmap(a.src,dtype=v.c.DT,mode='r')
 with np.load(a.cache) as z:
  mb=z['mb'];ks=('bo','bh','bl','bc') if feat=='BID' else ('mo','mh','ml','mc');vals=[z[k] for k in ks];A=v.c.bars_A(mb,*vals,tf);B=v.c.bars_B(mb,*vals,tf)
  if v.c.digest_arrays(A)!=v.c.digest_arrays(B):raise SystemExit('BAR_PARITY_FAIL')
  atrA=v.c.atr_A(A[2],A[3],A[4]);atrB=v.c.atr_B(B[2],B[3],B[4]);period=((A[0]+step)>=S['start'])&((A[0]+step)<S['end'])
  masks={};u={x:np.zeros(len(A[0]),bool) for x in ('BUY','SELL')}
  for q in qs:
   rep=q['representative'];_,side,_,_,_,meas,timing,t,fam,n=v.h86.parse_rep(rep);ma=v.h86.signal_A(*A,atrA,meas,timing,t,fam,n,side)&period;mbb=v.h86.signal_B(*B,atrB,meas,timing,t,fam,n,side)&period
   if not np.array_equal(ma,mbb):raise SystemExit('SIGNAL_PARITY_FAIL '+rep)
   masks[rep]=ma;u[side]|=ma
  ex=[z[k] for k in ('eb','ebh','ebl','eah','eal','first','last')];outs={}
  for side,code in [('BUY',1),('SELL',-1)]:
   if u[side].any():
    oa=v.c.outcome_A(mm['ts'],mm['bid'],mm['ask'],A[0],atrA,step,*ex,u[side],code);ob=v.outcome_B_fast(mm['ts'],mm['bid'],mm['ask'],B[0],atrB,step,*ex,u[side],code);outs[side]=(oa,ob)
  recs=[]
  for q in qs:
   rep=q['representative'];side=q['direction'];oa,ob=outs[side];ca=v.c.select_A(masks[rep],oa[0],oa[1]);cb=v.c.select_B(masks[rep],ob[0],ob[1])
   if not np.array_equal(ca,cb):raise SystemExit('SELECT_PARITY_FAIL '+rep)
   if len(ca):
    for k in range(6):
     if not np.array_equal(oa[k][ca],ob[k][cb]):raise SystemExit('TRADE_PARITY_FAIL '+rep)
   recs.append({'cluster_id':q['cluster_id'],'representative':rep,'direction':side,'cluster_type':q['type'],'cluster_size':q['size'],'baseline':base(masks[rep],oa,mm)})
 obj={'schema':'QROS_G30_F02_XAU_SUPERGATE_BASELINE_V90_v1','status':'PASS','segment':a.segment,'period_start':S['start'],'period_end':S['end'],'shard':a.shard,'candidate_count':len(recs),'source_sha256':S['src_sha'],'cache_sha256':S['cache_sha'],'input_sha256':v.INPUT_SHA,'signal_parity':'PASS_EXACT','trade_parity':'PASS_EXACT','records':recs}
 a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(v.safe(obj),separators=(',',':'),allow_nan=False));print(json.dumps({'segment':a.segment,'shard':a.shard,'candidates':len(recs),'status':'PASS_EXACT'}));print('bytes',a.out.stat().st_size,'sha256',v.sha(a.out))
if __name__=='__main__':main()
