#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,hashlib
from pathlib import Path
import numpy as np
from qros_seed0076_indicators_v220 import compute_all, EMA_PERIODS
TFS=('M1','M2','M3','M4','M5','M6','M10','M12','M15','M20','M30','H1','H2','H3','H4','D1','W1')

def arr_hash(a):
    a=np.ascontiguousarray(a);h=hashlib.sha256();mv=memoryview(a).cast('B')
    for i in range(0,len(mv),8*1024*1024):h.update(mv[i:i+8*1024*1024])
    return h.hexdigest()
def canonical_root(d):
    h=hashlib.sha256()
    for k in sorted(d):h.update(hashlib.sha256(k.encode()+b'\0'+bytes.fromhex(arr_hash(d[k]))).digest())
    return h.hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--asset',required=True);ap.add_argument('--point',type=float,required=True);ap.add_argument('--bar-dir',required=True);ap.add_argument('--out-dir',required=True);ap.add_argument('--receipt',required=True);a=ap.parse_args()
    bd=Path(a.bar_dir);out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True);res={};fail=[]
    for tf in TFS:
        b=np.load(bd/f'{a.asset}_{tf}_BID_BARS.npy',mmap_mode='r',allow_pickle=False); scale=float(a.point)
        h=b['high_bid'].astype(np.float64)*scale;l=b['low_bid'].astype(np.float64)*scale;c=b['close_bid'].astype(np.float64)*scale
        d=compute_all(h,l,c)
        completion=np.full(len(b),-1,dtype=np.int64)
        if len(b)>1:completion[:-1]=b['first_source_index'][1:]
        d['completion_source_index']=completion
        for name,x in d.items():
            if len(x)!=len(b):fail.append(f'{tf}:{name}:LEN')
        for name in ('ATR14','ATR50'):
            x=d[name];v=x[~np.isnan(x)]
            if np.any(v<0):fail.append(f'{tf}:{name}:NEG')
        for name in ('RSI14','STOCH14_RAW','STOCH14_3','ADX14'):
            x=d[name];v=x[~np.isnan(x)]
            if len(v) and (np.any(v< -1e-12) or np.any(v>100+1e-12)):fail.append(f'{tf}:{name}:RANGE')
        p=out/f'{a.asset}_{tf}_INDICATORS.npz';np.savez(p,**d)
        finite_first={}
        for k in ['ATR14','ATR50','RSI14','ROC5','CCI20','STOCH14_3','ADX14','EMA20','EMA35','EMA70','EMA105','EMA210']:
            ix=np.flatnonzero(~np.isnan(d[k]));finite_first[k]=int(ix[0]) if len(ix) else None
        res[tf]={'bars':int(len(b)),'content_root_sha256':canonical_root(d),'file':p.name,'file_bytes':p.stat().st_size,'finite_first':finite_first}
    receipt={'schema':'QROS_SEED0076_INDICATOR_CACHE_RECEIPT_1.0','status':'PASS' if not fail else 'FAIL','asset':a.asset,'point':a.point,'timeframes':res,'ema_periods':list(EMA_PERIODS),'formula_authority':'V210 plus pre-GA1 initialization closure V220','failures':fail,'economic_pnl_read':False,'holdout_open':False}
    raw=json.dumps(receipt,sort_keys=True,separators=(',',':')).encode();receipt['receipt_sha256']=hashlib.sha256(raw).hexdigest();Path(a.receipt).write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n');print(receipt['status'],a.asset,receipt['receipt_sha256']);return 0 if not fail else 2
if __name__=='__main__':raise SystemExit(main())
