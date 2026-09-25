#!/usr/bin/env python3
"""Exact frozen W5 V28 exploratory per-candidate path, reusable across masked configurations.
Each shard is independently SHA-addressed, read-back checked, restartable. Not Gate A.
"""
from __future__ import annotations
import os,json,hashlib,argparse,sys,time
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R));sys.path.insert(0,'/mnt/data/qros_nonstall_v23/work/legacy/source_pins')
from qros_w5_v28_frozen_exploratory_economic_kernel import precompute_trajectory
from qros_seed0076_structural_v220 import structural_states
T=np.dtype([('ts','<i8'),('bid','<i4'),('ask','<i4'),('flags','u1')]);PIN='18c19e3278843f5c38f17301549ee73b8c45215999ff861ea52fd70673398e26'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for q in iter(lambda:f.read(8<<20),b''):h.update(q)
 return h.hexdigest()
def json_atom(p,obj):
 t=p.with_suffix(p.suffix+'.partial');t.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n');os.replace(t,p)
def required():
 assert sha(R/'V28_EXPLORATORY_ECONOMIC_EXECUTION_FROZEN_BEFORE_PNL.json')==PIN
 e=json.load(open(R/'V28_EXECUTABLE_BAR_EXTREMA_RECEIPT.json'));assert sha(R/'V28_EXECUTABLE_BAR_EXTREMA.npz')==e['sha256']
 v=json.load(open(R/'V27_INDEPENDENT_ALL_22352_FULL10_BYTE_CLOSURE.json'));assert v['status']=='PASS' and v['semantic_configs_total']==22352
 return v
