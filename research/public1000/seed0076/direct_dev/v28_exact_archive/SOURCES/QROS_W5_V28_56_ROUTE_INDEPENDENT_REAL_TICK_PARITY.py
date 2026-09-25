#!/usr/bin/env python3
"""Deterministic outcome-blind independent V2 full-real-tick parity on every W5 V27 causal route.
Each channel has an atomic SHA-addressed receipt. No selecting winning configurations.
"""
from __future__ import annotations
import numpy as np,os,hashlib,json,argparse,pathlib,sys
R=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(R))
from REFERENCE_ONLY_seed0076_direct_dev_backtest_v2 import simulate
from qros_w5_v28_frozen_exploratory_economic_kernel import schedule_pure
T=np.dtype([('ts','<i8'),('bid','<i4'),('ask','<i4'),('flags','u1')]);ROUTES=('r0_w1','r1_w1','r1_w3','r1_w5','r2_w1','r2_w3','r2_w5')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(8<<20),b''):h.update(chunk)
 return h.hexdigest()
def atom(p,x):
 t=p.with_suffix(p.suffix+'.partial');t.write_text(json.dumps(x,indent=2,sort_keys=True,allow_nan=False)+'\n');os.replace(t,p)
def tape(ch,route):
 p=R/f'V28_ECON_TAPE_CH{ch}_{route}/FULL_TRAJECTORY_MANIFEST.json';m=json.load(open(p));assert m['status']=='PASS' and m['source_candidates']>=0
 fields=('entry_idx','exit_idx','entry_price','exit_price','risk','reason','stop','source_idx');d={x:[] for x in fields}
 for item in m['verified_shards']:
  recp=p.parent/item['path'];assert sha(recp)==item['sha256'];v=json.load(open(recp));fn=p.parent/f"part{v['part']:03d}_TRAJECTORY.npz";assert sha(fn)==v['sha256']
  with np.load(fn,allow_pickle=False) as z:
   for field in fields:d[field].append(z[field])
 return {k:np.concatenate(v) for k,v in d.items()},m

