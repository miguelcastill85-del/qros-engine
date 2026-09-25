#!/usr/bin/env python3
"""Pre-PnL synthetic causal economic-engine parity, exact field-by-field vs independent full-tick V2.
No real tick economics are observed. Old exploratory 19:30 profile preserved.
"""
from __future__ import annotations
import pathlib,sys,hashlib,json,datetime as dt
import numpy as np
R=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(R))
from qros_w5_v28_frozen_exploratory_economic_kernel import bar_valid_extrema,precompute_trajectory,schedule_pure,DAY
from REFERENCE_ONLY_seed0076_direct_dev_backtest_v2 import simulate
T=np.dtype([('ts','<i8'),('bid','<i4'),('ask','<i4'),('flags','u1')]);B=np.dtype([('bucket_ms','<i8'),('first_source_index','<i8'),('last_source_index','<i8')])
def main():
 days=[dt.date(2018,1,d) for d in (24,25,26,29,30)];t=[]
 for d in days:
  epoch=(d-dt.date(1970,1,1)).days*DAY
  for m in range(35,20*60+30):
   j=len(t);bid=135000+int(250*np.sin(j/39)+85*np.cos(j/21))+((m//73)%5)*29;ask=bid+6+(j%17==0)*20
   if j%113==0:ask=bid # hard zero-spread fixture
   if j%997==0:ask=bid-1 # crossed fixture
   if m%143==0:bid+=160;ask=bid+11 # gap fixture
   t.append((epoch+m*60000+1000,bid,ask,4))
 ticks=np.array(t,dtype=T);n=len(ticks);bars=np.empty(n,dtype=B);bars['bucket_ms']=(ticks['ts']//60000)*60000;bars['first_source_index']=np.arange(n);bars['last_source_index']=np.arange(n)
 assert np.all(ticks['ts'][1:]>ticks['ts'][:-1]);mn,mx=bar_valid_extrema(ticks['bid'],ticks['ask'],bars['first_source_index'],bars['last_source_index'])
 counts=[];all_fields=0
 for side in (1,-1):
  # 157 ex ante candidate positions include all five days, preopen, flat and invalid quote cases.
  picks=np.unique(np.r_[np.arange(0,n,37),np.arange(0,n,113),np.arange(15,n,211)]).astype(np.int64)
  stops=(ticks['bid'][picks]-160 if side==1 else ticks['ask'][picks]+160).astype(np.int32);bar_idx=picks.astype(np.int32)
  tr=precompute_trajectory(ticks['ts'],ticks['bid'],ticks['ask'],bars['bucket_ms'],bars['first_source_index'],bars['last_source_index'],mn,mx,picks,stops,bar_idx,side)
  selected=np.arange(len(picks),dtype=np.int64);got=schedule_pure(ticks['ts'],picks,selected,*tr,stops,side,3,True)
  ref,rej,bad=simulate(ticks,picks,np.full(len(picks),side,np.int8),stops,np.arange(len(picks),dtype=np.int64),3)
  assert len(bad)==0,('UNRESOLVED_SYNTHETIC',side,bad)
  assert len(ref)==got[0] and not got[5][5],('TRADE_COUNT_OR_EXIT',side,len(ref),got[0],got[5])
  assert np.array_equal(ref[:,[0,1,2,3,4,5,6,7,9,10]],got[6][:,[0,1,2,3,4,5,6,7,9,10]]),('INDEPENDENT_EVENT_PARITY',side)
  assert np.allclose(ref[:,8],got[6][:,8],atol=1e-14,rtol=0),('R_PARITY',side)
  assert np.array_equal(rej[:6],got[5][:6]),('REJECTION_PARITY',side,rej,got[5])
  # Independent direct oracle is unrelated to the precomputed transaction cache implementation.
  counts.append({'side':'BUY' if side==1 else 'SELL','synthetic_candidate_signals':len(picks),'trade_by_trade_11_field_parity_count':len(ref),'reject_counts':rej[:6].tolist(),'quote_violations_in_trades':int(sum(1 for row in got[6] if ticks['ask'][int(row[3])]<=ticks['bid'][int(row[3])]))});all_fields+=len(ref)*11
  assert counts[-1]['quote_violations_in_trades']==0
 j={'schema':'QROS_W5_V28_INDEPENDENT_ECONOMIC_KERNEL_SYNTHETIC_PARITY_V1','status':'PASS_BID_ASK_NO_OVERNIGHT_MAX3_PER_DAY_11_FIELDS','tests':counts,'all_fields_checked':all_fields,'economic_model':'EXPOSED_DEV_1930_SERVER_STOP_OPPOSITE_FRACTAL_NO_TP_NO_COMMISSION','V2_independent_source_SHA256':hashlib.sha256((R/'REFERENCE_ONLY_seed0076_direct_dev_backtest_v2.py').read_bytes()).hexdigest(),'cached_economic_kernel_SHA256':hashlib.sha256((R/'qros_w5_v28_frozen_exploratory_economic_kernel.py').read_bytes()).hexdigest(),'real_dev_economic_PnL_read':False,'broker_cost_certified':False,'holdout_open':False,'GA2_open':False}
 path=R/'V28_EXPLORATORY_ECONOMIC_SYNTHETIC_ORACLE_RECEIPT.json';path.write_text(json.dumps(j,indent=2,sort_keys=True)+'\n');print(json.dumps({'status':j['status'],'side_tests':len(counts),'total_trades_checked':sum(x['trade_by_trade_11_field_parity_count'] for x in counts),'fields':all_fields},sort_keys=True),flush=True)
if __name__=='__main__':main()
