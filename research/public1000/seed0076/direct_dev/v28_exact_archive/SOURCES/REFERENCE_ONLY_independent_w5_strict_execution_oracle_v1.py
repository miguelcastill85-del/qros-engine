#!/usr/bin/env python3
"""Ex ante signal-count stratified full-tick audit for the strict tie V209 cell.
This independent oracle uses original full-tick simulate not the event precomputation.
"""
import hashlib,json,sys,time
from pathlib import Path
import numpy as np
P=Path(__file__).parent;sys.path.insert(0,str(P))
from seed0076_direct_dev_backtest_v2 import DTYPE,simulate as full_tick
from direct_economic_event_cache_v1_1 import schedule_pure,DAY
from schedule_compact_candidate_days_v1 import schedule_compact
from direct_six_family_mask_batch_v1 import writejson
OUT=P/'direct_w5_strict_7family_dev_v1.tmp';tick=np.memmap('/mnt/data/seed0076_direct_dev/XAUUSD_DEV_PACKED17_151382388.bin',dtype=DTYPE,mode='r')
report={'schema':'QROS_SEED0076_DIRECT_M1_W5_STRICT_INDEPENDENT_FULL_TICK_ORACLE_V1','scope':'BUY_SELL_8_STRATIFIED_PHYSICAL_MASKS_EACH_PRE_PNL','period':'2018_2019_DEV_ALREADY_EXPOSED','holdout_open':False,'broker_commission_certified':False,'sides':{}}
for side,sign in (('BUY',1),('SELL',-1)):
 t0=time.perf_counter();t=np.load(OUT/(side+'_W5_STRICT_TRAJECTORIES.npz'),allow_pickle=False)
 a={k:t[k] for k in ('source_ix','stop_cents','entry_ix','exit_ix','entry_cents','exit_cents','risk_cents','state')};si=a['source_ix'];st=a['stop_cents']
 z=np.load(OUT/(side+'_W5_STRICT_UNIQUE_MASKS.npz'),allow_pickle=False);M=z['masks'];ids=z['mask_ids'];n=len(si)
 with (OUT/(side+'_W5_STRICT_PHYSICAL_CLASSES.jsonl')).open() as f:counts=np.fromiter((json.loads(r)['event_count'] for r in f),dtype=np.int64)
 order=np.argsort(counts,kind='stable');positive=np.flatnonzero(counts>0)
 chosen=list(dict.fromkeys([int(order[0]),int(positive[0]) if len(positive) else int(order[0]),int(order[len(order)//10]),int(order[len(order)//4]),int(order[len(order)//2]),int(order[3*len(order)//4]),int(order[9*len(order)//10]),int(order[-1])]))
 days=np.ascontiguousarray(tick['ts'][si]//DAY,dtype=np.int64);checks=[];total=0
 for k in chosen:
  ix=np.flatnonzero(np.unpackbits(M[k],bitorder='little')[:n]);r,rej,unresolved=full_tick(tick,si[ix],np.full(len(ix),sign,dtype=np.int8),st[ix],np.zeros(len(ix),dtype=np.int8),3)
  common=(si,ix,a['entry_ix'],a['exit_ix'],a['entry_cents'],a['exit_cents'],a['risk_cents'],a['state'],st,sign,3,True)
  old=schedule_pure(tick['ts'],*common);new=schedule_compact(days,*common)
  for label,got in (('SOURCE_EVENT_CACHE',old),('COMPACT_SCHEDULER',new)):
   if len(unresolved)!=0 or len(r)!=got[0] or not np.array_equal(rej[:6],got[5][:6]):raise RuntimeError('TRADE_COUNT_REJECT_'+label+'_'+side+'_'+str(k))
   for col in (1,2,3,4,5,6,7,9,10):
    if not np.array_equal(r[:,col],got[6][:,col]):raise RuntimeError('ORACLE_FIELDS_'+label+'_'+side+'_'+str(k)+'_'+str(col))
   if not np.allclose(r[:,8],got[6][:,8],rtol=0,atol=1e-14):raise RuntimeError('ORACLE_R_'+label+'_'+side+'_'+str(k))
  total+=len(r);checks.append({'physical_mask_id':str(ids[k]),'index':k,'signal_count':len(ix),'trades':len(r),'trade_sha256':hashlib.sha256(np.ascontiguousarray(r[:,1:]).astype('<f8').tobytes()).hexdigest()})
  print('W5_STRICT_FULL_TICK_PARITY_PASS',side,k,'signals',len(ix),'trades',len(r),flush=True)
 report['sides'][side]={'mask_cases':len(checks),'exact_full_tick_trade_rows':total,'checks':checks,'elapsed_seconds':round(time.perf_counter()-t0,3)}
print('ALL_W5_STRICT_INDEPENDENT_ORACLE_PASS',json.dumps({k:r['exact_full_tick_trade_rows'] for k,r in report['sides'].items()},sort_keys=True),flush=True)
report['status']='PASS'
writejson(OUT/'W5_STRICT_INDEPENDENT_FULL_TICK_ORACLE.json',report)
