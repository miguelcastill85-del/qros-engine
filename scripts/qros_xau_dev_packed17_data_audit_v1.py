#!/usr/bin/env python3
"""XAUUSD frozen DEV PACKED17 structural data audit, no broker-timezone assumptions.

Read-only 2M-row vectorized chunks. Bid/Ask raw int32 values are NOT rescaled.
Zero/crossed spreads are counted and preserved, never filled or imputed.
"""
import argparse,hashlib,json,os
from pathlib import Path
import numpy as np

ROWS=151382388
BYTES=2573500596
SHA='3ddb3c95acb9284196c5b6db84385271702800209ee33b1b1a2e1bd59cc9ff53'
DTYPE=np.dtype([('timestamp_ms','<u8'),('bid_raw','<i4'),('ask_raw','<i4'),('flags','u1')],align=False)
assert DTYPE.itemsize==17
PART_BOUNDARIES=[0,20000000,40000000,60000000,80000000,100000000,120000000,140000000,ROWS-1]

def canonical(o):return json.dumps(o,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def sha_file(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(4<<20),b''):h.update(b)
 return h.hexdigest()

def audit(input_path,output_path,chunk_rows=2000000):
 p=Path(input_path);out=Path(output_path)
 if p.stat().st_size!=BYTES:raise RuntimeError('SOURCE_SIZE_MISMATCH')
 if sha_file(p)!=SHA:raise RuntimeError('SOURCE_SHA_MISMATCH')
 a=np.memmap(p,dtype=DTYPE,mode='r',shape=(ROWS,))
 counts={'nonmonotonic_timestamp':0,'same_timestamp_adjacent':0,'exact_duplicate_adjacent':0,
     'nonpositive_bid':0,'nonpositive_ask':0,'crossed_quotes':0,'zero_spread':0,
     'gap_gt_1_minute':0,'gap_gt_1_hour':0,'gap_gt_1_day':0}
 hist=np.zeros(1001,dtype=np.uint64);flags=np.zeros(256,dtype=np.uint64)
 minimum={'timestamp_ms':int(a[0]['timestamp_ms']),'bid_raw':int(a[0]['bid_raw']),
          'ask_raw':int(a[0]['ask_raw']),'spread_raw':2**31-1}
 maximum={'timestamp_ms':int(a[0]['timestamp_ms']),'bid_raw':int(a[0]['bid_raw']),
          'ask_raw':int(a[0]['ask_raw']),'spread_raw':-2**31}
 prev=None;max_gap=0;crossed_samples=[];zero_samples=[];backward_samples=[]
 for start in range(0,ROWS,chunk_rows):
  end=min(ROWS,start+chunk_rows)
  sl=a[start:end]
  ts=sl['timestamp_ms'].astype('int64',copy=False)
  bid=sl['bid_raw'];ask=sl['ask_raw'];flag=sl['flags']
  spread=ask.astype('int64')-bid.astype('int64')
  counts['nonpositive_bid']+=int(np.count_nonzero(bid<=0))
  counts['nonpositive_ask']+=int(np.count_nonzero(ask<=0))
  counts['crossed_quotes']+=int(np.count_nonzero(spread<0))
  counts['zero_spread']+=int(np.count_nonzero(spread==0))
  if len(crossed_samples)<5:
   for i in np.flatnonzero(spread<0)[:5-len(crossed_samples)]:
    crossed_samples.append({'row':int(start+i),'ts_ms':int(ts[i]),'bid':int(bid[i]),'ask':int(ask[i])})
  if len(zero_samples)<5:
   for i in np.flatnonzero(spread==0)[:5-len(zero_samples)]:
    zero_samples.append({'row':int(start+i),'ts_ms':int(ts[i]),'bid':int(bid[i]),'ask':int(ask[i])})
  vals=spread[(spread>=0)&(spread<=999)]
  hist[:1000]+=np.bincount(vals.astype(np.int32),minlength=1000).astype(np.uint64)
  hist[1000]+=np.count_nonzero(spread>=1000)
  flags+=np.bincount(flag.astype(np.int32),minlength=256).astype(np.uint64)
  minimum['timestamp_ms']=min(minimum['timestamp_ms'],int(ts.min()))
  maximum['timestamp_ms']=max(maximum['timestamp_ms'],int(ts.max()))
  for label,v in [('bid_raw',bid),('ask_raw',ask),('spread_raw',spread)]:
   minimum[label]=min(minimum[label],int(v.min()));maximum[label]=max(maximum[label],int(v.max()))
  if prev is None:
   differences=np.diff(ts)
  else:
   differences=np.diff(ts,prepend=prev[0])
  counts['nonmonotonic_timestamp']+=int(np.count_nonzero(differences<0))
  counts['same_timestamp_adjacent']+=int(np.count_nonzero(differences==0))
  counts['gap_gt_1_minute']+=int(np.count_nonzero(differences>60000))
  counts['gap_gt_1_hour']+=int(np.count_nonzero(differences>3600000))
  counts['gap_gt_1_day']+=int(np.count_nonzero(differences>86400000))
  max_gap=max(max_gap,int(differences.max()))
  if len(backward_samples)<5:
   for i in np.flatnonzero(differences<0)[:5-len(backward_samples)]:backward_samples.append({'row':int(start+i),'ts_ms':int(ts[i])})
  # Equality includes ALL four fields; same timestamp with different prices is not exact duplicate.
  if prev is None:
   counts['exact_duplicate_adjacent']+=int(np.count_nonzero((ts[1:]==ts[:-1])&(bid[1:]==bid[:-1])&(ask[1:]==ask[:-1])&(flag[1:]==flag[:-1])))
  else:
   counts['exact_duplicate_adjacent']+=int((int(ts[0]),int(bid[0]),int(ask[0]),int(flag[0]))==prev)
   counts['exact_duplicate_adjacent']+=int(np.count_nonzero((ts[1:]==ts[:-1])&(bid[1:]==bid[:-1])&(ask[1:]==ask[:-1])&(flag[1:]==flag[:-1])))
  prev=(int(ts[-1]),int(bid[-1]),int(ask[-1]),int(flag[-1]))
  if (end//chunk_rows)%10==0 or end==ROWS:
   print(canonical({'rows_scanned':end,'total_rows':ROWS,'crossed':counts['crossed_quotes'],'zero_spread':counts['zero_spread']}),flush=True)
 boundary=[{'index':n,'timestamp_ms':int(a[n]['timestamp_ms']),'bid_raw':int(a[n]['bid_raw']),'ask_raw':int(a[n]['ask_raw']),'flags':int(a[n]['flags'])} for n in PART_BOUNDARIES]
 result={'schema':'QROS_SEED0076_XAU_DEV_PACKED17_RAW_AUDIT_1.0','status':'PASS_DATA_IDENTITY_SCAN_WITH_QUOTE_CLASSIFICATION',
    'rows_scanned':ROWS,'raw_bytes':BYTES,'raw_sha256':SHA,'record_dtype':'<u8 timestamp_ms, <i4 bid_raw, <i4 ask_raw, u1 flags',
    'price_scale':'UNBOUND_NO_ASSUMPTION','broker_timezone':'UNBOUND_NO_ASSUMPTION',
    'adjacent_counts':counts,'minima':minimum,'maxima':maximum,'max_gap_ms':max_gap,
    'spread_histogram_0_to_999_raw':{str(i):int(v) for i,v in enumerate(hist[:1000]) if v},
    'spread_raw_gte_1000':int(hist[1000]),
    'flag_counts':{str(i):int(v) for i,v in enumerate(flags) if v},
    'examples':{'crossed':crossed_samples,'zero_spread':zero_samples,'backwards':backward_samples},
    'part_boundaries':boundary,
    'scientific_limits':{'no_imputation':True,'no_quote_repair':True,'no_time_zone_inference':True,
      'no_economic_pnl':True,'no_mask_replay':True,'holdout_open':False,
      'zero_spread_trades_authorized':False,'negative_spread_trades_authorized':False}}
 if counts['nonmonotonic_timestamp']!=0:result['status']='FAIL_NONMONOTONIC_TIMESTAMP'
 out.parent.mkdir(parents=True,exist_ok=True);temp=out.with_suffix('.json.new')
 with temp.open('w') as f:
  f.write(json.dumps(result,indent=2,sort_keys=True)+'\n');f.flush();os.fsync(f.fileno())
 os.replace(temp,out)
 print(canonical({k:result[k] for k in ('status','rows_scanned','raw_sha256','adjacent_counts','minima','maxima','max_gap_ms','flag_counts')}),flush=True)
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args();audit(a.input,a.output)