def run(ch):
 o=R/f'V28_56_ROUTE_INDEPENDENT_CANARY_CH{ch}.json';side='BUY' if ch<4 else 'SELL';s=1 if ch<4 else -1
 if o.exists():
  r=json.load(open(o));assert r['channel']==ch and r['status']=='PASS_ALL_SEVEN_REAL_FULL_TICK_ROUTES';print(json.dumps({'status':'PASS_REUSE_INDEPENDENT_SHA','channel':ch,'sha256':sha(o),'cases':len(r['tests'])}));return
 t=np.memmap(R/'XAUUSD_DEV_PACKED17_151382388.bin',dtype=T,mode='r');tests=[];n=0;fields=0;rejections=0
 for route in ROUTES:
  d,man=tape(ch,route);candidate=R/f'W5_V27_EXECUTABLE_CANDIDATES_CH{ch}.npz'
  with np.load(candidate,allow_pickle=False) as z:
   assert np.array_equal(z[route+'_source_idx'],d['source_idx'])
  src=R/f'V27_FULL10_PRE_ECON_CH{ch}';key=('r0_w1_batch000' if ch in (0,4) and route=='r0_w1' else route)
  pj=[json.loads(line) for line in (src/f'{key}_PHYSICAL.jsonl').read_text().splitlines()]
  # First, median and last active physical masks by deterministic ordinal only; no PnL access.
  eligible=[i for i,x in enumerate(pj) if x['accepted_signal_count']>=16]
  if not eligible:eligible=[i for i,x in enumerate(pj) if x['accepted_signal_count']>0]
  assert eligible,('UNEXPECTED_ALL_EMPTY_FILTER_ROUTE',ch,route)
  selected_idx=sorted(set([eligible[0],eligible[len(eligible)//2],eligible[-1]]))
  with np.load(src/f'{key}_PHYSICAL_MASKS.npz',allow_pickle=False) as z:
   assert str(z['candidate_root_sha256'])==man['source_candidate_root']
   for pi in selected_idx:
    x=pj[pi];bits=np.unpackbits(z['masks'][pi],bitorder='little')[:len(d['source_idx'])];hits=np.flatnonzero(bits);assert len(hits)==x['accepted_signal_count']
    sel=hits[np.unique(np.linspace(0,len(hits)-1,min(len(hits),16),dtype=np.int64))]
    got=schedule_pure(t['ts'],d['source_idx'],sel,d['entry_idx'],d['exit_idx'],d['entry_price'],d['exit_price'],d['risk'],d['reason'],d['stop'],s,3,True)
    brute,rej,bad=simulate(t,d['source_idx'][sel],np.full(len(sel),s,np.int8),d['stop'][sel],sel,3)
    assert not len(bad) and len(brute)==got[0] and got[5][5]==0,('COUNT_OR_UNRESOLVED',ch,route,pi)
    assert np.array_equal(brute[:,[0,1,2,3,4,5,6,7,9,10]],got[6][:,[0,1,2,3,4,5,6,7,9,10]]),('FULL_TICK_FIELD_DRIFT',ch,route,pi)
    assert np.allclose(brute[:,8],got[6][:,8],rtol=0,atol=1e-14)
    assert np.array_equal(rej[:6],got[5][:6]),('DIRECT_TICK_REJECT_PARITY',ch,route,pi)
    n+=len(brute);fields+=len(brute)*11;rejections+=int(np.sum(rej[:6]));tests.append({'route':route,'mask_ordinal':pi,'physical_mask_id':x['physical_mask_id'],'independent_source_signals':len(sel),'trade_by_trade_exact':len(brute),'fields_equal':len(brute)*11,'rejections_equal':True})
 # Independent real max3/day edge test on the original same route raw candidate stream (not a filtered strategy):
 d,m=tape(ch,'r0_w1');day=t['ts'][d['source_idx']]//86400000;groups=np.flatnonzero((day==day[np.searchsorted(day,day[len(day)//2])]))
 if len(groups)<16:
  unique,cnt=np.unique(day,return_counts=True);focus=unique[np.argmax(cnt)];groups=np.flatnonzero(day==focus)
 ix=groups[:min(len(groups),200)];real=schedule_pure(t['ts'],d['source_idx'],ix,d['entry_idx'],d['exit_idx'],d['entry_price'],d['exit_price'],d['risk'],d['reason'],d['stop'],s,3,True)
 ref,rej,bad=simulate(t,d['source_idx'][ix],np.full(len(ix),s,np.int8),d['stop'][ix],ix,3)
 assert len(ref)==real[0] and not len(bad) and np.array_equal(ref[:,[0,1,2,3,4,5,6,7,9,10]],real[6][:,[0,1,2,3,4,5,6,7,9,10]]) and np.allclose(ref[:,8],real[6][:,8],rtol=0,atol=1e-14) and np.array_equal(rej[:6],real[5][:6])
 assert real[0]<=3 and np.all(real[6][:,10]==real[6][0,10]) if real[0] else True
 r={'schema':'QROS_W5_V28_INDEPENDENT_REAL_TICK_FULL56_ROUTE_PARITY_ONE_CHANNEL','status':'PASS_ALL_SEVEN_REAL_FULL_TICK_ROUTES','channel':ch,'side':side,'route_coverage':list(ROUTES),'tests':tests,'independent_real_trades':n,'exact_trade_fields':fields,'exact_rejections':rejections,'real_max3_per_day_raw_candidate_canary':{'candidate_count':len(ix),'trades':int(real[0]),'cap_rejections':int(real[5][2]),'independent_parity':'PASS'},'independent_V2_SHA256':sha(R/'REFERENCE_ONLY_seed0076_direct_dev_backtest_v2.py'),'holdout_open':False,'GA2_open':False,'broker_commission_certified':False}
 atom(o,r);print(json.dumps({'result':'PASS_REAL_7_ROUTE_INDEPENDENT_ORACLE','channel':ch,'tests':len(tests),'trades':n,'fields':fields,'max3_real_candidate_case':r['real_max3_per_day_raw_candidate_canary'],'receipt_sha256':sha(o)}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--channel',type=int,choices=range(8),required=True);a=p.parse_args();run(a.channel)
