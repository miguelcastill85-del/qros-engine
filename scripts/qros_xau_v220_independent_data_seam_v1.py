#!/usr/bin/env python3
"""Independent raw-tick / raw-bar / point-in-time canaries. No PnL; never mutates source."""
from __future__ import annotations
import hashlib, json, sys, zipfile, zlib
from pathlib import Path
import numpy as np

ROOT=Path('/mnt/data/qros_seed0076_delta_20260922')
DATA=Path('/mnt/data/qros_data_dev/XAUUSD_DEV_PACKED17_151382388.bin')
ZIP=Path('/mnt/data/QROS_SEED0076_XAU_DEV_QUOTE_ANOMALY_INDEX_20260922.zip')
BARS=ROOT/'bars_full'; IND=ROOT/'indicators_full'
DT=np.dtype([('ts','<i8'),('bid','<i4'),('ask','<i4'),('flags','u1')])
SOURCE_SHA='3ddb3c95acb9284196c5b6db84385271702800209ee33b1b1a2e1bd59cc9ff53'
ANOMALY_ZIP_MANIFEST_SHA='73049a78b1b45a47135e86dcc878511d0403d8626bcef53b91ffee820d684a36'
RANGE_CHECK=('M1','M5','M15')
TF_MINUTES={'M1':1,'M2':2,'M3':3,'M4':4,'M5':5,'M6':6,'M10':10,'M12':12,'M15':15,'M20':20,'M30':30,'H1':60,'H2':120,'H3':180,'H4':240,'D1':1440,'W1':10080}

def h256(raw):return hashlib.sha256(raw).hexdigest()
def qassert(cond,reason):
    if not cond:raise ValueError(reason)

def inspect_source(b,t,tf):
    lo,hi=int(b['first_source_index']),int(b['last_source_index'])
    qassert(0<=lo<=hi<len(t),'OUT_OF_SOURCE_RANGE')
    x=t[lo:hi+1];size=TF_MINUTES[tf]*60000
    if tf=='W1':
        days=x['ts']//86400000; src_bucket=(days-((days+3)%7))*86400000
    else:src_bucket=x['ts'] - np.remainder(x['ts'],size)
    got=(int(x['bid'][0]),int(np.max(x['bid'])),int(np.min(x['bid'])),int(x['bid'][-1]))
    exp=tuple(int(b[k]) for k in ['open_bid','high_bid','low_bid','close_bid'])
    qassert(got==exp,'SOURCE_BID_OHLC_MISMATCH')
    qassert(bool(np.all(src_bucket==int(b['bucket_ms']))),'SOURCE_BAR_MEMBERSHIP_MISMATCH')
    return hi-lo+1

def independent_canaries(t,barfiles):
    checked={};members={}
    for tf,p in barfiles.items():
        b=np.load(p,mmap_mode='r',allow_pickle=False)
        k=129 if tf=='M1' else 31 if tf in ('M5','M15') else 15
        rng=np.random.default_rng(515704 + len(tf)*11 + TF_MINUTES[tf])
        ix=np.unique(np.r_[0,1,len(b)-2,len(b)-1,rng.integers(0,len(b),k)])
        source_count=0
        for i in ix:source_count+=inspect_source(b[i],t,tf)
        completion_checks=0
        for i in ix:
            if i+1<len(b):
                qassert(int(b['last_source_index'][i])<int(b['first_source_index'][i+1]),'UNCLOSED_BAR_REUSE')
                completion_checks+=1
        checked[tf]={'direct_independent_raw_OHLC_and_bucket_tests':int(len(ix)),'causal_next_bar_checks':completion_checks,'observed_raw_tick_memberships':source_count,'first_source_index':int(b['first_source_index'][0]),'last_source_index':int(b['last_source_index'][-1])}
        members[tf]=b
    return checked,members

