#!/usr/bin/env python3
"""Independent standard-library QDATA v1 + replay reference.
Correctness oracle only; intentionally not optimized and shares no runtime code with C++.
"""
from __future__ import annotations
import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path
import sys

HEX=set('0123456789abcdef')

def sha(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1<<16),b''): h.update(b)
    return h.hexdigest()

def parse_kv(path: Path, magic: str, allowed: set[str]) -> dict[str,str]:
    raw=path.read_text(encoding='utf-8').splitlines()
    if not raw or raw[0] != magic: raise ValueError('magic/version mismatch')
    out={}
    for line in raw[1:]:
        if not line or line.startswith('#'): continue
        if '=' not in line: raise ValueError('invalid kv line')
        k,v=line.split('=',1)
        if not k or not v or k not in allowed or k in out: raise ValueError('bad/duplicate key')
        out[k]=v
    if set(out)!=allowed: raise ValueError('missing/extra key')
    return out

def valid_hash(x:str)->bool: return len(x)==64 and all(c in HEX for c in x)

@dataclass(frozen=True)
class Tick: seq:int; ts:int; day:int; bid:int; ask:int
@dataclass(frozen=True)
class Session: day:int; openseq:int; closeseq:int; opents:int; closets:int; offset:int

MAN_KEYS={
'authority_id','symbol','dataset_sha256','sessions_sha256','schema','expected_rows','first_seq','last_seq','first_ts_ns','last_ts_ns',
'price_decimals','point_size_u','tick_size_u','timezone_name','timezone_status','timezone_evidence_sha256','source_kind','source_id','source_evidence_sha256','purpose',
'session_policy_id','max_zero_spread_ppm','allow_nonpositive_prices'}
INTENT2_KEYS={'strategy_id','data_sha256','side','signal_seq','signal_ts_ns','signal_session_day','session_close_seq','stop_distance_u','target_distance_u',
'qdata_manifest_sha256','sessions_sha256','event_contract_sha256','execution_policy_sha256'}
TZ_KEYS={'authority_id','timezone_name','method','coverage_first_day','coverage_last_day','sessions_sha256','observed_offset_transitions','max_offset_jump_seconds','status'}
SRC_KEYS={'authority_id','source_kind','source_id','method','dataset_sha256','sessions_sha256','status'}

def load_manifest(path:Path):
    m=parse_kv(path,'QROS_QDATA_MANIFEST_V1',MAN_KEYS)
    for k in ['dataset_sha256','sessions_sha256','timezone_evidence_sha256','source_evidence_sha256']:
        if not valid_hash(m[k]): raise ValueError('bad hash')
    for k in ['expected_rows','first_seq','last_seq','first_ts_ns','last_ts_ns','price_decimals','point_size_u','tick_size_u','max_zero_spread_ppm','allow_nonpositive_prices']:
        m[k]=int(m[k])
    if m['schema']!='TICKS_CSV_V1': raise ValueError('schema')
    return m

def load_sessions(path:Path):
    with path.open(newline='') as f:
        r=csv.DictReader(f)
        expect=['session_day','open_seq','close_seq','open_ts_ns','close_ts_ns','utc_offset_seconds']
        if r.fieldnames!=expect: raise ValueError('session header')
        rows=[]
        for x in r:
            if None in x or any(v=='' for v in x.values()): raise ValueError('blank field')
            rows.append(Session(*(int(x[k]) for k in expect)))
    if not rows: raise ValueError('no sessions')
    return rows

def load_ticks(path:Path):
    with path.open(newline='') as f:
        r=csv.DictReader(f)
        expect=['seq','ts_ns','session_day','bid_u','ask_u']
        if r.fieldnames!=expect: raise ValueError('tick header')
        rows=[]
        for x in r:
            if None in x or any(v=='' for v in x.values()): raise ValueError('blank field')
            rows.append(Tick(*(int(x[k]) for k in expect)))
    return rows

