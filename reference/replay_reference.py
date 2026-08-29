#!/usr/bin/env python3
"""Independent, standard-library-only reference for parity checks. Not performance code."""
import csv, sys
from dataclasses import dataclass

@dataclass(frozen=True)
class Tick:
    seq:int; ts_ns:int; session_day:int; bid_u:int; ask_u:int

def load_ticks(path):
    out=[]
    with open(path,newline='') as f:
        r=csv.DictReader(f)
        if r.fieldnames != ['seq','ts_ns','session_day','bid_u','ask_u']:
            raise ValueError('unexpected ticks header')
        for x in r:
            out.append(Tick(*(int(x[k]) for k in r.fieldnames)))
    return out

def load_intent(path):
    with open(path) as f:
        if f.readline().rstrip('\n')!='QROS_INTENT_V1': raise ValueError('intent magic/version mismatch')
        kv={}
        allowed={'strategy_id','data_sha256','side','signal_seq','signal_ts_ns','signal_session_day','session_close_seq','stop_distance_u','target_distance_u'}
        for raw in f:
            line=raw.strip()
            if not line or line.startswith('#'): continue
            k,v=line.split('=',1)
            if k not in allowed or k in kv: raise ValueError('bad/duplicate key')
            kv[k]=v
        if set(kv)!=allowed: raise ValueError('missing key')
    for k in ['signal_seq','signal_ts_ns','signal_session_day','session_close_seq','stop_distance_u','target_distance_u']:
        kv[k]=int(kv[k])
    return kv

def replay(ticks,x):
    for i,t in enumerate(ticks):
        if t.ask_u<t.bid_u: return None,'DATA_ERROR'
        if i and (t.seq<=ticks[i-1].seq or t.ts_ns<ticks[i-1].ts_ns or t.session_day<ticks[i-1].session_day): return None,'DATA_ERROR'
    by_seq={t.seq:i for i,t in enumerate(ticks)}
    si=by_seq.get(x['signal_seq']); ci=by_seq.get(x['session_close_seq'])
    if si is None or ci is None or x['session_close_seq']<=x['signal_seq'] or ci<=si: return None,'DATA_ERROR'
    sig=ticks[si]; close=ticks[ci]
    if sig.ts_ns!=x['signal_ts_ns'] or sig.session_day!=x['signal_session_day'] or close.session_day!=x['signal_session_day']:
        return None,'DATA_ERROR'
    ei=None
    for i in range(si+1,ci+1):
        t=ticks[i]
        if t.session_day==x['signal_session_day'] and t.seq>x['signal_seq'] and t.ts_ns>=x['signal_ts_ns'] and t.ask_u>t.bid_u:
            ei=i; break
    side=x['side']
    if ei is None:
        return [x['strategy_id'],0,side,0,0,0,0,0,0,0,'NO_ENTRY',0,0,0],None
    t=ticks[ei]; ep=t.ask_u if side=='BUY' else t.bid_u
    stop=ep-x['stop_distance_u'] if side=='BUY' else ep+x['stop_distance_u']
    target=ep+x['target_distance_u'] if side=='BUY' else ep-x['target_distance_u']
    last=None
    for i in range(ei+1,ci+1):
        z=ticks[i]
        if z.session_day!=t.session_day: return None,'DATA_ERROR'
        if z.ask_u<=z.bid_u: continue
        last=i
        if side=='BUY':
            if z.bid_u<=stop: return [x['strategy_id'],1,side,t.seq,t.ts_ns,t.session_day,ep,z.seq,z.ts_ns,z.bid_u,'SL',z.bid_u-ep,z.bid_u-ep,x['stop_distance_u']],None
            if z.bid_u>=target: return [x['strategy_id'],1,side,t.seq,t.ts_ns,t.session_day,ep,z.seq,z.ts_ns,z.bid_u,'TP',z.bid_u-ep,z.bid_u-ep,x['stop_distance_u']],None
        else:
            if z.ask_u>=stop: return [x['strategy_id'],1,side,t.seq,t.ts_ns,t.session_day,ep,z.seq,z.ts_ns,z.ask_u,'SL',ep-z.ask_u,ep-z.ask_u,x['stop_distance_u']],None
            if z.ask_u<=target: return [x['strategy_id'],1,side,t.seq,t.ts_ns,t.session_day,ep,z.seq,z.ts_ns,z.ask_u,'TP',ep-z.ask_u,ep-z.ask_u,x['stop_distance_u']],None
    if last is None:
        return [x['strategy_id'],1,side,t.seq,t.ts_ns,t.session_day,ep,0,0,0,'UNRESOLVED_CLOSE',0,0,0],None
    z=ticks[last]; xp=z.bid_u if side=='BUY' else z.ask_u
    pnl=xp-ep if side=='BUY' else ep-xp
    return [x['strategy_id'],1,side,t.seq,t.ts_ns,t.session_day,ep,z.seq,z.ts_ns,xp,'SESSION_CLOSE',pnl,pnl,x['stop_distance_u']],None

def main():
    ticks=load_ticks(sys.argv[1]); x=load_intent(sys.argv[2]); row,err=replay(ticks,x)
    if err: print(err); return 4
    print('strategy_id,entered,side,entry_seq,entry_ts_ns,entry_day,entry_price_u,exit_seq,exit_ts_ns,exit_price_u,exit_reason,pnl_u,r_num,r_den')
    print(','.join(map(str,row)))
    return 0
if __name__=='__main__': raise SystemExit(main())