def build(ch,route,chunk,max_new):
 required();t0=time.monotonic();b=np.load(R/'XAUUSD_M1_VALID_BID_BARS_V24.npy',allow_pickle=False,mmap_mode='r');ticks=np.memmap(R/'XAUUSD_DEV_PACKED17_151382388.bin',dtype=T,mode='r');ex=np.load(R/'V28_EXECUTABLE_BAR_EXTREMA.npz',allow_pickle=False);minb=ex['minb'];maxa=ex['maxa']
 sign=1 if ch<4 else -1;side='BUY' if sign==1 else 'SELL';v=json.load(open(R/f'V27_EXECUTABLE_CANDIDATE_CH{ch}.json'));assert v['status'].startswith('PASS')
 z=np.load(R/f'W5_V27_EXECUTABLE_CANDIDATES_CH{ch}.npz',allow_pickle=False);k=route+'_source_idx';kb=route+'_bar';assert k in z and kb in z;si=z[k];bi=z[kb];ref=next(x for x in v['routes'] if x['route']==route)
 # Input stream exact V27 source-index/bar root as used by all 11176 mask generators.
 h=hashlib.sha256(np.stack([si,bi.astype(np.int64)],axis=1).tobytes()).hexdigest();assert h==ref['root_sha256']
 hi=b['high_bid'].astype(np.float64)*.01;lo=b['low_bid'].astype(np.float64)*.01;sh,sl,_,_=structural_states(hi,lo,5,0)
 x=(sl if sign==1 else sh)[bi]*100.;stop=np.empty(len(x),np.int32);ok=np.isfinite(x);stop[ok]=np.rint(x[ok]).astype(np.int32);stop[~ok]=np.iinfo(np.int32).max if sign==1 else 0
 out=R/f'V28_ECON_TAPE_CH{ch}_{route}';out.mkdir(exist_ok=True);receipts=[];made=0;total=(len(si)+chunk-1)//chunk
 for shard in range(total):
  s=shard*chunk;e=min(len(si),s+chunk);name=f'part{shard:03d}';rp=out/f'{name}_RECEIPT.json';op=out/f'{name}_TRAJECTORY.npz'
  if rp.exists():
   rec=json.load(open(rp));assert rec['begin']==s and rec['end']==e and rec['candidate_root']==h and rec['stop_rule']=='LATEST_CAUSAL_OPPOSITE_W5_FRACTAL' and sha(op)==rec['sha256'],('EXISTING_TRAJECTORY_SHA_DRIFT',rp)
   receipts.append({'path':rp.name,'sha256':sha(rp),'bytes':rp.stat().st_size});continue
  if op.exists():raise RuntimeError('UNVERIFIED_ORPHAN_TRAJECTORY_RECONCILE')
  path=precompute_trajectory(ticks['ts'],ticks['bid'],ticks['ask'],b['bucket_ms'],b['first_source_index'],b['last_source_index'],minb,maxa,si[s:e],stop[s:e],bi[s:e],sign)
  assert all(len(ar)==e-s for ar in path)
  entry_ix,exit_ix,entrypx,exitpx,risk,reason=path
  # Universal invariants, independent of future mask selection.
  good=(reason==4)|(reason==5)
  assert np.all((entry_ix[good]>=si[s:e][good])&(exit_ix[good]>=entry_ix[good])&(risk[good]>0))
  assert np.all((ticks['ask'][entry_ix[good]]>ticks['bid'][entry_ix[good]])&(ticks['bid'][entry_ix[good]]>0))
  assert np.all((ticks['ask'][exit_ix[good]]>ticks['bid'][exit_ix[good]])&(ticks['bid'][exit_ix[good]]>0))
  assert np.all(ticks['ts'][exit_ix[good]]//86400000==ticks['ts'][entry_ix[good]]//86400000),('OVERNIGHT_TRADE',ch,route,shard)
  tmp=op.with_suffix('.npz.partial')
  with open(tmp,'wb') as f:np.savez_compressed(f,entry_idx=entry_ix,exit_idx=exit_ix,entry_price=entrypx,exit_price=exitpx,risk=risk,reason=reason,stop=stop[s:e],source_idx=si[s:e],bar_idx=bi[s:e])
  os.replace(tmp,op)
  rec={'schema':'QROS_W5_V28_FROZEN_ONE_TRAJECTORY_SHARD','side':side,'channel':ch,'route':route,'part':shard,'begin':s,'end':e,'candidate_root':h,'sha256':sha(op),'bytes':op.stat().st_size,'reasons':np.bincount(reason,minlength=6).tolist(),'stop_rule':'LATEST_CAUSAL_OPPOSITE_W5_FRACTAL','execution':'ORIGINAL_EXPOSED_DEV_PROFILE_1930_EXPLORATORY_BID_ASK','holdout_open':False,'GA2_open':False,'Gate_A_approved':False,'broker_cost_certified':False,'elapsed_seconds':round(time.monotonic()-t0,3)};json_atom(rp,rec)
  receipts.append({'path':rp.name,'sha256':sha(rp),'bytes':rp.stat().st_size});made+=1
  json_atom(out/'PROGRESS.json',{'channel':ch,'route':route,'parts_verified':receipts,'target_parts':total,'candidate_root':h,'sequence':len(receipts),'last_end':e,'holdout_open':False})
  print(json.dumps({'status':'PASS_SHA_ONE_REAL_TRAJECTORY_SHARD','ch':ch,'route':route,'part':shard,'candidates':e-s,'elapsed':round(time.monotonic()-t0,2),'receipt_SHA256':sha(rp),'reasons':rec['reasons']}),flush=True)
  if max_new and made>=max_new:return
 assert len(receipts)==total
 man={'schema':'QROS_W5_V28_FULL_REAL_TRAJECTORY_ROUTE','status':'PASS','channel':ch,'side':side,'route':route,'source_candidates':len(si),'source_candidate_root':h,'chunk_size':chunk,'verified_shards':receipts,'original_model_kernel_sha256':sha(R/'qros_w5_v28_frozen_exploratory_economic_kernel.py'),'PnL_observed_from_unfiltered_candidate_tapes':False,'holdout_open':False,'GA2_open':False};json_atom(out/'FULL_TRAJECTORY_MANIFEST.json',man)
 print(json.dumps({'status':'PASS_FULL_ROUTE','ch':ch,'route':route,'candidate_count':len(si),'parts':total,'manifest_sha256':sha(out/'FULL_TRAJECTORY_MANIFEST.json'),'elapsed':round(time.monotonic()-t0,2)}),flush=True)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--channel',required=True,type=int,choices=range(8));ap.add_argument('--route',required=True,choices=['r0_w1','r1_w1','r1_w3','r1_w5','r2_w1','r2_w3','r2_w5']);ap.add_argument('--chunk-size',type=int,default=30000);ap.add_argument('--max-new-shards',type=int,default=2);a=ap.parse_args();build(a.channel,a.route,a.chunk_size,a.max_new_shards)
