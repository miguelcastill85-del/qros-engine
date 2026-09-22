#!/usr/bin/env python3
"""Read-only, no-PnL XAU M1 clock/data-boundary verifier against frozen V212/V219.
Source epoch milliseconds encode DARWINEX SERVER CIVIL LABELS, not UTC instants.
The script never rewrites ticks, bars, session masks or frozen scientific authorities.
"""
from __future__ import annotations
import argparse, hashlib, json
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np

FROZEN={
    'data_sha256':'3ddb3c95acb9284196c5b6db84385271702800209ee33b1b1a2e1bd59cc9ff53',
    'bar_sha256':'35a8644644daab5fc04a218d5527c3839b5248471801f8a56ebb8a71a7457f59',
    'anomaly_index_sha256':'57b2efaa7c3234bd17284eb87d67fa5066187924ba122a20ab006f9bb9e9c70b',
    'clock_policy_git_blob_sha1':'c16d561b66a51d3735960470ba893e53e6913d40',
    'session_policy_git_blob_sha1':'e841166c558c93a15fef16f174e55449b1f8164d',
    'expected_m1_bars':681772,
}
UTC=timezone.utc
NY=ZoneInfo('America/New_York')
TICK_DTYPE=np.dtype([('ts','<i8'),('bid','<i4'),('ask','<i4'),('flags','u1')])
class AuditError(RuntimeError): pass

def require(v,msg):
    if not v:raise AuditError(msg)

