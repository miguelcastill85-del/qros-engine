#!/usr/bin/env python3
"""Pre-result fixed economic oracle: original historical frozen trace vs independent V2 on real DEV ticks.
Deterministic candidate-signal position sample; no strategy selection, no holdout.
"""
from __future__ import annotations
import sys,pathlib,json,hashlib,os,numpy as np
R=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(R))
from qros_w5_v28_frozen_exploratory_economic_kernel import schedule_pure
from REFERENCE_ONLY_seed0076_direct_dev_backtest_v2 import simulate
T=np.dtype([('ts','<i8'),('bid','<i4'),('ask','<i4'),('flags','u1')])
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return h.hexdigest()
def part(ch,route):
 p=R/f'V28_ECON_TAPE_CH{ch}_{route}/FULL_TRAJECTORY_MANIFEST.json';j=json.load(open(p)); assert j['status']=='PASS'
 vals={k:[] for k in ['entry_idx','exit_idx','entry_price','exit_price','risk','reason','stop','source_idx']}
 for z in j['verified_shards']:
  rec=json.load(open(p.parent/z['path']));a=p.parent/f"part{rec['part']:03d}_TRAJECTORY.npz"; assert sha(a)==rec['sha256']
  with np.load(a,allow_pickle=False) as d:
   for k in vals:vals[k].append(d[k])
 return {k:np.concatenate(v) for k,v in vals.items()}
def main():
 assert json.load(open(R/'V27_INDEPENDENT_ALL_22352_FULL10_BYTE_CLOSURE.json'))['status']=='PASS'
 ticks=np.memmap(R/'XAUUSD_DEV_PACKED17_151382388.bin',dtype=T,mode='r');results=[]
 # Fix side×route source of two model-independent signal universes. Never inspect R to choose canaries.
 for ch,route,which in [(0,'r0_w1',7),(4,'r0_w1',7),(0,'r1_w3',0),(4,'r2_w1',0)]:
  d=part(ch,route);s=1 if ch<4 else -1;side='BUY' if s==1 else 'SELL'
  key=(route+'_batch000' if route=='r0_w1' and ch in (0,4) else route)+'_PHYSICAL_MASKS.npz';f=R/f'V27_FULL10_PRE_ECON_CH{ch}'/key
  with np.load(f,allow_pickle=False) as z:
   i=min(which,len(z['masks'])-1);bit=np.unpackbits(z['masks'][i],bitorder='little')[:len(d['source_idx'])]
  sel=np.flatnonzero(bit)
  # ex ante every k-th filtered signal, sample at most 32 across full exposed period, not by realized R
  keep=sel[np.unique(np.linspace(0,len(sel)-1,min(len(sel),32),dtype=np.int64))] if len(sel) else sel
  rv=schedule_pure(ticks['ts'],d['source_idx'],keep,d['entry_idx'],d['exit_idx'],d['entry_price'],d['exit_price'],d['risk'],d['reason'],d['stop'],s,3,True)
  ref,rej,bad=simulate(ticks,d['source_idx'][keep],np.full(len(keep),s,np.int8),d['stop'][keep],keep,3)
  assert not len(bad),('DIRECT_ORACLE_UNRESOLVED',ch,route)
  assert len(ref)==rv[0] and int(rv[5][5])==0,('REAL_TICK_TRADE_COUNT',ch,route,len(ref),rv[0])
  assert np.array_equal(ref[:,[0,1,2,3,4,5,6,7,9,10]],rv[6][:,[0,1,2,3,4,5,6,7,9,10]])
  assert np.allclose(ref[:,8],rv[6][:,8],atol=1e-14,rtol=0)
  # V2 cfg_idx stores candidate selection global source coordinate as provided
  assert np.array_equal(rv[5][:6],rej[:6]),('REAL_TICK_REJECTION_PARITY',ch,route,rv[5],rej)
  results.append({'channel':ch,'side':side,'route':route,'predeclared_physical_index':i,'source_signal_candidates_in_full_mask':len(sel),'sampled_candidates_before_PnL_look':len(keep),'exact_real_executions':len(ref),'fields_compared':len(ref)*11,'rejected_counts':rej[:6].tolist()})
 receipt={'schema':'QROS_W5_V28_EXANTE_STRATIFIED_INDEPENDENT_FULL_REAL_TICK_TRADE_PARITY_V1','status':'PASS','tests':results,'total_real_trades_independently_equal':sum(z['exact_real_executions'] for z in results),'all_11_fields_compared':sum(z['fields_compared'] for z in results),'broker_commission_certified':False,'development':'2018_2019_EXPOSED','holdout_open':False,'GA2_open':False,'gate_A_approved':False}
 out=R/'V28_INDEPENDENT_EXANTE_STRATIFIED_REAL_TICK_TRADE_CANARY_RECEIPT.json';tmp=out.with_suffix('.partial');tmp.write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n');os.replace(tmp,out)
 print(json.dumps({'status':'PASS_INDEPENDENT_FULL_REAL_TICK_TRADE_PARITY','cases':len(results),'trades':receipt['total_real_trades_independently_equal'],'fields':receipt['all_11_fields_compared'],'receipt_sha256':sha(out),'details':results}))
if __name__=='__main__':main()
