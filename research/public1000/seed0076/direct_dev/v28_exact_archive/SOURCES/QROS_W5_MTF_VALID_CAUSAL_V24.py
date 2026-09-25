#!/usr/bin/env python3
"""W5 exact valid quote derived M5/M15 caches and independent no-lookahead MTF index checks."""
import pathlib,sys,json,hashlib,os,time,bisect
import numpy as np
r=pathlib.Path('/mnt/data/QROS_W5_REALDATA_20260924');sys.path.insert(0,str(r));sys.path.insert(0,str(pathlib.Path('/mnt/data/qros_nonstall_v23/work')))
from qros_seed0076_indicators_v220 import compute_all
from qros_w5_mtf_causal_adapter_v1 import causal_context_index
B=np.dtype([('bucket_ms','<i8'),('first_source_index','<i8'),('last_source_index','<i8'),('open_bid','<i4'),('high_bid','<i4'),('low_bid','<i4'),('close_bid','<i4')]);old=np.load(r/'XAUUSD_M1_VALID_BID_BARS_V24.npy',mmap_mode='r',allow_pickle=False)
def aggregate(m1,minutes):
 step=np.int64(minutes*60000);bucket=(m1['bucket_ms']//step)*step;starts=np.r_[0,np.flatnonzero(bucket[1:]!=bucket[:-1])+1];ends=np.r_[starts[1:]-1,len(bucket)-1];out=np.empty(len(starts),dtype=B)
 out['bucket_ms']=bucket[starts];out['first_source_index']=m1['first_source_index'][starts];out['last_source_index']=m1['last_source_index'][ends];out['open_bid']=m1['open_bid'][starts];out['high_bid']=np.maximum.reduceat(m1['high_bid'],starts);out['low_bid']=np.minimum.reduceat(m1['low_bid'],starts);out['close_bid']=m1['close_bid'][ends]
 return out
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8_388_608),b''):h.update(b)
 return h.hexdigest()
def save(path,writer):
 tmp=path.with_suffix(path.suffix+'.tmp')
 with tmp.open('wb') as f:writer(f);f.flush();os.fsync(f.fileno())
 os.replace(tmp,path)
start=time.monotonic();tapes=np.load(r/'W5_VALID_QUOTE_RAW_AND_REARM_TAPES_V24.npz',allow_pickle=False);ad=tapes['admitted_idx'];offs=tapes['admitted_offsets'];rng=np.random.default_rng(20260924);all_receipts={};checked=0
for tf,m in [('M5',5),('M15',15)]:
 b=aggregate(old,m);p=r/f'XAUUSD_{tf}_VALID_BID_BARS_V24.npy';save(p,lambda f:np.save(f,b,allow_pickle=False));h=b['high_bid'].astype(float)*.01;l=b['low_bid'].astype(float)*.01;c=b['close_bid'].astype(float)*.01;d=compute_all(h,l,c);comp=np.full(len(b),-1,np.int64);comp[:-1]=b['first_source_index'][1:];d['completion_source_index']=comp;ip=r/f'XAUUSD_{tf}_VALID_INDICATORS_V24.npz';save(ip,lambda f:np.savez(f,**d))
 # Compare corrected v2.3 adapter with wholly independent Python bisect_right and exact first source completion inclusive.
 candidates=ad[offs[0]:offs[1]]
 if len(candidates)>1500:candidates=candidates[rng.choice(len(candidates),1500,replace=False)]
 completion=comp[:-1].tolist();got=causal_context_index(b,candidates)
 for idx,v in zip(candidates,got):
  expected=bisect.bisect_right(completion,int(idx))-1
  assert int(v)==expected and (expected<0 or completion[expected]<=int(idx)),('LOOKAHEAD_OR_LAG',tf,int(idx),int(v),expected)
 firsts=b['first_source_index'][1:];actual=causal_context_index(b,firsts);want=np.arange(len(firsts));assert np.array_equal(actual,want),('EXACT_MTF_COMPLETION_BOUNDARY',tf)
 assert np.all(b['bucket_ms'][1:]>b['bucket_ms'][:-1]) and np.all(b['first_source_index'][1:]>b['last_source_index'][:-1])
 checked+=len(candidates)+len(firsts)
 all_receipts[tf]={'bars':len(b),'source_first_idx':int(b['first_source_index'][0]),'source_last_idx':int(b['last_source_index'][-1]),'bar_SHA256':sha(p),'indicators_SHA256':sha(ip),'indicators_series':len(d),'independent_bisect_exact_samples':len(candidates),'all_exact_completion_source_boundaries_checked':len(firsts)}
receipt={'schema':'QROS_W5_V24_REALDATA_MTF_CAUSAL_VALID_CACHE','status':'PASS_VALID_QUOTE_M5_M15_AND_NO_LOOKAHEAD_BOUNDARY','parent_M1_valid_bar_SHA256':'8fed642eb3f948a9e0612d7b9b0ece453a71b32e41609a8fcc84ee41bd713b13','M5_M15':all_receipts,'independent_total_checks':checked,'clock':'RAW_SOURCE_LABELS_NO_INFERRED_UTC','broker_timezone_certified':False,'economic_run_authorized':False,'holdout_open':False,'GA2_open':False,'elapsed_seconds':round(time.monotonic()-start,2)}
p=r/'V24_MTF_VALID_CACHE_AND_INDEPENDENT_CAUSAL_PARITY.json';tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n');os.replace(tmp,p);print(json.dumps(receipt,sort_keys=True),flush=True)
