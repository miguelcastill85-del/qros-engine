#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,hashlib
from pathlib import Path
import numpy as np
from qros_seed0076_build_bar_cache_v220 import TICK_DTYPE,BAR_DTYPE,TF_MINUTES,bucket_intraday,bucket_week

def choose(n,k=31):
    if n<=k: return list(range(n))
    return sorted(set([0,1,n-2]+[int(i*(n-2)/(k-1)) for i in range(k)]))

def direct_m1(ticks,b):
    s=int(b['first_source_index']);e=int(b['last_source_index']);x=ticks[s:e+1]; key=int(b['bucket_ms'])
    return (np.all(bucket_intraday(x['ts'],1)==key) and int(x['bid'][0])==int(b['open_bid']) and int(x['bid'].max())==int(b['high_bid']) and int(x['bid'].min())==int(b['low_bid']) and int(x['bid'][-1])==int(b['close_bid']))

def aggregate_m1(m1,b,tf):
    key=int(b['bucket_ms']); keys=bucket_week(m1['bucket_ms']) if tf=='W1' else bucket_intraday(m1['bucket_ms'],TF_MINUTES[tf])
    ix=np.flatnonzero(keys==key)
    if not len(ix): return False
    x=m1[ix]
    return (int(x[0]['first_source_index'])==int(b['first_source_index']) and int(x[-1]['last_source_index'])==int(b['last_source_index']) and int(x[0]['open_bid'])==int(b['open_bid']) and int(x['high_bid'].max())==int(b['high_bid']) and int(x['low_bid'].min())==int(b['low_bid']) and int(x[-1]['close_bid'])==int(b['close_bid']))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--asset',required=True);ap.add_argument('--ticks',required=True);ap.add_argument('--bar-dir',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    ticks=np.memmap(a.ticks,dtype=TICK_DTYPE,mode='r'); bd=Path(a.bar_dir); m1=np.load(bd/f'{a.asset}_M1_BID_BARS.npy',mmap_mode='r',allow_pickle=False)
    failures=[]; checks=0
    for i in choose(len(m1),101):
        checks+=1
        if not direct_m1(ticks,m1[i]): failures.append(f'M1_DIRECT:{i}')
        if i<len(m1)-1 and not (int(m1[i+1]['first_source_index'])>int(m1[i]['last_source_index'])): failures.append(f'M1_CAUSAL_NEXT:{i}')
    for tf in list(TF_MINUTES)+['W1']:
        if tf=='M1': continue
        b=np.load(bd/f'{a.asset}_{tf}_BID_BARS.npy',mmap_mode='r',allow_pickle=False)
        for i in choose(len(b),31):
            checks+=1
            if not aggregate_m1(m1,b[i],tf): failures.append(f'{tf}_AGG:{i}')
    receipt={'schema':'QROS_SEED0076_BAR_CACHE_INDEPENDENT_ORACLE_1.0','status':'PASS' if not failures else 'FAIL','asset':a.asset,'checks':checks,'failures':failures,'method':'M1 selected bars recomputed directly from source ticks; higher timeframes selected bars independently recomputed from M1 members by canonical bucket; causal source-index monotonicity checked','economic_pnl_read':False,'holdout_open':False}
    raw=json.dumps(receipt,sort_keys=True,separators=(',',':')).encode();receipt['receipt_sha256']=hashlib.sha256(raw).hexdigest();Path(a.out).write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n');print(receipt['status'],checks,len(failures),receipt['receipt_sha256']);return 0 if not failures else 2
if __name__=='__main__':raise SystemExit(main())
