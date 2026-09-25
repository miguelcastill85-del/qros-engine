#!/usr/bin/env python3
"""Deterministic pre-economic XAU W5 valid-quote M1 cache, no imputation.
Preserves exact raw source and previous historical original V220 bars unchanged.
"""
from __future__ import annotations
import sys,json,os,hashlib,pathlib,time
import numpy as np,numba as nb
r=pathlib.Path('/mnt/data/QROS_W5_REALDATA_20260924');sys.path.insert(0,str(r))
from qros_seed0076_indicators_v220 import compute_all
T=np.dtype([('ts','<i8'),('bid','<i4'),('ask','<i4'),('flags','u1')]);B=np.dtype([('bucket_ms','<i8'),('first_source_index','<i8'),('last_source_index','<i8'),('open_bid','<i4'),('high_bid','<i4'),('low_bid','<i4'),('close_bid','<i4')]);ticks=np.memmap(r/'XAUUSD_DEV_PACKED17_151382388.bin',dtype=T,mode='r');bars=np.load(r/'XAUUSD_M1_BID_BARS.npy',mmap_mode='r',allow_pickle=False)
@nb.njit(cache=True)
def derive(bid,ask,bb):
 o=np.empty(len(bb),np.int32);h=np.empty(len(bb),np.int32);l=np.empty(len(bb),np.int32);c=np.empty(len(bb),np.int32);n=np.zeros(len(bb),np.int32)
 for i in range(len(bb)):
  for j in range(bb['first_source_index'][i],bb['last_source_index'][i]+1):
   if bid[j]<=0 or ask[j]<=bid[j]:continue
   p=bid[j]
   if n[i]==0:o[i]=p;h[i]=p;l[i]=p
   else:
    if p>h[i]:h[i]=p
    if p<l[i]:l[i]=p
   c[i]=p;n[i]+=1
 return o,h,l,c,n
def sha(path):
 hh=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(8_388_608),b''):hh.update(b)
 return hh.hexdigest()
def save_npy(path,a):
 tmp=path.with_suffix(path.suffix+'.tmp')
 with tmp.open('wb') as f:np.save(f,a,allow_pickle=False);f.flush();os.fsync(f.fileno())
 os.replace(tmp,path)
def save_npz(path,d):
 tmp=path.with_suffix(path.suffix+'.tmp')
 with tmp.open('wb') as f:np.savez(f,**d);f.flush();os.fsync(f.fileno())
 os.replace(tmp,path)
start=time.monotonic();o,h,l,c,n=derive(ticks['bid'],ticks['ask'],bars);valid=n>0;assert np.count_nonzero(~valid)==27
clean=np.empty(np.count_nonzero(valid),dtype=B)
for field in ('bucket_ms','first_source_index','last_source_index'):clean[field]=bars[field][valid]
for field,arr in [('open_bid',o),('high_bid',h),('low_bid',l),('close_bid',c)]:clean[field]=arr[valid]
assert (clean['first_source_index'][0]==0) and (clean['last_source_index'][-1]==len(ticks)-1) and np.all(clean['first_source_index'][1:]>clean['last_source_index'][:-1])
assert np.all(clean['high_bid']>=np.maximum(clean['open_bid'],clean['close_bid'])) and np.all(clean['low_bid']<=np.minimum(clean['open_bid'],clean['close_bid']))
# Independent literal numpy quote reduction on 1024 fixed sample bars + ALL no-valid buckets.
rng=np.random.default_rng(20260924);indices=np.unique(np.r_[rng.choice(len(bars),size=1024,replace=False),np.flatnonzero(~valid)]);oracle_rows=0
for i in indices:
 starti=int(bars['first_source_index'][i]);endi=int(bars['last_source_index'][i])+1;x=ticks[starti:endi];good=(x['bid']>0)&(x['ask']>x['bid']);q=x['bid'][good]
 assert len(q)==int(n[i]),('QUOTE_COUNT',i)
 if len(q):assert (o[i],h[i],l[i],c[i])==(int(q[0]),int(q.max()),int(q.min()),int(q[-1])),('BAR_VALUE',i)
 oracle_rows+=1
p=r/'XAUUSD_M1_VALID_BID_BARS_V24.npy';save_npy(p,clean)
hh=clean['high_bid'].astype(np.float64)*.01;ll=clean['low_bid'].astype(np.float64)*.01;cc=clean['close_bid'].astype(np.float64)*.01;d=compute_all(hh,ll,cc);completion=np.full(len(clean),-1,dtype=np.int64);completion[:-1]=clean['first_source_index'][1:];d['completion_source_index']=completion
ip=r/'XAUUSD_M1_VALID_INDICATORS_V24.npz';save_npz(ip,d)
assert np.array_equal(completion[:-1],clean['first_source_index'][1:])
empty_indices=np.flatnonzero(~valid);rec={'schema':'QROS_W5_V24_SANITIZED_M1_AND_INDICATOR_CACHE','status':'PASS_REAL_QUOTES_AND_INDEPENDENT_1024_BAR_ORACLE','raw_sha256':'3ddb3c95acb9284196c5b6db84385271702800209ee33b1b1a2e1bd59cc9ff53','unchanged_original_bar_sha256':'35a8644644daab5fc04a218d5527c3839b5248471801f8a56ebb8a71a7457f59','M1_valid_bar_file_sha256':sha(p),'M1_valid_bar_bytes':p.stat().st_size,'M1_valid_indicator_file_sha256':sha(ip),'M1_valid_indicator_bytes':ip.stat().st_size,'M1_original_bars':len(bars),'M1_sanitized_bars':len(clean),'M1_invalid_only_bars_excluded':int(np.count_nonzero(~valid)),'M1_invalid_only_bar_bucket_ms':[int(z) for z in bars['bucket_ms'][empty_indices]],'independent_oracle_bars':oracle_rows,'no_lookahead_data_rollup':'next_first_source_bar_pinned','new_future_signal_data_source':True,'exposed_2018_2019_only':True,'broker_timezone_DST_certified':False,'economic_run_authorized':False,'holdout_open':False,'GA2_open':False,'elapsed_seconds':round(time.monotonic()-start,2)}
rr=r/'V24_SANITIZED_M1_CACHE_RECEIPT.json';tmp=rr.with_suffix('.tmp');tmp.write_text(json.dumps(rec,sort_keys=True,indent=2)+'\n');os.replace(tmp,rr)
print(json.dumps({k:rec[k] for k in ('status','M1_sanitized_bars','M1_invalid_only_bars_excluded','M1_valid_bar_file_sha256','M1_valid_indicator_file_sha256','independent_oracle_bars','elapsed_seconds')},sort_keys=True),flush=True)