def audit(ticks_path:Path,sessions_path:Path,manifest_path:Path,tz_evidence:Path,src_evidence:Path):
    m=load_manifest(manifest_path); sessions=load_sessions(sessions_path); ticks=load_ticks(ticks_path)
    tz=parse_kv(tz_evidence,'QROS_TIMEZONE_EVIDENCE_V1',TZ_KEYS)
    src=parse_kv(src_evidence,'QROS_SOURCE_EVIDENCE_V1',SRC_KEYS)
    for k in ['coverage_first_day','coverage_last_day','observed_offset_transitions','max_offset_jump_seconds']: tz[k]=int(tz[k])
    dsha=sha(ticks_path); ssha=sha(sessions_path); msha=sha(manifest_path)
    integrity=(dsha==m['dataset_sha256'] and ssha==m['sessions_sha256'] and sha(tz_evidence)==m['timezone_evidence_sha256'] and sha(src_evidence)==m['source_evidence_sha256'])
    if len(ticks)!=m['expected_rows'] or not ticks: integrity=False
    if ticks and (ticks[0].seq!=m['first_seq'] or ticks[-1].seq!=m['last_seq'] or ticks[0].ts!=m['first_ts_ns'] or ticks[-1].ts!=m['last_ts_ns']): integrity=False
    zero=0; prev=None
    for t in ticks:
        if t.ask==t.bid: zero+=1
        if t.ask<t.bid or (not m['allow_nonpositive_prices'] and (t.bid<=0 or t.ask<=0)) or t.ts<=0: integrity=False
        if t.bid % m['tick_size_u'] or t.ask % m['tick_size_u']: integrity=False
        if prev and (t.seq<=prev.seq or t.ts<prev.ts or t.day<prev.day): integrity=False
        prev=t
    if len(sessions)==0: integrity=False
    transitions=0; max_jump=0
    for i,sess in enumerate(sessions):
        if sess.openseq<=0 or sess.closeseq<sess.openseq or sess.opents<=0 or sess.closets<sess.opents or not (-64800<=sess.offset<=64800): integrity=False
        if i:
            prevs=sessions[i-1]
            if sess.day<=prevs.day or sess.openseq<=prevs.closeseq or sess.opents<prevs.closets: integrity=False
            if sess.offset!=prevs.offset:
                transitions+=1; max_jump=max(max_jump,abs(sess.offset-prevs.offset))
    by_seq={t.seq:t for t in ticks}
    for sess in sessions:
        if sess.openseq not in by_seq or sess.closeseq not in by_seq: integrity=False; continue
        if by_seq[sess.openseq].ts!=sess.opents or by_seq[sess.closeseq].ts!=sess.closets: integrity=False
        for t in ticks:
            if sess.openseq<=t.seq<=sess.closeseq and (t.day!=sess.day or not(sess.opents<=t.ts<=sess.closets)): integrity=False
    covered=set()
    for sess in sessions: covered.update(range(sess.openseq,sess.closeseq+1))
    if any(t.seq not in covered for t in ticks): integrity=False
    ppm=(zero*1_000_000)//len(ticks) if ticks else 0
    if ppm>m['max_zero_spread_ppm']: integrity=False
    tz_sem=(tz['authority_id']==m['authority_id'] and tz['timezone_name']==m['timezone_name'] and tz['sessions_sha256']==ssha and
            tz['coverage_first_day']==sessions[0].day and tz['coverage_last_day']==sessions[-1].day and
            tz['observed_offset_transitions']==transitions and tz['max_offset_jump_seconds']==max_jump and tz['status']==m['timezone_status'])
    src_sem=(src['authority_id']==m['authority_id'] and src['source_kind']==m['source_kind'] and src['source_id']==m['source_id'] and
             src['dataset_sha256']==dsha and src['sessions_sha256']==ssha)
    integrity=integrity and tz_sem and src_sem
    tz_research=(m['timezone_status']=='VERIFIED' and tz['status']=='VERIFIED' and not tz['method'].startswith('SYNTHETIC'))
    src_research=(src['status']=='VERIFIED' and not src['method'].startswith('SYNTHETIC') and m['source_kind']!='SYNTHETIC_TEST')
    test_ready=integrity and m['purpose']=='TEST_ONLY' and m['timezone_status']=='TEST_ONLY' and tz['status']=='TEST_ONLY' and src['status']=='TEST_ONLY'
    research_ready=False  # v0.3 production evidence verifier intentionally fail-closed
    return {'manifest':m,'ticks':ticks,'sessions':sessions,'dsha':dsha,'ssha':ssha,'msha':msha,'integrity':integrity,'test_ready':test_ready,'research_ready':research_ready}

def load_intent(path:Path):
    x=parse_kv(path,'QROS_INTENT_V2',INTENT2_KEYS)
    for k in ['data_sha256','qdata_manifest_sha256','sessions_sha256','event_contract_sha256','execution_policy_sha256']:
        if not valid_hash(x[k]): raise ValueError('bad intent hash')
    for k in ['signal_seq','signal_ts_ns','signal_session_day','session_close_seq','stop_distance_u','target_distance_u']: x[k]=int(x[k])
    return x

