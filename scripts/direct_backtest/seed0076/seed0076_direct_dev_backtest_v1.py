#!/usr/bin/env python3
"""Minimal direct Seed0076 DEV economic smoke: *one preregistered config per side*.
No old-shard artefacts. Same core fractal / 3EMA / CLOSE_BREAK / ONE_SIGNAL_PER_LEVEL.
Exploratory execution overlay is fixed 23:50 Darwinex server flat, not the old
management-parameter universe. Historical DEV becomes EXPOSED on execution.
"""
from __future__ import annotations
import argparse,csv,datetime as dt,hashlib,json,time
from pathlib import Path
import numpy as np
from numba import njit
ROOT=Path('/mnt/data/seed0076_direct_dev')
RAW=ROOT/'XAUUSD_DEV_PACKED17_151382388.bin'
BAR=ROOT/'bars_full/XAUUSD_M1_BID_BARS.npy'
IND=ROOT/'indicators_full/XAUUSD_M1_INDICATORS.npz'
DTYPE=np.dtype([('ts','<i8'),('bid','<i4'),('ask','<i4'),('flags','u1')])
DAY=86400000
OPEN=61*60000
FLAT=(23*60+50)*60000
CLOSE= (23*60+59)*60000
FRI_CLOSE=(23*60+55)*60000
SOURCE_SHA='3ddb3c95acb9284196c5b6db84385271702800209ee33b1b1a2e1bd59cc9ff53'
M1_ARCHIVE_SHA='090800d73cb4258f610747ffbbd3606bfe21cecb787c3dad7bd46254552ef753'

@njit(cache=True)
def fractal_levels(hi,lo,window,tie):
    """Independent implementation of start-of-bar confirmed extrema; index is bar index."""
    n=len(hi); h=np.full(n,np.nan); l=np.full(n,np.nan)
    hid=np.full(n,-1,np.int64);lid=np.full(n,-1,np.int64)
    half=window//2
    for i in range(1,n):
        t=i-1
        if t>=window-1:
            p=t-half; valid_hi=True;valid_lo=True
            for q in range(t-window+1,t+1):
                if q==p:continue
                if tie==0:
                    if q<p:
                        if hi[p]<hi[q]:valid_hi=False
                        if lo[p]>lo[q]:valid_lo=False
                    else:
                        if hi[p]<=hi[q]:valid_hi=False
                        if lo[p]>=lo[q]:valid_lo=False
                else:
                    if hi[p]<=hi[q]:valid_hi=False
                    if lo[p]>=lo[q]:valid_lo=False
            if valid_hi:h[i]=hi[p];hid[i]=p
            if valid_lo:l[i]=lo[p];lid[i]=p
        # carry known state from the previous bar unless a new fractal completed
        if hid[i]<0: h[i]=h[i-1];hid[i]=hid[i-1]
        if lid[i]<0: l[i]=l[i-1];lid[i]=lid[i-1]
    return h,l,hid,lid

@njit(cache=True)
def close_break_signals(cl,first,sh,sl,hid,lid,ema_fast,ema_mid,ema_slow,side):
    n=len(cl); ix=np.empty(n,np.int64); stops=np.empty(n,np.int32); outn=0; consumed=-9999999
    for bi in range(2,n):
        t=bi-1;prev=cl[t-1];cur=cl[t]
        if side==1:
            level=sh[bi];ident=hid[bi];stop=sl[bi]
            trend=ema_fast[t]>ema_mid[t] and ema_mid[t]>ema_slow[t]
            crossed=prev<=level and cur>level
        else:
            level=sl[bi];ident=lid[bi];stop=sh[bi]
            trend=ema_fast[t]<ema_mid[t] and ema_mid[t]<ema_slow[t]
            crossed=prev>=level and cur<level
        if np.isnan(level) or np.isnan(stop) or ident<0 or ident==consumed:continue
        if crossed:
            # The raw candidate consumes its level *before* subsequent trend filtering.
            consumed=ident
            if trend:
                ix[outn]=first[bi]; stops[outn]=int(stop);outn+=1
    return ix[:outn],stops[:outn]

