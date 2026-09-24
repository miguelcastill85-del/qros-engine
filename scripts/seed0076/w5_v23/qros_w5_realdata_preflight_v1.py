#!/usr/bin/env python3
"""Exact raw XAU DEV carrier SHA + quote audit for a materialized local copy.
No trading, no PnL, no holdout. Never certifies broker sessions or costs.
"""
from __future__ import annotations
import argparse,hashlib,json,pathlib,os
import numpy as np
PINS={
 'ticks':{'sha256':'3ddb3c95acb9284196c5b6db84385271702800209ee33b1b1a2e1bd59cc9ff53','bytes':2573500596,'rows':151382388},
 'bars':{'sha256':'35a8644644daab5fc04a218d5527c3839b5248471801f8a56bbb8a71a7457f59'},
 'indicators':{'sha256':'f30da86f6c11b5a6573b3571ffd3c3621bbe4d51134258c89d956d6f9ab115b5'} }
TICK=np.dtype([('ts','<i8'),('bid','<i4'),('ask','<i4'),('flags','u1')])
def streamhash(p):
 h=hashlib.sha256()
 with pathlib.Path(p).open('rb') as f:
  for part in iter(lambda:f.read(8*1024*1024),b''):h.update(part)
 return h.hexdigest()
def verify(path,pin):
 p=pathlib.Path(path)
 if not p.is_file():raise ValueError('EXACT_CARRIER_NOT_MATERIALIZED:'+str(p))
 if 'bytes' in pin and p.stat().st_size!=pin['bytes']:raise ValueError('EXACT_BYTES_MISMATCH:'+str(p))
 if streamhash(p)!=pin['sha256']:raise ValueError('EXACT_SHA256_MISMATCH:'+str(p))
 return p
def audit(ticks,bars,ind,chunk=2000000):
 pts=verify(ticks,PINS['ticks']);bp=verify(bars,PINS['bars']);ip=verify(ind,PINS['indicators'])
 raw=np.memmap(pts,mode='r',dtype=TICK)
 if len(raw)!=PINS['ticks']['rows']:raise ValueError('TICK_COUNT_DRIFT')
 stats={'total_rows':int(len(raw)),'zero_spread':0,'crossed_spread':0,'non_positive':0,'non_monotonic_time':0,'flag_0':0}
 prev_ts=None
 for left in range(0,len(raw),chunk):
  x=raw[left:left+chunk];bid=x['bid'];ask=x['ask'];ts=x['ts'];v=(bid>0)&(ask>0)
  stats['zero_spread']+=int(np.count_nonzero(v&(ask==bid)));stats['crossed_spread']+=int(np.count_nonzero(v&(ask<bid)))
  stats['non_positive']+=int(np.count_nonzero(~v));stats['flag_0']+=int(np.count_nonzero(x['flags']==0))
  stats['non_monotonic_time']+=int(np.count_nonzero(ts[1:]<ts[:-1]));
  if prev_ts is not None and int(ts[0])<prev_ts:stats['non_monotonic_time']+=1
  prev_ts=int(ts[-1])
 if stats['non_monotonic_time']:raise ValueError('NON_MONOTONIC_SOURCE_TS')
 b=np.load(bp,mmap_mode='r',allow_pickle=False);required={'first_source_index','last_source_index','bucket_ms','high_bid','low_bid'}
 if not required.issubset(set(b.dtype.names or ())):raise ValueError('BAR_SCHEMA_DRIFT')
 first=b['first_source_index'];last=b['last_source_index']
 if not len(b) or int(first[0])<0 or int(last[-1])>=len(raw) or np.any(first[1:]<=last[:-1]):raise ValueError('BAR_SOURCE_COVERAGE_DRIFT')
 if np.any(b['bucket_ms'][1:]<=b['bucket_ms'][:-1]):raise ValueError('BAR_TIME_ORDER_DRIFT')
 with np.load(ip,allow_pickle=False) as z:
  comp=z['completion_source_index']
  if len(comp)!=len(b) or not np.array_equal(comp[:-1],first[1:]) or comp[-1]!=-1:raise ValueError('INDICATOR_COMPLETION_ALIGNMENT_DRIFT')
 return {'status':'REAL_DEV_CARRIER_SHA_AND_BASIC_QUOTE_AUDIT_PASS','data_SHA256':{k:v['sha256'] for k,v in PINS.items()},
   'source_server_clock':'SOURCE_LABELS_UNVERIFIED_BROKER_DST_CALENDAR_STILL_REQUIRED','quote_issues':stats,'M1_bar_count':len(b),'M1_completion_alignment':'PASS',
   'invalid_quote_execution_guard':'REQUIRED_EXCLUDE_ON_REAL_TICK_RUN','broker_calendar_certified':False,'broker_commission_certified':False,
   'full_10_family_tick_retest_parity':'PENDING','holdout_open':False,'GA2_open':False,'economic_run_authorized':False}
def main():
 p=argparse.ArgumentParser();p.add_argument('--ticks',required=True);p.add_argument('--bars',required=True);p.add_argument('--indicators',required=True);p.add_argument('--out',required=True);a=p.parse_args()
 try:
  result=audit(a.ticks,a.bars,a.indicators);out=pathlib.Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
  tmp=out.with_suffix(out.suffix+'.tmp');tmp.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n');os.replace(tmp,out)
  print(json.dumps({'status':result['status'],'economic_run_authorized':False}))
 except Exception as exc:
  print(json.dumps({'status':'FAIL_CLOSED','reason':str(exc),'economic_run_authorized':False}));raise SystemExit(3)
if __name__=='__main__':main()