def replay(a,x):
    ticks=a['ticks']; by_seq={t.seq:i for i,t in enumerate(ticks)}
    if x['data_sha256']!=a['dsha'] or x['qdata_manifest_sha256']!=a['msha'] or x['sessions_sha256']!=a['ssha']: raise ValueError('authority bind')
    si=by_seq.get(x['signal_seq']); ci=by_seq.get(x['session_close_seq'])
    if si is None or ci is None or ci<=si: return None,'DATA_ERROR'
    sig=ticks[si]; close=ticks[ci]
    if sig.ts!=x['signal_ts_ns'] or sig.day!=x['signal_session_day'] or close.day!=x['signal_session_day']: return None,'DATA_ERROR'
    auth=[s for s in a['sessions'] if s.day==x['signal_session_day']]
    if len(auth)!=1 or auth[0].closeseq!=x['session_close_seq']: raise ValueError('session close bind')
    ei=None
    for i in range(si+1,ci+1):
        t=ticks[i]
        if t.day==x['signal_session_day'] and t.seq>x['signal_seq'] and t.ts>=x['signal_ts_ns'] and t.ask>t.bid:
            ei=i; break
    side=x['side']
    if ei is None: return [x['strategy_id'],0,side,0,0,0,0,0,0,0,'NO_ENTRY',0,0,0],None
    t=ticks[ei]; ep=t.ask if side=='BUY' else t.bid
    stop=ep-x['stop_distance_u'] if side=='BUY' else ep+x['stop_distance_u']
    target=ep+x['target_distance_u'] if side=='BUY' else ep-x['target_distance_u']
    last=None
    for i in range(ei+1,ci+1):
        z=ticks[i]
        if z.day!=t.day: return None,'DATA_ERROR'
        if z.ask<=z.bid: continue
        last=i
        if side=='BUY':
            if z.bid<=stop: return [x['strategy_id'],1,side,t.seq,t.ts,t.day,ep,z.seq,z.ts,z.bid,'SL',z.bid-ep,z.bid-ep,x['stop_distance_u']],None
            if z.bid>=target: return [x['strategy_id'],1,side,t.seq,t.ts,t.day,ep,z.seq,z.ts,z.bid,'TP',z.bid-ep,z.bid-ep,x['stop_distance_u']],None
        else:
            if z.ask>=stop: return [x['strategy_id'],1,side,t.seq,t.ts,t.day,ep,z.seq,z.ts,z.ask,'SL',ep-z.ask,ep-z.ask,x['stop_distance_u']],None
            if z.ask<=target: return [x['strategy_id'],1,side,t.seq,t.ts,t.day,ep,z.seq,z.ts,z.ask,'TP',ep-z.ask,ep-z.ask,x['stop_distance_u']],None
    if last is None: return [x['strategy_id'],1,side,t.seq,t.ts,t.day,ep,0,0,0,'UNRESOLVED_CLOSE',0,0,0],None
    z=ticks[last]; xp=z.bid if side=='BUY' else z.ask; pnl=xp-ep if side=='BUY' else ep-xp
    return [x['strategy_id'],1,side,t.seq,t.ts,t.day,ep,z.seq,z.ts,xp,'SESSION_CLOSE',pnl,pnl,x['stop_distance_u']],None

def main(argv):
    if len(argv)!=8:
        print('usage: qdata_reference.py ticks sessions manifest tz_evidence source_evidence intent mode',file=sys.stderr); return 2
    a=audit(*(Path(x) for x in argv[1:6]))
    if argv[7]=='audit':
        print(f"integrity={int(a['integrity'])} test_ready={int(a['test_ready'])} research_ready={int(a['research_ready'])}"); return 0 if (a['research_ready'] or a['test_ready']) else 4
    if not (a['research_ready'] or a['test_ready']): return 4
    x=load_intent(Path(argv[6])); row,err=replay(a,x)
    if err: print(err); return 4
    print('strategy_id,entered,side,entry_seq,entry_ts_ns,entry_day,entry_price_u,exit_seq,exit_ts_ns,exit_price_u,exit_reason,pnl_u,r_num,r_den')
    print(','.join(map(str,row)))
    return 0
if __name__=='__main__': raise SystemExit(main(sys.argv))