@njit(cache=True)
def simulate(ticks,signal_ix,signal_side,signal_stop,signal_cfg,num_max=3):
    """Sequential per-asset scheduler; all inputs fixed before economic observation."""
    n=len(ticks);m=len(signal_ix)
    # 11 cols: cfg_idx,side,signal_ix,entry_ix,exit_ix,entry_px,stop_px,exit_px,R,reason,day
    trades=np.empty((m,11),np.float64);nt=0
    rejected=np.zeros(7,np.int64) # past-signal, outside-session, cap, bad-entry, stop geometry, missing-exit, outside-quote
    active_until=-1;current_day=-1;daily=0
    unresolved_days=np.empty(m,np.int64);unresolved_n=0
    for j in range(m):
        si=signal_ix[j];side=signal_side[j];stop=signal_stop[j]
        if si<=active_until:rejected[0]+=1;continue
        if si<0 or si>=n:rejected[6]+=1;continue
        day=ticks['ts'][si]//DAY; tod=ticks['ts'][si]%DAY
        weekday=(day+3)%7 # 1970-01-01 was Thursday
        if weekday>4 or tod<OPEN or tod>=FLAT:rejected[1]+=1;continue
        if day!=current_day:current_day=day;daily=0
        if daily>=num_max:rejected[2]+=1;continue
        session_end=(day*DAY)+(FRI_CLOSE if weekday==4 else CLOSE)
        close_trigger=(day*DAY)+FLAT
        # Limit signal to next M1 bucket; entry at first actually usable quote
        entry_ix=-1; bar_end=(ticks['ts'][si]//60000+1)*60000
        for k in range(si,n):
            if ticks['ts'][k]>=bar_end:break
            bid=ticks['bid'][k];ask=ticks['ask'][k]
            if bid>0 and ask>bid:
                entry_ix=k;break
        if entry_ix<0:rejected[3]+=1;continue
        entry=ticks['ask'][entry_ix] if side==1 else ticks['bid'][entry_ix]
        risk=entry-stop if side==1 else stop-entry
        # A stop already breached by the executable exit quote at entry is not an order.
        bid0=ticks['bid'][entry_ix];ask0=ticks['ask'][entry_ix]
        if risk<=0 or (side==1 and bid0<=stop) or (side==-1 and ask0>=stop):
            rejected[4]+=1;continue
        exit_ix=-1;outpx=0;reason=0
        # stop before scheduled time exit when both are reached on the same quote
        for k in range(entry_ix,n):
            tk=ticks['ts'][k]
            if tk>=session_end or tk//DAY!=day:break
            bid=ticks['bid'][k];ask=ticks['ask'][k]
            if bid<=0 or ask<=bid:continue
            mark=bid if side==1 else ask
            if (side==1 and mark<=stop) or (side==-1 and mark>=stop):
                exit_ix=k;outpx=mark;reason=1;break
            if tk>=close_trigger:
                exit_ix=k;outpx=mark;reason=2;break
        if exit_ix<0:
            # Fail this individual trade closed; never mark a fabricated exit
            rejected[5]+=1;unresolved_days[unresolved_n]=day;unresolved_n+=1;continue
        realized=(outpx-entry)/risk if side==1 else (entry-outpx)/risk
        trades[nt]=[signal_cfg[j],side,si,entry_ix,exit_ix,entry,stop,outpx,realized,reason,day]
        nt+=1;daily+=1;active_until=exit_ix
    return trades[:nt],rejected,unresolved_days[:unresolved_n]

def config(side):
    base={'asset':'XAUUSD','side':'BUY' if side==1 else 'SELL','timeframe':'M1','fractal_window':3,'tie_policy':'SOURCE_ASYMMETRIC','rearm_mode':'ONE_SIGNAL_PER_LEVEL','trigger':'CLOSE_BREAK'}
    filters={'TREND':{'mode':'EMA_ORDER','ema_triple':[9,20,50]}}
    serialized=json.dumps({**base,'filters':filters},sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
    return {'definition':{**base,'filters':filters},'semantic_config_id':hashlib.sha256(serialized).hexdigest()}

def sha_file(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()

def run(out_dir=ROOT/'run_v1'):
    out_dir=Path(out_dir);out_dir.mkdir(parents=True,exist_ok=True)
    if RAW.stat().st_size!=2573500596 or sha_file(RAW)!=SOURCE_SHA:raise RuntimeError('RAW_DEV_AUTHORITY_FAIL_CLOSED')
    z=np.load(IND,allow_pickle=False)
    bars=np.load(BAR,mmap_mode='r',allow_pickle=False)
    ticks=np.memmap(RAW,dtype=DTYPE,mode='r')
    if len(bars)!=681772 or len(ticks)!=151382388:raise RuntimeError('CARRIER_COUNT_MISMATCH')
    fast=z['EMA9'];mid=z['EMA20'];slow=z['EMA50']
    start=time.perf_counter()
    sh,sl,hid,lid=fractal_levels(bars['high_bid'].astype(np.float64),bars['low_bid'].astype(np.float64),3,0)
    t_fractal=time.perf_counter()-start
    a=[];side_rows=[];stop_rows=[];cfg_rows=[];signal_counts={}
    for side in (1,-1):
        si,stop=close_break_signals(bars['close_bid'],bars['first_source_index'],sh,sl,hid,lid,fast,mid,slow,side)
        a.append(si);side_rows.append(np.full(len(si),side,np.int8));stop_rows.append(stop);cfg_rows.append(np.full(len(si),0 if side==1 else 1,np.int8))
        signal_counts['BUY' if side==1 else 'SELL']=int(len(si))
    sig=np.concatenate(a);sides=np.concatenate(side_rows);stops=np.concatenate(stop_rows);cfgs=np.concatenate(cfg_rows)
    order=np.lexsort((cfgs,sig));sig=sig[order];sides=sides[order];stops=stops[order];cfgs=cfgs[order]
    t_sig=time.perf_counter()-start-t_fractal
    trades,rejected,unresolved_days=simulate(ticks,sig,sides,stops,cfgs)
    t_exec=time.perf_counter()-start-t_fractal-t_sig
    rs=trades[:,8];pos=rs[rs>0].sum();neg=-rs[rs<0].sum()
    cum=np.cumsum(rs);running=np.maximum.accumulate(np.r_[0.0,cum]);maxdd=float(np.max(running[1:]-cum)) if len(cum) else 0.0
    years={}
    for year in (2018,2019):
        fromdate=(dt.datetime(year,1,1)-dt.datetime(1970,1,1)).days
        todate=(dt.datetime(year+1,1,1)-dt.datetime(1970,1,1)).days
        mask=(trades[:,10]>=fromdate)&(trades[:,10]<todate)
        years[str(year)]={'trades':int(mask.sum()),'R':float(np.sum(rs[mask]))}
    out_csv=out_dir/'trades_exploratory_dev.csv'
    with out_csv.open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['config_id','side','signal_source_tick','entry_source_tick','exit_source_tick','entry_cents','stop_cents','exit_cents','R','exit_reason','server_civil_date'])
        cs=[config(1)['semantic_config_id'],config(-1)['semantic_config_id']]
        for row in trades:
            w.writerow([cs[int(row[0])],'BUY' if row[1]==1 else 'SELL',*[int(v) for v in row[2:8]],repr(float(row[8])),'STOP' if row[9]==1 else 'PLANNED_FLAT',str((dt.date(1970,1,1)+dt.timedelta(days=int(row[10]))))])
    s={
       'schema':'SEED0076_DIRECT_EXPLORATORY_DEV_BACKTEST_V1','asset':'XAUUSD','timeframe':'M1','period':'2018-2019_DEV_EXPOSED','old_60_shards_inspected':False,
       'seed':'WEB_SEED_0076','configs':[config(1),config(-1)],'source_sha256':SOURCE_SHA,'m1_frozen_archive_sha256':M1_ARCHIVE_SHA,
       'execution_profile':'EXPLORATORY_STOP_OPPOSITE_FRACTAL_NO_TP_PLANNED_FLAT_23_50_SERVER','execution_quote':'BUY_ASK_BID_EXIT__SELL_BID_ASK_EXIT',
       'session':'01:01--23:50 Darwinex server; last daily close before 23:59, Friday 23:55; historical 01:00 anomalies inadmissible',
       'fees':'NO_BROKER_COMMISSION_INCLUDED; actual observed variable Bid/Ask spread included; NOT_FINAL_NET_PNL',
       'execution':'first valid positive-spread quote in signal-available M1 bar; stop takes priority; actual first available quote on gaps; max three new positions per server day combined across sides; one active position per asset',
       'generated_signals':signal_counts,'candidate_event_count':int(len(sig)),'trades':int(len(rs)),'rejected_counts':dict(zip(['already_active','out_of_session','three_daily','no_usable_entry_quote','nonpositive_risk','no_usable_exit_quote','invalid_source_index'],map(int,rejected))),
       'gross_R_including_historical_spread':float(rs.sum()),'expectancy_R':float(rs.mean()) if len(rs) else None,'PF_R':float(pos/neg) if neg else None,'max_drawdown_R':maxdd,'annual':years,
       'stop_count':int(np.sum(trades[:,9]==1)),'planned_flat_count':int(np.sum(trades[:,9]==2)),'timings_seconds':{'fractals':t_fractal,'signals':t_sig,'sequential_execution':t_exec,'total_excluding_dev_hash_read':time.perf_counter()-start},
       'holdout_open':False,'economic_result_status':'EXPLORATORY_DEV_EXPOSED_NOT_GATE_A','full_universe_scored':False,
       'unresolved_server_dates':sorted(set(str(dt.date(1970,1,1)+dt.timedelta(days=int(d))) for d in unresolved_days)),
       'resolved_trades_after_unresolved_unsafe':True,
       'trades_file':str(out_csv.name),'trades_sha256':sha_file(out_csv)}
    if rejected[5]>0:
        # Preserve forensic trades in the previous run, but don't publish a selection-grade score.
        for key in ('gross_R_including_historical_spread','expectancy_R','PF_R','max_drawdown_R','annual','stop_count','planned_flat_count'):
            s[key]=None
        s['economic_result_status']='INVALID_UNRESOLVED_EXIT_SESSIONS_AND_SEQUENCE'
    path=out_dir/'results_exploratory_dev.json';path.write_text(json.dumps(s,sort_keys=True,indent=2)+'\n')
    print(json.dumps({'status':s['economic_result_status'],'signals':signal_counts,'trades_diagnostic_only':s['trades'],'R':s['gross_R_including_historical_spread'],'PF_R':s['PF_R'],'unresolved_exits':s['rejected_counts']['no_usable_exit_quote'],'unresolved_dates':s['unresolved_server_dates'],'seconds':s['timings_seconds'],'trades_sha256':s['trades_sha256']},sort_keys=True))
    return s

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out-dir',default=str(ROOT/'run_v1'));a=p.parse_args();run(Path(a.out_dir))
