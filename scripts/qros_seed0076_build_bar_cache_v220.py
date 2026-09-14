#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, hashlib, os
from pathlib import Path
import numpy as np

TICK_DTYPE=np.dtype([('ts','<i8'),('bid','<i4'),('ask','<i4'),('flags','u1')])
BAR_DTYPE=np.dtype([('bucket_ms','<i8'),('first_source_index','<i8'),('last_source_index','<i8'),('open_bid','<i4'),('high_bid','<i4'),('low_bid','<i4'),('close_bid','<i4')])
TF_MINUTES={'M1':1,'M2':2,'M3':3,'M4':4,'M5':5,'M6':6,'M10':10,'M12':12,'M15':15,'M20':20,'M30':30,'H1':60,'H2':120,'H3':180,'H4':240,'D1':1440}
WEEK_MS=7*86400000
DAY_MS=86400000

def sha256_file(path:Path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''): h.update(b)
    return h.hexdigest()

def bucket_intraday(ts,minutes):
    step=np.int64(minutes*60000)
    return (ts//step)*step

def bucket_week(ts):
    d=ts//DAY_MS
    monday=d-((d+3)%7)
    return monday*DAY_MS

def _reduce_sorted(keys, first_idx, last_idx, o, h, l, c):
    starts=np.r_[0, np.flatnonzero(keys[1:]!=keys[:-1])+1]
    ends=np.r_[starts[1:]-1, len(keys)-1]
    out=np.empty(len(starts),dtype=BAR_DTYPE)
    out['bucket_ms']=keys[starts]
    out['first_source_index']=first_idx[starts]
    out['last_source_index']=last_idx[ends]
    out['open_bid']=o[starts]
    out['close_bid']=c[ends]
    out['high_bid']=np.maximum.reduceat(h,starts)
    out['low_bid']=np.minimum.reduceat(l,starts)
    return out

def build_m1(tick_path:Path, chunk_records:int=8_000_000):
    mm=np.memmap(tick_path,dtype=TICK_DTYPE,mode='r')
    n=len(mm); pieces=[]; carry=None; pos=0
    while pos<n:
        end=min(n,pos+chunk_records); x=mm[pos:end]
        keys=bucket_intraday(x['ts'],1)
        global_idx=np.arange(pos,end,dtype=np.int64)
        bars=_reduce_sorted(keys,global_idx,global_idx,x['bid'],x['bid'],x['bid'],x['bid'])
        if carry is not None:
            if len(bars) and carry['bucket_ms']==bars[0]['bucket_ms']:
                merged=np.empty(1,dtype=BAR_DTYPE)
                merged[0]['bucket_ms']=carry['bucket_ms']; merged[0]['first_source_index']=carry['first_source_index']; merged[0]['last_source_index']=bars[0]['last_source_index']
                merged[0]['open_bid']=carry['open_bid']; merged[0]['high_bid']=max(int(carry['high_bid']),int(bars[0]['high_bid'])); merged[0]['low_bid']=min(int(carry['low_bid']),int(bars[0]['low_bid'])); merged[0]['close_bid']=bars[0]['close_bid']
                bars[0]=merged[0]
            else:
                pieces.append(np.array([carry],dtype=BAR_DTYPE))
        if len(bars):
            if len(bars)>1: pieces.append(bars[:-1].copy())
            carry=bars[-1].copy()
        pos=end
    if carry is not None: pieces.append(np.array([carry],dtype=BAR_DTYPE))
    return np.concatenate(pieces) if pieces else np.empty(0,dtype=BAR_DTYPE)

def aggregate_from_m1(m1,tf):
    if tf=='M1': return m1
    keys=bucket_week(m1['bucket_ms']) if tf=='W1' else bucket_intraday(m1['bucket_ms'],TF_MINUTES[tf])
    return _reduce_sorted(keys,m1['first_source_index'],m1['last_source_index'],m1['open_bid'],m1['high_bid'],m1['low_bid'],m1['close_bid'])

def save_bar(path:Path,bars):
    np.save(path,bars,allow_pickle=False)

def content_root(bars):
    h=hashlib.sha256(); mv=memoryview(np.ascontiguousarray(bars)).cast('B')
    for i in range(0,len(mv),8*1024*1024): h.update(mv[i:i+8*1024*1024])
    return h.hexdigest()

def validate(bars):
    if len(bars)==0: return ['EMPTY']
    err=[]
    if np.any(bars['bucket_ms'][1:]<=bars['bucket_ms'][:-1]): err.append('NON_INCREASING_BUCKET')
    if np.any(bars['first_source_index']>bars['last_source_index']): err.append('INDEX_ORDER')
    if np.any(bars['first_source_index'][1:]<=bars['last_source_index'][:-1]): err.append('SOURCE_OVERLAP')
    if np.any(bars['high_bid']<np.maximum(bars['open_bid'],bars['close_bid'])): err.append('HIGH_INVALID')
    if np.any(bars['low_bid']>np.minimum(bars['open_bid'],bars['close_bid'])): err.append('LOW_INVALID')
    return err

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--asset',required=True); ap.add_argument('--ticks',required=True); ap.add_argument('--out-dir',required=True); ap.add_argument('--receipt',required=True); a=ap.parse_args()
    out=Path(a.out_dir); out.mkdir(parents=True,exist_ok=True); ticks=Path(a.ticks)
    m1=build_m1(ticks); tfs=list(TF_MINUTES)+['W1']; results={}; failures=[]
    for tf in tfs:
        b=aggregate_from_m1(m1,tf); e=validate(b); failures.extend([tf+':'+x for x in e])
        p=out/f'{a.asset}_{tf}_BID_BARS.npy'; save_bar(p,b)
        results[tf]={'bars':int(len(b)),'content_sha256':content_root(b),'first_bucket_ms':int(b['bucket_ms'][0]),'last_bucket_ms':int(b['bucket_ms'][-1]),'first_source_index':int(b['first_source_index'][0]),'last_source_index':int(b['last_source_index'][-1]),'file':p.name,'file_bytes':p.stat().st_size,'file_sha256':sha256_file(p)}
    receipt={'schema':'QROS_SEED0076_BAR_CACHE_RECEIPT_1.0','status':'PASS' if not failures else 'FAIL','asset':a.asset,'tick_file':ticks.name,'tick_bytes':ticks.stat().st_size,'tick_records':ticks.stat().st_size//17,'bar_semantics':'source-server civil anchors; BID OHLC; missing intervals omitted; completed bar availability is next bar first_source_index','timeframes':results,'failures':failures,'economic_pnl_read':False,'holdout_open':False}
    raw=json.dumps(receipt,sort_keys=True,separators=(',',':')).encode(); receipt['receipt_sha256']=hashlib.sha256(raw).hexdigest(); Path(a.receipt).write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
    print(receipt['status'],a.asset,'M1',len(m1),'receipt',receipt['receipt_sha256']); return 0 if not failures else 2
if __name__=='__main__': raise SystemExit(main())