def contamination_index(members):
    with zipfile.ZipFile(ZIP) as z:
        manifest=json.loads(z.read('quote_index/manifest.json'))
        qassert(h256(z.read('quote_index/manifest.json'))==ANOMALY_ZIP_MANIFEST_SHA,'INDEX_MANIFEST_SHA_MISMATCH')
        record={}
        for group,name in [('crossed','crossed_quote_indices.u32le.zlib'),('zero','zero_spread_indices.u32le.zlib')]:
            meta=manifest['artifacts'][name];b=z.read('quote_index/'+name)
            qassert(h256(b)==meta['zlib_sha256'],'INDEX_PAYLOAD_ZLIB_SHA_MISMATCH')
            arr=np.frombuffer(zlib.decompress(b),dtype='<u4')
            qassert(len(arr)==meta['count'] and h256(arr.tobytes())==meta['raw_sha256'],'INDEX_UNPACKED_HASH_MISMATCH')
            qassert(bool(np.all(arr[1:]>arr[:-1])),'INDEX_NOT_STRICTLY_INCREASING')
            record[group]=arr
    out={}; masks={}
    for tf,b in members.items():
        n=len(b);x={}
        for group,idx in record.items():
            mapped=np.searchsorted(b['last_source_index'],idx.astype(np.int64),side='left')
            qassert(bool(np.all(mapped<n)),'INDEX_AFTER_LAST_BAR')
            qassert(bool(np.all(idx.astype(np.int64)>=b['first_source_index'][mapped])),'INDEX_FALLS_IN_GAP')
            bar_ix,cnt=np.unique(mapped,return_counts=True);mask=np.zeros(n,dtype=bool);mask[bar_ix]=True
            x[group]={'source_tick_count':int(len(idx)),'directly_affected_bars':int(len(bar_ix)),'max_anomalous_ticks_in_one_bar':int(cnt.max()) if len(cnt) else 0}
            masks[(tf,group)]=mask
        x['either_directly_affected_bars']=int(np.count_nonzero(masks[(tf,'crossed')]|masks[(tf,'zero')]))
        x['all_bars']=int(n)
        out[tf]=x
    p=ROOT/'XAU_QUOTE_ANOMALY_DIRECT_BAR_MEMBERSHIP_17TF.npz'
    np.savez_compressed(p,**{tf+'_'+name:arr for (tf,name),arr in masks.items()})
    out['index_file_sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
    out['index_file_name']=p.name
    return out

def point_in_time_canaries(members):
    sys.path.insert(0,'/mnt/data/qros_seed0076_exact_sources')
    from qros_seed0076_indicators_v220 import compute_all
    report={}
    for tf in RANGE_CHECK:
        b=members[tf];z=np.load(IND/f'XAUUSD_{tf}_INDICATORS.npz',allow_pickle=False)
        scale=0.01;h=b['high_bid'].astype(float)*scale;l=b['low_bid'].astype(float)*scale;c=b['close_bid'].astype(float)*scale
        r=compute_all(h,l,c)
        for k in ['EMA20','ATR14','RSI14','ADX14','CCI20','STOCH14_3']:
            qassert(np.array_equal(r[k],z[k],equal_nan=True),'ORIGINAL_INDICATOR_REPRO_MISMATCH_'+tf+'_'+k)
        cutoff=len(c)//3
        c2=c.copy();h2=h.copy();l2=l.copy()
        # Future-only perturbation. Preserve price geometry for altered future candles.
        c2[cutoff:]+=0.47;h2[cutoff:]+=0.48;l2[cutoff:]+=0.46
        modified=compute_all(h2,l2,c2)
        for k in r:
            qassert(np.array_equal(modified[k][:cutoff],r[k][:cutoff],equal_nan=True),'FUTURE_LEAK_'+tf+'_'+k)
        complete=z['completion_source_index'];expected=np.r_[b['first_source_index'][1:],[-1]]
        qassert(np.array_equal(complete,expected),'COMPLETION_SOURCE_INDEX_MISMATCH')
        report[tf]={'indicator_channel_count':len(r),'future_perturbation_cutoff_bar':cutoff,'earlier_values_unchanged':True,'real_cache_parity_channels':6,'completion_index_strict':bool(np.all(complete[:-1]>b['last_source_index'][:-1]))}
    return report

def main():
    qassert(DATA.stat().st_size==151382388*17,'SOURCE_LENGTH_DRIFT')
    digest=hashlib.sha256()
    with DATA.open('rb') as f:
        for chunk in iter(lambda:f.read(16*1024*1024),b''):digest.update(chunk)
    qassert(digest.hexdigest()==SOURCE_SHA,'SOURCE_SHA_DRIFT')
    ticks=np.memmap(DATA,dtype=DT,mode='r')
    bars={tf:BARS/f'XAUUSD_{tf}_BID_BARS.npy' for tf in TF_MINUTES}
    checks,mem=independent_canaries(ticks,bars)
    contamination=contamination_index(mem)
    temporal=point_in_time_canaries(mem)
    receipt={'schema':'QROS_SEED0076_XAU_DEV_RAW_INDEPENDENT_SEAM_1.0','source_dev_sha256':SOURCE_SHA,'source_records':len(ticks),'live_source_sha256_reverified':True,'scope':'DEV_ONLY_ALL_17_TF','direct_raw_tick_checks':checks,'anomaly_direct_membership':contamination,'future_perturbation_canaries':temporal,'errors':[],'scientific_status':'NON_ECONOMIC_CANARY_ONLY','broker_session_clock':'NOT_BOUND','economic_pnl_read':False,'holdout_open':False}
    p=ROOT/'XAU_DEV_RAW_INDEPENDENT_SEAM_RECEIPT.json';p.write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
    print('PASS_INDEPENDENT',sum(x['direct_independent_raw_OHLC_and_bucket_tests'] for x in checks.values()),'DIRECT_BARS','FUTURE_PERTURBATION',len(temporal),'TF','ANOMALIES',json.dumps({x:contamination[x] for x in ('M1','M5','M15')},sort_keys=True))
if __name__=='__main__':main()