def file_sha256(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for c in iter(lambda:f.read(8*1024*1024),b''):h.update(c)
    return h.hexdigest()

def server_ms_label(ms):
    return datetime.fromtimestamp(int(ms)/1000,UTC).replace(tzinfo=None)

def server_clock_resolve(label):
    """Use frozen source-server civil = NY wall +7h; infer true instant via NY IANA."""
    nywall=label-timedelta(hours=7)
    ny=nywall.replace(tzinfo=NY)
    utc=ny.astimezone(UTC)
    require(utc.astimezone(NY).replace(tzinfo=None)==nywall,'NY_WALL_ROUNDTRIP_FAIL')
    offset=(label-utc.replace(tzinfo=None)).total_seconds()/3600
    require(offset in (2.0,3.0),'INVALID_SERVER_UTC_OFFSET')
    require((offset==3.0)==(ny.utcoffset()==timedelta(hours=-4)),'US_DST_OFFSET_MISMATCH')
    return {'server_label':label.isoformat(timespec='milliseconds'),
            'ny_civil':ny.isoformat(timespec='milliseconds'),
            'actual_utc':utc.isoformat(timespec='milliseconds'),
            'server_utc_offset_hours':int(offset)}

def audit(bars_path,ticks_path,anomaly_path,include_data_hash=False):
    bars_path,ticks_path,anomaly_path=map(Path,(bars_path,ticks_path,anomaly_path))
    require(file_sha256(bars_path)==FROZEN['bar_sha256'],'BAR_SHA256_DRIFT')
    require(file_sha256(anomaly_path)==FROZEN['anomaly_index_sha256'],'ANOMALY_SHA256_DRIFT')
    ticks=np.memmap(ticks_path,dtype=TICK_DTYPE,mode='r')
    require(ticks_path.stat().st_size==2573500596 and len(ticks)==151382388,'TICK_LEN_DRIFT')
    if include_data_hash: require(file_sha256(ticks_path)==FROZEN['data_sha256'],'DEV_SHA256_DRIFT')
    b=np.load(bars_path,mmap_mode='r',allow_pickle=False)
    require(len(b)==FROZEN['expected_m1_bars'],'M1_COUNT_DRIFT')
    ts=b['bucket_ms'];first=b['first_source_index'];last=b['last_source_index']
    require(bool(np.all(np.diff(ts)>0)),'BAR_TIME_REGRESSION')
    require(int(first[0])==0 and int(last[-1])==len(ticks)-1,'BAR_SOURCE_BOUNDARY_DRIFT')
    require(bool(np.all(first[1:]==last[:-1]+1)),'BAR_SOURCE_GAP_OR_OVERLAP')
    require(bool(np.all(ticks['ts'][first]//60000*60000==ts)),'FIRST_TICK_BUCKET_MISMATCH')
    require(bool(np.all(ticks['ts'][last]//60000*60000==ts)),'LAST_TICK_BUCKET_MISMATCH')
    require(bool(np.all(ticks['ts'][first]<=ticks['ts'][last])),'SOURCE_TIME_REVERSE')
    days=ts//86400000
    weekdays=(days+3)%7 # 0 Monday, 4 Friday
    minute=(ts%86400000)//60000
    outside=(weekdays>4)|(minute<61)|((weekdays==4)&(minute>=1435))
    early=np.flatnonzero(outside)
    special=early[(weekdays[early]<5)&(minute[early]==60)]
    require(len(early)==len(special),'UNEXPECTED_OUT_OF_SESSION_BAR')
    with np.load(anomaly_path,allow_pickle=False) as a:
        cross=a['M1_crossed'];zero=a['M1_zero']
        require(cross.shape==zero.shape==(len(b),),'ANOMALY_M1_SHAPE_DRIFT')
        early_cross=int(cross[early].sum());early_zero=int(zero[early].sum())
    # Test EVERY source-server civil trading day once, not just a handful of DST samples.
    unique_days=np.unique(days)
    offsets=Counter()
    for d in unique_days:
        # 12:00 source label maps to 05:00 NY on the same day; no market at the DST switch.
        noon=datetime.fromtimestamp(int(d)*86400,UTC).replace(tzinfo=None)+timedelta(hours=12)
        res=server_clock_resolve(noon)
        offsets[str(res['server_utc_offset_hours'])]+=1
    gaps=np.flatnonzero(np.diff(ts)>48*3600000)
    dst=[]
    for y,m,d in ((2018,3,11),(2018,11,4),(2019,3,10),(2019,11,3)):
        point=int(datetime(y,m,d,tzinfo=UTC).timestamp()*1000)
        loc=int(np.searchsorted(ts,point))
        require(loc>0 and loc<len(ts),'DST_WITNESS_MISSING')
        before=int(last[loc-1]);after=int(first[loc]);prev=server_clock_resolve(server_ms_label(ticks['ts'][before]));nxt=server_clock_resolve(server_ms_label(ticks['ts'][after]))
        require(prev['server_utc_offset_hours']!=nxt['server_utc_offset_hours'],'DST_TRANSITION_UNOBSERVED')
        dst.append({'us_dst_date':f'{y:04d}-{m:02d}-{d:02d}','before':prev,'after':nxt})
    result={
      'schema':'QROS_SEED0076_XAU_CLOCK_SESSION_DELTA_AUDIT_1.0','status':'SOURCE_CLOCK_VERIFIED_WITH_2018_PREOPEN_QUARANTINE',
      'scientific_state':'PREREGISTERED_NO_RESULTS','economic_pnl_read':False,'holdout_open':False,'production_grant':False,
      'authority':FROZEN,
      'verified':{'m1_bars':len(b),'dev_rows':len(ticks),'tick_source_index_contiguous_all_bars':True,'tick_to_bar_boundary_all_bars':True,
          'civil_trade_days':len(unique_days),'server_offset_days':dict(offsets),'weekend_or_extended_gaps_gt48h':len(gaps),
          'four_dst_witnesses':dst,'out_of_frozen_XAU_1801_NY_window_M1_bars':len(early),
          'all_out_of_window_bars_at_source_server_0100':True,
          'early_first_server_label':server_ms_label(ts[early[0]]).isoformat(timespec='minutes'),
          'early_last_server_label':server_ms_label(ts[early[-1]]).isoformat(timespec='minutes'),
          'early_source_ticks_in_28_bars':int(np.sum(last[early]-first[early]+1)),
          'early_M1_bars_directly_crossed':early_cross,'early_M1_bars_directly_zero_spread':early_zero,
          'early_bar_source_ranges':[[int(first[i]),int(last[i])] for i in early.tolist()],
          'early_bar_source_labels':[server_ms_label(ts[i]).isoformat(timespec='minutes') for i in early.tolist()]},
      'scope':'Historical DEV source timestamp labels plus frozen V212 18:01 NY XAU session; no PnL or feature alteration.',
      'quarantine':'Quarantine only the 28 verified opening-minute M1 bars and execution paths depending on them pending 2018 historical broker-hours proof; retain all raw ticks/feature caches and frozen masks.',
      'false_pass_risk':'V219 PASS source clock + V212 static opening time can coexist while 28 real raw M1 bars fall 60 seconds before that opening; aggregate/clock PASS cannot imply every quote is admitted to the frozen execution session.',
      'false_fail_risk':'Do not reject all 2018-2019 or all candidates because 28 M1 bars violate an instrument session boundary; affected signal/indicator transitive paths require separate impact mapping.',
      'next_action':'Keep masks and frozen source bytes immutable. Bind official historical 2018-03-07 to 2018-03-08 broker opening-time change, if available; otherwise fail-close economic entry before frozen 18:01 NY and tag any dependency on 28 preopen bars. Rematerialize only missing XAU 24 mask groups and prove semantic+alias roots.'}
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--bars',default='/mnt/data/qros_bar_cache/XAUUSD_M1_BID_BARS.npy')
    p.add_argument('--ticks',default='/mnt/data/qros_data_dev/XAUUSD_DEV_PACKED17_151382388.bin')
    p.add_argument('--anomalies',default='/mnt/data/qros_seed0076_delta_20260922/XAU_QUOTE_ANOMALY_DIRECT_BAR_MEMBERSHIP_17TF.npz')
    p.add_argument('--output',required=True)
    p.add_argument('--hash-dev',action='store_true')
    a=p.parse_args()
    obj=audit(a.bars,a.ticks,a.anomalies,a.hash_dev)
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    data=(json.dumps(obj,sort_keys=True,indent=2,ensure_ascii=False)+'\n').encode()
    tmp=out.with_suffix(out.suffix+'.tmp');tmp.write_bytes(data);tmp.replace(out)
    print(json.dumps({'status':obj['status'],'m1':obj['verified']['m1_bars'],'preopen':obj['verified']['out_of_frozen_XAU_1801_NY_window_M1_bars'],'dst_checks':len(obj['verified']['four_dst_witnesses']),'sha256':hashlib.sha256(data).hexdigest()}))

if __name__=='__main__':main()
